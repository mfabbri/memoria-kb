from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.event_linking import build_candidate_document_event_links  # noqa: E402
from caduti_fonti_report.document_analysis.mention_extraction import extract_document_mentions  # noqa: E402


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "events" / "battaglia-purocielo.jsonld"


class DocumentEventLinkingTests(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(__file__).resolve().parents[1] / ".tmp-tests"
        base.mkdir(exist_ok=True)
        self.root = base / f"test-{uuid.uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.mentions = self.root / "mentions"
        self.mentions.mkdir()
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.event = {key: fixture[key] for key in ("event_id", "label", "review_status")}
        self.index = self.write(self.root / "events.json", {"@type": "HistoricalEventIndex", "events": [self.event]})

    def write(self, path: Path, payload: object) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def mention(self, mention_id: str = "mention:event", **changes: object) -> dict:
        return {"@type": "EventMentionCandidate", "mention_kind": "event", "mention_id": mention_id,
                "value": self.event["label"], "source_id": "fixture", "source_document_id": "doc:one",
                "chunk_id": "chunk:one", "weak_segment_id": "segment:one", "context": "Una relazione cita l'evento.",
                "segment_char_start": 10, "segment_char_end": 31, "confidence": 0.78,
                "review_status": "unreviewed", **changes}

    def write_mentions(self, mentions: list[object], filename: str = "one.mentions.json", **changes: object) -> Path:
        return self.write(self.mentions / filename, {"@type": "DocumentMentionCandidateDocument",
            "source_id": "fixture", "source_document_id": "doc:one", "mentions": mentions, **changes})

    def build(self, **kwargs: object) -> dict:
        return build_candidate_document_event_links(mentions_dir=self.mentions, events_index_json=self.index, **kwargs)

    def test_composes_event_extraction_and_preserves_hashed_provenance_without_writes(self) -> None:
        segments = self.root / "segments"
        text = "La BATTAGLIA DI PUROCIELO compare nella relazione."
        source = self.write(segments / "fixture" / "one.weak-segments.json", {
            "@type": "WeakDocumentSegmentDocument", "source_id": "fixture", "source_document_id": "doc:one",
            "segments": [{"segment_id": "segment:one", "segment_type": "archival_reference_context",
                          "chunk_id": "chunk:one", "text": text}],
        })
        fixture_before, index_before, source_before = FIXTURE.read_bytes(), self.index.read_bytes(), source.read_bytes()
        extract_document_mentions(segments_dir=segments, output_dir=self.mentions, events_index_json=self.index)
        mention_file = self.mentions / "fixture" / "doc-one.mentions.json"
        mention_before = mention_file.read_bytes()
        result = self.build(output_json=self.root / "links.json", output_md=self.root / "links.md")
        repeated = self.build()

        self.assertEqual(result, repeated)
        self.assertEqual(result["link_count"], 1)
        link = result["candidate_document_event_links"][0]
        self.assertEqual(link["event_id"], self.event["event_id"])
        self.assertEqual(link["matched_label"], "BATTAGLIA DI PUROCIELO")
        self.assertEqual(text[link["segment_char_start"]:link["segment_char_end"]], link["matched_label"])
        self.assertEqual((link["source_id"], link["source_document_id"], link["chunk_id"], link["weak_segment_id"]),
                         ("fixture", "doc:one", "chunk:one", "segment:one"))
        self.assertEqual(link["events_index"]["sha256"], hashlib.sha256(index_before).hexdigest())
        self.assertEqual(link["mentions_source"]["sha256"], hashlib.sha256(mention_before).hexdigest())
        self.assertEqual(link["confidence"], 0.78)
        self.assertEqual(link["review_status"], "unreviewed")
        self.assertTrue(link["requires_human_review"])
        self.assertFalse(link["event_write_allowed"])
        self.assertFalse(link["claim_extraction_allowed"])
        self.assertIn("event_link_not_person_participation", link["warnings"])
        self.assertEqual(json.loads((self.root / "links.json").read_text(encoding="utf-8")), result)
        self.assertIn("CandidateDocumentEventLink preview", (self.root / "links.md").read_text(encoding="utf-8"))
        self.assertEqual((FIXTURE.read_bytes(), self.index.read_bytes(), source.read_bytes(), mention_file.read_bytes()),
                         (fixture_before, index_before, source_before, mention_before))

    def test_shared_label_is_ambiguous_and_never_resolved_by_catalog_order(self) -> None:
        self.write(self.index, {"@type": "HistoricalEventIndex", "events": [self.event, {**self.event, "event_id": "event:other"}]})
        self.write_mentions([self.mention()])
        result = self.build()
        self.assertEqual(result["candidate_document_event_links"], [])
        self.assertEqual(result["skipped_mentions"][0]["reason"], "ambiguous_event_label")

    def test_whole_label_matching_does_not_invent_punctuation_or_substring_equivalence(self) -> None:
        self.write_mentions([self.mention("mention:substring", value="Battaglia di Purocielo Nord"),
                             self.mention("mention:punctuation", value="Battaglia-di-Purocielo")])
        result = self.build()
        self.assertEqual(result["link_count"], 0)
        self.assertEqual([item["reason"] for item in result["skipped_mentions"]], ["event_not_found", "event_not_found"])

    def test_missing_or_conflicting_provenance_and_wrong_types_are_audited(self) -> None:
        mentions = [self.mention("mention:no-document", source_document_id=" "),
                    self.mention("mention:no-source", source_id=None),
                    self.mention("mention:mismatch", source_document_id="doc:other"),
                    self.mention("mention:wrong-type", **{"@type": "PlaceMentionCandidate"}),
                    self.mention("mention:reviewed", review_status="reviewed")]
        self.write_mentions(mentions)
        result = self.build()
        self.assertEqual(result["link_count"], 0)
        self.assertEqual({item["mention_id"]: item["reason"] for item in result["skipped_mentions"]}, {
            "mention:no-document": "missing_source_document_id", "mention:no-source": "missing_source_id",
            "mention:mismatch": "document_provenance_mismatch", "mention:wrong-type": "unsupported_mention_type",
            "mention:reviewed": "mention_not_unreviewed",
        })

    def test_same_segment_duplicates_are_audited_but_distinct_segments_remain(self) -> None:
        self.write_mentions([self.mention("mention:first"), self.mention("mention:duplicate"),
                             self.mention("mention:second", weak_segment_id="segment:two")])
        result = self.build()
        self.assertEqual(result["link_count"], 2)
        self.assertEqual(result["skipped_mentions"][0]["reason"], "duplicate_event_link_in_segment")
        self.assertEqual(result["skipped_mentions"][0]["mention_id"], "mention:duplicate")

    def test_changed_index_provenance_and_boilerplate_cannot_create_links(self) -> None:
        self.write_mentions([self.mention("mention:stale", event_label_index={"sha256": "a" * 64}),
                             self.mention("mention:menu", context="Menu Home - Battaglia di Purocielo")])
        result = self.build()
        self.assertEqual(result["link_count"], 0)
        self.assertEqual([item["reason"] for item in result["skipped_mentions"]],
                         ["event_index_provenance_mismatch", "navigation_or_boilerplate_context"])

    def test_unsupported_and_malformed_documents_are_audited(self) -> None:
        self.write(self.mentions / "wrong.mentions.json", {"@type": "Other", "mentions": []})
        (self.mentions / "broken.mentions.json").write_text("{", encoding="utf-8")
        self.write(self.mentions / "not-list.mentions.json", {"@type": "DocumentMentionCandidateDocument", "mentions": {}})
        result = self.build()
        self.assertEqual(result["link_count"], 0)
        self.assertEqual({item["reason"] for item in result["skipped_documents"]},
                         {"unsupported_payload_type", "unreadable_mentions_payload", "mentions_not_list"})

    def test_invalid_event_index_fails_before_outputs_and_inputs_cannot_be_overwritten(self) -> None:
        self.write_mentions([self.mention()])
        with self.assertRaisesRegex(ValueError, "overwrite"):
            self.build(output_json=self.index)
        output = self.root / "must-not-exist.json"
        for events in ([self.event, self.event], [{"event_id": 42, "label": "Event"}], [{**self.event, "@id": "event:other"}]):
            with self.subTest(events=events):
                self.write(self.index, {"@type": "HistoricalEventIndex", "events": events})
                with self.assertRaises(ValueError):
                    self.build(output_json=output)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
