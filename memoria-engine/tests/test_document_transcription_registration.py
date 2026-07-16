from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.document_quality import assess_document_quality  # noqa: E402
from caduti_fonti_report.document_analysis.entity_extraction import extract_document_entities  # noqa: E402
from caduti_fonti_report.document_analysis.manual_registration import register_manual_document  # noqa: E402
from caduti_fonti_report.document_analysis.transcription_registration import register_document_transcription  # noqa: E402


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


class DocumentTranscriptionRegistrationTests(unittest.TestCase):
    def test_registers_manual_transcription_from_image_file_and_generates_metadata(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "2026" / "05" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_bytes = b"\xff\xd8\xffscan\xff\xd9"
            image_path.write_bytes(image_bytes)
            before_hash = hashlib.sha256(image_bytes).hexdigest()
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
                access_date="2026-05-16",
            )

            result = register_document_transcription(
                file_path=image_path,
                text="Nato il 28 gennaio 1920. Milito nella 36ma brigata.",
                root_dir=raw_dir,
                output_dir=output_dir,
            )
            text_payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))
            after_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
            metadata_file_exists = Path(text_payload["metadata_file"]).exists()

        self.assertEqual(after_hash, before_hash)
        self.assertEqual(text_payload["@type"], "ProcessedDocumentText")
        self.assertEqual(text_payload["document_class"], "image_scan")
        self.assertEqual(text_payload["text_status"], "extracted")
        self.assertEqual(text_payload["extraction_status"], "manual_transcription_registered")
        self.assertEqual(text_payload["transcription_method"], "manual_transcription")
        self.assertEqual(text_payload["review_status"], "unreviewed")
        self.assertEqual(text_payload["text_sha256"], hashlib.sha256(text_payload["text"].encode("utf-8")).hexdigest())
        self.assertTrue(metadata_file_exists)
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(text_payload))
        self.assertNotIn("verified_facts", json.dumps(text_payload))

    def test_transcribed_image_quality_becomes_ready_for_manual_review(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )
            register_document_transcription(
                file_path=image_path,
                text="Trascrizione da rivedere.",
                root_dir=raw_dir,
                output_dir=output_dir,
            )

            summary = assess_document_quality(metadata_dir=output_dir, text_dir=output_dir, output_dir=output_dir)
            quality = json.loads(Path(summary["documents"][0]["quality_path"]).read_text(encoding="utf-8"))

        self.assertEqual(quality["document_class"], "image_scan")
        self.assertEqual(quality["quality_status"], "ready_for_manual_review")
        self.assertEqual(quality["classification"], "image_transcription")
        self.assertFalse(quality["claim_allowed"])

    def test_transcribed_image_can_feed_entity_preview_without_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )
            register_document_transcription(
                file_path=image_path,
                text="Nato il 28 gennaio 1920.",
                root_dir=raw_dir,
                output_dir=output_dir,
            )

            payload = extract_document_entities(text_dir=output_dir, metadata_dir=output_dir)

        self.assertEqual(payload["entity_count"], 1)
        self.assertEqual(payload["extracted_entities"][0]["value"], "28 gennaio 1920")
        self.assertEqual(payload["extracted_entities"][0]["review_status"], "unreviewed")
        self.assertNotIn("EvidenceClaim", json.dumps(payload))

    def test_refuses_empty_transcription_and_existing_output_without_overwrite(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )

            with self.assertRaises(ValueError):
                register_document_transcription(file_path=image_path, text="   ", root_dir=raw_dir, output_dir=output_dir)

            register_document_transcription(file_path=image_path, text="Prima trascrizione.", root_dir=raw_dir, output_dir=output_dir)
            with self.assertRaises(FileExistsError):
                register_document_transcription(file_path=image_path, text="Seconda trascrizione.", root_dir=raw_dir, output_dir=output_dir)

    def test_refuses_missing_transcription_file_readably(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            missing_text = tmp_dir / "missing-transcription.txt"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )

            with self.assertRaisesRegex(FileNotFoundError, "File trascrizione non trovato"):
                register_document_transcription(
                    file_path=image_path,
                    text_file=missing_text,
                    root_dir=raw_dir,
                    output_dir=output_dir,
                )


if __name__ == "__main__":
    unittest.main()
