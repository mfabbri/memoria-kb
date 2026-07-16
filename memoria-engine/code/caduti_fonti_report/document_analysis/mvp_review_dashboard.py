from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .preview_payloads import (
    dict_object,
    list_items,
    list_strings,
    load_json_object,
    load_optional_json_object,
    write_json,
    write_markdown,
)
from .mvp_review_dashboard_markdown import render_mvp_review_dashboard_markdown


def build_mvp_review_dashboard(
    *,
    review_session_json: Path,
    review_queue_json: Path,
    review_decisions_summary_json: Path,
    consolidated_ledger_json: Path | None = None,
    verified_facts_preview_json: Path | None = None,
    profile_patch_preview_json: Path | None = None,
    profile_patch_sandbox_dir: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    session = load_json_object(review_session_json)
    queue = load_json_object(review_queue_json)
    decisions = load_json_object(review_decisions_summary_json)
    ledger = load_json_object(consolidated_ledger_json) if consolidated_ledger_json is not None else {}
    verified_facts_preview = load_optional_json_object(verified_facts_preview_json)
    profile_patch_preview = load_optional_json_object(profile_patch_preview_json)

    profiles = [_dashboard_profile(item) for item in list_items(session.get("profiles"))]
    queue_items = list_items(queue.get("items"))
    subject_counts = Counter(str(item.get("subject_kind", "") or "unknown") for item in queue_items)
    type_counts = Counter(str(item.get("item_type", "") or "unknown") for item in queue_items)
    priority_counts = Counter(str(item.get("priority", "") or "unknown") for item in queue_items)
    decision_session = dict_object(decisions.get("review_session"))
    review_focus = dict_object(session.get("review_focus"))
    focus_profiles = list_items(review_focus.get("profiles"))
    focus_item_count = sum(len(list_items(profile.get("items"))) for profile in focus_profiles)

    dashboard = {
        "@type": "MvpReviewDashboard",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "source_review_session_json": str(review_session_json),
        "source_review_queue_json": str(review_queue_json),
        "source_review_decisions_summary_json": str(review_decisions_summary_json),
        "source_consolidated_ledger_json": str(consolidated_ledger_json or ""),
        **(
            {"source_verified_facts_preview_json": str(verified_facts_preview_json)}
            if verified_facts_preview_json is not None
            else {}
        ),
        **(
            {"source_profile_patch_preview_json": str(profile_patch_preview_json)}
            if profile_patch_preview_json is not None
            else {}
        ),
        **(
            {"source_profile_patch_sandbox_dir": str(profile_patch_sandbox_dir)}
            if profile_patch_sandbox_dir is not None
            else {}
        ),
        "profile_count": len(profiles),
        "review_queue_item_count": _int_value(queue.get("item_count"), default=len(queue_items)),
        "pending_decision_count": _int_value(decisions.get("pending_count")),
        "accepted_decision_count": _int_value(decisions.get("accepted_count")),
        "invalid_decision_count": _int_value(decisions.get("invalid_count")),
        "decision_review_status": str(decisions.get("review_status", "")),
        "decision_session_status": str(decision_session.get("session_status", "not_started")),
        "focus_profile_count": len(focus_profiles),
        "focus_item_count": focus_item_count,
        "subject_kind_counts": dict(sorted(subject_counts.items())),
        "item_type_counts": dict(sorted(type_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "profiles": profiles,
        "work_files": _work_files(session=session, dashboard_sources={
            "review_session": review_session_json,
            "review_queue": review_queue_json,
            "review_decisions_summary": review_decisions_summary_json,
            "consolidated_ledger": consolidated_ledger_json,
            "verified_facts_preview": verified_facts_preview_json,
            "profile_patch_preview": profile_patch_preview_json,
            "profile_patch_sandbox": profile_patch_sandbox_dir,
        }),
        "ledger_evidence_store_coverage": dict_object(ledger.get("evidence_store_coverage")),
        "warnings": _warnings(decisions=decisions, session=session, queue_items=queue_items),
        "output_policy": {
            "primary_human_output": "historian_review/review_dashboard.md",
            "machine_output": "historian_review/review_dashboard.json",
            "preview_only": True,
            "applies_review_decisions": False,
            "creates_validated_facts": False,
            "modifies_profiles": False,
        },
    }
    if verified_facts_preview_json is not None:
        dashboard["verified_facts_preview"] = _verified_facts_preview_summary(
            verified_facts_preview,
            source_path=verified_facts_preview_json,
            include_facts=True,
        )
    if profile_patch_preview_json is not None:
        dashboard["profile_patch_preview"] = _profile_patch_preview_summary(
            profile_patch_preview,
            source_path=profile_patch_preview_json,
        )
    if profile_patch_sandbox_dir is not None:
        dashboard["profile_patch_sandbox"] = _profile_patch_sandbox_summary(profile_patch_sandbox_dir)
    if output_json is not None:
        write_json(output_json, dashboard)
    if output_md is not None:
        write_markdown(output_md, render_mvp_review_dashboard_markdown(dashboard))
    return dashboard


def _dashboard_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": str(profile.get("profile_id", "")),
        "canonical_name": str(profile.get("canonical_name", "")),
        "pilot_card_status": str(profile.get("pilot_card_status", "")),
        "model_card_review_status": str(profile.get("model_card_review_status", "")),
        "review_session_status": str(profile.get("review_session_status", "")),
        "review_item_count": _int_value(profile.get("review_item_count")),
        "pending_decision_count": _int_value(profile.get("pending_decision_count")),
        "accepted_decision_count": _int_value(profile.get("accepted_decision_count")),
        "invalid_decision_count": _int_value(profile.get("invalid_decision_count")),
        "document_count": _int_value(profile.get("document_count")),
        "candidate_evidence_claim_count": _int_value(profile.get("candidate_evidence_claim_count")),
        "reviewable_document_signal_count": _int_value(profile.get("reviewable_document_signal_count")),
        "candidate_card_path": str(profile.get("candidate_card_path", "")),
        "next_action": str(profile.get("next_action", "")),
        "review_focus_items": list_items(profile.get("review_focus_items"))[:5],
    }


def _work_files(*, session: dict[str, Any], dashboard_sources: dict[str, Path | None]) -> list[dict[str, str]]:
    files = [
        ("Review dashboard", "historian_review/review_dashboard.md"),
        ("Review session", str(dashboard_sources["review_session"])),
        ("Review queue", str(dashboard_sources["review_queue"])),
        ("Riepilogo decisioni", str(dashboard_sources["review_decisions_summary"])),
    ]
    ledger_path = dashboard_sources.get("consolidated_ledger")
    if ledger_path is not None:
        files.append(("Ledger consolidato", str(ledger_path)))
    verified_preview_path = dashboard_sources.get("verified_facts_preview")
    if verified_preview_path is not None:
        files.append(("Verified facts preview", str(verified_preview_path)))
    profile_patch_preview_path = dashboard_sources.get("profile_patch_preview")
    if profile_patch_preview_path is not None:
        files.append(("ProfilePatch preview", str(profile_patch_preview_path)))
    profile_patch_sandbox_path = dashboard_sources.get("profile_patch_sandbox")
    if profile_patch_sandbox_path is not None:
        files.append(("ProfilePatch sandbox", str(profile_patch_sandbox_path)))
    focus_template = dict_object(session.get("review_focus_decisions_template"))
    if list_items(focus_template.get("decisions")):
        files.append(("Template decisioni focus", "review_session.json:review_focus_decisions_template"))
    return [{"label": label, "path": path} for label, path in files]


def _warnings(*, decisions: dict[str, Any], session: dict[str, Any], queue_items: list[dict[str, Any]]) -> list[str]:
    warnings = [
        "Dashboard preview-only: non applica decisioni e non valida fatti storici.",
    ]
    pending = _int_value(decisions.get("pending_count"))
    if pending:
        warnings.append(f"Restano {pending} decisioni pending nella review queue.")
    if str(decisions.get("review_status", "")) != "reviewed":
        warnings.append(f"Stato decisioni non concluso: {decisions.get('review_status', '')}.")
    if not queue_items:
        warnings.append("Review queue vuota o non leggibile.")
    if _int_value(session.get("profile_count")) == 0:
        warnings.append("Nessun profilo disponibile nella review session.")
    return warnings


def _verified_facts_preview_summary(
    payload: dict[str, Any],
    *,
    source_path: Path,
    include_facts: bool = False,
) -> dict[str, Any]:
    if not payload:
        return {
            "available": False,
            "status": "missing",
            "source_path": str(source_path),
            "note": "File preview non presente o non leggibile.",
        }
    status = str(payload.get("status") or payload.get("review_status") or "")
    if status == "skipped":
        return {
            "available": False,
            "status": "skipped",
            "source_path": str(source_path),
            "reason": str(payload.get("reason", "")),
            "note": str(payload.get("note", "")),
        }
    facts = list_items(payload.get("facts"))
    summary: dict[str, Any] = {
        "available": True,
        "status": status or "preview-only",
        "source_path": str(source_path),
        "fact_count": _int_value(payload.get("fact_count"), default=len(facts)),
        "excluded_decision_count": _int_value(payload.get("excluded_decision_count")),
        "counts_by_profile": _dict_int_counts(payload.get("counts_by_profile")),
        "preview_only": bool(payload.get("preview_only", True)),
        "publication_status": str(payload.get("publication_status", "")),
    }
    if include_facts:
        summary["facts"] = [
            {
                "fact_id": str(fact.get("fact_id", "")),
                "profile_id": str(fact.get("profile_id", "")),
                "field": str(fact.get("field", "")),
                "value": str(fact.get("value", "")),
                "source_document_id": str(fact.get("source_document_id", "")),
                "source_decision_record_id": str(fact.get("source_decision_record_id", "")),
            }
            for fact in facts[:10]
        ]
    return summary


def _profile_patch_preview_summary(payload: dict[str, Any], *, source_path: Path) -> dict[str, Any]:
    if not payload:
        return {
            "available": False,
            "status": "missing",
            "source_path": str(source_path),
            "note": "File ProfilePatch preview non presente o non leggibile.",
        }
    if str(payload.get("status", "")) == "skipped":
        return {
            "available": False,
            "status": "skipped",
            "source_path": str(source_path),
            "reason": str(payload.get("reason", "")),
            "note": str(payload.get("note", "")),
        }
    patches = _profile_patch_items(payload)
    profile_ids = sorted({str(patch.get("profile_id", "")) for patch in patches if str(patch.get("profile_id", ""))})
    operation_count = sum(len(list_items(patch.get("operations"))) for patch in patches)
    return {
        "available": True,
        "status": str(payload.get("review_status") or payload.get("status") or "preview-only"),
        "source_path": str(source_path),
        "patch_count": _int_value(payload.get("patch_count"), default=len(patches)),
        "operation_count": _int_value(payload.get("operation_count"), default=operation_count),
        "skipped_fact_count": _int_value(payload.get("skipped_fact_count")),
        "profile_ids": profile_ids,
        "preview_only": bool(payload.get("preview_only", True)),
        "publication_status": str(payload.get("publication_status", "")),
    }


def _profile_patch_sandbox_summary(source_dir: Path) -> dict[str, Any]:
    if not source_dir.is_dir():
        return {
            "available": False,
            "status": "missing",
            "source_dir": str(source_dir),
            "note": "Directory sandbox non presente.",
        }
    sandbox_profiles = sorted(source_dir.glob("*.sandbox.profile.jsonld"))
    audit_files = sorted(source_dir.glob("*.sandbox.audit.json"))
    promotion_files = sorted(source_dir.glob("*.sandbox.promotion.json"))
    profile_ids: set[str] = set()
    for path in promotion_files:
        payload = load_optional_json_object(path)
        profile_id = str(payload.get("profile_id", ""))
        if profile_id:
            profile_ids.add(profile_id)
    return {
        "available": True,
        "status": "sandbox",
        "source_dir": str(source_dir),
        "sandbox_profile_count": len(sandbox_profiles),
        "audit_count": len(audit_files),
        "promotion_count": len(promotion_files),
        "profile_ids": sorted(profile_ids),
        "writes_canonical_profile": False,
    }


def _profile_patch_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if str(payload.get("@type", "")) == "ProfilePatch":
        return [payload]
    return list_items(payload.get("profile_patches"))


def _dict_int_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _int_value(count) for key, count in sorted(value.items())}


def _int_value(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build MVP historian review dashboard.")
    parser.add_argument("--review-session-json", required=True)
    parser.add_argument("--review-queue-json", required=True)
    parser.add_argument("--review-decisions-summary-json", required=True)
    parser.add_argument("--consolidated-ledger-json", default="")
    parser.add_argument("--verified-facts-preview-json", default="")
    parser.add_argument("--profile-patch-preview-json", default="")
    parser.add_argument("--profile-patch-sandbox-dir", default="")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args(argv)

    review_session_json = Path(args.review_session_json)
    review_dir = review_session_json.parent
    build_mvp_review_dashboard(
        review_session_json=review_session_json,
        review_queue_json=Path(args.review_queue_json),
        review_decisions_summary_json=Path(args.review_decisions_summary_json),
        consolidated_ledger_json=Path(args.consolidated_ledger_json) if args.consolidated_ledger_json else None,
        verified_facts_preview_json=Path(args.verified_facts_preview_json) if args.verified_facts_preview_json else None,
        profile_patch_preview_json=Path(args.profile_patch_preview_json) if args.profile_patch_preview_json else None,
        profile_patch_sandbox_dir=Path(args.profile_patch_sandbox_dir) if args.profile_patch_sandbox_dir else None,
        output_json=Path(args.output_json) if args.output_json else review_dir / "review_dashboard.json",
        output_md=Path(args.output_md) if args.output_md else review_dir / "review_dashboard.md",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
