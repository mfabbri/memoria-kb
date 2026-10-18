"""Read-only structural audit of a typed OCR layout, never semantic approval."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from .ocr_visual_review_ledger import _bbox, _digest, _invalid_constant, _text, _unique_object


def audit_ocr_page_layout(*, layout_path: Path, evidence_path: Path,
                          visual_audit_path: Path) -> dict[str, Any]:
    """Validate exact artifact bindings, declared order and raw-region ownership."""
    issues: list[dict[str, str]] = []
    inputs: dict[str, Any] = {}
    loaded: dict[str, Any] = {}
    counts = {"rows": 0, "columns": 0, "cells": 0, "evidence_regions": 0,
              "cell_region_links": 0, "excluded_regions": 0}

    def issue(code: str, unit: str = "") -> None:
        issues.append({"code": code, "unit": unit})

    for name, path in (("layout", layout_path), ("evidence", evidence_path),
                       ("visual_audit", visual_audit_path)):
        try:
            raw = Path(path).read_bytes()
            inputs[name] = {"path": str(path), "digest": _digest(raw)}
            payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                                 parse_constant=_invalid_constant)
            if not isinstance(payload, dict):
                raise ValueError("Object required")
            loaded[name] = payload
        except (OSError, UnicodeError, ValueError):
            issue("invalid_input", name)
    if not issues:
        layout, evidence, visual = (loaded[k] for k in ("layout", "evidence", "visual_audit"))
        for name, payload, kind in (("layout", layout, "OcrPageLayout"),
                                   ("evidence", evidence, "OcrPageEvidence"),
                                   ("visual_audit", visual, "OcrVisualReviewLedgerAudit")):
            if payload.get("@type") != kind or (name != "evidence" and payload.get("schema_version") != "1.0"):
                issue("unsupported_contract", name)
        if layout.get("template_status") == "incomplete":
            issue("incomplete_template", "layout")
        for name in ("evidence", "visual_audit"):
            if layout.get("source_" + name + "_digest") != inputs[name]["digest"]:
                issue("stale_input", name)
        visual_inputs = visual.get("inputs")
        visual_inputs = visual_inputs if isinstance(visual_inputs, dict) else {}
        for name in ("image", "evidence", "ledger", "structure"):
            entry = visual_inputs.get(name)
            if (not isinstance(entry, dict) or not _text(entry.get("path"))
                    or not _sha256(entry.get("digest"))):
                issue("invalid_visual_audit_input", name)
        visual_checks = visual.get("checks")
        if (not isinstance(visual_checks, dict) or visual_checks.get("issues") != []
                or type(visual_checks.get("issue_count")) is not int or visual_checks.get("issue_count") != 0
                or visual.get("processability_status") != "diagnostic_only"
                or visual.get("visual_coverage_status") != "complete_for_declared_units"
                or visual.get("semantic_accuracy_status") != "not_attested"
                or visual.get("preview_only") is not True
                or any(visual.get(k) is not False for k in ("human_review_request_allowed", "machine_pass",
                       "human_verified", "gold_promotion_allowed", "claim_extraction_allowed"))):
            issue("unsuccessful_visual_audit")
        for name, expected in (("evidence", inputs["evidence"]["digest"]),
                               ("image", "sha256:" + str(evidence.get("source_image_hash")))):
            entry = visual_inputs.get(name)
            if not isinstance(entry, dict) or entry.get("digest") != expected:
                issue("visual_audit_identity_mismatch", name)
        source = evidence.get("source_page")
        source = source if isinstance(source, dict) else {}
        anchor = source.get("original_page")
        anchor = anchor if isinstance(anchor, dict) else {}
        dimensions = anchor.get("source_dimensions")
        dimensions = dimensions if isinstance(dimensions, dict) else {}
        width, height = dimensions.get("width"), dimensions.get("height")
        if (type(width) is not int or type(height) is not int or width <= 0 or height <= 0):
            issue("invalid_source_dimensions")
            width = height = 0
        if (not _text(evidence.get("page_id")) or not _sha256("sha256:" + str(evidence.get("source_image_hash")))
                or any(layout.get(k) != evidence.get(k) for k in ("page_id", "source_image_hash", "source_page"))
                or anchor.get("page_id") != evidence.get("page_id")
                or anchor.get("source_image_hash") != evidence.get("source_image_hash")
                or type(source.get("frame_index")) is not int or source.get("frame_index", -1) < 0):
            issue("page_identity_mismatch")

        def indexed(items: Any, key: str, kind: str, *, empty: bool = False) -> dict[str, dict]:
            result: dict[str, dict] = {}
            if not isinstance(items, list) or (not items and not empty):
                issue("missing_units", kind)
                return result
            for item in items:
                identity = item.get(key) if isinstance(item, dict) else None
                if not _text(identity):
                    issue("invalid_unit", kind)
                elif identity in result:
                    issue("duplicate_unit", kind + ":" + identity)
                else:
                    result[identity] = item
            return result

        regions = indexed(evidence.get("regions"), "region_id", "region")
        rows = indexed(layout.get("rows"), "row_id", "row")
        columns = indexed(layout.get("columns"), "column_id", "column")
        counts.update(rows=len(rows), columns=len(columns), evidence_regions=len(regions))
        for units, field, kind in ((rows, "row_index", "row"), (columns, "column_index", "column")):
            indexes = [v.get(field) for v in units.values()]
            if any(type(i) is not int for i in indexes) or indexes != list(range(len(units))):
                issue("invalid_indexes", kind)
        for region_id, region in regions.items():
            geometry = region.get("geometry")
            if not isinstance(geometry, dict) or not _bbox(geometry.get("bbox"), width, height):
                issue("invalid_region_bbox", region_id)
            if not isinstance(region.get("text"), str):
                issue("invalid_region_text", region_id)
        cells: dict[str, dict] = {}
        owners: Counter = Counter()
        for row_id, row in rows.items():
            row_box = row.get("bbox")
            if not _bbox(row_box, width, height):
                issue("invalid_bbox", row_id)
            row_cells = indexed(row.get("cells"), "cell_id", "cell")
            indexes = [c.get("column_index") for c in row_cells.values()]
            if (any(type(i) is not int for i in indexes) or indexes != list(range(len(row_cells)))
                    or len(row_cells) > len(columns)):
                issue("invalid_indexes", row_id)
            for cell_id, cell in row_cells.items():
                counts["cells"] += 1
                if cell_id in cells:
                    issue("duplicate_unit", "cell:" + cell_id)
                cells[cell_id] = cell
                box = cell.get("bbox")
                if not _bbox(box, width, height):
                    issue("invalid_bbox", cell_id)
                elif _bbox(row_box, width, height) and not _contains(row_box, box):
                    issue("row_bbox_mismatch", cell_id)
                links = cell.get("source_region_ids")
                if (not isinstance(links, list) or not links
                        or any(not _text(r) or r not in regions for r in links)):
                    issue("invalid_region_links", cell_id)
                    continue
                owners.update(links)
                counts["cell_region_links"] += len(links)
                joiner = cell.get("joiner")
                if not isinstance(joiner, str) or joiner not in ("", " ", "\n"):
                    issue("invalid_joiner", cell_id)
                elif (not _text(cell.get("text"))
                      or any(not isinstance(regions[r].get("text"), str) for r in links)
                      or cell["text"] != joiner.join(regions[r]["text"] for r in links)):
                    issue("cell_text_mismatch", cell_id)
                for region_id in links:
                    geometry = regions[region_id].get("geometry")
                    region_box = geometry.get("bbox") if isinstance(geometry, dict) else None
                    if _bbox(region_box, width, height):
                        if _bbox(box, width, height) and not _contains(box, region_box):
                            issue("cell_bbox_mismatch", cell_id)
                        if _bbox(row_box, width, height) and not _contains(row_box, region_box):
                            issue("row_bbox_mismatch", row_id)
        order = layout.get("reading_order")
        if (not isinstance(order, list) or any(not _text(c) for c in order)
                or Counter(order) != Counter({key: 1 for key in cells})):
            issue("invalid_reading_order")
        exclusions = layout.get("exclusions")
        if not isinstance(exclusions, list):
            issue("invalid_exclusions")
        else:
            for exclusion in exclusions:
                region_id = exclusion.get("region_id") if isinstance(exclusion, dict) else None
                if not _text(region_id) or region_id not in regions:
                    issue("invalid_exclusion_region")
                else:
                    owners[region_id] += 1
                    counts["excluded_regions"] += 1
                if not isinstance(exclusion, dict) or not _text(exclusion.get("reason")):
                    issue("missing_exclusion_reason")
        if owners != Counter({key: 1 for key in regions}):
            issue("region_ownership_mismatch")
    return {"@type": "OcrPageLayoutAudit", "schema_version": "1.0", "inputs": inputs,
            "counts": counts, "checks": {"issues": issues, "issue_count": len(issues)},
            "processability_status": "blocked" if issues else "diagnostic_only",
            "structural_consistency_status": "blocked" if issues else "complete_for_declared_units",
            "semantic_accuracy_status": "not_attested", "human_review_request_allowed": False,
            "machine_pass": False, "human_verified": False, "gold_promotion_allowed": False,
            "claim_extraction_allowed": False, "preview_only": True, "operation_status": "preview"}


def _contains(outer: list[int], inner: list[int]) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None
