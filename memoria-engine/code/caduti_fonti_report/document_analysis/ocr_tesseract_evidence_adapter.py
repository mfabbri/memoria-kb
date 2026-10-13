"""Adapt new, attested single-page Tesseract runs to comparison evidence.

Only unchanged original pixels and an explicitly raw primary frame are supported.
The adapter performs no I/O, correction, accuracy evaluation or review decision.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
import math
from typing import Any

from .ocr_evidence_comparison import _identity, _regions


def adapt_tesseract_page_evidence(
    *, processed_text: Mapping[str, Any], primary_evidence: Mapping[str, Any],
    original_page: Mapping[str, Any], registration: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return detached diagnostic evidence or raise ValueError on unsupported input.

    ``registration`` may attest the paired ProcessedDocumentText; registration
    alone does not contain TSV layout. The explicit original anchor must match
    the PP-OCRv5 evidence exactly. Full-page raw identity is then shared, while
    Tesseract method/configuration and run provenance remain distinguishable.
    """
    primary = _identity(primary_evidence)
    _regions(primary_evidence)
    if primary["engine"] != "PP-OCRv5":
        raise ValueError("Primary evidence must be PP-OCRv5 (paddle-ocr-v5).")
    anchor = _copy(original_page)
    if anchor != primary["source_page"]["original_page"]:
        raise ValueError("original_page anchor does not match primary evidence.")
    source_page = primary["source_page"]
    if (source_page.get("crop") is not None or source_page.get("tile_id") is not None
            or source_page.get("target", "full_page") != "full_page"
            or source_page.get("variant_id", "raw") != "raw"):
        raise ValueError("Only a full-page raw primary coordinate frame is supported.")
    transform = primary["image_transform"]
    plain_identity = primary["transform_id"] == "original" and transform in ({}, None)
    copied_identity = (
        isinstance(transform, dict) and set(transform) == {"id", "parameters"}
        and transform["id"] == primary["transform_id"]
        and isinstance(transform["parameters"], dict)
        and set(transform["parameters"]) <= {"operation", "source_mode"}
        and transform["parameters"].get("operation") == "byte_copy"
    )
    if not (plain_identity or copied_identity):
        raise ValueError("Unsupported primary image_transform; exact raw identity is required.")
    if not isinstance(processed_text, Mapping) or processed_text.get("@type") != "ProcessedDocumentText":
        raise ValueError("Adapter requires ProcessedDocumentText with TSV layout.")
    payload = _copy(processed_text)
    if payload.get("transcription_method") != "external_ocr_unreviewed" or payload.get("ocr_engine") != "tesseract":
        raise ValueError("Adapter requires external_ocr_unreviewed Tesseract text.")
    if payload.get("ocr_quality_gate_status") != "accepted":
        raise ValueError("Adapter requires a ProcessedDocumentText accepted by the Tesseract quality gate.")
    run = _object(payload.get("ocr_run_provenance"), "ocr_run_provenance")
    if (run.get("@type") != "TesseractRunProvenance" or run.get("schema_version") != "1.0"
            or run.get("engine") != "tesseract" or run.get("status") != "complete"
            or run.get("adapter_ready") is not True or run.get("reasons") != []
            or run.get("coordinates_identical_to_source_pixels") is not True):
        raise ValueError("Complete adapter_ready TesseractRunProvenance v1 is required.")
    document_id = payload.get("source_document_id")
    if not isinstance(document_id, str) or not document_id.strip() or run.get("source_document_id") != document_id:
        raise ValueError("Tesseract source_document_id is missing or inconsistent.")
    if registration is not None:
        paired = _copy(registration)
        if (paired.get("@type") != "DocumentOcrRegistration"
                or paired.get("source_document_id") != document_id
                or paired.get("transcription_method") != payload["transcription_method"]
                or paired.get("ocr_run_provenance") != run):
            raise ValueError("Registration does not attest this ProcessedDocumentText.")
    source = _object(run.get("source_image"), "source_image")
    expected_hash = anchor["source_image_hash"]
    if (source.get("sha256_before") != expected_hash or source.get("sha256_after") != expected_hash
            or source.get("unchanged") is not True):
        raise ValueError("Original source before/after SHA-256 must match the original_page anchor.")
    selected = _object(run.get("selected_input"), "selected_input")
    if (selected.get("kind") != "original" or selected.get("transform") != "original_pixels"
            or selected.get("preprocessing", "missing") is not None):
        raise ValueError("Unsupported Tesseract photometric/input transform; original pixels required.")
    if selected.get("sha256") != expected_hash:
        raise ValueError("Selected original input SHA-256 does not match source.")
    dimensions = anchor["source_dimensions"]
    expected_frame = {"frame_index": 0, **dimensions}
    for probe in (source.get("probe"), selected.get("probe")):
        probe = _object(probe, "image probe")
        frames = probe.get("frames")
        if (probe.get("status") != "probed" or type(probe.get("frame_count")) is not int
                or probe["frame_count"] != 1 or frames != [expected_frame]
                or any(type(frames[0].get(field)) is not int for field in expected_frame)):
            raise ValueError("Source/selected probe must attest one frame with original dimensions.")
    pages = run.get("tsv_pages")
    if (pages != [{"page_number": 1, **dimensions}]
            or any(type(pages[0].get(field)) is not int for field in ("page_number", "width", "height"))):
        raise ValueError("TSV page mapping/dimensions do not match the original frame.")
    word_pages = run.get("tsv_word_page_numbers")
    if not isinstance(word_pages, list) or not word_pages or any(type(page) is not int or page != 1 for page in word_pages):
        raise ValueError("TSV word page mapping must attest page 1.")
    config = _object(run.get("configuration"), "configuration")
    required_config = ("executable", "language", "requested_page_segmentation_mode",
                       "effective_page_segmentation_mode", "engine_mode", "dpi")
    if any(not isinstance(config.get(field), str) for field in required_config) or not config["executable"].strip():
        raise ValueError("Tesseract configuration is incomplete.")
    if config["language"] != primary["language"] or payload.get("ocr_language") != config["language"]:
        raise ValueError("Tesseract language does not match primary evidence.")
    if payload.get("ocr_effective_page_segmentation_mode") != config["effective_page_segmentation_mode"]:
        raise ValueError("Effective Tesseract configuration is inconsistent.")
    if not isinstance(run.get("attempts"), list) or not run["attempts"]:
        raise ValueError("Tesseract provenance requires recorded attempts.")
    if not any(isinstance(attempt, Mapping) and attempt.get("input") == "original"
               and attempt.get("input_sha256") == expected_hash and attempt.get("status") == "selected"
               and attempt.get("page_segmentation_mode") == config["effective_page_segmentation_mode"]
               for attempt in run["attempts"]):
        raise ValueError("Tesseract attempts do not attest the selected original configuration.")
    if (type(payload.get("ocr_page_width")) is not int or type(payload.get("ocr_page_height")) is not int
            or payload["ocr_page_width"] != dimensions["width"]
            or payload["ocr_page_height"] != dimensions["height"]):
        raise ValueError("Tesseract layout dimensions do not match the original frame.")
    lines = payload.get("ocr_layout_lines")
    if (not isinstance(lines, list) or not lines or type(payload.get("ocr_line_count")) is not int
            or payload["ocr_line_count"] != len(lines)):
        raise ValueError("Tesseract requires nonempty, complete TSV layout lines.")
    regions = []
    for line in lines:
        line = _object(line, "TSV layout line")
        if (line.get("source_document_id") != document_id or type(line.get("page_number")) is not int
                or line["page_number"] != 1 or line.get("page_id") != "tesseract-page-1"):
            raise ValueError("TSV line page/source mapping is inconsistent.")
        left, top, width, height = [_finite(line.get(field), field) for field in ("left", "top", "width", "height")]
        if width <= 0 or height <= 0 or left < 0 or top < 0 or left + width > dimensions["width"] or top + height > dimensions["height"]:
            raise ValueError("TSV line geometry lies outside original dimensions or has no area.")
        confidence = _finite(line.get("confidence"), "confidence")
        if not 0 <= confidence <= 100:
            raise ValueError("TSV line confidence must be in Tesseract's 0..100 range.")
        regions.append({
            "region_id": line.get("region_id"), "text": line.get("text"),
            "geometry": {"bbox": [left, top, left + width, top + height]},
            "confidence": confidence, "confidence_scale": "tesseract_0_100",
            "source_tsv_line": line,
        })
    result = {
        "@type": "OcrPageEvidence", "schema_version": "1.0",
        **{field: primary[field] for field in ("page_id", "source_image_hash", "source_page", "language", "transform_id", "image_transform")},
        "engine": "tesseract", "model": {"configuration": config, "transcription_method": payload["transcription_method"]},
        "regions": regions, "ocr_run_provenance": run,
        "adapter": {"name": "tesseract_original_page_v1", "diagnostic_only": True,
                    "machine_pass_allowed": False, "visual_coverage_verified": False,
                    "source_document_id": document_id},
    }
    _identity(result)
    _regions(result)
    return result


def _copy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, allow_nan=False, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("Adapter input must be finite JSON data.") from exc


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Adapter requires {field} object.")
    return value


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"TSV {field} must be a finite number.")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError(f"TSV {field} must be a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"TSV {field} must be a finite number.")
    return number
