from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.manual_registration import register_manual_document
from caduti_fonti_report.document_analysis.metadata_extraction import extract_document_metadata
from caduti_fonti_report.document_analysis.text_extraction import extract_document_text
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


class DocumentTextExtractionTests(unittest.TestCase):
    def test_extracts_text_from_html_document_without_creating_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            output_dir = tmp_dir / "processed"
            store = RawDocumentStore(raw_dir)
            store.save_text_document(
                source_id="storia_memoria_bo",
                title="Scheda persona",
                url="https://example.test/scheda",
                text=(
                    "<html><head><style>.x { color: red; }</style>"
                    "<script>alert('x')</script></head>"
                    "<body><h1>Guazzaloca Laura</h1><p>Infermiera partigiana.</p></body></html>"
                ),
                media_type="text/html",
                metadata={"review_status": "unreviewed"},
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)

            summary = extract_document_text(metadata_dir=metadata_dir, output_dir=output_dir, raw_root_dir=raw_dir)
            text_payload = json.loads(Path(summary["documents"][0]["text_path"]).read_text(encoding="utf-8"))

        self.assertEqual(summary["document_count"], 1)
        self.assertEqual(summary["extracted_count"], 1)
        self.assertEqual(text_payload["@type"], "ProcessedDocumentText")
        self.assertEqual(text_payload["text"], "Guazzaloca Laura Infermiera partigiana.")
        self.assertTrue(text_payload["claim_eligible"])
        self.assertEqual(text_payload["review_status"], "unreviewed")
        self.assertEqual(text_payload["text_status"], "extracted")
        self.assertEqual(text_payload["extraction_status"], "text_extracted")
        self.assertEqual(text_payload["text_sha256"], hashlib.sha256(text_payload["text"].encode("utf-8")).hexdigest())
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(text_payload))
        self.assertNotIn("alert", text_payload["text"])

    def test_result_page_text_preserves_not_claim_eligible(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            output_dir = tmp_dir / "processed"
            store = RawDocumentStore(raw_dir)
            store.save_text_document(
                source_id="tna_wo417",
                title="TNA Discovery advanced search",
                url="https://discovery.nationalarchives.gov.uk/advanced-search",
                text="<html><body><p>No results for Guazzaloca Laura.</p></body></html>",
                media_type="text/html",
                metadata={"document_type": "search_result_reference"},
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)

            summary = extract_document_text(metadata_dir=metadata_dir, output_dir=output_dir, raw_root_dir=raw_dir)
            text_payload = json.loads(Path(summary["documents"][0]["text_path"]).read_text(encoding="utf-8"))

        self.assertEqual(text_payload["document_class"], "result_page")
        self.assertFalse(text_payload["claim_eligible"])
        self.assertEqual(text_payload["text_status"], "extracted")
        self.assertEqual(text_payload["text"], "No results for Guazzaloca Laura.")
        self.assertNotIn("EvidenceClaim", json.dumps(text_payload))

    def test_manual_image_is_skipped_without_ocr(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "2026" / "05" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
                access_date="2026-05-11",
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)

            summary = extract_document_text(metadata_dir=metadata_dir, output_dir=output_dir, raw_root_dir=raw_dir)
            text_payload = json.loads(Path(summary["documents"][0]["text_path"]).read_text(encoding="utf-8"))

        self.assertEqual(summary["extracted_count"], 0)
        self.assertEqual(summary["extraction_status_counts"], {"manual_ocr_required": 1})
        self.assertEqual(summary["document_class_counts"], {"image_scan": 1})
        self.assertEqual(text_payload["document_class"], "image_scan")
        self.assertFalse(text_payload["claim_eligible"])
        self.assertEqual(text_payload["extraction_status"], "manual_ocr_required")
        self.assertEqual(text_payload["text_status"], "not_extracted")
        self.assertEqual(text_payload["text"], "")
        self.assertEqual(text_payload["text_sha256"], "")

    def test_extracts_text_from_docx_without_creating_claims_or_modifying_raw(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            output_dir = tmp_dir / "processed"
            docx_path = raw_dir / "manual_uploads" / "scheda-andreoli.docx"
            _write_minimal_docx(
                docx_path,
                ["Andreoli Dino", "Nato il 17 maggio 1920.", "Milito nella 36a brigata Garibaldi."],
            )
            raw_before = docx_path.read_bytes()
            register_manual_document(
                file_path=docx_path,
                source_id="manual_uploads",
                title="Scheda Andreoli DOCX",
                archival_reference="Import manuale DOCX",
                access_date="2026-05-17",
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)

            summary = extract_document_text(metadata_dir=metadata_dir, output_dir=output_dir, raw_root_dir=raw_dir)
            text_payload = json.loads(Path(summary["documents"][0]["text_path"]).read_text(encoding="utf-8"))
            raw_after = docx_path.read_bytes()

        self.assertEqual(summary["document_count"], 1)
        self.assertEqual(summary["extracted_count"], 1)
        self.assertEqual(raw_after, raw_before)
        self.assertEqual(text_payload["@type"], "ProcessedDocumentText")
        self.assertEqual(
            text_payload["text"],
            "Andreoli Dino Nato il 17 maggio 1920. Milito nella 36a brigata Garibaldi.",
        )
        self.assertEqual(text_payload["document_class"], "word_document")
        self.assertTrue(text_payload["claim_eligible"])
        self.assertEqual(text_payload["review_status"], "unreviewed")
        self.assertEqual(text_payload["text_status"], "extracted")
        self.assertEqual(text_payload["extraction_status"], "text_extracted")
        self.assertEqual(text_payload["text_sha256"], hashlib.sha256(text_payload["text"].encode("utf-8")).hexdigest())
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(text_payload))
        self.assertNotIn("verified_facts", json.dumps(text_payload))

    def test_extracts_text_from_csv_as_tabular_document(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            output_dir = tmp_dir / "processed"
            csv_path = raw_dir / "legacy_documents" / "caduti_purocielo.csv"
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "nome,nascita,ruolo\nAndreoli Dino,17 maggio 1920,partigiano\nGuazzaloca Laura,28 gennaio 1920,infermiera\n",
                encoding="utf-8-sig",
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)

            summary = extract_document_text(metadata_dir=metadata_dir, output_dir=output_dir, raw_root_dir=raw_dir)
            text_payload = json.loads(Path(summary["documents"][0]["text_path"]).read_text(encoding="utf-8"))

        self.assertEqual(summary["document_count"], 1)
        self.assertEqual(summary["extracted_count"], 1)
        self.assertEqual(summary["document_class_counts"], {"tabular_document": 1})
        self.assertEqual(text_payload["document_class"], "tabular_document")
        self.assertTrue(text_payload["claim_eligible"])
        self.assertEqual(text_payload["text_status"], "extracted")
        self.assertEqual(text_payload["extraction_status"], "text_extracted")
        self.assertIn("Riga 1. nome: Andreoli Dino; nascita: 17 maggio 1920; ruolo: partigiano", text_payload["text"])
        self.assertIn("Riga 2. nome: Guazzaloca Laura; nascita: 28 gennaio 1920; ruolo: infermiera", text_payload["text"])
        self.assertNotIn("verified_facts", json.dumps(text_payload))


def _write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


if __name__ == "__main__":
    unittest.main()
