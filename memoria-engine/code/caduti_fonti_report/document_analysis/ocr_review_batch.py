"""Hash-bound, read-only page gates over an explicit OCR review package."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .ocr_review_orchestrator import run_ocr_review


REVIEW_ROLES = ("image", "evidence", "structure", "markdown", "lexicon_review",
                "layout", "ledger", "dispositions", "comparison", "tesseract_evidence")
_SAFE_STATUS = {"machine_pass": False, "auto_validation_enabled": False,
                "promotion_status": "unreviewed", "review_status": "unreviewed",
                "semantic_accuracy_status": "not_attested", "gold_promotion_allowed": False,
                "human_verified": False, "claim_extraction_allowed": False}


def _artifact(record: Any, label: str, *, root: Path | None = None) -> dict[str, str]:
    if (not isinstance(record, dict) or not isinstance(record.get("path"), str)
            or not record["path"].strip() or not isinstance(record.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None):
        raise ValueError(f"{label}: path e SHA-256 obbligatori.")
    path = Path(record["path"])
    if not path.is_absolute():
        raise ValueError(f"{label}: path assoluto richiesto.")
    path = path.resolve(strict=True)
    if not path.is_file() or (root is not None and not path.is_relative_to(root)):
        raise ValueError(f"{label}: file fuori dal package o non regolare.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record["sha256"]:
        raise ValueError(f"{label}: SHA-256 non corrispondente.")
    return {"path": str(path), "sha256": digest}


def _new_output(path: Path, package_root: Path) -> Path:
    if path.is_symlink() or path.exists():
        raise FileExistsError(f"Il report deve essere nuovo: {path}")
    destination = path.resolve()
    repository_root = Path(__file__).resolve().parents[4]
    if (not destination.parent.is_dir() or destination.is_relative_to(package_root)
            or destination.is_relative_to(repository_root)):
        raise ValueError("Il report richiede un padre esistente, esterno al package e al repository.")
    return destination


def run_ocr_review_batch(*, manifest_path: Path, output_path: Path,
                         apply: bool = False, package_payload: dict[str, Any] | None = None,
                         guard_manifest_path: Path | None = None,
                         guard_manifest_sha256: str | None = None) -> dict[str, Any]:
    """Validate the complete package before invoking independent page preflights.

    Missing/stale provenance is a package error; gate failures remain local to a
    page. Only an exclusive new aggregate report can be written by this wrapper.
    """
    source = Path(manifest_path).resolve(strict=package_payload is None)
    raw = (source.read_bytes() if package_payload is None else
           (json.dumps(package_payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))
    package_digest = hashlib.sha256(raw).hexdigest()
    package = json.loads(raw) if package_payload is None else package_payload
    guard = Path(guard_manifest_path).resolve(strict=True) if guard_manifest_path is not None else source
    expected_guard = guard_manifest_sha256 or package_digest
    if package_payload is not None and (guard_manifest_path is None or guard_manifest_sha256 is None or apply):
        raise ValueError("Preview payload richiede il binding al package originale e non scrive.")
    if (not isinstance(package, dict) or package.get("@type") != "OcrReviewPackage"
            or package.get("schema_version") != "1.0"
            or not isinstance(package.get("pages"), list) or not package["pages"]):
        raise ValueError("Manifest OcrReviewPackage schema 1.0 con pagine richiesto.")
    root = source.parent
    if package.get("output_dir") != str(root) or package.get("report_path") != str(source):
        raise ValueError("Manifest package: output_dir/report_path non corrispondenti.")
    if (package.get("machine_pass") is not False or package.get("auto_validation_enabled") is not False
            or package.get("review_status") != "unreviewed"):
        raise ValueError("Il package deve mantenere stato unreviewed senza promozione automatica.")
    destination = _new_output(Path(output_path), root)
    package_inputs = {role: _artifact(package.get(role), role,
                                    root=root if role == "t37_manifest" else None)
                      for role in ("source_manifest", "t37_manifest")}
    pages = []
    ids: set[str] = set()
    for page in package["pages"]:
        page_id = page.get("page_id") if isinstance(page, dict) else None
        if not isinstance(page_id, str) or not page_id.strip() or page_id in ids:
            raise ValueError("page_id obbligatori e unici nel package.")
        ids.add(page_id)
        roles = page.get("review_inputs")
        if not isinstance(roles, dict) or set(roles) != set(REVIEW_ROLES):
            raise ValueError(f"{page_id}: review_inputs deve dichiarare tutti e soli i ruoli richiesti.")
        inputs = {role: _artifact(roles[role], f"{page_id}/{role}",
                                 root=None if role == "image" else root)
                  for role in REVIEW_ROLES}
        pages.append((page_id, inputs))

    results = []
    for page_id, inputs in pages:
        result: dict[str, Any] = {"page_id": page_id, "inputs": inputs, **_SAFE_STATUS}
        try:
            # Recheck against the manifest immediately before and after each
            # gate, including blocked returns from the existing orchestrator.
            for role, record in inputs.items():
                _artifact(record, f"{page_id}/{role}")
            for role in ("evidence", "tesseract_evidence"):
                evidence = json.loads(Path(inputs[role]["path"]).read_bytes())
                if not isinstance(evidence, dict) or evidence.get("page_id") != page_id:
                    raise ValueError(f"{page_id}/{role}: identita' pagina non corrispondente.")
            review = run_ocr_review(**{role + "_path": Path(record["path"])
                                      for role, record in inputs.items()})
            for role, record in inputs.items():
                _artifact(record, f"{page_id}/{role}")
            result.update(status=review["status"], review=review | _SAFE_STATUS)
        except Exception as exc:
            result.update(status="error", error={"type": type(exc).__name__, "detail": str(exc)})
        results.append(result)
    # A later page may share inputs with an earlier one. Keep the complete
    # aggregate bound to bytes still current at the end of processing.
    for result in results:
        try:
            for role, record in result["inputs"].items():
                _artifact(record, f"{result['page_id']}/{role}")
        except (OSError, ValueError) as exc:
            result.pop("review", None)
            result.update(status="error", error={"type": type(exc).__name__, "detail": str(exc)})
    # The report must never claim linkage to a manifest changed during gates.
    if hashlib.sha256(guard.read_bytes()).hexdigest() != expected_guard:
        raise ValueError("Il manifest package sorgente e' cambiato durante il batch.")
    for role, record in package_inputs.items():
        _artifact(record, role)
    counts = dict(sorted(Counter(row["status"] for row in results).items()))
    report = {"@type": "OcrReviewBatch", "schema_version": "1.0",
              "package_manifest": {"path": str(source), "sha256": package_digest},
              "package_inputs": package_inputs, "pages": results, "counts": counts,
              "status": "blocked" if any(row["status"] in ("blocked", "error", "correction_required")
                                         for row in results) else "completed",
              **_SAFE_STATUS, "operation_status": "written" if apply else "preview",
              "output_path": str(destination)}
    if apply:
        payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        _new_output(Path(output_path), root)
        with destination.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    return report
