"""Preview-first export from structured OCR evidence to Markdown."""

from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any

from .document_structure import reconstruct_document_structure, render_document_structure_markdown


_CHECKPOINT_MANIFEST_FILENAME = "structured-checkpoint.manifest.json"
_CHECKPOINT_MANIFEST_TYPE = "StructuredMarkdownCheckpoint"
_CHECKPOINT_MANIFEST_VERSION = "1.0"


def export_structured_pages_markdown(
    *, root_dir: Path, output_dir: Path, profile: str, apply: bool = False
) -> dict[str, Any]:
    """Plan or write Markdown derived from ``OcrPageEvidence`` JSON files."""
    root = Path(root_dir)
    destination = Path(output_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Root evidenze OCR non trovata: {root}")
    started = time.perf_counter()
    documents: list[dict[str, Any]] = []
    planned: set[Path] = set()
    evidence_paths = sorted(root.rglob("*.evidence.json"))
    checkpoint_id = _batch_checkpoint(root, evidence_paths)
    checkpoint_manifest = _checkpoint_manifest(
        root=root,
        profile=profile,
        checkpoint_id=checkpoint_id,
        item_count=len(evidence_paths),
    )
    checkpoint_status = _checkpoint_manifest_status(
        manifest_path=destination / _CHECKPOINT_MANIFEST_FILENAME,
        expected=checkpoint_manifest,
    )
    if apply and checkpoint_status["status"] == "mismatch_existing_manifest":
        return _export_report(
            root=root,
            destination=destination,
            profile=profile,
            apply=apply,
            checkpoint_id=checkpoint_id,
            evidence_count=len(evidence_paths),
            checkpoint_manifest=checkpoint_status,
            documents=[],
            started=started,
        )
    if apply and checkpoint_status["status"] == "would_create":
        _create_checkpoint_manifest(checkpoint_status["path"], checkpoint_manifest)
        checkpoint_status = {**checkpoint_status, "status": "created"}
    for evidence_path in evidence_paths:
        documents.append(_export_one(evidence_path=evidence_path, output_dir=destination, profile=profile, apply=apply, planned=planned))
    return _export_report(
        root=root,
        destination=destination,
        profile=profile,
        apply=apply,
        checkpoint_id=checkpoint_id,
        evidence_count=len(evidence_paths),
        checkpoint_manifest=checkpoint_status,
        documents=documents,
        started=started,
    )


def _export_report(
    *,
    root: Path,
    destination: Path,
    profile: str,
    apply: bool,
    checkpoint_id: str,
    evidence_count: int,
    checkpoint_manifest: dict[str, Any],
    documents: list[dict[str, Any]],
    started: float,
) -> dict[str, Any]:
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    total = len(documents)
    counts = {status: sum(item.get("status") == status for item in documents) for status in sorted({item.get("status") for item in documents})}
    return {
        "@type": "StructuredMarkdownExportReport",
        "root_dir": str(root),
        "output_dir": str(destination),
        "profile": profile,
        "apply": apply,
        "checkpoint_id": checkpoint_id,
        "checkpoint_item_count": evidence_count,
        "checkpoint_manifest": checkpoint_manifest,
        "documents": documents,
        "summary": {"total": total, "counts_by_status": counts},
        "duration_ms": duration_ms,
        "throughput_items_per_second": round(total / (duration_ms / 1000), 3) if duration_ms else 0.0,
    }


def _batch_checkpoint(root: Path, evidence_paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for evidence_path in evidence_paths:
        relative_path = evidence_path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative_path).to_bytes(4, "big"))
        digest.update(relative_path)
        payload = evidence_path.read_bytes()
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return f"sha256:{digest.hexdigest()}"


def _checkpoint_manifest(*, root: Path, profile: str, checkpoint_id: str, item_count: int) -> dict[str, Any]:
    return {
        "@type": _CHECKPOINT_MANIFEST_TYPE,
        "schema_version": _CHECKPOINT_MANIFEST_VERSION,
        "root": str(root.resolve()),
        "profile": profile,
        "checkpoint_id": checkpoint_id,
        "item_count": item_count,
    }


def _checkpoint_manifest_status(*, manifest_path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    status: dict[str, Any] = {"path": str(manifest_path), "manifest": expected}
    if not manifest_path.exists():
        return {**status, "status": "would_create"}
    try:
        actual = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            **status,
            "status": "mismatch_existing_manifest",
            "reason": f"manifest non leggibile: {type(exc).__name__}: {exc}",
        }
    if not isinstance(actual, dict):
        return {**status, "status": "mismatch_existing_manifest", "reason": "manifest non e' un oggetto JSON"}
    mismatches = {
        field: {"expected": expected[field], "actual": actual.get(field)}
        for field in expected
        if actual.get(field) != expected[field]
    }
    if mismatches:
        return {**status, "status": "mismatch_existing_manifest", "mismatches": mismatches}
    return {**status, "status": "existing_compatible"}


def _create_checkpoint_manifest(manifest_path: str, manifest: dict[str, Any]) -> None:
    target = Path(manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _export_one(*, evidence_path: Path, output_dir: Path, profile: str, apply: bool, planned: set[Path]) -> dict[str, Any]:
    base = {"evidence_path": str(evidence_path), "profile": profile}
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {**base, "status": "skipped_invalid_json", "reason": f"{type(exc).__name__}: {exc}"}
    if not isinstance(payload, dict) or payload.get("@type") != "OcrPageEvidence":
        return {**base, "status": "skipped_invalid_evidence", "reason": "OcrPageEvidence non valido"}
    try:
        structure = reconstruct_document_structure(evidence=payload, profile=profile)
    except (TypeError, ValueError) as exc:
        return {**base, "status": "skipped_invalid_evidence", "reason": str(exc)}
    page_id = structure.page_id
    source_document_id = _safe_path_part(str(payload.get("source_document_id", page_id)))
    target = output_dir / source_document_id / f"{_safe_path_part(page_id)}.md"
    item = {**base, "source_document_id": source_document_id, "page_id": page_id, "output_path": str(target)}
    normalized = target.resolve()
    try:
        normalized.relative_to(output_dir.resolve())
    except ValueError:
        return {**item, "status": "skipped_unsafe_output", "reason": "output fuori dalla directory richiesta"}
    if normalized in planned:
        return {**item, "status": "skipped_duplicate_output", "reason": "output duplicato"}
    planned.add(normalized)
    if target.exists():
        return {**item, "status": "skipped_existing_output", "reason": "output gia' presente"}
    if not apply:
        return {**item, "status": "would_write", "block_count": len(structure.blocks)}
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(render_document_structure_markdown(structure))
    except FileExistsError:
        return {**item, "status": "skipped_existing_output", "reason": "output creato durante l'esportazione"}
    return {**item, "status": "written", "block_count": len(structure.blocks)}


def _safe_path_part(value: str) -> str:
    candidate = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-")
    return candidate if candidate not in {"", ".", ".."} else "unknown"
