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
    review_summary = _load_json_object(review_summary_json) if review_summary_json is not None else {}
    plans = [plan for plan in _list_dicts(plan_payload.get("plans"))]
    selected_plan = _select_plan(plans=plans, action_id=action_id, plan_id=plan_id)
    selected_action_id = str(action_id or selected_plan.get("action_id", "")).strip()
    selected_plan_id = str(plan_id or selected_plan.get("feedback_search_plan_id", "") or selected_plan.get("@id", "")).strip()
    selected_source_id = str(source_id or _first_planned_source_id(selected_plan)).strip()
    status = str(outcome_status).strip()
    result_documents = _string_list(result_source_document_ids or [])
    approved_decision = _approved_decision(review_summary, selected_action_id)
    approved_for_demo = bool(approved_decision)

    outcome_id = _outcome_id(
        action_id=selected_action_id,
        plan_id=selected_plan_id,
        source_id=selected_source_id,
        outcome_status=status,
        query=query,
    )
    loop_status = _loop_status(
        approved_for_demo=approved_for_demo,
        outcome_status=status,
        result_source_document_ids=result_documents,
    )
    profile_id = str(selected_plan.get("profile_id", "")).strip()
    now = executed_at or datetime.now(UTC).isoformat()
    payload = {
        "@type": "FeedbackLoopOutcome",
        "@id": outcome_id,
        "feedback_loop_outcome_id": outcome_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "executed_at": now,
        "run_id": run_id,
        "source_feedback_plan_json": str(feedback_plan_json),
        "source_review_summary_json": str(review_summary_json or ""),
        "feedback_search_plan_id": selected_plan_id,
        "research_feedback_action_id": selected_action_id,
        "profile_id": profile_id,
        "source_document_id": str(selected_plan.get("source_document_id", "")).strip(),
        "source_id": selected_source_id,
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
        "outcome_status": outcome_status,
        "query": query,
        "result_source_document_ids": result_source_document_ids,
        "summary": notes or _default_summary(outcome_status),
        "executed_at": executed_at,
        "profile_write_allowed": False,
        "requires_human_review_before_claim_promotion": True,
    }


def _select_plan(*, plans: list[dict[str, Any]], action_id: str, plan_id: str) -> dict[str, Any]:
    action_id = action_id.strip()
    plan_id = plan_id.strip()
    for plan in plans:
        if action_id and str(plan.get("action_id", "")).strip() == action_id:
            return plan
        if plan_id and str(plan.get("feedback_search_plan_id", "") or plan.get("@id", "")).strip() == plan_id:
            return plan
    return {}


def _approved_decision(review_summary: dict[str, Any], action_id: str) -> dict[str, Any]:
    if not action_id:
        return {}
    for decision in _list_dicts(review_summary.get("decisions")):
        if str(decision.get("action_id", "")).strip() != action_id:
            continue
        if str(decision.get("decision_status", "")).strip() != "accepted":
            continue
        if str(decision.get("decision", "")).strip().upper() in APPROVING_TRIAGE_DECISIONS:
            return decision
    return {}


def _loop_status(*, approved_for_demo: bool, outcome_status: str, result_source_document_ids: list[str]) -> str:
    if outcome_status not in AUDITABLE_OUTCOME_STATUSES:
        return "invalid_outcome_status"
    if not approved_for_demo:
        return "pending_historian_approval"
    if outcome_status == "candidate_results" and not result_source_document_ids:
        return "missing_candidate_result_document"
    return "closed_with_auditable_outcome"


def _warnings(*, approved_for_demo: bool, outcome_status: str, result_source_document_ids: list[str]) -> list[str]:
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
    return warnings


def _first_planned_source_id(plan: dict[str, Any]) -> str:
    for source_plan in _list_dicts(plan.get("source_plans")):
        source_id = str(source_plan.get("source_id", "")).strip()
        if source_id:
            return source_id
    return ""


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


def _outcome_id(*, action_id: str, plan_id: str, source_id: str, outcome_status: str, query: str) -> str:
    digest = hashlib.sha256(f"{action_id}|{plan_id}|{source_id}|{outcome_status}|{query}".encode("utf-8")).hexdigest()[:16]
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
    return [str(item).strip() for item in value if str(item).strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra un esito preview-only del feedback loop storico.")
    parser.add_argument("--feedback-plan-json", required=True)
    parser.add_argument("--review-summary-json", default="")
    parser.add_argument("--action-id", default="")
    parser.add_argument("--plan-id", default="")
    parser.add_argument("--source-id", default="")
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
