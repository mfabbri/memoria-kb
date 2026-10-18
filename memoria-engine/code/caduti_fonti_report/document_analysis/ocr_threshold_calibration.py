"""Deterministic calibration-only cutoff selection; never activates OCR acceptance."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .ocr_threshold_audit import (
    CONFIDENCE_LEVEL, MATERIAL_ERROR_CATEGORIES, MAX_PAGE_MATERIAL_WORD_ERROR_RATE,
    TARGET_FALSE_ACCEPT_PAGE_RATE, _clopper_pearson_upper, _is_sha256, _parse_timestamp,
)


def calibrate_ocr_threshold(*, dataset_path: Path) -> dict[str, Any]:
    """Freeze a threshold using only explicitly declared calibration cases.

    The selection bound is a tuning criterion, not independent holdout evidence.
    ``calibration_sha256`` binds the exact input bytes, including score provenance.
    """
    raw = Path(dataset_path).read_bytes()
    try:
        dataset = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Dataset calibration JSON non valido.") from exc
    _validate(dataset)
    strata = dataset["required_strata"]
    alpha = (1 - CONFIDENCE_LEVEL) / len(strata)
    cases = dataset["cases"]
    selected = None
    # Include tied scores together; never optimize on an arbitrary page ordering.
    for cutoff in sorted({case["score"] for case in cases}):
        summaries = {}
        for stratum in strata:
            accepted = [case for case in cases if case["stratum"] == stratum and case["score"] <= cutoff]
            errors = sum(100 * case["material_word_error_count"] > case["reference_word_count"]
                         for case in accepted)
            upper = _clopper_pearson_upper(errors, len(accepted), alpha) if accepted else 1.0
            summaries[stratum] = {"accepted_page_count": len(accepted), "page_limit_breaches": errors,
                                  "selection_upper_bound": upper}
        if all(item["selection_upper_bound"] <= TARGET_FALSE_ACCEPT_PAGE_RATE for item in summaries.values()):
            selected = (cutoff, summaries)
    if selected is None:
        raise ValueError("Nessun cutoff supportato: campioni per strato insufficienti o rischio calibration eccessivo.")
    cutoff, summaries = selected
    digest = hashlib.sha256(raw).hexdigest()
    report = {
        "@type": "OcrAutoValidationCalibrationArtifact", "schema_version": "1.0",
        "dataset_sha256": digest,
        "threshold": {
            "score_name": dataset["score_name"], "direction": "lower_is_safer", "cutoff": cutoff,
            "calibration_id": dataset["calibration_id"], "calibration_sha256": digest,
            "frozen_at": dataset["frozen_at"], "frozen_before_holdout": True,
        },
        "selection": {"method": "largest_observed_cutoff_with_all_strata_bonferroni_cp_upper_at_most_0.05",
                      "max_page_material_word_error_rate": MAX_PAGE_MATERIAL_WORD_ERROR_RATE,
                      "target_false_accept_page_rate": TARGET_FALSE_ACCEPT_PAGE_RATE,
                      "confidence_level": CONFIDENCE_LEVEL, "strata": summaries,
                      "case_count": len(cases), "partition": "calibration"},
        "status": "frozen_calibration_requires_independent_holdout_audit",
        "machine_pass": False, "auto_validation_enabled": False,
        "limitations": ["Selection bounds on tuning data do not establish holdout accuracy.",
                        "Partition and chronology are supplied declarations; independent holdout audit remains required."],
    }
    report["artifact_payload_sha256"] = hashlib.sha256(
        json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return report


def _validate(dataset: Any) -> None:
    if (not isinstance(dataset, dict) or dataset.get("@type") != "OcrAutoValidationCalibration"
            or dataset.get("schema_version") != "1.0"):
        raise ValueError("Richiesto OcrAutoValidationCalibration v1.0.")
    if dataset.get("partition") != "calibration" or dataset.get("holdout_not_opened") is not True:
        raise ValueError("Sono ammesse solo partition=calibration e holdout_not_opened=true.")
    if dataset.get("direction") != "lower_is_safer":
        raise ValueError("direction deve essere lower_is_safer.")
    for field in ("calibration_id", "score_name"):
        if not isinstance(dataset.get(field), str) or not dataset[field].strip():
            raise ValueError(f"{field} mancante.")
    _parse_timestamp(dataset.get("frozen_at"), "frozen_at")
    strata = dataset.get("required_strata")
    if (not isinstance(strata, list) or not strata
            or any(not isinstance(item, str) or not item.strip() for item in strata)
            or len(set(strata)) != len(strata)):
        raise ValueError("required_strata deve elencare strati unici e non vuoti.")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases calibration mancanti.")
    seen: dict[str, set[str]] = {field: set() for field in ("page_id", "source_document_id", "source_image_sha256")}
    for case in cases:
        if (not isinstance(case, dict) or case.get("partition") != "calibration"
                or case.get("review_status") != "human_verified" or case.get("accuracy_eligible") is not True):
            raise ValueError("Ogni caso deve essere calibration, human_verified e accuracy_eligible.")
        for field in ("page_id", "source_document_id", "reference_id"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"{field} mancante.")
        for field in ("source_image_sha256", "reference_evaluation_sha256", "score_source_sha256"):
            if not _is_sha256(case.get(field)):
                raise ValueError(f"{field} non valido.")
        for field, values in seen.items():
            if case[field] in values:
                raise ValueError(f"{field} duplicato.")
            values.add(case[field])
        if case.get("stratum") not in strata:
            raise ValueError("Strato non dichiarato.")
        score = case.get("score")
        try:
            finite_score = isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score)
        except OverflowError:
            finite_score = False
        if not finite_score:
            raise ValueError("score deve essere numerico finito.")
        for field, minimum in (("material_word_error_count", 0), ("reference_word_count", 1)):
            value = case.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{field} non valido.")
        categories = case.get("material_error_categories")
        if (not isinstance(categories, list) or any(not isinstance(item, str) or item not in MATERIAL_ERROR_CATEGORIES for item in categories)
                or len(set(categories)) != len(categories)
                or bool(categories) != (case["material_word_error_count"] > 0)):
            raise ValueError("material_error_categories incomplete o non valide.")
