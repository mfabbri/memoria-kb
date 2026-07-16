from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

IMAGE_CLASS_SCAN = "document_scan_dark_text"
IMAGE_CLASS_LOW_CONTRAST = "document_scan_low_contrast"
IMAGE_CLASS_WATERMARK = "document_scan_watermark_or_light_overlay"
IMAGE_CLASS_PHOTO_OF_DOCUMENT = "photo_of_document"
IMAGE_CLASS_HISTORICAL_MAP = "historical_map"
IMAGE_CLASS_PHOTOGRAPH = "photograph_non_text"
IMAGE_CLASS_UNKNOWN = "unknown"

PREPROCESS_NONE = "none"
PREPROCESS_DARK_FOREGROUND = "dark_foreground_binary"
PREPROCESS_ADAPTIVE_THRESHOLD = "adaptive_threshold"
PREPROCESS_CONTRAST_SHARPEN = "contrast_sharpen"
PREPROCESS_DESKEW_THRESHOLD = "deskew_then_threshold"
PREPROCESS_REGION_ONLY = "region_ocr_only"
PREPROCESS_MANUAL_REVIEW = "manual_review_required"

OCR_RAW_FIRST = "raw_ocr_first"
OCR_PREPROCESS_REVIEW = "preprocess_then_ocr_after_review"
OCR_REGION_ONLY = "region_ocr_only"
OCR_MANUAL_REVIEW = "manual_review_required"
OCR_SKIP = "skip_ocr"

IMAGE_OCR_ACTION = "image_ocr_required"
MAP_ACTIONS = {"historical_map_georeferencing_required", "historical_map_ocr_required"}

LOW_CONTRAST_TERMS = ("low_contrast", "low-contrast", "sbiad", "faded", "pallid", "chiaro", "light")
WATERMARK_TERMS = ("watermark", "filigrana", "overlay", "zoom", "germandocsinrussia")
PHOTO_DOC_TERMS = ("foto_documento", "photo_of_document", "documento_foto", "foto-di-documento")
PHOTO_TERMS = ("foto", "photo", "photograph", "ritratto", "portrait")
SCAN_TERMS = ("scan", "scansione", "pagina", "page", "delo", "fond")
MAP_TERMS = ("mappa", "carta", "cartografia", "map", "maps", "karte", "karten", "mapa")


def build_image_preprocessing_plan(
    *,
    input_plan_json: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if progress_callback is not None:
        progress_callback(f"image_preprocessing_plan read input path={input_plan_json}")
    input_plan = json.loads(input_plan_json.read_text(encoding="utf-8"))
    if not isinstance(input_plan, dict):
        raise ValueError("input_processing_plan JSON must contain an object")
    assets = input_plan.get("assets", [])
    if not isinstance(assets, list):
        assets = []
    items = [_planned_image(asset) for asset in assets if isinstance(asset, dict) and _is_image_candidate(asset)]
    class_counts = Counter(str(item["image_class_candidate"]) for item in items)
    preprocessing_counts = Counter(str(item["recommended_preprocessing"]) for item in items)
    strategy_counts = Counter(str(item["recommended_ocr_strategy"]) for item in items)
    result = {
        "@type": "ImagePreprocessingPlan",
        "input_processing_plan": str(input_plan_json),
        "root_dir": str(input_plan.get("root_dir", "")),
        "image_count": len(items),
        "image_class_counts": dict(sorted(class_counts.items())),
        "recommended_preprocessing_counts": dict(sorted(preprocessing_counts.items())),
        "recommended_ocr_strategy_counts": dict(sorted(strategy_counts.items())),
        "review_status": "unreviewed",
        "items": items,
    }
    if output_json is not None:
        if progress_callback is not None:
            progress_callback(f"image_preprocessing_plan write json path={output_json}")
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        if progress_callback is not None:
            progress_callback(f"image_preprocessing_plan write markdown path={output_md}")
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_image_preprocessing_plan_markdown(result), encoding="utf-8")
    return result


def render_image_preprocessing_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Image preprocessing plan",
        "",
        f"- Input plan: `{plan.get('input_processing_plan', '')}`",
        f"- Root: `{plan.get('root_dir', '')}`",
        f"- Immagini candidate: `{plan.get('image_count', 0)}`",
        f"- Stato revisione: `{plan.get('review_status', '')}`",
        "",
        "## Classi candidate",
        "",
    ]
    _append_counts(lines, plan.get("image_class_counts", {}))
    lines.extend(["", "## Preprocessing raccomandato", ""])
    _append_counts(lines, plan.get("recommended_preprocessing_counts", {}))
    lines.extend(["", "## Strategie OCR", ""])
    _append_counts(lines, plan.get("recommended_ocr_strategy_counts", {}))
    lines.extend(["", "## Immagini", ""])
    items = plan.get("items", [])
    if not isinstance(items, list) or not items:
        lines.append("_Nessuna immagine candidata._")
    else:
        for item in items:
            if not isinstance(item, dict):
                continue
            lines.extend(
                [
                    f"### {item.get('title', '') or item.get('raw_file', '') or item.get('image_id', '')}",
                    "",
                    f"- Raw file: `{item.get('raw_file', '')}`",
                    f"- Sidecar: `{item.get('sidecar_file', '')}`",
                    f"- Classe candidata: `{item.get('image_class_candidate', '')}`",
                    f"- Preprocessing: `{item.get('recommended_preprocessing', '')}`",
                    f"- Strategia OCR: `{item.get('recommended_ocr_strategy', '')}`",
                    f"- Rischio: `{item.get('risk', '')}`",
                    f"- Revisione: `{item.get('review_status', '')}`",
                    f"- Ragione: {item.get('reason', '')}",
                ]
            )
            signals = item.get("quality_signals", [])
            if isinstance(signals, list) and signals:
                lines.append(f"- Segnali: {', '.join(f'`{signal}`' for signal in signals)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _append_counts(lines: list[str], counts: Any) -> None:
    if isinstance(counts, dict) and counts:
        for key, count in counts.items():
            lines.append(f"- `{key}`: `{count}`")
    else:
        lines.append("- Nessun elemento.")


def _is_image_candidate(asset: dict[str, Any]) -> bool:
    media_type = str(asset.get("media_type", "")).casefold()
    action = str(asset.get("recommended_action", "")).casefold()
    raw_file = str(asset.get("raw_file", "")).casefold()
    return (
        media_type.startswith("image/")
        or action == IMAGE_OCR_ACTION
        or action in MAP_ACTIONS
        or raw_file.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"))
    )


def _planned_image(asset: dict[str, Any]) -> dict[str, Any]:
    image_class, quality_signals, preprocessing, ocr_strategy, reason, risk = _classify_image(asset)
    image_id = str(asset.get("source_document_id") or asset.get("source_id") or asset.get("raw_file", ""))
    return {
        "@type": "ImagePreprocessingPlanItem",
        "image_id": image_id,
        "title": str(asset.get("title", "")),
        "raw_file": str(asset.get("raw_file", "")),
        "sidecar_file": str(asset.get("sidecar_file", "")),
        "source_id": str(asset.get("source_id", "")),
        "source_document_id": str(asset.get("source_document_id", "")),
        "image_class_candidate": image_class,
        "quality_signals": quality_signals,
        "recommended_preprocessing": preprocessing,
        "recommended_ocr_strategy": ocr_strategy,
        "reason": reason,
        "risk": risk,
        "review_status": str(asset.get("review_status", "")) or "unreviewed",
    }


def _classify_image(asset: dict[str, Any]) -> tuple[str, list[str], str, str, str, str]:
    action = str(asset.get("recommended_action", "")).casefold()
    document_class = str(asset.get("document_class_guess", "")).casefold()
    haystack = _asset_haystack(asset)
    if action in MAP_ACTIONS or document_class == "historical_map" or _contains_any(haystack, MAP_TERMS):
        return (
            IMAGE_CLASS_HISTORICAL_MAP,
            ["map_keyword_or_input_action"],
            PREPROCESS_MANUAL_REVIEW,
            OCR_REGION_ONLY,
            "Mappe e carte richiedono revisione prima di qualunque soglia globale.",
            "high",
        )
    if _contains_any(haystack, WATERMARK_TERMS):
        return (
            IMAGE_CLASS_WATERMARK,
            ["watermark_or_light_overlay_keyword"],
            PREPROCESS_ADAPTIVE_THRESHOLD,
            OCR_PREPROCESS_REVIEW,
            "Possibile overlay o filigrana: provare preprocessing solo dopo revisione.",
            "medium",
        )
    if _contains_any(haystack, LOW_CONTRAST_TERMS):
        return (
            IMAGE_CLASS_LOW_CONTRAST,
            ["low_contrast_keyword"],
            PREPROCESS_CONTRAST_SHARPEN,
            OCR_PREPROCESS_REVIEW,
            "Segnale di basso contrasto: contrasto/sharpening e controllo umano.",
            "medium",
        )
    if _contains_any(haystack, PHOTO_DOC_TERMS):
        return (
            IMAGE_CLASS_PHOTO_OF_DOCUMENT,
            ["photo_of_document_keyword"],
            PREPROCESS_DESKEW_THRESHOLD,
            OCR_PREPROCESS_REVIEW,
            "Foto di documento: possibile deskew/soglia dopo revisione.",
            "medium",
        )
    if _looks_like_non_text_photo(haystack, action, document_class):
        return (
            IMAGE_CLASS_PHOTOGRAPH,
            ["photograph_keyword_without_document_signal"],
            PREPROCESS_NONE,
            OCR_SKIP,
            "Fotografia senza segnale testuale: evitare OCR/preprocessing automatico.",
            "low",
        )
    if action == IMAGE_OCR_ACTION or document_class == "image_scan" or _contains_any(haystack, SCAN_TERMS):
        return (
            IMAGE_CLASS_SCAN,
            ["image_ocr_or_scan_signal"],
            PREPROCESS_DARK_FOREGROUND,
            OCR_RAW_FIRST,
            "Scansione candidata OCR: eseguire prima OCR raw, poi derivato se serve.",
            "low",
        )
    return (
        IMAGE_CLASS_UNKNOWN,
        ["insufficient_image_context"],
        PREPROCESS_MANUAL_REVIEW,
        OCR_MANUAL_REVIEW,
        "Immagine candidata ma contesto insufficiente per una scelta automatica.",
        "medium",
    )


def _asset_haystack(asset: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "title",
        "raw_file",
        "sidecar_file",
        "media_type",
        "document_class_guess",
        "recommended_action",
    ):
        parts.append(str(asset.get(key, "")))
    reasons = asset.get("reasons", [])
    if isinstance(reasons, list):
        parts.extend(str(reason) for reason in reasons)
    next_actions = asset.get("suggested_next_actions", [])
    if isinstance(next_actions, list):
        parts.extend(str(action) for action in next_actions)
    return " ".join(parts).casefold()


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term in value for term in terms)


def _looks_like_non_text_photo(haystack: str, action: str, document_class: str) -> bool:
    if action == IMAGE_OCR_ACTION or document_class in {"image_scan", "historical_map"}:
        return False
    return _contains_any(haystack, PHOTO_TERMS) and not _contains_any(haystack, SCAN_TERMS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un piano preview-only di preprocessing immagini.")
    parser.add_argument("--input-plan-json", required=True)
    parser.add_argument("--output-json", default="risultati/document_analysis/image_preprocessing_plan.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/image_preprocessing_plan.md")
    args = parser.parse_args()

    plan = build_image_preprocessing_plan(
        input_plan_json=Path(args.input_plan_json),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"Image preprocessing plan JSON scritto in {args.output_json}")
    print(f"Image preprocessing plan Markdown scritto in {args.output_md}")
    print(f"Immagini candidate: {plan['image_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
