"""Read-only audit of image-bound visual observations, never semantic attestation."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


def audit_ocr_visual_review_ledger(*, ledger_path: Path, image_path: Path,
                                  evidence_path: Path, structure_path: Path) -> dict[str, Any]:
    """Check declared units and artifacts; no file writes or gold promotion."""
    issues: list[dict[str, str]] = []

    def issue(code: str, unit: str = "") -> None:
        issues.append({"code": code, "unit": unit})

    paths = {"ledger": Path(ledger_path), "image": Path(image_path),
             "evidence": Path(evidence_path), "structure": Path(structure_path)}
    inputs: dict[str, Any] = {}
    loaded: dict[str, Any] = {}
    for name, path in paths.items():
        try:
            raw = path.read_bytes()
            inputs[name] = {"path": str(path), "digest": _digest(raw)}
            if name != "image":
                loaded[name] = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                                          parse_constant=_invalid_constant)
                if not isinstance(loaded[name], dict):
                    issue("invalid_input", name)
        except (OSError, UnicodeError, ValueError):
            issue("unreadable_input", name)
    if not issues:
        ledger, evidence, structure = (loaded[name] for name in ("ledger", "evidence", "structure"))
        for name, payload, kind in (("ledger", ledger, "OcrVisualReviewLedger"),
                                    ("evidence", evidence, "OcrPageEvidence"),
                                    ("structure", structure, "DocumentStructure")):
            if payload.get("@type") != kind or (name != "evidence" and payload.get("schema_version") != "1.0"):
                issue("unsupported_contract", name)
        if ledger.get("template_status") == "incomplete":
            issue("incomplete_template", "ledger")
        for name in ("evidence", "structure"):
            if ledger.get("source_" + name + "_digest") != inputs[name]["digest"]:
                issue("stale_input", name)
        source = evidence.get("source_page")
        source = source if isinstance(source, dict) else {}
        anchor = source.get("original_page")
        anchor = anchor if isinstance(anchor, dict) else {}
        frame = ledger.get("frame_index")
        width = height = 0
        try:
            from PIL import Image
            if type(frame) is not int or frame < 0:
                raise ValueError("Explicit frame required")
            with Image.open(paths["image"]) as image:
                if image.format != "TIFF":
                    raise ValueError("TIFF required")
                image.seek(frame)
                width, height = image.size
        except (ImportError, OSError, ValueError, EOFError):
            issue("unverifiable_image_frame")
        dimensions = {"width": width, "height": height}
        image_hash = inputs["image"]["digest"].removeprefix("sha256:")
        for payload_name, payload in (("ledger", ledger), ("evidence", evidence), ("original_page", anchor)):
            if not _text(payload.get("page_id")) or payload.get("page_id") != structure.get("page_id"):
                issue("page_identity_mismatch", payload_name)
            if payload.get("source_image_hash") != image_hash:
                issue("image_hash_mismatch", payload_name)
        if (ledger.get("source_page") != source or type(source.get("frame_index")) is not int
                or source.get("frame_index") != frame or ledger.get("source_dimensions") != dimensions
                or anchor.get("source_dimensions") != dimensions or not _text(anchor.get("source_file"))):
            issue("frame_identity_mismatch")
        for payload in (ledger, anchor):
            declared_dimensions = payload.get("source_dimensions")
            if (not isinstance(declared_dimensions, dict)
                    or any(type(declared_dimensions.get(key)) is not int for key in ("width", "height"))):
                issue("invalid_source_dimensions")
        identity = structure.get("source_evidence")
        if not isinstance(identity, dict) or any(identity.get(key) != evidence.get(key) for key in (
                "page_id", "source_image_hash", "source_page", "transform_id", "image_transform", "engine", "model", "language")):
            issue("structure_identity_mismatch")
        transform = evidence.get("image_transform")
        plain = evidence.get("transform_id") == "original" and transform in (None, {})
        copied = (isinstance(transform, dict) and set(transform) == {"id", "parameters"}
                  and transform["id"] == evidence.get("transform_id")
                  and isinstance(transform["parameters"], dict)
                  and set(transform["parameters"]) <= {"operation", "source_mode"}
                  and transform["parameters"].get("operation") == "byte_copy")
        if (not (plain or copied) or source.get("crop") is not None or source.get("tile_id") is not None
                or source.get("target", "full_page") != "full_page" or source.get("variant_id", "raw") != "raw"):
            issue("unsupported_coordinate_frame")

        def indexed(payload: Any, id_field: str, kind: str) -> dict[str, dict]:
            result: dict[str, dict] = {}
            if not isinstance(payload, list) or not payload:
                issue("missing_units", kind)
                return result
            for item in payload:
                key = item.get(id_field) if isinstance(item, dict) else None
                if not _text(key):
                    issue("invalid_unit", kind)
                elif key in result:
                    issue("duplicate_unit", kind + ":" + key)
                else:
                    result[key] = item
            return result

        regions = indexed(evidence.get("regions"), "region_id", "region")
        blocks = indexed(structure.get("blocks"), "block_id", "block")
        tiles = indexed(ledger.get("review_tiles"), "tile_id", "tile")
        owners: Counter = Counter()
        for block_id, block in blocks.items():
            links = block.get("source_region_ids")
            if not isinstance(links, list) or not links or any(not _text(r) or r not in regions for r in links):
                issue("invalid_region_links", block_id)
            else:
                owners.update(links)
        if owners != Counter({key: 1 for key in regions}):
            issue("region_ownership_mismatch")
        boxes: list[list[int]] = []
        for tile_id, tile in tiles.items():
            box = tile.get("bbox")
            if _bbox(box, width, height):
                boxes.append(box)
            else:
                issue("invalid_bbox", "tile:" + tile_id)
        if any(_overlap(left, right) for i, left in enumerate(boxes) for right in boxes[i + 1:]):
            issue("tile_overlap")
        if sum((b[2] - b[0]) * (b[3] - b[1]) for b in boxes) != width * height or not boxes:
            issue("tile_coverage_gap_or_excess")
        for region_id, region in regions.items():
            geometry = region.get("geometry")
            if not isinstance(geometry, dict) or not _bbox(geometry.get("bbox"), width, height):
                issue("invalid_region_bbox", region_id)

        observations = indexed(ledger.get("observations"), "observation_id", "observation")
        counts: Counter = Counter()
        for observation_id, observation in observations.items():
            kind, unit_id = observation.get("unit_type"), observation.get("unit_id")
            declared = {"tile": tiles, "block": blocks, "region": regions}.get(kind) if isinstance(kind, str) else None
            if declared is None or not _text(unit_id) or unit_id not in declared:
                issue("unexpected_observation", observation_id)
                continue
            counts[kind, unit_id] += 1
            unit = declared[unit_id]
            box = observation.get("bbox")
            if not _bbox(box, width, height):
                issue("invalid_bbox", observation_id)
            geometry = unit.get("geometry")
            expected_box = (geometry.get("bbox") if isinstance(geometry, dict) else None) if kind == "region" else unit.get("bbox")
            if kind == "block":
                links = unit.get("source_region_ids")
                if observation.get("source_region_ids") != links or observation.get("candidate_text") != unit.get("text"):
                    issue("candidate_observation_mismatch", observation_id)
                region_boxes = [regions[r]["geometry"]["bbox"] for r in links
                                if r in regions and isinstance(regions[r].get("geometry"), dict)
                                and _bbox(regions[r]["geometry"].get("bbox"), width, height)] if isinstance(links, list) and all(_text(r) for r in links) else []
                expected_box = ([min(b[0] for b in region_boxes), min(b[1] for b in region_boxes),
                                 max(b[2] for b in region_boxes), max(b[3] for b in region_boxes)] if region_boxes else None)
            if box != expected_box:
                issue("unit_bbox_mismatch", observation_id)
            if kind == "region" and observation.get("candidate_text") != unit.get("text"):
                issue("candidate_observation_mismatch", observation_id)
            if observation.get("outcome") not in ("readable", "illegible", "no_text") or not _text(observation.get("text")):
                issue("empty_or_invalid_reading", observation_id)
            observer = observation.get("observer")
            if not isinstance(observer, dict) or any(not _text(observer.get(k)) for k in (
                    "observer_id", "model", "configuration", "observed_at")):
                issue("missing_observer_provenance", observation_id)
            else:
                try:
                    timestamp = datetime.fromisoformat(observer["observed_at"].replace("Z", "+00:00"))
                    if timestamp.utcoffset() is None:
                        raise ValueError("Timezone required")
                except ValueError:
                    issue("invalid_observer_timestamp", observation_id)
            crop = observation.get("crop_artifact")
            try:
                if not isinstance(crop, dict) or not _text(crop.get("path")):
                    raise ValueError("Crop required")
                crop_path = paths["ledger"].parent / crop["path"]
                if _digest(crop_path.read_bytes()) != crop.get("digest"):
                    issue("crop_hash_mismatch", observation_id)
                elif _bbox(box, width, height) and not _crop_matches_source(paths["image"], frame, box, crop_path):
                    issue("crop_pixel_mismatch", observation_id)
            except (OSError, ValueError):
                issue("missing_crop_artifact", observation_id)
        expected_counts = Counter({(kind, key): 1 for kind, units in (
            ("tile", tiles), ("block", blocks), ("region", regions)) for key in units})
        if counts != expected_counts:
            issue("observation_coverage_mismatch")
    return {"@type": "OcrVisualReviewLedgerAudit", "schema_version": "1.0", "inputs": inputs,
            "checks": {"issues": issues, "issue_count": len(issues)},
            "processability_status": "blocked" if issues else "diagnostic_only",
            "visual_coverage_status": "blocked" if issues else "complete_for_declared_units",
            "semantic_accuracy_status": "not_attested", "human_review_request_allowed": False,
            "machine_pass": False, "human_verified": False, "gold_promotion_allowed": False,
            "claim_extraction_allowed": False, "preview_only": True, "operation_status": "preview"}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def _invalid_constant(value: str) -> Any:
    raise ValueError("Non-finite JSON value: " + value)


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _bbox(value: Any, width: int, height: int) -> bool:
    return (isinstance(value, list) and len(value) == 4 and all(type(v) is int for v in value)
            and 0 <= value[0] < value[2] <= width and 0 <= value[1] < value[3] <= height)


def _overlap(a: list[int], b: list[int]) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _crop_matches_source(image_path: Path, frame: int, bbox: list[int], crop_path: Path) -> bool:
    """Require crop pixels to equal the declared raw-frame rectangle exactly."""
    try:
        from PIL import Image
        with Image.open(image_path) as source:
            source.seek(frame)
            expected = source.crop(tuple(bbox)).convert("RGBA")
        with Image.open(crop_path) as artifact:
            actual = artifact.convert("RGBA")
        return actual.size == expected.size and actual.tobytes() == expected.tobytes()
    except (ImportError, OSError, TypeError, ValueError, EOFError):
        return False
