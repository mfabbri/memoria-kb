from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.models import to_json_safe
from caduti_fonti_report.raw_store import RawDocumentStore


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


def fixed_now() -> datetime:
    return datetime(2026, 4, 26, 12, 0, tzinfo=UTC)


class RawStoreTests(unittest.TestCase):
    def test_save_text_document_writes_content_sidecar_and_hash(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = RawDocumentStore(tmp_dir / "raw", now_factory=fixed_now)
            document = store.save_text_document(
                source_id="storia_memoria_bo_excel",
                title="Scheda Andreoli Dino",
                url="file:///archivi/storia.sba.unibo.it/Bologna.xls",
                text="Riga Excel: Andreoli Dino",
                metadata={"row": "42"},
            )

            document_path = Path(document.local_path)
            sidecar_path = document_path.parent / "document.yaml"
            content_text = document_path.read_text(encoding="utf-8")
            sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))

            self.assertEqual(document_path.name, "content.txt")
            self.assertEqual(content_text, "Riga Excel: Andreoli Dino")
            self.assertIn("storia-memoria-bo-excel/2026/04", document.local_path.replace("\\", "/"))

        self.assertEqual(document.content_hash, hashlib.sha256("Riga Excel: Andreoli Dino".encode("utf-8")).hexdigest())
        self.assertEqual(sidecar["content_hash"], document.content_hash)
        self.assertEqual(sidecar["metadata"]["access_mode"], "stored_text")
        self.assertEqual(sidecar["metadata"]["row"], "42")
        json.dumps(to_json_safe(document))

    def test_save_reference_document_writes_sidecar_without_content(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = RawDocumentStore(tmp_dir / "raw", now_factory=fixed_now)
            document = store.save_reference_document(
                source_id="tna_wo417",
                title="TNA WO 417 reference",
                url="https://discovery.nationalarchives.gov.uk/",
                reason="needs_credentials",
                query='exact="Andreoli Dino"',
            )
            document_dir = tmp_dir / "raw" / "tna-wo417" / "2026" / "04" / document.document_id
            sidecar_path = document_dir / "document.yaml"
            sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))

        self.assertEqual(document.local_path, "")
        self.assertEqual(document.content_hash, "")
        self.assertFalse((document_dir / "content.txt").exists())
        self.assertEqual(sidecar["metadata"]["access_mode"], "reference_only")
        self.assertEqual(sidecar["metadata"]["reason"], "needs_credentials")
        self.assertEqual(sidecar["metadata"]["query"], 'exact="Andreoli Dino"')
        json.dumps(to_json_safe(document))


if __name__ == "__main__":
    unittest.main()
