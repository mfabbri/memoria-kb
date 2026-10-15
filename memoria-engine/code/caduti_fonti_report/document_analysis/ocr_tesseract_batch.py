"""Manifest-driven, offline adaptation of attested Tesseract page evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .ocr_tesseract_evidence_adapter import adapt_tesseract_page_evidence


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload, hashlib.sha256(raw).hexdigest()


def _resolve(base: Path, value: str | Path) -> Path:
    path = Path(value)
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(serialized)


def run_tesseract_evidence_batch(
    *, manifest_path: Path, output_dir: Path | None = None,
    report_path: Path | None = None, apply: bool = False,
) -> dict[str, Any]:
    """Adapt cases independently; write new evidence/report only with explicit apply.

    Manifest v1 contains ``cases`` with a unique filename-safe ``case_id`` and
    JSON paths ``processed_text``, ``primary_evidence``, ``original_page`` and
    optionally ``registration``. All relative paths, including destinations,
    resolve against the manifest directory. Original anchors are JSON objects.
    Structural manifest errors and destination collisions abort before writes;
    page input and adapter errors are recorded independently in manifest order.
    """
    manifest_path = manifest_path.resolve()
    manifest, manifest_hash = _read_json(manifest_path)
    if (manifest.get("@type") != "TesseractEvidenceBatchManifest"
            or manifest.get("schema_version") != "1.0"
            or not isinstance(manifest.get("cases"), list) or not manifest["cases"]):
        raise ValueError("Expected TesseractEvidenceBatchManifest v1.0 with nonempty cases.")
    base = manifest_path.parent
    required = {"case_id", "processed_text", "primary_evidence", "original_page"}
    cases = []
    seen: set[str] = set()
    for case in manifest["cases"]:
        if not isinstance(case, dict) or not required <= case.keys() or case.keys() - required - {"registration"}:
            raise ValueError("Each manifest case requires case_id and explicit JSON input paths.")
        case_id = case["case_id"]
        if (not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}", case_id)
                or case_id.casefold() in seen):
            raise ValueError("Manifest case_id must be unique and filename-safe (case insensitive).")
        seen.add(case_id.casefold())
        inputs = {}
        for key, value in case.items():
            if key == "case_id":
                continue
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Manifest {key} must be a nonempty JSON path.")
            inputs[key] = _resolve(base, value)
        cases.append((case_id, inputs))
    if apply and (output_dir is None or report_path is None):
        raise ValueError("--apply requires explicit output_dir and report_path.")
    destination_dir = _resolve(base, output_dir) if output_dir is not None else None
    report_destination = _resolve(base, report_path) if report_path is not None else None
    outputs = {case_id: (destination_dir / f"{case_id}.tesseract.evidence.json").resolve()
               for case_id, _ in cases} if destination_dir is not None else {}
    destinations = list(outputs.values()) + ([report_destination] if report_destination is not None else [])
    input_paths = {manifest_path} | {path for _, inputs in cases for path in inputs.values()}
    if len(set(destinations)) != len(destinations) or any(path in input_paths for path in destinations):
        raise ValueError("Evidence/report destinations must be distinct from each other and all inputs.")
    if any(left != right and left in right.parents for left in destinations for right in destinations):
        raise ValueError("A destination file cannot also be a destination directory.")
    for path in destinations:
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refusing existing destination: {path}")
    report: dict[str, Any] = {
        "@type": "TesseractEvidenceBatchReport", "schema_version": "1.0",
        "manifest": {"path": str(manifest_path), "sha256": manifest_hash},
        "diagnostic_only": True, "machine_pass_allowed": False,
        "visual_coverage_verified": False, "apply": apply, "cases": [],
    }
    for case_id, inputs in cases:
        record: dict[str, Any] = {
            "case_id": case_id, "inputs": {key: {"path": str(path)} for key, path in inputs.items()},
            "status": "error", "written": False,
            "output_path": str(outputs[case_id]) if case_id in outputs else None,
        }
        report["cases"].append(record)
        try:
            payloads = {}
            for key, path in inputs.items():
                payloads[key], digest = _read_json(path)
                record["inputs"][key]["sha256"] = digest
            evidence = adapt_tesseract_page_evidence(**payloads)
            if apply:
                _write_new(outputs[case_id], evidence)
            record.update(status="success", written=apply, page_id=evidence["page_id"])
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
            record["error"] = {"type": type(exc).__name__, "message": str(exc)}
    report["summary"] = {
        "success": sum(case["status"] == "success" for case in report["cases"]),
        "error": sum(case["status"] == "error" for case in report["cases"]),
    }
    if apply:
        _write_new(report_destination, report)
    return report
