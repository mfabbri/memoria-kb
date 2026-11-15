"""Preview explicit, review-only relations between catalogued SourceDocuments."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .source_document_catalog import resolve_source_documents

ALLOWED_RELATIONS = {"local_capture_of", "original_page_of", "derived_from"}


def build_source_document_lineage_preview(*, links_json: Path, catalog_db: Path,
                                          output_dir: Path) -> dict[str, Any]:
    path = links_json.resolve(strict=True)
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid SourceDocumentLineageRequest JSON") from error
    if not isinstance(payload, dict) or payload.get("@type") != "SourceDocumentLineageRequest":
        raise ValueError("Expected SourceDocumentLineageRequest")
    links = payload.get("links")
    if not isinstance(links, list) or not links:
        raise ValueError("links must be a non-empty list")
    normalized = []
    keys = set()
    for item in links:
        if not isinstance(item, dict):
            raise ValueError("Each link must be an object")
        source = _required(item.get("source_document_id"), "source_document_id")
        target = _required(item.get("related_source_document_id"), "related_source_document_id")
        relation = _required(item.get("relation_type"), "relation_type")
        rationale = _required(item.get("rationale"), "rationale")
        evidence = _required(item.get("provenance_ref"), "provenance_ref")
        if source == target:
            raise ValueError("A lineage relation cannot point to itself")
        if relation not in ALLOWED_RELATIONS:
            raise ValueError(f"Unsupported relation_type: {relation}")
        key = (source, target, relation)
        if key in keys:
            raise ValueError("Duplicate lineage link")
        keys.add(key)
        normalized.append({"source_document_id": source, "related_source_document_id": target,
                           "relation_type": relation, "rationale": rationale,
                           "provenance_ref": evidence, "review_status": "unreviewed"})
    catalog = resolve_source_documents(catalog_db,
        {item[k] for item in normalized for k in ("source_document_id", "related_source_document_id")})
    report = {"@type": "CandidateSourceDocumentLineageSet", "schema_version": "1.0",
        "request_input": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
        "catalog_snapshot": catalog, "links": normalized, "preview_only": True,
        "canonical_write_allowed": False, "catalog_modified": False}
    out = output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("output_dir must be new or empty")
    out.mkdir(parents=True, exist_ok=True)
    (out / "source-document-lineage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "source-document-lineage.md").write_text("# Candidate SourceDocument lineage\n\n" +
        "\n".join(f"- `{x['source_document_id']}` — {x['relation_type']} — `{x['related_source_document_id']}`; unreviewed; {x['provenance_ref']}" for x in normalized) +
        "\n\nPreview only; catalog unchanged.\n", encoding="utf-8")
    return report


def _required(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()
