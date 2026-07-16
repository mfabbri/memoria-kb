from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.military_glossary import (  # noqa: E402
    extract_military_glossary_mentions,
    load_military_glossary_entries,
    render_military_glossary_mentions_markdown,
)
from caduti_fonti_report.knowledge_catalog import default_military_glossary_dir  # noqa: E402


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


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class MilitaryGlossaryTests(unittest.TestCase):
    def test_loads_seed_glossary_entries(self) -> None:
        glossary_dir = default_military_glossary_dir()

        entries = load_military_glossary_entries(glossary_dir)

        self.assertGreaterEqual(len(entries), 5)
        division = next(entry for entry in entries if entry.entry_id == "military-glossary-entry:de:division")
        self.assertEqual(division.term, "Division")
        self.assertEqual(division.language, "de")
        self.assertEqual(division.review_status, "unreviewed")

    def test_extracts_candidates_from_text_document_without_verified_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "processed"
            glossary_dir = default_military_glossary_dir()
            text_path = text_dir / "manual_uploads" / "doc-1.text.json"
            write_json(
                text_path,
                _processed_text(
                    source_document_id="manual:doc-1",
                    document_class="word_document",
                    text="Nel documento appare il 26. Panzer-Division e un Bataillon nei pressi indicati.",
                ),
            )
            output_json = tmp_dir / "mentions.json"
            output_md = tmp_dir / "mentions.md"

            result = extract_military_glossary_mentions(
                text_dir=text_dir,
                glossary_dir=glossary_dir,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(result["@type"], "CandidateMilitaryGlossaryMentionSet")
        self.assertEqual(persisted["document_count"], 1)
        self.assertEqual(persisted["review_status"], "unreviewed")
        values = {mention["term"] for mention in persisted["documents"][0]["mentions"]}
        self.assertIn("Division", values)
        self.assertIn("Bataillon", values)
        mention = persisted["documents"][0]["mentions"][0]
        self.assertEqual(mention["@type"], "CandidateMilitaryGlossaryMention")
        self.assertEqual(mention["review_status"], "unreviewed")
        self.assertFalse(mention["claim_extraction_allowed"])
        self.assertFalse(mention["territorial_presence_claim_allowed"])
        self.assertIn("CandidateMilitaryGlossaryMention preview", markdown)
        serialized = json.dumps(persisted)
        self.assertNotIn("EvidenceClaim", serialized)
        self.assertNotIn("ProfilePatch", serialized)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn('"@type": "MilitaryUnit"', serialized)

    def test_extracts_from_image_ocr_text_and_preserves_image_provenance(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "processed"
            glossary_dir = default_military_glossary_dir()
            text_path = text_dir / "manual_uploads" / "scan-1.text.json"
            write_json(
                text_path,
                _processed_text(
                    source_document_id="manual:scan-1",
                    document_class="image_scan",
                    media_type="image/jpeg",
                    extraction_status="external_ocr_unreviewed",
                    raw_file="scans/karte-1944.jpg",
                    text="OCR non revisionato: Rgt. e Kompanie sono leggibili sulla scansione.",
                ),
            )

            result = extract_military_glossary_mentions(text_dir=text_dir, glossary_dir=glossary_dir)

        self.assertEqual(result["document_count"], 1)
        document = result["documents"][0]
        self.assertEqual(document["document_class"], "image_scan")
        self.assertEqual(document["media_type"], "image/jpeg")
        self.assertEqual(document["extraction_status"], "external_ocr_unreviewed")
        self.assertEqual(document["raw_file"], "scans/karte-1944.jpg")
        terms = {mention["term"] for mention in document["mentions"]}
        self.assertIn("Regiment", terms)
        self.assertIn("Kompanie", terms)
        for mention in document["mentions"]:
            self.assertEqual(mention["document_class"], "image_scan")
            self.assertEqual(mention["extraction_status"], "external_ocr_unreviewed")
            self.assertEqual(mention["review_status"], "unreviewed")

    def test_skips_images_without_ocr_text(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "processed"
            glossary_dir = default_military_glossary_dir()
            write_json(
                text_dir / "manual_uploads" / "scan-2.text.json",
                _processed_text(
                    source_document_id="manual:scan-2",
                    document_class="image_scan",
                    media_type="image/jpeg",
                    extraction_status="manual_ocr_required",
                    text_status="not_extracted",
                    text="",
                ),
            )

            result = extract_military_glossary_mentions(text_dir=text_dir, glossary_dir=glossary_dir)

        self.assertEqual(result["document_count"], 0)
        self.assertEqual(result["mention_count"], 0)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(result["skipped_documents"][0]["reason"], "text_not_extracted")

    def test_markdown_renderer_handles_empty_result(self) -> None:
        markdown = render_military_glossary_mentions_markdown(
            {
                "extraction_method": "deterministic_military_glossary_lookup",
                "glossary_dir": "../memoria-knowledge/glossary/military",
                "document_count": 0,
                "mention_count": 0,
                "skipped_count": 0,
                "review_status": "unreviewed",
                "documents": [],
            }
        )

        self.assertIn("Nessuna menzione candidata", markdown)
        self.assertIn("Menzioni candidate: `0`", markdown)


def _processed_text(
    *,
    source_document_id: str,
    document_class: str,
    text: str,
    media_type: str = "text/plain",
    extraction_status: str = "text_extracted",
    text_status: str = "extracted",
    raw_file: str = "raw/doc.txt",
) -> dict:
    return {
        "@type": "ProcessedDocumentText",
        "source_id": "manual_uploads",
        "source_document_id": source_document_id,
        "document_class": document_class,
        "claim_eligible": True,
        "review_status": "unreviewed",
        "raw_file": raw_file,
        "metadata_file": "processed/doc.metadata.json",
        "media_type": media_type,
        "extraction_status": extraction_status,
        "text_status": text_status,
        "text": text,
        "text_length": len(text),
        "text_sha256": "",
    }


if __name__ == "__main__":
    unittest.main()
