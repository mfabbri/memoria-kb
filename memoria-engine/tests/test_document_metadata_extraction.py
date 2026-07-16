from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.metadata_extraction import extract_document_metadata
from caduti_fonti_report.document_analysis.manual_registration import register_manual_document
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


class DocumentMetadataExtractionTests(unittest.TestCase):
    def test_extracts_metadata_for_manual_image_without_ocr_or_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
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

            summary = extract_document_metadata(root_dir=raw_dir, output_dir=output_dir)
            metadata_path = Path(summary["documents"][0]["metadata_path"])
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(summary["document_count"], 1)
        self.assertEqual(metadata["@type"], "ProcessedDocumentMetadata")
        self.assertEqual(metadata["document_class"], "image_scan")
        self.assertFalse(metadata["claim_eligible"])
        self.assertEqual(metadata["extraction_status"], "manual_ocr_required")
        self.assertEqual(metadata["text_status"], "not_extracted")
        self.assertEqual(metadata["review_status"], "unreviewed")
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(metadata))

    def test_result_page_metadata_is_not_claim_eligible(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            store = RawDocumentStore(raw_dir)
            store.save_reference_document(
                source_id="tna_wo417",
                title="TNA Discovery advanced search",
                url="https://discovery.nationalarchives.gov.uk/advanced-search",
                reason="no_results",
                query='exact="Guazzaloca Laura"',
                metadata={"document_type": "search_result_reference"},
            )

            summary = extract_document_metadata(root_dir=raw_dir, output_dir=output_dir)
            metadata = json.loads(Path(summary["documents"][0]["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(metadata["document_class"], "result_page")
        self.assertFalse(metadata["claim_eligible"])
        self.assertEqual(metadata["extraction_status"], "metadata_only")
        self.assertEqual(metadata["text_status"], "not_extracted")

    def test_html_document_keeps_provenance_but_does_not_extract_text(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            store = RawDocumentStore(raw_dir)
            stored = store.save_text_document(
                source_id="storia_memoria_bo",
                title="Scheda persona",
                url="https://example.test/scheda",
                text="<html><body>Guazzaloca Laura</body></html>",
                media_type="text/html",
                metadata={"review_status": "unreviewed"},
            )

            summary = extract_document_metadata(root_dir=raw_dir, output_dir=output_dir)
            metadata = json.loads(Path(summary["documents"][0]["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(metadata["document_class"], "html_document")
        self.assertTrue(metadata["claim_eligible"])
        self.assertEqual(metadata["source_document_id"], stored.document_id)
        self.assertEqual(metadata["text_status"], "not_extracted")
        self.assertEqual(metadata["sha256"], stored.content_hash)

    def test_docx_document_is_classified_as_word_document(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            docx_path = raw_dir / "manual_uploads" / "scheda-andreoli.docx"
            _write_minimal_docx(docx_path, ["Andreoli Dino", "Nato a San Lazzaro di Savena."])
            registered = register_manual_document(
                file_path=docx_path,
                source_id="manual_uploads",
                title="Scheda Andreoli DOCX",
                archival_reference="Import manuale DOCX",
                access_date="2026-05-17",
            )

            summary = extract_document_metadata(root_dir=raw_dir, output_dir=output_dir)
            metadata = json.loads(Path(summary["documents"][0]["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(metadata["document_class"], "word_document")
        self.assertTrue(metadata["claim_eligible"])
        self.assertEqual(metadata["review_status"], "unreviewed")
        self.assertEqual(metadata["source_document_id"], registered["document"]["document_id"])
        self.assertEqual(metadata["sha256"], registered["document"]["content_hash"])
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(metadata))

    def test_online_detail_sidecar_is_applied_to_per_file_document(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            text_path = raw_dir / "fonti_online" / "partigiani_italia" / "balboni-william" / "balboni.txt"
            text_path.parent.mkdir(parents=True)
            text_path.write_text("Balboni, William Cognome: Balboni", encoding="utf-8")
            sidecar = {
                "document_id": "partigiani_italia:dadc75fad9db03ae",
                "source_id": "partigiani_italia",
                "title": "Balboni, William",
                "url": "https://partigianiditalia.cultura.gov.it/persona/?id=fixture",
                "access_date": "2026-06-06",
                "file": str(text_path),
                "metadata": {
                    "document_type": "online_detail_document",
                    "media_type": "text/plain",
                    "review_status": "unreviewed",
                    "claim_eligible": True,
                    "profile_id": "person:purocielo:balboni-william",
                    "source_document_id": "partigiani_italia:dadc75fad9db03ae",
                    "detail_assessment": "claim_candidates_extracted",
                    "detail_extracted_fields_json": json.dumps({"family_name": "Balboni"}, ensure_ascii=False),
                    "provenance": "online_source_acquisition",
                },
            }
            text_path.with_name(f"{text_path.name}.document.yaml").write_text(
                yaml.safe_dump(sidecar, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            summary = extract_document_metadata(root_dir=raw_dir, output_dir=output_dir)
            metadata = json.loads(Path(summary["documents"][0]["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(summary["document_count"], 1)
        self.assertEqual(metadata["source_id"], "partigiani_italia")
        self.assertEqual(metadata["source_document_id"], "partigiani_italia:dadc75fad9db03ae")
        self.assertEqual(metadata["document_type"], "online_detail_document")
        self.assertTrue(metadata["claim_eligible"])
        self.assertEqual(metadata["profile_id"], "person:purocielo:balboni-william")
        self.assertEqual(metadata["detail_assessment"], "claim_candidates_extracted")
        self.assertEqual(json.loads(metadata["detail_extracted_fields_json"])["family_name"], "Balboni")
        self.assertIn("balboni.txt", metadata["raw_file"])

    def test_copied_per_file_sidecar_prefers_local_sibling_over_original_file_path(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            original_dir = tmp_dir / "original"
            original_image = original_dir / "andreoli-image-1.jpg"
            original_image.parent.mkdir(parents=True)
            original_image.write_bytes(b"\xff\xd8\xfforiginal\xff\xd9")

            copied_image = raw_dir / "fonti_online" / "partigiani_italia" / "andreoli-dino" / "andreoli-image-1.jpg"
            copied_image.parent.mkdir(parents=True)
            copied_image.write_bytes(b"\xff\xd8\xffcopied\xff\xd9")
            sidecar = {
                "document_id": "partigiani_italia:b45553cd6b1673d8:image:1",
                "source_id": "partigiani_italia",
                "title": "Andreoli, Dino - immagine 1",
                "file": str(original_image),
                "metadata": {
                    "document_type": "online_detail_image",
                    "document_class": "image_scan",
                    "media_type": "image/jpeg",
                    "review_status": "unreviewed",
                    "claim_eligible": False,
                    "profile_id": "person:purocielo:andreoli-dino",
                    "source_document_id": "partigiani_italia:b45553cd6b1673d8",
                    "provenance": "online_source_acquisition",
                },
            }
            copied_image.with_name(f"{copied_image.name}.document.yaml").write_text(
                yaml.safe_dump(sidecar, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            summary = extract_document_metadata(root_dir=raw_dir, output_dir=output_dir)
            metadata = json.loads(Path(summary["documents"][0]["metadata_path"]).read_text(encoding="utf-8"))

        self.assertEqual(summary["document_count"], 1)
        self.assertEqual(metadata["source_document_id"], "partigiani_italia:b45553cd6b1673d8:image:1")
        self.assertEqual(metadata["document_type"], "online_detail_image")
        self.assertFalse(metadata["claim_eligible"])
        self.assertEqual(metadata["profile_id"], "person:purocielo:andreoli-dino")
        self.assertIn("fonti_online", metadata["raw_file"])
        self.assertIn("andreoli-image-1.jpg", metadata["raw_file"])
        self.assertNotEqual(metadata["raw_file"], str(original_image))


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
