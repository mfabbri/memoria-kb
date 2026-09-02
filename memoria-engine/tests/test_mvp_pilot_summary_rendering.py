from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_pilot_summary import (  # noqa: E402
    _build_document_duplicate_diagnostics,
    _build_reviewable_document_signals,
    render_mvp_pilot_summary_markdown,
)
from caduti_fonti_report.document_analysis.mvp_pilot_package_status import (  # noqa: E402
    pilot_package_status_and_action,
)
from caduti_fonti_report.document_analysis.mvp_pilot_readiness import (  # noqa: E402
    readiness_status_and_action,
)
from caduti_fonti_report.document_analysis.mvp_pilot_profile_readiness import (  # noqa: E402
    build_profile_readiness,
)


class MvpPilotSummaryRenderingTests(unittest.TestCase):
    def test_profile_readiness_builder_preserves_profile_document_intersection(self) -> None:
        readiness = build_profile_readiness(
            profiles=[{"profile_id": "person:one", "canonical_name": "One"}],
            documents=[{"source_document_id": "doc-1"}],
            links=[{"profile_id": "person:one", "source_document_id": "doc-1"}],
            claims=[{"profile_id": "person:one", "source_document_id": "doc-other"}],
            reviewable_document_signals=[
                {"profile_id": "person:one", "signals": [{"source_document_id": "doc-1"}]}
            ],
        )

        self.assertEqual(readiness[0]["document_count"], 1)
        self.assertEqual(readiness[0]["candidate_evidence_claim_count"], 1)
        self.assertEqual(readiness[0]["readiness_status"], "ready_for_review")

    def test_profile_readiness_status_and_action_preserves_decision_order(self) -> None:
        cases = [
            (dict(document_count=0, link_count=0, claim_count=0, signal_count=0), "needs_documents"),
            (dict(document_count=1, link_count=0, claim_count=0, signal_count=0), "needs_links"),
            (dict(document_count=1, link_count=1, claim_count=0, signal_count=1), "needs_signal_review"),
            (dict(document_count=1, link_count=1, claim_count=0, signal_count=0), "needs_claims"),
            (dict(document_count=1, link_count=1, claim_count=1, signal_count=0), "ready_for_review"),
        ]
        for inputs, expected_status in cases:
            with self.subTest(inputs=inputs):
                self.assertEqual(readiness_status_and_action(**inputs)[0], expected_status)

    def test_pilot_package_status_and_action_covers_empty_and_signal_states(self) -> None:
        self.assertEqual(
            pilot_package_status_and_action(
                profile_count=0,
                document_count=0,
                link_count=0,
                claim_count=0,
                signal_count=0,
                ready_count=0,
                blockers=[],
            )[0],
            "needs_profiles",
        )
        self.assertEqual(
            pilot_package_status_and_action(
                profile_count=1,
                document_count=1,
                link_count=1,
                claim_count=0,
                signal_count=1,
                ready_count=0,
                blockers=[],
            ),
            (
                "needs_document_signal_review",
                "Revisionare le piste documentali e segmentare i documenti multi-scheda prima dei claim.",
            ),
        )

    def test_pilot_package_status_and_action_covers_ready_states(self) -> None:
        base = dict(profile_count=1, document_count=1, link_count=1, claim_count=1, signal_count=1)
        self.assertEqual(
            pilot_package_status_and_action(**base, ready_count=1, blockers=[])[0],
            "ready_for_human_review",
        )
        self.assertEqual(
            pilot_package_status_and_action(**base, ready_count=1, blockers=["OCR"])[0],
            "ready_with_document_intake_warnings",
        )
    def test_document_duplicate_diagnostics_preserve_identity_priority_deduplication_and_order(self) -> None:
        diagnostics = _build_document_duplicate_diagnostics(
            [
                {"source_document_id": "doc-title-2", "title": "Same title"},
                {"source_document_id": "doc-sha-1", "sha256": "ABC", "title": "Ignored title"},
                {"source_document_id": "doc-title-1", "title": "Same title"},
                {"source_document_id": "doc-sha-2", "sha256": "abc", "raw_file": "ignored.pdf"},
                {"source_document_id": "doc-unique", "url": "https://example.test/one"},
                {"source_document_id": "doc-empty"},
            ]
        )

        self.assertEqual(diagnostics["duplicate_document_count"], 2)
        self.assertEqual(diagnostics["estimated_unique_document_count"], 4)
        self.assertEqual(
            diagnostics["duplicate_document_groups"],
            [
                {
                    "key_kind": "sha256",
                    "key_value": "abc",
                    "document_count": 2,
                    "source_document_ids": ["doc-sha-1", "doc-sha-2"],
                    "titles": ["Ignored title"],
                    "raw_files": ["ignored.pdf"],
                    "review_status": "unreviewed",
                },
                {
                    "key_kind": "title",
                    "key_value": "same title",
                    "document_count": 2,
                    "source_document_ids": ["doc-title-2", "doc-title-1"],
                    "titles": ["Same title"],
                    "raw_files": [],
                    "review_status": "unreviewed",
                },
            ],
        )

    def test_reviewable_document_signals_preserve_order_deduplication_and_profile_filters(self) -> None:
        signals = _build_reviewable_document_signals(
            profiles=[{"profile_id": "person:one", "canonical_name": "One"}],
            links=[
                {"@id": "link-z", "profile_id": "person:one", "source_document_id": "doc-z"},
                {"@id": "link-a", "profile_id": "person:one", "source_document_id": "doc-a"},
            ],
            entities=[
                {"@id": "entity-a", "source_document_id": "doc-a", "value": "Entity A"},
                {"@id": "entity-z", "source_document_id": "doc-z", "value": "Entity Z"},
            ],
            feedback_actions=[
                {"@id": "action-a", "source_document_id": "doc-a", "value": "Action A"},
                {"@id": "action-a", "source_document_id": "doc-a", "value": "Action A"},
            ],
            skipped_claim_entities=[
                {"@id": "skip-other", "source_document_id": "doc-a", "candidate_profile_ids": ["person:other"]},
                {"@id": "skip-one", "source_document_id": "doc-a", "candidate_profile_ids": ["person:one"]},
            ],
            skipped_structured_documents=[],
        )

        self.assertEqual(len(signals), 1)
        self.assertEqual(
            [(signal["signal_type"], signal["source_item_id"]) for signal in signals[0]["signals"]],
            [
                ("candidate_document_person_link", "link-z"),
                ("candidate_document_person_link", "link-a"),
                ("research_feedback_action", "action-a"),
                ("extracted_entity", "entity-a"),
                ("skipped_claim_candidate", "skip-one"),
                ("extracted_entity", "entity-z"),
            ],
        )

    def test_render_diagnostic_blocks_from_summary_payload(self) -> None:
        markdown = render_mvp_pilot_summary_markdown(
            {
                "run_dir": "run-1",
                "review_status": "unreviewed",
                "publication_status": "not_publishable_without_human_review",
                "pilot_package_scorecard": {
                    "package_status": "blocked",
                    "ready_for_review_profile_count": 1,
                    "profile_count": 2,
                    "blocked_profile_count": 1,
                    "document_count": 3,
                    "candidate_document_person_link_count": 4,
                    "candidate_evidence_claim_count": 5,
                    "reviewable_document_signal_count": 6,
                    "minimum_review_item_count": 15,
                    "next_action": "Review package.",
                    "top_blockers": ["Missing claim review."],
                },
                "document_intake_readiness": {
                    "available": True,
                    "local_run_dir": "local-run",
                    "input_processing_plan": {
                        "asset_count": 7,
                        "action_counts": {"text_extract": 2},
                    },
                    "metadata_extraction": {"document_count": 3},
                    "text_extraction": {"extracted_count": 2, "document_count": 3},
                    "ocr_batch": {"summary": {"processed": 1, "error": 0}},
                    "image_ocr_readiness": {
                        "image_ocr_required_count": 1,
                        "blocking_image_count": 0,
                        "support_image_count": 1,
                        "unknown_image_count": 0,
                        "warnings": ["Support image only."],
                    },
                    "mvp_document_count": 3,
                    "mvp_blockers": ["Need one manual check."],
                    "next_action": "Review intake.",
                },
                "mvp_signal_diagnostics": {
                    "document_count": 3,
                    "estimated_unique_document_count": 2,
                    "duplicate_document_group_count": 1,
                    "weak_nominal_link_count": 1,
                    "candidate_document_person_link_count": 4,
                    "profiles_with_links_no_claims_count": 1,
                    "next_action": "Review signals.",
                    "claim_funnel_diagnostics": {
                        "funnel_status": "needs_review",
                        "skipped_entity_count": 2,
                        "skipped_with_candidate_profiles_count": 1,
                        "claims_with_weak_segment_id_count": 1,
                        "claims_with_chunk_id_only_count": 0,
                        "next_action": "Review funnel.",
                        "counts_by_skip_reason": {"weak_context": 2},
                    },
                    "duplicate_document_groups": [
                        {
                            "key_kind": "title",
                            "key_value": "same-title",
                            "document_count": 2,
                            "source_document_ids": ["doc-1", "doc-2"],
                        }
                    ],
                    "profiles_with_links_no_claims": [
                        {
                            "profile_id": "person:test",
                            "canonical_name": "Test Person",
                            "candidate_document_person_link_count": 4,
                            "reviewable_document_signal_count": 6,
                            "readiness_status": "needs_claims",
                        }
                    ],
                    "mvp_blockers": ["Weak signal."],
                },
            }
        )

        self.assertIn("## Scorecard pacchetto MVP", markdown)
        self.assertIn("- Stato pacchetto: `blocked`", markdown)
        self.assertIn("- Missing claim review.", markdown)
        self.assertIn("## Stato ingest documentale", markdown)
        self.assertIn("- Run locale: `local-run`", markdown)
        self.assertIn("- `text_extract`: `2`", markdown)
        self.assertIn("- Warning: Support image only.", markdown)
        self.assertIn("- Prossima azione consigliata: Review intake.", markdown)
        self.assertIn("## Diagnostica segnale MVP", markdown)
        self.assertIn("- Documenti unici stimati: `2`", markdown)
        self.assertIn("Motivi skip claim:", markdown)
        self.assertIn("- `weak_context`: `2`", markdown)
        self.assertIn("- `title` = `same-title` (2 documenti: doc-1, doc-2)", markdown)
        self.assertIn("- `person:test` - Test Person: 4 link, 6 piste, stato `needs_claims`", markdown)
        self.assertIn("- Weak signal.", markdown)


if __name__ == "__main__":
    unittest.main()
