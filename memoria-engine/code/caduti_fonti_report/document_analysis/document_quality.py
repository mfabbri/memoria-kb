from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import monotonic
from typing import Any, Callable


def assess_document_quality(
    *,
    metadata_dir: Path,
    text_dir: Path,
    output_dir: Path,
    progress_callback: Callable[[str], None] | None = None,
    progress_every: int = 500,
    progress_seconds: float = 30.0,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    processed = []
    metadata_paths = sorted(metadata_dir.rglob("*.metadata.json"))
    total = len(metadata_paths)
    reporter = _ProgressReporter(
        progress_callback,
        item_interval=progress_every,
        seconds_interval=progress_seconds,
    )
    reporter.report(f"quality metadata start count={total}", force=True)
    for index, metadata_path in enumerate(metadata_paths, start=1):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            reporter.report(f"quality metadata {index}/{total} processed={len(processed)} skipped=non_dict")
            continue
        text_payload = _load_text_payload(metadata=metadata, text_dir=text_dir)
        quality = _quality_assessment(metadata=metadata, text_payload=text_payload, metadata_path=metadata_path)
        quality_path = output_dir / _quality_relative_path(quality)
        quality_path.parent.mkdir(parents=True, exist_ok=True)
        quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
        processed.append(
            {
                "source_document_id": quality["source_document_id"],
                "quality_path": str(quality_path),
                "document_class": quality["document_class"],
                "quality_status": quality["quality_status"],
                "classification": quality["classification"],
                "claim_allowed": quality["claim_allowed"],
            }
        )
        reporter.report(
            "quality metadata "
            f"{index}/{total} processed={len(processed)} "
            f"class={quality['document_class']} status={quality['quality_status']}"
        )
    reporter.report(f"quality metadata done processed={len(processed)}", force=True)

    return {
        "@type": "DocumentQualityAssessmentSet",
        "metadata_dir": str(metadata_dir),
        "text_dir": str(text_dir),
        "output_dir": str(output_dir),
        "document_count": len(processed),
        "documents": processed,
    }


def _quality_assessment(
    *,
    metadata: dict[str, Any],
    text_payload: dict[str, Any] | None,
    metadata_path: Path,
) -> dict[str, Any]:
    document_class = str(metadata.get("document_class", ""))
    text_status = str((text_payload or {}).get("text_status", metadata.get("text_status", ""))) or "not_extracted"
    text_length = int((text_payload or {}).get("text_length", 0) or 0)
    quality_status, classification, reasons = _classify_quality(
        document_class=document_class,
        text_status=text_status,
        text_length=text_length,
    )
    return {
        "@type": "DocumentQualityAssessment",
        "source_id": str(metadata.get("source_id", "")),
        "source_document_id": str(metadata.get("source_document_id", "")),
        "title": str(metadata.get("title", "")),
        "document_class": document_class,
        "classification": classification,
        "quality_status": quality_status,
        "claim_allowed": False,
        "review_status": str(metadata.get("review_status", "")) or "unreviewed",
        "raw_file": str(metadata.get("raw_file", "")),
        "metadata_file": str(metadata_path),
        "text_file": str((text_payload or {}).get("_text_file", "")),
        "media_type": str(metadata.get("media_type", "")),
        "sha256": str(metadata.get("sha256", "")),
        "url": str(metadata.get("url", "")),
        "archival_reference": str(metadata.get("archival_reference", "")),
        "access_date": str(metadata.get("access_date", "")),
        "text_status": text_status,
        "text_length": text_length,
        "reasons": reasons,
    }


def _classify_quality(*, document_class: str, text_status: str, text_length: int) -> tuple[str, str, list[str]]:
    if document_class == "result_page":
        return "audit_only", "result_page", ["result_page_not_sufficient_for_claims"]
    if document_class == "reference_page":
        return "metadata_only", "reference_page", ["reference_only_document"]
    if document_class == "image_scan" and text_status == "extracted" and text_length > 0:
        return "ready_for_manual_review", "image_transcription", ["transcription_registered_for_manual_review"]
    if document_class == "image_scan":
        return "manual_ocr_required", "image_scan", ["image_requires_manual_ocr"]
    if document_class == "html_document" and text_status == "extracted" and text_length > 0:
        return "ready_for_manual_review", "person_detail_or_html_document", ["text_extracted_for_manual_review"]
    if text_status == "extracted" and text_length > 0:
        return "ready_for_manual_review", "generic_text_document", ["text_extracted_for_manual_review"]
    return "manual_review_required", document_class or "unknown", ["text_missing_or_not_extractable"]


def _load_text_payload(*, metadata: dict[str, Any], text_dir: Path) -> dict[str, Any] | None:
    text_path = text_dir / _text_relative_path(metadata)
    if not text_path.exists():
        return None
    payload = json.loads(text_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    payload["_text_file"] = str(text_path)
    return payload


def _text_relative_path(metadata: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(metadata.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(metadata.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.text.json"


def _quality_relative_path(quality: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(quality.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(quality.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.quality.json"


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
        self.item_interval = item_interval
        self.seconds_interval = seconds_interval
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
    parser = argparse.ArgumentParser(description="Valuta qualita' e utilizzabilita' dei documenti processati.")
    parser.add_argument("--metadata-dir", default="data/processed/documents")
    parser.add_argument("--text-dir", default="data/processed/documents")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--summary-json", default="risultati/document_analysis/document_quality_assessment.json")
    args = parser.parse_args()

    summary = assess_document_quality(
        metadata_dir=Path(args.metadata_dir),
        text_dir=Path(args.text_dir),
        output_dir=Path(args.output_dir),
    )
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Assessment qualita' scritti in {args.output_dir}")
    print(f"Summary JSON scritto in {summary_path}")
    print(f"Documenti processati: {summary['document_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
