from __future__ import annotations

import argparse
import csv
import sqlite3
from contextlib import closing
from pathlib import Path

from .export_audit_report import MANUAL_REVIEW_STATUSES
from .sqlite_store import SQLiteEvidenceStore


CSV_SPECS = {
    "search_runs.csv": (
        ["run_id", "timestamp", "input_file", "source_ids_json"],
        """
        SELECT run_id, timestamp, input_file, source_ids_json
        FROM search_runs
        WHERE run_id = ?
        ORDER BY timestamp ASC
        """,
    ),
    "person_queries.csv": (
        ["id", "run_id", "full_name", "given_name", "family_name"],
        """
        SELECT id, run_id, full_name, given_name, family_name
        FROM person_queries
        WHERE run_id = ?
        ORDER BY full_name ASC, id ASC
        """,
    ),
    "source_results.csv": (
        ["id", "run_id", "source_id", "source_name", "status", "query", "search_url"],
        """
        SELECT id, run_id, source_id, source_name, status, query, search_url
        FROM source_results
        WHERE run_id = ?
        ORDER BY source_id ASC, id ASC
        """,
    ),
    "source_documents.csv": (
        ["document_id", "run_id", "source_id", "title", "url", "access_date", "local_path", "content_hash"],
        """
        SELECT document_id, run_id, source_id, title, url, access_date, local_path, content_hash
        FROM source_documents
        WHERE run_id = ?
        ORDER BY source_id ASC, title ASC, document_id ASC
        """,
    ),
    "evidence_claims.csv": (
        ["claim_id", "run_id", "subject_id", "field", "value", "source_document_id", "review_status"],
        """
        SELECT claim_id, run_id, subject_id, field, value, source_document_id, review_status
        FROM evidence_claims
        WHERE run_id = ?
        ORDER BY subject_id ASC, field ASC, claim_id ASC
        """,
    ),
}


def export_audit_csv(*, db_path: Path, run_id: str, output_dir: Path) -> dict[str, object]:
    store = SQLiteEvidenceStore(db_path)
    if not _run_exists(store, run_id):
        raise ValueError(f"Run non trovata: {run_id}")

    output_dir.mkdir(parents=True, exist_ok=True)
    row_counts: dict[str, int] = {}
    for filename, (headers, sql) in CSV_SPECS.items():
        rows = _fetch_all(store, sql, (run_id,))
        _write_csv(output_dir / filename, headers, rows)
        row_counts[filename] = len(rows)

    manual_rows = _manual_review_rows(store, run_id)
    manual_headers = ["run_id", "source_id", "status", "reason", "search_url"]
    _write_csv(output_dir / "manual_review.csv", manual_headers, manual_rows)
    row_counts["manual_review.csv"] = len(manual_rows)

    return {
        "run_id": run_id,
        "output_dir": str(output_dir),
        "files": row_counts,
    }


def _run_exists(store: SQLiteEvidenceStore, run_id: str) -> bool:
    with closing(store.connect()) as connection:
        row = connection.execute("SELECT 1 FROM search_runs WHERE run_id = ?", (run_id,)).fetchone()
    return row is not None


def _manual_review_rows(store: SQLiteEvidenceStore, run_id: str) -> list[dict[str, str]]:
    result_rows = _fetch_all(
        store,
        """
        SELECT source_id, status, search_url
        FROM source_results
        WHERE run_id = ?
        ORDER BY source_id ASC, id ASC
        """,
        (run_id,),
    )
    document_counts = {
        str(row["source_id"]): int(row["count"])
        for row in _fetch_all(
            store,
            """
            SELECT source_id, COUNT(*) AS count
            FROM source_documents
            WHERE run_id = ?
            GROUP BY source_id
            """,
            (run_id,),
        )
    }

    manual_rows: list[dict[str, str]] = []
    for result in result_rows:
        source_id = str(result["source_id"])
        status = str(result["status"])
        reason = ""
        if status in MANUAL_REVIEW_STATUSES:
            reason = f"stato {status}: verifica manuale richiesta"
        elif document_counts.get(source_id, 0) == 0:
            reason = "nessun documento registrato per la fonte"
        if reason:
            manual_rows.append(
                {
                    "run_id": run_id,
                    "source_id": source_id,
                    "status": status,
                    "reason": reason,
                    "search_url": str(result["search_url"]),
                }
            )
    return manual_rows


def _fetch_all(store: SQLiteEvidenceStore, sql: str, parameters: tuple[object, ...]) -> list[sqlite3.Row]:
    with closing(store.connect()) as connection:
        return list(connection.execute(sql, parameters))


def _write_csv(path: Path, headers: list[str], rows: list[sqlite3.Row] | list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row[header] for header in headers})


def main() -> int:
    parser = argparse.ArgumentParser(description="Esporta CSV audit da una run nel database SQLite.")
    parser.add_argument("--db", default="data/evidence.sqlite", help="Percorso del database SQLite.")
    parser.add_argument("--run-id", required=True, help="Identificativo della run da esportare.")
    parser.add_argument("--output-dir", required=True, help="Cartella di output dei CSV.")
    args = parser.parse_args()

    try:
        result = export_audit_csv(
            db_path=Path(args.db),
            run_id=args.run_id,
            output_dir=Path(args.output_dir),
        )
    except ValueError as error:
        print(str(error))
        return 2

    print(f"CSV audit esportati in {result['output_dir']}")
    for filename, count in result["files"].items():
        print(f"{filename}: {count} righe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
