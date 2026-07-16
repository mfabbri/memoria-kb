from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.candidate_evidence_claims import (  # noqa: E402
    CandidateEvidenceClaimRecord,
)


class CandidateEvidenceClaimRecordTests(unittest.TestCase):
    def test_extracts_candidate_claim_fields_and_dedupe_key(self) -> None:
        payload = {
            "@id": "candidate-evidence-claim:abc",
            "@type": "CandidateEvidenceClaim",
            "person_candidate_id": "person:purocielo:andreoli-dino",
            "profile_id": "person:purocielo:andreoli-dino",
            "field": "birth.date",
            "value": "28 gennaio 1920",
            "normalized_value": "28 gennaio 1920",
            "source_id": "camalanca_html",
            "source_document_id": "doc-1",
            "evidence_span": "Nato il 28 gennaio 1920.",
            "context": "Nato il 28 gennaio 1920.",
            "chunk_id": "chunk-1",
            "weak_segment_id": "segment-1",
            "extraction_method": "document_entity_context_rules",
            "confidence": 0.85,
            "reasons": ["italian_textual_date_pattern", ""],
            "review_status": "unreviewed",
        }

        record = CandidateEvidenceClaimRecord.from_payload(payload)

        self.assertEqual(record.claim_id, "candidate-evidence-claim:abc")
        self.assertEqual(record.profile_id, "person:purocielo:andreoli-dino")
        self.assertEqual(record.field, "birth.date")
        self.assertEqual(record.value, "28 gennaio 1920")
        self.assertEqual(record.source_document_id, "doc-1")
        self.assertEqual(record.effective_profile_id, "person:purocielo:andreoli-dino")
        self.assertEqual(record.reasons, ("italian_textual_date_pattern",))
        self.assertEqual(record.reasons_text, "italian_textual_date_pattern")
        self.assertEqual(record.dedupe_key, ("person:purocielo:andreoli-dino", "doc-1", "birth.date", "28 gennaio 1920"))
        self.assertIs(record.payload, payload)

    def test_effective_profile_id_falls_back_to_person_candidate_id(self) -> None:
        record = CandidateEvidenceClaimRecord.from_payload(
            {
                "person_candidate_id": "person:purocielo:balboni-william",
                "source_document_id": "doc-1",
                "field": "birth.date",
                "normalized_value": "1921",
            }
        )

        self.assertEqual(record.effective_profile_id, "person:purocielo:balboni-william")
        self.assertEqual(record.dedupe_key, ("person:purocielo:balboni-william", "doc-1", "birth.date", "1921"))

    def test_missing_optional_shapes_are_empty_and_preview_safe(self) -> None:
        record = CandidateEvidenceClaimRecord.from_payload(
            {
                "@id": None,
                "profile_id": None,
                "reasons": "not-a-list",
            }
        )

        self.assertEqual(record.claim_id, "")
        self.assertEqual(record.profile_id, "")
        self.assertEqual(record.reasons, ())
        self.assertEqual(record.reasons_text, "")
        self.assertEqual(record.confidence, "")
        self.assertEqual(record.dedupe_key, ("", "", "", ""))

    def test_structured_extraction_has_higher_priority(self) -> None:
        generic = CandidateEvidenceClaimRecord.from_payload({"extraction_method": "document_entity_context_rules"})
        structured = CandidateEvidenceClaimRecord.from_payload({"extraction_method": "online_detail_structured_fields"})

        self.assertEqual(generic.priority(structured_extraction_method="online_detail_structured_fields"), 1)
        self.assertEqual(structured.priority(structured_extraction_method="online_detail_structured_fields"), 2)


if __name__ == "__main__":
    unittest.main()
