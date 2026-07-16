from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from .image_preprocessing import preprocess_dark_foreground_for_ocr
from .transcription_registration import register_document_transcription

CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
OCR_FALLBACK_PAGE_SEGMENTATION_MODES = ("12", "6", "11")


def run_document_ocr(
    *,
    file_path: Path,
    sidecar_path: Path | None = None,
    root_dir: Path = Path("data/raw"),
    output_dir: Path = Path("data/processed/documents"),
    language: str = "ita",
    tesseract_path: str = "tesseract",
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    dpi: str = "",
    preprocess_before_ocr: bool = False,
    enable_region_ocr: bool = False,
    review_status: str = "unreviewed",
    overwrite: bool = False,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    image_path = Path(file_path)
    if not image_path.exists() or not image_path.is_file():
        raise FileNotFoundError(f"Documento immagine non trovato: {image_path}")

    with tempfile.TemporaryDirectory(prefix="caduti-ocr-preprocess-") as tmp_dir:
        ocr_image_path = image_path
        preprocessing_report: dict[str, Any] | None = None
        if preprocess_before_ocr:
            preprocessed_path = Path(tmp_dir) / "preprocessed.png"
            preprocessing_report = preprocess_dark_foreground_for_ocr(
                file_path=image_path,
                output_file=preprocessed_path,
                overwrite=True,
            )
            ocr_image_path = preprocessed_path

        ocr_text_result = _run_tesseract_with_fallbacks(
            image_path=ocr_image_path,
            language=language,
            tesseract_path=tesseract_path,
            page_segmentation_mode=page_segmentation_mode,
            engine_mode=engine_mode,
            dpi=dpi,
            command_runner=command_runner,
        )
        ocr_text = ocr_text_result["text"]
        effective_page_segmentation_mode = ocr_text_result["page_segmentation_mode"]
        ocr_quality = _read_tesseract_quality(
            image_path=ocr_image_path,
            language=language,
            tesseract_path=tesseract_path,
            page_segmentation_mode=effective_page_segmentation_mode,
            engine_mode=engine_mode,
            dpi=dpi,
            command_runner=command_runner,
        )
        ocr_metadata = {
            "ocr_engine": "tesseract",
            "ocr_language": language,
            "ocr_page_segmentation_mode": page_segmentation_mode,
            "ocr_effective_page_segmentation_mode": effective_page_segmentation_mode,
            "ocr_fallback_attempts": ocr_text_result["attempts"],
            "ocr_quality_status": ocr_quality["ocr_quality_status"],
            "ocr_word_count": ocr_quality["ocr_word_count"],
            "ocr_mean_confidence": ocr_quality["ocr_mean_confidence"],
            "ocr_low_confidence_words_count": ocr_quality["ocr_low_confidence_words_count"],
            "ocr_quality_reasons": ocr_quality["ocr_quality_reasons"],
            "ocr_layout_status": ocr_quality["ocr_layout_status"],
            "ocr_page_width": ocr_quality["ocr_page_width"],
            "ocr_page_height": ocr_quality["ocr_page_height"],
            "ocr_line_count": ocr_quality["ocr_line_count"],
            "ocr_footnote_candidates": ocr_quality["ocr_footnote_candidates"],
            "ocr_reference_candidates": ocr_quality["ocr_reference_candidates"],
            "ocr_preprocessing_enabled": preprocess_before_ocr,
            "ocr_preprocessing_status": "preprocessed_temporary" if preprocessing_report is not None else "not_requested",
        }
        if preprocessing_report is not None:
            ocr_metadata["ocr_preprocessing_method"] = preprocessing_report["preprocessing_method"]
            ocr_metadata["ocr_preprocessing_parameters"] = preprocessing_report["parameters"]
            ocr_metadata["ocr_preprocessing_foreground_percent"] = preprocessing_report["foreground_percent"]
            ocr_metadata["ocr_input_source"] = "temporary_preprocessed_image"
        else:
            ocr_metadata["ocr_input_source"] = "original_image"
        if enable_region_ocr:
            region_payload = _run_region_ocr(
                image_path=ocr_image_path,
                language=language,
                tesseract_path=tesseract_path,
                page_segmentation_mode=effective_page_segmentation_mode,
                engine_mode=engine_mode,
                dpi=dpi,
                command_runner=command_runner,
            )
            ocr_metadata.update(region_payload)
    result = register_document_transcription(
        file_path=image_path,
        sidecar_path=sidecar_path,
        text=ocr_text,
        root_dir=root_dir,
        output_dir=output_dir,
        transcription_method="external_ocr_unreviewed",
        review_status=review_status,
        derived_metadata=ocr_metadata,
        overwrite=overwrite,
    )
    result["@type"] = "DocumentOcrRegistration"
    result["ocr_engine"] = "tesseract"
    result["ocr_language"] = language
    result["ocr_effective_page_segmentation_mode"] = effective_page_segmentation_mode
    result["ocr_quality_status"] = ocr_quality["ocr_quality_status"]
    result["ocr_mean_confidence"] = ocr_quality["ocr_mean_confidence"]
    result["ocr_layout_status"] = ocr_quality["ocr_layout_status"]
    result["ocr_preprocessing_status"] = ocr_metadata["ocr_preprocessing_status"]
    if enable_region_ocr:
        result["ocr_region_status"] = ocr_metadata["ocr_region_status"]
    result["tesseract_path"] = tesseract_path
    return result


def _run_tesseract_with_fallbacks(
    *,
    image_path: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    dpi: str = "",
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    modes = _fallback_page_segmentation_modes(page_segmentation_mode)
    attempts: list[dict[str, str]] = []
    last_empty_error = ""
    for mode in modes:
        try:
            text = _run_tesseract(
                image_path=image_path,
                language=language,
                tesseract_path=tesseract_path,
                page_segmentation_mode=mode,
                engine_mode=engine_mode,
                dpi=dpi,
                command_runner=command_runner,
            )
        except ValueError as exc:
            last_empty_error = str(exc)
            attempts.append(
                {
                    "page_segmentation_mode": mode,
                    "status": "empty",
                    "reason": str(exc),
                }
            )
            continue
        attempts.append(
            {
                "page_segmentation_mode": mode,
                "status": "extracted",
                "reason": "",
            }
        )
        return {
            "text": text,
            "page_segmentation_mode": mode,
            "attempts": attempts,
        }
    raise ValueError(last_empty_error or "OCR Tesseract vuoto.")


def _fallback_page_segmentation_modes(primary_mode: str) -> list[str]:
    primary = primary_mode.strip()
    modes = [primary]
    modes.extend(mode for mode in OCR_FALLBACK_PAGE_SEGMENTATION_MODES if mode != primary)
    return modes


def _run_tesseract(
    *,
    image_path: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    dpi: str = "",
    command_runner: CommandRunner | None = None,
) -> str:
    command = _build_tesseract_command(
        image_path=image_path,
        language=language,
        tesseract_path=tesseract_path,
        page_segmentation_mode=page_segmentation_mode,
        engine_mode=engine_mode,
        dpi=dpi,
    )

    runner = command_runner or _default_command_runner
    try:
        completed = runner(command)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Tesseract non trovato: {tesseract_path}") from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        detail = f": {stderr}" if stderr else "."
        raise RuntimeError(f"OCR Tesseract fallito{detail}")

    text = " ".join((completed.stdout or "").split())
    if not text:
        raise ValueError("OCR Tesseract vuoto.")
    return text


def _read_tesseract_quality(
    *,
    image_path: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    dpi: str = "",
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    command = _build_tesseract_command(
        image_path=image_path,
        language=language,
        tesseract_path=tesseract_path,
        page_segmentation_mode=page_segmentation_mode,
        engine_mode=engine_mode,
        dpi=dpi,
    )
    command.append("tsv")

    runner = command_runner or _default_command_runner
    try:
        completed = runner(command)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Tesseract non trovato: {tesseract_path}") from exc

    if completed.returncode != 0:
        return _quality_payload(word_confidences=[], reasons=["tesseract_tsv_failed"])
    records = _parse_tesseract_tsv(completed.stdout or "")
    return _quality_payload(
        word_confidences=[record["confidence"] for record in records["words"]],
        reasons=[],
        layout=_layout_payload(records),
    )


def _build_tesseract_command(
    *,
    image_path: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    dpi: str = "",
) -> list[str]:
    command = [tesseract_path, str(image_path), "stdout"]
    if language.strip():
        command.extend(["-l", language.strip()])
    if page_segmentation_mode.strip():
        command.extend(["--psm", page_segmentation_mode.strip()])
    if engine_mode.strip():
        command.extend(["--oem", engine_mode.strip()])
    if dpi.strip():
        command.extend(["--dpi", dpi.strip()])
    return command


def _run_region_ocr(
    *,
    image_path: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str,
    engine_mode: str,
    dpi: str,
    command_runner: CommandRunner | None,
) -> dict[str, Any]:
    try:
        from PIL import Image, ImageEnhance, ImageFilter
    except ImportError:
        return {
            "ocr_region_status": "preprocessing_unavailable",
            "ocr_region_outputs": [],
            "ocr_region_reasons": ["pillow_unavailable"],
        }

    outputs: list[dict[str, Any]] = []
    reasons: list[str] = []
    with tempfile.TemporaryDirectory(prefix="caduti-ocr-regions-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        with Image.open(image_path) as image:
            prepared = ImageEnhance.Contrast(image.convert("L")).enhance(1.8).filter(ImageFilter.SHARPEN)
            width, height = prepared.size
            regions = {
                "bottom_region": (0, int(height * 0.68), width, height),
                "left_page": (0, 0, int(width * 0.52), height),
                "right_page": (int(width * 0.48), 0, width, height),
            }
            for region_name, box in regions.items():
                crop_path = tmp_path / f"{region_name}.png"
                prepared.crop(box).save(crop_path)
                try:
                    text = _run_tesseract(
                        image_path=crop_path,
                        language=language,
                        tesseract_path=tesseract_path,
                        page_segmentation_mode=page_segmentation_mode,
                        engine_mode=engine_mode,
                        dpi=dpi,
                        command_runner=command_runner,
                    )
                except (RuntimeError, ValueError) as exc:
                    outputs.append(
                        {
                            "region": region_name,
                            "status": "ocr_failed",
                            "text": "",
                            "text_length": 0,
                            "error": str(exc),
                            "review_status": "unreviewed",
                        }
                    )
                    reasons.append(f"{region_name}_failed")
                    continue
                outputs.append(
                    {
                        "region": region_name,
                        "status": "extracted",
                        "text": text,
                        "text_length": len(text),
                        "reference_signal": _has_reference_signal(text),
                        "review_status": "unreviewed",
                    }
                )
    status = "regions_extracted" if any(output["status"] == "extracted" for output in outputs) else "regions_failed"
    return {
        "ocr_region_status": status,
        "ocr_region_outputs": outputs,
        "ocr_region_reasons": sorted(set(reasons)),
    }


def _parse_tesseract_tsv(tsv_text: str) -> dict[str, Any]:
    lines = [line for line in tsv_text.splitlines() if line.strip()]
    if not lines:
        return {"page": {}, "words": [], "lines": []}
    headers = lines[0].split("\t")
    records: list[dict[str, Any]] = []
    for line in lines[1:]:
        columns = line.split("\t")
        if len(columns) < len(headers):
            continue
        record = {headers[index]: columns[index] for index in range(len(headers))}
        records.append(record)
    page = _parse_page_record(records)
    words = _parse_word_records(records)
    return {"page": page, "words": words, "lines": _group_words_by_line(words)}


def _parse_page_record(records: list[dict[str, Any]]) -> dict[str, int]:
    for record in records:
        if record.get("level") == "1":
            return {
                "width": _int_or_zero(record.get("width", "")),
                "height": _int_or_zero(record.get("height", "")),
            }
    return {}


def _parse_word_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for record in records:
        if record.get("level") != "5":
            continue
        text = str(record.get("text", "")).strip()
        if not text:
            continue
        confidence = _float_or_none(record.get("conf", ""))
        if confidence is None or confidence < 0:
            continue
        words.append(
            {
                "text": text,
                "confidence": confidence,
                "left": _int_or_zero(record.get("left", "")),
                "top": _int_or_zero(record.get("top", "")),
                "width": _int_or_zero(record.get("width", "")),
                "height": _int_or_zero(record.get("height", "")),
                "page_num": record.get("page_num", ""),
                "block_num": record.get("block_num", ""),
                "par_num": record.get("par_num", ""),
                "line_num": record.get("line_num", ""),
            }
        )
    return words


def _group_words_by_line(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for word in words:
        key = (str(word["page_num"]), str(word["block_num"]), str(word["par_num"]), str(word["line_num"]))
        grouped.setdefault(key, []).append(word)

    lines: list[dict[str, Any]] = []
    for key_words in grouped.values():
        sorted_words = sorted(key_words, key=lambda item: item["left"])
        left = min(word["left"] for word in sorted_words)
        top = min(word["top"] for word in sorted_words)
        right = max(word["left"] + word["width"] for word in sorted_words)
        bottom = max(word["top"] + word["height"] for word in sorted_words)
        confidences = [word["confidence"] for word in sorted_words]
        lines.append(
            {
                "text": " ".join(word["text"] for word in sorted_words),
                "left": left,
                "top": top,
                "width": right - left,
                "height": bottom - top,
                "confidence": round(sum(confidences) / len(confidences), 2),
                "word_count": len(sorted_words),
            }
        )
    return sorted(lines, key=lambda item: (item["top"], item["left"]))


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _int_or_zero(value: str) -> int:
    try:
        return int(float(value))
    except ValueError:
        return 0


def _layout_payload(records: dict[str, Any]) -> dict[str, Any]:
    page = records.get("page") or {}
    page_height = int(page.get("height", 0) or 0)
    page_width = int(page.get("width", 0) or 0)
    lines = records.get("lines") or []
    if not page_height or not lines:
        return {
            "ocr_layout_status": "layout_unavailable",
            "ocr_page_width": page_width or None,
            "ocr_page_height": page_height or None,
            "ocr_line_count": len(lines),
            "ocr_footnote_candidates": [],
            "ocr_reference_candidates": [],
        }

    footnotes: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    for line in lines:
        reasons = _line_candidate_reasons(line=line, page_height=page_height)
        if "bottom_page_region" in reasons and _has_note_or_reference_signal(line["text"]):
            footnotes.append(_candidate_from_line(line=line, reasons=reasons))
        if _has_reference_signal(line["text"]):
            references.append(_candidate_from_line(line=line, reasons=reasons + ["reference_pattern"]))
    return {
        "ocr_layout_status": "layout_detected",
        "ocr_page_width": page_width,
        "ocr_page_height": page_height,
        "ocr_line_count": len(lines),
        "ocr_footnote_candidates": footnotes[:20],
        "ocr_reference_candidates": references[:20],
    }


def _line_candidate_reasons(*, line: dict[str, Any], page_height: int) -> list[str]:
    reasons: list[str] = []
    if line["top"] >= page_height * 0.72:
        reasons.append("bottom_page_region")
    if int(line.get("height", 0)) <= max(18, page_height * 0.025):
        reasons.append("small_text_region")
    if _has_reference_signal(line["text"]):
        reasons.append("reference_pattern")
    if re.search(r"^\s*\d{1,3}[\).\s]", line["text"]):
        reasons.append("leading_note_number")
    return reasons


def _candidate_from_line(*, line: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "text": line["text"],
        "left": line["left"],
        "top": line["top"],
        "width": line["width"],
        "height": line["height"],
        "confidence": line["confidence"],
        "word_count": line["word_count"],
        "reasons": sorted(set(reasons)),
        "review_status": "unreviewed",
    }


def _has_note_or_reference_signal(text: str) -> bool:
    return bool(re.search(r"(^|\s)\d{1,3}[\).\s]", text)) or _has_reference_signal(text)


def _has_reference_signal(text: str) -> bool:
    return bool(re.search(r"\b(cfr|ivi|ibidem|v|vedi|pp|p)\.?(?=\s|$)|[A-Z][a-z]+,\s|[12][0-9]{3}", text, flags=re.IGNORECASE))


def _quality_payload(
    *,
    word_confidences: list[float],
    reasons: list[str],
    layout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    low_confidence_threshold = 50.0
    if not word_confidences:
        quality_status = "needs_review"
        mean_confidence = None
        low_confidence_count = 0
        quality_reasons = reasons + ["ocr_confidence_unavailable"]
    else:
        mean_confidence = round(sum(word_confidences) / len(word_confidences), 2)
        low_confidence_count = sum(1 for confidence in word_confidences if confidence < low_confidence_threshold)
        if mean_confidence < low_confidence_threshold or low_confidence_count:
            quality_status = "low_confidence"
            quality_reasons = reasons + ["ocr_low_confidence_words"]
        else:
            quality_status = "usable_for_preview"
            quality_reasons = reasons + ["ocr_confidence_available"]
    return {
        "ocr_quality_status": quality_status,
        "ocr_word_count": len(word_confidences),
        "ocr_mean_confidence": mean_confidence,
        "ocr_low_confidence_words_count": low_confidence_count,
        "ocr_quality_reasons": quality_reasons,
        **(layout or {
            "ocr_layout_status": "layout_unavailable",
            "ocr_page_width": None,
            "ocr_page_height": None,
            "ocr_line_count": 0,
            "ocr_footnote_candidates": [],
            "ocr_reference_candidates": [],
        }),
    }


def _default_command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue OCR locale Tesseract e registra testo revisionabile.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--sidecar", default="")
    parser.add_argument("--root-dir", default="data/raw")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--language", default="ita")
    parser.add_argument("--tesseract-path", default="tesseract")
    parser.add_argument("--psm", default="")
    parser.add_argument("--oem", default="")
    parser.add_argument("--dpi", default="")
    parser.add_argument("--preprocess-before-ocr", action="store_true")
    parser.add_argument("--enable-region-ocr", action="store_true")
    parser.add_argument("--review-status", default="unreviewed")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        result = run_document_ocr(
            file_path=Path(args.file),
            sidecar_path=Path(args.sidecar) if args.sidecar.strip() else None,
            root_dir=Path(args.root_dir),
            output_dir=Path(args.output_dir),
            language=args.language,
            tesseract_path=args.tesseract_path,
            page_segmentation_mode=args.psm,
            engine_mode=args.oem,
            dpi=args.dpi,
            preprocess_before_ocr=args.preprocess_before_ocr,
            enable_region_ocr=args.enable_region_ocr,
            review_status=args.review_status,
            overwrite=args.overwrite,
        )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
