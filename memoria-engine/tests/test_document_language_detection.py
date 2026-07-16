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

from caduti_fonti_report.document_analysis.language_detection import (  # noqa: E402
    detect_document_languages,
    render_document_language_markdown,
)


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


def write_text_payload(
    root_dir: Path,
    *,
    source_document_id: str,
    text: str,
    text_status: str = "extracted",
) -> Path:
    source_id = "manual_uploads"
    text_dir = root_dir / source_id
    text_dir.mkdir(parents=True, exist_ok=True)
    path = text_dir / f"{source_document_id.replace(':', '-')}.text.json"
    payload = {
        "@type": "ProcessedDocumentText",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "document_class": "word_document",
        "claim_eligible": True,
        "review_status": "unreviewed",
        "raw_file": f"{source_id}/{source_document_id}.docx",
        "metadata_file": f"{source_id}/{source_document_id}.metadata.json",
        "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "extraction_status": "text_extracted" if text_status == "extracted" else "manual_ocr_required",
        "text_status": text_status,
        "text": text,
        "text_length": len(text),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class DocumentLanguageDetectionTests(unittest.TestCase):
    def test_detects_italian_german_and_english_texts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            write_text_payload(
                text_dir,
                source_document_id="doc:it",
                text="Documento di archivio della Resistenza. Nato nel comune e partigiano della brigata.",
            )
            write_text_payload(
                text_dir,
                source_document_id="doc:de",
                text="Das Archiv und die Akten nennen den Ort. Geboren und gestorben im Krieg.",
            )
            write_text_payload(
                text_dir,
                source_document_id="doc:en",
                text="The archive record shows the born and died date, service place and war document.",
            )

            payload = detect_document_languages(text_dir=text_dir)

        by_doc = {item["source_document_id"]: item for item in payload["language_assessments"]}
        self.assertEqual(by_doc["doc:it"]["primary_language"], "it")
        self.assertEqual(by_doc["doc:de"]["primary_language"], "de")
        self.assertEqual(by_doc["doc:en"]["primary_language"], "en")
        self.assertTrue(all(item["review_status"] == "unreviewed" for item in by_doc.values()))
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_marks_mixed_language_signals(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            write_text_payload(
                text_dir,
                source_document_id="doc:mixed",
                text=(
                    "Documento di archivio della Resistenza e della brigata. "
                    "Das Archiv und die Akten nennen den Ort und den Krieg."
                ),
            )

            payload = detect_document_languages(text_dir=text_dir)

        assessment = payload["language_assessments"][0]
        self.assertTrue(assessment["is_multilingual"])
        self.assertIn("mixed_language_signals", assessment["warnings"])
        self.assertIn(assessment["primary_language"], {"it", "de"})

    def test_short_text_becomes_undetermined_with_warning(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            write_text_payload(text_dir, source_document_id="doc:short", text="Dino")

            payload = detect_document_languages(text_dir=text_dir, min_text_chars=40)

        assessment = payload["language_assessments"][0]
        self.assertEqual(assessment["primary_language"], "und")
        self.assertIn("text_too_short", assessment["warnings"])
        self.assertIn("language_undetermined", assessment["warnings"])

    def test_skips_not_extracted_documents_and_writes_outputs(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            output_dir = tmp_dir / "languages"
            output_json = tmp_dir / "language.json"
            output_md = tmp_dir / "language.md"
            write_text_payload(text_dir, source_document_id="doc:ok", text="Document archive and war service record.")
            write_text_payload(text_dir, source_document_id="doc:missing", text="", text_status="not_extracted")

            payload = detect_document_languages(
                text_dir=text_dir,
                output_dir=output_dir,
                output_json=output_json,
                output_md=output_md,
            )
            sidecar = output_dir / "manual_uploads" / "doc-ok.language.json"
            sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        self.assertEqual(payload["assessment_count"], 1)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["skipped_documents"][0]["reason"], "text_not_extracted")
        self.assertEqual(sidecar_payload["@type"], "DocumentLanguageAssessment")
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)

    def test_markdown_renderer_lists_language_assessments(self) -> None:
        payload = {
            "detection_method": "deterministic_marker_language_detection",
            "assessment_count": 1,
            "skipped_count": 0,
            "language_assessments": [
                {
                    "source_document_id": "doc:1",
                    "primary_language": "it",
                    "confidence": 0.91,
                    "is_multilingual": False,
                    "review_status": "unreviewed",
                    "warnings": [],
                    "text_file": "doc.text.json",
                }
            ],
        }

        markdown = render_document_language_markdown(payload)

        self.assertIn("# DocumentLanguageAssessment preview", markdown)
        self.assertIn("doc:1", markdown)
        self.assertIn("Lingua primaria: `it`", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
