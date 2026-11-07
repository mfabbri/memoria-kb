from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.feedback_loop_evaluation import build_feedback_loop_evaluation  # noqa: E402
from caduti_fonti_report.document_analysis.feedback_loop_outcome import build_feedback_loop_outcome  # noqa: E402


class FeedbackLoopEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        base = Path(__file__).resolve().parents[1] / ".tmp-tests"
        base.mkdir(exist_ok=True)
        self.root = base / f"test-{uuid.uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.plan = self.write("plan.json", {
            "@type": "FeedbackSearchPlanSet", "plans": [{
                "@type": "FeedbackSearchPlan", "@id": "plan:one", "feedback_search_plan_id": "plan:one",
                "action_id": "action:one", "profile_id": "person:test", "source_document_id": "doc:seed",
                "source_plans": [{"source_id": source, "status": "planned", "planned_attempts": [{"attempt_id": "strategy:one"}]}
                                 for source in ("source:a", "source:b")],
            }],
        })
        self.review = self.write("review.json", {"@type": "ResearchFeedbackActionReviewSummary", "decisions": [{
            "action_id": "action:one", "decision_status": "accepted", "decision": "BUONA",
            "person_id": "person:test", "source_document_id": "doc:seed",
        }]})

    def write(self, filename: str, payload: dict) -> Path:
        path = self.root / filename
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def outcome(self, filename: str = "outcome.json", *, source: str = "source:a", status: str = "no_results", run_id: str = "run:one") -> Path:
        output = self.root / filename
        build_feedback_loop_outcome(feedback_plan_json=self.plan, review_summary_json=self.review,
            plan_id="plan:one", source_id=source, outcome_status=status, run_id=run_id,
            executed_at="2026-11-07T10:00:00+00:00", query="Test query",
            result_source_document_ids=["doc:result"] if status == "candidate_results" else [], output_json=output)
        return output

    def test_composes_real_outcome_builder_and_measures_partial_source_coverage(self) -> None:
        outcome = self.outcome()
        before = {path: path.read_bytes() for path in (self.plan, self.review, outcome)}
        output_json, output_md = self.root / "evaluation.json", self.root / "evaluation.md"
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], output_json=output_json, output_md=output_md)
        repeated = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome])

        self.assertEqual(payload, repeated)
        self.assertEqual(json.loads(output_json.read_text(encoding="utf-8")), payload)
        coverage = payload["metrics"]["source_coverage"]
        self.assertEqual((coverage["status"], coverage["numerator"], coverage["denominator"], coverage["value"]), ("measured", 1, 2, 0.5))
        self.assertEqual(payload["metrics"]["retrieval_outcomes"]["value"]["no_results"], 1)
        self.assertEqual(len(coverage["provenance"]), 2)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in payload["input_artifacts"]))
        self.assertTrue(payload["audit_only"])
        self.assertFalse(payload["profile_write_allowed"])
        self.assertFalse(payload["claim_promotion_allowed"])
        self.assertFalse(payload["creates_verified_facts"])
        self.assertIn("no_results_is_not_historical_absence", payload["warnings"])
        self.assertIn("source_coverage", output_md.read_text(encoding="utf-8"))
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_missing_optional_measurements_are_unavailable(self) -> None:
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[self.outcome()])
        for name in ("claim_document_attribution", "conflict_preservation", "review_latency_seconds", "session_tokens", "session_cost_usd"):
            self.assertEqual(payload["metrics"][name]["status"], "unavailable", name)
            self.assertIsNone(payload["metrics"][name]["value"], name)
        self.assertEqual(payload["issues"], [])

    def test_measures_explicit_claim_conflict_review_and_usage_inputs(self) -> None:
        first = self.outcome(status="candidate_results")
        second = self.outcome("second.json", source="source:b", status="blocked_or_dynamic", run_id="run:two")
        first_id = json.loads(first.read_text(encoding="utf-8"))["@id"]
        second_id = json.loads(second.read_text(encoding="utf-8"))["@id"]
        claims = self.write("claims.json", {"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": [
            {"@type": "CandidateEvidenceClaim", "@id": "claim:one", "source_document_id": "doc:result", "source_id": "source:a"},
            {"@type": "CandidateEvidenceClaim", "@id": "claim:two", "source_id": "source:a"},
        ]})
        measurements = self.write("measurements.json", {"@type": "FeedbackLoopEvaluationMeasurements",
            "conflicts": [
                {"conflict_id": "conflict:one", "outcome_id": first_id, "before_claim_ids": ["claim:one", "claim:two"], "after_claim_ids": ["claim:two", "claim:one"]},
                {"conflict_id": "conflict:two", "outcome_id": second_id, "before_claim_ids": ["claim:one", "claim:two"], "after_claim_ids": ["claim:one"]},
            ],
            "reviews": [
                {"review_id": "review:one", "outcome_id": first_id, "started_at": "2026-11-07T10:00:00Z", "completed_at": "2026-11-07T10:00:10Z"},
                {"review_id": "review:two", "outcome_id": second_id, "started_at": "2026-11-07T10:00:00Z", "completed_at": "2026-11-07T10:00:20Z"},
            ],
            "sessions": [
                {"session_id": "session:one", "run_id": "run:one", "input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 5, "cost_usd": 1.0},
                {"session_id": "session:two", "run_id": "run:two", "input_tokens": 20, "cached_input_tokens": 0, "output_tokens": 2, "cost_usd": 2.0},
            ]})
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[second, first], candidate_claims_json=claims, measurements_json=measurements)
        reverse = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[first, second], candidate_claims_json=claims, measurements_json=measurements)
        metrics = payload["metrics"]
        self.assertEqual(payload, reverse)
        self.assertEqual(metrics["source_coverage"]["value"], 1.0)
        self.assertEqual(metrics["claim_document_attribution"]["value"], 0.5)
        self.assertEqual(metrics["conflict_preservation"]["value"], 0.5)
        self.assertEqual(metrics["review_latency_seconds"]["value"], 15.0)
        self.assertEqual(metrics["session_tokens"]["value"], {"input_tokens": 30, "cached_input_tokens": 3, "output_tokens": 7})
        self.assertEqual(metrics["session_cost_usd"]["value"], 3.0)
        self.assertEqual(metrics["retrieval_outcomes"]["value"], {"blocked_or_dynamic": 1, "candidate_results": 1, "needs_manual_review": 0, "no_results": 0})
        self.assertEqual(payload["issues"], [])

    def test_duplicate_outcomes_are_all_excluded(self) -> None:
        first = self.outcome()
        duplicate = self.root / "duplicate.json"
        duplicate.write_bytes(first.read_bytes())
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[first, duplicate])
        self.assertEqual(payload["accepted_outcome_ids"], [])
        self.assertEqual(payload["excluded_outcome_count"], 2)
        self.assertEqual([issue["reason"] for issue in payload["issues"]], ["duplicate_outcome_id", "duplicate_outcome_id"])
        self.assertEqual(payload["metrics"]["source_coverage"]["status"], "partial")
        self.assertEqual(payload["metrics"]["source_coverage"]["numerator"], 0)

    def test_mismatched_or_pending_events_do_not_count_as_auditable_coverage(self) -> None:
        original = json.loads(self.outcome().read_text(encoding="utf-8"))
        scenarios = [
            ("source_id", "source:unknown", "source_not_planned"),
            ("profile_id", "person:other", "mismatched_profile_id"),
            ("research_feedback_action_id", "action:other", "mismatched_research_feedback_action_id"),
            ("strategy_ids", ["strategy:unknown"], "strategy_not_attributed_to_planned_source"),
            ("run_id", "", "missing_run_or_execution_timestamp"),
            ("approved_for_demo", False, "missing_or_mismatched_human_approval"),
            ("approved_decision", {"action_id": "action:other", "decision_status": "accepted", "decision": "BUONA"}, "missing_or_mismatched_human_approval"),
            ("loop_status", "pending_historian_approval", "loop_not_closed"),
        ]
        for index, (field, value, reason) in enumerate(scenarios):
            with self.subTest(field=field):
                path = self.write(f"bad-{index}.json", {**original, field: value})
                payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[path])
                self.assertEqual(payload["accepted_outcome_ids"], [])
                self.assertEqual(payload["issues"][0]["reason"], reason)

    def test_incomplete_measurements_remain_partial_and_unbound_records_are_flagged(self) -> None:
        outcome = self.outcome()
        outcome_id = json.loads(outcome.read_text(encoding="utf-8"))["@id"]
        measurements = self.write("measurements.json", {"@type": "FeedbackLoopEvaluationMeasurements",
            "reviews": [
                {"review_id": "review:valid", "outcome_id": outcome_id, "started_at": "2026-11-07T10:00:00Z", "completed_at": "2026-11-07T10:00:10Z"},
                {"review_id": "review:invalid", "outcome_id": outcome_id, "started_at": "2026-11-07T10:00:00", "completed_at": "2026-11-07T10:00:10"},
            ],
            "sessions": [
                {"session_id": "session:valid", "run_id": "run:one", "input_tokens": 10, "cached_input_tokens": 2, "output_tokens": 3},
                {"session_id": "session:invalid", "run_id": "run:one", "input_tokens": 1, "cached_input_tokens": 2, "output_tokens": 3, "cost_usd": -1},
                {"session_id": "session:unbound", "run_id": "run:unknown", "cost_usd": 50},
            ]})
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], measurements_json=measurements)
        self.assertEqual(payload["metrics"]["review_latency_seconds"]["status"], "partial")
        self.assertEqual(payload["metrics"]["review_latency_seconds"]["value"], 10)
        self.assertEqual(payload["metrics"]["session_tokens"]["status"], "partial")
        self.assertEqual(payload["metrics"]["session_cost_usd"]["status"], "unavailable")
        self.assertIn("invalid_or_unbound_sessions_record", {item["reason"] for item in payload["issues"]})

    def test_rejects_wrong_schema_duplicate_plans_and_output_overwriting_inputs(self) -> None:
        outcome = self.outcome()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], output_json=self.plan)
        measurements = self.write("wrong.json", {"@type": "Unknown"})
        with self.assertRaisesRegex(ValueError, "FeedbackLoopEvaluationMeasurements"):
            build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], measurements_json=measurements)
        plan_payload = json.loads(self.plan.read_text(encoding="utf-8"))
        plan_payload["plans"].append(dict(plan_payload["plans"][0]))
        self.plan.write_text(json.dumps(plan_payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unique IDs"):
            build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome])

    def test_duplicate_claims_do_not_inflate_attribution_and_empty_outcomes_have_no_distribution(self) -> None:
        claims = self.write("claims.json", {"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": [
            {"@type": "CandidateEvidenceClaim", "@id": "claim:duplicate", "source_document_id": "doc:one", "source_id": "source:a"},
            {"@type": "CandidateEvidenceClaim", "@id": "claim:duplicate", "source_document_id": "doc:two", "source_id": "source:b"},
        ]})
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[], candidate_claims_json=claims)
        metric = payload["metrics"]["claim_document_attribution"]
        self.assertEqual((metric["status"], metric["numerator"], metric["denominator"]), ("partial", 0, 2))
        self.assertEqual(payload["metrics"]["source_coverage"]["value"], 0)
        self.assertEqual(payload["metrics"]["retrieval_outcomes"]["status"], "unavailable")
        self.assertEqual(len(payload["issues"]), 2)

    def test_session_comparison_metadata_is_explicit_and_legacy_totals_remain_measurable(self) -> None:
        outcome = self.outcome()
        metadata = {"comparison_group_id": "task:fixture", "task_contract_sha256": "A" * 64,
                    "quality_gate_status": "passed", "model_id": "fixture-model", "comparison_role": "baseline"}
        measurements = self.write("sessions.json", {"@type": "FeedbackLoopEvaluationMeasurements", "sessions": [
            {"session_id": "session:ready", "run_id": "run:one", "input_tokens": 10, "cached_input_tokens": 2,
             "output_tokens": 3, "cost_usd": 0.5, **metadata},
            {"session_id": "session:cost-only", "run_id": "run:one", "cost_usd": 0.2,
             **{**metadata, "comparison_role": "candidate"}},
            {"session_id": "session:legacy", "run_id": "run:one", "input_tokens": 5, "cached_input_tokens": 0, "output_tokens": 1},
        ]})
        before = measurements.read_bytes()
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], measurements_json=measurements)
        readiness = payload["metrics"]["session_comparison_readiness"]
        by_id = {row["session_id"]: row for row in readiness["by_session"]}
        self.assertEqual(readiness["value"], {"ready": 2, "not_comparable": 1})
        self.assertEqual(by_id["session:ready"]["task_contract_sha256"], "a" * 64)
        self.assertEqual(by_id["session:ready"]["comparison_role"], "baseline")
        self.assertEqual(by_id["session:ready"]["available_measures"], ["tokens", "cost_usd"])
        self.assertEqual(by_id["session:cost-only"]["available_measures"], ["cost_usd"])
        self.assertIn("missing_task_contract_sha256", by_id["session:legacy"]["reasons"])
        self.assertEqual(payload["metrics"]["session_tokens"]["value"]["input_tokens"], 15)
        self.assertEqual(payload["metrics"]["session_cost_usd"]["value"], 0.7)
        self.assertEqual({item["reason"] for item in payload["issues"]}, {"unmeasurable_sessions_tokens", "unmeasurable_sessions_cost"})
        self.assertEqual(measurements.read_bytes(), before)

    def test_invalid_session_metadata_and_usage_never_become_comparison_ready(self) -> None:
        outcome = self.outcome()
        valid = {"session_id": "session:test", "run_id": "run:one", "input_tokens": 10,
                 "cached_input_tokens": 0, "output_tokens": 1, "comparison_group_id": "task:fixture",
                 "task_contract_sha256": "a" * 64, "quality_gate_status": "passed",
                 "model_id": "fixture-model", "comparison_role": "candidate"}
        scenarios = [
            ("task_contract_sha256", "not-a-digest", "invalid_task_contract_sha256"),
            ("quality_gate_status", "unknown", "invalid_quality_gate_status"),
            ("quality_gate_status", "failed", "quality_gate_not_passed"),
            ("model_id", " ", "invalid_model_id"),
            ("comparison_group_id", 42, "invalid_comparison_group_id"),
            ("comparison_role", "observer", "invalid_comparison_role"),
            ("cached_input_tokens", 11, "invalid_session_tokens"),
            ("cost_usd", -1, "invalid_session_cost"),
            ("run_id", "run:unknown", "invalid_or_unbound_sessions_record"),
        ]
        for field, value, reason in scenarios:
            with self.subTest(field=field, value=value):
                measurements = self.write("bad-sessions.json", {"@type": "FeedbackLoopEvaluationMeasurements", "sessions": [{**valid, field: value}]})
                payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], measurements_json=measurements)
                record = payload["metrics"]["session_comparison_readiness"]["by_session"][0]
                self.assertEqual(record["status"], "not_comparable")
                self.assertIn(reason, record["reasons"])
                self.assertNotIn("delta", payload["metrics"]["session_comparison_readiness"])

    def test_triage_summary_timing_binds_to_one_auditable_outcome_and_preserves_provenance(self) -> None:
        outcome = self.outcome()
        summary = self.write("timed-review.json", {"@type": "ResearchFeedbackActionReviewSummary", "decisions": [{
            "action_id": "action:one", "decision_status": "accepted", "reviewer": "fixture-reviewer",
            "review_started_at": "2026-11-07T10:00:00+01:00", "reviewed_at": "2026-11-07T09:01:30Z",
            "review_timing_status": "measured", "review_duration_seconds": 90.0,
        }]})
        before = summary.read_bytes()
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], review_summary_json=summary)
        metric = payload["metrics"]["review_latency_seconds"]
        self.assertEqual((metric["status"], metric["value"], metric["denominator"]), ("measured", 90.0, 1))
        record = metric["by_review"][0]
        self.assertEqual(record["reviewer"], "fixture-reviewer")
        self.assertEqual(record["input_artifact"], str(summary))
        self.assertEqual(record["outcome_id"], json.loads(outcome.read_text(encoding="utf-8"))["@id"])
        self.assertEqual(metric["provenance"][0]["sha256"], next(item["sha256"] for item in payload["input_artifacts"] if item["path"] == str(summary)))
        self.assertEqual(payload["issues"], [])
        self.assertEqual(summary.read_bytes(), before)

    def test_triage_summary_ambiguous_missing_or_invalid_timing_is_excluded(self) -> None:
        first = self.outcome()
        valid = {"action_id": "action:one", "decision_status": "accepted", "review_started_at": "2026-11-07T10:00:00Z",
                 "reviewed_at": "2026-11-07T10:01:00Z", "review_timing_status": "measured", "review_duration_seconds": 60}
        scenarios = [
            ({**valid, "action_id": "action:missing"}, "review_summary_outcome_binding_not_unique"),
            ({**valid, "review_started_at": "2026-11-07T10:00:00"}, "invalid_review_summary_timing"),
            ({**valid, "review_duration_seconds": 5}, "inconsistent_review_summary_duration"),
        ]
        for decision, reason in scenarios:
            with self.subTest(reason=reason):
                summary = self.write("bad-review.json", {"@type": "ResearchFeedbackActionReviewSummary", "decisions": [decision]})
                payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[first], review_summary_json=summary)
                self.assertEqual(payload["metrics"]["review_latency_seconds"]["status"], "unavailable")
                self.assertEqual(payload["metrics"]["review_latency_seconds"]["denominator"], 1)
                self.assertEqual(payload["issues"][0]["reason"], reason)
        second = self.outcome("second-action-outcome.json", source="source:b", run_id="run:two")
        summary = self.write("ambiguous-review.json", {"@type": "ResearchFeedbackActionReviewSummary", "decisions": [valid]})
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[first, second], review_summary_json=summary)
        self.assertEqual(payload["metrics"]["review_latency_seconds"]["by_review"], [])
        self.assertEqual(payload["issues"][0]["reason"], "review_summary_outcome_binding_not_unique")

    def test_accepted_review_without_timestamps_counts_as_unavailable(self) -> None:
        outcome = self.outcome()
        summary = self.write("untimed-review.json", {"@type": "ResearchFeedbackActionReviewSummary", "decisions": [{
            "action_id": "action:one", "decision_status": "accepted", "review_timing_status": "unavailable",
        }]})
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], review_summary_json=summary)
        metric = payload["metrics"]["review_latency_seconds"]
        self.assertEqual((metric["status"], metric["value"], metric["numerator"], metric["denominator"]), ("unavailable", None, 0, 1))
        self.assertEqual(payload["issues"][0]["reason"], "review_summary_timing_unavailable")

    def comparison_session(self, session_id: str, role: str, **values: object) -> dict:
        return {"session_id": session_id, "run_id": "run:one", "comparison_group_id": "comparison:one",
                "task_contract_sha256": "a" * 64, "quality_gate_status": "passed", "model_id": "fixture-model",
                "comparison_role": role, "input_tokens": 100, "cached_input_tokens": 20,
                "output_tokens": 10, "cost_usd": 1.0, **values}

    def test_observed_deltas_use_one_baseline_and_multiple_sorted_candidates(self) -> None:
        outcome = self.outcome()
        measurements = self.write("paired.json", {"@type": "FeedbackLoopEvaluationMeasurements", "sessions": [
            self.comparison_session("session:z", "candidate", input_tokens=80, cached_input_tokens=30, output_tokens=12, cost_usd=0.7),
            self.comparison_session("session:base", "baseline"),
            self.comparison_session("session:a", "candidate", input_tokens=120, cached_input_tokens=0, output_tokens=8, cost_usd=1.5),
        ]})
        original = measurements.read_bytes()
        markdown = self.root / "paired.md"
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], measurements_json=measurements, output_md=markdown)
        self.assertEqual(payload, build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], measurements_json=measurements))
        self.assertIn("Observed candidate-minus-baseline deltas", markdown.read_text(encoding="utf-8"))
        metric = payload["metrics"]["session_usage_deltas"]
        self.assertEqual((metric["status"], metric["numerator"], metric["denominator"]), ("measured", 2, 2))
        pairs = metric["by_comparison"]
        self.assertEqual([row["candidate_session_id"] for row in pairs], ["session:a", "session:z"])
        self.assertEqual(pairs[0]["baseline_session_id"], "session:base")
        self.assertEqual(pairs[0]["measures"]["input_tokens"], {"status": "measured", "baseline": 100, "candidate": 120, "candidate_minus_baseline": 20})
        self.assertEqual(pairs[1]["measures"]["input_tokens"]["candidate_minus_baseline"], -20)
        self.assertEqual(pairs[1]["measures"]["cached_input_tokens"]["candidate_minus_baseline"], 10)
        self.assertAlmostEqual(pairs[1]["measures"]["cost_usd"]["candidate_minus_baseline"], -0.3)
        self.assertEqual(pairs[0]["provenance"][0]["sha256"], next(row["sha256"] for row in payload["input_artifacts"] if row["path"] == str(measurements)))
        self.assertEqual(measurements.read_bytes(), original)

    def test_invalid_comparison_groups_emit_issues_and_no_deltas(self) -> None:
        outcome = self.outcome()
        baseline = self.comparison_session("session:base", "baseline")
        candidate = self.comparison_session("session:candidate", "candidate")
        scenarios = [
            ([candidate], "comparison_baseline_not_unique"),
            ([baseline], "comparison_candidate_missing"),
            ([baseline, {**baseline, "session_id": "session:second-base"}, candidate], "comparison_baseline_not_unique"),
            ([baseline, {**candidate, "task_contract_sha256": "b" * 64}], "comparison_task_contract_mismatch"),
            ([baseline, {**candidate, "quality_gate_status": "failed"}], "comparison_quality_gate_not_passed"),
            ([baseline, {**candidate, "run_id": "run:unknown"}], "comparison_group_contains_not_comparable_session"),
        ]
        for rows, reason in scenarios:
            with self.subTest(reason=reason):
                measurements = self.write("invalid-group.json", {"@type": "FeedbackLoopEvaluationMeasurements", "sessions": rows})
                payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], measurements_json=measurements)
                metric = payload["metrics"]["session_usage_deltas"]
                self.assertEqual(metric["status"], "unavailable")
                self.assertEqual(metric["by_comparison"], [])
                self.assertIn(reason, metric["by_group"][0]["reasons"])
                self.assertIn(reason, {row["reason"] for row in payload["issues"]})

    def test_missing_pair_measure_is_unavailable_without_inference(self) -> None:
        outcome = self.outcome()
        baseline = self.comparison_session("session:base", "baseline")
        candidate = self.comparison_session("session:candidate", "candidate", input_tokens=80)
        candidate.pop("cost_usd")
        measurements = self.write("missing-cost.json", {"@type": "FeedbackLoopEvaluationMeasurements", "sessions": [baseline, candidate]})
        payload = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], measurements_json=measurements)
        metric = payload["metrics"]["session_usage_deltas"]
        pair = metric["by_comparison"][0]
        self.assertEqual((metric["status"], pair["status"]), ("partial", "partial"))
        self.assertEqual(pair["measures"]["input_tokens"]["candidate_minus_baseline"], -20)
        self.assertEqual(pair["measures"]["cost_usd"], {"status": "unavailable", "baseline": 1.0, "candidate": None, "candidate_minus_baseline": None})

        token_only = dict(baseline)
        token_only.pop("cost_usd")
        cost_only = {key: value for key, value in self.comparison_session("session:cost", "candidate").items()
                     if key not in {"input_tokens", "cached_input_tokens", "output_tokens"}}
        measurements = self.write("disjoint-usage.json", {"@type": "FeedbackLoopEvaluationMeasurements", "sessions": [token_only, cost_only]})
        metric = build_feedback_loop_evaluation(feedback_plan_json=self.plan, outcome_json=[outcome], measurements_json=measurements)["metrics"]["session_usage_deltas"]
        self.assertEqual(metric["status"], "unavailable")
        self.assertEqual(metric["by_comparison"][0]["status"], "unavailable")
        self.assertTrue(all(row["candidate_minus_baseline"] is None for row in metric["by_comparison"][0]["measures"].values()))


if __name__ == "__main__":
    unittest.main()
