from __future__ import annotations

import hashlib
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.inventory import build_raw_document_inventory
from caduti_fonti_report.document_analysis.manual_registration import register_manual_document


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


class ManualDocumentRegistrationTests(unittest.TestCase):
    def test_registers_manual_image_with_sidecar_without_modifying_file(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw" / "manual_uploads" / "2026" / "05"
            raw_dir.mkdir(parents=True)
            image_path = raw_dir / "RH_20_10_199_0006.jpg"
            image_bytes = b"\xff\xd8\xffmanual-image-bytes\xff\xd9"
            image_path.write_bytes(image_bytes)
            before_hash = hashlib.sha256(image_bytes).hexdigest()

            result = register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Foto documento RH 20/10/199 0006",
                archival_reference="RH 20/10/199 0006",
                access_date="2026-05-11",
            )
            sidecar_path = Path(result["sidecar_path"])
            sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))
            after_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()

            inventory = build_raw_document_inventory(root_dir=tmp_dir / "raw" / "manual_uploads")

        self.assertEqual(after_hash, before_hash)
        self.assertEqual(sidecar["source_id"], "manual_uploads")
        self.assertEqual(sidecar["content_hash"], before_hash)
        self.assertEqual(sidecar["metadata"]["access_mode"], "manual_upload")
        self.assertEqual(sidecar["metadata"]["archival_reference"], "RH 20/10/199 0006")
        self.assertEqual(sidecar["metadata"]["extraction_status"], "manual_ocr_required")
        self.assertEqual(sidecar["metadata"]["review_status"], "unreviewed")
        self.assertEqual(inventory["document_count"], 1)
        document = inventory["documents"][0]
        self.assertEqual(document["status"], "manual_upload")
        self.assertEqual(document["source_id"], "manual_uploads")
        self.assertEqual(document["archival_reference"], "RH 20/10/199 0006")
        self.assertEqual(document["extraction_status"], "manual_ocr_required")

    def test_refuses_to_overwrite_existing_sidecar_by_default(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            file_path = tmp_dir / "document.txt"
            file_path.write_text("test", encoding="utf-8")
            (tmp_dir / "document.yaml").write_text("source_id: existing\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                register_manual_document(
                    file_path=file_path,
                    source_id="manual_uploads",
                    title="Documento",
                    archival_reference="REF",
                )

    def test_requires_url_or_archival_reference(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            file_path = tmp_dir / "document.txt"
            file_path.write_text("test", encoding="utf-8")

            with self.assertRaises(ValueError):
                register_manual_document(
                    file_path=file_path,
                    source_id="manual_uploads",
                    title="Documento",
                )


if __name__ == "__main__":
    unittest.main()
