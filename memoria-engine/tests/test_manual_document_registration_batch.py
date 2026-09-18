from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.manual_registration_batch import (  # noqa: E402
    preview_manual_documents_batch,
    register_manual_documents_batch,
    write_batch_report,
)
from caduti_fonti_report.document_analysis.metadata_extraction import extract_document_metadata  # noqa: E402


@contextmanager
def workspace_temp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"test-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class ManualDocumentRegistrationBatchTests(unittest.TestCase):
    def test_preview_is_recursive_and_does_not_create_sidecars(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "foto"
            image_path = root_dir / "cartella" / "pagina-1.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffpagina-1\xff\xd9")

            report = preview_manual_documents_batch(
                root_dir=root_dir,
                source_id="manual_uploads",
                archival_reference="Raccolta",
            )

            self.assertTrue(report["preview_only"])
            self.assertEqual(report["summary"]["would_register"], 1)
            self.assertFalse(image_path.with_name("pagina-1.jpg.document.yaml").exists())

    def test_registers_images_recursively_without_modifying_files(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "foto"
            first = root_dir / "cartella-a" / "pagina-1.jpg"
            second = root_dir / "cartella-b" / "pagina-2.jpeg"
            note = root_dir / "note.txt"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_bytes(b"\xff\xd8\xffpagina-1\xff\xd9")
            second.write_bytes(b"\xff\xd8\xffpagina-2\xff\xd9")
            note.write_text("non immagine", encoding="utf-8")
            before_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in [first, second]}

            report = register_manual_documents_batch(
                root_dir=root_dir,
                source_id="manual_uploads",
                archival_reference="Da assegnare - import batch Foto",
                access_date="2026-05-16",
                title_template="Foto {relative_path}",
            )
            sidecars = [yaml.safe_load(path.with_name(f"{path.name}.document.yaml").read_text(encoding="utf-8")) for path in [first, second]]
            after_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in [first, second]}
            metadata_summary = extract_document_metadata(root_dir=root_dir, output_dir=tmp_dir / "processed")
            image_metadata = [item for item in metadata_summary["documents"] if item["document_class"] == "image_scan"]

        self.assertEqual(before_hashes, after_hashes)
        self.assertEqual(report["@type"], "ManualDocumentBatchRegistration")
        self.assertEqual(report["summary"]["registered"], 2)
        self.assertEqual(report["summary"]["total"], 2)
        self.assertEqual(sidecars[0]["source_id"], "manual_uploads")
        self.assertEqual(sidecars[0]["title"], "Foto cartella-a\\pagina-1.jpg" if "\\" in sidecars[0]["title"] else "Foto cartella-a/pagina-1.jpg")
        self.assertEqual(sidecars[0]["metadata"]["archival_reference"], "Da assegnare - import batch Foto")
        self.assertEqual(sidecars[0]["metadata"]["review_status"], "unreviewed")
        self.assertEqual(sidecars[0]["metadata"]["extraction_status"], "manual_ocr_required")
        self.assertEqual(len(image_metadata), 2)

    def test_skips_existing_sidecar_without_overwrite(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "foto"
            image_path = root_dir / "pagina-1.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffpagina-1\xff\xd9")
            image_path.with_name("pagina-1.jpg.document.yaml").write_text("source_id: existing\n", encoding="utf-8")

            report = register_manual_documents_batch(
                root_dir=root_dir,
                source_id="manual_uploads",
                archival_reference="Raccolta",
            )

        self.assertEqual(report["summary"]["registered"], 0)
        self.assertEqual(report["summary"]["skipped_existing_sidecar"], 1)

    def test_requires_collection_archival_reference(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "foto"
            root_dir.mkdir()

            with self.assertRaisesRegex(ValueError, "archival_reference obbligatorio"):
                register_manual_documents_batch(
                    root_dir=root_dir,
                    source_id="manual_uploads",
                    archival_reference="",
                )

    def test_writes_json_and_markdown_report(self) -> None:
        report = {
            "@type": "ManualDocumentBatchRegistration",
            "root_dir": "foto",
            "source_id": "manual_uploads",
            "archival_reference": "Raccolta",
            "summary": {"total": 1, "registered": 1},
            "documents": [{"status": "registered", "file": "foto.jpg", "sidecar_path": "document.yaml", "title": "foto.jpg"}],
        }
        with workspace_temp_dir() as tmp_dir:
            output_json = tmp_dir / "manual_batch.json"
            output_md = tmp_dir / "manual_batch.md"
            write_batch_report(report=report, output_json=output_json, output_md=output_md)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(payload["@type"], "ManualDocumentBatchRegistration")
        self.assertIn("# Registrazione batch documenti manuali", markdown)
        self.assertIn("foto.jpg", markdown)


if __name__ == "__main__":
    unittest.main()
