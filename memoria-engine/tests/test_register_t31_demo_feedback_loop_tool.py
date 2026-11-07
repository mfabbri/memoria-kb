from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "register_t31_demo_feedback_loop.py"
SPEC = importlib.util.spec_from_file_location("register_t31_demo_feedback_loop", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class RegisterT31DemoFeedbackLoopToolTests(unittest.TestCase):
    def test_main_records_both_executed_strategies_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            database_dir = data_root / "database"
            run_dir = data_root / "risultati" / "runs" / "candidate-pipeline"
            document_dir = run_dir / "document_analysis"
            historian_dir = run_dir / "historian_review"
            for directory in (database_dir, document_dir, historian_dir):
                directory.mkdir(parents=True, exist_ok=True)
            plan = {
                "@type": "FeedbackSearchPlan", "@id": TOOL.PLAN_ID,
                "feedback_search_plan_id": TOOL.PLAN_ID, "action_id": TOOL.ACTION_ID,
                "profile_id": TOOL.PROFILE_ID, "source_document_id": TOOL.SOURCE_DOCUMENT_ID,
                "source_plans": [{
                    "source_id": TOOL.SOURCE_ID, "status": "planned",
                    "planned_attempts": [{"attempt_id": "nome-cognome"}, {"attempt_id": "testo-libero-nome-completo"}],
                }],
            }
            (document_dir / "mvp_pilot_summary.json").write_text(json.dumps({
                "research_feedback_actions": [{"action_id": TOOL.ACTION_ID}],
                "feedback_search_plans": [plan],
            }), encoding="utf-8")
            descriptor = run_dir / "candidate.json"
            descriptor.write_text(json.dumps({"run_id": "candidate-pipeline", "artifacts": {}, "notes": []}), encoding="utf-8")
            arguments = ["register_t31_demo_feedback_loop.py", "--data-root", str(data_root), "--run-id", "candidate-pipeline", "--descriptor-path", str(descriptor), "--backup-path", str(run_dir / "before.json")]
            with patch("sys.argv", arguments), patch("builtins.print"):
                self.assertEqual(TOOL.main(), 0)
            outcome = json.loads((historian_dir / "feedback_loop_outcome.t31-demo.json").read_text(encoding="utf-8"))
            self.assertEqual(outcome["loop_status"], "closed_with_auditable_outcome")
            self.assertEqual(outcome["strategy_ids"], ["nome-cognome", "testo-libero-nome-completo"])
            self.assertEqual(outcome["strategy_attribution_status"], "explicit")
            self.assertEqual(outcome["search_memory_update_preview"]["strategy_ids"], outcome["strategy_ids"])

    def test_explicit_candidate_descriptor_does_not_modify_active_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            database_dir = data_root / "database"
            run_dir = data_root / "risultati" / "runs" / "candidate-pipeline"
            database_dir.mkdir(parents=True)
            run_dir.mkdir(parents=True)

            active_descriptor = database_dir / "memoria_mvp_demo.active.json"
            candidate_descriptor = run_dir / "memoria_mvp_demo.candidate.json"
            candidate_backup = run_dir / "memoria_mvp_demo.candidate.before-feedback.json"
            active_descriptor.write_text(json.dumps({"run_id": "active-pipeline"}), encoding="utf-8")
            candidate_descriptor.write_text(
                json.dumps({"run_id": "candidate-pipeline", "artifacts": {}, "notes": []}),
                encoding="utf-8",
            )

            TOOL._update_descriptor(
                data_root=data_root,
                run_id="candidate-pipeline",
                descriptor_path=candidate_descriptor,
                backup_path=candidate_backup,
                generated_at="2026-07-18T10:00:00+00:00",
                query="query",
                outcome={
                    "loop_status": "closed_with_auditable_outcome",
                    "outcome_status": "needs_manual_review",
                    "feedback_loop_outcome_id": "feedback-loop:test",
                    "execution_mode": "manual_review_session",
                },
                review_table_md=run_dir / "review.md",
                review_summary_json=run_dir / "review.json",
                plan_json=run_dir / "plan.json",
                outcome_json=run_dir / "outcome.json",
                outcome_md=run_dir / "outcome.md",
            )

            active = json.loads(active_descriptor.read_text(encoding="utf-8"))
            candidate = json.loads(candidate_descriptor.read_text(encoding="utf-8"))
            backup = json.loads(candidate_backup.read_text(encoding="utf-8"))

            self.assertEqual(active, {"run_id": "active-pipeline"})
            self.assertEqual(backup["run_id"], "candidate-pipeline")
            self.assertEqual(candidate["t31_feedback_loop"]["status"], "closed_with_auditable_outcome")
            self.assertEqual(candidate["artifacts"]["feedback_outcome"], str(run_dir / "outcome.json"))

    def test_rejects_descriptor_for_a_different_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            run_dir = data_root / "risultati" / "runs" / "candidate-pipeline"
            run_dir.mkdir(parents=True)
            candidate_descriptor = run_dir / "memoria_mvp_demo.candidate.json"
            candidate_descriptor.write_text(json.dumps({"run_id": "other-pipeline"}), encoding="utf-8")

            with self.assertRaisesRegex(SystemExit, "Descriptor run mismatch"):
                TOOL._update_descriptor(
                    data_root=data_root,
                    run_id="candidate-pipeline",
                    descriptor_path=candidate_descriptor,
                    backup_path=run_dir / "backup.json",
                    generated_at="2026-07-18T10:00:00+00:00",
                    query="query",
                    outcome={},
                    review_table_md=run_dir / "review.md",
                    review_summary_json=run_dir / "review.json",
                    plan_json=run_dir / "plan.json",
                    outcome_json=run_dir / "outcome.json",
                    outcome_md=run_dir / "outcome.md",
                )


if __name__ == "__main__":
    unittest.main()
