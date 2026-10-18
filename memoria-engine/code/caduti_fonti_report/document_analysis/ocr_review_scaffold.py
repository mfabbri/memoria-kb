"""Preview-first preparation of incomplete, image-bound OCR review artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .ocr_lexicon_candidates import build_document_lexicon_review
from .ocr_review_orchestrator import _validate_evidence_comparison
from .ocr_visual_review_ledger import _bbox, _digest, _invalid_constant, _unique_object


def _read_object(path: Path, label: str) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                       parse_constant=_invalid_constant)
    if not isinstance(value, dict):
        raise ValueError(f"{label} deve essere un oggetto JSON.")
    return value, _digest(raw)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _id(prefix: str, value: str) -> str:
    return prefix + "-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _tiles(width: int, height: int, tile_size: int) -> list[dict[str, Any]]:
    result = []
    for top in range(0, height, tile_size):
        for left in range(0, width, tile_size):
            box = [left, top, min(left + tile_size, width), min(top + tile_size, height)]
            result.append({"tile_id": f"tile-{len(result) + 1:04d}", "bbox": box})
    return result


def scaffold_ocr_review(*, image_path: Path, evidence_path: Path, structure_path: Path,
                        markdown_path: Path, lexicon_path: Path, output_dir: Path,
                        comparison_path: Path, tesseract_evidence_path: Path,
                        glossary_path: Path | None = None, apply: bool = False,
                        variant_image_path: Path | None = None,
                        tile_size: int = 1200) -> dict[str, Any]:
    """Build deterministic sidecar templates; never fill visual judgments or layout."""
    image_path, evidence_path, structure_path = map(Path, (image_path, evidence_path, structure_path))
    markdown_path, lexicon_path, output_dir = map(Path, (markdown_path, lexicon_path, output_dir))
    if type(tile_size) is not int or not 128 <= tile_size <= 4096:
        raise ValueError("--tile-size deve essere un intero tra 128 e 4096.")
    evidence, evidence_digest = _read_object(evidence_path, "evidence")
    structure, structure_digest = _read_object(structure_path, "structure")
    if evidence.get("@type") != "OcrPageEvidence" or structure.get("@type") != "DocumentStructure":
        raise ValueError("Servono OcrPageEvidence e DocumentStructure.")
    if structure.get("schema_version") != "1.0":
        raise ValueError("DocumentStructure schema_version 1.0 richiesto.")
    markdown = markdown_path.read_bytes()
    markdown_digest = _digest(markdown)
    image_digest = _digest(image_path.read_bytes())
    if evidence.get("source_image_hash") != image_digest.removeprefix("sha256:"):
        raise ValueError("Hash TIFF diverso da OcrPageEvidence.")
    comparison_paths = {"image": image_path, "evidence": evidence_path,
                        "comparison": Path(comparison_path),
                        "tesseract_evidence": Path(tesseract_evidence_path)}
    _, comparison_digest = _read_object(comparison_paths["comparison"], "comparison")
    _, tesseract_digest = _read_object(comparison_paths["tesseract_evidence"], "tesseract_evidence")
    comparison_snapshot = {name: {"path": str(comparison_paths[name]), "digest": digest}
                           for name, digest in (("image", image_digest), ("evidence", evidence_digest),
                                                ("comparison", comparison_digest),
                                                ("tesseract_evidence", tesseract_digest))}
    _validate_evidence_comparison(comparison_paths, comparison_snapshot)
    if not isinstance(evidence.get("source_page"), dict) or not isinstance(structure.get("blocks"), list):
        raise ValueError("source_page e blocks sono richiesti.")
    if not isinstance(evidence["source_page"].get("original_page"), dict):
        raise ValueError("source_page.original_page deve essere un oggetto.")
    source_identity = structure.get("source_evidence")
    if not isinstance(source_identity, dict) or any(source_identity.get(key) != evidence.get(key) for key in (
            "page_id", "source_image_hash", "source_page", "transform_id", "image_transform", "engine", "model", "language")):
        raise ValueError("Identita' source_evidence non coerente con OcrPageEvidence.")
    if structure.get("page_id") != evidence.get("page_id"):
        raise ValueError("page_id della struttura diverso da OcrPageEvidence.")
    regions = evidence.get("regions")
    if not isinstance(regions, list) or not regions:
        raise ValueError("Almeno una regione OCR e' richiesta.")
    region_by_id = {r.get("region_id"): r for r in regions if isinstance(r, dict) and isinstance(r.get("region_id"), str)}
    if len(region_by_id) != len(regions) or not all(region_by_id):
        raise ValueError("region_id mancanti o duplicati.")
    blocks = structure["blocks"]
    if not blocks:
        raise ValueError("Almeno un block OCR e' richiesto.")
    owner_count = {key: 0 for key in region_by_id}
    block_boxes = {}
    block_ids = set()
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("block_id"), str) or not block.get("block_id"):
            raise ValueError("block_id non valido.")
        if block["block_id"] in block_ids:
            raise ValueError("block_id duplicato.")
        block_ids.add(block["block_id"])
        if not isinstance(block.get("text"), str):
            raise ValueError(f"Testo mancante nel block {block['block_id']}.")
        links = block.get("source_region_ids")
        if not isinstance(links, list) or not links or any(key not in region_by_id for key in links):
            raise ValueError(f"source_region_ids non validi nel block {block.get('block_id')}.")
        for key in links:
            owner_count[key] += 1
        linked = []
        for key in links:
            geometry = region_by_id[key].get("geometry")
            box = geometry.get("bbox") if isinstance(geometry, dict) else None
            if not isinstance(box, list) or len(box) != 4 or any(type(value) is not int for value in box):
                raise ValueError(f"BBox non valida per regione {key}.")
            linked.append(box)
        block_boxes[block["block_id"]] = [min(b[0] for b in linked), min(b[1] for b in linked),
                                           max(b[2] for b in linked), max(b[3] for b in linked)]
    if any(count != 1 for count in owner_count.values()):
        raise ValueError("Ogni regione deve appartenere esattamente a un block.")
    try:
        from PIL import Image
        with Image.open(image_path) as image:
            if image.format != "TIFF":
                raise ValueError("L'immagine deve essere TIFF.")
            frame = evidence["source_page"].get("frame_index")
            if type(frame) is not int or frame < 0:
                raise ValueError("frame_index esplicito richiesto.")
            image.seek(frame)
            width, height = image.size
            source_dims = {"width": width, "height": height}
            anchor = evidence["source_page"].get("original_page", {})
            if (anchor.get("source_dimensions") != source_dims or anchor.get("page_id") != evidence.get("page_id")
                    or anchor.get("source_image_hash") != evidence.get("source_image_hash")):
                raise ValueError("Original-page identity/dimensions non coerenti.")
            transform = evidence.get("image_transform")
            plain = evidence.get("transform_id") == "original" and transform in (None, {})
            copied = (isinstance(transform, dict) and set(transform) == {"id", "parameters"}
                      and transform["id"] == evidence.get("transform_id")
                      and isinstance(transform["parameters"], dict)
                      and set(transform["parameters"]) <= {"operation", "source_mode"}
                      and transform["parameters"].get("operation") == "byte_copy"
                      and evidence["source_page"].get("variant_id") == "raw"
                      and evidence["source_page"].get("target") == "full_page"
                      and evidence["source_page"].get("tile_id") is None
                      and evidence["source_page"].get("crop") is None)
            if copied and (variant_image_path is None
                           or _digest(Path(variant_image_path).read_bytes()) != image_digest):
                raise ValueError("La variante raw byte_copy deve essere fornita e byte-identica al TIFF.")
            if not (plain or copied):
                raise ValueError("Scaffold ammesso solo su coordinate originali TIFF.")
            boxes = {"tile:" + t["tile_id"]: t["bbox"] for t in _tiles(width, height, tile_size)}
            for region_id, region in region_by_id.items():
                geometry = region.get("geometry")
                box = geometry.get("bbox") if isinstance(geometry, dict) else None
                if not _bbox(box, width, height):
                    raise ValueError(f"BBox non valida per regione {region_id}.")
                boxes["region:" + region_id] = box
            for block in blocks:
                box = block_boxes[block["block_id"]]
                if not _bbox(box, width, height):
                    raise ValueError(f"BBox non valida per block {block['block_id']}.")
                boxes["block:" + block["block_id"]] = box
    except ImportError as exc:
        raise ValueError("Pillow richiesto per generare i crop.") from exc
    tiles = _tiles(width, height, tile_size)
    parent = output_dir.parent
    if not parent.is_dir():
        raise ValueError("La directory padre dell'output deve esistere.")
    if output_dir.exists():
        raise ValueError(f"La directory di output deve essere nuova: {output_dir}")
    if not output_dir.name:
        raise ValueError("Directory di output non valida.")

    lexicon_preview_path = output_dir / "lexicon-review.json"
    lexicon_report = build_document_lexicon_review(
        structure_path=structure_path, lexicon_path=lexicon_path,
        glossary_path=Path(glossary_path) if glossary_path else None,
        output_path=lexicon_preview_path, apply=False,
    )
    visual_ledger = {
        "@type": "OcrVisualReviewLedger", "schema_version": "1.0", "template_status": "incomplete",
        "page_id": evidence["page_id"], "source_image_hash": evidence["source_image_hash"],
        "source_page": evidence["source_page"], "frame_index": evidence["source_page"]["frame_index"],
        "source_dimensions": source_dims, "transform_id": evidence["transform_id"],
        "source_evidence_digest": evidence_digest, "source_structure_digest": structure_digest,
        "review_tiles": tiles, "observations": [],
    }
    observations = []
    for kind, units in (("tile", tiles), ("block", blocks), ("region", regions)):
        for unit in units:
            unit_id = unit["tile_id"] if kind == "tile" else unit["block_id"] if kind == "block" else unit["region_id"]
            box = unit["bbox"] if kind == "tile" else block_boxes[unit_id] if kind == "block" else unit["geometry"]["bbox"]
            crop_name = f"{kind}-{_id('u', unit_id)}.png"
            observation = {"observation_id": f"{kind}:{unit_id}", "unit_type": kind, "unit_id": unit_id,
                           "bbox": box, "outcome": "", "text": "", "observer": {},
                           "crop_artifact": {"path": "crops/" + crop_name, "digest": ""}}
            if kind in ("block", "region"):
                observation["candidate_text"] = unit.get("text", "")
            if kind == "block":
                observation["source_region_ids"] = unit["source_region_ids"]
            observations.append((observation, box, crop_name))
    visual_ledger["observations"] = [x[0] for x in observations]
    layout = {"@type": "OcrPageLayout", "schema_version": "1.0", "template_status": "incomplete",
              "page_id": evidence["page_id"], "source_image_hash": evidence["source_image_hash"],
              "source_page": evidence["source_page"], "source_evidence_digest": evidence_digest,
              "source_visual_audit_digest": "", "columns": [], "rows": [], "reading_order": [], "exclusions": []}
    not_found = []
    for block in lexicon_report["blocks"]:
        for token in block["tokens"]:
            if token["status"] == "not_found":
                not_found.append({"page_id": block["page_id"], "block_id": block["block_id"],
                                  "start": token["start"], "end": token["end"], "raw_token": token["raw_token"],
                                  "disposition": "", "reason": "", "visual_observation_id": ""})
    dispositions = {"@type": "OcrLexicalDispositionLedger", "schema_version": "1.0",
                    "template_status": "incomplete", "source_structure_digest": structure_digest,
                    "source_lexicon_review_digest": "", "source_visual_audit_digest": "",
                    "dispositions": not_found}
    manifest = {"@type": "OcrReviewScaffold", "schema_version": "1.0", "status": "template_incomplete",
                "inputs": {"image_digest": image_digest, "evidence_digest": evidence_digest,
                           "tesseract_evidence_path": str(comparison_paths["tesseract_evidence"]),
                           "tesseract_evidence_digest": tesseract_digest,
                           "comparison_path": str(comparison_paths["comparison"]),
                           "comparison_digest": comparison_digest,
                           "structure_digest": structure_digest, "markdown_digest": markdown_digest,
                           "lexicon_path": str(lexicon_path)},
                "outputs": ["lexicon-review.json", "visual-ledger.json", "layout.json",
                            "dispositions.json", "crops/"],
                "required_manual_fields": ["visual observation text/outcome and observer provenance",
                                           "semantic columns, rows and cell-to-region order",
                                           "each not-found token disposition, reason and linked visual observation"],
                "authorizations": {"human_review_request_allowed": False, "machine_pass": False,
                                   "auto_validation_enabled": False, "gold_promotion_allowed": False}}
    report = {"@type": "OcrReviewScaffoldReport", "schema_version": "1.0", "status": "template_incomplete",
              "operation_status": "preview", "output_dir": str(output_dir), "tile_count": len(tiles),
              "observation_count": len(observations), "crop_count": len(observations),
              "lexical_disposition_count": len(not_found), "outputs": manifest["outputs"],
              "authorizations": manifest["authorizations"]}
    if not apply:
        return report

    with tempfile.TemporaryDirectory(prefix=".ocr-review-scaffold-", dir=parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        lexicon_report = build_document_lexicon_review(
            structure_path=structure_path, lexicon_path=lexicon_path,
            glossary_path=Path(glossary_path) if glossary_path else None,
            output_path=stage / "lexicon-review.json", apply=True,
        )
        for observation, box, crop_name in observations:
            crop_path = stage / "crops" / crop_name
            crop_path.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(image_path) as image:
                image.seek(frame)
                image.crop(tuple(box)).save(crop_path, format="PNG")
            observation["crop_artifact"]["digest"] = _digest(crop_path.read_bytes())
        dispositions["source_lexicon_review_digest"] = _digest((stage / "lexicon-review.json").read_bytes())
        _write_json(stage / "visual-ledger.json", visual_ledger)
        _write_json(stage / "layout.json", layout)
        _write_json(stage / "dispositions.json", dispositions)
        manifest["inputs"]["lexicon_review_digest"] = dispositions["source_lexicon_review_digest"]
        _write_json(stage / "scaffold-manifest.json", manifest)
        os.replace(stage, output_dir)
    return report | {"operation_status": "written"}
