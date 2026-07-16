from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .evidence_store_records import EvidenceStoreRecord
from .preview_payloads import dict_object, list_items, list_strings, write_json, write_markdown, yaml_value

APPROVED_DECISION_STATUSES = {"approved", "accepted", "reviewed"}
FACT_APPROVAL_ACTIONS = {"confirm", "approve_claim", "approved"}
NON_FACT_ACTIONS = {
    "accept_for_search",
    "pending",
    "request_more_sources",
    "uncertain",
    "reject_false_positive",
    "needs_better_ocr",
    "needs_human_transcription",
}


def build_verified_facts_preview(
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
    source_run_ids = [run_id for run_id in evidence_source_run_id if str(run_id).strip()]
    if not source_run_ids:
        raise ValueError("Specificare almeno un evidence_source_run_id.")
    profile_ids = [value for value in profile_id or [] if str(value).strip()]
    records = _fetch_evidence_records(evidence_db=evidence_db, source_run_ids=source_run_ids)
    facts: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in records:
        store_record = EvidenceStoreRecord.from_row(row)
        if store_record.record_kind != "historical_review_decision":
            continue
        decision = _decision_from_record(store_record)
        if profile_ids and decision.get("profile_id") not in profile_ids:
            continue
        fact, reason = _fact_from_decision(decision)
        if fact is None:
            excluded.append(_excluded_decision(decision, reason=reason))
            continue
        facts.append(fact)
    facts.sort(key=lambda item: (str(item.get("profile_id", "")), str(item.get("field", "")), str(item.get("fact_id", ""))))
    if limit > 0:
        facts = facts[:limit]
    payload: dict[str, Any] = {
        "@type": "VerifiedFactsPreview",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_evidence_db": str(evidence_db),
        "source_run_ids": sorted(source_run_ids),
        "profile_ids": profile_ids,
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "fact_count": len(facts),
        "excluded_decision_count": len(excluded),
        "facts": facts,
        "excluded_decisions": excluded,
        "counts_by_profile": dict(Counter(str(fact.get("profile_id", "")) for fact in facts)),
        "safety_notes": [
            "Preview read-only derivata da decisioni storiche nello evidence store.",
            "Non modifica profili JSON-LD e non scrive verified_facts canonici.",
            "accept_for_search non produce fatti verificati o preview fact.",
        ],
    }
    if output_json is not None:
        write_json(output_json, payload)
    if output_md is not None:
        write_markdown(output_md, render_verified_facts_preview_markdown(payload))
    return payload


def render_verified_facts_preview_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: verified_facts_preview",
        f"review_status: {yaml_value(payload.get('review_status', 'preview-only'))}",
        f"publication_status: {yaml_value(payload.get('publication_status', 'not_publishable_without_editorial_review'))}",
        "preview_only: true",
        "---",
        "",
        "# Verified facts preview",
        "",
        "Preview tecnica derivata da decisioni storiche approvate. Non e' un dataset canonico.",
        "",
        "## Sintesi",
        "",
        f"- Fatti preview: `{payload.get('fact_count', 0)}`",
        f"- Decisioni escluse: `{payload.get('excluded_decision_count', 0)}`",
        f"- Evidence DB: `{payload.get('source_evidence_db', '')}`",
        f"- Run store: `{', '.join(list_strings(payload.get('source_run_ids')))}`",
        "",
        "## Fatti preview",
        "",
    ]
    facts = list_items(payload.get("facts"))
    if not facts:
        lines.append("_Nessun fatto preview generato._")
    for fact in facts:
        lines.extend(
            [
                f"### {fact.get('fact_id', '')}",
                "",
                f"- Profilo: `{fact.get('profile_id', '')}`",
                f"- Campo: `{fact.get('field', '')}`",
                f"- Valore: `{fact.get('value', '')}`",
                f"- Documento: `{fact.get('source_document_id', '')}`",
                f"- Decisione: `{fact.get('source_decision_record_id', '')}`",
                f"- Revisore: `{fact.get('reviewer', '')}`",
                f"- Data review: `{fact.get('reviewed_at', '')}`",
                "",
            ]
        )
        provenance = list_strings(fact.get("provenance"))
        if provenance:
            lines.append("Provenance:")
            lines.extend(f"- {item}" for item in provenance)
            lines.append("")
    lines.extend(["## Decisioni escluse", ""])
    excluded = list_items(payload.get("excluded_decisions"))
    if not excluded:
        lines.append("_Nessuna decisione esclusa._")
    for decision in excluded:
        lines.append(
            f"- `{decision.get('source_decision_record_id', '')}`: {decision.get('reason', '')} "
            f"(`{decision.get('selected_action', '')}` / `{decision.get('decision_status', '')}`)"
        )
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Output automatico preview-only.",
            "- Non modifica profili JSON-LD, claim o dati storici canonici.",
            "- Non applica ProfilePatch.",
            "- `accept_for_search` resta una decisione di ricerca, non un fatto.",
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


def _decision_from_record(store_record: EvidenceStoreRecord) -> dict[str, Any]:
    payload = store_record.scoped_payload(profile_id=store_record.primary_profile_id())
    candidate = dict_object(payload.get("candidate"))
    return {
        "source_decision_record_id": store_record.record_id,
        "source_run_id": store_record.source_run_id,
        "payload_hash": store_record.payload_hash,
        "profile_id": str(payload.get("profile_id", "")).strip(),
        "source_document_id": str(payload.get("source_document_id", "")).strip(),
        "source_item_id": str(payload.get("source_item_id", "")),
        "item_id": str(payload.get("item_id", "")),
        "selected_action": str(payload.get("selected_action", "")).strip(),
        "decision_status": str(payload.get("decision_status", "")).strip(),
        "subject_kind": str(payload.get("subject_kind", "")).strip(),
        "reviewer": str(payload.get("reviewer", "")),
        "reviewed_at": str(payload.get("reviewed_at", "")),
        "field": str(candidate.get("field") or payload.get("field") or "").strip(),
        "value": str(candidate.get("value") or payload.get("value") or "").strip(),
    }


def _fact_from_decision(decision: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    selected_action = str(decision.get("selected_action", "")).strip()
    decision_status = str(decision.get("decision_status", "")).strip()
    if selected_action in NON_FACT_ACTIONS:
        return None, f"azione_non_fattuale:{selected_action}"
    if selected_action not in FACT_APPROVAL_ACTIONS:
        return None, f"azione_non_abilitata:{selected_action or 'missing'}"
    if decision_status not in APPROVED_DECISION_STATUSES:
        return None, f"decision_status_non_approvato:{decision_status or 'missing'}"
    if str(decision.get("subject_kind", "")).strip() == "workflow":
        return None, "decisione_workflow"
    for key in ("profile_id", "source_document_id", "field", "value"):
        if not str(decision.get(key, "")).strip():
            return None, f"campo_mancante:{key}"
    fact_id = _fact_id(decision)
    fact = {
        "@type": "VerifiedFactPreview",
        "fact_id": fact_id,
        "profile_id": decision["profile_id"],
        "field": decision["field"],
        "value": decision["value"],
        "source_document_id": decision["source_document_id"],
        "source_run_id": decision["source_run_id"],
        "source_decision_record_id": decision["source_decision_record_id"],
        "source_item_id": decision["source_item_id"],
        "item_id": decision["item_id"],
        "selected_action": selected_action,
        "decision_status": decision_status,
        "reviewer": decision["reviewer"],
        "reviewed_at": decision["reviewed_at"],
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "provenance": [
            f"historical_review_decision_record_id={decision['source_decision_record_id']}",
            f"source_run_id={decision['source_run_id']}",
            f"source_document_id={decision['source_document_id']}",
            f"payload_hash={decision['payload_hash']}",
        ],
    }
    return fact, ""


def _excluded_decision(decision: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "source_decision_record_id": decision.get("source_decision_record_id", ""),
        "profile_id": decision.get("profile_id", ""),
        "source_document_id": decision.get("source_document_id", ""),
        "selected_action": decision.get("selected_action", ""),
        "decision_status": decision.get("decision_status", ""),
        "reason": reason,
    }


def _fact_id(decision: dict[str, Any]) -> str:
    parts = {
        "profile_id": decision.get("profile_id", ""),
        "field": decision.get("field", ""),
        "value": decision.get("value", ""),
        "source_document_id": decision.get("source_document_id", ""),
        "source_decision_record_id": decision.get("source_decision_record_id", ""),
    }
    digest = hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"verified-fact-preview:{_slug(str(decision.get('profile_id', '')))}:{_slug(str(decision.get('field', '')))}:{digest}"


def _slug(value: str) -> str:
    text = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in text.split("-") if part) or "record"


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera verified_facts preview da decisioni storiche nello evidence store.")
    parser.add_argument("--evidence-db", required=True)
    parser.add_argument("--evidence-source-run-id", action="append", default=[])
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    try:
        preview = build_verified_facts_preview(
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
    print(f"Verified facts preview: {args.output_md}")
    print(f"Fatti preview: {preview['fact_count']}")
    print(f"Decisioni escluse: {preview['excluded_decision_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
