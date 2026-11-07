"""Preview/apply registration of an explicitly catalogued online SourceDocument."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from caduti_fonti_report.models import SearchRun, SourceDocument
from caduti_fonti_report.source_catalog import resolve_source_registry_path


def register_online_source_document(
    *, database_path: Path, source_id: str, document_id: str, title: str,
    url: str, access_date: str, sources_registry: Path | None = None,
    apply: bool = False, timestamp: str, expected_existing_title: str | None = None,
) -> dict[str, Any]:
    source_id = _required(source_id, "source_id")
    document_id = _required(document_id, "document_id")
    title = _required(title, "title")
    url = _required(url, "url")
    access_date = _required(access_date, "access_date")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Online SourceDocument URL must be an absolute HTTPS URL.")
    try:
        date.fromisoformat(access_date)
    except ValueError as error:
        raise ValueError("access_date must use YYYY-MM-DD.") from error
    _validate_registry_source(source_id, sources_registry or resolve_source_registry_path())
    if not database_path.is_file():
        raise ValueError("Operational SQLite database must already exist; registration will not create it.")
    run_id = "source-registration-" + document_id
    source = SourceDocument(
        document_id=document_id, source_id=source_id, title=title, url=url,
        access_date=access_date, media_type="text/html", local_path="", content_hash="",
        metadata={"source_registry_id": source_id, "registration_method": "manual_online_source",
                  "capture_status": "excerpt_only", "full_page_archived": "false",
                  "review_status": "unreviewed"},
    )
    run = SearchRun(
        run_id=run_id, timestamp=timestamp, input_file=url, source_ids=[source_id],
        parameters={"operation": "register-online-source-document"},
        metadata={"document_id": document_id, "source_registry_id": source_id},
    )
    if not apply:
        status = _check_existing(database_path, source, expected_existing_title)
        return {"status": status,
                "apply": False, "database_path": str(database_path.resolve()),
                "source_document": asdict(source), "run_id": run_id}

    columns = {"document_id", "run_id", "source_id", "title", "url", "access_date",
               "local_path", "content_hash", "payload_json"}
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        table_columns = {row[1] for row in connection.execute("PRAGMA table_info(source_documents)")}
        if not columns.issubset(table_columns):
            raise ValueError("Operational database has no compatible source_documents table.")
        existing = connection.execute(
            "SELECT source_id, title, url, access_date, payload_json FROM source_documents WHERE document_id=?", (document_id,)
        ).fetchone()
        if existing:
            if (existing[0], existing[2], existing[3]) != (source.source_id, source.url, source.access_date):
                raise ValueError("SourceDocument ID exists with different identity metadata; refusing overwrite.")
            if existing[1] != source.title:
                if expected_existing_title is None or existing[1] != expected_existing_title:
                    raise ValueError("SourceDocument title differs; refusing overwrite without --expected-existing-title compare-and-swap confirmation.")
                payload = json.loads(existing[4])
                if not isinstance(payload, dict) or payload.get("title") != existing[1]:
                    raise ValueError("SourceDocument payload title is inconsistent; refusing correction.")
                payload["title"] = source.title
                connection.execute(
                    "UPDATE source_documents SET title=?, payload_json=? WHERE document_id=? AND title=?",
                    (source.title, json.dumps(payload, ensure_ascii=False, sort_keys=True), document_id, existing[1]),
                )
                connection.commit()
                return {"status": "title_corrected", "apply": True,
                        "database_path": str(database_path.resolve()), "source_document": asdict(source),
                        "run_id": run_id}
            connection.rollback()
            return {"status": "already_registered", "apply": True,
                    "database_path": str(database_path.resolve()), "source_document": asdict(source),
                    "run_id": run_id}
        if connection.execute("SELECT 1 FROM search_runs WHERE run_id=?", (run_id,)).fetchone():
            raise ValueError("Registration run ID already exists without its SourceDocument; refusing overwrite.")
        encode = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
        connection.execute(
            "INSERT INTO search_runs (run_id,timestamp,input_file,source_ids_json,parameters_json,metadata_json,payload_json) "
            "VALUES (?,?,?,?,?,?,?)",
            (run.run_id, run.timestamp, run.input_file, encode(run.source_ids), encode(run.parameters),
             encode(run.metadata), encode(asdict(run))),
        )
        connection.execute(
            "INSERT INTO source_documents (document_id,run_id,source_id,title,url,access_date,local_path,content_hash,payload_json) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (source.document_id, run.run_id, source.source_id, source.title, source.url, source.access_date,
             source.local_path, source.content_hash, encode(asdict(source))),
        )
        connection.commit()
    return {"status": "registered", "apply": True, "database_path": str(database_path.resolve()),
            "source_document": asdict(source), "run_id": run_id}


def _validate_registry_source(source_id: str, registry_path: Path) -> None:
    if not registry_path.is_file():
        raise ValueError("Source registry file does not exist.")
    try:
        payload = yaml.safe_load(registry_path.read_text(encoding="utf-8-sig")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError("Could not read the source registry.") from error
    enabled = payload.get("enabled_sources") if isinstance(payload, dict) else None
    if not isinstance(enabled, list) or source_id not in enabled:
        raise ValueError("source_id is not enabled in the source registry.")


def _check_existing(database_path: Path, source: SourceDocument, expected_existing_title: str | None = None) -> str:
    uri = database_path.resolve().as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(source_documents)")}
            needed = {"document_id", "source_id", "title", "url", "access_date"}
            if not needed.issubset(columns):
                raise ValueError("Operational database has no compatible source_documents table.")
            row = connection.execute(
                "SELECT source_id,title,url,access_date FROM source_documents WHERE document_id=?",
                (source.document_id,),
            ).fetchone()
    except sqlite3.Error as error:
        raise ValueError("Could not read the operational SourceDocument catalog.") from error
    if not row:
        return "would_register"
    if (row[0], row[2], row[3]) != (source.source_id, source.url, source.access_date):
        raise ValueError("SourceDocument ID exists with different identity metadata; refusing overwrite.")
    if row[1] != source.title:
        if expected_existing_title is not None and row[1] == expected_existing_title:
            return "would_correct_title"
        raise ValueError("SourceDocument title differs; refusing overwrite without --expected-existing-title compare-and-swap confirmation.")
    return "already_registered"


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " is required.")
    return value.strip()
