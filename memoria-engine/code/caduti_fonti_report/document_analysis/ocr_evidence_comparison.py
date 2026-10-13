"""Pure, page-scoped diagnostics between distinguishable OCR readings.

Bounding envelopes are compared in an identical declared frame, without a
calibrated overlap threshold. A positive overlap is a candidate relation, not
proof of correct text or original-image coverage. Split/merge components stay
ambiguous. Neither agreement nor unmatched regions detect shared omissions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
from typing import Any
import unicodedata

from .ocr_reference_metrics import _evidence_identity


@dataclass(frozen=True)
class _Region:
    region_id: str
    text: str
    bbox: tuple[float, float, float, float]


def compare_ocr_page_evidence(*, left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """Return diagnostic overlap components, preserving both source readings.

    Fail closed on incompatible page/crop/frame identity or malformed geometry.
    An engine/model difference establishes distinguishable metadata only; it
    cannot establish statistical independence or OCR accuracy. The function has
    no I/O and does not mutate either input.
    """
    left_identity, right_identity = _identity(left), _identity(right)
    for field in ("page_id", "source_image_hash", "source_page", "language",
                  "transform_id", "image_transform"):
        if _json(left_identity[field]) != _json(right_identity[field]):
            raise ValueError(f"Incompatible OCR evidence {field}.")
    if (left_identity["engine"], _json(left_identity["model"])) == (
            right_identity["engine"], _json(right_identity["model"])):
        raise ValueError("OCR readings require distinguishable engine/model metadata.")

    left_regions, right_regions = _regions(left), _regions(right)
    left_edges: dict[str, set[str]] = {region_id: set() for region_id in left_regions}
    right_edges: dict[str, set[str]] = {region_id: set() for region_id in right_regions}
    overlaps: dict[tuple[str, str], float] = {}
    for left_id, left_region in left_regions.items():
        for right_id, right_region in right_regions.items():
            area = _overlap_area(left_region.bbox, right_region.bbox)
            if area > 0:
                left_edges[left_id].add(right_id)
                right_edges[right_id].add(left_id)
                overlaps[left_id, right_id] = area

    agreements: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    matched_left: set[str] = set()
    matched_right: set[str] = set()
    seen_left: set[str] = set()
    for start in sorted(left_edges):
        if start in seen_left or not left_edges[start]:
            continue
        component_left, component_right = {start}, set()
        pending = [start]
        while pending:
            left_id = pending.pop()
            for right_id in sorted(left_edges[left_id]):
                component_right.add(right_id)
                for neighbor in sorted(right_edges[right_id]):
                    if neighbor not in component_left:
                        component_left.add(neighbor)
                        pending.append(neighbor)
        seen_left.update(component_left)
        if len(component_left) == len(component_right) == 1:
            left_id, right_id = next(iter(component_left)), next(iter(component_right))
            left_text, right_text = left_regions[left_id].text, right_regions[right_id].text
            exact = left_text == right_text
            normalized = _normalize(left_text) == _normalize(right_text)
            comparison = {
                "left_region_id": left_id, "right_region_id": right_id,
                "left_text": left_text, "right_text": right_text,
                "overlap_area": overlaps[left_id, right_id],
                "exact_agreement": exact, "normalized_agreement": normalized,
            }
            (agreements if normalized else disagreements).append(comparison)
            matched_left.add(left_id)
            matched_right.add(right_id)
        else:
            ambiguous.append({
                "left_region_ids": sorted(component_left),
                "right_region_ids": sorted(component_right),
                "overlaps": [
                    {"left_region_id": left_id, "right_region_id": right_id, "overlap_area": area}
                    for (left_id, right_id), area in sorted(overlaps.items())
                    if left_id in component_left and right_id in component_right
                ],
            })
    return {
        "@type": "OcrPageEvidenceComparison", "schema_version": "1.0",
        "diagnostic_only": True,
        "text_correction_performed": False, "visual_coverage_verified": False,
        "shared_omission_detection_performed": False, "machine_pass_allowed": False,
        "alignment_policy": "positive_bbox_overlap_one_to_one_components",
        "text_comparison_policy": "exact_and_nfkc_casefold_collapsed_whitespace",
        "left_evidence": left_identity, "right_evidence": right_identity,
        "agreements": agreements, "disagreements": disagreements,
        "ambiguous_overlaps": ambiguous,
        "unmatched_left_region_ids": sorted(set(left_regions) - matched_left),
        "unmatched_right_region_ids": sorted(set(right_regions) - matched_right),
    }


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("OCR evidence provenance must be finite and JSON serializable.") from exc


def _identity(evidence: Mapping[str, Any]) -> dict[str, Any]:
    # Reuse the established original-page/hash validation; retain full, detached
    # provenance rather than introducing a separate page identity convention.
    validated = _evidence_identity(evidence)
    identity = {field: validated[field] for field in
                ("page_id", "source_image_hash", "transform_id", "engine", "language")}
    for field in ("source_page", "model", "image_transform"):
        identity[field] = json.loads(_json(evidence.get(field)))
    if not identity["model"]:
        raise ValueError("OCR evidence requires nonempty model metadata.")
    original = identity["source_page"]["original_page"]
    dimensions = original["source_dimensions"]
    if any(type(dimensions[field]) is not int for field in ("width", "height")):
        raise ValueError("Original source_dimensions must be positive integers.")
    crop = identity["source_page"].get("crop")
    if crop is not None:
        if not isinstance(crop, Mapping):
            raise ValueError("source_page crop must be an object.")
        box = _bbox([crop.get(field) for field in ("left", "top", "right", "bottom")])
        if box[2] > dimensions["width"] or box[3] > dimensions["height"]:
            raise ValueError("source_page crop lies outside the original image.")
    return identity


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("OCR geometry coordinates must be finite numbers.")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ValueError("OCR geometry coordinates must be finite numbers.") from exc
    if not math.isfinite(number):
        raise ValueError("OCR geometry coordinates must be finite numbers.")
    return number


def _bbox(value: Any) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("OCR geometry requires bbox [left, top, right, bottom].")
    left, top, right, bottom = (_number(item) for item in value)
    area = (right - left) * (bottom - top)
    if left < 0 or top < 0 or right <= left or bottom <= top or not math.isfinite(area):
        raise ValueError("OCR geometry requires a nonnegative bbox with positive finite area.")
    return left, top, right, bottom


def _geometry(value: Any) -> tuple[float, float, float, float]:
    if not isinstance(value, Mapping):
        raise ValueError("OCR region requires geometry.")
    polygon = value.get("polygon")
    polygon_bbox = None
    if polygon is not None:
        if not isinstance(polygon, (list, tuple)) or len(polygon) < 3:
            raise ValueError("OCR polygon requires at least three [x, y] points.")
        points = []
        for point in polygon:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError("OCR polygon requires [x, y] points.")
            points.append((_number(point[0]), _number(point[1])))
        if points[0] == points[-1]:
            points.pop()  # Both open and explicitly closed polygon rings are standard.
        if len(points) < 3 or len(set(points)) != len(points):
            raise ValueError("OCR polygon requires distinct vertices.")
        edges = list(zip(points, points[1:] + points[:1]))
        for index, (a, b) in enumerate(edges):
            for other_index in range(index + 1, len(edges)):
                if other_index == index + 1 or (index == 0 and other_index == len(edges) - 1):
                    continue
                c, d = edges[other_index]
                if _segments_intersect(a, b, c, d):
                    raise ValueError("OCR polygon must not self-intersect.")
        twice_area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))
        if not math.isfinite(twice_area) or twice_area == 0:
            raise ValueError("OCR polygon requires positive finite area.")
        polygon_bbox = _bbox([min(p[0] for p in points), min(p[1] for p in points),
                              max(p[0] for p in points), max(p[1] for p in points)])
    if value.get("bbox") is not None:
        box = _bbox(value["bbox"])
        if polygon_bbox is not None and box != polygon_bbox:
            raise ValueError("OCR bbox and polygon declare inconsistent geometry.")
        return box
    if polygon_bbox is None:
        raise ValueError("OCR region requires bbox or polygon geometry.")
    return polygon_bbox


def _segments_intersect(a: tuple[float, float], b: tuple[float, float],
                        c: tuple[float, float], d: tuple[float, float]) -> bool:
    def cross(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    ab_c, ab_d, cd_a, cd_b = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    for orientation, p, q, r in ((ab_c, a, b, c), (ab_d, a, b, d),
                                (cd_a, c, d, a), (cd_b, c, d, b)):
        if orientation == 0 and min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and min(p[1], q[1]) <= r[1] <= max(p[1], q[1]):
            return True
    return ((ab_c > 0) != (ab_d > 0)) and ((cd_a > 0) != (cd_b > 0))


def _regions(evidence: Mapping[str, Any]) -> dict[str, _Region]:
    values = evidence.get("regions")
    if not isinstance(values, list):
        raise ValueError("OcrPageEvidence requires a regions list.")
    regions: dict[str, _Region] = {}
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("OCR region must be an object.")
        region_id, text = value.get("region_id"), value.get("text")
        if not isinstance(region_id, str) or not region_id.strip() or region_id in regions:
            raise ValueError("OCR region_id must be nonempty and unique within each reading.")
        if not isinstance(text, str):
            raise ValueError("OCR region text must be a string.")
        regions[region_id] = _Region(region_id, text, _geometry(value.get("geometry")))
    return dict(sorted(regions.items()))


def _overlap_area(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return max(0.0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0.0, min(left[3], right[3]) - max(left[1], right[1]))


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())
