"""Prepare word-level OCR/reference differences for visual adjudication.

This module deliberately proposes no material-error labels. It only aligns an
exact OCR evidence stream to a verified page reference and anchors candidate
tokens to their source regions for review on the original image.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import unicodedata
from typing import Any, Mapping

from .document_structure import reconstruct_document_structure
from .ocr_reference_metrics import _tokens as metric_tokens
from .ocr_reference_metrics import evaluate_page_reference, load_page_reference

_MAX_ALIGNMENT_CELLS = 4_000_000
# Character metrics use a two-row DP, so this bounds CPU comparisons rather
# than matrix memory. It accommodates ordinary 300-word pages (~4.4M cells).
_MAX_CHARACTER_COMPARISONS = 10_000_000


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _read_json(path: Path, label: str) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} non leggibile o JSON non valido: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} deve essere un oggetto JSON.")
    _canonical(payload)
    return payload, hashlib.sha256(raw).hexdigest()


def _normalise(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _tokenize(value: str) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    start: int | None = None
    for index, character in enumerate(value):
        category = unicodedata.category(character)[0]
        is_word = category in {"L", "N"} or (category == "M" and start is not None)
        if is_word:
            if start is None:
                start = index
            continue
        if start is not None:
            raw = value[start:index]
            tokens.append({"text": raw, "normalized": _normalise(raw), "start": start, "end": index})
            start = None
    if start is not None:
        raw = value[start:]
        tokens.append({"text": raw, "normalized": _normalise(raw), "start": start, "end": len(value)})
    return tokens


def _evidence_tokens(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    regions = evidence.get("regions")
    if not isinstance(regions, list):
        raise ValueError("OcrPageEvidence senza lista regions valida.")
    result: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for region_index, region in enumerate(regions):
        if not isinstance(region, Mapping):
            raise ValueError(f"Regione OCR {region_index} non valida.")
        region_id, text = region.get("region_id"), region.get("text")
        if not isinstance(region_id, str) or not region_id.strip() or region_id in seen_ids:
            raise ValueError(f"Regione OCR {region_index} richiede region_id univoco.")
        region_id = region_id.strip()
        if region_id in seen_ids:
            raise ValueError(f"Regione OCR {region_index} richiede region_id univoco.")
        if not isinstance(text, str):
            raise ValueError(f"Regione OCR {region_id} senza testo valido.")
        seen_ids.add(region_id)
        geometry = region.get("geometry")
        bbox = geometry.get("bbox") if isinstance(geometry, Mapping) else None
        if bbox is not None and (not isinstance(bbox, list) or len(bbox) != 4
                                 or any(isinstance(value, bool) or not isinstance(value, (int, float))
                                        or not math.isfinite(value) for value in bbox)):
            raise ValueError(f"Bounding box non valida per la regione OCR {region_id}.")
        for token in _tokenize(text):
            result.append(token | {"region_id": region_id, "bbox": bbox})
    return result


def _alignment(reference_tokens: list[dict[str, Any]], output_tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return deterministic edit operations using the reference metric tie order."""
    rows, columns = len(reference_tokens) + 1, len(output_tokens) + 1
    if rows * columns > _MAX_ALIGNMENT_CELLS:
        raise ValueError("Allineamento troppo grande per una singola pagina (limite 4M celle).")
    matrix = [[0] * columns for _ in range(rows)]
    for row in range(1, rows):
        matrix[row][0] = row
    for column in range(1, columns):
        matrix[0][column] = column
    normalized_output = [token["normalized"] for token in output_tokens]
    for row in range(1, rows):
        expected = reference_tokens[row - 1]["normalized"]
        for column in range(1, columns):
            matrix[row][column] = min(
                matrix[row - 1][column - 1] + (expected != normalized_output[column - 1]),
                matrix[row - 1][column] + 1,
                matrix[row][column - 1] + 1,
            )

    operations: list[dict[str, Any]] = []
    row, column = len(reference_tokens), len(output_tokens)
    while row or column:
        if (row and column and reference_tokens[row - 1]["normalized"] == normalized_output[column - 1]
                and matrix[row][column] == matrix[row - 1][column - 1]):
            operations.append({"operation": "match", "reference_token_index": row - 1,
                               "output_token_index": column - 1})
            row, column = row - 1, column - 1
        elif row and column and matrix[row][column] == matrix[row - 1][column - 1] + 1:
            operations.append({"operation": "substitution", "reference_token_index": row - 1,
                               "output_token_index": column - 1})
            row, column = row - 1, column - 1
        elif row and matrix[row][column] == matrix[row - 1][column] + 1:
            operations.append({"operation": "omission", "reference_token_index": row - 1,
                               "output_token_index": None})
            row -= 1
        elif column and matrix[row][column] == matrix[row][column - 1] + 1:
            operations.append({"operation": "addition", "reference_token_index": None,
                               "output_token_index": column - 1})
            column -= 1
        else:
            raise RuntimeError("No optimal token alignment transition")
    return list(reversed(operations))


def build_ocr_material_error_draft(
    *, reference_path: Path, evidence_path: Path, structure_path: Path,
    image_path: Path, output_path: Path, apply: bool = False,
) -> dict[str, Any]:
    """Build a provenance-bound mismatch draft; never classify materiality."""
    paths = {name: Path(path) for name, path in {
        "reference": reference_path, "evidence": evidence_path,
        "structure": structure_path, "image": image_path,
    }.items()}
    target = Path(output_path)
    if target.resolve() in {path.resolve() for path in paths.values()}:
        raise ValueError("Output non puo' sostituire un input.")
    repo_root = Path(__file__).resolve().parents[4]
    try:
        target.resolve().relative_to(repo_root)
    except ValueError:
        pass
    else:
        raise ValueError("La bozza OCR reale deve restare fuori dal repository.")

    reference, reference_hash = _read_json(paths["reference"], "Reference")
    evidence, evidence_hash = _read_json(paths["evidence"], "Evidence")
    structure_payload, structure_hash = _read_json(paths["structure"], "Struttura")
    image_hash = hashlib.sha256(paths["image"].read_bytes()).hexdigest()

    if reference.get("origin") != "human_verified" or reference.get("review_status") != "verified":
        raise ValueError("La bozza richiede reference human_verified/verified.")
    loaded_reference = load_page_reference(reference)
    if image_hash != loaded_reference.source_image_hash or image_hash != evidence.get("source_image_hash"):
        raise ValueError("Hash TIFF non coincide con reference ed evidence.")
    if evidence.get("@type") != "OcrPageEvidence":
        raise ValueError("Evidence richiesta: OcrPageEvidence.")
    profile = structure_payload.get("profile")
    rebuilt_structure = reconstruct_document_structure(evidence=evidence, profile=profile)
    if _canonical(structure_payload) != _canonical(rebuilt_structure.to_dict()):
        raise ValueError("Struttura obsoleta o divergente dall'evidence esatta.")
    expected_tokens = _tokenize(loaded_reference.text)
    if [token["normalized"] for token in expected_tokens] != metric_tokens(loaded_reference.text):
        raise ValueError("Il token count della reference non e' mappabile in modo univoco ai token visualizzati.")
    actual_tokens = _evidence_tokens(evidence)
    evidence_text = "\n".join(region["text"] for region in evidence["regions"])
    if [token["normalized"] for token in actual_tokens] != metric_tokens(evidence_text):
        raise ValueError("Il token count dell'evidence non e' mappabile in modo univoco alle regioni.")
    token_cells = (len(expected_tokens) + 1) * (len(actual_tokens) + 1)
    reference_chars = _normalise(loaded_reference.text)
    evidence_chars = _normalise(evidence_text)
    character_cells = (len(reference_chars) + 1) * (len(evidence_chars) + 1)
    if token_cells > _MAX_ALIGNMENT_CELLS:
        raise ValueError("Allineamento troppo grande per una singola pagina (limite 4M celle).")
    if character_cells > _MAX_CHARACTER_COMPARISONS:
        raise ValueError("Confronto caratteri troppo grande per una singola pagina (limite 10M confronti).")

    evaluation = evaluate_page_reference(reference=reference, evidence=evidence, structure=rebuilt_structure)
    if not evaluation["accuracy_eligible"]:
        raise ValueError("Reference/evidence/struttura non sono accuracy-eligible per questa pagina.")

    operations = _alignment(expected_tokens, actual_tokens)
    candidates: list[dict[str, Any]] = []
    for alignment_index, operation in enumerate(operations):
        kind = operation["operation"]
        if kind == "match":
            continue
        reference_index = operation["reference_token_index"]
        output_index = operation["output_token_index"]
        actual = actual_tokens[output_index] if output_index is not None else None
        candidates.append({
            "candidate_id": f"diff-{len(candidates) + 1:04d}",
            "alignment_index": alignment_index,
            "operation": kind,
            "reference_token_index": reference_index,
            "output_token_index": output_index,
            "reference_token": expected_tokens[reference_index]["text"] if reference_index is not None else None,
            "candidate_token": actual["text"] if actual else None,
            "candidate_source_region_ids": [actual["region_id"]] if actual else [],
            "candidate_bounding_boxes": [actual["bbox"]] if actual and actual["bbox"] is not None else [],
            "material_word_error": None,
            "material_error_category": None,
            "visual_review_status": "pending_visual_adjudication",
            "review_note": None,
        })

    payload = {
        "@type": "OcrMaterialErrorReviewDraft",
        "schema_version": "1.0",
        "draft_only": True,
        "inputs": {name: {"path": str(path), "sha256": digest} for name, path, digest in (
            ("reference", paths["reference"], reference_hash),
            ("evidence", paths["evidence"], evidence_hash),
            ("structure", paths["structure"], structure_hash),
            ("image", paths["image"], image_hash),
        )},
        "page_identity": {"page_id": loaded_reference.page_id,
                           "source_image_hash": loaded_reference.source_image_hash,
                           "engine": evidence.get("engine"), "language": evidence.get("language"),
                           "transform_id": evidence.get("transform_id")},
        "accuracy_eligible_reference": True,
        "reference_word_count": len(expected_tokens),
        "alignment_scope": "normalized evidence-region token stream; structure and visual materiality require separate review",
        "alignment_operation_count": len(operations),
        "candidate_difference_count": len(candidates),
        "status": "pending_visual_adjudication" if candidates else "no_token_differences",
        "candidates": candidates,
        "safety": {"material_word_error_count": None, "risk_score": None, "cutoff": None,
                   "machine_pass": False, "auto_validation_enabled": False,
                   "reference_promotion_allowed": False},
        "limitations": [
            "Token differences are suggestions only; verify each against the TIFF/crop and all persistent OCR outputs.",
            "This draft does not classify materiality, certify a zero-error page, or count structural errors.",
            "Only adjudicated calibration cases may feed calibration; never use this draft to inspect or tune on holdout.",
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    operation_status = "preview"
    if apply:
        if target.exists():
            if target.read_text(encoding="utf-8") != encoded:
                raise ValueError(f"Output gia' esistente e diverso: {target}")
            operation_status = "skipped_existing"
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
            operation_status = "written"
    return payload | {"operation_status": operation_status, "output_path": str(target)}
