"""Deterministic candidate diagnostic index; neither probability nor calibration."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


SCORE_SPEC = {
    "version": "ocr-coverage-disagreement-max-v1",
    "formula": "max(1 - evidence_region_coverage_ratio, disagreement_pair_ratio)",
    "components": {
        "D": "disagreement_pair_count/one_to_one_pair_count",
        "C": "1-evidence_region_coverage_ratio",
    },
    "direction": "lower_is_safer",
    "interpretation": "candidate_diagnostic_index_not_probability_not_calibrated",
    "limitations": ["Shared omissions by both recognizers are not detected.",
                    "Region counts are not material word error rates or image coverage."],
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def build_ocr_risk_score(*, bundle_path: Path, output_path: Path, apply: bool = False) -> dict[str, Any]:
    """Bind a diagnostic index to exact bundle bytes; never consult labels or sources.

    Absent features and zero denominators emit not_scorable. Invalid supplied
    values raise ValueError before any output is written.
    """
    source, target = Path(bundle_path), Path(output_path)
    if source.resolve() == target.resolve():
        raise ValueError("Output must not replace the source bundle.")
    raw = source.read_bytes()
    bundle = json.loads(raw.decode("utf-8"))
    if not isinstance(bundle, dict) or bundle.get("@type") != "OcrRiskFeatureBundle":
        raise ValueError("Expected OcrRiskFeatureBundle.")
    if bundle.get("schema_version") != "1.1" or bundle.get("feature_version") != "1.1":
        raise ValueError("Unsupported OCR feature bundle version.")
    # Reject nonfinite JSON, even in fields not used by this formula.
    _canonical(bundle)
    identity = bundle.get("candidate_identity")
    if not isinstance(identity, dict):
        raise ValueError("Missing candidate_identity.")
    for key in ("source_document_id", "page_id", "source_image_hash", "transform_id", "engine", "language"):
        if not isinstance(identity.get(key), str) or not identity[key].strip():
            raise ValueError(f"Missing or invalid candidate identity: {key}")
    digest = identity["source_image_hash"]
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("Invalid candidate source_image_hash.")
    for key in ("source_page", "image_transform", "model"):
        if not isinstance(identity.get(key), dict) or not identity[key]:
            raise ValueError(f"Missing or invalid candidate identity: {key}")
    features = bundle.get("features")
    if features is None:
        features = {}
    if not isinstance(features, dict):
        raise ValueError("features must be an object.")
    reasons: list[str] = []
    issue_count = features.get("assessment_issue_count")
    if issue_count is None:
        reasons.append("missing_feature:assessment_issue_count")
    elif type(issue_count) is not int or issue_count < 0:
        raise ValueError("Invalid nonnegative integer: assessment_issue_count")
    elif issue_count:
        reasons.append("assessment_issues_present")
    processability = bundle.get("processability_status")
    if processability is None:
        reasons.append("missing_processability_status")
    elif processability == "blocked":
        reasons.append("source_processability_blocked")
    elif processability != "diagnostic_only":
        raise ValueError("Unknown source processability_status.")
    for key in ("machine_pass", "auto_validation_enabled"):
        if key in bundle and bundle[key] is not False:
            raise ValueError(f"Inconsistent source safety field: {key}")
    for key in ("risk_score", "cutoff"):
        if bundle.get(key) is not None:
            raise ValueError(f"Feature bundle must not already contain {key}.")
    counts: dict[str, int | None] = {}
    for key in ("disagreement_pair_count", "one_to_one_pair_count", "left_region_count", "right_region_count",
                "unmatched_left_region_count", "unmatched_right_region_count", "evidence_region_count",
                "represented_region_count", "normalized_agreement_pair_count", "exact_agreement_pair_count"):
        value = features.get(key)
        if value is None:
            reasons.append("missing_feature:" + key)
        elif type(value) is not int or value < 0:
            raise ValueError(f"Invalid nonnegative integer: {key}")
        counts[key] = value
    ratios: dict[str, float | None] = {}
    for key in ("evidence_region_coverage_ratio", "disagreement_pair_ratio"):
        value = features.get(key)
        if value is None:
            reasons.append("missing_feature:" + key)
        elif (isinstance(value, bool) or not isinstance(value, (int, float))
              or not 0 <= value <= 1 or not math.isfinite(value)):
            raise ValueError(f"Invalid bounded ratio: {key}")
        ratios[key] = value

    def within(part: str, total: str) -> None:
        if counts[part] is not None and counts[total] is not None and counts[part] > counts[total]:
            raise ValueError(f"Inconsistent counts: {part} exceeds {total}")

    for part, total in (("disagreement_pair_count", "one_to_one_pair_count"),
                        ("exact_agreement_pair_count", "normalized_agreement_pair_count"),
                        ("represented_region_count", "evidence_region_count"),
                        ("unmatched_left_region_count", "left_region_count"),
                        ("unmatched_right_region_count", "right_region_count")):
        within(part, total)
    pairs = counts["one_to_one_pair_count"]
    disagreements = counts["disagreement_pair_count"]
    agreements = counts["normalized_agreement_pair_count"]
    if all(value is not None for value in (pairs, disagreements, agreements)) and agreements + disagreements != pairs:
        raise ValueError("Agreement and disagreement counts do not sum to pairs.")
    for side in ("left", "right"):
        total, unmatched = counts[side + "_region_count"], counts["unmatched_" + side + "_region_count"]
        if all(value is not None for value in (pairs, total, unmatched)) and pairs + unmatched != total:
            raise ValueError(f"Inconsistent {side} paired/unmatched region counts.")
    for numerator, denominator, ratio_key in (
        (disagreements, pairs, "disagreement_pair_ratio"),
        (counts["represented_region_count"], counts["evidence_region_count"], "evidence_region_coverage_ratio"),
    ):
        ratio = ratios[ratio_key]
        if denominator == 0:
            reasons.append("zero_denominator:" + ratio_key)
            if ratio is not None:
                raise ValueError(f"Ratio must be null for zero denominator: {ratio_key}")
        elif numerator is not None and denominator is not None and ratio is not None:
            if not math.isclose(ratio, numerator / denominator, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError(f"Ratio disagrees with counts: {ratio_key}")
    left, right = counts["left_region_count"], counts["right_region_count"]
    if left == right == 0:
        reasons.append("zero_denominator:total_region_count")
    if counts["evidence_region_count"] is not None and left is not None and right is not None:
        if counts["evidence_region_count"] not in (left, right):
            raise ValueError("Candidate evidence count is not a comparison side count.")
    components = None
    if not reasons:
        components = {"D": ratios["disagreement_pair_ratio"],
                      "C": 1 - ratios["evidence_region_coverage_ratio"]}
    payload = {
        "@type": "OcrRiskScore", "schema_version": "1.0",
        "feature_version": bundle["feature_version"],
        "score_spec": SCORE_SPEC,
        "score_spec_sha256": hashlib.sha256(_canonical(SCORE_SPEC).encode("utf-8")).hexdigest(),
        "inputs": {"bundle": {"path": str(source), "sha256": hashlib.sha256(raw).hexdigest()}},
        "candidate_identity": identity,
        "score_status": "not_scorable" if reasons else "diagnostic_only",
        "not_scorable_reasons": reasons, "components": components,
        "risk_score": max(components.values()) if components is not None else None,
        "direction": "lower_is_safer", "cutoff": None,
        "machine_pass": False, "auto_validation_enabled": False, "diagnostic_only": True,
        "shared_omission_detection_performed": False, "semantic_accuracy_status": "not_attested",
        "claim_extraction_allowed": False,
    }
    payload["@id"] = "ocr-risk-score:" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if source.read_bytes() != raw:
        raise ValueError("Source bundle changed during scoring.")
    status = "preview"
    if apply:
        if target.exists():
            if target.read_text(encoding="utf-8") != encoded:
                raise ValueError(f"Output already exists and differs: {target}")
            status = "skipped_existing"
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
            status = "written"
    return payload | {"operation_status": status, "output_path": str(target)}
