from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mention_extraction import (  # noqa: E402
    extract_document_mentions,
    render_document_mentions_markdown,
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


def write_segments_payload(
    root_dir: Path,
    *,
    source_id: str = "manual_uploads",
    source_document_id: str = "doc:1",
    segments: list[dict[str, object]],
) -> Path:
    segments_dir = root_dir / source_id
    segments_dir.mkdir(parents=True, exist_ok=True)
    path = segments_dir / f"{source_document_id.replace(':', '-')}.weak-segments.json"
    payload = {
        "@type": "WeakDocumentSegmentDocument",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "chunk_file": f"{source_id}/{source_document_id}.chunks.json",
        "review_status": "unreviewed",
        "segment_count": len(segments),
        "segments": segments,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def segment(*, segment_id: str, segment_type: str, text: str) -> dict[str, object]:
    return {
        "@type": "WeakDocumentSegment",
        "@id": segment_id,
        "segment_id": segment_id,
        "source_id": "manual_uploads",
        "source_document_id": "doc:signals",
        "chunk_id": "physical-document-chunk:test",
        "chunk_index": 1,
        "segment_index": 1,
        "segment_type": segment_type,
        "chunk_char_start": 0,
        "chunk_char_end": len(text),
        "text": text,
        "review_status": "unreviewed",
    }


class DocumentMentionExtractionTests(unittest.TestCase):
    def test_extracts_candidate_mentions_with_provenance_and_no_claims(self) -> None:
        segments = [
            segment(
                segment_id="weak-document-segment:person",
                segment_type="person_mention_context",
                text="Andreoli Dino e Rossi Mario sono citati nella relazione.",
            ),
            segment(
                segment_id="weak-document-segment:formation",
                segment_type="formation_context",
                text="La 36a Brigata Garibaldi opera nella zona.",
            ),
            segment(
                segment_id="weak-document-segment:archive",
                segment_type="archival_reference_context",
                text="Riferimento archivistico RH 36/117/3 nel fascicolo 12.",
            ),
        ]
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            output_dir = tmp_dir / "mentions"
            output_json = tmp_dir / "document_mentions.json"
            output_md = tmp_dir / "document_mentions.md"
            write_segments_payload(segments_dir, source_document_id="doc:signals", segments=segments)

            payload = extract_document_mentions(
                segments_dir=segments_dir,
                output_dir=output_dir,
                output_json=output_json,
                output_md=output_md,
            )
            document = payload["documents"][0]
            mentions = document["mentions"]
            persisted = json.loads((output_dir / "manual_uploads" / "doc-signals.mentions.json").read_text("utf-8"))
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        mention_types = {mention["@type"] for mention in mentions}
        mention_kinds = {mention["mention_kind"] for mention in mentions}
        self.assertEqual(payload["@type"], "DocumentMentionCandidateSet")
        self.assertEqual(payload["document_count"], 1)
        self.assertEqual(payload["mention_count"], 5)
        self.assertEqual(document["@type"], "DocumentMentionCandidateDocument")
        self.assertEqual(document["review_status"], "unreviewed")
        self.assertEqual(persisted["mention_count"], 5)
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)
        self.assertEqual(
            mention_types,
            {"PersonMentionCandidate", "FormationMentionCandidate", "ArchivalReferenceMentionCandidate"},
        )
        self.assertEqual(mention_kinds, {"person", "formation", "archival_reference"})
        self.assertTrue(all(mention["review_status"] == "unreviewed" for mention in mentions))
        self.assertTrue(all(mention["candidate_profile_id"] == "" for mention in mentions))
        self.assertTrue(all(mention["claim_extraction_allowed"] is False for mention in mentions))
        self.assertTrue(all(mention["chunk_id"] == "physical-document-chunk:test" for mention in mentions))
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_skips_segments_without_mentions_without_promoting_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            write_segments_payload(
                segments_dir,
                source_document_id="doc:none",
                segments=[
                    segment(
                        segment_id="weak-document-segment:none",
                        segment_type="person_mention_context",
                        text="testo generico senza segnali utili",
                    )
                ],
            )

            payload = extract_document_mentions(segments_dir=segments_dir)

        self.assertEqual(payload["document_count"], 1)
        self.assertEqual(payload["mention_count"], 0)
        self.assertEqual(payload["documents"][0]["mentions"], [])
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_filters_navigation_false_positive_person_mentions_but_keeps_real_names(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            write_segments_payload(
                segments_dir,
                source_document_id="doc:false-positive-persons",
                segments=[
                    segment(
                        segment_id="weak-document-segment:navigation",
                        segment_type="person_mention_context",
                        text=(
                            "Alfonso Bagni e Adelmo Brini sono citati. "
                            "Malanca Salta Malanca Centro Malanca Menu Malanca Video "
                            "Info Mostra Visita Informazioni Documenti Statuto."
                        ),
                    )
                ],
            )

            payload = extract_document_mentions(segments_dir=segments_dir)

        values = {mention["value"] for mention in payload["documents"][0]["mentions"]}
        self.assertIn("Alfonso Bagni", values)
        self.assertIn("Adelmo Brini", values)
        self.assertNotIn("Malanca Salta", values)
        self.assertNotIn("Malanca Centro", values)
        self.assertNotIn("Malanca Menu", values)
        self.assertNotIn("Malanca Video", values)
        self.assertNotIn("Info Mostra", values)
        self.assertNotIn("Visita Informazioni", values)
        self.assertNotIn("Documenti Statuto", values)
        self.assertTrue(all(mention["review_status"] == "unreviewed" for mention in payload["documents"][0]["mentions"]))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_extracts_place_and_date_mentions_without_jsonld_linking_or_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            write_segments_payload(
                segments_dir,
                source_document_id="doc:place-date",
                segments=[
                    segment(
                        segment_id="weak-document-segment:place-date",
                        segment_type="person_mention_context",
                        text=(
                            "Andreoli Dino risulta collegato a Purocielo il 12 marzo 1920 "
                            "e a Ca' di Malanca nel settembre 1944."
                        ),
                    )
                ],
            )

            payload = extract_document_mentions(segments_dir=segments_dir)

        mentions = payload["documents"][0]["mentions"]
        kinds = {mention["mention_kind"] for mention in mentions}
        values = {mention["value"] for mention in mentions}
        place_mentions = [mention for mention in mentions if mention["mention_kind"] == "place"]
        date_mentions = [mention for mention in mentions if mention["mention_kind"] == "date"]

        self.assertIn("person", kinds)
        self.assertIn("place", kinds)
        self.assertIn("date", kinds)
        self.assertIn("Purocielo", values)
        self.assertIn("Ca' di Malanca", values)
        self.assertIn("12 marzo 1920", values)
        self.assertIn("settembre 1944", values)
        self.assertTrue(all(mention["@type"] == "PlaceMentionCandidate" for mention in place_mentions))
        self.assertTrue(all(mention["@type"] == "DateMentionCandidate" for mention in date_mentions))
        self.assertTrue(all(mention["candidate_place_id"] == "" for mention in place_mentions))
        self.assertTrue(all(mention["candidate_date_id"] == "" for mention in date_mentions))
        self.assertTrue(all(mention["candidate_event_id"] == "" for mention in [*place_mentions, *date_mentions]))
        self.assertTrue(all(mention["claim_extraction_allowed"] is False for mention in [*place_mentions, *date_mentions]))
        self.assertTrue(all(mention["review_status"] == "unreviewed" for mention in [*place_mentions, *date_mentions]))
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_does_not_extract_bare_year_as_date_mention(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            write_segments_payload(
                segments_dir,
                source_document_id="doc:bare-year",
                segments=[
                    segment(
                        segment_id="weak-document-segment:bare-year",
                        segment_type="formation_context",
                        text="La Brigata Garibaldi opera nella zona nel 1944.",
                    )
                ],
            )

            payload = extract_document_mentions(segments_dir=segments_dir)

        date_values = [
            mention["value"]
            for mention in payload["documents"][0]["mentions"]
            if mention["mention_kind"] == "date"
        ]
        self.assertEqual(date_values, [])

    def test_person_filter_does_not_remove_formation_or_archival_mentions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            write_segments_payload(
                segments_dir,
                source_document_id="doc:supporting-mentions",
                segments=[
                    segment(
                        segment_id="weak-document-segment:formation",
                        segment_type="formation_context",
                        text="La 36a Brigata Garibaldi compare nella relazione.",
                    ),
                    segment(
                        segment_id="weak-document-segment:archive",
                        segment_type="archival_reference_context",
                        text="Il riferimento RH 36/117/3 resta da verificare.",
                    ),
                ],
            )

            payload = extract_document_mentions(segments_dir=segments_dir)

        kinds = {mention["mention_kind"] for mention in payload["documents"][0]["mentions"]}
        values = {mention["value"] for mention in payload["documents"][0]["mentions"]}
        self.assertIn("formation", kinds)
        self.assertIn("archival_reference", kinds)
        self.assertTrue(any(value.startswith("36a Brigata Garibaldi") for value in values))
        self.assertIn("RH 36/117/3", values)

    def test_skips_invalid_segment_documents(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            segments_dir.mkdir()
            (segments_dir / "bad.weak-segments.json").write_text(
                json.dumps({"@type": "PhysicalDocumentChunkDocument", "source_document_id": "doc:bad"}),
                encoding="utf-8",
            )

            payload = extract_document_mentions(segments_dir=segments_dir)

        self.assertEqual(payload["document_count"], 0)
        self.assertEqual(payload["mention_count"], 0)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["skipped_documents"][0]["reason"], "unsupported_payload_type")

    def test_markdown_renderer_lists_mentions_for_review(self) -> None:
        payload = {
            "extraction_method": "deterministic_mention_candidate_rules",
            "document_count": 1,
            "mention_count": 1,
            "skipped_count": 0,
            "documents": [
                {
                    "source_document_id": "doc:1",
                    "source_id": "manual_uploads",
                    "review_status": "unreviewed",
                    "mention_count": 1,
                    "segments_file": "doc.weak-segments.json",
                    "mentions": [
                        {
                            "mention_id": "document-mention-candidate:abc",
                            "mention_kind": "person",
                            "value": "Andreoli Dino",
                            "confidence": 0.62,
                        }
                    ],
                }
            ],
        }

        markdown = render_document_mentions_markdown(payload)

        self.assertIn("# DocumentMentionCandidate preview", markdown)
        self.assertIn("document-mention-candidate:abc", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
