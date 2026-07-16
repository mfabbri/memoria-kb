from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .models import EvidenceClaim, HistoricalEvent, PersonQuery, Place, SearchRun, SourceDocument, SourceResult, to_json_safe


class SQLiteEvidenceStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_schema(self) -> None:
        with closing(self.connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS search_runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    input_file TEXT,
                    source_ids_json TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS person_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    given_name TEXT,
                    family_name TEXT,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES search_runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS source_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_name TEXT,
                    status TEXT,
                    query TEXT,
                    search_url TEXT,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES search_runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS source_documents (
                    document_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    title TEXT,
                    url TEXT,
                    access_date TEXT,
                    local_path TEXT,
                    content_hash TEXT,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES search_runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS evidence_claims (
                    claim_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    field TEXT NOT NULL,
                    value TEXT,
                    source_document_id TEXT,
                    review_status TEXT,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES search_runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    date_start TEXT,
                    date_end TEXT,
                    review_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS places (
                    place_id TEXT PRIMARY KEY,
                    preferred_label TEXT NOT NULL,
                    place_type TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_import_batches (
                    import_batch_id TEXT PRIMARY KEY,
                    source_run_id TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    source_run_dir TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_records (
                    record_id TEXT PRIMARY KEY,
                    import_batch_id TEXT NOT NULL,
                    source_run_id TEXT NOT NULL,
                    record_kind TEXT NOT NULL,
                    subject_id TEXT,
                    source_document_id TEXT,
                    review_status TEXT,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (import_batch_id) REFERENCES evidence_import_batches(import_batch_id)
                );
                """
            )
            connection.commit()

    def insert_search_run(self, run: SearchRun) -> None:
        payload = to_json_safe(run)
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO search_runs (
                    run_id, timestamp, input_file, source_ids_json, parameters_json, metadata_json, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.timestamp,
                    run.input_file,
                    self._json(run.source_ids),
                    self._json(run.parameters),
                    self._json(run.metadata),
                    self._json(payload),
                ),
            )
            connection.commit()

    def delete_run(self, run_id: str) -> None:
        with closing(self.connect()) as connection:
            connection.execute("DELETE FROM evidence_claims WHERE run_id = ?", (run_id,))
            connection.execute("DELETE FROM source_documents WHERE run_id = ?", (run_id,))
            connection.execute("DELETE FROM source_results WHERE run_id = ?", (run_id,))
            connection.execute("DELETE FROM person_queries WHERE run_id = ?", (run_id,))
            connection.execute("DELETE FROM search_runs WHERE run_id = ?", (run_id,))
            connection.commit()

    def insert_person_query(self, run_id: str, person_query: PersonQuery) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT INTO person_queries (
                    run_id, full_name, given_name, family_name, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    person_query.full_name,
                    person_query.given_name,
                    person_query.family_name,
                    self._json(person_query),
                ),
            )
            connection.commit()

    def insert_source_result(self, run_id: str, source_result: SourceResult) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT INTO source_results (
                    run_id, source_id, source_name, status, query, search_url, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_result.source_id,
                    source_result.source_name,
                    source_result.status,
                    source_result.query,
                    source_result.search_url,
                    self._json(source_result),
                ),
            )
            connection.commit()

    def insert_source_document(self, run_id: str, document: SourceDocument) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO source_documents (
                    document_id, run_id, source_id, title, url, access_date, local_path, content_hash, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.document_id,
                    run_id,
                    document.source_id,
                    document.title,
                    document.url,
                    document.access_date,
                    document.local_path,
                    document.content_hash,
                    self._json(document),
                ),
            )
            connection.commit()

    def insert_evidence_claim(self, run_id: str, claim: EvidenceClaim) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO evidence_claims (
                    claim_id, run_id, subject_id, field, value, source_document_id, review_status, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim.claim_id,
                    run_id,
                    claim.subject_id,
                    claim.field,
                    claim.value,
                    claim.source_document_id,
                    claim.review_status,
                    self._json(claim),
                ),
            )
            connection.commit()

    def insert_event(self, event: HistoricalEvent) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO events (
                    event_id, event_type, label, date_start, date_end, review_status, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type,
                    event.label,
                    event.date_start,
                    event.date_end,
                    event.review_status,
                    self._json(event),
                ),
            )
            connection.commit()

    def fetch_events(self) -> list[sqlite3.Row]:
        with closing(self.connect()) as connection:
            return list(connection.execute("SELECT * FROM events ORDER BY label ASC, event_id ASC"))

    def insert_place(self, place: Place) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO places (
                    place_id, preferred_label, place_type, review_status, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    place.place_id,
                    place.preferred_label,
                    place.place_type,
                    place.review_status,
                    self._json(place),
                ),
            )
            connection.commit()

    def fetch_places(self) -> list[sqlite3.Row]:
        with closing(self.connect()) as connection:
            return list(connection.execute("SELECT * FROM places ORDER BY preferred_label ASC, place_id ASC"))

    def count(self, table_name: str) -> int:
        self._validate_table_name(table_name)
        with closing(self.connect()) as connection:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
        return int(row["count"])

    def fetch_all(self, table_name: str) -> list[sqlite3.Row]:
        self._validate_table_name(table_name)
        with closing(self.connect()) as connection:
            return list(connection.execute(f"SELECT * FROM {table_name}"))

    def insert_evidence_import_batch(self, batch: dict[str, Any]) -> None:
        with closing(self.connect()) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO evidence_import_batches (
                    import_batch_id, source_run_id, imported_at, source_run_dir,
                    record_count, payload_hash, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(batch.get("import_batch_id", "")),
                    str(batch.get("source_run_id", "")),
                    str(batch.get("imported_at", "")),
                    str(batch.get("source_run_dir", "")),
                    int(batch.get("record_count", 0)),
                    str(batch.get("payload_hash", "")),
                    self._json(batch),
                ),
            )
            connection.commit()

    def insert_evidence_record(self, record: dict[str, Any]) -> bool:
        with closing(self.connect()) as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO evidence_records (
                    record_id, import_batch_id, source_run_id, record_kind,
                    subject_id, source_document_id, review_status, payload_hash, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.get("record_id", "")),
                    str(record.get("import_batch_id", "")),
                    str(record.get("source_run_id", "")),
                    str(record.get("record_kind", "")),
                    str(record.get("subject_id", "")),
                    str(record.get("source_document_id", "")),
                    str(record.get("review_status", "")),
                    str(record.get("payload_hash", "")),
                    self._json(record),
                ),
            )
            connection.commit()
            return cursor.rowcount > 0

    def _json(self, value: Any) -> str:
        return json.dumps(to_json_safe(value), ensure_ascii=False, sort_keys=True)

    def _validate_table_name(self, table_name: str) -> None:
        allowed = {
            "search_runs",
            "person_queries",
            "source_results",
            "source_documents",
            "evidence_claims",
            "events",
            "places",
            "evidence_import_batches",
            "evidence_records",
        }
        if table_name not in allowed:
            raise ValueError(f"Tabella non prevista: {table_name}")
