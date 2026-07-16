from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caduti_fonti_report.sqlite_store import SQLiteEvidenceStore

IMPORT_SPECS = (
    ("document_analysis/candidate_document_person_links.json", "candidate_document_person_link", ("candidate_document_person_links",)),
    ("document_analysis/extracted_entities.json", "extracted_entity", ("extracted_entities",)),
    ("document_analysis/candidate_evidence_claims.json", "candidate_evidence_claim", ("candidate_evidence_claims", "claims")),
    ("document_analysis/candidate_evidence_claims.json", "skipped_candidate_claim", ("skipped_entities", "skipped_claims")),
    ("historian_review/review_queue.json", "review_queue_item", ("items", "review_items")),
    ("historian_review/review_decisions_summary.json", "review_decision", ("decisions", "provided_decisions")),
)


def import_document_analysis_evidence_to_db(
    *,
    run_dir: Path,
    db_path: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    source_run_id = _source_run_id(run_dir)
    records = _collect_records(run_dir=run_dir, source_run_id=source_run_id)
    records_hash = _hash_payload([record["record_id"] for record in records])
    imported_at = datetime.now(UTC).isoformat()
    import_batch_id = f"evidence-import:{source_run_id}:{records_hash[:16]}"
    for record in records:
        record["import_batch_id"] = import_batch_id

    batch = {
        "@type": "EvidenceImportBatch",
        "import_batch_id": import_batch_id,
        "source_run_id": source_run_id,
        "source_run_dir": str(run_dir),
        "imported_at": imported_at,
        "record_count": len(records),
        "payload_hash": records_hash,
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "note": "Append-only import di candidati e segnali di review; non produce verified_facts.",
    }

    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    store.insert_evidence_import_batch(batch)
    inserted_count = 0
    for record in records:
        if store.insert_evidence_record(record):
            inserted_count += 1

    result = {
        "@type": "DocumentAnalysisEvidenceStoreImport",
        "generated_at": imported_at,
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "db": str(db_path),
        "run_dir": str(run_dir),
        "source_run_id": source_run_id,
        "import_batch_id": import_batch_id,
        "record_count": len(records),
        "inserted_record_count": inserted_count,
        "already_present_record_count": len(records) - inserted_count,
        "record_kind_counts": dict(sorted(Counter(record["record_kind"] for record in records).items())),
        "coverage": _coverage(records),
        "warnings": _warnings(run_dir=run_dir, records=records),
        "note": "Nessun record importato e' un fatto storico verificato.",
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_import_markdown(result), encoding="utf-8")
    return result


def render_import_markdown(result: dict[str, Any]) -> str:
    lines = [
        "---",
        'type: "document_analysis_evidence_store_import"',
        f'review_status: "{result.get("review_status", "unreviewed")}"',
        f'publication_status: "{result.get("publication_status", "not_publishable_without_human_review")}"',
        "---",
        "",
        "# Evidence store import",
        "",
        "Import append-only di candidati e segnali di review nel database generale.",
        "",
        "## Sintesi",
        "",
        f"- Database: `{result.get('db', '')}`",
        f"- Run sorgente: `{result.get('source_run_id', '')}`",
        f"- Cartella run: `{result.get('run_dir', '')}`",
        f"- Batch: `{result.get('import_batch_id', '')}`",
        f"- Record letti: `{result.get('record_count', 0)}`",
        f"- Record inseriti: `{result.get('inserted_record_count', 0)}`",
        f"- Record gia' presenti: `{result.get('already_present_record_count', 0)}`",
        "",
        "## Tipi record",
        "",
    ]
    counts = result.get("record_kind_counts")
    if isinstance(counts, dict) and counts:
        for kind, count in counts.items():
            lines.append(f"- `{kind}`: `{count}`")
    else:
        lines.append("- Nessun record importato.")
    coverage = result.get("coverage")
    if isinstance(coverage, dict):
        lines.extend(
            [
                "",
                "## Copertura scoping",
                "",
                f"- Record con soggetto: `{coverage.get('with_subject_count', 0)}`",
                f"- Record con documento: `{coverage.get('with_source_document_count', 0)}`",
                f"- Record workflow non scopiati: `{coverage.get('workflow_unscoped_count', 0)}`",
                f"- Record senza soggetto ne' documento: `{coverage.get('unscoped_without_document_count', 0)}`",
            ]
        )
    warnings = result.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.extend(["", "## Warning", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Import append-only: un reimport identico non duplica record.",
            "- I record restano candidati `unreviewed` o `pending`.",
            "- Nessun claim candidato diventa `EvidenceClaim` validato.",
            "- Nessun `verified_facts` viene creato o modificato.",
            "",
        ]
    )
    return "\n".join(lines)


def _collect_records(*, run_dir: Path, source_run_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    direct_kinds = set()
    for relative_path, record_kind, list_keys in IMPORT_SPECS:
        path = run_dir / relative_path
        payload = _load_json_object(path)
        if not payload:
            continue
        for item in _extract_items(payload, list_keys):
            effective_record_kind = _record_kind_for_item(record_kind=record_kind, item=item)
            record = _record_from_item(
                item=item,
                source_run_id=source_run_id,
                record_kind=effective_record_kind,
                source_file=path,
            )
            if record is not None:
                records.append(record)
                direct_kinds.add(effective_record_kind)
    summary_path = run_dir / "document_analysis" / "mvp_pilot_summary.json"
    summary = _load_json_object(summary_path)
    if summary:
        if "candidate_document_person_link" not in direct_kinds:
            for item in _extract_items(summary, ("candidate_document_person_links",)):
                record = _record_from_item(item=item, source_run_id=source_run_id, record_kind="candidate_document_person_link", source_file=summary_path)
                if record is not None:
                    records.append(record)
        if "candidate_evidence_claim" not in direct_kinds:
            for item in _extract_items(summary, ("candidate_evidence_claims",)):
                record = _record_from_item(item=item, source_run_id=source_run_id, record_kind="candidate_evidence_claim", source_file=summary_path)
                if record is not None:
                    records.append(record)
        for group in _extract_items(summary, ("reviewable_document_signals",)):
            for item in _extract_items(group, ("signals",)):
                record = _record_from_item(item=item, source_run_id=source_run_id, record_kind="reviewable_document_signal", source_file=summary_path)
                if record is not None:
                    records.append(record)
    records.sort(key=lambda item: (item["record_kind"], item["record_id"]))
    return records


def _record_from_item(
    *,
    item: dict[str, Any],
    source_run_id: str,
    record_kind: str,
    source_file: Path,
) -> dict[str, Any] | None:
    payload = dict(item)
    payload["@type"] = str(payload.get("@type") or _type_for_kind(record_kind))
    payload["source_run_id"] = source_run_id
    payload["source_import_file"] = str(source_file)
    payload.setdefault("review_status", _default_review_status(record_kind))
    payload.setdefault("publication_status", "not_publishable_without_human_review")
    payload_hash = _hash_payload(payload)
    source_id = _source_record_id(payload)
    record_id = f"evidence-record:{source_run_id}:{record_kind}:{_slug(source_id)}:{payload_hash[:16]}"
    return {
        "@type": "EvidenceStoreRecord",
        "record_id": record_id,
        "source_run_id": source_run_id,
        "record_kind": record_kind,
        "source_record_id": source_id,
        "subject_id": _subject_id(payload),
        "source_document_id": _source_document_id(payload),
        "review_status": str(payload.get("review_status", "")),
        "publication_status": str(payload.get("publication_status", "")),
        "payload_hash": payload_hash,
        "payload": payload,
    }


def _record_kind_for_item(*, record_kind: str, item: dict[str, Any]) -> str:
    if record_kind == "review_decision" and _is_historical_review_decision(item):
        return "historical_review_decision"
    return record_kind


def _is_historical_review_decision(item: dict[str, Any]) -> bool:
    profile_id = str(item.get("profile_id", "")).strip()
    source_document_id = str(item.get("source_document_id", "")).strip()
    subject_kind = str(item.get("subject_kind", "")).strip()
    selected_action = str(item.get("selected_action", "")).strip()
    decision_status = str(item.get("decision_status", "")).strip()
    return (
        bool(profile_id)
        and bool(source_document_id)
        and subject_kind != "workflow"
        and bool(selected_action)
        and selected_action != "pending"
        and decision_status in {"accepted", "reviewed", "approved"}
    )


def _source_run_id(run_dir: Path) -> str:
    manifest = _load_json_object(run_dir / "manifest.json")
    for key in ("run_id", "pipeline_run_id"):
        value = str(manifest.get(key, "")).strip()
        if value:
            return value
    return run_dir.name


def _extract_items(payload: dict[str, Any], list_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    for key in list_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if _looks_like_record(payload):
        return [payload]
    return []


def _looks_like_record(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("@id", "id", "item_id", "claim_id", "source_document_id"))


def _source_record_id(payload: dict[str, Any]) -> str:
    for key in ("@id", "id", "item_id", "claim_id", "link_id", "entity_id", "decision_id"):
        value = str(payload.get(key, "")).strip()
        if value:
            return value
    return _hash_payload(payload)[:24]


def _subject_id(payload: dict[str, Any]) -> str:
    for key in ("profile_id", "person_id", "person_candidate_id", "subject_id", "candidate_profile_id"):
        value = str(payload.get(key, "")).strip()
        if value:
            return value
    for key in ("candidate_profile_ids", "profile_ids", "person_ids", "subject_ids"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                item_text = str(item).strip()
                if item_text:
                    return item_text
    return ""


def _source_document_id(payload: dict[str, Any]) -> str:
    value = payload.get("source_document_id")
    if isinstance(value, str):
        return value
    value = payload.get("source_document_ids")
    if isinstance(value, list) and value:
        return str(value[0])
    return ""


def _default_review_status(record_kind: str) -> str:
    if record_kind in {"review_decision", "historical_review_decision"}:
        return "pending"
    return "unreviewed"


def _type_for_kind(record_kind: str) -> str:
    return {
        "candidate_document_person_link": "CandidateDocumentPersonLink",
        "extracted_entity": "ExtractedEntity",
        "candidate_evidence_claim": "CandidateEvidenceClaim",
        "skipped_candidate_claim": "SkippedCandidateClaim",
        "review_queue_item": "MvpReviewQueueItem",
        "review_decision": "MvpReviewDecision",
        "historical_review_decision": "HistoricalReviewDecision",
        "reviewable_document_signal": "ReviewableDocumentSignal",
    }.get(record_kind, "EvidenceStoreRecordPayload")


def _warnings(*, run_dir: Path, records: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if not records:
        warnings.append("Nessun record importabile trovato nella run.")
    missing_files = [relative_path for relative_path, _, _ in IMPORT_SPECS if not (run_dir / relative_path).is_file()]
    if missing_files:
        warnings.append("Alcuni output non sono presenti: " + ", ".join(sorted(set(missing_files))))
    return warnings


def _coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, dict[str, int]] = {}
    for record in records:
        kind = str(record.get("record_kind", ""))
        payload = record.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        subject_id = str(record.get("subject_id", "")).strip()
        source_document_id = str(record.get("source_document_id", "")).strip()
        is_workflow = str(payload.get("subject_kind", "")).strip() == "workflow"
        bucket = by_kind.setdefault(
            kind,
            {
                "total": 0,
                "with_subject": 0,
                "with_source_document": 0,
                "workflow_unscoped": 0,
                "unscoped_without_document": 0,
            },
        )
        bucket["total"] += 1
        if subject_id:
            bucket["with_subject"] += 1
        if source_document_id:
            bucket["with_source_document"] += 1
        if is_workflow and not subject_id:
            bucket["workflow_unscoped"] += 1
        if not subject_id and not source_document_id:
            bucket["unscoped_without_document"] += 1
    return {
        "with_subject_count": sum(1 for record in records if str(record.get("subject_id", "")).strip()),
        "with_source_document_count": sum(1 for record in records if str(record.get("source_document_id", "")).strip()),
        "workflow_unscoped_count": sum(
            1
            for record in records
            if not str(record.get("subject_id", "")).strip()
            and isinstance(record.get("payload"), dict)
            and str(record["payload"].get("subject_kind", "")).strip() == "workflow"
        ),
        "unscoped_without_document_count": sum(
            1
            for record in records
            if not str(record.get("subject_id", "")).strip() and not str(record.get("source_document_id", "")).strip()
        ),
        "by_kind": dict(sorted(by_kind.items())),
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _hash_payload(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    text = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in text.split("-") if part) or "record"


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa output documentali/MVP nello evidence store append-only.")
    parser.add_argument("--run-dir", required=True, help="Directory run pipeline con output document_analysis/historian_review.")
    parser.add_argument("--db", required=True, help="Percorso del database SQLite.")
    parser.add_argument("--output-json", default="", help="Report JSON di import.")
    parser.add_argument("--output-md", default="", help="Report Markdown di import.")
    args = parser.parse_args()

    result = import_document_analysis_evidence_to_db(
        run_dir=Path(args.run_dir),
        db_path=Path(args.db),
        output_json=Path(args.output_json) if args.output_json else None,
        output_md=Path(args.output_md) if args.output_md else None,
    )
    print(f"Evidence store import batch: {result['import_batch_id']}")
    print(f"Record letti: {result['record_count']}")
    print(f"Record inseriti: {result['inserted_record_count']}")
    print(f"Record gia' presenti: {result['already_present_record_count']}")
    print(f"Database: {result['db']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
