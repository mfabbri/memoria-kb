from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import monotonic
from typing import Any, Callable

from .inventory import build_raw_document_inventory


def extract_document_metadata(
    *,
    root_dir: Path,
    output_dir: Path,
    progress_callback: Callable[[str], None] | None = None,
    progress_every: int = 500,
    progress_seconds: float = 30.0,
) -> dict[str, Any]:
    inventory_progress = None
    if progress_callback is not None:
        def inventory_progress(message: str) -> None:
            progress_callback(f"metadata inventory {message}")

    inventory = build_raw_document_inventory(
        root_dir=root_dir,
        progress_callback=inventory_progress,
        progress_every=progress_every,
        progress_seconds=progress_seconds,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    processed = []
    documents = inventory.get("documents", [])
    total = len(documents) if isinstance(documents, list) else 0
    reporter = _ProgressReporter(
        progress_callback,
        item_interval=progress_every,
        seconds_interval=progress_seconds,
    )
    reporter.report(f"metadata write start count={total}", force=True)
    for index, document in enumerate(documents if isinstance(documents, list) else [], start=1):
        if not isinstance(document, dict):
            reporter.report(f"metadata write {index}/{total} processed={len(processed)} skipped=non_dict")
            continue
        metadata = _processed_metadata(document)
        metadata_path = output_dir / _metadata_relative_path(metadata)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        processed.append(
            {
                "source_document_id": metadata["source_document_id"],
                "metadata_path": str(metadata_path),
                "document_class": metadata["document_class"],
                "claim_eligible": metadata["claim_eligible"],
            }
        )
        reporter.report(f"metadata write {index}/{total} processed={len(processed)}")
    reporter.report(f"metadata write done processed={len(processed)}", force=True)

    return {
        "@type": "ProcessedDocumentMetadataSet",
        "root_dir": str(root_dir),
        "output_dir": str(output_dir),
        "document_count": len(processed),
        "documents": processed,
    }


def _processed_metadata(document: dict[str, Any]) -> dict[str, Any]:
    media_type = str(document.get("media_type", ""))
    status = str(document.get("status", ""))
    sidecar_metadata = document.get("sidecar_metadata", {}) if isinstance(document.get("sidecar_metadata"), dict) else {}
    document_class = _document_class(document)
    claim_eligible = document_class not in {"result_page", "reference_page", "image_scan", "unknown"}
    if "document_class" in sidecar_metadata:
        document_class = str(sidecar_metadata.get("document_class") or document_class)
    if _has_value(sidecar_metadata.get("claim_eligible")):
        claim_eligible = _as_bool(sidecar_metadata.get("claim_eligible"))
    text_status = "not_extracted"
    extraction_status = str(document.get("extraction_status", ""))
    if media_type.startswith("image/"):
        extraction_status = extraction_status or "manual_ocr_required"
    else:
        extraction_status = extraction_status or "metadata_only"
    if document_class in {"result_page", "reference_page"}:
        claim_eligible = False
        extraction_status = "metadata_only"

    metadata = {
        "@type": "ProcessedDocumentMetadata",
        "source_id": str(document.get("source_id", "")),
        "source_document_id": _source_document_id(document),
        "title": str(document.get("title", "")),
        "document_class": document_class,
        "claim_eligible": claim_eligible,
        "status": status,
        "media_type": media_type,
        "raw_file": str(document.get("raw_file", "")),
        "sidecar_file": str(document.get("sidecar_file", "")),
        "sha256": str(document.get("sha256", "")),
        "url": str(document.get("url", "")),
        "archival_reference": str(document.get("archival_reference", "")),
        "access_date": str(document.get("access_date", "")),
        "review_status": str(document.get("review_status", "")) or "unreviewed",
        "extraction_status": extraction_status,
        "text_status": text_status,
    }
    for key, value in sidecar_metadata.items():
        if key in metadata or not _has_value(value):
            continue
        metadata[key] = value
    return metadata


def _document_class(document: dict[str, Any]) -> str:
    status = str(document.get("status", ""))
    media_type = str(document.get("media_type", ""))
    title = str(document.get("title", "")).casefold()
    raw_file = str(document.get("raw_file", "")).casefold()
    if media_type.startswith("image/"):
        return "image_scan"
    if "search_result" in status or "search" in title or "advanced-search" in str(document.get("url", "")):
        return "result_page"
    if status == "reference_only":
        return "reference_page"
    if media_type in {"text/html", "application/xhtml+xml"}:
        return "html_document"
    if media_type == "application/pdf" or raw_file.endswith(".pdf"):
        return "pdf_document"
    if (
        media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or raw_file.endswith(".docx")
    ):
        return "word_document"
    if media_type in {"text/csv", "application/vnd.ms-excel"} or raw_file.endswith((".csv", ".xls", ".xlsx")):
        return "tabular_document"
    if status in {"manual_upload", "stored"}:
        return "generic_document"
    return "unknown"


def _source_document_id(document: dict[str, Any]) -> str:
    value = str(document.get("source_document_id", "")).strip()
    if value:
        return value
    source_id = str(document.get("source_id", "unknown")).strip() or "unknown"
    digest = str(document.get("sha256", ""))[:16] or "unknown"
    return f"{source_id}:{digest}"


def _has_value(value: Any) -> bool:
    return value not in (None, "")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "si", "sì"}


def _metadata_relative_path(metadata: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(metadata.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(metadata.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.metadata.json"


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


class _ProgressReporter:
    def __init__(
        self,
        callback: Callable[[str], None] | None,
        *,
        item_interval: int,
        seconds_interval: float,
    ) -> None:
        self.callback = callback
        self.item_interval = max(1, int(item_interval))
        self.seconds_interval = max(0.0, float(seconds_interval))
        self.last_item = 0
        self.last_time = monotonic()

    def report(self, message: str, *, force: bool = False) -> None:
        if self.callback is None:
            return
        item = _progress_item(message)
        now = monotonic()
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Estrae metadati processati dai documenti raw/cache senza OCR o claim.")
    parser.add_argument("--root-dir", default="data/raw")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--summary-json", default="risultati/document_analysis/document_metadata_extraction.json")
    args = parser.parse_args()

    summary = extract_document_metadata(root_dir=Path(args.root_dir), output_dir=Path(args.output_dir))
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Metadati processati scritti in {args.output_dir}")
    print(f"Summary JSON scritto in {summary_path}")
    print(f"Documenti processati: {summary['document_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
