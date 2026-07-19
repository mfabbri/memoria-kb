from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "register_t31_demo_feedback_loop.py"
SPEC = importlib.util.spec_from_file_location("register_t31_demo_feedback_loop", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class RegisterT31DemoFeedbackLoopToolTests(unittest.TestCase):
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
