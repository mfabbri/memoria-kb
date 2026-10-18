from __future__ import annotations

import copy
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from caduti_fonti_report.document_analysis.ocr_review_package import build_ocr_review_package
from caduti_fonti_report.document_analysis.ocr_review_batch import run_ocr_review_batch
from caduti_fonti_report.document_analysis.ocr_review_orchestrator import _validate_evidence_comparison
from caduti_fonti_report.memoria_cli import main


class OcrReviewPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "original.tif"
        Image.new("L", (20, 10), 255).save(self.image)
        self.variant = self.root / "raw.tif"
        self.variant.write_bytes(self.image.read_bytes())
        digest = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.evidence = {"@type": "OcrPageEvidence", "schema_version": "1.0", "page_id": "p1",
            "source_image_hash": digest, "transform_id": "t36:raw", "engine": "paddle-ocr-v5",
            "language": "deu", "model": {"name": "fixture"},
            "image_transform": {"id": "t36:raw", "parameters": {"operation": "byte_copy"}},
            "source_page": {"variant_id": "raw", "target": "full_page", "tile_id": None,
                "original_page": {"page_id": "p1", "source_file": str(self.image),
                    "source_image_hash": digest, "source_dimensions": {"width": 20, "height": 10}}},
            "regions": [{"region_id": "r1", "text": "Bekannt", "geometry": {"bbox": [0, 0, 20, 10]}}]}
        self.page = {"page_id": "p1", "source": {"path": str(self.image), "sha256": digest,
            "image_dimensions": {"width": 20, "height": 10}}, "variants": [{"variant_id": "raw",
                "path": "raw.tif", "sha256": digest, "transform": self.evidence["image_transform"],
                "ocr_outputs": [{"target": "full_page", "artifact": "raw.tif", "artifact_sha256": digest,
                    "source_bbox": [0, 0, 20, 10], "structured_evidence": self.evidence}]}]}
        self.manifest = self.root / "pilot.json"
        self.right = self.root / "tesseract.json"
        self.lexicon = self.root / "lexicon.json"
        self.write(self.lexicon, {"@type": "OcrLanguageLexicon", "schema_version": "1.0", "@id": "fixture:de",
            "version": "1", "language": "deu", "entries": [{"term": "Bekannt", "category": "word",
                "source_id": "fixture", "version": "1"}]})
        self.sync()
        self.output = self.root / "output"

    def write(self, path, payload):
        path.write_text(json.dumps(payload), encoding="utf-8")

    def sync(self):
        self.write(self.manifest, {"@type": "OcrTransformPilot", "schema_version": "1.0", "language": "deu",
            "review_status": "unreviewed", "accuracy_claim": "none_without_human_reference", "pages": [self.page]})
        right = copy.deepcopy(self.evidence)
        right.update(engine="tesseract", model={"name": "tesseract"})
        self.write(self.right, right)

    def run_package(self, **overrides):
        args = dict(manifest_path=self.manifest, variant_id="raw", page_profiles={"p1": "numbered_report"},
            tesseract_evidence={"p1": self.right}, lexicons={"p1": self.lexicon}, output_dir=self.output)
        args.update(overrides)
        return build_ocr_review_package(**args)

    def test_preview_is_clean_and_deterministic(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        first, second = self.run_package(), self.run_package()
        self.assertEqual(first, second)
        self.assertEqual(first["operation_status"], "preview")
        self.assertFalse(first["machine_pass"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_apply_hashes_final_paths_and_retains_provenance(self):
        before = self.manifest.read_bytes()
        report = self.run_package(apply=True)
        self.assertEqual(before, self.manifest.read_bytes())
        self.assertEqual(json.loads((self.output / "package-manifest.json").read_text()), report)
        page = report["pages"][0]
        self.assertEqual(set(page["review_inputs"]), {"image", "evidence", "structure", "markdown",
            "lexicon_review", "layout", "ledger", "dispositions", "comparison", "tesseract_evidence"})
        for artifact in [*page["outputs"], *page["t37"].values(), *page["review_inputs"].values(), report["t37_manifest"]]:
            self.assertEqual(artifact["sha256"], hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest())
        folder = self.output / "pages" / "p1.evidence"
        paths = {"image": self.image, "evidence": folder / "evidence.json",
                 "tesseract_evidence": folder / "tesseract-evidence.json", "comparison": folder / "comparison.json"}
        snapshot = {name: {"digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in paths.items()}
        _validate_evidence_comparison(paths, snapshot)
        candidate = json.loads(paths["evidence"].read_text())
        self.assertEqual(candidate["transform_id"], "t36:raw")
        self.assertEqual(candidate["source_page"]["frame_index"], 0)
        self.assertNotIn("frame_index", json.loads(Path(page["t37"]["evidence"]["path"]).read_text())["source_page"])
        ledger = json.loads((folder / "review" / "visual-ledger.json").read_text())
        self.assertEqual(ledger["template_status"], "incomplete")
        self.assertTrue(all(not row["text"] and not row["outcome"] and not row["observer"] for row in ledger["observations"]))
        self.assertNotIn(".ocr-review-package-", "".join(p.read_text() for p in self.output.rglob("*.json")))
        before = {str(path): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}
        batch = run_ocr_review_batch(manifest_path=self.output / "package-manifest.json",
                                    output_path=self.root / "batch.json")
        self.assertEqual(batch["pages"][0]["status"], "blocked")
        assessment = next(stage for stage in batch["pages"][0]["review"]["stages"]
                          if stage["stage"] == "candidate_assessment")
        self.assertEqual(assessment["status"], "passed")
        self.assertEqual(assessment["issues"], [])
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.output.rglob("*") if path.is_file()})
        self.assertFalse((self.root / "batch.json").exists())

    def test_exact_maps_and_existing_output(self):
        for name in ("page_profiles", "tesseract_evidence", "lexicons", "glossaries"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.run_package(**{name: {}})
            self.assertFalse(self.output.exists())
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.run_package(apply=True)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_bad_evidence_and_byte_copy_operation_fail_without_output(self):
        self.write(self.right, {})
        with self.assertRaises(ValueError):
            self.run_package(apply=True)
        self.assertFalse(self.output.exists())
        self.evidence["image_transform"]["parameters"]["operation"] = "resize"
        self.sync()
        with self.assertRaisesRegex(ValueError, "byte_copy"):
            self.run_package(apply=True)
        self.assertFalse(self.output.exists())

    def test_raw_bytes_and_multiframe_rejected(self):
        self.variant.write_bytes(b"different")
        digest = hashlib.sha256(self.variant.read_bytes()).hexdigest()
        variant = self.page["variants"][0]
        variant["sha256"] = variant["ocr_outputs"][0]["artifact_sha256"] = digest
        self.sync()
        with self.assertRaisesRegex(ValueError, "byte-identica"):
            self.run_package()
        Image.new("L", (20, 10), 255).save(self.image, save_all=True, append_images=[Image.new("L", (20, 10), 0)])
        self.variant.write_bytes(self.image.read_bytes())
        digest = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.page["source"]["sha256"] = digest
        self.evidence["source_image_hash"] = digest
        self.evidence["source_page"]["original_page"]["source_image_hash"] = digest
        variant["sha256"] = variant["ocr_outputs"][0]["artifact_sha256"] = digest
        self.sync()
        with self.assertRaisesRegex(ValueError, "single-frame"):
            self.run_package()
        self.assertFalse(self.output.exists())

    def test_tesseract_identity_and_frame_locator_mismatches(self):
        right = json.loads(self.right.read_text())
        right["source_page"]["frame_index"] = 0
        self.write(self.right, right)
        with self.assertRaisesRegex(ValueError, "source_page"):
            self.run_package(apply=True)
        self.assertFalse(self.output.exists())
        self.evidence["source_page"]["frame_index"] = 1
        self.sync()
        with self.assertRaisesRegex(ValueError, "frame_index"):
            self.run_package(apply=True)
        self.assertFalse(self.output.exists())

    def test_second_page_failure_rolls_back_entire_package(self):
        page2 = copy.deepcopy(self.page)
        page2["page_id"] = "p2"
        candidate = page2["variants"][0]["ocr_outputs"][0]["structured_evidence"]
        candidate["page_id"] = candidate["source_page"]["original_page"]["page_id"] = "p2"
        manifest = json.loads(self.manifest.read_text())
        manifest["pages"].append(page2)
        self.write(self.manifest, manifest)
        right2 = self.root / "bad-second-page.json"
        self.write(right2, {})
        before = set(self.root.iterdir())
        with self.assertRaises(ValueError):
            self.run_package(page_profiles={"p1": "numbered_report", "p2": "numbered_report"},
                tesseract_evidence={"p1": self.right, "p2": right2},
                lexicons={"p1": self.lexicon, "p2": self.lexicon}, apply=True)
        self.assertEqual(set(self.root.iterdir()), before)

    def test_cli_and_duplicate_map_rejection(self):
        args = ["documents", "ocr-review-package", "--manifest", str(self.manifest), "--variant", "raw",
            "--page-profile", "p1=numbered_report", "--tesseract-evidence", f"p1={self.right}",
            "--lexicon", f"p1={self.lexicon}", "--output-dir", str(self.output)]
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            self.assertEqual(main(args), 0)
            self.assertEqual(main(args + ["--lexicon", f"p1={self.lexicon}"]), 1)
        self.assertEqual(json.loads(output.getvalue())["operation_status"], "preview")
        self.assertIn("duplicati", error.getvalue())


if __name__ == "__main__":
    unittest.main()
