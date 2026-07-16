from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .mvp_review_decisions_markdown import render_mvp_review_decisions_markdown

PENDING_ACTION = "pending"


def build_mvp_review_decisions_summary(
    *,
    review_queue_json: Path,
    decisions_json: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    if not review_queue_json.exists() or not review_queue_json.is_file():
        raise FileNotFoundError(f"Review queue non trovata: {review_queue_json}")
    if not decisions_json.exists() or not decisions_json.is_file():
        raise FileNotFoundError(f"File decisioni non trovato: {decisions_json}")

    queue = _load_json_object(review_queue_json)
    decisions_payload = _load_json_object(decisions_json)
    queue_items = _list_items(queue.get("items"))
    queue_by_id = {str(item.get("item_id", "")): item for item in queue_items if str(item.get("item_id", ""))}
    decisions_by_id = _collect_decisions_by_id(decisions_payload)
    decision_file_coverage = _build_decision_file_coverage(
        queue_items=queue_items,
        queue_by_id=queue_by_id,
        decisions_payload=decisions_payload,
        decisions_by_id=decisions_by_id,
    )
    validation_errors: list[dict[str, str]] = []
    reviewed_items: list[dict[str, Any]] = []

    for item in queue_items:
        item_id = str(item.get("item_id", ""))
        decision = decisions_by_id.get(item_id, {})
        selected_action = str(decision.get("selected_action", "")).strip()
        allowed_decisions = _list_strings(item.get("allowed_decisions"))
        status = "pending"
        error = ""
        if selected_action:
            if selected_action in allowed_decisions:
                status = "accepted"
            else:
                status = "invalid"
                error = f"Azione non ammessa per {item_id}: {selected_action}"
                validation_errors.append(
                    {
                        "item_id": item_id,
                        "error_type": "action_not_allowed",
                        "selected_action": selected_action,
                        "message": error,
                    }
                )
        reviewed_items.append(
            {
                "@type": "ReviewDecisionStatus",
                "item_id": item_id,
                "item_type": str(item.get("item_type", "")),
                "subject_kind": str(item.get("subject_kind", "")),
                "profile_id": str(item.get("profile_id", "")),
                "source_document_id": str(item.get("source_document_id", "")),
                "source_item_id": str(item.get("source_item_id", "")),
                "question": str(item.get("question", "")),
                "allowed_decisions": allowed_decisions,
                "candidate": _dict_object(item.get("candidate")),
                "context": str(item.get("context", "")),
                "selected_action": selected_action or PENDING_ACTION,
                "decision_status": status,
                "reviewer": str(decision.get("reviewer", "")),
                "reviewed_at": str(decision.get("reviewed_at", "")),
                "notes": str(decision.get("notes", "")),
                "error": error,
            }
        )

    for item_id, decision in decisions_by_id.items():
        if item_id not in queue_by_id:
            validation_errors.append(
                {
                    "item_id": item_id,
                    "error_type": "unknown_item_id",
                    "selected_action": str(decision.get("selected_action", "")),
                    "message": f"Decisione riferita a item sconosciuto: {item_id}",
                }
            )

    counts_by_status = Counter(str(item.get("decision_status", "")) for item in reviewed_items)
    counts_by_action = Counter(str(item.get("selected_action", "")) for item in reviewed_items)
    counts_by_item_type = Counter(str(item.get("item_type", "")) for item in reviewed_items)
    counts_by_subject_kind = Counter(str(item.get("subject_kind", "")) for item in reviewed_items)
    review_session = _build_review_session(reviewed_items)
    review_status = _summary_status(
        accepted=counts_by_status.get("accepted", 0),
        pending=counts_by_status.get("pending", 0),
        invalid=counts_by_status.get("invalid", 0),
        validation_errors=len(validation_errors),
    )
    summary: dict[str, Any] = {
        "@type": "MvpReviewDecisionsSummary",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_review_queue_json": str(review_queue_json),
        "source_decisions_json": str(decisions_json),
        "review_status": review_status,
        "publication_status": "not_publishable_without_human_review",
        "item_count": len(queue_items),
        "accepted_count": counts_by_status.get("accepted", 0),
        "pending_count": counts_by_status.get("pending", 0),
        "invalid_count": counts_by_status.get("invalid", 0),
        "validation_error_count": len(validation_errors),
        "counts_by_status": dict(sorted(counts_by_status.items())),
        "counts_by_action": dict(sorted(counts_by_action.items())),
        "counts_by_item_type": dict(sorted(counts_by_item_type.items())),
        "counts_by_subject_kind": dict(sorted(counts_by_subject_kind.items())),
        "decision_file_coverage": decision_file_coverage,
        "review_session": review_session,
        "decisions": reviewed_items,
        "validation_errors": validation_errors,
        "warnings": [
            "Il riepilogo valida decisioni umane, ma non applica patch.",
            "Nessuna decisione crea fatti verificati o aggiorna profili JSON-LD.",
            "Le decisioni pending richiedono revisione prima di qualsiasi pubblicazione.",
        ],
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_review_decisions_markdown(summary), encoding="utf-8")
    return summary


def _summary_status(*, accepted: int, pending: int, invalid: int, validation_errors: int) -> str:
    if invalid or validation_errors:
        return "invalid"
    if accepted and pending:
        return "partial_review"
    if accepted and not pending:
        return "reviewed"
    return "pending_review"


def _build_review_session(reviewed_items: list[dict[str, Any]]) -> dict[str, Any]:
    profiles_by_id: dict[str, list[dict[str, Any]]] = {}
    unscoped_item_count = 0
    for item in reviewed_items:
        profile_id = str(item.get("profile_id", "")).strip()
        if not profile_id:
            unscoped_item_count += 1
            continue
        profiles_by_id.setdefault(profile_id, []).append(item)

    profile_summaries: list[dict[str, Any]] = []
    for profile_id, profile_items in sorted(profiles_by_id.items()):
        counts_by_status = Counter(str(item.get("decision_status", "")) for item in profile_items)
        counts_by_action = Counter(str(item.get("selected_action", "")) for item in profile_items)
        counts_by_item_type = Counter(str(item.get("item_type", "")) for item in profile_items)
        counts_by_subject_kind = Counter(str(item.get("subject_kind", "")) for item in profile_items)
        session_status = _profile_session_status(
            accepted=counts_by_status.get("accepted", 0),
            pending=counts_by_status.get("pending", 0),
            invalid=counts_by_status.get("invalid", 0),
        )
        profile_summaries.append(
            {
                "@type": "MvpReviewSessionProfile",
                "profile_id": profile_id,
                "session_status": session_status,
                "item_count": len(profile_items),
                "accepted_count": counts_by_status.get("accepted", 0),
                "pending_count": counts_by_status.get("pending", 0),
                "invalid_count": counts_by_status.get("invalid", 0),
                "counts_by_status": dict(sorted(counts_by_status.items())),
                "counts_by_action": dict(sorted(counts_by_action.items())),
                "counts_by_item_type": dict(sorted(counts_by_item_type.items())),
                "counts_by_subject_kind": dict(sorted(counts_by_subject_kind.items())),
            }
        )

    session_statuses = Counter(str(item.get("session_status", "")) for item in profile_summaries)
    return {
        "@type": "MvpReviewSession",
        "session_status": _overall_session_status(session_statuses),
        "profile_count": len(profile_summaries),
        "unscoped_item_count": unscoped_item_count,
        "ready_for_curator_review_count": session_statuses.get("ready_for_curator_review", 0),
        "in_review_count": session_statuses.get("in_review", 0),
        "not_started_count": session_statuses.get("not_started", 0),
        "invalid_count": session_statuses.get("invalid", 0),
        "profiles": profile_summaries,
    }


def _profile_session_status(*, accepted: int, pending: int, invalid: int) -> str:
    if invalid:
        return "invalid"
    if accepted and pending:
        return "in_review"
    if accepted and not pending:
        return "ready_for_curator_review"
    return "not_started"


def _overall_session_status(session_statuses: Counter[str]) -> str:
    if session_statuses.get("invalid", 0):
        return "invalid"
    if session_statuses.get("in_review", 0):
        return "in_review"
    if session_statuses.get("ready_for_curator_review", 0) and session_statuses.get("not_started", 0):
        return "in_review"
    if session_statuses.get("ready_for_curator_review", 0):
        return "ready_for_curator_review"
    return "not_started"


def _build_decision_file_coverage(
    *,
    queue_items: list[dict[str, Any]],
    queue_by_id: dict[str, dict[str, Any]],
    decisions_payload: dict[str, Any],
    decisions_by_id: dict[str, dict[str, Any]],
) -> dict[str, int | str]:
    decision_entries = _list_items(decisions_payload.get("decisions"))
    provided_known_item_count = 0
    provided_unknown_item_count = 0
    selected_action_count = 0
    blank_action_count = 0
    provided_without_item_id_count = 0

    for decision in decision_entries:
        item_id = str(decision.get("item_id", "")).strip()
        selected_action = str(decision.get("selected_action", "")).strip()
        if not item_id:
            provided_without_item_id_count += 1
            continue
        if item_id not in queue_by_id:
            provided_unknown_item_count += 1
            continue
        provided_known_item_count += 1
        if selected_action:
            selected_action_count += 1
        else:
            blank_action_count += 1

    queue_item_ids = {str(item.get("item_id", "")).strip() for item in queue_items if str(item.get("item_id", "")).strip()}
    provided_queue_item_ids = {item_id for item_id in decisions_by_id if item_id in queue_by_id}
    queue_items_without_provided_decision_count = len(queue_item_ids - provided_queue_item_ids)
    coverage_status = "not_started"
    if selected_action_count and queue_items_without_provided_decision_count:
        coverage_status = "partial"
    elif selected_action_count and blank_action_count:
        coverage_status = "partial"
    elif selected_action_count and not queue_items_without_provided_decision_count and not blank_action_count:
        coverage_status = "complete"

    return {
        "@type": "MvpReviewDecisionFileCoverage",
        "coverage_status": coverage_status,
        "queue_item_count": len(queue_items),
        "provided_decision_count": len(decision_entries),
        "provided_known_item_count": provided_known_item_count,
        "provided_unknown_item_count": provided_unknown_item_count,
        "provided_without_item_id_count": provided_without_item_id_count,
        "selected_action_count": selected_action_count,
        "blank_action_count": blank_action_count,
        "queue_items_without_provided_decision_count": queue_items_without_provided_decision_count,
    }


def _collect_decisions_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions_by_id: dict[str, dict[str, Any]] = {}
    for decision in _list_items(payload.get("decisions")):
        item_id = str(decision.get("item_id", "")).strip()
        if item_id:
            decisions_by_id[item_id] = decision
    return decisions_by_id


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida e riepiloga decisioni della review queue MVP.")
    parser.add_argument("--review-queue-json", required=True)
    parser.add_argument("--decisions-json", required=True)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    review_queue_json = Path(args.review_queue_json)
    decisions_json = Path(args.decisions_json)
    output_dir = review_queue_json.parent
    output_json = Path(args.output_json) if args.output_json else output_dir / "review_decisions_summary.json"
    output_md = Path(args.output_md) if args.output_md else output_dir / "review_decisions_summary.md"
    try:
        summary = build_mvp_review_decisions_summary(
            review_queue_json=review_queue_json,
            decisions_json=decisions_json,
            output_json=output_json,
            output_md=output_md,
        )
    except FileNotFoundError as error:
        print(str(error))
        return 2
    print(f"Riepilogo decisioni MVP: {output_md}")
    print(f"Stato: {summary['review_status']}")
    print(f"Accettati: {summary['accepted_count']}")
    print(f"Pending: {summary['pending_count']}")
    print(f"Errori validazione: {summary['validation_error_count']}")
    return 1 if summary["review_status"] == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
