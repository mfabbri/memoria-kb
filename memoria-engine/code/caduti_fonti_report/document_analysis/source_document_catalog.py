"""Read-only SourceDocument existence checks against an explicit SQLite catalog."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


def resolve_source_documents(catalog_db: Path, document_ids: set[str]) -> dict[str, object]:
    """Verify document IDs in source_documents without creating or changing the database."""
    if not catalog_db.is_file():
        raise ValueError("SourceDocument catalog must be an existing SQLite file.")
    resolved_path = catalog_db.resolve()
    uri = resolved_path.as_uri() + "?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
        try:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if "source_documents" not in tables:
                raise ValueError("SourceDocument catalog lacks source_documents table.")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(source_documents)")}
            if "document_id" not in columns:
                raise ValueError("SourceDocument catalog lacks document_id column.")
            requested = sorted(value.strip() for value in document_ids if value.strip())
            found: set[str] = set()
            for offset in range(0, len(requested), 500):
                batch = requested[offset:offset + 500]
                if batch:
                    placeholders = ",".join("?" for _ in batch)
                    found.update(str(row[0]) for row in connection.execute(
                        f"SELECT document_id FROM source_documents WHERE document_id IN ({placeholders})", batch
                    ))
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise ValueError("SourceDocument catalog is not a readable compatible SQLite database.") from error
    missing = sorted(set(requested) - found)
    if missing:
        raise ValueError("SourceDocument IDs are absent from catalog: " + ", ".join(missing))
    digest = hashlib.sha256()
    database_raw = resolved_path.read_bytes()
    digest.update(database_raw)
    wal_path = Path(str(resolved_path) + "-wal")
    wal_raw = wal_path.read_bytes() if wal_path.is_file() else None
    if wal_raw is not None:
        digest.update(b"\0WAL\0")
        digest.update(wal_raw)
    return {"path": str(resolved_path), "sha256": digest.hexdigest(), "resolved_document_ids": requested,
            "database_sha256": hashlib.sha256(database_raw).hexdigest(),
            "wal_sha256": hashlib.sha256(wal_raw).hexdigest() if wal_raw is not None else None}
