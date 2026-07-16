from __future__ import annotations

import argparse
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from .evidence_store_records import EvidenceStoreRecord
from .preview_payloads import (
    dict_object,
    list_items,
    list_strings,
    load_json_object,
    unique_non_empty,
    write_json,
    write_markdown,
    yaml_value,
)

DECISION_RECORD_KINDS = {"historical_review_decision", "review_decision"}


def build_dataset_export_preview(
    *,
    evidence_db: Path,
    evidence_source_run_id: list[str],
    output_json: Path | None = None,
    output_md: Path | None = None,
    profile_id: list[str] | None = None,
    verified_facts_preview_json: Path | None = None,
    profile_patch_preview_json: Path | None = None,
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
    if profile_filter:
        records = [record for record in records if _record_matches_profiles(record, profile_filter)]
    if limit > 0:
        records = records[:limit]

    verified_preview = _verified_facts_preview_summary(
        verified_facts_preview_json,
        profile_filter=profile_filter,
    )
    profile_patch_preview = _profile_patch_preview_summary(
        profile_patch_preview_json,
        profile_filter=profile_filter,
    )
    generated_at = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "@type": "DatasetExportPreview",
        "generated_at": generated_at,
        "source_evidence_db": str(evidence_db),
        "source_run_ids": sorted(source_run_ids),
        "profile_ids": profile_filter,
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "record_count": len(records),
        "persons": _persons(records),
        "source_documents": _source_documents(records),
        "review_decisions": _review_decisions(records),
        "verified_facts_preview": verified_preview,
        "profile_patch_preview": profile_patch_preview,
        "provenance": {
            "evidence_record_count": len(records),
            "source_run_ids": sorted(source_run_ids),
            "record_ids": [record.record_id for record in records],
            "payload_hashes": sorted({record.payload_hash for record in records if record.payload_hash}),
        },
        "safety_notes": [
            "Export preview-only read-only da evidence store e preview gia' generate.",
            "Non crea verified_facts canonici.",
            "Non modifica profili JSON-LD.",
            "Non applica ProfilePatch e non pubblica dataset canonici.",
        ],
    }
    if output_json is not None:
        write_json(output_json, payload)
    if output_md is not None:
        write_markdown(output_md, render_dataset_export_preview_markdown(payload))
    return payload


def render_dataset_export_preview_markdown(payload: dict[str, Any]) -> str:
    verified = dict_object(payload.get("verified_facts_preview"))
    patch = dict_object(payload.get("profile_patch_preview"))
    lines = [
        "---",
        "type: dataset_export_preview",
        f"review_status: {yaml_value(payload.get('review_status', 'preview-only'))}",
        f"publication_status: {yaml_value(payload.get('publication_status', 'not_publishable_without_editorial_review'))}",
        "preview_only: true",
        "---",
        "",
        "# Dataset export preview",
        "",
        "Fotografia tecnica preview-only. Non e' un dataset canonico e non e' pubblicabile senza revisione editoriale.",
        "",
        "## Sintesi",
        "",
        f"- Record evidence: `{payload.get('record_count', 0)}`",
        f"- Persone: `{len(list_items(payload.get('persons')))}`",
        f"- Documenti sorgente: `{len(list_items(payload.get('source_documents')))}`",
        f"- Decisioni review: `{len(list_items(payload.get('review_decisions')))}`",
        f"- Fatti preview: `{verified.get('fact_count', 0)}`",
        f"- ProfilePatch preview: `{patch.get('patch_count', 0)}`",
        f"- Run store: `{', '.join(list_strings(payload.get('source_run_ids')))}`",
        "",
        "## Persone",
        "",
    ]
    persons = list_items(payload.get("persons"))
    if not persons:
        lines.extend(["_Nessuna persona nell'export._", ""])
    for person in persons:
        lines.extend(
            [
                f"### {person.get('profile_id', '')}",
                "",
                f"- Record: `{person.get('record_count', 0)}`",
                f"- Documenti: `{', '.join(list_strings(person.get('source_document_ids')))}`",
                f"- Tipi record: `{', '.join(list_strings(person.get('record_kinds')))}`",
                "",
            ]
        )
    lines.extend(["## Documenti sorgente", ""])
    documents = list_items(payload.get("source_documents"))
    if not documents:
        lines.extend(["_Nessun documento sorgente nell'export._", ""])
    for document in documents:
        lines.append(
            f"- `{document.get('source_document_id', '')}`: "
            f"{document.get('record_count', 0)} record, profili `{', '.join(list_strings(document.get('profile_ids')))}`"
        )
    lines.extend(["", "## Decisioni review", ""])
    decisions = list_items(payload.get("review_decisions"))
    if not decisions:
        lines.extend(["_Nessuna decisione review nella run filtrata._", ""])
    for decision in decisions:
        lines.append(
            f"- `{decision.get('record_id', '')}` "
            f"profilo `{decision.get('profile_id', '')}` "
            f"azione `{decision.get('selected_action', '')}` "
            f"status `{decision.get('decision_status', '')}`"
        )
    lines.extend(
        [
            "",
            "## Preview collegate",
            "",
            f"- Verified facts preview: `{verified.get('status', 'not_provided')}` "
            f"({verified.get('fact_count', 0)} fatti)",
            f"- ProfilePatch preview: `{patch.get('status', 'not_provided')}` "
            f"({patch.get('patch_count', 0)} patch, {patch.get('operation_count', 0)} operazioni)",
            "",
            "## Vincoli",
            "",
            "- Output automatico preview-only.",
            "- Non scrive nello evidence store.",
            "- Non crea fatti canonici.",
            "- Non modifica profili JSON-LD.",
            "- Non applica ProfilePatch.",
            "- Non e' pubblicabile senza revisione editoriale.",
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


def _persons(records: list[EvidenceStoreRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[EvidenceStoreRecord]] = defaultdict(list)
    for record in records:
        for profile in record.profile_ids():
            grouped[profile].append(record)
    persons = []
    for profile, profile_records in grouped.items():
        persons.append(
            {
                "profile_id": profile,
                "record_count": len(profile_records),
                "source_document_ids": sorted(
                    {record.effective_source_document_id for record in profile_records if record.effective_source_document_id}
                ),
                "record_kinds": sorted({record.record_kind for record in profile_records if record.record_kind}),
                "review_statuses": dict(Counter(record.review_status for record in profile_records if record.review_status)),
                "provenance": [_provenance(record, profile_id=profile) for record in profile_records],
            }
        )
    return sorted(persons, key=lambda item: str(item.get("profile_id", "")))


def _source_documents(records: list[EvidenceStoreRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[EvidenceStoreRecord]] = defaultdict(list)
    for record in records:
        document_id = record.effective_source_document_id
        if document_id:
            grouped[document_id].append(record)
    documents = []
    for document_id, document_records in grouped.items():
        profile_ids = sorted({profile for record in document_records for profile in record.profile_ids()})
        documents.append(
            {
                "source_document_id": document_id,
                "record_count": len(document_records),
                "profile_ids": profile_ids,
                "record_kinds": sorted({record.record_kind for record in document_records if record.record_kind}),
                "review_statuses": dict(Counter(record.review_status for record in document_records if record.review_status)),
                "provenance": [_provenance(record, profile_id=record.primary_profile_id()) for record in document_records],
            }
        )
    return sorted(documents, key=lambda item: str(item.get("source_document_id", "")))


def _review_decisions(records: list[EvidenceStoreRecord]) -> list[dict[str, Any]]:
    decisions = []
    for record in records:
        if record.record_kind not in DECISION_RECORD_KINDS:
            continue
        payload = record.scoped_payload(profile_id=record.primary_profile_id())
        profile = str(payload.get("profile_id", "")).strip()
        decisions.append(
            {
                "record_id": record.record_id,
                "source_run_id": record.source_run_id,
                "record_kind": record.record_kind,
                "profile_id": profile,
                "source_document_id": str(payload.get("source_document_id", "")).strip(),
                "source_item_id": str(payload.get("source_item_id", "")).strip(),
                "item_id": str(payload.get("item_id", "")).strip(),
                "review_status": record.review_status,
                "selected_action": str(payload.get("selected_action", "")).strip(),
                "decision_status": str(payload.get("decision_status", "")).strip(),
                "reviewer": str(payload.get("reviewer", "")).strip(),
                "reviewed_at": str(payload.get("reviewed_at", "")).strip(),
                "payload_hash": record.payload_hash,
                "provenance": _provenance(record, profile_id=profile),
            }
        )
    return sorted(decisions, key=lambda item: (str(item.get("profile_id", "")), str(item.get("record_id", ""))))


def _verified_facts_preview_summary(path: Path | None, *, profile_filter: list[str]) -> dict[str, Any]:
    if path is None:
        return {"status": "not_provided", "enabled": False, "fact_count": 0, "facts": []}
    if not path.is_file():
        raise FileNotFoundError(f"Verified facts preview non trovato: {path}")
    payload = load_json_object(path)
    facts = [
        fact
        for fact in list_items(payload.get("facts"))
        if str(fact.get("@type", "")) == "VerifiedFactPreview"
        and (not profile_filter or str(fact.get("profile_id", "")).strip() in profile_filter)
    ]
    return {
        "status": "available" if payload.get("@type") == "VerifiedFactsPreview" else "ignored",
        "enabled": True,
        "source_path": str(path),
        "review_status": payload.get("review_status", ""),
        "publication_status": payload.get("publication_status", ""),
        "fact_count": len(facts),
        "excluded_decision_count": int(payload.get("excluded_decision_count", 0) or 0),
        "facts": [_fact_summary(fact) for fact in facts],
    }


def _profile_patch_preview_summary(path: Path | None, *, profile_filter: list[str]) -> dict[str, Any]:
    if path is None:
        return {"status": "not_provided", "enabled": False, "patch_count": 0, "operation_count": 0, "profile_patches": []}
    if not path.is_file():
        raise FileNotFoundError(f"ProfilePatch preview non trovato: {path}")
    payload = load_json_object(path)
    patches = [
        patch
        for patch in list_items(payload.get("profile_patches"))
        if not profile_filter or str(patch.get("profile_id", "")).strip() in profile_filter
    ]
    return {
        "status": "available" if payload.get("@type") == "ProfilePatchPreviewBatch" else "ignored",
        "enabled": True,
        "source_path": str(path),
        "review_status": payload.get("review_status", ""),
        "publication_status": payload.get("publication_status", ""),
        "apply_policy": payload.get("apply_policy", ""),
        "patch_count": len(patches),
        "operation_count": sum(len(list_items(patch.get("operations"))) for patch in patches),
        "profile_patches": [_patch_summary(patch) for patch in patches],
    }


def _fact_summary(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        "@type": fact.get("@type", ""),
        "fact_id": fact.get("fact_id", ""),
        "profile_id": fact.get("profile_id", ""),
        "field": fact.get("field", ""),
        "value": fact.get("value", ""),
        "source_document_id": fact.get("source_document_id", ""),
        "source_run_id": fact.get("source_run_id", ""),
        "source_decision_record_id": fact.get("source_decision_record_id", ""),
        "reviewer": fact.get("reviewer", ""),
        "reviewed_at": fact.get("reviewed_at", ""),
        "provenance": list_strings(fact.get("provenance")),
    }


def _patch_summary(patch: dict[str, Any]) -> dict[str, Any]:
    operations = list_items(patch.get("operations"))
    return {
        "@type": patch.get("@type", ""),
        "profile_id": patch.get("profile_id", ""),
        "review_status": patch.get("review_status", ""),
        "publication_status": patch.get("publication_status", ""),
        "apply_policy": patch.get("apply_policy", ""),
        "operation_count": len(operations),
        "operations": [
            {
                "operation_id": operation.get("operation_id", ""),
                "op": operation.get("op", ""),
                "path": operation.get("path", ""),
                "value": operation.get("value", ""),
                "verified_fact_preview_id": operation.get("verified_fact_preview_id", ""),
                "source_document_id": operation.get("source_document_id", ""),
                "source_run_id": operation.get("source_run_id", ""),
                "source_decision_record_id": operation.get("source_decision_record_id", ""),
                "provenance": list_strings(operation.get("provenance")),
            }
            for operation in operations
        ],
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

def main() -> int:
    parser = argparse.ArgumentParser(description="Esporta una preview read-only del dataset minimo.")
    parser.add_argument("--evidence-db", required=True)
    parser.add_argument("--evidence-source-run-id", action="append", default=[])
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--verified-facts-preview-json", default="")
    parser.add_argument("--profile-patch-preview-json", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    verified_path = Path(args.verified_facts_preview_json) if str(args.verified_facts_preview_json).strip() else None
    patch_path = Path(args.profile_patch_preview_json) if str(args.profile_patch_preview_json).strip() else None
    try:
        payload = build_dataset_export_preview(
            evidence_db=Path(args.evidence_db),
            evidence_source_run_id=args.evidence_source_run_id,
            profile_id=args.profile_id,
            verified_facts_preview_json=verified_path,
            profile_patch_preview_json=patch_path,
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            limit=args.limit,
        )
    except (FileNotFoundError, ValueError, JSONDecodeError, sqlite3.Error) as exc:
        print(str(exc))
        return 2
    print(f"Dataset export preview: {args.output_md}")
    print(f"Record evidence: {payload['record_count']}")
    print(f"Persone: {len(payload['persons'])}")
    print(f"Decisioni review: {len(payload['review_decisions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
