from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import load_source_registry
from .connectors.local_excel import build_file_url, build_row_snippet, load_excel_rows, normalize_value, row_matches_query
from .models import EvidenceClaim, PersonQuery, Source, SourceDocument
from .raw_store import slugify_identifier
from .sqlite_store import SQLiteEvidenceStore


@dataclass
class ExtractionSummary:
    run_id: str
    source_id: str
    people: int = 0
    matched_people: int = 0
    documents: int = 0
    claims: int = 0


def extract_table_claims_to_db(
    *,
    db_path: Path,
    run_id: str,
    source_id: str,
    sources_yaml_path: Path,
) -> ExtractionSummary:
    registry = load_source_registry(sources_yaml_path)
    if source_id not in registry:
        raise ValueError(f"Fonte non trovata nel registry: {source_id}")

    source = registry[source_id]
    mappings = claim_mappings_from_source(source)
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()

    if not run_exists(store, run_id):
        raise ValueError(f"Run non trovata nel database: {run_id}")

    people = fetch_person_queries(store, run_id)
    summary = ExtractionSummary(run_id=run_id, source_id=source_id, people=len(people))
    if not mappings:
        return summary

    now = datetime.now(UTC).isoformat()
    workbooks = load_excel_rows(source)

    for person_query in people:
        matched_for_person = False
        for workbook_path, sheet_name, rows in workbooks:
            for row in rows:
                if not row_matches_query(row, person_query.full_name, source):
                    continue
                matched_for_person = True
                document = source_document_from_row(
                    run_id=run_id,
                    source=source,
                    person_query=person_query,
                    workbook_path=workbook_path,
                    sheet_name=sheet_name,
                    row=row,
                    access_date=now,
                )
                store.insert_source_document(run_id, document)
                summary.documents += 1

                claims = claims_from_row(
                    run_id=run_id,
                    source=source,
                    person_query=person_query,
                    document=document,
                    row=row,
                    mappings=mappings,
                    created_at=now,
                )
                for claim in claims:
                    store.insert_evidence_claim(run_id, claim)
                summary.claims += len(claims)
        if matched_for_person:
            summary.matched_people += 1

    return summary


def claim_mappings_from_source(source: Source) -> list[dict[str, Any]]:
    extraction = source.extraction if isinstance(source.extraction, dict) else {}
    raw_mappings = extraction.get("claim_mappings", [])
    if not isinstance(raw_mappings, list):
        return []

    mappings: list[dict[str, Any]] = []
    for item in raw_mappings:
        if not isinstance(item, dict):
            continue
        column = str(item.get("column", "")).strip()
        field = str(item.get("field", "")).strip()
        if not column or not field:
            continue
        mappings.append(
            {
                "column": column,
                "field": field,
                "confidence": _float_or_default(item.get("confidence"), 0.0),
            }
        )
    return mappings


def source_document_from_row(
    *,
    run_id: str,
    source: Source,
    person_query: PersonQuery,
    workbook_path: Path,
    sheet_name: str,
    row: dict[str, str],
    access_date: str,
) -> SourceDocument:
    row_number = str(row.get("__row_number__", "")).strip()
    file_url = build_file_url(workbook_path)
    seed = "|".join([run_id, source.source_id, person_query.full_name, str(workbook_path), sheet_name, row_number])
    suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    title = f"{source.source_name} - {person_query.full_name} - riga {row_number or '?'}"
    document_id = "-".join(
        [
            slugify_identifier(source.source_id),
            slugify_identifier(person_query.full_name),
            slugify_identifier(workbook_path.stem),
            slugify_identifier(row_number or "row"),
            suffix,
        ]
    )
    return SourceDocument(
        document_id=document_id,
        source_id=source.source_id,
        title=title,
        url=file_url,
        access_date=access_date,
        media_type="application/vnd.ms-excel",
        local_path=str(workbook_path),
        content_hash="",
        raw_text=build_row_snippet(row, source),
        metadata={
            "access_mode": "local_table_row",
            "person_full_name": person_query.full_name,
            "workbook_path": str(workbook_path),
            "sheet_name": sheet_name,
            "row_number": row_number,
        },
    )


def claims_from_row(
    *,
    run_id: str,
    source: Source,
    person_query: PersonQuery,
    document: SourceDocument,
    row: dict[str, str],
    mappings: list[dict[str, Any]],
    created_at: str,
) -> list[EvidenceClaim]:
    extraction = source.extraction if isinstance(source.extraction, dict) else {}
    extraction_method = str(extraction.get("method") or "local_table_claims")
    claims: list[EvidenceClaim] = []

    for mapping in mappings:
        column = str(mapping["column"])
        raw_value = row.get(column, "")
        value = str(raw_value or "").strip()
        if not value:
            continue
        field = str(mapping["field"])
        claim_id = deterministic_claim_id(
            run_id=run_id,
            source_id=source.source_id,
            subject_id=subject_id_for_person(person_query),
            field=field,
            value=value,
            document_id=document.document_id,
        )
        claims.append(
            EvidenceClaim(
                claim_id=claim_id,
                subject_id=subject_id_for_person(person_query),
                field=field,
                value=value,
                normalized_value=normalize_value(value),
                source_document_id=document.document_id,
                source_url=document.url,
                quote="",
                extraction_method=extraction_method,
                confidence=float(mapping.get("confidence", 0.0)),
                review_status="unreviewed",
                created_at=created_at,
            )
        )
    return claims


def deterministic_claim_id(
    *,
    run_id: str,
    source_id: str,
    subject_id: str,
    field: str,
    value: str,
    document_id: str,
) -> str:
    seed = "|".join([run_id, source_id, subject_id, field, normalize_value(value), document_id])
    suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return "-".join(["claim", slugify_identifier(source_id), slugify_identifier(subject_id), slugify_identifier(field), suffix])


def subject_id_for_person(person_query: PersonQuery) -> str:
    return f"person:{slugify_identifier(person_query.full_name)}"


def fetch_person_queries(store: SQLiteEvidenceStore, run_id: str) -> list[PersonQuery]:
    rows = _query(
        store,
        """
        SELECT payload_json
        FROM person_queries
        WHERE run_id = ?
        ORDER BY id ASC
        """,
        (run_id,),
    )
    return [person_query_from_payload(json.loads(str(row["payload_json"]))) for row in rows]


def person_query_from_payload(payload: dict[str, Any]) -> PersonQuery:
    return PersonQuery(
        full_name=str(payload.get("full_name", "")),
        given_name=str(payload.get("given_name", "")),
        family_name=str(payload.get("family_name", "")),
        aliases=[str(item) for item in payload.get("aliases", []) if str(item)],
        birth_date=str(payload.get("birth_date", "")),
        birth_place=str(payload.get("birth_place", "")),
        death_date=str(payload.get("death_date", "")),
        death_place=str(payload.get("death_place", "")),
        formation=str(payload.get("formation", "")),
        event_hint=str(payload.get("event_hint", "")),
        place_hint=str(payload.get("place_hint", "")),
        source_hints={str(key): str(value) for key, value in (payload.get("source_hints", {}) or {}).items()},
        metadata={str(key): str(value) for key, value in (payload.get("metadata", {}) or {}).items()},
    )


def run_exists(store: SQLiteEvidenceStore, run_id: str) -> bool:
    rows = _query(store, "SELECT 1 FROM search_runs WHERE run_id = ? LIMIT 1", (run_id,))
    return bool(rows)


def _query(store: SQLiteEvidenceStore, sql: str, parameters: tuple[object, ...]) -> list[sqlite3.Row]:
    with closing(store.connect()) as connection:
        return list(connection.execute(sql, parameters))


def _float_or_default(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Estrae EvidenceClaim da fonti tabellari locali configurate nel registry YAML.")
    parser.add_argument("--db", default="data/evidence.sqlite", help="Percorso del database SQLite.")
    parser.add_argument("--run-id", required=True, help="Run gia' presente nel database.")
    parser.add_argument("--source", required=True, help="ID della fonte tabellare.")
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml", help="Registry YAML delle fonti.")
    args = parser.parse_args()

    try:
        summary = extract_table_claims_to_db(
            db_path=Path(args.db),
            run_id=args.run_id,
            source_id=args.source,
            sources_yaml_path=Path(args.sources_yaml),
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Errore: {exc}")
        return 2

    print(f"Run: {summary.run_id}")
    print(f"Fonte: {summary.source_id}")
    print(f"Persone nella run: {summary.people}")
    print(f"Persone con match tabellare: {summary.matched_people}")
    print(f"Documenti tabellari registrati: {summary.documents}")
    print(f"EvidenceClaim registrati: {summary.claims}")
    print(f"Database: {Path(args.db)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
