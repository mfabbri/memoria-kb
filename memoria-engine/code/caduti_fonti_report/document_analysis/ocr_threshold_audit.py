"""Fail-closed audit of per-page quality and auto-acceptance risk thresholds.

The first threshold limits material word errors per reference word on a page.
The second bounds the share of auto-accepted pages that exceed that page limit.
The audit never changes OCR candidate status itself.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


MAX_PAGE_MATERIAL_WORD_ERROR_RATE = 0.01
TARGET_FALSE_ACCEPT_PAGE_RATE = 0.05
CONFIDENCE_LEVEL = 0.95
MATERIAL_ERROR_CATEGORIES = {"text", "omission", "number_or_name", "structure"}


def audit_ocr_auto_validation_threshold(
    *, dataset_path: Path, cohort_manifest_path: Path
) -> dict[str, Any]:
    """Audit a frozen threshold against human-verified, page-level holdout data."""
    path = Path(dataset_path)
    manifest_path = Path(cohort_manifest_path)
    raw = path.read_bytes()
    manifest_raw = manifest_path.read_bytes()
    try:
        dataset = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Dataset holdout non leggibile o JSON non valido: {exc}") from exc
    try:
        cohort_manifest = json.loads(manifest_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Manifest coorte non leggibile o JSON non valido: {exc}") from exc
    _validate_dataset(dataset)
    cohort_pages = _validate_cohort_manifest(
        cohort_manifest,
        dataset=dataset,
        manifest_raw=manifest_raw,
    )
    _validate_cohort_cases(dataset["cases"], cohort_pages)

    threshold = dataset["threshold"]
    cutoff = threshold["cutoff"]
    required_strata = dataset["required_strata"]
    accepted_by_stratum: dict[str, list[tuple[dict[str, Any], float]]] = {
        name: [] for name in required_strata
    }
    seen_pages: set[str] = set()
    for case in dataset["cases"]:
        page_id = case["page_id"]
        if page_id in seen_pages:
            raise ValueError(f"page_id duplicato nel holdout: {page_id}")
        seen_pages.add(page_id)
        if case["stratum"] not in accepted_by_stratum:
            raise ValueError(f"Strato non pre-dichiarato: {case['stratum']}")
        page_error_rate = case["material_word_error_count"] / case["reference_word_count"]
        if case["score"] <= cutoff:
            accepted_by_stratum[case["stratum"]].append((case, page_error_rate))

    strata: dict[str, dict[str, Any]] = {}
    all_accepted = [item for cases in accepted_by_stratum.values() for item in cases]
    per_stratum_alpha = (1.0 - CONFIDENCE_LEVEL) / len(required_strata)
    for name, items in accepted_by_stratum.items():
        breaches = sum(rate > MAX_PAGE_MATERIAL_WORD_ERROR_RATE for _, rate in items)
        upper = _clopper_pearson_upper(breaches, len(items), per_stratum_alpha) if items else None
        strata[name] = {
            "auto_accepted_page_count": len(items),
            "pages_over_page_word_error_limit": breaches,
            "observed_false_accept_page_rate": breaches / len(items) if items else None,
            "bonferroni_familywise_95_percent_upper_bound": upper,
            "meets_5_percent_false_accept_target": (
                upper is not None and upper <= TARGET_FALSE_ACCEPT_PAGE_RATE
            ),
        }

    breach_count = sum(rate > MAX_PAGE_MATERIAL_WORD_ERROR_RATE for _, rate in all_accepted)
    pooled_upper = (
        _clopper_pearson_upper(breach_count, len(all_accepted), 1.0 - CONFIDENCE_LEVEL)
        if all_accepted else None
    )
    strata_ready = all(item["meets_5_percent_false_accept_target"] for item in strata.values())
    pooled_ready = pooled_upper is not None and pooled_upper <= TARGET_FALSE_ACCEPT_PAGE_RATE
    eligible = strata_ready and pooled_ready
    return {
        "@type": "OcrAutoValidationThresholdAudit",
        "schema_version": "1.2",
        "dataset": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
        "cohort": {
            "cohort_id": cohort_manifest["cohort_id"],
            "manifest_path": str(manifest_path),
            "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "registered_page_count": len(cohort_pages),
        },
        "policy": {
            "max_page_material_word_error_rate": MAX_PAGE_MATERIAL_WORD_ERROR_RATE,
            "target_false_accept_page_rate": TARGET_FALSE_ACCEPT_PAGE_RATE,
            "confidence_level": CONFIDENCE_LEVEL,
            "interval": "one_sided_exact_binomial_clopper_pearson",
            "stratum_multiplicity_adjustment": "bonferroni_familywise_95_percent",
            "page_error_unit": "material_word_errors_per_reference_word",
            "system_error_unit": "auto_accepted_pages_over_page_word_error_limit",
            "material_error_scope": ["text", "omission", "number_or_name", "structure"],
        },
        "threshold": threshold,
        "holdout": {
            "case_count": len(dataset["cases"]),
            "auto_accepted_page_count": len(all_accepted),
            "pages_over_page_word_error_limit": breach_count,
            "observed_false_accept_page_rate": (
                breach_count / len(all_accepted) if all_accepted else None
            ),
            "one_sided_95_percent_upper_bound": pooled_upper,
            "required_strata": required_strata,
            "strata": strata,
        },
        "pilot_activation_eligible": eligible,
        "machine_pass": False,
        "auto_validation_enabled": False,
        "status": "pilot_threshold_supported" if eligible else "no_go_holdout_evidence_insufficient_or_risk_too_high",
        "limitations": [
            "This audit does not activate auto-validation or set machine_pass.",
            "Holdout labels and stratum assignments must be independently verified and representative.",
            "The score and cutoff must have been frozen using calibration data before this holdout was opened.",
        ],
    }


def _validate_dataset(dataset: Any) -> None:
    if not isinstance(dataset, dict) or dataset.get("@type") != "OcrAutoValidationHoldout":
        raise ValueError("Dataset richiesto: @type OcrAutoValidationHoldout.")
    if dataset.get("schema_version") != "1.2":
        raise ValueError("schema_version holdout non supportata.")
    policy = dataset.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("policy holdout non valida.")
    if policy.get("max_page_material_word_error_rate") != MAX_PAGE_MATERIAL_WORD_ERROR_RATE:
        raise ValueError("Il limite per pagina deve essere 0.01 (1% delle parole reference).")
    if policy.get("target_false_accept_page_rate") != TARGET_FALSE_ACCEPT_PAGE_RATE:
        raise ValueError("Il target di false accettazioni deve essere 0.05 (5% delle pagine).")
    if policy.get("confidence_level") != CONFIDENCE_LEVEL:
        raise ValueError("Il livello di confidenza del pilot deve essere 0.95.")
    threshold = dataset.get("threshold")
    if (not isinstance(threshold, dict) or threshold.get("direction") != "lower_is_safer"
            or not isinstance(threshold.get("score_name"), str) or not threshold["score_name"].strip()
            or not isinstance(threshold.get("calibration_id"), str) or not threshold["calibration_id"].strip()
            or not _is_sha256(threshold.get("calibration_sha256"))
            or not isinstance(threshold.get("cutoff"), (int, float))
            or isinstance(threshold.get("cutoff"), bool) or not math.isfinite(threshold["cutoff"])
            or threshold.get("frozen_before_holdout") is not True):
        raise ValueError("Soglia non valida: servono score, cutoff, calibration_id/hash e frozen_before_holdout=true.")
    threshold_frozen_at = _parse_timestamp(threshold.get("frozen_at"), "threshold.frozen_at")
    if not isinstance(dataset.get("cohort_id"), str) or not dataset["cohort_id"].strip():
        raise ValueError("Dataset senza cohort_id.")
    if not _is_sha256(dataset.get("cohort_manifest_sha256")):
        raise ValueError("Dataset senza SHA-256 valido del manifest coorte.")
    required_strata = dataset.get("required_strata")
    if (not isinstance(required_strata, list) or not required_strata
            or any(not isinstance(item, str) or not item.strip() for item in required_strata)
            or len(set(required_strata)) != len(required_strata)):
        raise ValueError("required_strata deve elencare strati pre-dichiarati, unici e non vuoti.")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases deve contenere pagine holdout adjudicate.")
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{index}] non e' un oggetto.")
        if case.get("partition") != "holdout" or case.get("review_status") != "human_verified":
            raise ValueError(f"cases[{index}] deve essere holdout e human_verified.")
        if case.get("accuracy_eligible") is not True:
            raise ValueError(f"cases[{index}] non e' una reference OCR accuracy-eligible.")
        if not isinstance(case.get("page_id"), str) or not case["page_id"].strip():
            raise ValueError(f"cases[{index}] senza page_id.")
        if not isinstance(case.get("source_document_id"), str) or not case["source_document_id"].strip():
            raise ValueError(f"cases[{index}] senza source_document_id.")
        if not _is_sha256(case.get("source_image_sha256")):
            raise ValueError(f"cases[{index}] senza SHA-256 TIFF valido.")
        if not isinstance(case.get("stratum"), str) or not case["stratum"].strip():
            raise ValueError(f"cases[{index}] senza stratum.")
        if not isinstance(case.get("score"), (int, float)) or isinstance(case.get("score"), bool) or not math.isfinite(case["score"]):
            raise ValueError(f"cases[{index}] score non numerico.")
        error_count = case.get("material_word_error_count")
        reference_word_count = case.get("reference_word_count")
        if (not isinstance(error_count, int) or isinstance(error_count, bool) or error_count < 0):
            raise ValueError(f"cases[{index}] material_word_error_count deve essere un intero >= 0.")
        if (not isinstance(reference_word_count, int) or isinstance(reference_word_count, bool)
                or reference_word_count <= 0):
            raise ValueError(f"cases[{index}] reference_word_count deve essere un intero > 0.")
        categories = case.get("material_error_categories")
        if (not isinstance(categories, list)
                or any(category not in MATERIAL_ERROR_CATEGORIES for category in categories)
                or len(set(categories)) != len(categories)
                or bool(categories) != (error_count > 0)):
            raise ValueError(
                f"cases[{index}] material_error_categories deve elencare categorie valide "
                "se material_word_error_count > 0, altrimenti deve essere vuota."
            )
        if not isinstance(case.get("reference_id"), str) or not case["reference_id"].strip():
            raise ValueError(f"cases[{index}] senza reference_id.")
        if not _is_sha256(case.get("reference_evaluation_sha256")):
            raise ValueError(f"cases[{index}] senza digest dell'evaluation human-verified.")
        if not _is_sha256(case.get("score_source_sha256")):
            raise ValueError(f"cases[{index}] senza digest della sorgente dello score.")


def _validate_cohort_manifest(
    manifest: Any,
    *,
    dataset: dict[str, Any],
    manifest_raw: bytes,
) -> dict[str, dict[str, Any]]:
    if not isinstance(manifest, dict) or manifest.get("@type") != "OcrAutoValidationHoldoutCohort":
        raise ValueError("Manifest richiesto: @type OcrAutoValidationHoldoutCohort.")
    if manifest.get("schema_version") != "1.1":
        raise ValueError("schema_version manifest coorte non supportata.")
    cohort_id = manifest.get("cohort_id")
    if not isinstance(cohort_id, str) or not cohort_id.strip():
        raise ValueError("Manifest coorte senza cohort_id.")
    if manifest.get("partition") != "holdout" or manifest.get("frozen_before_threshold") is not True:
        raise ValueError("Manifest coorte deve essere holdout e frozen_before_threshold=true.")
    cohort_frozen_at = _parse_timestamp(manifest.get("frozen_at"), "manifest.frozen_at")
    threshold_frozen_at = _parse_timestamp(dataset["threshold"].get("frozen_at"), "threshold.frozen_at")
    if cohort_frozen_at >= threshold_frozen_at:
        raise ValueError("Il manifest coorte deve essere congelato prima del cutoff.")
    expected_digest = hashlib.sha256(manifest_raw).hexdigest()
    if dataset.get("cohort_id") != cohort_id or dataset.get("cohort_manifest_sha256") != expected_digest:
        raise ValueError("cohort_id o digest del manifest non corrispondente al dataset.")

    required_strata = manifest.get("required_strata")
    if (not isinstance(required_strata, list) or not required_strata
            or any(not isinstance(item, str) or not item.strip() for item in required_strata)
            or len(set(required_strata)) != len(required_strata)):
        raise ValueError("Manifest required_strata deve elencare strati unici e non vuoti.")
    if dataset.get("required_strata") != required_strata:
        raise ValueError("required_strata del dataset non corrisponde al manifest coorte.")
    sampling_design = manifest.get("sampling_design")
    if not isinstance(sampling_design, dict):
        raise ValueError("Manifest coorte senza sampling_design.")
    for field in ("frame", "method"):
        if not isinstance(sampling_design.get(field), str) or not sampling_design[field].strip():
            raise ValueError(f"sampling_design.{field} deve descrivere il campionamento.")
    if sampling_design.get("independence_unit") != "source_document_id":
        raise ValueError("sampling_design.independence_unit deve dichiarare source_document_id.")
    stratum_definitions = manifest.get("stratum_definitions")
    if not isinstance(stratum_definitions, dict) or set(stratum_definitions) != set(required_strata):
        raise ValueError("stratum_definitions deve definire esattamente tutti gli strati richiesti.")
    for stratum, definition in stratum_definitions.items():
        if not isinstance(definition, dict):
            raise ValueError(f"stratum_definitions.{stratum} non valida.")
        for field in ("language", "readability", "layout"):
            if not isinstance(definition.get(field), str) or not definition[field].strip():
                raise ValueError(f"stratum_definitions.{stratum}.{field} mancante.")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Manifest coorte senza pagine preregistrate.")

    cohort_pages: dict[str, dict[str, Any]] = {}
    seen_image_hashes: set[str] = set()
    seen_document_ids: set[str] = set()
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise ValueError(f"pages[{index}] del manifest non e' un oggetto.")
        page_id = page.get("page_id")
        if not isinstance(page_id, str) or not page_id.strip():
            raise ValueError(f"pages[{index}] del manifest senza page_id.")
        if page_id in cohort_pages:
            raise ValueError(f"page_id duplicato nel manifest coorte: {page_id}")
        if not isinstance(page.get("source_document_id"), str) or not page["source_document_id"].strip():
            raise ValueError(f"pages[{index}] del manifest senza source_document_id.")
        if not _is_sha256(page.get("source_image_sha256")):
            raise ValueError(f"pages[{index}] del manifest senza SHA-256 TIFF valido.")
        image_hash = page["source_image_sha256"]
        if image_hash in seen_image_hashes:
            raise ValueError(f"SHA-256 TIFF duplicato nel manifest coorte: {image_hash}.")
        seen_image_hashes.add(image_hash)
        document_id = page["source_document_id"]
        if document_id in seen_document_ids:
            raise ValueError(
                "source_document_id duplicato: il campionamento dichiara unità indipendenti a livello documento."
            )
        seen_document_ids.add(document_id)
        stratum = page.get("stratum")
        if not isinstance(stratum, str) or stratum not in required_strata:
            raise ValueError(f"pages[{index}] del manifest ha strato non preregistrato.")
        definition = stratum_definitions[stratum]
        for field in ("language", "readability", "layout"):
            value = page.get(field)
            if not isinstance(value, str) or value != definition[field]:
                raise ValueError(f"pages[{index}].{field} non corrisponde alla definizione dello strato.")
        if not isinstance(page.get("selection_reason"), str) or not page["selection_reason"].strip():
            raise ValueError(f"pages[{index}] senza selection_reason.")
        exposure = page.get("prior_engine_exposure")
        if (not isinstance(exposure, list) or not exposure or any(
                not isinstance(item, dict)
                or not isinstance(item.get("engine"), str) or not item["engine"].strip()
                or item.get("status") not in {"exposed", "not_exposed", "unknown"}
                for item in exposure)):
            raise ValueError(f"pages[{index}].prior_engine_exposure deve dichiarare engine e status.")
        transformations = page.get("transformations")
        if (not isinstance(transformations, list) or any(
                not isinstance(item, dict)
                or not isinstance(item.get("name"), str) or not item["name"].strip()
                or not isinstance(item.get("applied"), bool)
                or (item.get("output_sha256") is not None and not _is_sha256(item.get("output_sha256")))
                for item in transformations)):
            raise ValueError(f"pages[{index}].transformations deve registrare nome, stato e digest opzionale.")
        cohort_pages[page_id] = page
    return cohort_pages


def _validate_cohort_cases(
    cases: list[dict[str, Any]], cohort_pages: dict[str, dict[str, Any]]
) -> None:
    case_pages: dict[str, dict[str, Any]] = {}
    for case in cases:
        page_id = case["page_id"]
        if page_id in case_pages:
            raise ValueError(f"page_id duplicato nel holdout: {page_id}")
        case_pages[page_id] = case
    missing = sorted(set(cohort_pages) - set(case_pages))
    extra = sorted(set(case_pages) - set(cohort_pages))
    if missing or extra:
        raise ValueError(f"Casi holdout non corrispondono alla coorte; mancanti={missing}, extra={extra}.")
    for page_id, page in cohort_pages.items():
        case = case_pages[page_id]
        for field in ("source_document_id", "source_image_sha256", "stratum"):
            if case.get(field) != page[field]:
                raise ValueError(f"{field} del caso non corrisponde al manifest per {page_id}.")


def _is_sha256(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} deve essere un timestamp ISO-8601 con fuso orario.")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} non e' un timestamp ISO-8601 valido.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} deve includere un fuso orario.")
    return parsed


def _clopper_pearson_upper(errors: int, sample_size: int, alpha: float) -> float:
    """Return the exact one-sided binomial upper confidence limit."""
    if sample_size <= 0 or errors < 0 or errors > sample_size:
        raise ValueError("Conteggi binomiali non validi.")
    if errors == sample_size:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(80):
        probability = (low + high) / 2
        if _binomial_cdf(errors, sample_size, probability) > alpha:
            low = probability
        else:
            high = probability
    return (low + high) / 2


def _binomial_cdf(max_errors: int, sample_size: int, probability: float) -> float:
    if probability <= 0:
        return 1.0
    if probability >= 1:
        return 0.0
    log_p = math.log(probability)
    log_q = math.log1p(-probability)
    terms = [
        math.lgamma(sample_size + 1) - math.lgamma(errors + 1)
        - math.lgamma(sample_size - errors + 1) + errors * log_p
        + (sample_size - errors) * log_q
        for errors in range(max_errors + 1)
    ]
    maximum = max(terms)
    return math.exp(maximum) * sum(math.exp(term - maximum) for term in terms)
