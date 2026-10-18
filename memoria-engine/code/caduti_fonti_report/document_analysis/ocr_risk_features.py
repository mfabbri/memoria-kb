"""Versioned descriptive OCR features; no calibrated risk or acceptance score."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any

from .ocr_candidate_assessment import build_ocr_candidate_assessment
from .ocr_evidence_comparison import compare_ocr_page_evidence


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _read(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Input must be a JSON object: {path}")
    _canonical(value)
    return value, hashlib.sha256(raw).hexdigest()


def _confidence_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    """Summarize native region confidence without mixing units or engines."""
    regions = evidence["regions"]
    values: list[float] = []
    scales: set[str] = set()
    missing_count = invalid_count = missing_scale_count = 0
    for region in regions:
        value = region.get("confidence")
        if value is None:
            missing_count += 1
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            invalid_count += 1
            continue
        scale = region.get("confidence_scale")
        if not isinstance(scale, str) or not scale.strip():
            missing_scale_count += 1
        else:
            scales.add(scale.strip())
        values.append(float(value))

    summary: dict[str, Any] = {
        "status": "not_exposed",
        "region_count": len(regions),
        "confidence_count": len(values),
        "missing_count": missing_count,
        "invalid_count": invalid_count,
        "missing_scale_count": missing_scale_count,
        "confidence_coverage_ratio": len(values) / len(regions) if regions else None,
        "confidence_scale": next(iter(scales)) if len(scales) == 1 else None,
        "confidence_scales": sorted(scales),
        "mean": None,
        "median": None,
        "p10": None,
        "min": None,
        "max": None,
    }
    if invalid_count:
        summary["status"] = "invalid_values"
    elif missing_scale_count:
        summary["status"] = "scale_missing"
    elif len(scales) > 1:
        summary["status"] = "mixed_scales"
    elif values:
        ordered = sorted(values)
        p10_index = max(0, math.ceil(0.10 * len(ordered)) - 1)
        summary.update({
            "status": "available",
            "mean": round(mean(values), 6),
            "median": round(median(values), 6),
            "p10": round(ordered[p10_index], 6),
            "min": round(ordered[0], 6),
            "max": round(ordered[-1], 6),
        })
    return summary


def build_ocr_risk_features(
    *, assessment_path: Path, structure_path: Path, markdown_path: Path,
    evidence_path: Path, lexicon_review_path: Path, comparison_path: Path,
    left_path: Path, right_path: Path, image_path: Path, output_path: Path, apply: bool = False,
) -> dict[str, Any]:
    """Recompute both diagnostics from exact sources, rejecting divergent reports.

    Paths in reports must match the explicit source paths. Hashes attest current
    artifact bytes, not image authenticity or OCR correctness. Source image
    bytes are hashed; no image decoding, reference, OCR engine, or model is used.
    """
    paths = {name: Path(path) for name, path in {
        "assessment": assessment_path, "structure": structure_path, "markdown": markdown_path,
        "evidence": evidence_path, "lexicon_review": lexicon_review_path,
        "comparison": comparison_path, "left": left_path, "right": right_path,
        "image": image_path,
    }.items()}
    if Path(output_path).resolve() in {path.resolve() for path in paths.values()}:
        raise ValueError("Output must not replace an input artifact.")
    before = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    assessment, _ = _read(paths["assessment"])
    comparison, _ = _read(paths["comparison"])
    left, _ = _read(paths["left"])
    right, _ = _read(paths["right"])
    candidate, _ = _read(paths["evidence"])
    structure, _ = _read(paths["structure"])
    document_id = candidate.get("source_document_id")
    if (not isinstance(document_id, str) or not document_id.strip()
            or any(evidence.get("source_document_id") != document_id for evidence in (left, right))):
        raise ValueError("Evidence source_document_id must be present and equal across candidate, left and right.")
    if any(evidence.get("source_image_hash") != before["image"]
           for evidence in (candidate, left, right)):
        raise ValueError("Source image bytes do not match evidence source_image_hash.")
    if before["evidence"] not in (before["left"], before["right"]):
        raise ValueError("Candidate evidence is not an exact comparison input.")
    recomputed_assessment = build_ocr_candidate_assessment(
        structure_path=paths["structure"], markdown_path=paths["markdown"],
        evidence_path=paths["evidence"], lexicon_review_path=paths["lexicon_review"],
        output_path=paths["assessment"], apply=False,
    )
    operational = {"operation_status", "output_path"}
    substantive = lambda value: {key: item for key, item in value.items() if key not in operational}
    if _canonical(substantive(assessment)) != _canonical(substantive(recomputed_assessment)):
        raise ValueError("Stale or divergent candidate assessment.")
    if any("identity" in issue["code"] for issue in recomputed_assessment["checks"]["issues"]):
        raise ValueError("Candidate assessment has incompatible page/image/frame identity.")
    recomputed = compare_ocr_page_evidence(left=left, right=right)
    expected_inputs = {
        side: {"path": str(paths[side]), "sha256": before[side]} for side in ("left", "right")
    }
    if comparison.get("inputs") != expected_inputs:
        raise ValueError("Stale comparison input hashes or paths.")
    wrapper = {
        "machine_pass": False, "auto_validation_enabled": False,
        "semantic_accuracy_status": "not_attested", "review_status": "unreviewed",
        "promotion_status": "unreviewed",
    }
    for key, value in wrapper.items():
        if key in comparison and _canonical(comparison[key]) != _canonical(value):
            raise ValueError(f"Invalid comparison safety field: {key}")
    comparison_core = {key: value for key, value in comparison.items()
                       if key not in operational | set(wrapper) | {"inputs"}}
    if _canonical(comparison_core) != _canonical(recomputed):
        raise ValueError("Stale or divergent evidence comparison.")
    # Guard against source updates during recomputation; never emit mixed snapshots.
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != before[name]
           for name, path in paths.items()):
        raise ValueError("Input artifact changed during feature extraction.")
    diagnostics = recomputed_assessment["diagnostics"]
    coverage = diagnostics["region_coverage"]
    agreements = len(recomputed["agreements"])
    disagreements = len(recomputed["disagreements"])
    pairs = agreements + disagreements
    features = {
        "assessment_issue_count": recomputed_assessment["checks"]["issue_count"],
        "candidate_block_count": len(structure["blocks"]),
        "lexical_alert_count": diagnostics["lexical_alert_count"],
        "pending_lexical_group_count": diagnostics["pending_classification_group_count"],
        "evidence_region_count": coverage["evidence_region_count"],
        "represented_region_count": coverage["represented_region_count"],
        "evidence_region_coverage_ratio": coverage["coverage_ratio"],
        "left_region_count": len(left["regions"]), "right_region_count": len(right["regions"]),
        "normalized_agreement_pair_count": agreements,
        "exact_agreement_pair_count": sum(pair["exact_agreement"] for pair in recomputed["agreements"]),
        "disagreement_pair_count": disagreements,
        "one_to_one_pair_count": pairs,
        "disagreement_pair_ratio": disagreements / pairs if pairs else None,
        "ambiguous_overlap_component_count": len(recomputed["ambiguous_overlaps"]),
        "unmatched_left_region_count": len(recomputed["unmatched_left_region_ids"]),
        "unmatched_right_region_count": len(recomputed["unmatched_right_region_ids"]),
        "confidence_by_evidence": {
            "left": _confidence_summary(left),
            "right": _confidence_summary(right),
        },
    }
    payload = {
        "@type": "OcrRiskFeatureBundle", "schema_version": "1.1", "feature_version": "1.1",
        "inputs": {name: {"path": str(path), "sha256": before[name]} for name, path in paths.items()},
        "candidate_identity": {key: candidate.get(key) for key in (
            "source_document_id", "page_id", "source_image_hash", "source_page", "transform_id", "image_transform", "engine", "model", "language")},
        "left_evidence": recomputed["left_evidence"], "right_evidence": recomputed["right_evidence"],
        "features": features,
        "feature_semantics": {
            "evidence_region_coverage_ratio": "Represented OCR regions / candidate evidence regions; not image coverage.",
            "disagreement_pair_ratio": "Disagreeing one-to-one overlap pairs / all one-to-one pairs; null without pairs.",
            "unmatched_regions": "Includes ambiguous split/merge regions; counts overlap with ambiguity diagnostics.",
            "lexical_alert_count": "Dictionary alerts, not material errors or manual actions.",
            "confidence_by_evidence": "Per-region native confidence summaries stay separate by evidence and are not word-weighted. p10 uses the nearest-rank definition. Values are not normalized or compared across engines; no confidence-to-risk mapping is calibrated.",
        },
        "processability_status": recomputed_assessment["processability_status"],
        "score_status": "not_calibrated", "risk_score": None, "cutoff": None,
        "diagnostic_only": True, "auto_validation_enabled": False, "machine_pass": False,
        "visual_coverage_status": "not_assessed", "shared_omission_detection_performed": False,
        "semantic_accuracy_status": "not_attested", "claim_extraction_allowed": False,
    }
    payload["@id"] = "ocr-risk-features:" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    status = "preview"
    if apply:
        target = Path(output_path)
        if target.exists():
            if target.read_text(encoding="utf-8") != encoded:
                raise ValueError(f"Output already exists and differs: {target}")
            status = "skipped_existing"
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
            status = "written"
    return payload | {"operation_status": status, "output_path": str(output_path)}
