from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.feedback_loop_outcome import (  # noqa: E402
    build_feedback_loop_outcome,
    render_feedback_loop_outcome_markdown,
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


def write_feedback_plan(path: Path) -> None:
    payload = {
        "@type": "FeedbackSearchPlanSet",
        "review_status": "unreviewed",
        "execution_allowed": False,
        "online_search_started": False,
        "profile_write_allowed": False,
        "plans": [
            {
                "@type": "FeedbackSearchPlan",
                "@id": "feedback-search-plan:a19b13e6e3cd8b0d",
                "feedback_search_plan_id": "feedback-search-plan:a19b13e6e3cd8b0d",
                "action_id": "research-feedback-action:7bdbb2060d955baa",
                "source_document_id": "legacy_csv:a4ac96061a2381b5",
                "profile_id": "person:purocielo:andreoli-dino",
                "status": "ready_for_review",
                "manual_review_required": True,
                "source_plans": [
                    {
                        "@type": "FeedbackSearchSourcePlan",
                        "source_id": "storia_memoria_bo",
                        "status": "planned",
                        "planned_attempt_count": 2,
                        "planned_attempts": [
                            {
                                "query": "Andreoli Dino",
                                "strategy_id": "testo-libero-nome-completo",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_review_summary(path: Path, *, decision: str = "BUONA", status: str = "accepted") -> None:
    payload = {
        "@type": "ResearchFeedbackActionReviewSummary",
        "review_status": "reviewed",
        "accepted_count": 1 if status == "accepted" else 0,
        "decisions": [
            {
                "@type": "ResearchFeedbackActionTriageDecision",
                "decision_status": status,
                "decision": decision,
                "action_id": "research-feedback-action:7bdbb2060d955baa",
                "person_id": "person:purocielo:andreoli-dino",
                "source_document_id": "legacy_csv:a4ac96061a2381b5",
                "notes": "Richiede controllo mirato per la demo.",
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class FeedbackLoopOutcomeTests(unittest.TestCase):
    def test_builds_closed_no_results_outcome_without_promoting_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            feedback_plan_json = tmp_dir / "feedback_search_plan.json"
            review_summary_json = tmp_dir / "research_feedback_actions_review_summary.json"
            output_json = tmp_dir / "feedback_loop_outcome.json"
            output_md = tmp_dir / "feedback_loop_outcome.md"
            write_feedback_plan(feedback_plan_json)
            write_review_summary(review_summary_json)

            payload = build_feedback_loop_outcome(
                feedback_plan_json=feedback_plan_json,
                review_summary_json=review_summary_json,
                action_id="research-feedback-action:7bdbb2060d955baa",
                outcome_status="no_results",
                execution_mode="manual_review_session",
                query="Andreoli Dino site:storiaememoriadibologna.it",
                notes="Sessione manuale tracciata: nessun risultato utile.",
                run_id="prova-preview-profili-5-reviewed-01-pipeline",
                executed_at="2026-07-15T10:00:00+00:00",
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False)
            output_json_exists = output_json.exists()

        self.assertEqual(payload["@type"], "FeedbackLoopOutcome")
        self.assertEqual(payload["loop_status"], "closed_with_auditable_outcome")
        self.assertEqual(payload["outcome_status"], "no_results")
        self.assertTrue(payload["approved_for_demo"])
        self.assertEqual(payload["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(payload["source_id"], "storia_memoria_bo")
        self.assertFalse(payload["profile_write_allowed"])
        self.assertFalse(payload["claim_promotion_allowed"])
        self.assertFalse(payload["creates_verified_facts"])
        self.assertFalse(payload["applies_profile_patch"])
        self.assertEqual(persisted["search_memory_update_preview"]["outcome_status"], "no_results")
        self.assertTrue(output_json_exists)
        self.assertIn("Feedback loop outcome preview", markdown)
        self.assertIn("no_results_is_search_memory_not_historical_absence_proof", serialized)
        self.assertNotIn("VerifiedFact", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_without_historian_approval_loop_stays_pending(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            feedback_plan_json = tmp_dir / "feedback_search_plan.json"
            review_summary_json = tmp_dir / "research_feedback_actions_review_summary.json"
            write_feedback_plan(feedback_plan_json)
            write_review_summary(review_summary_json, decision="INUTILE")

            payload = build_feedback_loop_outcome(
                feedback_plan_json=feedback_plan_json,
                review_summary_json=review_summary_json,
                action_id="research-feedback-action:7bdbb2060d955baa",
                outcome_status="no_results",
                query="Andreoli Dino",
            )

        self.assertEqual(payload["loop_status"], "pending_historian_approval")
        self.assertFalse(payload["approved_for_demo"])
        self.assertIn("historian_feedback_action_approval_missing", payload["warnings"])
        self.assertFalse(payload["creates_verified_facts"])

    def test_candidate_results_require_document_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            feedback_plan_json = tmp_dir / "feedback_search_plan.json"
            review_summary_json = tmp_dir / "research_feedback_actions_review_summary.json"
            write_feedback_plan(feedback_plan_json)
            write_review_summary(review_summary_json)

            payload = build_feedback_loop_outcome(
                feedback_plan_json=feedback_plan_json,
                review_summary_json=review_summary_json,
                action_id="research-feedback-action:7bdbb2060d955baa",
                outcome_status="candidate_results",
                query="Andreoli Dino",
            )

        self.assertEqual(payload["loop_status"], "missing_candidate_result_document")
        self.assertIn("candidate_results_requires_source_document_id", payload["warnings"])

    def test_markdown_renderer_lists_result_documents(self) -> None:
        markdown = render_feedback_loop_outcome_markdown(
            {
                "loop_status": "closed_with_auditable_outcome",
                "outcome_status": "candidate_results",
                "research_feedback_action_id": "research-feedback-action:abc",
                "feedback_search_plan_id": "feedback-search-plan:def",
                "profile_id": "person:test",
                "source_id": "source:test",
                "query": "Nome Cognome",
                "approved_for_demo": True,
                "result_source_document_ids": ["source:test-doc"],
                "search_memory_update_preview": {
                    "profile_id": "person:test",
                    "outcome_status": "candidate_results",
                    "summary": "Documento candidato da rivedere.",
                },
            }
        )

        self.assertIn("source:test-doc", markdown)
        self.assertIn("Documento candidato da rivedere.", markdown)


if __name__ == "__main__":
    unittest.main()
