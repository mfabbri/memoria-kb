from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.document_quality import assess_document_quality
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


class DocumentQualityAssessmentTests(unittest.TestCase):
    def test_html_with_extracted_text_is_ready_for_manual_review_without_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            processed_dir = tmp_dir / "processed"
            store = RawDocumentStore(raw_dir)
            stored = store.save_text_document(
                source_id="camalanca_html",
                title="Scheda Adelmo Brini",
                url="https://www.camalanca.it/adelmo-brini/",
                text="<html><head><title>Adelmo Brini</title></head><body>Scheda partigiano.</body></html>",
                media_type="text/html",
                metadata={"review_status": "unreviewed"},
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)
            extract_document_text(metadata_dir=metadata_dir, output_dir=processed_dir, raw_root_dir=raw_dir)

            summary = assess_document_quality(metadata_dir=metadata_dir, text_dir=processed_dir, output_dir=processed_dir)
            quality = json.loads(Path(summary["documents"][0]["quality_path"]).read_text(encoding="utf-8"))

        self.assertEqual(summary["document_count"], 1)
        self.assertEqual(quality["@type"], "DocumentQualityAssessment")
        self.assertEqual(quality["source_document_id"], stored.document_id)
        self.assertEqual(quality["quality_status"], "ready_for_manual_review")
        self.assertEqual(quality["classification"], "person_detail_or_html_document")
        self.assertFalse(quality["claim_allowed"])
        self.assertEqual(quality["review_status"], "unreviewed")
        self.assertEqual(quality["text_status"], "extracted")
        self.assertGreater(quality["text_length"], 0)
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(quality))
        self.assertNotIn("verified_facts", json.dumps(quality))

    def test_result_page_is_audit_only_even_when_text_exists(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            processed_dir = tmp_dir / "processed"
            store = RawDocumentStore(raw_dir)
            store.save_text_document(
                source_id="tna_wo417",
                title="TNA Discovery advanced search",
                url="https://discovery.nationalarchives.gov.uk/advanced-search",
                text="<html><body>No results for Guazzaloca Laura.</body></html>",
                media_type="text/html",
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)
            extract_document_text(metadata_dir=metadata_dir, output_dir=processed_dir, raw_root_dir=raw_dir)

            summary = assess_document_quality(metadata_dir=metadata_dir, text_dir=processed_dir, output_dir=processed_dir)
            quality = json.loads(Path(summary["documents"][0]["quality_path"]).read_text(encoding="utf-8"))

        self.assertEqual(quality["document_class"], "result_page")
        self.assertEqual(quality["quality_status"], "audit_only")
        self.assertEqual(quality["classification"], "result_page")
        self.assertFalse(quality["claim_allowed"])
        self.assertIn("result_page_not_sufficient_for_claims", quality["reasons"])

    def test_manual_image_requires_manual_ocr(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
                access_date="2026-05-16",
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)

            summary = assess_document_quality(metadata_dir=metadata_dir, text_dir=output_dir, output_dir=output_dir)
            quality = json.loads(Path(summary["documents"][0]["quality_path"]).read_text(encoding="utf-8"))

        self.assertEqual(quality["document_class"], "image_scan")
        self.assertEqual(quality["quality_status"], "manual_ocr_required")
        self.assertEqual(quality["classification"], "image_scan")
        self.assertFalse(quality["claim_allowed"])

    def test_html_without_text_payload_requires_manual_review(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            output_dir = tmp_dir / "processed"
            store = RawDocumentStore(raw_dir)
            store.save_text_document(
                source_id="camalanca_html",
                title="Scheda senza testo estratto",
                url="https://www.camalanca.it/scheda/",
                text="<html><body>Testo non ancora estratto.</body></html>",
                media_type="text/html",
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)

            summary = assess_document_quality(metadata_dir=metadata_dir, text_dir=output_dir, output_dir=output_dir)
            quality = json.loads(Path(summary["documents"][0]["quality_path"]).read_text(encoding="utf-8"))

        self.assertEqual(quality["document_class"], "html_document")
        self.assertEqual(quality["quality_status"], "manual_review_required")
        self.assertEqual(quality["text_status"], "not_extracted")
        self.assertFalse(quality["claim_allowed"])

    def test_quality_assessment_reports_progress(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            processed_dir = tmp_dir / "processed"
            store = RawDocumentStore(raw_dir)
            store.save_text_document(
                source_id="camalanca_html",
                title="Scheda Andreoli",
                url="https://example.test/andreoli",
                text="<html><body>Andreoli Dino</body></html>",
                media_type="text/html",
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)
            extract_document_text(metadata_dir=metadata_dir, output_dir=processed_dir, raw_root_dir=raw_dir)
            progress: list[str] = []

            assess_document_quality(
                metadata_dir=metadata_dir,
                text_dir=processed_dir,
                output_dir=processed_dir,
                progress_callback=progress.append,
                progress_every=1,
            )

        self.assertTrue(progress[0].startswith("quality metadata start count=1"))
        self.assertTrue(any("quality metadata 1/1 processed=1" in line for line in progress))
        self.assertTrue(progress[-1].startswith("quality metadata done processed=1"))


if __name__ == "__main__":
    unittest.main()
