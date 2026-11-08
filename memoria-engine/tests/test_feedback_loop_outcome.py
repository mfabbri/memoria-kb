from __future__ import annotations

import json
import os
import shutil
import subprocess
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
        "actions_sha256": "a" * 64,
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


def write_review_summary(
    path: Path, *, decision: str = "BUONA", status: str = "accepted", actions_sha256: str = "a" * 64
) -> None:
    payload = {
        "@type": "ResearchFeedbackActionReviewSummary",
        "actions_sha256": actions_sha256,
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
    def test_installed_launcher_records_explicit_outcome_preview(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            plan, review = tmp_dir / "plan.json", tmp_dir / "review.json"
            output = tmp_dir / "outcome.json"
            write_feedback_plan(plan)
            write_review_summary(review)
            launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
            if not launcher.is_file():
                self.skipTest("Installed memoria launcher is not available in this environment.")
            before = {path: path.read_bytes() for path in (plan, review)}
            completed = subprocess.run(
                [str(launcher), "feedback", "outcome", "--feedback-plan-json", str(plan),
                 "--review-summary-json", str(review), "--action-id", "research-feedback-action:7bdbb2060d955baa",
                 "--plan-id", "feedback-search-plan:a19b13e6e3cd8b0d", "--source-id", "storia_memoria_bo",
                 "--strategy-id", "testo-libero-nome-completo", "--outcome-status", "no_results",
                 "--query", "Andreoli Dino", "--run-id", "run:launcher-fixture",
                 "--executed-at", "2026-07-15T10:00:00+00:00", "--output-json", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["@type"], "FeedbackLoopOutcome")
            self.assertEqual(payload["research_feedback_action_id"], "research-feedback-action:7bdbb2060d955baa")
            self.assertEqual(payload["feedback_search_plan_id"], "feedback-search-plan:a19b13e6e3cd8b0d")
            self.assertEqual(payload["source_id"], "storia_memoria_bo")
            self.assertEqual(payload["run_id"], "run:launcher-fixture")
            self.assertEqual(payload["executed_at"], "2026-07-15T10:00:00+00:00")
            self.assertFalse(payload["profile_write_allowed"])
            self.assertFalse(payload["claim_promotion_allowed"])
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def build_outcome(self, root: Path, **overrides: object) -> dict:
        arguments = {
            "feedback_plan_json": root / "plan.json",
            "review_summary_json": root / "review.json",
            "action_id": "research-feedback-action:7bdbb2060d955baa",
            "outcome_status": "no_results",
            "run_id": "run:fixture",
            "executed_at": "2026-07-15T10:00:00+00:00",
            "query": "Andreoli Dino",
        }
        arguments.update(overrides)
        return build_feedback_loop_outcome(**arguments)

    def write_inputs(self, root: Path) -> dict:
        write_feedback_plan(root / "plan.json")
        write_review_summary(root / "review.json")
        return json.loads((root / "plan.json").read_text(encoding="utf-8"))

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
        self.assertEqual(payload["review_action_set_provenance"], "matched")
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

    def test_mismatched_action_set_hash_cannot_approve_outcome(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            feedback_plan_json = tmp_dir / "feedback_search_plan.json"
            review_summary_json = tmp_dir / "research_feedback_actions_review_summary.json"
            write_feedback_plan(feedback_plan_json)
            write_review_summary(review_summary_json, actions_sha256="b" * 64)

            payload = build_feedback_loop_outcome(
                feedback_plan_json=feedback_plan_json,
                review_summary_json=review_summary_json,
                action_id="research-feedback-action:7bdbb2060d955baa",
                outcome_status="no_results",
                query="Andreoli Dino",
            )

        self.assertEqual(payload["review_action_set_provenance"], "mismatch")
        self.assertFalse(payload["approved_for_demo"])
        self.assertEqual(payload["loop_status"], "pending_historian_approval")
        self.assertIn("review_action_set_hash_mismatch", payload["warnings"])

    def test_missing_action_set_hash_cannot_approve_outcome(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            feedback_plan_json = tmp_dir / "feedback_search_plan.json"
            review_summary_json = tmp_dir / "research_feedback_actions_review_summary.json"
            write_feedback_plan(feedback_plan_json)
            write_review_summary(review_summary_json, actions_sha256="")

            payload = build_feedback_loop_outcome(
                feedback_plan_json=feedback_plan_json,
                review_summary_json=review_summary_json,
                action_id="research-feedback-action:7bdbb2060d955baa",
                outcome_status="no_results",
                query="Andreoli Dino",
            )

        self.assertEqual(payload["review_action_set_provenance"], "unavailable")
        self.assertFalse(payload["approved_for_demo"])
        self.assertIn("review_action_set_hash_unavailable", payload["warnings"])

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

    def test_provenance_is_preserved_in_append_only_memory_preview(self) -> None:
        with workspace_temp_dir() as root:
            plan = self.write_inputs(root)
            attempt = plan["plans"][0]["source_plans"][0]["planned_attempts"][0]
            attempt["attempt_id"] = attempt.pop("strategy_id")
            (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            original_plan = (root / "plan.json").read_bytes()
            original_review = (root / "review.json").read_bytes()
            payload = self.build_outcome(root, outcome_status="candidate_results", result_source_document_ids=["doc:new"])
            memory = payload["search_memory_update_preview"]
            repeated = self.build_outcome(root, outcome_status="candidate_results", result_source_document_ids=["doc:new"])
            other_run = self.build_outcome(root, run_id="run:second", outcome_status="candidate_results", result_source_document_ids=["doc:new"])

            self.assertEqual(payload["loop_status"], "closed_with_auditable_outcome")
            self.assertEqual(payload["strategy_ids"], ["testo-libero-nome-completo"])
            self.assertEqual(payload["strategy_attribution_status"], "inferred_unique")
            self.assertEqual(payload["selected_source_plan"]["planned_attempts"], [attempt])
            for field in ("run_id", "source_document_id", "source_id", "strategy_ids", "planned_strategy_ids", "strategy_attribution_status", "executed_at", "query", "result_source_document_ids"):
                self.assertEqual(memory[field], payload[field])
            self.assertEqual(memory["merge_policy"], "append_execution_event_preview_only")
            self.assertFalse(memory["profile_write_allowed"])
            self.assertEqual(payload["@id"], repeated["@id"])
            self.assertNotEqual(payload["@id"], other_run["@id"])
            self.assertEqual((root / "plan.json").read_bytes(), original_plan)
            self.assertEqual((root / "review.json").read_bytes(), original_review)

    def test_missing_discordant_and_ambiguous_plan_selectors_fail_before_output(self) -> None:
        for scenario in ("missing", "discordant", "unknown", "duplicate", "divergent_ids"):
            with self.subTest(scenario=scenario), workspace_temp_dir() as root:
                plan = self.write_inputs(root)
                arguments = {}
                if scenario == "missing":
                    arguments["action_id"] = ""
                elif scenario == "discordant":
                    arguments["plan_id"] = "plan:other"
                elif scenario == "unknown":
                    arguments["action_id"] = "action:unknown"
                elif scenario == "duplicate":
                    plan["plans"].append(dict(plan["plans"][0]))
                else:
                    plan["plans"][0]["@id"] = "plan:divergent"
                (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
                output = root / "must-not-exist.json"
                with self.assertRaises(ValueError):
                    self.build_outcome(root, output_json=output, **arguments)
                self.assertFalse(output.exists())

    def test_source_must_be_unambiguously_planned(self) -> None:
        for scenario in ("unknown", "skipped", "multiple"):
            with self.subTest(scenario=scenario), workspace_temp_dir() as root:
                plan = self.write_inputs(root)
                arguments = {}
                if scenario == "unknown":
                    arguments["source_id"] = "source:not-planned"
                elif scenario == "skipped":
                    plan["plans"][0]["source_plans"][0]["status"] = "skipped"
                else:
                    second = dict(plan["plans"][0]["source_plans"][0])
                    second["source_id"] = "source:second"
                    plan["plans"][0]["source_plans"].append(second)
                (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "planned source"):
                    self.build_outcome(root, **arguments)

    def test_multiple_executed_strategies_require_explicit_attribution(self) -> None:
        with workspace_temp_dir() as root:
            plan = self.write_inputs(root)
            source = plan["plans"][0]["source_plans"][0]
            source["planned_attempts"].append({"attempt_id": "nome-cognome", "query_fields": {"nom": "Dino", "cog": "Andreoli"}})
            (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            ambiguous = self.build_outcome(root)
            explicit = self.build_outcome(root, strategy_ids=["testo-libero-nome-completo", "nome-cognome"])
            self.assertEqual(ambiguous["loop_status"], "missing_strategy_attribution")
            self.assertEqual(ambiguous["strategy_ids"], [])
            self.assertEqual(ambiguous["strategy_attribution_status"], "ambiguous")
            self.assertEqual(ambiguous["planned_strategy_ids"], ["nome-cognome", "testo-libero-nome-completo"])
            self.assertEqual(explicit["loop_status"], "closed_with_auditable_outcome")
            self.assertEqual(explicit["strategy_ids"], ["nome-cognome", "testo-libero-nome-completo"])
            self.assertEqual(explicit["strategy_attribution_status"], "explicit")
            self.assertEqual(explicit["search_memory_update_preview"]["strategy_ids"], explicit["strategy_ids"])
            with self.assertRaisesRegex(ValueError, "selected strategy"):
                self.build_outcome(root, strategy_ids=["strategy:not-planned"])

    def test_missing_run_and_strategy_cannot_close_auditable_loop(self) -> None:
        with workspace_temp_dir() as root:
            plan = self.write_inputs(root)
            self.assertEqual(self.build_outcome(root, run_id=" ")["loop_status"], "missing_run_id")
            plan["plans"][0]["source_plans"][0]["planned_attempts"] = []
            (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            payload = self.build_outcome(root)
            self.assertEqual(payload["loop_status"], "missing_strategy_attribution")
            self.assertEqual(payload["strategy_attribution_status"], "unavailable")

    def test_no_results_rejects_document_ids_and_invalid_timestamps(self) -> None:
        with workspace_temp_dir() as root:
            self.write_inputs(root)
            with self.assertRaisesRegex(ValueError, "no_results"):
                self.build_outcome(root, result_source_document_ids=["doc:new"])
            for timestamp in ("not-a-timestamp", "2026-07-15T10:00:00"):
                with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                    self.build_outcome(root, executed_at=timestamp)
            payload = self.build_outcome(root, outcome_status="candidate_results", result_source_document_ids=[None, 42, " "])
            self.assertEqual(payload["loop_status"], "missing_candidate_result_document")

    def test_review_identity_mismatch_or_duplicate_approval_cannot_close_loop(self) -> None:
        for scenario in ("other_profile", "other_document", "duplicate"):
            with self.subTest(scenario=scenario), workspace_temp_dir() as root:
                self.write_inputs(root)
                review = json.loads((root / "review.json").read_text(encoding="utf-8"))
                if scenario == "other_profile":
                    review["decisions"][0]["person_id"] = "person:other"
                elif scenario == "other_document":
                    review["decisions"][0]["source_document_id"] = "doc:other"
                else:
                    review["decisions"].append(dict(review["decisions"][0]))
                (root / "review.json").write_text(json.dumps(review), encoding="utf-8")
                payload = self.build_outcome(root)
                self.assertEqual(payload["loop_status"], "pending_historian_approval")
                self.assertFalse(payload["approved_for_demo"])


if __name__ == "__main__":
    unittest.main()
