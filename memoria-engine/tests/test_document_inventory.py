from __future__ import annotations

import hashlib
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.inventory import build_raw_document_inventory, render_raw_document_inventory_markdown
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
    return datetime(2026, 5, 11, 12, 0, tzinfo=UTC)


class DocumentInventoryTests(unittest.TestCase):
    def test_inventory_reads_stored_and_reference_documents_without_modifying_raw(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            store = RawDocumentStore(raw_dir, now_factory=fixed_now)
            stored = store.save_text_document(
                source_id="storia_memoria_bo",
                title="Scheda Guazzaloca Laura",
                url="https://example.test/scheda",
                text="Persone Giordano Romeo",
                media_type="text/html",
                metadata={"review_status": "unreviewed"},
            )
            reference = store.save_reference_document(
                source_id="tna_wo417",
                title="TNA WO 417 search",
                url="https://discovery.nationalarchives.gov.uk/advanced-search",
                reason="no_results",
                query='exact="Guazzaloca Laura"',
            )

            before_paths = sorted(path.relative_to(raw_dir) for path in raw_dir.rglob("*"))
            inventory = build_raw_document_inventory(root_dir=raw_dir)
            after_paths = sorted(path.relative_to(raw_dir) for path in raw_dir.rglob("*"))

        self.assertEqual(before_paths, after_paths)
        self.assertEqual(inventory["document_count"], 2)
        by_id = {document["source_document_id"]: document for document in inventory["documents"]}
        self.assertEqual(by_id[stored.document_id]["status"], "stored")
        self.assertEqual(by_id[stored.document_id]["sha256"], hashlib.sha256("Persone Giordano Romeo".encode("utf-8")).hexdigest())
        self.assertEqual(by_id[stored.document_id]["review_status"], "unreviewed")
        self.assertEqual(by_id[reference.document_id]["status"], "reference_only")
        self.assertEqual(by_id[reference.document_id]["raw_file"], "")
        self.assertEqual(by_id[reference.document_id]["url"], "https://discovery.nationalarchives.gov.uk/advanced-search")

    def test_inventory_includes_files_without_sidecar(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            file_path = raw_dir / "custom-source" / "loose.html"
            file_path.parent.mkdir(parents=True)
            file_path.write_text("<html>Documento sciolto</html>", encoding="utf-8")

            inventory = build_raw_document_inventory(root_dir=raw_dir)

        self.assertEqual(inventory["document_count"], 1)
        document = inventory["documents"][0]
        self.assertEqual(document["status"], "file_without_sidecar")
        self.assertEqual(document["source_id"], "custom_source")
        self.assertEqual(document["media_type"], "text/html")
        self.assertEqual(document["sha256"], hashlib.sha256("<html>Documento sciolto</html>".encode("utf-8")).hexdigest())

    def test_inventory_records_unreadable_sidecar_without_failing(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            sidecar_path = raw_dir / "broken" / "document.yaml"
            sidecar_path.parent.mkdir(parents=True)
            sidecar_path.write_text("title: [non chiuso\n", encoding="utf-8")

            inventory = build_raw_document_inventory(root_dir=raw_dir)
            markdown = render_raw_document_inventory_markdown(inventory)

        self.assertEqual(inventory["document_count"], 0)
        self.assertEqual(inventory["error_count"], 1)
        self.assertEqual(inventory["errors"][0]["kind"], "sidecar_read_error")
        self.assertIn("document.yaml", inventory["errors"][0]["path"])
        self.assertIn("Errori lettura", markdown)

    def test_inventory_records_unreadable_file_without_modifying_raw(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            file_path = raw_dir / "custom-source" / "loose.txt"
            file_path.parent.mkdir(parents=True)
            file_path.write_text("Documento", encoding="utf-8")
            before_paths = sorted(path.relative_to(raw_dir) for path in raw_dir.rglob("*"))

            with patch(
                "caduti_fonti_report.document_analysis.inventory._sha256_file",
                side_effect=OSError("lettura negata"),
            ):
                inventory = build_raw_document_inventory(root_dir=raw_dir)
            after_paths = sorted(path.relative_to(raw_dir) for path in raw_dir.rglob("*"))

        self.assertEqual(before_paths, after_paths)
        self.assertEqual(inventory["document_count"], 1)
        self.assertEqual(inventory["error_count"], 1)
        self.assertEqual(inventory["documents"][0]["status"], "read_error")
        self.assertEqual(inventory["documents"][0]["sha256"], "")
        self.assertEqual(inventory["errors"][0]["kind"], "file_read_error")

    def test_markdown_renders_inventory_without_claims(self) -> None:
        inventory = {
            "root_dir": "data/raw",
            "document_count": 1,
            "error_count": 0,
            "errors": [],
            "documents": [
                {
                    "title": "TNA WO 417 search",
                    "status": "reference_only",
                    "source_id": "tna_wo417",
                    "source_document_id": "tna_wo417:1",
                    "media_type": "text/uri-list",
                    "raw_file": "",
                    "sidecar_file": "tna/document.yaml",
                    "sha256": "",
                    "url": "https://discovery.nationalarchives.gov.uk/advanced-search",
                }
            ],
        }

        markdown = render_raw_document_inventory_markdown(inventory)

        self.assertIn("# Raw document inventory", markdown)
        self.assertIn("reference_only", markdown)
        self.assertNotIn("EvidenceClaim", markdown)


if __name__ == "__main__":
    unittest.main()
