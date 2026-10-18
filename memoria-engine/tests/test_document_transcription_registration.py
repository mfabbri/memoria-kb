from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.document_quality import assess_document_quality  # noqa: E402
from caduti_fonti_report.document_analysis.entity_extraction import extract_document_entities  # noqa: E402
from caduti_fonti_report.document_analysis.manual_registration import register_manual_document  # noqa: E402
from caduti_fonti_report.document_analysis.transcription_registration import register_document_transcription  # noqa: E402
from caduti_fonti_report.document_analysis import transcription_registration  # noqa: E402


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
    def test_explicit_metadata_bypasses_lookup_and_rechecks_inputs_before_writing(self):
        for mutation in (None, "metadata", "sidecar", "image"):
            with self.subTest(mutation=mutation), workspace_temp_dir() as tmp_dir:
                raw = tmp_dir / "raw"
                raw.mkdir()
                image = raw / "page.tiff"
                image.write_bytes(b"synthetic TIFF")
                sidecar = raw / "page.tiff.document.yaml"
                sidecar.write_text(json.dumps({"source_id": "source", "document_id": "doc", "local_path": str(image)}), encoding="utf-8")
                metadata_path = tmp_dir / "metadata.json"
                metadata_path.write_text(json.dumps({
                    "@type": "ProcessedDocumentMetadata", "document_class": "image_scan",
                    "source_id": "source", "source_document_id": "doc", "raw_file": image.name,
                    "sidecar_file": sidecar.name, "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                }), encoding="utf-8")
                original = transcription_registration._processed_text_from_transcription
                def build_text(**kwargs):
                    payload = original(**kwargs)
                    if mutation is not None:
                        path = {"metadata": metadata_path, "sidecar": sidecar, "image": image}[mutation]
                        path.write_bytes(path.read_bytes() + b" ")
                    return payload
                with patch.object(transcription_registration, "_find_metadata", side_effect=AssertionError("lookup")), patch.object(
                    transcription_registration, "extract_document_metadata", side_effect=AssertionError("extract")
                ), patch.object(transcription_registration, "_processed_text_from_transcription", side_effect=build_text):
                    kwargs = dict(file_path=image, root_dir=raw, output_dir=tmp_dir / "out", text="Testo valido",
                                  metadata_path=metadata_path, metadata_sha256=hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
                                  sidecar_sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest())
                    if mutation is None:
                        result = register_document_transcription(**kwargs)
                        payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))
                        self.assertEqual(payload["source_document_id"], "doc")
                        self.assertEqual(payload["metadata_file"], str(metadata_path))
                        self.assertEqual(payload["transcription_method"], "manual_transcription")
                    else:
                        with self.assertRaises(ValueError):
                            register_document_transcription(**kwargs)
                        self.assertFalse((tmp_dir / "out").exists())

    def test_explicit_metadata_requires_path_and_digest_together(self):
        for kwargs in ({"metadata_path": Path("metadata.json")}, {"metadata_sha256": "0" * 64},
                       {"sidecar_sha256": "0" * 64},
                       {"metadata_path": Path("metadata.json"), "metadata_sha256": "0" * 64},
                       {"metadata_path": Path("metadata.json"), "metadata_sha256": "bad", "sidecar_sha256": "0" * 64},
                       {"metadata_path": Path("metadata.json"), "metadata_sha256": "0" * 64, "sidecar_sha256": "bad"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                register_document_transcription(file_path=Path("absent.tiff"), text="Testo", **kwargs)

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
