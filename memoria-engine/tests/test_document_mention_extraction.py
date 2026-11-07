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

from caduti_fonti_report.document_analysis.mention_extraction import (  # noqa: E402
    extract_document_mentions,
    main,
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


def write_event_index(root_dir: Path, *, events: list[dict[str, object]] | None = None) -> Path:
    fixture = Path(__file__).resolve().parent / "fixtures" / "events" / "battaglia-purocielo.jsonld"
    event = json.loads(fixture.read_text(encoding="utf-8"))
    path = root_dir / "events.index.jsonld"
    path.write_text(json.dumps({
        "@type": "HistoricalEventIndex",
        "events": events if events is not None else [{"event_id": event["event_id"], "label": event["label"]}],
    }), encoding="utf-8")
    return path


class DocumentMentionExtractionTests(unittest.TestCase):
    def test_event_label_mentions_preserve_source_span_and_unresolved_identity(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir, output_dir = tmp_dir / "segments", tmp_dir / "mentions"
            text = "La BATTAGLIA DI PUROCIELO compare nella relazione."
            source = write_segments_payload(segments_dir, source_document_id="doc:event", segments=[
                segment(segment_id="segment:event", segment_type="archival_reference_context", text=text),
            ])
            index = write_event_index(tmp_dir)
            original = {path: path.read_bytes() for path in (source, index)}
            payload = extract_document_mentions(segments_dir=segments_dir, output_dir=output_dir, events_index_json=index)
            repeated = extract_document_mentions(segments_dir=segments_dir, output_dir=output_dir, events_index_json=index)
            events = [item for item in payload["documents"][0]["mentions"] if item["mention_kind"] == "event"]
            self.assertEqual(payload, repeated)
            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event["@type"], "EventMentionCandidate")
            self.assertEqual(event["value"], "BATTAGLIA DI PUROCIELO")
            self.assertEqual(text[event["segment_char_start"]:event["segment_char_end"]], event["value"])
            self.assertEqual(event["source_id"], "manual_uploads")
            self.assertEqual(event["source_document_id"], "doc:event")
            self.assertEqual(event["weak_segment_id"], "segment:event")
            self.assertEqual(event["chunk_id"], "physical-document-chunk:test")
            self.assertIn(event["value"], event["context"])
            self.assertEqual(event["event_label_index"], {"path": str(index), "sha256": hashlib.sha256(original[index]).hexdigest()})
            self.assertEqual(event["candidate_event_id"], "")
            self.assertNotIn("event_id", event)
            self.assertEqual(event["review_status"], "unreviewed")
            self.assertFalse(event["claim_extraction_allowed"])
            self.assertIn("mention_candidate_not_identity_resolution", event["warnings"])
            self.assertIn("event_mention_not_event_link", event["warnings"])
            self.assertIn("mention_candidate_not_verified_fact", event["warnings"])
            self.assertEqual({path: path.read_bytes() for path in original}, original)
            persisted = json.loads((output_dir / "manual_uploads" / "doc-event.mentions.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted, payload["documents"][0])

    def test_event_extraction_requires_whole_explicit_label_and_allowed_segment(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            write_segments_payload(segments_dir, segments=[
                segment(segment_id="segment:partial", segment_type="person_mention_context", text="Battaglia di PurocieloNord; Battaglia di un altro luogo."),
                segment(segment_id="segment:unsupported", segment_type="generic_text", text="Battaglia di Purocielo"),
            ])
            payload = extract_document_mentions(segments_dir=segments_dir, events_index_json=write_event_index(tmp_dir))
        self.assertEqual([item for item in payload["documents"][0]["mentions"] if item["mention_kind"] == "event"], [])

    def test_event_label_punctuation_is_literal_and_span_preserves_the_full_label(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            text = "Citata Operazione (A). nella relazione; Operazione A non coincide."
            write_segments_payload(segments_dir, segments=[segment(
                segment_id="segment:event", segment_type="archival_reference_context", text=text,
            )])
            index = write_event_index(tmp_dir, events=[{"event_id": "event:operation", "label": "Operazione (A)."}])
            payload = extract_document_mentions(segments_dir=segments_dir, events_index_json=index)
        events = [item for item in payload["documents"][0]["mentions"] if item["mention_kind"] == "event"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["value"], "Operazione (A).")
        self.assertEqual(text[events[0]["segment_char_start"]:events[0]["segment_char_end"]], events[0]["value"])

    def test_no_event_index_keeps_legacy_output_and_shared_labels_do_not_assign_identity(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir = tmp_dir / "segments"
            write_segments_payload(segments_dir, segments=[
                segment(segment_id="segment:event", segment_type="formation_context", text="Battaglia di Purocielo"),
            ])
            legacy = extract_document_mentions(segments_dir=segments_dir)
            self.assertEqual(legacy, extract_document_mentions(segments_dir=segments_dir, events_index_json=None))
            self.assertNotIn("event_label_index", legacy)
            self.assertFalse(any(item["mention_kind"] == "event" for item in legacy["documents"][0]["mentions"]))
            index = write_event_index(tmp_dir, events=[
                {"event_id": "event:one", "label": "Battaglia di Purocielo"},
                {"event_id": "event:two", "label": "Battaglia di Purocielo"},
            ])
            payload = extract_document_mentions(segments_dir=segments_dir, events_index_json=index)
        events = [item for item in payload["documents"][0]["mentions"] if item["mention_kind"] == "event"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["candidate_event_id"], "")

    def test_malformed_event_indices_fail_before_outputs_are_written(self) -> None:
        cases = [
            {"@type": "Other", "events": []},
            {"@type": "HistoricalEventIndex", "events": {}},
            {"@type": "HistoricalEventIndex", "events": [{"event_id": "event:one", "label": " "}]},
            {"@type": "HistoricalEventIndex", "events": [{"event_id": 42, "label": "Label"}]},
            {"@type": "HistoricalEventIndex", "events": [{"event_id": "event:one", "label": "Label"}, {"event_id": "event:one", "label": "Other"}]},
            {"@type": "HistoricalEventIndex", "events": [{"event_id": "event:one", "@id": "event:other", "label": "Label"}]},
        ]
        for index_payload in cases:
            with self.subTest(index=index_payload), workspace_temp_dir() as tmp_dir:
                index, output = tmp_dir / "events.json", tmp_dir / "result.json"
                index.write_text(json.dumps(index_payload), encoding="utf-8")
                with self.assertRaises(ValueError):
                    extract_document_mentions(segments_dir=tmp_dir, events_index_json=index, output_json=output)
                self.assertFalse(output.exists())

    def test_cli_accepts_explicit_event_index(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            segments_dir, output_dir = tmp_dir / "segments", tmp_dir / "mentions"
            write_segments_payload(segments_dir, segments=[segment(segment_id="segment:event", segment_type="person_mention_context", text="Battaglia di Purocielo")])
            index, output_json, output_md = write_event_index(tmp_dir), tmp_dir / "result.json", tmp_dir / "result.md"
            arguments = ["mention_extraction", "--segments-dir", str(segments_dir), "--output-dir", str(output_dir),
                         "--events-index-json", str(index), "--output-json", str(output_json), "--output-md", str(output_md)]
            with patch("sys.argv", arguments), patch("builtins.print"):
                self.assertEqual(main(), 0)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertTrue(any(item["mention_kind"] == "event" for item in payload["documents"][0]["mentions"]))

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
