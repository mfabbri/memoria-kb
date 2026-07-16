from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..raw_store import slugify_identifier


def register_manual_document(
    *,
    file_path: Path,
    source_id: str,
    title: str,
    url: str = "",
    archival_reference: str = "",
    access_date: str = "",
    review_status: str = "unreviewed",
    sidecar_path: Path | None = None,
    extra_metadata: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    file_path = Path(file_path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Documento manuale non trovato: {file_path}")
    if not source_id.strip():
        raise ValueError("source_id obbligatorio.")
    if not title.strip():
        raise ValueError("title obbligatorio.")
    if not url.strip() and not archival_reference.strip():
        raise ValueError("Specificare almeno url o archival_reference.")

    sidecar_path = Path(sidecar_path) if sidecar_path is not None else file_path.with_name("document.yaml")
    if sidecar_path.exists() and not overwrite:
        raise FileExistsError(f"Sidecar gia' presente: {sidecar_path}")

    media_type = _guess_media_type(file_path)
    content_hash = _sha256_file(file_path)
    document_id = f"{slugify_identifier(source_id)}:{content_hash[:16]}"
    payload = {
        "document_id": document_id,
        "source_id": source_id.strip(),
        "title": title.strip(),
        "url": url.strip(),
        "access_date": access_date.strip() or datetime.now(UTC).date().isoformat(),
        "media_type": media_type,
        "local_path": str(file_path),
        "content_hash": content_hash,
        "raw_text": "",
        "document_dir": str(file_path.parent),
        "metadata": {
            "access_mode": "manual_upload",
            "archival_reference": archival_reference.strip(),
            "extraction_status": _default_extraction_status(media_type),
            "review_status": review_status.strip() or "unreviewed",
        },
    }
    if extra_metadata:
        payload["metadata"].update(extra_metadata)
    sidecar_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {
        "@type": "ManualDocumentRegistration",
        "sidecar_path": str(sidecar_path),
        "document": payload,
    }


def _default_extraction_status(media_type: str) -> str:
    if media_type.startswith("image/"):
        return "manual_ocr_required"
    return "manual_review_required"


def _guess_media_type(path: Path) -> str:
    media_type, _encoding = mimetypes.guess_type(str(path))
    return media_type or "application/octet-stream"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra un documento manuale creando un sidecar document.yaml.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--url", default="")
    parser.add_argument("--archival-reference", default="")
    parser.add_argument("--access-date", default="")
    parser.add_argument("--review-status", default="unreviewed")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result = register_manual_document(
        file_path=Path(args.file),
        source_id=args.source_id,
        title=args.title,
        url=args.url,
        archival_reference=args.archival_reference,
        access_date=args.access_date,
        review_status=args.review_status,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
