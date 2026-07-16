from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Callable

import yaml

SIDECAR_NAMES = {"document.yaml", "document.yml", "document.json"}
SIDECAR_SUFFIXES = {".document.yaml", ".document.yml", ".document.json"}


def build_raw_document_inventory(
    *,
    root_dir: Path,
    progress_callback: Callable[[str], None] | None = None,
    progress_every: int = 500,
    progress_seconds: float = 30.0,
) -> dict[str, Any]:
    root_dir = Path(root_dir)
    records = []
    errors = []
    if root_dir.exists():
        progress = _ProgressReporter(
            progress_callback,
            item_interval=progress_every,
            seconds_interval=progress_seconds,
        )
        sidecar_paths = sorted(_sidecar_paths(root_dir))
        progress.report(f"inventory sidecars start count={len(sidecar_paths)}", force=True)
        for index, sidecar_path in enumerate(sidecar_paths, start=1):
            record, error = _record_from_sidecar(root_dir=root_dir, sidecar_path=sidecar_path)
            if error:
                errors.append(error)
                progress.report(
                    f"inventory sidecar_error {index}/{len(sidecar_paths)} path={_relative_or_str(sidecar_path, root_dir)} "
                    f"error={error.get('error_type', '')}",
                    force=True,
                )
            if record:
                records.append(record)
            progress.report(f"inventory sidecars {index}/{len(sidecar_paths)} records={len(records)} errors={len(errors)}")
        sidecar_content_paths = _sidecar_content_paths(root_dir=root_dir, records=records)
        file_paths = sorted(path for path in root_dir.rglob("*") if path.is_file())
        progress.report(f"inventory files start count={len(file_paths)} sidecar_content={len(sidecar_content_paths)}", force=True)
        for index, file_path in enumerate(file_paths, start=1):
            if _is_sidecar_path(file_path):
                progress.report(f"inventory files {index}/{len(file_paths)} records={len(records)} errors={len(errors)}")
                continue
            if file_path in sidecar_content_paths:
                progress.report(f"inventory files {index}/{len(file_paths)} records={len(records)} errors={len(errors)}")
                continue
            record, error = _record_from_file(root_dir=root_dir, file_path=file_path)
            if error:
                errors.append(error)
                progress.report(
                    f"inventory file_error {index}/{len(file_paths)} path={_relative_or_str(file_path, root_dir)} "
                    f"error={error.get('error_type', '')}",
                    force=True,
                )
            records.append(record)
            progress.report(f"inventory files {index}/{len(file_paths)} records={len(records)} errors={len(errors)}")
        progress.report(f"inventory done records={len(records)} errors={len(errors)}", force=True)

    return {
        "@type": "RawDocumentInventory",
        "root_dir": str(root_dir),
        "document_count": len(records),
        "error_count": len(errors),
        "errors": errors,
        "documents": records,
    }


def render_raw_document_inventory_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Raw document inventory",
        "",
        f"- Root: `{inventory.get('root_dir', '')}`",
        f"- Documenti: `{inventory.get('document_count', 0)}`",
        f"- Errori lettura: `{inventory.get('error_count', 0)}`",
        "",
    ]
    errors = inventory.get("errors", [])
    if isinstance(errors, list) and errors:
        lines.extend(["## Errori lettura", ""])
        for error in errors:
            if not isinstance(error, dict):
                continue
            lines.append(
                f"- `{error.get('path', '')}`: `{error.get('error_type', '')}` - {error.get('message', '')}"
            )
        lines.append("")
    lines.extend(["## Documenti", ""])
    documents = inventory.get("documents", [])
    if not documents:
        lines.append("Nessun documento trovato.")
    for document in documents:
        title = document.get("title") or document.get("source_document_id") or document.get("raw_file") or "(senza titolo)"
        lines.extend(
            [
                f"### {title}",
                "",
                f"- Stato: `{document.get('status', '')}`",
                f"- Fonte: `{document.get('source_id', '')}`",
                f"- Document ID: `{document.get('source_document_id', '')}`",
                f"- Media type: `{document.get('media_type', '')}`",
                f"- Raw file: `{document.get('raw_file', '')}`",
                f"- Sidecar: `{document.get('sidecar_file', '')}`",
                f"- SHA256: `{document.get('sha256', '')}`",
                f"- Estrazione: `{document.get('extraction_status', '')}`",
                f"- Revisione: `{document.get('review_status', '')}`",
                f"- URL/Riferimento: {document.get('url') or document.get('archival_reference') or '(non disponibile)'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_raw_document_inventory(*, root_dir: Path, output_json: Path, output_md: Path) -> dict[str, Any]:
    inventory = build_raw_document_inventory(root_dir=root_dir)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_raw_document_inventory_markdown(inventory), encoding="utf-8")
    return inventory


def _sidecar_paths(root_dir: Path) -> list[Path]:
    return [path for path in root_dir.rglob("*") if path.is_file() and _is_sidecar_path(path)]


def _is_sidecar_path(path: Path) -> bool:
    if path.name in SIDECAR_NAMES:
        return True
    return any(path.name.endswith(suffix) for suffix in SIDECAR_SUFFIXES)


def _sidecar_content_paths(*, root_dir: Path, records: list[dict[str, Any]]) -> set[Path]:
    paths = set()
    for record in records:
        raw_file = str(record.get("raw_file", "")).strip()
        if not raw_file:
            continue
        raw_path = Path(raw_file)
        if not raw_path.is_absolute():
            raw_path = root_dir / raw_path
        paths.add(raw_path)
    return paths


def _record_from_sidecar(*, root_dir: Path, sidecar_path: Path) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    try:
        payload = _load_sidecar(sidecar_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return None, _read_error(
            path=sidecar_path,
            root_dir=root_dir,
            kind="sidecar_read_error",
            exc=exc,
        )
    metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
    document_dir = Path(str(payload.get("document_dir") or sidecar_path.parent))
    local_path = str(payload.get("local_path") or payload.get("file") or metadata.get("local_path") or metadata.get("file") or "").strip()
    content_path = _content_path_for_sidecar(
        sidecar_path=sidecar_path,
        document_dir=document_dir,
        declared_path=local_path,
    )

    has_content = content_path.exists() and content_path.is_file()
    error = None
    if has_content:
        sha256, error = _safe_sha256_file(path=content_path, root_dir=root_dir, kind="content_read_error")
    else:
        sha256 = str(payload.get("content_hash", "")).strip()
    status = "stored" if has_content else "reference_only"
    if error:
        status = "read_error"
    if metadata.get("access_mode") == "reference_only":
        status = "reference_only"
    if metadata.get("access_mode") == "manual_upload":
        status = "manual_upload"
    if metadata.get("provenance") == "online_source_acquisition" and has_content:
        status = "stored"

    return {
        "status": status,
        "raw_file": _relative_or_str(content_path, root_dir) if has_content else "",
        "sidecar_file": _relative_or_str(sidecar_path, root_dir),
        "document_dir": str(document_dir),
        "source_id": str(payload.get("source_id") or metadata.get("source_id") or ""),
        "source_document_id": str(payload.get("document_id") or metadata.get("document_id") or metadata.get("source_document_id") or ""),
        "title": str(payload.get("title") or metadata.get("title") or ""),
        "url": str(payload.get("url") or metadata.get("url") or metadata.get("source_url") or ""),
        "archival_reference": str(metadata.get("archival_reference", "")),
        "access_date": str(payload.get("access_date") or metadata.get("access_date") or ""),
        "media_type": str(payload.get("media_type") or metadata.get("media_type") or "") or _guess_media_type(content_path),
        "sha256": sha256,
        "review_status": str(metadata.get("review_status", "")),
        "extraction_status": str(metadata.get("extraction_status", "")),
        "sidecar_metadata": metadata,
    }, error


def _record_from_file(*, root_dir: Path, file_path: Path) -> tuple[dict[str, Any], dict[str, str] | None]:
    sha256, error = _safe_sha256_file(path=file_path, root_dir=root_dir, kind="file_read_error")
    return {
        "status": "read_error" if error else "file_without_sidecar",
        "raw_file": _relative_or_str(file_path, root_dir),
        "sidecar_file": "",
        "document_dir": str(file_path.parent),
        "source_id": _source_id_from_path(root_dir=root_dir, file_path=file_path),
        "source_document_id": "",
        "title": file_path.name,
        "url": "",
        "archival_reference": "",
        "access_date": "",
        "media_type": _guess_media_type(file_path),
        "sha256": sha256,
        "review_status": "",
        "extraction_status": "",
    }, error


def _content_path_for_sidecar(*, sidecar_path: Path, document_dir: Path, declared_path: str) -> Path:
    sibling_path = _per_file_sidecar_content_path(sidecar_path)
    if sibling_path is not None and sibling_path.exists() and sibling_path.is_file():
        return sibling_path
    content_path = Path(declared_path) if declared_path else document_dir / "content.txt"
    if not content_path.is_absolute():
        content_path = document_dir / content_path
    return content_path


def _per_file_sidecar_content_path(sidecar_path: Path) -> Path | None:
    name = sidecar_path.name
    for suffix in sorted(SIDECAR_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix):
            return sidecar_path.with_name(name[: -len(suffix)])
    return None


def _load_sidecar(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        payload = json.loads(text)
    else:
        payload = yaml.safe_load(text) or {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_sha256_file(*, path: Path, root_dir: Path, kind: str) -> tuple[str, dict[str, str] | None]:
    try:
        return _sha256_file(path), None
    except OSError as exc:
        return "", _read_error(path=path, root_dir=root_dir, kind=kind, exc=exc)


def _read_error(*, path: Path, root_dir: Path, kind: str, exc: BaseException) -> dict[str, str]:
    return {
        "kind": kind,
        "path": _relative_or_str(path, root_dir),
        "error_type": type(exc).__name__,
        "message": str(exc),
    }


class _ProgressReporter:
    def __init__(self, callback: Callable[[str], None] | None, *, item_interval: int = 500, seconds_interval: float = 30.0) -> None:
        self.callback = callback
        self.item_interval = item_interval
        self.seconds_interval = seconds_interval
        self.last_item = 0
        self.last_time = time.monotonic()

    def report(self, message: str, *, force: bool = False) -> None:
        if self.callback is None:
            return
        item = _progress_item(message)
        now = time.monotonic()
        if force or item - self.last_item >= self.item_interval or now - self.last_time >= self.seconds_interval:
            self.callback(message)
            self.last_item = item
            self.last_time = now


def _progress_item(message: str) -> int:
    for token in message.split():
        if "/" not in token:
            continue
        current, _sep, _total = token.partition("/")
        try:
            return int(current)
        except ValueError:
            continue
    return 0


def _guess_media_type(path: Path) -> str:
    media_type, _encoding = mimetypes.guess_type(str(path))
    return media_type or "application/octet-stream"


def _relative_or_str(path: Path, root_dir: Path) -> str:
    try:
        return str(path.relative_to(root_dir))
    except ValueError:
        return str(path)


def _source_id_from_path(*, root_dir: Path, file_path: Path) -> str:
    try:
        return file_path.relative_to(root_dir).parts[0].replace("-", "_")
    except (ValueError, IndexError):
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Costruisce un inventario offline dei documenti raw/cache.")
    parser.add_argument("--root-dir", default="data/raw")
    parser.add_argument("--output-json", default="risultati/document_analysis/document_inventory.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/document_inventory.md")
    args = parser.parse_args()

    inventory = write_raw_document_inventory(
        root_dir=Path(args.root_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"Inventario JSON scritto in {args.output_json}")
    print(f"Inventario Markdown scritto in {args.output_md}")
    print(f"Documenti inventariati: {inventory['document_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
