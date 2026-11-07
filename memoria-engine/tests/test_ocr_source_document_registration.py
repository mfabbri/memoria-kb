from __future__ import annotations

import hashlib
import io
import json
from contextlib import closing, redirect_stdout
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.document_structure import reconstruct_document_structure, render_document_structure_markdown
from caduti_fonti_report.document_analysis.ocr_source_document_registration import register_ocr_source_document, source_document_id
from caduti_fonti_report.memoria_cli import main


class OcrSourceDocumentRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root / "original.tif"
        self.original.write_bytes(b"synthetic original bytes")
        self.digest = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.document_id = source_document_id("offline", self.original, self.digest)
        self.registry = self.root / "sources.yaml"
        self.registry.write_text("sources:\n- id: offline\n", encoding="utf-8")
        self.evidence = {"@type": "OcrPageEvidence", "schema_version": "1.0", "page_id": "p1",
            "source_document_id": self.document_id, "source_image_hash": self.digest,
            "transform_id": "raw", "engine": "synthetic", "language": "deu", "model": {"name": "offline"},
            "source_page": {"page_id": "p1", "page_index": 1}, "image_transform": None,
            "regions": [{"region_id": "r1", "text": "1. Synthetic text", "geometry": {"bbox": [0, 0, 40, 10]}}]}
        structure = reconstruct_document_structure(evidence=self.evidence, profile="numbered_report")
        self.write("evidence.json", self.evidence)
        self.write("structure.json", structure.to_dict())
        (self.root / "page.md").write_bytes(render_document_structure_markdown(structure).encode("utf-8"))
        self.manifest = {"@type": "OcrSourceDocumentRegistration", "schema_version": "1.0", "source_id": "offline",
            "source_document_id": self.document_id, "local_path": "original.tif", "content_hash": self.digest,
            "title": "Synthetic source", "media_type": "image/tiff", "access_date": "2026-11-01T00:00:00Z",
            "workflow_status": "provisional_auto_validated", "review_status": "unreviewed", "pages": [{
                "page_id": "p1", "source_document_id": self.document_id, "source_page": self.evidence["source_page"],
                "source_image": self.ref("original.tif"), "evidence": self.ref("evidence.json"),
                "structure": self.ref("structure.json"), "markdown": self.ref("page.md"),
                "transcription_validation_status": "provisional_auto_validated", "review_status": "unreviewed"}]}
        self.manifest_path = self.root / "manifest.json"
        self.database = self.root / "new" / "evidence.sqlite"
        self.save()

    def write(self, name, payload):
        (self.root / name).write_text(json.dumps(payload), encoding="utf-8")

    def ref(self, name):
        return {"path": name, "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}

    def save(self):
        self.write("manifest.json", self.manifest)

    def run_registration(self, apply=False):
        return register_ocr_source_document(manifest_path=self.manifest_path, database_path=self.database,
            sources_registry_path=self.registry, apply=apply)

    def test_preview_no_directory_then_apply_round_trip_retry_no_claims(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        preview = self.run_registration()
        self.assertEqual(preview["status"], "would_register")
        self.assertFalse(self.database.parent.exists())
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertEqual(self.run_registration(True)["status"], "registered")
        database_bytes = self.database.read_bytes()
        self.assertEqual(self.run_registration(True)["status"], "already_registered")
        self.assertEqual(self.run_registration()["status"], "already_registered")
        self.assertEqual(database_bytes, self.database.read_bytes())
        with closing(sqlite3.connect(self.database)) as connection:
            payload = json.loads(connection.execute("SELECT payload_json FROM source_documents").fetchone()[0])
            self.assertEqual(connection.execute("SELECT count(*) FROM source_documents").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM search_runs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM evidence_claims").fetchone()[0], 0)
        self.assertEqual(payload["content_hash"], self.digest)
        self.assertEqual(payload["local_path"], str(self.original.resolve()))
        self.assertEqual(payload["raw_text"], "")
        self.assertEqual(payload["media_type"], "image/tiff")
        metadata = payload["metadata"]
        self.assertEqual(metadata["ocr_artifact_manifest_sha256"], self.ref("manifest.json")["sha256"])
        self.assertEqual(metadata["ocr_review_status"], "unreviewed")
        self.assertEqual(metadata["ocr_workflow_status"], "provisional_auto_validated")
        for flag in ("machine_pass", "human_verified", "claim_extraction_allowed"):
            self.assertFalse(preview[flag])
            self.assertEqual(metadata[flag], "false")

    def test_divergent_retry_does_not_overwrite_or_add_audit_run(self):
        self.run_registration(True)
        before = self.database.read_bytes()
        self.manifest["title"] = "Changed title"
        self.save()
        for apply in (False, True):
            with self.assertRaisesRegex(ValueError, "divergent"):
                self.run_registration(apply)
        self.assertEqual(before, self.database.read_bytes())

    def test_corrupt_original_and_derivatives_rejected_before_store_creation(self):
        for name in ("original.tif", "evidence.json", "structure.json", "page.md"):
            path = self.root / name
            original = path.read_bytes()
            path.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                self.run_registration(True)
            self.assertFalse(self.database.exists())
            path.write_bytes(original)

    def test_hash_valid_structure_from_different_evidence_is_rejected(self):
        payload = json.loads((self.root / "structure.json").read_text())
        payload["source_evidence"]["engine"] = "different"
        self.write("structure.json", payload)
        self.manifest["pages"][0]["structure"] = self.ref("structure.json")
        self.save()
        with self.assertRaisesRegex(ValueError, "DocumentStructure"):
            self.run_registration(True)
        self.assertFalse(self.database.exists())

    def test_hash_valid_markdown_from_different_structure_is_rejected(self):
        (self.root / "page.md").write_text("unrelated text", encoding="utf-8")
        self.manifest["pages"][0]["markdown"] = self.ref("page.md")
        self.save()
        with self.assertRaisesRegex(ValueError, "Markdown"):
            self.run_registration(True)

    def test_binding_and_promotion_attempts_are_rejected(self):
        mutations = [("source_document_id", "wrong"), ("source_id", "missing"),
            ("review_status", "verified"), ("machine_pass", True), ("human_verified", True),
            ("claim_extraction_allowed", True), ("access_date", "2026-11-01")]
        for key, value in mutations:
            original = self.manifest.get(key)
            self.manifest[key] = value
            self.save()
            with self.assertRaises(ValueError, msg=key):
                self.run_registration(True)
            self.assertFalse(self.database.exists())
            if original is None:
                del self.manifest[key]
            else:
                self.manifest[key] = original
        self.save()

    def test_evidence_document_binding_and_duplicate_page_rejected(self):
        self.evidence["source_document_id"] = "wrong"
        self.write("evidence.json", self.evidence)
        self.manifest["pages"][0]["evidence"] = self.ref("evidence.json")
        self.save()
        with self.assertRaisesRegex(ValueError, "document binding"):
            self.run_registration(True)
        self.evidence["source_document_id"] = self.document_id
        self.write("evidence.json", self.evidence)
        self.manifest["pages"][0]["evidence"] = self.ref("evidence.json")
        self.manifest["pages"].append(self.manifest["pages"][0].copy())
        self.save()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_registration(True)

    def test_cli_preview_and_apply(self):
        args = ["documents", "register-ocr-source", "--manifest", str(self.manifest_path),
            "--database", str(self.database), "--sources-registry", str(self.registry)]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "would_register")
        self.assertFalse(self.database.exists())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args + ["--apply"]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "registered")

    def test_derived_raster_requires_transformation_linking_both_hashes(self):
        raster = self.root / "page.png"
        raster.write_bytes(b"synthetic raster")
        raster_ref = self.ref("page.png")
        self.evidence["source_image_hash"] = raster_ref["sha256"]
        structure = reconstruct_document_structure(evidence=self.evidence, profile="numbered_report")
        self.write("evidence.json", self.evidence)
        self.write("structure.json", structure.to_dict())
        (self.root / "page.md").write_bytes(render_document_structure_markdown(structure).encode("utf-8"))
        page = self.manifest["pages"][0]
        page.update(source_image=raster_ref, evidence=self.ref("evidence.json"),
            structure=self.ref("structure.json"), markdown=self.ref("page.md"))
        self.save()
        with self.assertRaisesRegex(ValueError, "source_image_transform"):
            self.run_registration(True)
        self.assertFalse(self.database.exists())
        page["source_image_transform"] = {"original_sha256": self.digest,
            "source_image_sha256": raster_ref["sha256"], "description": "Offline synthetic rasterization"}
        self.save()
        result = self.run_registration(True)
        self.assertEqual(result["status"], "registered")
        self.assertEqual(result["source_document"]["content_hash"], self.digest)
        self.assertNotEqual(result["source_document"]["content_hash"], raster_ref["sha256"])


if __name__ == "__main__":
    unittest.main()
