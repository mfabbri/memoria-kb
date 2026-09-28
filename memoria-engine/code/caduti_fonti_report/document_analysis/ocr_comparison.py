"""Deterministic, read-only orchestration for page-scoped OCR comparisons."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import json
from typing import Any

from .document_structure import reconstruct_document_structure
from .ocr_reference_metrics import evaluate_page_reference


def compare_manifest(*, manifest: Mapping[str, Any], base_dir: str | Path | None = None) -> dict[str, Any]:
    """Evaluate the cases declared by a comparison manifest without writing files.

    Each case points to a page reference and an ``OcrPageEvidence`` JSON file.
    The structure is reconstructed from the evidence so the report cannot drift
    from the selected profile.  References remain diagnostic unless the T38
    contract marks them as human-verified and identity-compatible.
    """
    if not isinstance(manifest, Mapping) or manifest.get("@type") != "OcrComparisonManifest":
        raise ValueError("Il confronto OCR richiede @type OcrComparisonManifest.")
    if manifest.get("schema_version") != "1.0":
        raise ValueError("Il manifest di confronto OCR richiede schema_version 1.0.")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Il manifest di confronto OCR richiede cases non vuoto.")
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            raise ValueError(f"Caso di confronto {index} non valido.")
        case_id = _required_text(case.get("case_id"), f"cases[{index}].case_id")
        if case_id in seen:
            raise ValueError(f"case_id duplicato: {case_id}.")
        seen.add(case_id)
        profile = _required_text(case.get("profile"), f"cases[{index}].profile")
        reference = _load_json(root, case.get("reference_path"), f"cases[{index}].reference_path")
        evidence = _load_json(root, case.get("evidence_path"), f"cases[{index}].evidence_path")
        structure = reconstruct_document_structure(evidence=evidence, profile=profile)
        evaluation = evaluate_page_reference(reference=reference, evidence=evidence, structure=structure)
        results.append({"case_id": case_id, "profile": profile, "evaluation": evaluation})
    eligible = sum(1 for item in results if item["evaluation"]["accuracy_eligible"])
    return {
        "@type": "OcrComparisonReport",
        "schema_version": "1.0",
        "case_count": len(results),
        "accuracy_eligible_case_count": eligible,
        "results": results,
    }


def compare_manifest_file(path: str | Path) -> dict[str, Any]:
    """Load one manifest path and return the same in-memory report."""
    manifest_path = Path(path)
    manifest = _read_json(manifest_path)
    return compare_manifest(manifest=manifest, base_dir=manifest_path.parent)


def _load_json(root: Path, value: Any, field: str) -> dict[str, Any]:
    relative_path = _required_text(value, field)
    path = Path(relative_path)
    if not path.is_absolute():
        path = root / path
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{field} deve contenere un oggetto JSON.")
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Impossibile leggere JSON di confronto: {path}.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Il JSON di confronto deve contenere un oggetto: {path}.")
    return payload


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Il confronto OCR richiede {field} non vuoto.")
    return value.strip()
