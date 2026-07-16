from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .evidence_store_records import EvidenceStoreRecord
from .preview_payloads import (
    dict_object,
    list_items,
    list_strings,
    unique_non_empty,
    write_json,
    write_markdown,
    yaml_value,
)

DECISION_RECORD_KINDS = {"historical_review_decision", "review_decision"}
APPROVAL_ACTIONS = {"confirm", "approve_claim", "approved"}
REQUEST_MORE_SOURCES_ACTIONS = {"request_more_sources", "needs_better_ocr", "needs_human_transcription"}
UNCERTAIN_ACTIONS = {"uncertain", "pending"}
REJECTION_ACTIONS = {"reject_false_positive", "reject", "rejected"}
CONFLICT_ACTIONS = {"conflict_open", "open_conflict", "mark_conflict"}
SUPERSEDED_ACTIONS = {"superseded", "withdraw", "withdrawn"}
WORKFLOW_ACTIONS = {"needs_better_ocr", "needs_human_transcription", "workflow_warning"}


def build_review_decision_conflict_register_preview(
    *,
    evidence_db: Path,
    evidence_source_run_id: list[str],
    output_json: Path | None = None,
    output_md: Path | None = None,
    profile_id: list[str] | None = None,
    limit: int = 0,
) -> dict[str, Any]:
    if not evidence_db.is_file():
        raise FileNotFoundError(f"Evidence DB non trovato: {evidence_db}")
    source_run_ids = unique_non_empty(evidence_source_run_id)
    if not source_run_ids:
        raise ValueError("Specificare almeno un evidence_source_run_id.")
    profile_filter = unique_non_empty(profile_id or [])
    records = [
        EvidenceStoreRecord.from_row(row)
        for row in _fetch_evidence_records(evidence_db=evidence_db, source_run_ids=source_run_ids)
    ]
    records = [record for record in records if record.record_kind in DECISION_RECORD_KINDS]
    if profile_filter:
        records = [record for record in records if _record_matches_profiles(record, profile_filter)]
    decisions = [_decision_from_record(record) for record in records]
    decisions.sort(key=lambda item: (str(item.get("profile_id", "")), str(item.get("record_id", ""))))
    if limit > 0:
        decisions = decisions[:limit]

    open_conflicts = [
        _conflict_case(decision)
        for decision in decisions
        if decision["normalized_state"] in {"conflict_open", "uncertain", "request_more_sources"}
    ]
    counts_by_state = Counter(str(decision.get("normalized_state", "")) for decision in decisions)
    counts_by_scope = Counter(str(decision.get("decision_scope", "")) for decision in decisions)
    payload: dict[str, Any] = {
        "@type": "ReviewDecisionConflictRegisterPreview",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_evidence_db": str(evidence_db),
        "source_run_ids": sorted(source_run_ids),
        "profile_ids": profile_filter,
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "decision_count": len(decisions),
        "historical_decision_count": counts_by_scope.get("historical_substantive", 0),
        "operational_decision_count": counts_by_scope.get("operational_or_workflow", 0),
        "open_conflict_count": len(open_conflicts),
        "eligible_for_verified_fact_preview_count": sum(
            1 for decision in decisions if bool(decision.get("eligible_for_verified_fact_preview"))
        ),
        "counts_by_state": dict(counts_by_state),
        "counts_by_scope": dict(counts_by_scope),
        "decisions": decisions,
        "open_conflicts": open_conflicts,
        "provenance": {
            "evidence_record_count": len(records),
            "source_run_ids": sorted(source_run_ids),
            "record_ids": [record.record_id for record in records],
            "payload_hashes": sorted({record.payload_hash for record in records if record.payload_hash}),
        },
        "safety_notes": [
            "Registro preview-only read-only da evidence store.",
            "Non risolve conflitti e non approva decisioni.",
            "Non crea verified_facts canonici.",
            "Non modifica profili JSON-LD e non applica ProfilePatch.",
        ],
    }
    if output_json is not None:
        write_json(output_json, payload)
    if output_md is not None:
        write_markdown(output_md, render_review_decision_conflict_register_markdown(payload))
    return payload


def render_review_decision_conflict_register_markdown(payload: dict[str, Any]) -> str:
    decisions = list_items(payload.get("decisions"))
    open_conflicts = list_items(payload.get("open_conflicts"))
    lines = [
        "---",
        "type: review_decision_conflict_register_preview",
        f"review_status: {yaml_value(payload.get('review_status', 'preview-only'))}",
        f"publication_status: {yaml_value(payload.get('publication_status', 'not_publishable_without_editorial_review'))}",
        "preview_only: true",
        "---",
        "",
        "# ReviewDecision/Conflict register preview",
        "",
        "Registro tecnico preview-only. Non e' un review store canonico e non risolve conflitti storici.",
        "",
        "## Sintesi",
        "",
        f"- Decisioni: `{payload.get('decision_count', 0)}`",
        f"- Decisioni storiche sostanziali: `{payload.get('historical_decision_count', 0)}`",
        f"- Decisioni operative/workflow: `{payload.get('operational_decision_count', 0)}`",
        f"- Conflitti/ambiguita' aperti: `{payload.get('open_conflict_count', 0)}`",
        f"- Eleggibili per verified_facts.preview: `{payload.get('eligible_for_verified_fact_preview_count', 0)}`",
        f"- Run store: `{', '.join(list_strings(payload.get('source_run_ids')))}`",
        "",
        "## Stati",
        "",
    ]
    counts_by_state = dict_object(payload.get("counts_by_state"))
    if not counts_by_state:
        lines.extend(["_Nessuno stato decisionale._", ""])
    for state, count in sorted(counts_by_state.items()):
        lines.append(f"- `{state}`: `{count}`")
    lines.extend(["", "## Decisioni", ""])
    if not decisions:
        lines.extend(["_Nessuna decisione nella run filtrata._", ""])
    for decision in decisions:
        lines.extend(
            [
                f"### {decision.get('record_id', '')}",
                "",
                f"- Profilo: `{decision.get('profile_id', '')}`",
                f"- Documento: `{decision.get('source_document_id', '')}`",
                f"- Stato normalizzato: `{decision.get('normalized_state', '')}`",
                f"- Ambito: `{decision.get('decision_scope', '')}`",
                f"- Azione: `{decision.get('selected_action', '')}`",
                f"- Decision status: `{decision.get('decision_status', '')}`",
                f"- Eligible verified_facts.preview: `{str(bool(decision.get('eligible_for_verified_fact_preview'))).lower()}`",
                f"- Revisore: `{decision.get('reviewer', '')}`",
                "",
            ]
        )
    lines.extend(["## Conflitti e ambiguita' aperti", ""])
    if not open_conflicts:
        lines.extend(["_Nessun conflitto o ambiguita' aperta nel registro preview._", ""])
    for conflict in open_conflicts:
        lines.append(
            f"- `{conflict.get('conflict_id', '')}` "
            f"profilo `{conflict.get('profile_id', '')}` "
            f"stato `{conflict.get('normalized_state', '')}` "
            f"documento `{conflict.get('source_document_id', '')}`"
        )
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Output automatico preview-only.",
            "- Non scrive nello evidence store.",
            "- Non crea fatti canonici.",
            "- Non modifica profili JSON-LD.",
            "- Non applica ProfilePatch.",
            "- Non risolve conflitti storici.",
            "",
        ]
    )
    return "\n".join(lines)


def _fetch_evidence_records(*, evidence_db: Path, source_run_ids: list[str]) -> list[dict[str, Any]]:
    uri = evidence_db.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in source_run_ids)
        rows = connection.execute(
            f"""
            SELECT record_id, source_run_id, record_kind, subject_id,
                   source_document_id, review_status, payload_hash, payload_json
            FROM evidence_records
            WHERE source_run_id IN ({placeholders})
            ORDER BY source_run_id ASC, record_kind ASC, record_id ASC
            """,
            tuple(source_run_ids),
        ).fetchall()
    return [dict(row) for row in rows]


def _decision_from_record(record: EvidenceStoreRecord) -> dict[str, Any]:
    payload = record.scoped_payload(profile_id=record.primary_profile_id())
    candidate = dict_object(payload.get("candidate"))
    selected_action = str(payload.get("selected_action", "")).strip()
    decision_status = str(payload.get("decision_status", "")).strip()
    subject_kind = str(payload.get("subject_kind", record.subject_kind)).strip()
    profile = str(payload.get("profile_id", "")).strip()
    source_document_id = str(payload.get("source_document_id", "")).strip()
    normalized_state = _normalized_state(
        selected_action=selected_action,
        decision_status=decision_status,
        review_status=record.review_status,
    )
    decision_scope = _decision_scope(
        record_kind=record.record_kind,
        selected_action=selected_action,
        subject_kind=subject_kind,
    )
    eligible = (
        decision_scope == "historical_substantive"
        and normalized_state == "approved"
        and selected_action in APPROVAL_ACTIONS
        and bool(profile)
        and bool(source_document_id)
    )
    return {
        "@type": "ReviewDecisionRegisterEntryPreview",
        "record_id": record.record_id,
        "source_run_id": record.source_run_id,
        "record_kind": record.record_kind,
        "profile_id": profile,
        "source_document_id": source_document_id,
        "source_item_id": str(payload.get("source_item_id", "")).strip(),
        "item_id": str(payload.get("item_id", "")).strip(),
        "source_record_id": str(payload.get("source_record_id", "")).strip(),
        "review_item_id": str(payload.get("review_item_id", "") or payload.get("item_id", "")).strip(),
        "review_status": record.review_status,
        "selected_action": selected_action,
        "decision_status": decision_status,
        "normalized_state": normalized_state,
        "decision_scope": decision_scope,
        "eligible_for_verified_fact_preview": eligible,
        "opens_conflict": normalized_state in {"conflict_open", "uncertain", "request_more_sources"},
        "subject_kind": subject_kind,
        "field": str(candidate.get("field") or payload.get("field") or "").strip(),
        "value": str(candidate.get("value") or payload.get("value") or "").strip(),
        "reviewer": str(payload.get("reviewer", "")).strip(),
        "reviewed_at": str(payload.get("reviewed_at", "")).strip(),
        "payload_hash": record.payload_hash,
        "provenance": _provenance(record, profile_id=profile),
    }


def _normalized_state(*, selected_action: str, decision_status: str, review_status: str) -> str:
    values = {selected_action, decision_status, review_status}
    if values.intersection(CONFLICT_ACTIONS):
        return "conflict_open"
    if values.intersection(SUPERSEDED_ACTIONS):
        return "superseded"
    if values.intersection(REQUEST_MORE_SOURCES_ACTIONS):
        return "request_more_sources"
    if values.intersection(UNCERTAIN_ACTIONS):
        return "uncertain"
    if values.intersection(REJECTION_ACTIONS):
        return "rejected"
    if selected_action in APPROVAL_ACTIONS or decision_status in {"approved", "accepted", "reviewed"}:
        return "approved"
    return str(decision_status or review_status or selected_action or "unknown").strip() or "unknown"


def _decision_scope(*, record_kind: str, selected_action: str, subject_kind: str) -> str:
    if subject_kind == "workflow" or selected_action in WORKFLOW_ACTIONS:
        return "operational_or_workflow"
    if record_kind == "historical_review_decision":
        return "historical_substantive"
    return "operational_or_workflow"


def _conflict_case(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "@type": "ConflictCasePreview",
        "conflict_id": f"conflict-preview:{_slug(str(decision.get('record_id', '')))}",
        "source_decision_record_id": decision.get("record_id", ""),
        "source_run_id": decision.get("source_run_id", ""),
        "profile_id": decision.get("profile_id", ""),
        "source_document_id": decision.get("source_document_id", ""),
        "normalized_state": decision.get("normalized_state", ""),
        "selected_action": decision.get("selected_action", ""),
        "decision_status": decision.get("decision_status", ""),
        "reviewer": decision.get("reviewer", ""),
        "reviewed_at": decision.get("reviewed_at", ""),
        "resolution_policy": "requires_human_review",
        "provenance": decision.get("provenance", {}),
    }


def _provenance(record: EvidenceStoreRecord, *, profile_id: str = "") -> dict[str, str]:
    return {
        "record_id": record.record_id,
        "source_run_id": record.source_run_id,
        "record_kind": record.record_kind,
        "profile_id": profile_id,
        "source_document_id": record.effective_source_document_id,
        "payload_hash": record.payload_hash,
    }


def _record_matches_profiles(record: EvidenceStoreRecord, profile_filter: list[str]) -> bool:
    return bool(set(record.profile_ids()).intersection(profile_filter))


def _slug(value: str) -> str:
    text = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in text.split("-") if part) or "record"


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un registro preview di decisioni e conflitti dallo evidence store.")
    parser.add_argument("--evidence-db", required=True)
    parser.add_argument("--evidence-source-run-id", action="append", default=[])
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    try:
        payload = build_review_decision_conflict_register_preview(
            evidence_db=Path(args.evidence_db),
            evidence_source_run_id=args.evidence_source_run_id,
            profile_id=args.profile_id,
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            limit=args.limit,
        )
    except (FileNotFoundError, ValueError, sqlite3.Error) as exc:
        print(str(exc))
        return 2
    print(f"ReviewDecision/Conflict register preview: {args.output_md}")
    print(f"Decisioni: {payload['decision_count']}")
    print(f"Conflitti/ambiguita' aperti: {payload['open_conflict_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
