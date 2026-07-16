from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.review_queue_items import ReviewQueueItemRecord  # noqa: E402


class ReviewQueueItemRecordTests(unittest.TestCase):
    def test_extracts_candidate_claim_fields(self) -> None:
        payload = {
            "item_id": "mvp-review-item:0030",
            "item_type": "candidate_claim_review",
            "subject_kind": "claim",
            "profile_id": "person:purocielo:andreoli-dino",
            "canonical_name": "Andreoli Dino",
            "source_document_id": "doc-andreoli",
            "source_item_id": "candidate-evidence-claim:recognition",
            "priority": " high ",
            "risk": " medium ",
            "question": "Il claim e' supportato dal documento?",
            "context": "Estratto candidato.",
            "raw_file": " documenti_da_processare/andreoli/doc.pdf ",
            "metadata_file": " documenti_processati/andreoli/doc.metadata.json ",
            "document_reference_note": " seed legacy CSV ",
            "allowed_decisions": ["confirm", "reject", "uncertain"],
            "candidate": {
                "field": "partisan.recognition_status",
                "value": "Partigiano Combattente",
            },
        }

        record = ReviewQueueItemRecord.from_payload(payload)

        self.assertEqual(record.item_id, "mvp-review-item:0030")
        self.assertEqual(record.item_type, "candidate_claim_review")
        self.assertEqual(record.profile_id, "person:purocielo:andreoli-dino")
        self.assertEqual(record.source_document_id, "doc-andreoli")
        self.assertEqual(record.priority, "high")
        self.assertEqual(record.risk, "medium")
        self.assertEqual(record.raw_file, "documenti_da_processare/andreoli/doc.pdf")
        self.assertEqual(record.metadata_file, "documenti_processati/andreoli/doc.metadata.json")
        self.assertEqual(record.document_reference_note, "seed legacy CSV")
        self.assertEqual(record.allowed_decisions, ("confirm", "reject", "uncertain"))
        self.assertEqual(record.allowed_decisions_text, "confirm, reject, uncertain")
        self.assertEqual(record.candidate_field, "partisan.recognition_status")
        self.assertEqual(record.candidate_value, "Partigiano Combattente")
        self.assertIs(record.payload, payload)

    def test_missing_candidate_keeps_empty_candidate_fields(self) -> None:
        record = ReviewQueueItemRecord.from_payload(
            {
                "item_id": "mvp-review-item:0002",
                "item_type": "person_document_link_review",
                "allowed_decisions": ["confirm", "", "uncertain"],
            }
        )

        self.assertEqual(record.item_id, "mvp-review-item:0002")
        self.assertEqual(record.allowed_decisions, ("confirm", "uncertain"))
        self.assertEqual(record.candidate_field, "")
        self.assertEqual(record.candidate_value, "")
        self.assertEqual(record.raw_file, "")
        self.assertEqual(record.metadata_file, "")
        self.assertEqual(record.document_reference_note, "")

    def test_invalid_optional_shapes_are_normalized_to_empty_values(self) -> None:
        record = ReviewQueueItemRecord.from_payload(
            {
                "item_id": None,
                "allowed_decisions": "confirm, reject",
                "candidate": ["not", "a", "dict"],
            }
        )

        self.assertEqual(record.item_id, "")
        self.assertEqual(record.allowed_decisions, ())
        self.assertEqual(record.allowed_decisions_text, "")
        self.assertEqual(record.candidate_field, "")
        self.assertEqual(record.candidate_value, "")


if __name__ == "__main__":
    unittest.main()
