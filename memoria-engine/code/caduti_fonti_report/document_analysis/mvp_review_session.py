from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .mvp_review_session_markdown import render_mvp_review_session_markdown
from .review_queue_items import ReviewQueueItemRecord


def build_mvp_review_session(
    *,
    summary_json: Path,
    digest_json: Path,
    review_queue_json: Path,
    review_decisions_summary_json: Path,
    consolidated_ledger_json: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    summary = _load_json_object(summary_json)
    digest = _load_json_object(digest_json)
    queue = _load_json_object(review_queue_json)
    decisions = _load_json_object(review_decisions_summary_json)
    ledger = _load_json_object(consolidated_ledger_json) if consolidated_ledger_json is not None else {}
    ledger_coverage = _ledger_evidence_store_coverage(ledger)
    ledger_profiles_by_id = {
        str(item.get("profile_id", "")): item
        for item in _list_items(ledger.get("profiles"))
        if str(item.get("profile_id", ""))
    }
    decision_session = _dict_object(decisions.get("review_session"))
    session_profiles_by_id = {
        str(item.get("profile_id", "")): item
        for item in _list_items(decision_session.get("profiles"))
        if str(item.get("profile_id", ""))
    }
    cards_by_id = {
        str(item.get("profile_id", "")): item
        for item in _list_items(digest.get("cards"))
        if str(item.get("profile_id", ""))
    }
    readiness_by_id = {
        str(item.get("profile_id", "")): item
        for item in _list_items(summary.get("profile_readiness"))
        if str(item.get("profile_id", ""))
    }
    queue_items_by_profile = _queue_items_by_profile(_list_items(queue.get("items")))
    decisions_by_item_id = _decisions_by_item_id(_list_items(decisions.get("decisions")))
    profiles = []
    review_focus_profiles = []
    for profile in _list_items(summary.get("profiles")):
        profile_id = str(profile.get("profile_id", ""))
        if not profile_id:
            continue
        card = cards_by_id.get(profile_id, {})
        readiness = readiness_by_id.get(profile_id, {})
        profile_session = session_profiles_by_id.get(profile_id, {})
        queue_items = queue_items_by_profile.get(profile_id, [])
        status = _pilot_card_status(readiness=readiness, profile_session=profile_session)
        decision_summary = _decision_summary(profile_session)
        ledger_profile = ledger_profiles_by_id.get(profile_id, {})
        profile_ledger_coverage = _dict_object(ledger_profile.get("evidence_store_coverage"))
        model_card_review_status = _model_card_review_status(
            pilot_card_status=status,
            profile_session=profile_session,
        )
        review_focus_items = [
            _review_focus_item(item, decisions_by_item_id.get(str(item.get("item_id", "")), {}))
            for item in queue_items[:5]
        ]
        if review_focus_items and model_card_review_status in {
            "in_historical_review",
            "ready_for_historical_review",
            "ready_for_publication_review",
        }:
            review_focus_profiles.append(
                {
                    "profile_id": profile_id,
                    "canonical_name": str(profile.get("canonical_name") or card.get("canonical_name") or profile_id),
                    "model_card_review_status": model_card_review_status,
                    "items": review_focus_items,
                }
            )
        profiles.append(
            {
                "@type": "MvpReviewSessionProfile",
                "profile_id": profile_id,
                "canonical_name": str(profile.get("canonical_name") or card.get("canonical_name") or profile_id),
                "pilot_card_status": status,
                "model_card_review_status": model_card_review_status,
                "readiness_status": str(readiness.get("readiness_status", "")),
                "review_session_status": str(profile_session.get("session_status", "not_started")),
                "document_count": _int_value(readiness.get("document_count")),
                "candidate_document_person_link_count": _int_value(
                    card.get("candidate_document_person_link_count")
                ),
                "candidate_evidence_claim_count": _int_value(card.get("candidate_evidence_claim_count")),
                "reviewable_document_signal_count": _int_value(card.get("reviewable_document_signal_count")),
                "review_item_count": len(queue_items),
                "accepted_decision_count": _int_value(profile_session.get("accepted_count")),
                "pending_decision_count": _int_value(profile_session.get("pending_count")),
                "invalid_decision_count": _int_value(profile_session.get("invalid_count")),
                "approved_decision_count": decision_summary["approved"],
                "rejected_decision_count": decision_summary["rejected"],
                "uncertain_decision_count": decision_summary["uncertain"],
                "decision_counts_by_action": _dict_int_counts(profile_session.get("counts_by_action")),
                "decision_counts_by_status": _dict_int_counts(profile_session.get("counts_by_status")),
                "ledger_evidence_store_coverage": profile_ledger_coverage,
                "candidate_card_path": str(card.get("candidate_card_path", "")),
                "candidate_card_exists": bool(card.get("candidate_card_exists")),
                "next_action": _next_action(status=status, readiness=readiness, profile_session=profile_session),
                "priority_review_items": [_queue_item_summary(item) for item in queue_items[:5]],
                "review_focus_items": review_focus_items,
                "review_status": "unreviewed",
                "publication_status": "not_publishable_without_curator_review",
                "publication_constraint": _publication_constraint(model_card_review_status),
            }
        )

    status_counts = Counter(str(item.get("pilot_card_status", "")) for item in profiles)
    review_focus_decisions_template = _review_focus_decisions_template(review_focus_profiles)
    session = {
        "@type": "MvpReviewSessionPack",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_curator_review",
        "source_summary_json": str(summary_json),
        "source_digest_json": str(digest_json),
        "source_review_queue_json": str(review_queue_json),
        "source_review_decisions_summary_json": str(review_decisions_summary_json),
        "source_consolidated_ledger_json": str(consolidated_ledger_json or ""),
        "ledger_evidence_store_coverage": ledger_coverage,
        "profile_count": len(profiles),
        "review_queue_item_count": _int_value(queue.get("item_count")),
        "decision_review_status": str(decisions.get("review_status", "")),
        "decision_session_status": str(decision_session.get("session_status", "not_started")),
        "publication_candidate_count": status_counts.get("publication_candidate", 0),
        "ready_for_review_count": status_counts.get("ready_for_review", 0),
        "needs_better_ocr_count": status_counts.get("needs_better_ocr", 0),
        "needs_document_signal_count": status_counts.get("needs_document_signal", 0),
        "auto_preview_count": status_counts.get("auto_preview", 0),
        "profiles": profiles,
        "review_focus": {
            "@type": "MvpReviewFocus",
            "max_items_per_profile": 5,
            "profile_count": len(review_focus_profiles),
            "item_count": sum(len(profile.get("items", [])) for profile in review_focus_profiles),
            "profiles": review_focus_profiles,
            "note": "Percorso guidato preview-only: aiuta la review, non suggerisce decisioni storiche.",
        },
        "review_focus_decisions_template": review_focus_decisions_template,
        "output_policy": {
            "primary_human_output": "historian_review/review_session.md",
            "machine_output": "historian_review/review_session.json",
            "consolidates_model_card_review": True,
            "new_model_cards_reviewed_artifacts": False,
        },
        "warnings": _warnings(profiles=profiles, decisions=decisions, ledger_coverage=ledger_coverage),
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_review_session_markdown(session), encoding="utf-8")
    return session


def _pilot_card_status(*, readiness: dict[str, Any], profile_session: dict[str, Any]) -> str:
    session_status = str(profile_session.get("session_status", "not_started"))
    if session_status == "ready_for_curator_review":
        return "publication_candidate"
    if _int_value(profile_session.get("invalid_count")) > 0:
        return "needs_curator_resolution"
    readiness_status = str(readiness.get("readiness_status", ""))
    next_action = str(readiness.get("next_action", "")).casefold()
    if "ocr" in readiness_status.casefold() or "ocr" in next_action:
        return "needs_better_ocr"
    if readiness_status == "ready_for_review":
        return "ready_for_review"
    if readiness_status in {"needs_documents", "needs_links", "needs_claims", "needs_signal_review"}:
        return "needs_document_signal"
    return "auto_preview"


def _next_action(*, status: str, readiness: dict[str, Any], profile_session: dict[str, Any]) -> str:
    if status == "publication_candidate":
        return "Preparare la scheda modello per lettura curatoriale finale."
    if status == "needs_curator_resolution":
        return "Risolvere decisioni invalide o contraddittorie prima della demo."
    if status == "needs_better_ocr":
        return "Eseguire OCR migliore o trascrizione manuale sui documenti prioritari."
    if status == "ready_for_review":
        return "Completare la review storica degli item associati al profilo."
    pending = _int_value(profile_session.get("pending_count"))
    if pending:
        return f"Compilare {pending} decisioni pending nella review queue."
    return str(readiness.get("next_action") or "Revisionare la scheda pilota e scegliere la prossima azione.")


def _model_card_review_status(*, pilot_card_status: str, profile_session: dict[str, Any]) -> str:
    session_status = str(profile_session.get("session_status", "not_started"))
    if session_status == "ready_for_curator_review":
        return "ready_for_publication_review"
    if _int_value(profile_session.get("invalid_count")) > 0:
        return "needs_curator_resolution"
    if _int_value(profile_session.get("pending_count")) > 0:
        return "in_historical_review"
    if pilot_card_status == "needs_better_ocr":
        return "needs_better_transcription"
    if pilot_card_status == "needs_document_signal":
        return "needs_more_sources"
    if pilot_card_status == "ready_for_review":
        return "ready_for_historical_review"
    return "candidate_model_card"


def _publication_constraint(model_card_review_status: str) -> str:
    if model_card_review_status == "ready_for_publication_review":
        return "Pronta per lettura curatoriale finale, non pubblicabile automaticamente."
    if model_card_review_status == "needs_curator_resolution":
        return "Non pubblicabile: decisioni invalide o contraddittorie da risolvere."
    if model_card_review_status == "in_historical_review":
        return "Non pubblicabile: restano decisioni storiche pending."
    if model_card_review_status == "needs_better_transcription":
        return "Non pubblicabile: serve OCR migliore o trascrizione umana."
    if model_card_review_status == "needs_more_sources":
        return "Non pubblicabile: segnale documentale insufficiente."
    return "Non pubblicabile senza review curatoriale umana."


def _decision_summary(profile_session: dict[str, Any]) -> dict[str, int]:
    counts_by_action = _dict_int_counts(profile_session.get("counts_by_action"))
    approved_actions = {"approve_claim", "accept_for_search", "link_to_existing_profile", "candidate_new_person"}
    rejected_actions = {"reject_claim", "reject_false_positive", "superseded", "withdrawn"}
    uncertain_actions = {
        "uncertain",
        "mark_uncertain",
        "open_conflict",
        "needs_correction",
        "request_more_sources",
        "needs_better_ocr",
        "needs_human_transcription",
    }
    return {
        "approved": sum(counts_by_action.get(action, 0) for action in approved_actions),
        "rejected": sum(counts_by_action.get(action, 0) for action in rejected_actions),
        "uncertain": sum(counts_by_action.get(action, 0) for action in uncertain_actions),
    }


def _queue_items_by_profile(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        profile_id = str(item.get("profile_id", "")).strip()
        if profile_id:
            grouped.setdefault(profile_id, []).append(item)
    return grouped


def _queue_item_summary(item: dict[str, Any]) -> dict[str, str]:
    record = ReviewQueueItemRecord.from_payload(item)
    return {
        "item_id": record.item_id,
        "item_type": record.item_type,
        "subject_kind": record.subject_kind,
        "priority": record.priority,
        "risk": record.risk,
        "question": record.question,
        "source_document_id": record.source_document_id,
        "raw_file": record.raw_file,
        "metadata_file": record.metadata_file,
        "document_reference_note": record.document_reference_note,
    }


def _review_focus_item(item: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    record = ReviewQueueItemRecord.from_payload(item)
    return {
        "item_id": record.item_id,
        "item_type": record.item_type,
        "subject_kind": record.subject_kind,
        "priority": record.priority,
        "risk": record.risk,
        "question": record.question,
        "source_document_id": record.source_document_id,
        "raw_file": record.raw_file,
        "metadata_file": record.metadata_file,
        "document_reference_note": record.document_reference_note,
        "allowed_decisions": list(record.allowed_decisions),
        "selected_action": str(decision.get("selected_action", "pending") or "pending"),
        "decision_status": str(decision.get("decision_status", "pending") or "pending"),
        "reviewer": str(decision.get("reviewer", "")),
        "notes": str(decision.get("notes", "")),
    }


def _decisions_by_item_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("item_id", "")): item for item in items if str(item.get("item_id", ""))}


def _review_focus_decisions_template(focus_profiles: list[dict[str, Any]]) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for profile in focus_profiles:
        profile_id = str(profile.get("profile_id", ""))
        canonical_name = str(profile.get("canonical_name", ""))
        for item in _list_items(profile.get("items")):
            decisions.append(
                {
                    "@type": "ReviewDecision",
                    "item_id": str(item.get("item_id", "")),
                    "item_type": str(item.get("item_type", "")),
                    "subject_kind": str(item.get("subject_kind", "")),
                    "profile_id": profile_id,
                    "canonical_name": canonical_name,
                    "source_document_id": str(item.get("source_document_id", "")),
                    "selected_action": "",
                    "allowed_decisions": _list_strings(item.get("allowed_decisions")),
                    "reviewer": "",
                    "reviewed_at": "",
                    "notes": "",
                    "review_status": "draft",
                }
            )
    return {
        "@type": "ReviewDecisionTemplate",
        "template_scope": "review_focus",
        "review_status": "draft",
        "item_count": len(decisions),
        "decisions": decisions,
        "note": "Sottoinsieme compilabile degli item focus; gli item non inclusi restano pending nella review queue completa.",
    }


def _ledger_evidence_store_coverage(ledger: dict[str, Any]) -> dict[str, Any]:
    coverage = _dict_object(ledger.get("evidence_store_coverage"))
    if not coverage:
        return {"enabled": False}
    return coverage


def _warnings(*, profiles: list[dict[str, Any]], decisions: dict[str, Any], ledger_coverage: dict[str, Any]) -> list[str]:
    warnings = ["Sessione preview-only: serve revisione umana prima di qualsiasi pubblicazione."]
    if not profiles:
        warnings.append("Nessun profilo pilota nella sessione.")
    if not any(profile.get("pilot_card_status") == "publication_candidate" for profile in profiles):
        warnings.append("Nessuna scheda e' publication_candidate: il pacchetto resta materiale di review.")
    if _int_value(decisions.get("pending_count")) > 0:
        warnings.append("Esistono decisioni pending da compilare.")
    if _int_value(decisions.get("invalid_count")) > 0 or _int_value(decisions.get("validation_error_count")) > 0:
        warnings.append("Esistono decisioni invalide da correggere.")
    if ledger_coverage.get("enabled") and _int_value(ledger_coverage.get("record_count")) and not _int_value(ledger_coverage.get("profiles_with_records_count")):
        warnings.append("Il ledger contiene record store, ma nessuno e' associato ai profili della sessione.")
    if ledger_coverage.get("enabled") and _int_value(ledger_coverage.get("record_count")) == _int_value(ledger_coverage.get("workflow_unscoped_record_count")):
        warnings.append("La copertura store del ledger contiene solo workflow non scopiati.")
    return warnings


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


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _dict_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _dict_int_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _int_value(raw_value) for key, raw_value in sorted(value.items())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera una sessione di revisione MVP.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--digest-json", required=True)
    parser.add_argument("--review-queue-json", required=True)
    parser.add_argument("--review-decisions-summary-json", required=True)
    parser.add_argument("--consolidated-ledger-json", default="")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args(argv)
    review_dir = Path(args.review_queue_json).parent
    output_json = Path(args.output_json) if args.output_json else review_dir / "review_session.json"
    output_md = Path(args.output_md) if args.output_md else review_dir / "review_session.md"
    build_mvp_review_session(
        summary_json=Path(args.summary_json),
        digest_json=Path(args.digest_json),
        review_queue_json=Path(args.review_queue_json),
        review_decisions_summary_json=Path(args.review_decisions_summary_json),
        consolidated_ledger_json=Path(args.consolidated_ledger_json) if args.consolidated_ledger_json else None,
        output_json=output_json,
        output_md=output_md,
    )
    print(f"Sessione review MVP: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
