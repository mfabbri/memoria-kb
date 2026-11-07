"""Offline feedback evaluation; identifiers measure attribution, not historical truth.

Optional ``FeedbackLoopEvaluationMeasurements`` has three record lists:
``conflicts``: conflict_id, outcome_id, before_claim_ids, after_claim_ids;
``reviews``: review_id, outcome_id, started_at, completed_at (aware ISO timestamps);
``sessions``: session_id, run_id, input_tokens, cached_input_tokens, output_tokens,
cost_usd. Optional comparison metadata is comparison_group_id, task_contract_sha256,
quality_gate_status (passed/failed/not_run), model_id and comparison_role
(baseline/candidate). Comparison readiness requires all metadata, a passed gate
and valid recorded token or cost measurements. Observed usage deltas require one
baseline and at least one candidate per declared group, with identical task hashes.
Each list is optional. Missing/invalid measurements are never estimated.
An optional ``ResearchFeedbackActionReviewSummary`` supplies explicit triage
timings; each timed action must bind to exactly one auditable outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .feedback_loop_outcome import APPROVING_TRIAGE_DECISIONS, AUDITABLE_OUTCOME_STATUSES


def build_feedback_loop_evaluation(
    *, feedback_plan_json: Path, outcome_json: list[Path],
    candidate_claims_json: Path | None = None, measurements_json: Path | None = None,
    review_summary_json: Path | None = None,
    output_json: Path | None = None, output_md: Path | None = None,
) -> dict[str, Any]:
    paths = [feedback_plan_json, *outcome_json, *([candidate_claims_json] if candidate_claims_json else []),
             *([measurements_json] if measurements_json else []),
             *([review_summary_json] if review_summary_json else [])]
    if output_json is not None and output_md is not None and output_json.resolve() == output_md.resolve():
        raise ValueError("JSON and Markdown outputs require distinct paths.")
    for output in (output_json, output_md):
        if output is not None and output.resolve() in {path.resolve() for path in paths}:
            raise ValueError("Evaluation output must not overwrite an input artifact.")
    inputs = {str(path): _input_reference(path) for path in paths}
    plan_payload = _load(feedback_plan_json, "FeedbackSearchPlanSet")
    plans = _plans(plan_payload)
    planned = {(plan_id, source_id) for plan_id, plan in plans.items() for source_id in plan["sources"]}
    issues: list[dict[str, str]] = []
    raw = [(path, _load(path, "FeedbackLoopOutcome")) for path in outcome_json]
    identifiers = Counter(_identifier(item, "feedback_loop_outcome_id") for _, item in raw)
    accepted = []
    for path, item in sorted(raw, key=lambda pair: (str(pair[0]), _text(pair[1].get("@id")))):
        event_id = _identifier(item, "feedback_loop_outcome_id")
        reason = "duplicate_outcome_id" if event_id and identifiers[event_id] > 1 else _outcome_error(item, plans)
        if reason:
            issues.append({"input": str(path), "record_id": event_id, "reason": reason})
        else:
            accepted.append({**item, "feedback_loop_outcome_id": event_id, "input_artifact": str(path)})
    accepted.sort(key=lambda item: item["feedback_loop_outcome_id"])
    event_ids = [item["feedback_loop_outcome_id"] for item in accepted]
    outcome_refs = [inputs[item["input_artifact"]] for item in accepted]
    covered = {(item["feedback_search_plan_id"], item["source_id"]) for item in accepted}
    metrics: dict[str, Any] = {
        "source_coverage": _metric(
            len(covered) / len(planned) if planned else None, len(covered), len(planned), event_ids,
            [inputs[str(feedback_plan_json)], *outcome_refs], partial=bool(issues),
            definition="Distinct planned (feedback_search_plan_id, source_id) pairs with an auditable outcome.",
        ),
        "retrieval_outcomes": _metric(
            {status: sum(item["outcome_status"] == status for item in accepted) for status in sorted(AUDITABLE_OUTCOME_STATUSES)} if accepted else None,
            len(accepted), len(raw), event_ids, outcome_refs, partial=bool(issues),
            definition="Auditable outcomes by status; no_results is search memory, not historical absence or a technical failure.",
        ),
    }
    metrics["claim_document_attribution"] = _claim_metric(candidate_claims_json, inputs, issues)
    measurements = _load(measurements_json, "FeedbackLoopEvaluationMeasurements") if measurements_json else {}
    measurement_ref = [inputs[str(measurements_json)]] if measurements_json else []
    summary_reviews, excluded_summary_reviews = _review_summary_measurements(review_summary_json, accepted, issues)
    summary_ref = [inputs[str(review_summary_json)]] if review_summary_json else []
    metrics.update(_measurement_metrics(measurements, accepted, measurement_ref, issues,
        summary_reviews=summary_reviews, summary_ref=summary_ref, excluded_summary_reviews=excluded_summary_reviews))
    payload = {
        "@type": "FeedbackLoopEvaluation", "schema_version": "1.0", "audit_only": True,
        "review_status": "unreviewed", "profile_write_allowed": False,
        "claim_promotion_allowed": False, "creates_verified_facts": False,
        "input_artifacts": sorted(inputs.values(), key=lambda item: item["path"]),
        "planned_profile_source_pairs": [
            {"feedback_search_plan_id": plan_id, "profile_id": plans[plan_id]["profile_id"], "source_id": source_id}
            for plan_id, source_id in sorted(planned)
        ],
        "accepted_outcome_ids": event_ids, "excluded_outcome_count": len(raw) - len(accepted),
        "metrics": metrics,
        "issues": sorted(issues, key=lambda item: (item["input"], item["record_id"], item["reason"])),
        "warnings": ["evaluation_is_audit_only", "document_ids_are_not_catalog_existence_checks",
                     "no_results_is_not_historical_absence", "session_totals_do_not_establish_cost_savings",
                     "session_deltas_are_observations_not_causal_savings"],
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_feedback_loop_evaluation_markdown(payload), encoding="utf-8")
    return payload


def _plans(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(payload.get("plans"), list):
        raise ValueError("FeedbackSearchPlanSet requires a plans list.")
    plans = {}
    for plan in payload["plans"]:
        if not isinstance(plan, dict):
            raise ValueError("Invalid feedback plan record.")
        plan_id = _identifier(plan, "feedback_search_plan_id")
        if not plan_id or plan_id in plans or any(not _text(plan.get(key)) for key in ("action_id", "profile_id", "source_document_id")):
            raise ValueError("Feedback plans require unique IDs and action/profile/document provenance.")
        sources = {}
        for source in plan.get("source_plans", []):
            if not isinstance(source, dict) or source.get("status") != "planned":
                continue
            source_id = _text(source.get("source_id"))
            if not source_id or source_id in sources:
                raise ValueError("Planned sources require unique nonempty source IDs per plan.")
            sources[source_id] = {_text(attempt.get("strategy_id") or attempt.get("attempt_id"))
                                  for attempt in source.get("planned_attempts", [])
                                  if isinstance(attempt, dict) and not attempt.get("skip_reason")} - {""}
        plans[plan_id] = {**plan, "sources": sources}
    return plans


def _outcome_error(item: dict[str, Any], plans: dict[str, Any]) -> str:
    if not _identifier(item, "feedback_loop_outcome_id"):
        return "missing_or_divergent_outcome_id"
    plan = plans.get(_text(item.get("feedback_search_plan_id")))
    if plan is None:
        return "unknown_feedback_plan"
    for field, plan_field in (("research_feedback_action_id", "action_id"), ("profile_id", "profile_id"), ("source_document_id", "source_document_id")):
        if _text(item.get(field)) != _text(plan[plan_field]):
            return f"mismatched_{field}"
    source_id = _text(item.get("source_id"))
    if source_id not in plan["sources"]:
        return "source_not_planned"
    strategies = _strings(item.get("strategy_ids"))
    if not strategies or not set(strategies).issubset(plan["sources"][source_id]):
        return "strategy_not_attributed_to_planned_source"
    if not _text(item.get("run_id")) or _timestamp(item.get("executed_at")) is None:
        return "missing_run_or_execution_timestamp"
    if item.get("loop_status") != "closed_with_auditable_outcome":
        return "loop_not_closed"
    approval = item.get("approved_decision")
    if (
        item.get("approved_for_demo") is not True
        or not isinstance(approval, dict)
        or _text(approval.get("action_id")) != _text(plan.get("action_id"))
        or approval.get("decision_status") != "accepted"
        or _text(approval.get("decision")).upper() not in APPROVING_TRIAGE_DECISIONS
    ):
        return "missing_or_mismatched_human_approval"
    if item.get("outcome_status") not in AUDITABLE_OUTCOME_STATUSES:
        return "unsupported_outcome_status"
    docs = _strings(item.get("result_source_document_ids"))
    if (item["outcome_status"] == "candidate_results" and not docs) or (item["outcome_status"] == "no_results" and docs):
        return "inconsistent_result_documents"
    if any(item.get(field) is not False for field in ("profile_write_allowed", "claim_promotion_allowed", "creates_verified_facts")):
        return "unsafe_or_missing_preview_flags"
    return ""


def _claim_metric(path: Path | None, inputs: dict[str, Any], issues: list[dict[str, str]]) -> dict[str, Any]:
    if path is None:
        return _metric(None, 0, 0, [], [], definition="Claim IDs with nonempty source_document_id and source_id; catalog resolution is not tested.")
    payload = _load(path, "CandidateEvidenceClaimSet")
    claims = payload.get("candidate_evidence_claims")
    if not isinstance(claims, list):
        raise ValueError("CandidateEvidenceClaimSet requires candidate_evidence_claims.")
    attributed, record_ids, invalid = 0, [], False
    identifiers = Counter(_identifier(claim, "claim_id") for claim in claims if isinstance(claim, dict))
    for index, claim in enumerate(claims):
        claim_id = _identifier(claim, "claim_id") if isinstance(claim, dict) else ""
        record_ids.append(claim_id or f"row:{index + 1}")
        if not claim_id or identifiers[claim_id] != 1 or claim.get("@type") != "CandidateEvidenceClaim":
            issues.append({"input": str(path), "record_id": claim_id, "reason": "invalid_or_duplicate_claim"})
            invalid = True
        elif _text(claim.get("source_document_id")) and _text(claim.get("source_id")):
            attributed += 1
    return _metric(attributed / len(claims) if claims else None, attributed, len(claims), record_ids,
                   [inputs[str(path)]], partial=invalid, definition="Claim IDs with nonempty source_document_id and source_id; catalog resolution is not tested.")


def _measurement_metrics(payload: dict[str, Any], outcomes: list[dict[str, Any]], refs: list[dict[str, str]], issues: list[dict[str, str]],
                         *, summary_reviews: list[dict[str, Any]], summary_ref: list[dict[str, str]], excluded_summary_reviews: int) -> dict[str, Any]:
    event_ids = {item["feedback_loop_outcome_id"] for item in outcomes}
    run_ids = {item["run_id"] for item in outcomes}
    path = refs[0]["path"] if refs else ""
    groups = {}
    for name, id_field, binding_field, bindings in (
        ("conflicts", "conflict_id", "outcome_id", event_ids),
        ("reviews", "review_id", "outcome_id", event_ids),
        ("sessions", "session_id", "run_id", run_ids),
    ):
        rows = payload.get(name, [])
        if not isinstance(rows, list):
            raise ValueError(f"{name} measurements must be a list.")
        if name == "reviews":
            rows = [*rows, *summary_reviews]
        counts = Counter(_text(row.get(id_field)) for row in rows if isinstance(row, dict))
        valid = []
        for row in rows:
            record_id = _text(row.get(id_field)) if isinstance(row, dict) else ""
            if not record_id or counts[record_id] != 1 or _text(row.get(binding_field)) not in bindings:
                issues.append({"input": _text(row.get("_input_artifact")) or path if isinstance(row, dict) else path,
                               "record_id": record_id, "reason": f"invalid_or_unbound_{name}_record"})
            else:
                valid.append(row)
        groups[name] = (rows, valid)
    conflict_rows, conflicts = groups["conflicts"]
    measured_conflicts = [row for row in conflicts if _valid_string_list(row.get("before_claim_ids"), allow_empty=False)
                          and _valid_string_list(row.get("after_claim_ids"), allow_empty=True)]
    preserved = sum(set(_strings(row["before_claim_ids"])).issubset(_strings(row["after_claim_ids"])) for row in measured_conflicts)
    review_rows, reviews = groups["reviews"]
    durations = []
    for row in reviews:
        start, end = _timestamp(row.get("started_at")), _timestamp(row.get("completed_at"))
        if start is not None and end is not None and end >= start:
            durations.append((row["review_id"], (end - start).total_seconds()))
    session_rows, sessions = groups["sessions"]
    token_rows = [row for row in sessions if all(_nonnegative_integer(row.get(key)) for key in ("input_tokens", "cached_input_tokens", "output_tokens"))
                  and row["cached_input_tokens"] <= row["input_tokens"]]
    cost_rows = [row for row in sessions if _nonnegative_number(row.get("cost_usd"))]
    for name, rows, measured in (("conflicts", conflict_rows, measured_conflicts), ("reviews", review_rows, [row for row in reviews if row["review_id"] in {key for key, _ in durations}]), ("sessions_tokens", session_rows, token_rows), ("sessions_cost", session_rows, cost_rows)):
        measured_ids = {_text(row.get("conflict_id") or row.get("review_id") or row.get("session_id")) for row in measured}
        for row in rows:
            record_id = _text(row.get("conflict_id") or row.get("review_id") or row.get("session_id")) if isinstance(row, dict) else ""
            if record_id and record_id not in measured_ids:
                issues.append({"input": _text(row.get("_input_artifact")) or path if isinstance(row, dict) else path,
                               "record_id": record_id, "reason": f"unmeasurable_{name}"})
    metrics = {
        "conflict_preservation": _metric(preserved / len(measured_conflicts) if measured_conflicts else None, preserved, len(measured_conflicts),
            [row["conflict_id"] for row in measured_conflicts], refs, partial=len(measured_conflicts) < len(conflict_rows),
            definition="Fraction of declared conflict records retaining every before_claim_id in after_claim_ids; no conflict is resolved automatically."),
        "review_latency_seconds": _metric(sum(value for _, value in durations) / len(durations) if durations else None, len(durations), len(review_rows) + excluded_summary_reviews,
            [key for key, _ in durations], [*refs, *summary_ref], partial=len(durations) < len(review_rows) + excluded_summary_reviews,
            definition="Mean completed_at minus started_at for explicit review measurements; summary decisions bind to exactly one auditable outcome by action_id."),
        "session_tokens": _metric({key: sum(row[key] for row in token_rows) for key in ("input_tokens", "cached_input_tokens", "output_tokens")} if token_rows else None,
            len(token_rows), len(session_rows), [row["session_id"] for row in token_rows], refs, partial=len(token_rows) < len(session_rows), definition="Recorded token totals; cached input is a subset of input tokens."),
        "session_cost_usd": _metric(sum(row["cost_usd"] for row in cost_rows) if cost_rows else None, len(cost_rows), len(session_rows),
            [row["session_id"] for row in cost_rows], refs, partial=len(cost_rows) < len(session_rows), definition="Recorded USD costs only; totals do not demonstrate savings or equivalent task quality."),
    }
    metrics["session_tokens"]["by_session"] = sorted(
        [{key: row[key] for key in ("session_id", "run_id", "input_tokens", "cached_input_tokens", "output_tokens")} for row in token_rows],
        key=lambda row: row["session_id"],
    )
    metrics["session_cost_usd"]["by_session"] = sorted(
        [{key: row[key] for key in ("session_id", "run_id", "cost_usd")} for row in cost_rows],
        key=lambda row: row["session_id"],
    )
    duration_by_id = dict(durations)
    metrics["review_latency_seconds"]["by_review"] = sorted([
        {"review_id": row["review_id"], "outcome_id": row["outcome_id"], "reviewer": _text(row.get("reviewer")),
         "started_at": row["started_at"], "completed_at": row["completed_at"],
         "duration_seconds": duration_by_id[row["review_id"]], "input_artifact": _text(row.get("_input_artifact")) or path}
        for row in reviews if row["review_id"] in duration_by_id
    ], key=lambda row: row["review_id"])
    metrics["session_comparison_readiness"] = _session_comparison_readiness(session_rows, sessions, refs, issues)
    metrics["session_usage_deltas"] = _session_usage_deltas(
        sessions, metrics["session_comparison_readiness"]["by_session"], refs, issues
    )
    return metrics


def _review_summary_measurements(path: Path | None, outcomes: list[dict[str, Any]], issues: list[dict[str, str]]) -> tuple[list[dict[str, Any]], int]:
    if path is None:
        return [], 0
    payload = _load(path, "ResearchFeedbackActionReviewSummary")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("ResearchFeedbackActionReviewSummary requires decisions.")
    action_counts = Counter(_text(row.get("action_id")) for row in decisions if isinstance(row, dict))
    rows, excluded = [], 0
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            issues.append({"input": str(path), "record_id": f"row:{index + 1}", "reason": "invalid_review_summary_decision"})
            excluded += 1
            continue
        if decision.get("decision_status") != "accepted":
            continue
        if not any(_text(decision.get(key)) for key in ("review_started_at", "reviewed_at")) and decision.get("review_timing_status") not in {"measured", "invalid"}:
            action_id = _text(decision.get("action_id"))
            issues.append({"input": str(path), "record_id": action_id, "reason": "review_summary_timing_unavailable"})
            excluded += 1
            continue
        action_id = _text(decision.get("action_id"))
        matches = [item for item in outcomes if item["research_feedback_action_id"] == action_id]
        start, end = _timestamp(decision.get("review_started_at")), _timestamp(decision.get("reviewed_at"))
        reason = ""
        if not action_id or action_counts[action_id] != 1 or len(matches) != 1:
            reason = "review_summary_outcome_binding_not_unique"
        elif decision.get("decision_status") != "accepted":
            reason = "review_summary_decision_not_accepted"
        elif decision.get("review_timing_status") != "measured" or start is None or end is None or end < start:
            reason = "invalid_review_summary_timing"
        elif decision.get("review_duration_seconds") is not None and (
            not _nonnegative_number(decision["review_duration_seconds"])
            or not math.isclose(decision["review_duration_seconds"], (end - start).total_seconds(), abs_tol=1e-9)
        ):
            reason = "inconsistent_review_summary_duration"
        if reason:
            issues.append({"input": str(path), "record_id": action_id, "reason": reason})
            excluded += 1
            continue
        outcome_id = matches[0]["feedback_loop_outcome_id"]
        digest = hashlib.sha256(json.dumps([action_id, outcome_id, decision["review_started_at"], decision["reviewed_at"]]).encode("utf-8")).hexdigest()[:16]
        rows.append({"review_id": f"review-summary:{digest}", "outcome_id": outcome_id,
                     "reviewer": _text(decision.get("reviewer")), "started_at": decision["review_started_at"],
                     "completed_at": decision["reviewed_at"], "_input_artifact": str(path)})
    return rows, excluded


def _session_comparison_readiness(rows: list[Any], sessions: list[dict[str, Any]], refs: list[dict[str, str]], issues: list[dict[str, str]]) -> dict[str, Any]:
    valid_ids = {_text(row["session_id"]) for row in sessions}
    records = []
    path = refs[0]["path"] if refs else ""
    for raw in rows:
        row = raw if isinstance(raw, dict) else {}
        record = {key: _text(row.get(key)) for key in ("session_id", "run_id", "comparison_group_id", "task_contract_sha256", "quality_gate_status", "model_id", "comparison_role")}
        reasons = []
        if record["session_id"] not in valid_ids:
            reasons.append("invalid_or_unbound_sessions_record")
        for key in ("comparison_group_id", "model_id"):
            if not record[key]:
                reasons.append(f"invalid_{key}" if key in row else f"missing_{key}")
        digest = record["task_contract_sha256"]
        if not digest:
            reasons.append("invalid_task_contract_sha256" if "task_contract_sha256" in row else "missing_task_contract_sha256")
        elif len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
            reasons.append("invalid_task_contract_sha256")
        else:
            record["task_contract_sha256"] = digest.lower()
        quality = record["quality_gate_status"]
        if not quality:
            reasons.append("invalid_quality_gate_status" if "quality_gate_status" in row else "missing_quality_gate_status")
        elif quality not in {"passed", "failed", "not_run"}:
            reasons.append("invalid_quality_gate_status")
        elif quality != "passed":
            reasons.append("quality_gate_not_passed")
        role = record["comparison_role"]
        if not role:
            reasons.append("invalid_comparison_role" if "comparison_role" in row else "missing_comparison_role")
        elif role not in {"baseline", "candidate"}:
            reasons.append("invalid_comparison_role")
        token_keys = ("input_tokens", "cached_input_tokens", "output_tokens")
        tokens_valid = all(_nonnegative_integer(row.get(key)) for key in token_keys) and row.get("cached_input_tokens", 0) <= row.get("input_tokens", 0)
        cost_valid = _nonnegative_number(row.get("cost_usd"))
        if any(key in row for key in token_keys) and not tokens_valid:
            reasons.append("invalid_session_tokens")
        if "cost_usd" in row and not cost_valid:
            reasons.append("invalid_session_cost")
        available = [name for name, valid in (("tokens", tokens_valid), ("cost_usd", cost_valid)) if valid]
        if not available:
            reasons.append("missing_comparison_usage")
        record.update({"status": "not_comparable" if reasons else "ready", "reasons": sorted(set(reasons)), "available_measures": available})
        records.append(record)
        for reason in reasons:
            if reason.startswith("invalid_") and reason != "invalid_or_unbound_sessions_record":
                issues.append({"input": path, "record_id": record["session_id"], "reason": reason})
    records.sort(key=lambda row: (row["session_id"], row["run_id"], json.dumps(row, sort_keys=True)))
    ready = sum(row["status"] == "ready" for row in records)
    metric = _metric({"ready": ready, "not_comparable": len(records) - ready} if records else None,
        ready, len(records), [row["session_id"] for row in records if row["session_id"]], refs,
        definition="Readiness from declared task fingerprint, group, model, baseline/candidate role and passed quality gate; no task equivalence or savings is inferred.")
    metric["by_session"] = records
    return metric


def _session_usage_deltas(sessions: list[dict[str, Any]], readiness: list[dict[str, Any]],
                         refs: list[dict[str, str]], issues: list[dict[str, str]]) -> dict[str, Any]:
    """Compare declared task groups; deltas describe observations, not savings."""
    by_id = {_text(row["session_id"]): row for row in sessions}
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in readiness:
        if row["comparison_group_id"]:
            groups.setdefault(row["comparison_group_id"], []).append(row)
    comparisons, group_records = [], []
    candidate_count = 0
    path = refs[0]["path"] if refs else ""
    for group_id, members in sorted(groups.items()):
        baselines = [row for row in members if row["comparison_role"] == "baseline"]
        candidates = [row for row in members if row["comparison_role"] == "candidate"]
        candidate_count += len(candidates)
        reasons = []
        if len(baselines) != 1:
            reasons.append("comparison_baseline_not_unique")
        if not candidates:
            reasons.append("comparison_candidate_missing")
        if any(row["status"] != "ready" for row in members):
            reasons.append("comparison_group_contains_not_comparable_session")
        if len({row["task_contract_sha256"] for row in members}) != 1:
            reasons.append("comparison_task_contract_mismatch")
        if any(row["quality_gate_status"] != "passed" for row in members):
            reasons.append("comparison_quality_gate_not_passed")
        group_records.append({"comparison_group_id": group_id,
            "session_ids": sorted(row["session_id"] for row in members),
            "status": "excluded" if reasons else "comparable", "reasons": reasons})
        if reasons:
            issues.extend({"input": path, "record_id": group_id, "reason": reason} for reason in reasons)
            continue
        baseline_meta = baselines[0]
        baseline = by_id[baseline_meta["session_id"]]
        for candidate_meta in sorted(candidates, key=lambda row: row["session_id"]):
            candidate = by_id[candidate_meta["session_id"]]
            measures = {}
            for name in ("input_tokens", "cached_input_tokens", "output_tokens", "cost_usd"):
                kind = "cost_usd" if name == "cost_usd" else "tokens"
                measured = kind in baseline_meta["available_measures"] and kind in candidate_meta["available_measures"]
                measures[name] = {"status": "measured" if measured else "unavailable",
                    "baseline": baseline.get(name), "candidate": candidate.get(name),
                    "candidate_minus_baseline": candidate[name] - baseline[name] if measured else None}
            comparisons.append({"comparison_group_id": group_id,
                "task_contract_sha256": baseline_meta["task_contract_sha256"],
                "baseline_session_id": baseline_meta["session_id"], "candidate_session_id": candidate_meta["session_id"],
                "baseline_run_id": baseline_meta["run_id"], "candidate_run_id": candidate_meta["run_id"],
                "baseline_model_id": baseline_meta["model_id"], "candidate_model_id": candidate_meta["model_id"],
                "status": "measured" if all(item["status"] == "measured" for item in measures.values()) else (
                    "partial" if any(item["status"] == "measured" for item in measures.values()) else "unavailable"),
                "measures": measures, "provenance": refs})
    measured_count = sum(row["status"] != "unavailable" for row in comparisons)
    partial = any(row["status"] != "measured" for row in comparisons) or any(row["status"] == "excluded" for row in group_records)
    metric = _metric({"observed_pair_count": measured_count} if measured_count else None,
        measured_count, candidate_count,
        [row[key] for row in comparisons for key in ("baseline_session_id", "candidate_session_id")], refs,
        partial=partial,
        definition="Observed candidate-minus-baseline absolute usage deltas for declared groups with identical task hashes and passed gates; no savings or causality is established.")
    metric["by_comparison"] = comparisons
    metric["by_group"] = group_records
    return metric


def _metric(value: Any, numerator: int, denominator: int, record_ids: list[str], provenance: list[dict[str, str]], *, partial: bool = False, definition: str) -> dict[str, Any]:
    return {"status": "unavailable" if value is None else ("partial" if partial else "measured"),
            "value": value, "numerator": numerator, "denominator": denominator,
            "record_ids": sorted(set(record_ids)), "provenance": sorted({item["path"]: item for item in provenance}.values(), key=lambda item: item["path"]),
            "definition": definition}


def _identifier(item: dict[str, Any], field: str) -> str:
    values = {_text(item.get(key)) for key in ("@id", field)} - {""}
    return next(iter(values)) if len(values) == 1 else ""


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value: Any) -> list[str]:
    return [item.strip() for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def _valid_string_list(value: Any, *, allow_empty: bool) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(isinstance(item, str) and item.strip() for item in value)


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
        return parsed if parsed is not None and parsed.tzinfo is not None and parsed.utcoffset() is not None else None
    except ValueError:
        return None


def _nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _nonnegative_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _load(path: Path, expected_type: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("@type") != expected_type:
        raise ValueError(f"Expected {expected_type}: {path}")
    return payload


def _input_reference(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def render_feedback_loop_evaluation_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Feedback loop evaluation", "", "Audit-only; no claim or profile promotion.", "",
             "| KPI | Availability | Value | Measured / denominator |", "| --- | --- | --- | --- |"]
    for name, metric in sorted(payload.get("metrics", {}).items()):
        lines.append(f"| {name} | {metric['status']} | {json.dumps(metric['value'], ensure_ascii=False)} | {metric['numerator']} / {metric['denominator']} |")
    readiness = payload.get("metrics", {}).get("session_comparison_readiness", {}).get("by_session", [])
    if readiness:
        lines.extend(["", "## Session comparison readiness", "", "| Session | Status | Reasons |", "| --- | --- | --- |"])
        lines.extend(f"| {row['session_id']} | {row['status']} | {', '.join(row['reasons'])} |" for row in readiness)
    comparisons = payload.get("metrics", {}).get("session_usage_deltas", {}).get("by_comparison", [])
    if comparisons:
        lines.extend(["", "## Observed candidate-minus-baseline deltas", "",
                      "Values describe recorded sessions; they do not establish savings or causality.", "",
                      "| Group | Baseline | Candidate | Measure | Availability | Baseline value | Candidate value | Delta |",
                      "| --- | --- | --- | --- | --- | --- | --- | --- |"])
        for pair in comparisons:
            for name, measure in pair["measures"].items():
                lines.append(f"| {pair['comparison_group_id']} | {pair['baseline_session_id']} | {pair['candidate_session_id']} | {name} | {measure['status']} | {measure['baseline']} | {measure['candidate']} | {measure['candidate_minus_baseline']} |")
    lines.extend(["", f"Excluded outcomes: {payload.get('excluded_outcome_count', 0)}", "", "## Data issues", ""])
    lines.extend(f"- `{item['record_id']}`: `{item['reason']}` ({item['input']})" for item in payload.get("issues", []))
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate recorded feedback artifacts without network or canonical writes.")
    parser.add_argument("--feedback-plan-json", required=True)
    parser.add_argument("--outcome-json", action="append", default=[])
    parser.add_argument("--candidate-claims-json")
    parser.add_argument("--measurements-json")
    parser.add_argument("--review-summary-json")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md")
    args = parser.parse_args()
    build_feedback_loop_evaluation(feedback_plan_json=Path(args.feedback_plan_json), outcome_json=[Path(path) for path in args.outcome_json],
        candidate_claims_json=Path(args.candidate_claims_json) if args.candidate_claims_json else None,
        measurements_json=Path(args.measurements_json) if args.measurements_json else None,
        review_summary_json=Path(args.review_summary_json) if args.review_summary_json else None,
        output_json=Path(args.output_json), output_md=Path(args.output_md) if args.output_md else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
