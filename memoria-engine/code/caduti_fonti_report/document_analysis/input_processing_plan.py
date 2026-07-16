from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from .inventory import build_raw_document_inventory

TEXT_ACTION = "text_document_ready"
HTML_ACTION = "html_document_ready"
WORD_ACTION = "word_document_ready"
TABULAR_ACTION = "tabular_document_ready"
IMAGE_OCR_ACTION = "image_ocr_required"
MAP_GEOREFERENCING_ACTION = "historical_map_georeferencing_required"
MAP_OCR_ACTION = "historical_map_ocr_required"
PDF_ACTION = "pdf_text_extraction_required"
AUDIO_ACTION = "audio_transcription_required"
VIDEO_ACTION = "video_transcription_required"
UNSUPPORTED_ACTION = "unsupported_media_type"
MANUAL_REVIEW_ACTION = "manual_review_required"
MAP_TERMS = ("mappa", "carta", "cartografia", "map", "maps", "karte", "karten", "mapa")


def build_input_processing_plan(
    *,
    root_dir: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if progress_callback is not None:
        progress_callback("input_processing_plan inventory start")
    inventory = build_raw_document_inventory(root_dir=root_dir, progress_callback=progress_callback)
    if progress_callback is not None:
        progress_callback(
            "input_processing_plan inventory done "
            f"documents={inventory.get('document_count', 0)} errors={inventory.get('error_count', 0)}"
        )
    assets = [_planned_asset(document) for document in inventory.get("documents", []) if isinstance(document, dict)]
    if progress_callback is not None:
        progress_callback(f"input_processing_plan assets classified count={len(assets)}")
    action_counts = Counter(str(asset.get("recommended_action", "")) for asset in assets)
    errors = inventory.get("errors", [])
    if not isinstance(errors, list):
        errors = []
    result = {
        "@type": "InputProcessingPlan",
        "root_dir": str(root_dir),
        "asset_count": len(assets),
        "action_counts": dict(sorted(action_counts.items())),
        "error_count": len(errors),
        "errors": errors,
        "review_status": "unreviewed",
        "assets": assets,
    }
    if output_json is not None:
        if progress_callback is not None:
            progress_callback(f"input_processing_plan write json path={output_json}")
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        if progress_callback is not None:
            progress_callback(f"input_processing_plan write markdown path={output_md}")
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_input_processing_plan_markdown(result), encoding="utf-8")
    return result


def render_input_processing_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Input processing plan",
        "",
        f"- Root: `{plan.get('root_dir', '')}`",
        f"- Asset: `{plan.get('asset_count', 0)}`",
        f"- Errori lettura: `{plan.get('error_count', 0)}`",
        f"- Stato revisione: `{plan.get('review_status', '')}`",
        "",
        "## Azioni proposte",
        "",
    ]
    action_counts = plan.get("action_counts", {})
    if isinstance(action_counts, dict) and action_counts:
        for action, count in action_counts.items():
            lines.append(f"- `{action}`: `{count}`")
    else:
        lines.append("- Nessun asset trovato.")
    errors = plan.get("errors", [])
    if isinstance(errors, list) and errors:
        lines.extend(["", "## Errori lettura", ""])
        for error in errors:
            if not isinstance(error, dict):
                continue
            lines.append(
                f"- `{error.get('path', '')}`: `{error.get('error_type', '')}` - {error.get('message', '')}"
            )
    lines.extend(["", "## Asset", ""])
    assets = plan.get("assets", [])
    if not isinstance(assets, list) or not assets:
        lines.append("_Nessun asset pianificato._")
    else:
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            lines.extend(
                [
                    f"### {asset.get('title', '') or asset.get('raw_file', '') or asset.get('source_document_id', '')}",
                    "",
                    f"- Azione: `{asset.get('recommended_action', '')}`",
                    f"- Media type: `{asset.get('media_type', '')}`",
                    f"- Document class: `{asset.get('document_class_guess', '')}`",
                    f"- Raw file: `{asset.get('raw_file', '')}`",
                    f"- Revisione: `{asset.get('review_status', '')}`",
                ]
            )
            reasons = asset.get("reasons", [])
            if isinstance(reasons, list) and reasons:
                lines.append(f"- Motivi: {', '.join(f'`{reason}`' for reason in reasons)}")
            next_actions = asset.get("suggested_next_actions", [])
            if isinstance(next_actions, list) and next_actions:
                lines.append(f"- Prossime azioni: {', '.join(f'`{action}`' for action in next_actions)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _planned_asset(document: dict[str, Any]) -> dict[str, Any]:
    recommended_action, document_class, reasons, next_actions = _classify_document(document)
    return {
        "@type": "InputProcessingPlanAsset",
        "source_id": str(document.get("source_id", "")),
        "source_document_id": str(document.get("source_document_id", "")),
        "title": str(document.get("title", "")),
        "raw_file": str(document.get("raw_file", "")),
        "sidecar_file": str(document.get("sidecar_file", "")),
        "media_type": str(document.get("media_type", "")),
        "sha256": str(document.get("sha256", "")),
        "document_class_guess": document_class,
        "recommended_action": recommended_action,
        "suggested_next_actions": next_actions,
        "reasons": reasons,
        "review_status": str(document.get("review_status", "")) or "unreviewed",
    }


def _classify_document(document: dict[str, Any]) -> tuple[str, str, list[str], list[str]]:
    if str(document.get("status", "")) == "read_error":
        return MANUAL_REVIEW_ACTION, "unreadable_document", ["input_read_error"], ["manual_review_required"]
    media_type = str(document.get("media_type", "")).casefold()
    raw_file = str(document.get("raw_file", "")).casefold()
    if _is_historical_map_candidate(document):
        return (
            MAP_GEOREFERENCING_ACTION,
            "historical_map",
            ["historical_map_keyword_signal", "map_pipeline_requires_review"],
            [MAP_OCR_ACTION],
        )
    if media_type == "text/plain" or raw_file.endswith(".txt"):
        return TEXT_ACTION, "text_document", ["text_media_type"], ["metadata_extraction", "text_extraction"]
    if media_type in {"text/html", "application/xhtml+xml"} or raw_file.endswith((".html", ".htm")):
        return HTML_ACTION, "html_document", ["html_media_type"], ["metadata_extraction", "text_extraction"]
    if (
        media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or raw_file.endswith(".docx")
    ):
        return WORD_ACTION, "word_document", ["word_document_media_type"], ["metadata_extraction", "text_extraction"]
    if media_type in {"text/csv", "application/vnd.ms-excel"} or raw_file.endswith((".csv", ".xls", ".xlsx")):
        return TABULAR_ACTION, "tabular_document", ["tabular_media_type"], ["metadata_extraction", "text_extraction"]
    if media_type.startswith("image/"):
        return IMAGE_OCR_ACTION, "image_scan", ["image_media_type"], ["manual_ocr_or_explicit_ocr_batch"]
    if media_type == "application/pdf" or raw_file.endswith(".pdf"):
        return PDF_ACTION, "pdf_document", ["pdf_media_type"], ["manual_review_required"]
    if media_type.startswith("audio/"):
        return AUDIO_ACTION, "audio_document", ["audio_media_type"], ["manual_or_explicit_transcription"]
    if media_type.startswith("video/"):
        return VIDEO_ACTION, "video_document", ["video_media_type"], ["manual_or_explicit_transcription"]
    if media_type == "application/octet-stream":
        return UNSUPPORTED_ACTION, "unknown", ["unsupported_or_unknown_media_type"], ["manual_review_required"]
    return MANUAL_REVIEW_ACTION, "generic_document", ["unhandled_media_type"], ["manual_review_required"]


def _is_historical_map_candidate(document: dict[str, Any]) -> bool:
    media_type = str(document.get("media_type", "")).casefold()
    if media_type and not media_type.startswith("image/") and media_type != "application/pdf":
        return False
    haystack = " ".join(
        str(document.get(key, ""))
        for key in ("title", "raw_file", "sidecar_file", "archival_reference", "url")
    ).casefold()
    return any(term in haystack for term in MAP_TERMS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un piano preview-only di processing degli asset locali.")
    parser.add_argument("--root-dir", default="data/raw")
    parser.add_argument("--output-json", default="risultati/document_analysis/input_processing_plan.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/input_processing_plan.md")
    args = parser.parse_args()

    plan = build_input_processing_plan(
        root_dir=Path(args.root_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"Input processing plan JSON scritto in {args.output_json}")
    print(f"Input processing plan Markdown scritto in {args.output_md}")
    print(f"Asset pianificati: {plan['asset_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
