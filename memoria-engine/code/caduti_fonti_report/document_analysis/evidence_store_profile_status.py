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
    write_json,
    write_markdown,
    yaml_value,
)


def build_evidence_store_profile_status(
    *,
    db_path: Path,
    profile_id: str,
    output_json: Path | None = None,
    output_md: Path | None = None,
    limit: int = 50,
    evidence_source_run_id: list[str] | None = None,
) -> dict[str, Any]:
    normalized_profile_id = profile_id.strip()
    if not normalized_profile_id:
        raise ValueError("Specificare un profile_id non vuoto.")
    if not db_path.exists() or not db_path.is_file():
        raise FileNotFoundError(f"Evidence DB non trovato: {db_path}")

    source_run_ids = sorted({str(run_id).strip() for run_id in evidence_source_run_id or [] if str(run_id).strip()})
    records = _fetch_profile_records(
        db_path=db_path,
        profile_id=normalized_profile_id,
        limit=max(limit, 0),
        source_run_ids=source_run_ids,
    )
    source_documents = _source_documents(records)
    document_review_coverage = _document_review_coverage(source_documents)
    candidate_claims = _records_by_kind(records, {"candidate_evidence_claim", "skipped_candidate_claim"})
    skipped_signals = _records_by_kind(records, {"skipped_candidate_claim", "reviewable_document_signal"})
    review_items = _records_by_kind(records, {"review_queue_item"})
    review_decisions = _records_by_kind(records, {"review_decision", "historical_review_decision"})
    profile_evidence_review_state = _profile_evidence_review_state(
        record_count=len(records),
        candidate_claims=candidate_claims,
        skipped_signals=skipped_signals,
        review_items=review_items,
        review_decisions=review_decisions,
    )
    empty_result_diagnostics = (
        _empty_result_diagnostics(
            db_path=db_path,
            profile_id=normalized_profile_id,
            source_run_ids=source_run_ids,
        )
        if not records
        else {}
    )
    payload: dict[str, Any] = {
        "@type": "EvidenceStoreProfileStatus",
        "generated_at": datetime.now(UTC).isoformat(),
        "profile_id": normalized_profile_id,
        "source_database": str(db_path),
        "source_run_ids": source_run_ids,
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_human_review",
        "preview_only": True,
        "record_count": len(records),
        "counts_by_record_kind": dict(Counter(str(record.get("record_kind", "")) for record in records)),
        "counts_by_review_status": dict(Counter(str(record.get("review_status", "")) for record in records)),
        "counts_by_source_run_id": dict(Counter(str(record.get("source_run_id", "")) for record in records)),
        "profile_evidence_review_state": profile_evidence_review_state,
        "document_review_coverage": document_review_coverage,
        "source_documents": source_documents,
        "candidate_claims": candidate_claims,
        "skipped_signals": skipped_signals,
        "review_items": review_items,
        "review_decisions": review_decisions,
        "empty_result_diagnostics": empty_result_diagnostics,
        "next_action": _next_action(
            record_count=len(records),
            candidate_claims=candidate_claims,
            skipped_signals=skipped_signals,
            review_items=review_items,
            review_decisions=review_decisions,
        ),
        "safety_notes": [
            "Vista read-only derivata dallo evidence store append-only.",
            "Non modifica profili JSON-LD, claim o dati storici canonici.",
            "Non applica decisioni e non produce fatti pubblicabili.",
        ],
    }

    if output_json is not None:
        write_json(output_json, payload)
    if output_md is not None:
        write_markdown(output_md, render_evidence_store_profile_status_markdown(payload))
    return payload


def render_evidence_store_profile_status_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: evidence_store_profile_status",
        f"profile_id: {yaml_value(payload.get('profile_id', ''))}",
        f"review_status: {yaml_value(payload.get('review_status', 'preview-only'))}",
        f"publication_status: {yaml_value(payload.get('publication_status', 'not_publishable_without_human_review'))}",
        "preview_only: true",
        "---",
        "",
        "# Evidence Store profile status",
        "",
        "Vista read-only per profilo pilota derivata dallo evidence store append-only.",
        "",
        "## Sintesi",
        "",
        f"- Profilo: `{payload.get('profile_id', '')}`",
        f"- Run store: `{', '.join(list_strings(payload.get('source_run_ids'))) or 'tutte'}`",
        f"- Record importati: `{payload.get('record_count', 0)}`",
        f"- Documenti distinti: `{len(list_items(payload.get('source_documents')))}`",
        f"- Claim candidati: `{len(list_items(payload.get('candidate_claims')))}`",
        f"- Segnali scartati: `{len(list_items(payload.get('skipped_signals')))}`",
        f"- Review items: `{len(list_items(payload.get('review_items')))}`",
        f"- Decisioni: `{len(list_items(payload.get('review_decisions')))}`",
        f"- Stato evidenze profilo: `{payload.get('profile_evidence_review_state', '')}`",
        f"- Prossima azione: {payload.get('next_action', '')}",
        "",
        "## Copertura documenti",
        "",
    ]
    coverage = dict_object(payload.get("document_review_coverage"))
    if coverage:
        lines.extend(
            [
                f"- Documenti con claim candidati: `{coverage.get('documents_with_candidate_claims_count', 0)}`",
                f"- Documenti con segnali scartati/revisionabili: `{coverage.get('documents_with_skipped_signals_count', 0)}`",
                f"- Documenti con review item: `{coverage.get('documents_with_review_items_count', 0)}`",
                f"- Documenti con decisioni: `{coverage.get('documents_with_review_decisions_count', 0)}`",
                f"- Documenti senza decisioni: `{coverage.get('documents_without_review_decisions_count', 0)}`",
                "",
            ]
        )
    documents = list_items(payload.get("source_documents"))
    if documents:
        lines.extend(["| Documento | Stato | Claim | Segnali | Item | Decisioni |", "|---|---|---:|---:|---:|---:|"])
        for document in documents:
            lines.append(
                "| "
                f"`{document.get('source_document_id', '')}` "
                f"| `{document.get('document_review_state', '')}` "
                f"| {document.get('candidate_claim_count', 0)} "
                f"| {document.get('skipped_signal_count', 0)} "
                f"| {document.get('review_item_count', 0)} "
                f"| {document.get('review_decision_count', 0)} |"
            )
    else:
        lines.append("_Nessun documento scopiato sul profilo._")
    lines.extend(
        [
            "",
        "## Record per tipo",
        "",
        ]
    )
    counts_by_kind = dict_object(payload.get("counts_by_record_kind"))
    if counts_by_kind:
        lines.extend(f"- `{kind}`: `{count}`" for kind, count in sorted(counts_by_kind.items()))
    else:
        lines.append("_Nessun record scopiato sul profilo._")
    lines.extend(["", "## Documenti", ""])
    _append_record_list(
        lines,
        list_items(payload.get("source_documents")),
        fields=["source_document_id", "record_count", "record_kinds"],
    )
    lines.extend(["", "## Claim candidati", ""])
    _append_record_list(lines, list_items(payload.get("candidate_claims")), fields=["record_id", "source_document_id", "review_status", "summary"])
    lines.extend(["", "## Segnali scartati", ""])
    _append_record_list(lines, list_items(payload.get("skipped_signals")), fields=["record_id", "source_document_id", "review_status", "summary"])
    lines.extend(["", "## Review items", ""])
    _append_record_list(lines, list_items(payload.get("review_items")), fields=["record_id", "source_document_id", "review_status", "summary"])
    lines.extend(["", "## Decisioni", ""])
    _append_record_list(lines, list_items(payload.get("review_decisions")), fields=["record_id", "source_document_id", "review_status", "summary"])
    diagnostics = dict_object(payload.get("empty_result_diagnostics"))
    if diagnostics:
        lines.extend(["", "## Diagnostica risultato vuoto", ""])
        lines.extend(
            [
                f"- Stato diagnostica: `{diagnostics.get('status', '')}`",
                f"- Record totali nello store: `{diagnostics.get('evidence_store_record_count', 0)}`",
                f"- Record nelle run richieste: `{diagnostics.get('requested_run_record_count', 0)}`",
                f"- Record del profilo in tutte le run: `{diagnostics.get('profile_record_count_all_runs', 0)}`",
                f"- Prossima azione diagnostica: {diagnostics.get('diagnostic_next_action', '')}",
                "",
            ]
        )
        runs_with_profile = list_items(diagnostics.get("runs_with_profile"))
        if runs_with_profile:
            lines.extend(["### Run alternative con record del profilo", ""])
            for item in runs_with_profile:
                lines.append(f"- `{item.get('source_run_id', '')}`: `{item.get('record_count', 0)}` record")
            lines.append("")
        profiles_in_requested_runs = list_items(diagnostics.get("profiles_in_requested_runs"))
        if profiles_in_requested_runs:
            lines.extend(["### Profili presenti nelle run richieste", ""])
            for item in profiles_in_requested_runs:
                lines.append(f"- `{item.get('profile_id', '')}`: `{item.get('record_count', 0)}` record")
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Output automatico preview-only.",
            "- La vista non modifica profili, claim o dati storici canonici.",
            "- Ogni decisione storica resta da validare nel workflow umano dedicato.",
            "",
        ]
    )
    return "\n".join(lines)


def _fetch_profile_records(*, db_path: Path, profile_id: str, limit: int, source_run_ids: list[str]) -> list[dict[str, Any]]:
    records = _fetch_records(db_path=db_path, source_run_ids=source_run_ids)
    filtered = [record for record in records if _record_matches_profile(record, profile_id=profile_id)]
    if limit > 0:
        return filtered[:limit]
    return filtered


def _fetch_records(*, db_path: Path, source_run_ids: list[str]) -> list[dict[str, Any]]:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        if source_run_ids:
            placeholders = ",".join("?" for _ in source_run_ids)
            rows = list(
                connection.execute(
                    f"""
                    SELECT record_id, import_batch_id, source_run_id, record_kind,
                           subject_id, source_document_id, review_status, payload_hash, payload_json
                    FROM evidence_records
                    WHERE source_run_id IN ({placeholders})
                    ORDER BY source_run_id ASC, record_kind ASC, record_id ASC
                    """,
                    tuple(source_run_ids),
                )
            )
        else:
            rows = list(
                connection.execute(
                    """
                    SELECT record_id, import_batch_id, source_run_id, record_kind,
                           subject_id, source_document_id, review_status, payload_hash, payload_json
                    FROM evidence_records
                    ORDER BY source_run_id ASC, record_kind ASC, record_id ASC
                    """
                )
            )
    return [_record_from_row(row) for row in rows]


def _record_from_row(row: sqlite3.Row) -> dict[str, Any]:
    store_record = EvidenceStoreRecord.from_row(dict(row))
    payload = store_record.payload
    return {
        "record_id": store_record.record_id,
        "import_batch_id": str(row["import_batch_id"] or ""),
        "source_run_id": store_record.source_run_id,
        "record_kind": store_record.record_kind,
        "subject_id": store_record.subject_id,
        "source_document_id": store_record.effective_source_document_id,
        "review_status": store_record.review_status or str(payload.get("review_status", "")),
        "payload_hash": store_record.payload_hash,
        "payload": payload,
        "summary": _record_summary(payload),
    }


def _record_matches_profile(record: dict[str, Any], *, profile_id: str) -> bool:
    return profile_id in _record_profile_ids(record)


def _record_profile_ids(record: dict[str, Any]) -> set[str]:
    store_record = EvidenceStoreRecord(
        record_id=str(record.get("record_id", "")),
        source_run_id=str(record.get("source_run_id", "")),
        record_kind=str(record.get("record_kind", "")),
        subject_id=str(record.get("subject_id", "")).strip(),
        source_document_id=str(record.get("source_document_id", "")).strip(),
        review_status=str(record.get("review_status", "")),
        payload_hash=str(record.get("payload_hash", "")),
        payload=dict_object(record.get("payload")),
    )
    candidates = set(store_record.profile_ids())
    payload = store_record.payload
    candidates.update(list_strings(payload.get("accepted_candidate_profile_ids")))
    return {value for value in candidates if value}


def _empty_result_diagnostics(*, db_path: Path, profile_id: str, source_run_ids: list[str]) -> dict[str, Any]:
    all_records = _fetch_records(db_path=db_path, source_run_ids=[])
    requested_records = _fetch_records(db_path=db_path, source_run_ids=source_run_ids) if source_run_ids else all_records
    profile_records = [record for record in all_records if _record_matches_profile(record, profile_id=profile_id)]
    profile_runs = Counter(str(record.get("source_run_id", "")) for record in profile_records if str(record.get("source_run_id", "")).strip())
    profiles_in_requested_runs = Counter(
        profile
        for record in requested_records
        for profile in _record_profile_ids(record)
    )

    if not all_records:
        status = "store_empty"
        next_action = "Importare una run nello Evidence Store prima di usare profile-status."
    elif profile_records and source_run_ids:
        status = "profile_available_in_other_runs"
        next_action = "Rigenerare profile-status su una delle run alternative che contiene il profilo."
    elif source_run_ids and not requested_records:
        status = "requested_runs_without_records"
        next_action = "Verificare la sessione consolidate attiva o selezionare una run importata nello store."
    elif requested_records:
        status = "requested_runs_have_other_profiles"
        next_action = "Verificare ProfileId oppure scegliere uno dei profili presenti nella run richiesta."
    else:
        status = "profile_not_found_in_store"
        next_action = "Importare una run utile per questo profilo nello Evidence Store."

    return {
        "status": status,
        "profile_id": profile_id,
        "requested_source_run_ids": source_run_ids,
        "evidence_store_record_count": len(all_records),
        "requested_run_record_count": len(requested_records),
        "profile_record_count_all_runs": len(profile_records),
        "runs_with_profile": _counter_items(profile_runs),
        "profiles_in_requested_runs": _counter_items(profiles_in_requested_runs, key_name="profile_id"),
        "diagnostic_next_action": next_action,
    }


def _counter_items(counter: Counter[str], *, key_name: str = "source_run_id", limit: int = 10) -> list[dict[str, Any]]:
    return [
        {key_name: key, "record_count": count}
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
        if key
    ]


def _source_documents(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        source_document_id = str(record.get("source_document_id", "")).strip()
        if source_document_id:
            grouped.setdefault(source_document_id, []).append(record)
    documents: list[dict[str, Any]] = []
    for source_document_id, document_records in sorted(grouped.items()):
        candidate_claim_records = _records_with_kinds(document_records, {"candidate_evidence_claim", "skipped_candidate_claim"})
        skipped_signal_records = _records_with_kinds(document_records, {"skipped_candidate_claim", "reviewable_document_signal"})
        review_item_records = _records_with_kinds(document_records, {"review_queue_item"})
        review_decision_records = _records_with_kinds(document_records, {"review_decision", "historical_review_decision"})
        documents.append(
            {
                "source_document_id": source_document_id,
                "record_count": len(document_records),
                "record_kinds": sorted({str(record.get("record_kind", "")) for record in document_records if record.get("record_kind")}),
                "review_statuses": sorted({str(record.get("review_status", "")) for record in document_records if record.get("review_status")}),
                "candidate_claim_count": len(candidate_claim_records),
                "skipped_signal_count": len(skipped_signal_records),
                "review_item_count": len(review_item_records),
                "review_decision_count": len(review_decision_records),
                "candidate_claim_record_ids": _record_ids(candidate_claim_records),
                "skipped_signal_record_ids": _record_ids(skipped_signal_records),
                "review_item_record_ids": _record_ids(review_item_records),
                "review_decision_record_ids": _record_ids(review_decision_records),
                "document_review_state": _document_review_state(
                    candidate_claim_records=candidate_claim_records,
                    skipped_signal_records=skipped_signal_records,
                    review_item_records=review_item_records,
                    review_decision_records=review_decision_records,
                ),
            }
        )
    return documents


def _document_review_coverage(source_documents: list[dict[str, Any]]) -> dict[str, Any]:
    state_counts = Counter(str(document.get("document_review_state", "")) for document in source_documents)
    return {
        "document_count": len(source_documents),
        "documents_with_candidate_claims_count": sum(1 for document in source_documents if int(document.get("candidate_claim_count", 0)) > 0),
        "documents_with_skipped_signals_count": sum(1 for document in source_documents if int(document.get("skipped_signal_count", 0)) > 0),
        "documents_with_review_items_count": sum(1 for document in source_documents if int(document.get("review_item_count", 0)) > 0),
        "documents_with_review_decisions_count": sum(1 for document in source_documents if int(document.get("review_decision_count", 0)) > 0),
        "documents_without_review_decisions_count": sum(1 for document in source_documents if int(document.get("review_decision_count", 0)) == 0),
        "counts_by_document_review_state": dict(sorted(state_counts.items())),
    }


def _records_with_kinds(records: list[dict[str, Any]], kinds: set[str]) -> list[dict[str, Any]]:
    return [record for record in records if str(record.get("record_kind", "")) in kinds]


def _record_ids(records: list[dict[str, Any]]) -> list[str]:
    return sorted(str(record.get("record_id", "")) for record in records if str(record.get("record_id", "")).strip())


def _document_review_state(
    *,
    candidate_claim_records: list[dict[str, Any]],
    skipped_signal_records: list[dict[str, Any]],
    review_item_records: list[dict[str, Any]],
    review_decision_records: list[dict[str, Any]],
) -> str:
    if review_decision_records:
        return "decision_available"
    if review_item_records:
        return "pending_review_item"
    if candidate_claim_records or skipped_signal_records:
        return "needs_review_item"
    return "evidence_only"


def _records_by_kind(records: list[dict[str, Any]], kinds: set[str]) -> list[dict[str, Any]]:
    selected = [
        _public_record(record)
        for record in records
        if str(record.get("record_kind", "")) in kinds
    ]
    return selected


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(record.get("record_id", "")),
        "source_run_id": str(record.get("source_run_id", "")),
        "record_kind": str(record.get("record_kind", "")),
        "subject_id": str(record.get("subject_id", "")),
        "source_document_id": str(record.get("source_document_id", "")),
        "review_status": str(record.get("review_status", "")),
        "payload_hash": str(record.get("payload_hash", "")),
        "summary": str(record.get("summary", "")),
    }


def _next_action(
    *,
    record_count: int,
    candidate_claims: list[dict[str, Any]],
    skipped_signals: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
    review_decisions: list[dict[str, Any]],
) -> str:
    if _has_approved_decision(review_decisions):
        return "Valutare una preview dei fatti approvati in un task separato."
    if any(str(item.get("review_status", "")) in {"pending", "unreviewed", "draft"} for item in review_items):
        return "Revisionare gli item storici pendenti per questo profilo."
    if candidate_claims or skipped_signals:
        return "Generare o aggiornare target storici revisionabili dai claim candidati."
    if record_count > 0:
        return "Arricchire il collegamento profilo-documento prima della revisione storica."
    return "Importare una run utile nello evidence store per questo profilo."


def _profile_evidence_review_state(
    *,
    record_count: int,
    candidate_claims: list[dict[str, Any]],
    skipped_signals: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
    review_decisions: list[dict[str, Any]],
) -> str:
    if _has_approved_decision(review_decisions):
        return "approved_decision_available"
    if any(str(item.get("review_status", "")) in {"pending", "unreviewed", "draft"} for item in review_items):
        return "pending_historical_review"
    if candidate_claims or skipped_signals:
        return "needs_historical_review_targets"
    if record_count > 0:
        return "linked_evidence_without_review_items"
    return "no_evidence_records"


def _has_approved_decision(review_decisions: list[dict[str, Any]]) -> bool:
    approved_statuses = {"approved", "reviewed", "accepted"}
    approved_actions = {"approve", "approved", "confirm", "accepted", "accept"}
    for decision in review_decisions:
        if str(decision.get("review_status", "")).strip() in approved_statuses:
            return True
        summary = str(decision.get("summary", "")).lower()
        if any(f"action={action}" in summary or f"selected_action={action}" in summary for action in approved_actions):
            return True
    return False


def _record_summary(payload: dict[str, Any]) -> str:
    parts = []
    for key in ("@type", "item_id", "decision_id", "field", "value", "reason", "selected_action", "question"):
        value = str(payload.get(key, "")).strip()
        if value:
            parts.append(f"{key}={value}")
    return " | ".join(parts)


def _append_record_list(lines: list[str], records: list[dict[str, Any]], *, fields: list[str]) -> None:
    if not records:
        lines.append("_Nessun elemento._")
        return
    for record in records:
        label = str(record.get(fields[0], "")).strip() if fields else ""
        lines.append(f"### {label or 'record'}")
        lines.append("")
        for field in fields:
            value = record.get(field, "")
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            lines.append(f"- {field}: `{value}`")
        lines.append("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Costruisce una vista read-only dello evidence store per profilo.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--evidence-source-run-id", action="append", default=[])
    args = parser.parse_args()

    try:
        status = build_evidence_store_profile_status(
            db_path=Path(args.db),
            profile_id=args.profile_id,
            output_json=Path(args.output_json) if args.output_json else None,
            output_md=Path(args.output_md) if args.output_md else None,
            limit=args.limit,
            evidence_source_run_id=args.evidence_source_run_id,
        )
    except (FileNotFoundError, ValueError, sqlite3.Error) as exc:
        print(str(exc))
        return 2

    if args.output_md:
        print(f"Evidence Store profile status: {args.output_md}")
    if args.output_json:
        print(f"Evidence Store profile status JSON: {args.output_json}")
    print(f"Record profilo: {status['record_count']}")
    print(f"Prossima azione: {status['next_action']}")
    diagnostics = dict_object(status.get("empty_result_diagnostics"))
    if diagnostics:
        print(f"Diagnostica vuoto: {diagnostics['status']} - {diagnostics['diagnostic_next_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
