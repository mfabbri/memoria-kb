from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.candidate_place_updates import build_candidate_place_updates  # noqa: E402


PLACE_ID = "place:purocielo"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "places" / "purocielo.jsonld"


def claim(claim_id: str, field: str, value: str, **overrides: object) -> dict:
    payload = {
        "@type": "CandidateEvidenceClaim", "@id": claim_id, "place_id": PLACE_ID,
        "field": field, "value": value, "source_document_id": "doc:1", "source_id": "fixture",
        "source_url": "https://example.test/doc-1", "evidence_span": "Test evidence",
        "confidence": 0.72, "review_status": "unreviewed", "extraction_method": "fixture_rule",
    }
    payload.update(overrides)
    return payload


class CandidatePlaceUpdatesTests(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(__file__).resolve().parents[1] / ".tmp-tests"
        base.mkdir(exist_ok=True)
        self.root = base / f"test-{uuid.uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.place = self.root / "place.jsonld"
        self.place.write_bytes(FIXTURE.read_bytes())
        self.claims = self.root / "claims.json"

    def build(self, claims: list[dict]) -> dict:
        self.claims.write_text(json.dumps({"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": claims}), encoding="utf-8")
        return build_candidate_place_updates(candidate_claims_json=self.claims, place_jsonld=self.place)

    def test_preserves_provenance_and_inputs_for_existing_alias(self) -> None:
        first = claim("claim:1", "place.alternate_label", "Puro Cielo", chunk_id="chunk:1", provenance={"method": "offline_fixture"})
        second = claim("claim:2", "place.alternate_label", "Puro Cielo", source_document_id="doc:2", source_id="second-source", confidence=0.81)
        second["url"] = second.pop("source_url")
        second["url"] = "https://example.test/doc-2"
        before = self.place.read_bytes()
        expected_claims_bytes = json.dumps({"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": [second, first]}).encode("utf-8")
        payload = self.build([second, first])
        repeated = build_candidate_place_updates(candidate_claims_json=self.claims, place_jsonld=self.place)

        self.assertEqual(self.place.read_bytes(), before)
        self.assertEqual(self.claims.read_bytes(), expected_claims_bytes)
        self.assertEqual(payload, repeated)
        self.assertEqual(payload, self.build([first, second]))
        self.assertTrue(payload["preview_only"])
        self.assertFalse(payload["place_write_allowed"])
        update = payload["candidate_updates"][0]
        self.assertEqual(update["classification"], "existing")
        self.assertEqual(update["source_claims"], [first, second])
        self.assertEqual(update["source_claim_ids"], ["claim:1", "claim:2"])
        self.assertEqual(update["source_document_ids"], ["doc:1", "doc:2"])
        self.assertEqual(update["source_ids"], ["fixture", "second-source"])
        self.assertEqual(update["source_urls"], ["https://example.test/doc-1", "https://example.test/doc-2"])
        self.assertEqual(update["evidence_spans"], ["Test evidence"])
        self.assertEqual(update["confidence"], 0.81)
        self.assertEqual(update["review_status"], "pending")

    def test_conflicting_scalar_values_remain_visible(self) -> None:
        payload = self.build([
            claim("claim:other-name", "place.preferred_label", "Altro Purocielo"),
            claim("claim:current-name", "place.preferred_label", "Purocielo"),
        ])
        by_value = {item["candidate_value"]: item for item in payload["candidate_updates"]}
        conflict = by_value["Altro Purocielo"]
        self.assertEqual(conflict["classification"], "conflicting")
        self.assertEqual(conflict["current_values"], ["Purocielo"])
        self.assertEqual(conflict["competing_candidate_values"], ["Purocielo"])
        self.assertEqual(by_value["Purocielo"]["classification"], "existing")
        self.assertEqual(by_value["Purocielo"]["competing_candidate_values"], ["Altro Purocielo"])

    def test_new_alias_and_same_as_always_require_review(self) -> None:
        before = self.place.read_bytes()
        payload = self.build([
            claim("claim:alias", "place.alternate_label", "Purocielo candidato"),
            claim("claim:same-as", "place.same_as", "https://example.test/place/1"),
        ])
        for update in payload["candidate_updates"]:
            self.assertEqual(update["classification"], "new")
            self.assertEqual(update["review_status"], "pending")
            self.assertTrue(update["requires_human_review"])
            self.assertFalse(update["apply_allowed"])
            self.assertFalse(update["automatic_merge_allowed"])
        self.assertEqual({item["proposed_action"] for item in payload["candidate_updates"]}, {"review_same_as", "review_alternate_label"})
        self.assertEqual(self.place.read_bytes(), before)
        self.assertEqual(json.loads(self.place.read_text(encoding="utf-8"))["same_as"], [])

    def test_skips_other_place_missing_provenance_and_unsupported_fields(self) -> None:
        payload = self.build([
            claim("claim:other", "place.type", "building", place_id="place:other"),
            claim("claim:no-document", "place.type", "building", source_document_id=" "),
            claim("claim:no-source", "place.type", "building", source_id=None),
            claim("claim:person", "person.full_name", "Person Name"),
        ])
        self.assertEqual(payload["candidate_updates"], [])
        self.assertEqual({item["claim_id"]: item["reason"] for item in payload["skipped_claims"]}, {
            "claim:other": "other_place", "claim:no-document": "missing_source_document_id",
            "claim:no-source": "missing_source_id", "claim:person": "unsupported_field",
        })

    def test_subject_id_fallback_does_not_override_conflicting_place_id(self) -> None:
        fallback = claim("claim:fallback", "place.preferred_label", "Purocielo", subject_id=PLACE_ID)
        fallback.pop("place_id")
        payload = self.build([fallback, claim("claim:conflict", "place.type", "building", subject_id="place:other")])
        self.assertEqual(len(payload["candidate_updates"]), 1)
        self.assertEqual(payload["candidate_updates"][0]["place_id"], PLACE_ID)
        self.assertEqual(payload["skipped_claims"][0]["reason"], "conflicting_place_identity")

    def test_reviewed_and_missing_status_claims_cannot_be_requeued(self) -> None:
        reviewed = claim("claim:reviewed", "place.type", "building", review_status="reviewed")
        missing_status = claim("claim:no-status", "place.type", "building")
        missing_status.pop("review_status")
        null_status = claim("claim:null-status", "place.type", "building", review_status=None)
        pending = claim("claim:pending", "place.type", "building", review_status="pending")
        unreviewed = claim("claim:unreviewed", "place.type", "building")

        payload = self.build([reviewed, missing_status, null_status, pending, unreviewed])

        self.assertEqual(len(payload["candidate_updates"]), 1)
        self.assertEqual(payload["candidate_updates"][0]["source_claim_ids"], ["claim:unreviewed"])
        self.assertEqual(payload["candidate_updates"][0]["review_status"], "pending")
        self.assertEqual({item["claim_id"]: item["reason"] for item in payload["skipped_claims"]}, {
            "claim:reviewed": "claim_not_unreviewed",
            "claim:no-status": "claim_not_unreviewed",
            "claim:null-status": "claim_not_unreviewed",
            "claim:pending": "claim_not_unreviewed",
        })

    def test_same_as_identifiers_are_compared_exactly(self) -> None:
        place = json.loads(self.place.read_text(encoding="utf-8"))
        place["same_as"] = ["https://example.test/Place/1"]
        self.place.write_text(json.dumps(place), encoding="utf-8")
        payload = self.build([claim("claim:uri", "place.same_as", "https://example.test/place/1")])
        self.assertEqual(payload["candidate_updates"][0]["classification"], "new")

    def test_rejects_divergent_place_identifiers(self) -> None:
        place = json.loads(self.place.read_text(encoding="utf-8"))
        place["@id"] = "place:other"
        self.place.write_text(json.dumps(place), encoding="utf-8")
        self.claims.write_text(json.dumps({"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": []}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "divergent"):
            build_candidate_place_updates(candidate_claims_json=self.claims, place_jsonld=self.place)


if __name__ == "__main__":
    unittest.main()
