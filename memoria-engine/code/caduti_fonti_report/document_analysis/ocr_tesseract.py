from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

import yaml

from .image_preprocessing import preprocess_dark_foreground_for_ocr
from .transcription_registration import register_document_transcription

CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
OCR_FALLBACK_PAGE_SEGMENTATION_MODES = ("12", "6", "11")
OCR_QUALITY_MIN_ALPHANUMERIC_TOKENS = 2
OCR_QUALITY_MIN_ALPHANUMERIC_LINES = 1
OCR_QUALITY_MIN_MEAN_CONFIDENCE = 35.0
OCR_QUALITY_MAX_LOW_CONFIDENCE_RATIO = 0.75


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
    source_document_id = _source_document_id_from_sidecar(file_path=image_path, sidecar_path=sidecar_path)

    with tempfile.TemporaryDirectory(prefix="caduti-ocr-preprocess-") as tmp_dir:
        initial_image_path = image_path
        initial_preprocessing_report: dict[str, Any] | None = None
        if preprocess_before_ocr:
            initial_image_path = Path(tmp_dir) / "preprocessed.png"
            initial_preprocessing_report = preprocess_dark_foreground_for_ocr(
                file_path=image_path, output_file=initial_image_path, overwrite=True,
            )

        ocr_text_result = _run_tesseract_with_quality_retries(
            image_path=initial_image_path,
            original_image_path=image_path,
            language=language,
            tesseract_path=tesseract_path,
            page_segmentation_mode=page_segmentation_mode,
            engine_mode=engine_mode,
            dpi=dpi,
            source_document_id=source_document_id,
            temporary_dir=Path(tmp_dir),
            initial_preprocessing_report=initial_preprocessing_report,
            command_runner=command_runner,
        )
        ocr_text = ocr_text_result["text"]
        effective_page_segmentation_mode = ocr_text_result["page_segmentation_mode"]
        ocr_quality = ocr_text_result["quality"]
        ocr_image_path = ocr_text_result["image_path"]
        preprocessing_report = ocr_text_result["preprocessing_report"]
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
            "ocr_layout_lines": ocr_quality["ocr_layout_lines"],
            "ocr_footnote_candidates": ocr_quality["ocr_footnote_candidates"],
            "ocr_reference_candidates": ocr_quality["ocr_reference_candidates"],
            "ocr_preprocessing_enabled": preprocessing_report is not None,
            "ocr_preprocessing_status": ocr_text_result["preprocessing_status"],
            "ocr_quality_gate_status": "accepted",
            "ocr_quality_gate_score": ocr_text_result["quality_score"],
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


def _run_tesseract_with_quality_retries(
    *,
    image_path: Path,
    original_image_path: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    dpi: str = "",
    source_document_id: str,
    temporary_dir: Path,
    initial_preprocessing_report: dict[str, Any] | None,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    primary_mode, alternate_mode = _quality_retry_page_segmentation_modes(page_segmentation_mode)
    primary = _evaluate_ocr_candidate(
        image_path=image_path, input_kind="requested_preprocessed" if initial_preprocessing_report else "original",
        language=language, tesseract_path=tesseract_path, page_segmentation_mode=primary_mode,
        engine_mode=engine_mode, dpi=dpi, source_document_id=source_document_id, command_runner=command_runner,
    )
    attempts.append(primary["attempt"])
    candidates.append(primary)
    if not primary["usable"]:
        alternate = _evaluate_ocr_candidate(
            image_path=image_path, input_kind="requested_preprocessed" if initial_preprocessing_report else "original", language=language, tesseract_path=tesseract_path,
            page_segmentation_mode=alternate_mode, engine_mode=engine_mode, dpi=dpi,
            source_document_id=source_document_id, command_runner=command_runner,
        )
        attempts.append(alternate["attempt"])
        candidates.append(alternate)
    usable = [candidate for candidate in candidates if candidate["usable"]]
    preprocessing_report = initial_preprocessing_report
    preprocessing_status = "preprocessed_temporary" if initial_preprocessing_report else "not_requested"
    if not usable:
        best = max(candidates, key=lambda candidate: candidate["quality_score"])
        preprocessed_path = temporary_dir / "preprocessed-quality-retry.png"
        try:
            retry_report = preprocess_dark_foreground_for_ocr(
                file_path=original_image_path, output_file=preprocessed_path, overwrite=True,
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
            attempts.append({"input": "temporary_preprocessed", "page_segmentation_mode": best["page_segmentation_mode"], "status": "preprocess_failed", "reason": str(exc)})
        else:
            preprocessed = _evaluate_ocr_candidate(
                image_path=preprocessed_path, input_kind="temporary_preprocessed", language=language,
                tesseract_path=tesseract_path, page_segmentation_mode=best["page_segmentation_mode"],
                engine_mode=engine_mode, dpi=dpi, source_document_id=source_document_id, command_runner=command_runner,
            )
            attempts.append(preprocessed["attempt"])
            candidates.append(preprocessed)
            preprocessing_report = retry_report
            preprocessing_status = "quality_retry_temporary"
            usable = [candidate for candidate in candidates if candidate["usable"]]
    if not usable:
        reasons = "; ".join(str(attempt.get("reason", "")) for attempt in attempts if attempt.get("reason"))
        raise ValueError(f"OCR Tesseract qualitativamente insufficiente prima della registrazione.{(' ' + reasons) if reasons else ''}")
    selected = max(usable, key=lambda candidate: candidate["quality_score"])
    for attempt in attempts:
        if attempt.get("candidate_id") == selected["candidate_id"]:
            attempt["status"] = "selected"
    return {
        "text": selected["text"], "quality": selected["quality"], "quality_score": selected["quality_score"],
        "image_path": selected["image_path"], "page_segmentation_mode": selected["page_segmentation_mode"],
        "attempts": attempts, "preprocessing_report": preprocessing_report if selected["input_kind"] != "original" else None,
        "preprocessing_status": preprocessing_status if selected["input_kind"] != "original" else "not_requested",
    }


def _quality_retry_page_segmentation_modes(primary_mode: str) -> tuple[str, str]:
    primary = primary_mode.strip()
    alternate = next((mode for mode in OCR_FALLBACK_PAGE_SEGMENTATION_MODES if mode != primary), "6")
    return primary, alternate


def _evaluate_ocr_candidate(
    *, image_path: Path, input_kind: str, language: str, tesseract_path: str, page_segmentation_mode: str,
    engine_mode: str, dpi: str, source_document_id: str, command_runner: CommandRunner | None,
) -> dict[str, Any]:
    candidate_id = f"{input_kind}:{page_segmentation_mode or 'default'}"
    try:
        text = _run_tesseract(image_path=image_path, language=language, tesseract_path=tesseract_path,
                              page_segmentation_mode=page_segmentation_mode, engine_mode=engine_mode, dpi=dpi,
                              command_runner=command_runner)
    except ValueError as exc:
        return {"candidate_id": candidate_id, "input_kind": input_kind, "image_path": image_path,
                "page_segmentation_mode": page_segmentation_mode, "text": "", "quality": _quality_payload(word_confidences=[], reasons=["ocr_empty"]),
                "quality_score": 0.0, "usable": False,
                "attempt": {"candidate_id": candidate_id, "input": input_kind, "page_segmentation_mode": page_segmentation_mode, "status": "empty", "reason": str(exc), "quality_score": 0.0}}
    quality = _read_tesseract_quality(image_path=image_path, language=language, tesseract_path=tesseract_path,
                                      page_segmentation_mode=page_segmentation_mode, engine_mode=engine_mode, dpi=dpi,
                                      source_document_id=source_document_id, command_runner=command_runner)
    score, usable, reasons = _quality_gate_score(text=text, quality=quality)
    status = "usable" if usable else "quality_rejected"
    return {"candidate_id": candidate_id, "input_kind": input_kind, "image_path": image_path,
            "page_segmentation_mode": page_segmentation_mode, "text": text, "quality": quality,
            "quality_score": score, "usable": usable,
            "attempt": {"candidate_id": candidate_id, "input": input_kind, "page_segmentation_mode": page_segmentation_mode,
                        "status": status, "reason": ",".join(reasons), "quality_score": score,
                        "word_count": quality["ocr_word_count"], "line_count": quality["ocr_line_count"]}}


def _quality_gate_score(*, text: str, quality: dict[str, Any]) -> tuple[float, bool, list[str]]:
    alpha_tokens = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
    alpha_lines = [line for line in quality.get("ocr_layout_lines", []) if re.search(r"[^\W_]", str(line.get("text", "")), flags=re.UNICODE)]
    word_count = int(quality.get("ocr_word_count", 0) or 0)
    low_count = int(quality.get("ocr_low_confidence_words_count", 0) or 0)
    mean_confidence = quality.get("ocr_mean_confidence")
    low_ratio = (low_count / word_count) if word_count else 1.0
    score = (float(mean_confidence) if mean_confidence is not None else 0.0) + min(len(alpha_tokens), 20) * 2 + min(len(alpha_lines), 10) - low_ratio * 25
    reasons: list[str] = []
    if len(alpha_tokens) < OCR_QUALITY_MIN_ALPHANUMERIC_TOKENS:
        reasons.append("too_few_alphanumeric_tokens")
    if len(alpha_lines) < OCR_QUALITY_MIN_ALPHANUMERIC_LINES:
        reasons.append("no_alphanumeric_tsv_lines")
    if mean_confidence is None or float(mean_confidence) < OCR_QUALITY_MIN_MEAN_CONFIDENCE:
        reasons.append("mean_confidence_below_threshold")
    if low_ratio > OCR_QUALITY_MAX_LOW_CONFIDENCE_RATIO:
        reasons.append("diffuse_low_confidence")
    return round(score, 2), not reasons, reasons


def _run_tesseract(
    *,
    image_path: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    dpi: str = "",
    source_document_id: str = "",
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
    source_document_id: str = "",
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
        layout=_layout_payload(records=records, source_document_id=source_document_id),
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
    for line_key, key_words in grouped.items():
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
                "page_num": line_key[0],
                "block_num": line_key[1],
                "par_num": line_key[2],
                "line_num": line_key[3],
            }
        )
    return sorted(
        lines,
        key=lambda item: (
            _int_or_zero(str(item["page_num"])),
            item["top"],
            item["left"],
            _int_or_zero(str(item["block_num"])),
            _int_or_zero(str(item["par_num"])),
            _int_or_zero(str(item["line_num"])),
        ),
    )


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


def _layout_payload(*, records: dict[str, Any], source_document_id: str) -> dict[str, Any]:
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
            "ocr_layout_lines": [],
            "ocr_footnote_candidates": [],
            "ocr_reference_candidates": [],
        }

    footnotes: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    layout_lines = [
        _layout_line_from_tsv(
            line=line,
            read_order=index,
            source_document_id=source_document_id,
        )
        for index, line in enumerate(lines, start=1)
    ]
    for line in layout_lines:
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
        "ocr_layout_lines": layout_lines,
        "ocr_footnote_candidates": footnotes[:20],
        "ocr_reference_candidates": references[:20],
    }


def _layout_line_from_tsv(*, line: dict[str, Any], read_order: int, source_document_id: str) -> dict[str, Any]:
    page_number = _int_or_zero(str(line["page_num"]))
    block_number = _int_or_zero(str(line["block_num"]))
    paragraph_number = _int_or_zero(str(line["par_num"]))
    line_number = _int_or_zero(str(line["line_num"]))
    region_id = (
        f"tesseract-region-p{page_number}-b{block_number}"
        f"-par{paragraph_number}-l{line_number}"
    )
    return {
        "source_document_id": source_document_id,
        "ocr_line_id": f"tesseract-line-p{page_number}-b{block_number}-par{paragraph_number}-l{line_number}",
        "page_id": f"tesseract-page-{page_number}",
        "page_number": page_number,
        "region_id": region_id,
        "read_order": read_order,
        "read_order_status": "inferred",
        "read_order_basis": "page_top_then_left_then_tsv_hierarchy",
        "text": line["text"],
        "left": line["left"],
        "top": line["top"],
        "width": line["width"],
        "height": line["height"],
        "confidence": line["confidence"],
        "word_count": line["word_count"],
        "review_status": "unreviewed",
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
        "source_document_id": line["source_document_id"],
        "ocr_line_id": line["ocr_line_id"],
        "page_id": line["page_id"],
        "region_id": line["region_id"],
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


def _source_document_id_from_sidecar(*, file_path: Path, sidecar_path: Path | None) -> str:
    resolved_sidecar = sidecar_path or file_path.with_name(f"{file_path.name}.document.yaml")
    if not resolved_sidecar.exists():
        resolved_sidecar = file_path.with_name("document.yaml")
    if not resolved_sidecar.exists():
        return ""
    payload = yaml.safe_load(resolved_sidecar.read_text(encoding="utf-8")) or {}
    return str(payload.get("document_id", "")).strip() if isinstance(payload, dict) else ""


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
            "ocr_layout_lines": [],
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
