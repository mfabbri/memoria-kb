"""Preview/apply registration of one explicit local SourceDocument."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from caduti_fonti_report.models import SearchRun, SourceDocument
from caduti_fonti_report.source_catalog import resolve_source_registry_path


def register_local_source_document(*, database_path: Path, file_path: Path,
                                   source_id: str, title: str, access_date: str,
                                   archival_reference: str = "",
                                   sources_registry: Path | None = None,
                                   apply: bool = False, timestamp: str) -> dict[str, Any]:
    file_path = file_path.resolve(strict=True)
    if not file_path.is_file():
        raise ValueError("file_path must identify one regular file")
    for value, name in ((source_id, "source_id"), (title, "title")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} is required")
    try:
        date.fromisoformat(access_date)
    except (TypeError, ValueError) as error:
        raise ValueError("access_date must use YYYY-MM-DD") from error
    if not database_path.is_file():
        raise ValueError("Operational SQLite database must already exist")
    registry = sources_registry or resolve_source_registry_path()
    try:
        payload = yaml.safe_load(registry.read_text(encoding="utf-8-sig")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ValueError("Could not read source registry") from error
    enabled = payload.get("enabled_sources") if isinstance(payload, dict) else None
    if not isinstance(enabled, list) or source_id not in enabled:
        raise ValueError("source_id is not enabled in source registry")
    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
    document_id = "local-source:" + hashlib.sha256(
        json.dumps([source_id, digest], separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    document = SourceDocument(
        document_id=document_id, source_id=source_id, title=title.strip(),
        access_date=access_date, media_type=media_type, local_path=str(file_path),
        content_hash=digest, metadata={"registration_method": "explicit_local_file",
        "archival_reference": archival_reference.strip(), "review_status": "unreviewed"})
    run = SearchRun(run_id="local-source-registration-" + document_id.split(":", 1)[1],
        timestamp=timestamp, input_file=str(file_path), source_ids=[source_id],
        parameters={"operation": "register-local-source"},
        metadata={"document_id": document_id, "content_hash": digest})
    if not apply:
        return {"status": _existing_status(database_path, document), "apply": False,
                "source_document": asdict(document), "run_id": run.run_id}
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(source_documents)")}
        if not {"document_id", "run_id", "source_id", "title", "url", "access_date", "local_path", "content_hash", "payload_json"}.issubset(columns):
            raise ValueError("Operational database has no compatible source_documents table")
        row = connection.execute("SELECT payload_json FROM source_documents WHERE document_id=?", (document_id,)).fetchone()
        if row:
            if json.loads(row[0]) != asdict(document):
                raise ValueError("Existing SourceDocument differs; refusing overwrite")
            connection.rollback()
            return {"status": "already_registered", "apply": True, "source_document": asdict(document), "run_id": run.run_id}
        run_exists = connection.execute("SELECT 1 FROM search_runs WHERE run_id=?", (run.run_id,)).fetchone()
        if run_exists:
            raise ValueError("Registration run exists without its SourceDocument")
        encode = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
        connection.execute("INSERT INTO search_runs VALUES (?,?,?,?,?,?,?)", (run.run_id, run.timestamp,
            run.input_file, encode(run.source_ids), encode(run.parameters), encode(run.metadata), encode(asdict(run))))
        connection.execute("INSERT INTO source_documents VALUES (?,?,?,?,?,?,?,?,?)", (document.document_id,
            run.run_id, source_id, document.title, "", access_date, str(file_path), digest, encode(asdict(document))))
        connection.commit()
    return {"status": "registered", "apply": True, "source_document": asdict(document), "run_id": run.run_id}


def _existing_status(database_path: Path, document: SourceDocument) -> str:
    with closing(sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        row = connection.execute("SELECT payload_json FROM source_documents WHERE document_id=?", (document.document_id,)).fetchone()
    if not row:
        return "would_register"
    if json.loads(row[0]) != asdict(document):
        raise ValueError("Existing SourceDocument differs; refusing overwrite")
    return "already_registered"
