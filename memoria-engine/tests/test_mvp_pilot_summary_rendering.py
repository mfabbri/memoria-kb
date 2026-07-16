from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_pilot_summary import (  # noqa: E402
    render_mvp_pilot_summary_markdown,
)


class MvpPilotSummaryRenderingTests(unittest.TestCase):
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
