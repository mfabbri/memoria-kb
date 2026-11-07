from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.candidate_event_updates import build_candidate_event_updates
from caduti_fonti_report.document_analysis.event_linking import build_candidate_document_event_links
from caduti_fonti_report.document_analysis.mention_extraction import extract_document_mentions


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "events" / "battaglia-purocielo.jsonld"
EVENT_ID = "event:battaglia-purocielo"


class CandidateEventUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("event-update-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.claims = self.root / "claims.json"
        self.links = self.root / "links.json"
        self.event = self.root / "event.jsonld"
        self.event.write_bytes(FIXTURE.read_bytes())
        self.write_links([self.link()])

    def write(self, path: Path, payload: object) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def link(self, **changes: object) -> dict:
        return {"@type": "CandidateDocumentEventLink", "@id": "link:one", "event_id": EVENT_ID,
                "source_id": "fixture", "source_document_id": "doc:one", "weak_segment_id": "segment:one",
                "chunk_id": "chunk:one", "review_status": "unreviewed", "requires_human_review": True,
                "event_write_allowed": False, **changes}

    def claim(self, identifier: str = "claim:one", **changes: object) -> dict:
        return {"@type": "CandidateEvidenceClaim", "@id": identifier, "event_id": EVENT_ID,
                "source_id": "fixture", "source_document_id": "doc:one", "field": "event.date_start",
                "value": "1944-10-10", "confidence": 0.7, "review_status": "unreviewed", **changes}

    def write_links(self, links: list[object]) -> None:
        self.write(self.links, {"@type": "CandidateDocumentEventLinkSet", "preview_only": True,
                               "event_write_allowed": False, "candidate_document_event_links": links})

    def build(self, claims: list[object]) -> dict:
        self.write(self.claims, {"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": claims})
        return build_candidate_event_updates(candidate_claims_json=self.claims,
                                             candidate_event_links_json=self.links, event_jsonld=self.event)

    def test_composes_segment_mention_link_claim_and_preview_without_changing_inputs(self) -> None:
        before = FIXTURE.read_bytes()
        payload = json.loads(before)
        index = self.write(self.root / "index.json", {"@type": "HistoricalEventIndex", "events": [payload]})
        segments = self.root / "segments"
        self.write(segments / "fixture" / "one.weak-segments.json", {
            "@type": "WeakDocumentSegmentDocument", "source_id": "fixture", "source_document_id": "doc:one",
            "segments": [{"segment_id": "segment:one", "chunk_id": "chunk:one",
                          "segment_type": "archival_reference_context",
                          "text": "La Battaglia di Purocielo compare nella relazione."}],
        })
        mentions = self.root / "mentions"
        extract_document_mentions(segments_dir=segments, output_dir=mentions, events_index_json=index)
        link_set = build_candidate_document_event_links(mentions_dir=mentions, events_index_json=index, output_json=self.links)
        link = link_set["candidate_document_event_links"][0]
        claim = self.claim(candidate_document_event_link_id=link["@id"], weak_segment_id=link["weak_segment_id"],
                           chunk_id=link["chunk_id"], evidence_span="Battaglia di Purocielo")
        links_before = self.links.read_bytes()
        result = self.build([claim])
        claims_before = self.claims.read_bytes()
        repeated = build_candidate_event_updates(candidate_claims_json=self.claims,
                                                 candidate_event_links_json=self.links, event_jsonld=self.event)
        self.assertEqual(result, repeated)
        update = result["candidate_updates"][0]
        self.assertEqual(update["classification"], "new")
        self.assertEqual(update["source_claims"], [claim])
        self.assertEqual(update["candidate_document_event_links"], [link])
        self.assertEqual(update["source_document_ids"], ["doc:one"])
        self.assertEqual(link["review_status"], "unreviewed")
        self.assertEqual(update["review_status"], "pending")
        self.assertTrue(update["requires_human_review"])
        for key in ("apply_allowed", "automatic_merge_allowed", "event_write_allowed"):
            self.assertFalse(update[key])
            self.assertFalse(result[key])
        self.assertEqual(result["inputs"]["candidate_event_links"]["sha256"], hashlib.sha256(links_before).hexdigest())
        self.assertNotIn("participants", update)
        self.assertNotIn("human_verified", update)
        self.assertEqual((FIXTURE.read_bytes(), self.event.read_bytes(), self.links.read_bytes(), self.claims.read_bytes()),
                         (before, before, links_before, claims_before))

    def test_classifies_existing_conflicting_scalar_and_list_addition(self) -> None:
        result = self.build([self.claim("a", field="event.label", value="Battaglia di Purocielo"),
                             self.claim("b", field="event.label", value="Altro titolo"),
                             self.claim("c", field="event.place_labels", value="Faenza")])
        by_value = {item["candidate_value"]: item for item in result["candidate_updates"]}
        self.assertEqual(by_value["Battaglia di Purocielo"]["classification"], "existing")
        self.assertEqual(by_value["Altro titolo"]["classification"], "conflicting")
        self.assertEqual(by_value["Faenza"]["classification"], "new")

    def test_competing_values_for_empty_scalar_require_review_as_conflicting(self) -> None:
        result = self.build([self.claim("a"), self.claim("b", value="1944-10-11")])
        self.assertEqual([item["classification"] for item in result["candidate_updates"]], ["conflicting", "conflicting"])

    def test_rejects_other_event_divergent_identity_and_missing_source(self) -> None:
        result = self.build([self.claim("a", event_id="event:other"),
                             self.claim("b", subject_id="event:other"),
                             self.claim("c", source_document_id=""), self.claim("d", source_id="")])
        self.assertEqual(result["candidate_updates"], [])
        self.assertEqual([item["reason"] for item in result["skipped_claims"]],
                         ["other_event", "conflicting_event_identity", "missing_source_document_id", "missing_source_id"])

    def test_requires_compatible_link_including_explicit_segment_and_link_id(self) -> None:
        result = self.build([self.claim("a", source_document_id="doc:other"),
                             self.claim("b", candidate_document_event_link_id="link:other"),
                             self.claim("c", weak_segment_id="segment:other"),
                             self.claim("d", chunk_id="chunk:other")])
        self.assertEqual(result["candidate_updates"], [])
        self.assertEqual({item["reason"] for item in result["skipped_claims"]}, {"missing_compatible_event_link"})

    def test_invalid_or_duplicate_link_cannot_support_update(self) -> None:
        for links, reason in (([self.link(review_status="approved")], "link_not_review_only"),
                              ([self.link(source_id="")], "missing_link_source_id"),
                              ([self.link(), self.link()], "duplicate_link_id")):
            with self.subTest(reason=reason):
                self.write_links(links)
                result = self.build([self.claim()])
                self.assertEqual(result["candidate_updates"], [])
                self.assertEqual(result["skipped_links"][0]["reason"], reason)

    def test_rejects_participation_unsupported_type_review_and_invalid_values(self) -> None:
        result = self.build([self.claim("a", field="event.participants"), self.claim("b", field=["event.label"]),
                             self.claim("c", **{"@type": "EvidenceClaim"}),
                             self.claim("d", review_status="approved"), self.claim("e", value=[]),
                             self.claim("f", confidence=float("nan")), self.claim("g", confidence=True)])
        self.assertEqual(result["candidate_updates"], [])
        self.assertEqual([item["reason"] for item in result["skipped_claims"]],
                         ["unsupported_field", "unsupported_field", "unsupported_claim_type", "claim_not_unreviewed",
                          "missing_or_invalid_value", "invalid_confidence", "invalid_confidence"])

    def test_duplicate_or_divergent_claim_identifiers_are_audited(self) -> None:
        result = self.build([self.claim(), self.claim(value="1944-10-11"), self.claim("other", claim_id="divergent")])
        self.assertEqual(result["candidate_updates"], [])
        self.assertEqual([item["reason"] for item in result["skipped_claims"]],
                         ["duplicate_claim_id", "duplicate_claim_id", "conflicting_claim_identity"])

    def test_rejects_malformed_or_write_enabled_input_sets_and_divergent_event(self) -> None:
        self.build([])
        for path, payload in ((self.claims, {"@type": "CandidateEvidenceClaimSet"}),
                              (self.links, {"@type": "CandidateDocumentEventLinkSet", "candidate_document_event_links": [],
                                            "preview_only": True, "event_write_allowed": True}),
                              (self.event, {"@type": "HistoricalEvent", "event_id": EVENT_ID, "@id": "event:other"})):
            with self.subTest(path=path):
                originals = {item: item.read_bytes() for item in (self.event, self.links, self.claims)}
                self.write(path, payload)
                with self.assertRaises(ValueError):
                    build_candidate_event_updates(candidate_claims_json=self.claims,
                                                  candidate_event_links_json=self.links, event_jsonld=self.event)
                for item, raw in originals.items():
                    item.write_bytes(raw)


if __name__ == "__main__":
    unittest.main()
