from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .sqlite_store import SQLiteEvidenceStore


TABLES = [
    "search_runs",
    "person_queries",
    "source_results",
    "source_documents",
    "evidence_claims",
    "evidence_import_batches",
    "evidence_records",
]


def build_summary(store: SQLiteEvidenceStore) -> list[str]:
    lines = ["Database summary"]
    for table_name in TABLES:
        lines.append(f"{table_name}: {store.count(table_name)}")
    return lines


def build_runs(store: SQLiteEvidenceStore, *, limit: int = 5) -> list[str]:
    rows = _query(
        store,
        """
        SELECT
            r.run_id,
            r.timestamp,
            r.source_ids_json,
            COUNT(DISTINCT pq.id) AS person_queries,
            COUNT(DISTINCT sr.id) AS source_results,
            COUNT(DISTINCT sd.document_id) AS source_documents,
            COUNT(DISTINCT ec.claim_id) AS evidence_claims
        FROM search_runs r
        LEFT JOIN person_queries pq ON pq.run_id = r.run_id
        LEFT JOIN source_results sr ON sr.run_id = r.run_id
        LEFT JOIN source_documents sd ON sd.run_id = r.run_id
        LEFT JOIN evidence_claims ec ON ec.run_id = r.run_id
        GROUP BY r.run_id
        ORDER BY r.timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )
    lines = [f"Recent runs (limit {limit})"]
    if not rows:
        lines.append("(nessuna run)")
        return lines
    for row in rows:
        sources = ", ".join(_json_list(row["source_ids_json"]))
        lines.append(
            " | ".join(
                [
                    f"run_id={row['run_id']}",
                    f"timestamp={row['timestamp']}",
                    f"sources={sources}",
                    f"person_queries={row['person_queries']}",
                    f"source_results={row['source_results']}",
                    f"source_documents={row['source_documents']}",
                    f"evidence_claims={row['evidence_claims']}",
                ]
            )
        )
    return lines


def build_run_detail(store: SQLiteEvidenceStore, *, run_id: str) -> list[str]:
    rows = _query(
        store,
        """
        SELECT
            r.run_id,
            r.timestamp,
            r.input_file,
            r.source_ids_json,
            COUNT(DISTINCT pq.id) AS person_queries,
            COUNT(DISTINCT sr.id) AS source_results,
            COUNT(DISTINCT sd.document_id) AS source_documents,
            COUNT(DISTINCT ec.claim_id) AS evidence_claims
        FROM search_runs r
        LEFT JOIN person_queries pq ON pq.run_id = r.run_id
        LEFT JOIN source_results sr ON sr.run_id = r.run_id
        LEFT JOIN source_documents sd ON sd.run_id = r.run_id
        LEFT JOIN evidence_claims ec ON ec.run_id = r.run_id
        WHERE r.run_id = ?
        GROUP BY r.run_id
        """,
        (run_id,),
    )
    if not rows:
        return [f"Run non trovata: {run_id}"]

    row = rows[0]
    lines = [
        f"run_id: {row['run_id']}",
        f"timestamp: {row['timestamp']}",
        f"input_file: {row['input_file']}",
        f"sources: {', '.join(_json_list(row['source_ids_json']))}",
        f"person_queries: {row['person_queries']}",
        f"source_results: {row['source_results']}",
        f"source_documents: {row['source_documents']}",
        f"evidence_claims: {row['evidence_claims']}",
    ]
    return lines


def build_documents(store: SQLiteEvidenceStore, *, limit: int = 20) -> list[str]:
    rows = _query(
        store,
        """
        SELECT document_id, run_id, source_id, title, url
        FROM source_documents
        ORDER BY access_date DESC, document_id ASC
        LIMIT ?
        """,
        (limit,),
    )
    lines = [f"Source documents (limit {limit})"]
    if not rows:
        lines.append("(nessun documento)")
        return lines
    for row in rows:
        lines.append(
            " | ".join(
                [
                    f"document_id={row['document_id']}",
                    f"run_id={row['run_id']}",
                    f"source_id={row['source_id']}",
                    f"title={row['title']}",
                    f"url={row['url']}",
                ]
            )
        )
    return lines


def build_sources(store: SQLiteEvidenceStore) -> list[str]:
    rows = _query(
        store,
        """
        SELECT source_id, status, COUNT(*) AS count
        FROM source_results
        GROUP BY source_id, status
        ORDER BY source_id ASC, status ASC
        """,
        (),
    )
    lines = ["Sources by status"]
    if not rows:
        lines.append("(nessuna fonte)")
        return lines
    for row in rows:
        lines.append(f"source_id={row['source_id']} | status={row['status']} | count={row['count']}")
    return lines


def build_evidence_imports(store: SQLiteEvidenceStore, *, limit: int = 10) -> list[str]:
    rows = _query(
        store,
        """
        SELECT import_batch_id, source_run_id, imported_at, source_run_dir, record_count, payload_hash
        FROM evidence_import_batches
        ORDER BY imported_at DESC, import_batch_id ASC
        LIMIT ?
        """,
        (limit,),
    )
    lines = [f"Evidence import batches (limit {limit})"]
    if not rows:
        lines.append("(nessun batch importato)")
        return lines
    for row in rows:
        lines.append(
            " | ".join(
                [
                    f"import_batch_id={row['import_batch_id']}",
                    f"source_run_id={row['source_run_id']}",
                    f"imported_at={row['imported_at']}",
                    f"records={row['record_count']}",
                    f"payload_hash={row['payload_hash']}",
                    f"source_run_dir={row['source_run_dir']}",
                ]
            )
        )
    return lines


def build_evidence_records(store: SQLiteEvidenceStore) -> list[str]:
    rows = _query(
        store,
        """
        SELECT source_run_id, record_kind, review_status, COUNT(*) AS count
        FROM evidence_records
        GROUP BY source_run_id, record_kind, review_status
        ORDER BY source_run_id ASC, record_kind ASC, review_status ASC
        """,
        (),
    )
    lines = ["Evidence records by run, kind and status"]
    if not rows:
        lines.append("(nessun record importato)")
        return lines
    for row in rows:
        lines.append(
            " | ".join(
                [
                    f"source_run_id={row['source_run_id']}",
                    f"record_kind={row['record_kind']}",
                    f"review_status={row['review_status']}",
                    f"count={row['count']}",
                ]
            )
        )
    return lines


def build_evidence_subjects(store: SQLiteEvidenceStore, *, limit: int = 20) -> list[str]:
    rows = _query(
        store,
        """
        SELECT subject_id, COUNT(*) AS record_count, COUNT(DISTINCT source_document_id) AS source_documents
        FROM evidence_records
        WHERE subject_id IS NOT NULL AND subject_id <> ''
        GROUP BY subject_id
        ORDER BY record_count DESC, subject_id ASC
        LIMIT ?
        """,
        (limit,),
    )
    lines = [f"Evidence records by subject (limit {limit})"]
    if not rows:
        lines.append("(nessun soggetto con record importati)")
        return lines
    for row in rows:
        lines.append(
            " | ".join(
                [
                    f"subject_id={row['subject_id']}",
                    f"records={row['record_count']}",
                    f"source_documents={row['source_documents']}",
                ]
            )
        )
    return lines


def build_evidence_coverage(store: SQLiteEvidenceStore) -> list[str]:
    rows = _query(
        store,
        """
        SELECT record_kind, subject_id, source_document_id, payload_json
        FROM evidence_records
        ORDER BY record_kind ASC, record_id ASC
        """,
        (),
    )
    lines = ["Evidence coverage by kind"]
    if not rows:
        lines.append("(nessun record importato)")
        return lines
    coverage: dict[str, dict[str, int]] = {}
    for row in rows:
        kind = str(row["record_kind"] or "")
        subject_id = str(row["subject_id"] or "").strip()
        source_document_id = str(row["source_document_id"] or "").strip()
        payload = _json_object(row["payload_json"])
        record_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
        subject_kind = str(record_payload.get("subject_kind", "")).strip() if isinstance(record_payload, dict) else ""
        bucket = coverage.setdefault(
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
        if subject_kind == "workflow" and not subject_id:
            bucket["workflow_unscoped"] += 1
        if not subject_id and not source_document_id:
            bucket["unscoped_without_document"] += 1
    for kind, bucket in sorted(coverage.items()):
        lines.append(
            " | ".join(
                [
                    f"record_kind={kind}",
                    f"total={bucket['total']}",
                    f"with_subject={bucket['with_subject']}",
                    f"with_source_document={bucket['with_source_document']}",
                    f"workflow_unscoped={bucket['workflow_unscoped']}",
                    f"unscoped_without_document={bucket['unscoped_without_document']}",
                ]
            )
        )
    return lines


def inspect_database(
    *,
    db_path: Path,
    summary: bool = False,
    runs: bool = False,
    run_id: str = "",
    documents: bool = False,
    sources: bool = False,
    evidence_imports: bool = False,
    evidence_records: bool = False,
    evidence_subjects: bool = False,
    evidence_coverage: bool = False,
    limit: int = 5,
) -> str:
    store = SQLiteEvidenceStore(db_path)
    selected_any = (
        summary
        or runs
        or bool(run_id)
        or documents
        or sources
        or evidence_imports
        or evidence_records
        or evidence_subjects
        or evidence_coverage
    )
    sections: list[list[str]] = []

    if not selected_any:
        sections.append(build_summary(store))
        sections.append(build_runs(store, limit=limit))
    else:
        if summary:
            sections.append(build_summary(store))
        if runs:
            sections.append(build_runs(store, limit=limit))
        if run_id:
            sections.append(build_run_detail(store, run_id=run_id))
        if documents:
            sections.append(build_documents(store, limit=limit))
        if sources:
            sections.append(build_sources(store))
        if evidence_imports:
            sections.append(build_evidence_imports(store, limit=limit))
        if evidence_records:
            sections.append(build_evidence_records(store))
        if evidence_subjects:
            sections.append(build_evidence_subjects(store, limit=limit))
        if evidence_coverage:
            sections.append(build_evidence_coverage(store))

    return "\n\n".join("\n".join(section) for section in sections)


def _query(store: SQLiteEvidenceStore, sql: str, parameters: tuple[object, ...]) -> list[sqlite3.Row]:
    with closing(store.connect()) as connection:
        return list(connection.execute(sql, parameters))


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _json_object(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ispeziona il database SQLite delle evidenze.")
    parser.add_argument("--db", default="data/evidence.sqlite", help="Percorso del database SQLite.")
    parser.add_argument("--summary", action="store_true", help="Mostra conteggi per tabella.")
    parser.add_argument("--runs", action="store_true", help="Mostra le run recenti.")
    parser.add_argument("--run-id", default="", help="Mostra il dettaglio di una run.")
    parser.add_argument("--documents", action="store_true", help="Mostra documenti registrati.")
    parser.add_argument("--sources", action="store_true", help="Mostra riepilogo per fonte e status.")
    parser.add_argument("--evidence-imports", action="store_true", help="Mostra batch append-only importati nello store.")
    parser.add_argument("--evidence-records", action="store_true", help="Mostra record candidati per run, tipo e stato.")
    parser.add_argument("--evidence-subjects", action="store_true", help="Mostra soggetti/profili con record candidati.")
    parser.add_argument("--evidence-coverage", action="store_true", help="Mostra copertura record per soggetto, documento e workflow.")
    parser.add_argument("--limit", type=int, default=5, help="Numero massimo di righe per le viste elenco.")
    args = parser.parse_args()

    print(
        inspect_database(
            db_path=Path(args.db),
            summary=args.summary,
            runs=args.runs,
            run_id=args.run_id,
            documents=args.documents,
            sources=args.sources,
            evidence_imports=args.evidence_imports,
            evidence_records=args.evidence_records,
            evidence_subjects=args.evidence_subjects,
            evidence_coverage=args.evidence_coverage,
            limit=args.limit,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
