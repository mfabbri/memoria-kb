"""Offline, explicit registration of hash-bound OCR derivatives.

Registration records provenance only. It does not run OCR or create claims.
"""
from __future__ import annotations

from dataclasses import asdict
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

import yaml

from ..models import SearchRun, SourceDocument
from ..sqlite_store import SQLiteEvidenceStore
from .document_structure import reconstruct_document_structure, render_document_structure_markdown


def source_document_id(source_id: str, original_path: Path, content_hash: str) -> str:
    """Identify original bytes independently of OCR variants and execution time."""
    identity = json.dumps([source_id, original_path.resolve().as_uri(), content_hash], separators=(",", ":"))
    return "ocr-source-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _hash(value: Any, name: str) -> str:
    value = _text(value, name)
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _file(base: Path, reference: Any, name: str) -> tuple[Path, bytes]:
    ref = _object(reference, name)
    path = Path(_text(ref.get("path"), name + ".path"))
    path = (base / path).resolve() if not path.is_absolute() else path.resolve()
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != _hash(ref.get("sha256"), name + ".sha256"):
        raise ValueError(f"{name} SHA-256 mismatch")
    return path, data


def _json(data: bytes, name: str) -> dict[str, Any]:
    return _object(json.loads(data), name)


def _existing(connection: sqlite3.Connection, document: SourceDocument) -> bool:
    table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='source_documents'").fetchone()
    if table is None:
        return False
    row = connection.execute("SELECT payload_json FROM source_documents WHERE document_id = ?", (document.document_id,)).fetchone()
    if row is None:
        return False
    if json.loads(row[0]) != asdict(document):
        raise ValueError("Existing SourceDocument has a divergent payload; explicit review is required")
    return True


def register_ocr_source_document(*, manifest_path: Path, database_path: Path,
                                 sources_registry_path: Path | None = None, apply: bool = False) -> dict[str, Any]:
    """Validate all files before preview or atomic, non-overwriting registration.

    Version 1.0 accepts local originals and unreviewed OCR candidates only.
    Paths in the manifest are relative to its directory unless absolute.
    """
    manifest_path = manifest_path.resolve()
    manifest_bytes = manifest_path.read_bytes()
    manifest = _json(manifest_bytes, "manifest")
    if manifest.get("@type") != "OcrSourceDocumentRegistration" or manifest.get("schema_version") != "1.0":
        raise ValueError("Expected OcrSourceDocumentRegistration schema_version 1.0")
    source_id = _text(manifest.get("source_id"), "source_id")
    if sources_registry_path is None:
        sources_registry_path = Path(__file__).resolve().parents[4] / "memoria-sources/registry/camalanca_fonti.yaml"
    registry = _object(yaml.safe_load(sources_registry_path.read_text(encoding="utf-8")), "sources registry")
    if source_id not in {item.get("id") for item in registry.get("sources", []) if isinstance(item, dict)}:
        raise ValueError("source_id is not present in the sources registry")
    original_path, _ = _file(manifest_path.parent, {"path": manifest.get("local_path"), "sha256": manifest.get("content_hash")}, "original")
    digest = manifest["content_hash"]
    document_id = source_document_id(source_id, original_path, digest)
    if manifest.get("source_document_id") != document_id:
        raise ValueError("source_document_id does not match the original identity")
    access_date = _text(manifest.get("access_date"), "access_date")
    timestamp = datetime.fromisoformat(access_date.replace("Z", "+00:00"))
    if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("access_date must be a UTC timestamp")
    workflow_status = _text(manifest.get("workflow_status"), "workflow_status")
    if manifest.get("review_status") != "unreviewed":
        raise ValueError("Version 1.0 requires review_status=unreviewed; human decisions need a separate review flow")
    for flag in ("machine_pass", "human_verified", "claim_extraction_allowed"):
        if manifest.get(flag, False) is not False:
            raise ValueError(f"Registration cannot enable {flag}")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("pages must be a non-empty list")
    page_ids: set[str] = set()
    for item in pages:
        page = _object(item, "page")
        page_id = _text(page.get("page_id"), "page_id")
        if page_id in page_ids:
            raise ValueError("Duplicate page_id")
        page_ids.add(page_id)
        if page.get("source_document_id") != document_id or page.get("review_status") != "unreviewed":
            raise ValueError("Page document binding or review_status mismatch")
        _text(page.get("transcription_validation_status"), "transcription_validation_status")
        image_path, _ = _file(manifest_path.parent, page.get("source_image"), "source_image")
        image_hash = page["source_image"]["sha256"]
        if image_path != original_path or image_hash != digest:
            transform = _object(page.get("source_image_transform"), "source_image_transform")
            if transform.get("original_sha256") != digest or transform.get("source_image_sha256") != image_hash:
                raise ValueError("Derived source image requires a transformation bound to original and image hashes")
            _text(transform.get("description"), "source_image_transform.description")
        _, evidence_bytes = _file(manifest_path.parent, page.get("evidence"), "evidence")
        _, structure_bytes = _file(manifest_path.parent, page.get("structure"), "structure")
        _, markdown_bytes = _file(manifest_path.parent, page.get("markdown"), "markdown")
        evidence = _json(evidence_bytes, "evidence")
        structure = _json(structure_bytes, "structure")
        if evidence.get("page_id") != page_id or evidence.get("source_image_hash") != image_hash:
            raise ValueError("Evidence page/image binding mismatch")
        source_page = _object(evidence.get("source_page"), "evidence.source_page")
        if evidence.get("source_document_id") != document_id or source_page != page.get("source_page"):
            raise ValueError("Evidence source_page/document binding mismatch")
        for flag in ("machine_pass", "human_verified", "claim_extraction_allowed"):
            if page.get(flag, False) is not False or evidence.get(flag, False) is not False:
                raise ValueError(f"Registration cannot enable {flag}")
        reconstructed = reconstruct_document_structure(evidence=evidence, profile=_text(structure.get("profile"), "structure.profile"))
        if structure != reconstructed.to_dict():
            raise ValueError("DocumentStructure does not match the exact OCR evidence")
        if markdown_bytes != render_document_structure_markdown(reconstructed).encode("utf-8"):
            raise ValueError("Markdown does not match DocumentStructure")
    document = SourceDocument(document_id=document_id, source_id=source_id,
        title=_text(manifest.get("title"), "title"), access_date=access_date,
        media_type=_text(manifest.get("media_type"), "media_type"), local_path=str(original_path), content_hash=digest,
        metadata={"ocr_artifact_manifest_path": str(manifest_path),
                  "ocr_artifact_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                  "ocr_workflow_status": workflow_status, "ocr_review_status": "unreviewed",
                  "machine_pass": "false", "human_verified": "false", "claim_extraction_allowed": "false"})
    database_path = database_path.resolve()
    exists = False
    if database_path.exists():
        with closing(sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)) as connection:
            exists = _existing(connection, document)
    status = "already_registered" if exists else "would_register"
    if apply and not exists:
        store = SQLiteEvidenceStore(database_path)
        store.init_schema()
        with closing(store.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if _existing(connection, document):
                status = "already_registered"
            else:
                run = SearchRun(run_id="ocr-registration-" + document_id, timestamp=access_date,
                    input_file=str(manifest_path), source_ids=[source_id], parameters={"operation": "register-ocr-source"},
                    metadata={"manifest_sha256": document.metadata["ocr_artifact_manifest_sha256"]})
                encoded = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
                connection.execute("INSERT INTO search_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (run.run_id, run.timestamp, run.input_file, encoded(run.source_ids), encoded(run.parameters), encoded(run.metadata), encoded(asdict(run))))
                connection.execute("INSERT INTO source_documents (document_id, run_id, source_id, title, url, access_date, local_path, content_hash, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (document_id, run.run_id, source_id, document.title, document.url, access_date, str(original_path), digest, encoded(asdict(document))))
                status = "registered"
    return {"status": status, "apply": apply, "database_path": str(database_path), "source_document": asdict(document),
            "page_count": len(pages), "machine_pass": False, "human_verified": False, "claim_extraction_allowed": False}
