from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

from ..raw_store import slugify_identifier


def register_html_documents(
    *,
    root_dir: Path,
    source_id: str,
    base_url: str = "",
    access_date: str = "",
    review_status: str = "unreviewed",
    overwrite: bool = False,
) -> dict[str, Any]:
    root_dir = Path(root_dir)
    if not root_dir.exists() or not root_dir.is_dir():
        raise FileNotFoundError(f"Cartella HTML non trovata: {root_dir}")
    if not source_id.strip():
        raise ValueError("source_id obbligatorio.")

    sidecar_root = root_dir / ".document_sidecars"
    existing_sidecars = _existing_sidecars_by_local_path(sidecar_root)
    registered = []
    skipped = []
    for html_path in _html_paths(root_dir, sidecar_root=sidecar_root):
        payload = _sidecar_payload(
            html_path=html_path,
            root_dir=root_dir,
            source_id=source_id,
            base_url=base_url,
            access_date=access_date,
            review_status=review_status,
        )
        sidecar_path = existing_sidecars.get(str(html_path)) or sidecar_root / _safe_sidecar_dir(payload["document_id"]) / "document.yaml"
        if str(html_path) in existing_sidecars and not overwrite:
            skipped.append({"raw_file": str(html_path), "sidecar_path": str(sidecar_path), "reason": "sidecar_exists"})
            continue
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
        registered.append(
            {
                "raw_file": str(html_path),
                "sidecar_path": str(sidecar_path),
                "source_document_id": payload["document_id"],
                "title": payload["title"],
                "url": payload["url"],
            }
        )

    return {
        "@type": "HtmlDocumentRegistrationBatch",
        "root_dir": str(root_dir),
        "source_id": source_id.strip(),
        "registered_count": len(registered),
        "skipped_count": len(skipped),
        "registered": registered,
        "skipped": skipped,
    }


def _existing_sidecars_by_local_path(sidecar_root: Path) -> dict[str, Path]:
    existing = {}
    if not sidecar_root.exists():
        return existing
    for sidecar_path in sidecar_root.rglob("document.yaml"):
        try:
            payload = yaml.safe_load(sidecar_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(payload, dict) and str(payload.get("local_path", "")).strip():
            existing[str(Path(str(payload["local_path"])))] = sidecar_path
    return existing


def _html_paths(root_dir: Path, *, sidecar_root: Path) -> list[Path]:
    paths = []
    for path in root_dir.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in {".html", ".htm"}:
            continue
        if _is_relative_to(path, sidecar_root):
            continue
        paths.append(path)
    return sorted(paths)


def _sidecar_payload(
    *,
    html_path: Path,
    root_dir: Path,
    source_id: str,
    base_url: str,
    access_date: str,
    review_status: str,
) -> dict[str, Any]:
    content_hash = _sha256_file(html_path)
    title = _html_title(html_path) or html_path.stem.replace("-", " ").replace("_", " ").strip() or html_path.name
    document_id = f"{slugify_identifier(source_id)}-{slugify_identifier(_relative_without_suffix(html_path, root_dir))}-{content_hash[:12]}"
    return {
        "document_id": document_id,
        "source_id": source_id.strip(),
        "title": title,
        "url": _document_url(html_path=html_path, root_dir=root_dir, base_url=base_url),
        "access_date": access_date.strip() or datetime.now(UTC).date().isoformat(),
        "media_type": "text/html",
        "local_path": str(html_path),
        "content_hash": content_hash,
        "raw_text": "",
        "document_dir": str(html_path.parent),
        "metadata": {
            "access_mode": "manual_upload",
            "archival_reference": "",
            "extraction_status": "manual_review_required",
            "review_status": review_status.strip() or "unreviewed",
            "registration_method": "html_batch",
        },
    }


def _relative_without_suffix(path: Path, root_dir: Path) -> str:
    relative = path.relative_to(root_dir)
    return str(relative.with_suffix(""))


def _document_url(*, html_path: Path, root_dir: Path, base_url: str) -> str:
    if not base_url.strip():
        return ""
    base = base_url.strip().rstrip("/") + "/"
    relative = html_path.relative_to(root_dir).as_posix()
    if relative.endswith("/index.html") or relative.endswith("/index.htm"):
        relative = relative.rsplit("/", 1)[0] + "/"
    quoted = "/".join(quote(part) for part in relative.split("/"))
    return base + quoted


def _html_title(path: Path) -> str:
    parser = _TitleParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.close()
    return " ".join(parser.title.split())


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self._parts: list[str] = []

    @property
    def title(self) -> str:
        return "".join(self._parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._parts.append(data)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_sidecar_dir(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "document"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra HTML locali creando sidecar document.yaml derivati.")
    parser.add_argument("--root-dir", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--access-date", default="")
    parser.add_argument("--review-status", default="unreviewed")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result = register_html_documents(
        root_dir=Path(args.root_dir),
        source_id=args.source_id,
        base_url=args.base_url,
        access_date=args.access_date,
        review_status=args.review_status,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
