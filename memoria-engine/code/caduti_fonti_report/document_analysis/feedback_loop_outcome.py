from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUDITABLE_OUTCOME_STATUSES = {
    "candidate_results",
    "no_results",
    "needs_manual_review",
    "blocked_or_dynamic",
}

APPROVING_TRIAGE_DECISIONS = {"BUONA", "DUBBIA"}


def build_feedback_loop_outcome(
    *,
    feedback_plan_json: Path,
    review_summary_json: Path | None = None,
    action_id: str = "",
    plan_id: str = "",
    source_id: str = "",
    strategy_ids: list[str] | None = None,
    outcome_status: str,
    execution_mode: str = "manual_review_session",
    query: str = "",
    result_source_document_ids: list[str] | None = None,
    notes: str = "",
    run_id: str = "",
    executed_at: str | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    plan_payload = _load_json_object(feedback_plan_json)
    if plan_payload.get("@type") != "FeedbackSearchPlanSet":
        raise ValueError("Expected a FeedbackSearchPlanSet.")
    review_summary = _load_json_object(review_summary_json) if review_summary_json is not None else {}
    plans = [plan for plan in _list_dicts(plan_payload.get("plans"))]
    selected_plan = _select_plan(plans=plans, action_id=action_id, plan_id=plan_id)
    selected_action_id = str(selected_plan["action_id"]).strip()
    selected_plan_id = _plan_identifier(selected_plan)
    source_plan = _select_source_plan(selected_plan, source_id=source_id)
    selected_source_id = str(source_plan["source_id"]).strip()
    selected_strategies, planned_strategies, strategy_attribution = _strategy_attribution(source_plan, strategy_ids)
    status = str(outcome_status).strip()
    result_documents = sorted(set(_string_list(result_source_document_ids or [])))
    if status == "no_results" and result_documents:
        raise ValueError("A no_results outcome cannot include result SourceDocument IDs.")
    approved_decision = _approved_decision(review_summary, selected_plan)
    approved_for_demo = bool(approved_decision)

    now = _execution_time(executed_at)
    selected_run_id = str(run_id or "").strip()
    outcome_id = _outcome_id(
        action_id=selected_action_id,
        plan_id=selected_plan_id,
        source_id=selected_source_id,
        outcome_status=status,
        query=query,
        strategy_ids=selected_strategies,
        run_id=selected_run_id,
        executed_at=now,
    )
    loop_status = _loop_status(
        approved_for_demo=approved_for_demo,
        outcome_status=status,
        result_source_document_ids=result_documents,
        strategy_attribution=strategy_attribution,
        run_id=selected_run_id,
    )
    profile_id = str(selected_plan.get("profile_id", "")).strip()
    payload = {
        "@type": "FeedbackLoopOutcome",
        "@id": outcome_id,
        "feedback_loop_outcome_id": outcome_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "executed_at": now,
        "run_id": selected_run_id,
        "source_feedback_plan_json": str(feedback_plan_json),
        "source_review_summary_json": str(review_summary_json or ""),
        "feedback_search_plan_id": selected_plan_id,
        "research_feedback_action_id": selected_action_id,
        "profile_id": profile_id,
        "source_document_id": str(selected_plan.get("source_document_id", "")).strip(),
        "source_id": selected_source_id,
        "strategy_ids": selected_strategies,
        "planned_strategy_ids": planned_strategies,
        "strategy_attribution_status": strategy_attribution,
        "selected_source_plan": source_plan,
        "execution_mode": execution_mode,
        "query": query,
        "outcome_status": status,
        "loop_status": loop_status,
        "approved_for_demo": approved_for_demo,
        "approved_decision": approved_decision,
        "result_source_document_ids": result_documents,
        "notes": notes,
        "profile_write_allowed": False,
        "claim_promotion_allowed": False,
        "creates_verified_facts": False,
        "applies_profile_patch": False,
        "search_memory_update_preview": _search_memory_update_preview(
            outcome_id=outcome_id,
            action_id=selected_action_id,
            plan_id=selected_plan_id,
            profile_id=profile_id,
            source_id=selected_source_id,
            source_document_id=str(selected_plan.get("source_document_id", "")).strip(),
            strategy_ids=selected_strategies,
            planned_strategy_ids=planned_strategies,
            strategy_attribution_status=strategy_attribution,
            run_id=selected_run_id,
            outcome_status=status,
            query=query,
            result_source_document_ids=result_documents,
            notes=notes,
            executed_at=now,
        ),
        "warnings": _warnings(
            approved_for_demo=approved_for_demo,
            outcome_status=status,
            result_source_document_ids=result_documents,
            strategy_attribution=strategy_attribution,
            run_id=selected_run_id,
        ),
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_feedback_loop_outcome_markdown(payload), encoding="utf-8")
    return payload


def render_feedback_loop_outcome_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Feedback loop outcome preview",
        "",
        f"- Stato loop: `{payload.get('loop_status', '')}`",
        f"- Esito: `{payload.get('outcome_status', '')}`",
        f"- Azione: `{payload.get('research_feedback_action_id', '')}`",
        f"- Piano: `{payload.get('feedback_search_plan_id', '')}`",
        f"- Profilo: `{payload.get('profile_id', '')}`",
        f"- Fonte: `{payload.get('source_id', '')}`",
        f"- Strategie: `{', '.join(payload.get('strategy_ids', []))}` ({payload.get('strategy_attribution_status', '')})",
        f"- Run: `{payload.get('run_id', '')}`",
        f"- Esecuzione: `{payload.get('executed_at', '')}`",
        f"- Query/sessione: `{payload.get('query', '')}`",
        f"- Approvata per demo: `{payload.get('approved_for_demo', False)}`",
        "",
        "Questo artefatto e' preview-only: non crea fatti verificati, non applica patch e non modifica profili canonici.",
        "",
        "## Risultati",
        "",
    ]
    documents = payload.get("result_source_document_ids", [])
    if isinstance(documents, list) and documents:
        for document_id in documents:
            lines.append(f"- `{document_id}`")
    else:
        lines.append("_Nessun nuovo documento candidato registrato._")
    lines.extend(["", "## Memoria di ricerca preview", ""])
    memory = payload.get("search_memory_update_preview", {})
    if isinstance(memory, dict):
        lines.append(f"- Profilo: `{memory.get('profile_id', '')}`")
        lines.append(f"- Stato ricerca: `{memory.get('outcome_status', '')}`")
        lines.append(f"- Nota: {memory.get('summary', '') or '-'}")
    warnings = payload.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        lines.extend(["", "## Warning", ""])
        for warning in warnings:
            lines.append(f"- `{warning}`")
    return "\n".join(lines).rstrip() + "\n"


def _search_memory_update_preview(
    *,
    outcome_id: str,
    action_id: str,
    plan_id: str,
    profile_id: str,
    source_id: str,
    source_document_id: str,
    strategy_ids: list[str],
    planned_strategy_ids: list[str],
    strategy_attribution_status: str,
    run_id: str,
    outcome_status: str,
    query: str,
    result_source_document_ids: list[str],
    notes: str,
    executed_at: str,
) -> dict[str, Any]:
    return {
        "@type": "PersonResearchProfileSearchMemoryUpdatePreview",
        "profile_id": profile_id,
        "feedback_loop_outcome_id": outcome_id,
        "research_feedback_action_id": action_id,
        "feedback_search_plan_id": plan_id,
        "source_id": source_id,
        "source_document_id": source_document_id,
        "strategy_ids": strategy_ids,
        "planned_strategy_ids": planned_strategy_ids,
        "strategy_attribution_status": strategy_attribution_status,
        "run_id": run_id,
        "outcome_status": outcome_status,
        "query": query,
        "result_source_document_ids": result_source_document_ids,
        "summary": notes or _default_summary(outcome_status),
        "executed_at": executed_at,
        "profile_write_allowed": False,
        "merge_policy": "append_execution_event_preview_only",
        "requires_human_review_before_claim_promotion": True,
    }


def _select_plan(*, plans: list[dict[str, Any]], action_id: str, plan_id: str) -> dict[str, Any]:
    action_id = action_id.strip()
    plan_id = plan_id.strip()
    if not action_id and not plan_id:
        raise ValueError("An action_id or plan_id is required to select a feedback plan.")
    matches = [
        plan for plan in plans
        if (not action_id or str(plan.get("action_id") or "").strip() == action_id)
        and (not plan_id or _plan_identifier(plan) == plan_id)
    ]
    if len(matches) != 1:
        raise ValueError("Feedback plan selection must match exactly one plan and action.")
    selected = matches[0]
    if not str(selected.get("action_id") or "").strip() or not _plan_identifier(selected):
        raise ValueError("The selected feedback plan requires plan and action identifiers.")
    if any(not str(selected.get(field) or "").strip() for field in ("profile_id", "source_document_id")):
        raise ValueError("The selected feedback plan requires profile and source document identifiers.")
    return selected


def _plan_identifier(plan: dict[str, Any]) -> str:
    identifiers = {str(plan.get(key) or "").strip() for key in ("feedback_search_plan_id", "@id")}
    identifiers.discard("")
    if len(identifiers) > 1:
        raise ValueError("Feedback plan identifiers are divergent.")
    return next(iter(identifiers), "")


def _select_source_plan(plan: dict[str, Any], *, source_id: str) -> dict[str, Any]:
    selected_id = source_id.strip()
    matches = [
        item for item in _list_dicts(plan.get("source_plans"))
        if item.get("status") == "planned" and str(item.get("source_id") or "").strip()
        and (not selected_id or str(item["source_id"]).strip() == selected_id)
    ]
    if len(matches) != 1:
        raise ValueError("Source selection must match exactly one planned source.")
    return matches[0]


def _strategy_attribution(source_plan: dict[str, Any], strategy_ids: list[str] | None) -> tuple[list[str], list[str], str]:
    planned = sorted({
        str(attempt.get("strategy_id") or attempt.get("attempt_id") or "").strip()
        for attempt in _list_dicts(source_plan.get("planned_attempts"))
        if not attempt.get("skip_reason")
    } - {""})
    selected = sorted(set(_string_list(strategy_ids or [])))
    if selected:
        if not set(selected).issubset(planned):
            raise ValueError("Every selected strategy must belong to the selected planned source.")
        return selected, planned, "explicit"
    if len(planned) == 1:
        return planned, planned, "inferred_unique"
    return [], planned, "ambiguous" if planned else "unavailable"


def _approved_decision(review_summary: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    action_id = str(plan["action_id"]).strip()
    matches = []
    for decision in _list_dicts(review_summary.get("decisions")):
        if str(decision.get("action_id", "")).strip() != action_id:
            continue
        if str(decision.get("decision_status", "")).strip() != "accepted":
            continue
        if any(
            str(decision.get(key) or "").strip() not in ("", str(plan[field]).strip())
            for key, field in (("person_id", "profile_id"), ("profile_id", "profile_id"), ("source_document_id", "source_document_id"))
        ):
            continue
        if str(decision.get("decision", "")).strip().upper() in APPROVING_TRIAGE_DECISIONS:
            matches.append(decision)
    return matches[0] if len(matches) == 1 else {}


def _loop_status(*, approved_for_demo: bool, outcome_status: str, result_source_document_ids: list[str], strategy_attribution: str, run_id: str) -> str:
    if outcome_status not in AUDITABLE_OUTCOME_STATUSES:
        return "invalid_outcome_status"
    if not approved_for_demo:
        return "pending_historian_approval"
    if outcome_status == "candidate_results" and not result_source_document_ids:
        return "missing_candidate_result_document"
    if strategy_attribution in {"ambiguous", "unavailable"}:
        return "missing_strategy_attribution"
    if not run_id:
        return "missing_run_id"
    return "closed_with_auditable_outcome"


def _warnings(*, approved_for_demo: bool, outcome_status: str, result_source_document_ids: list[str], strategy_attribution: str, run_id: str) -> list[str]:
    warnings = [
        "feedback_loop_outcome_preview_only",
        "outcome_does_not_create_verified_facts",
        "outcome_does_not_modify_profiles",
    ]
    if not approved_for_demo:
        warnings.append("historian_feedback_action_approval_missing")
    if outcome_status == "candidate_results" and not result_source_document_ids:
        warnings.append("candidate_results_requires_source_document_id")
    if outcome_status == "no_results":
        warnings.append("no_results_is_search_memory_not_historical_absence_proof")
    if outcome_status not in AUDITABLE_OUTCOME_STATUSES:
        warnings.append("outcome_status_not_allowed")
    if strategy_attribution in {"ambiguous", "unavailable"}:
        warnings.append("executed_strategy_attribution_missing")
    if not run_id:
        warnings.append("execution_run_id_missing")
    return warnings


def _execution_time(value: str | None) -> str:
    if not value:
        return datetime.now(UTC).isoformat()
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("executed_at requires a timezone-aware ISO timestamp.")
    return timestamp.isoformat()


def _default_summary(outcome_status: str) -> str:
    if outcome_status == "no_results":
        return "Ricerca eseguita senza risultati utili; non e' prova di assenza storica."
    if outcome_status == "needs_manual_review":
        return "La ricerca richiede revisione manuale prima di produrre nuovi claim."
    if outcome_status == "blocked_or_dynamic":
        return "La fonte non ha prodotto un esito acquisibile automaticamente."
    if outcome_status == "candidate_results":
        return "La ricerca ha prodotto documenti candidati da sottoporre a review."
    return ""


def _outcome_id(*, action_id: str, plan_id: str, source_id: str, outcome_status: str, query: str, strategy_ids: list[str], run_id: str, executed_at: str) -> str:
    identity = [action_id, plan_id, source_id, strategy_ids, run_id, executed_at, outcome_status, query]
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    return f"feedback-loop-outcome:{digest}"


def _load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra un esito preview-only del feedback loop storico.")
    parser.add_argument("--feedback-plan-json", required=True)
    parser.add_argument("--review-summary-json", default="")
    parser.add_argument("--action-id", default="")
    parser.add_argument("--plan-id", default="")
    parser.add_argument("--source-id", default="")
    parser.add_argument("--strategy-id", action="append", default=[])
    parser.add_argument("--outcome-status", required=True, choices=sorted(AUDITABLE_OUTCOME_STATUSES))
    parser.add_argument("--execution-mode", default="manual_review_session")
    parser.add_argument("--query", default="")
    parser.add_argument("--result-source-document-id", action="append", default=[])
    parser.add_argument("--notes", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--executed-at", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    payload = build_feedback_loop_outcome(
        feedback_plan_json=Path(args.feedback_plan_json),
        review_summary_json=Path(args.review_summary_json) if args.review_summary_json.strip() else None,
        action_id=args.action_id,
        plan_id=args.plan_id,
        source_id=args.source_id,
        strategy_ids=args.strategy_id,
        outcome_status=args.outcome_status,
        execution_mode=args.execution_mode,
        query=args.query,
        result_source_document_ids=args.result_source_document_id,
        notes=args.notes,
        run_id=args.run_id,
        executed_at=args.executed_at or None,
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"FeedbackLoopOutcome JSON scritto in {args.output_json}")
    print(f"FeedbackLoopOutcome Markdown scritto in {args.output_md}")
    print(f"Stato loop: {payload['loop_status']}")
    return 0 if payload["loop_status"] == "closed_with_auditable_outcome" else 1


if __name__ == "__main__":
    raise SystemExit(main())
