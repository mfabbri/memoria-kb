"""Finalize editable OCR review sidecars without weakening package provenance."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from . import ocr_review_batch as batch


EDITABLE_REVIEW_ROLES = ("lexicon_review", "layout", "ledger", "dispositions")


def _read_manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Il package manifest deve essere un oggetto JSON.")
    return value, hashlib.sha256(raw).hexdigest()


def _current_artifact(record: Any, label: str, *, root: Path | None, expected_digest: bool) -> dict[str, str]:
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
    if expected_digest and digest != record["sha256"]:
        raise ValueError(f"{label}: input immutabile modificato o SHA-256 non corrispondente.")
    return {"path": str(path), "sha256": digest}


def _submission_manifest(source: Path, final: Path, package: dict[str, Any], source_digest: str) -> dict[str, Any]:
    root = source.parent
    if (package.get("@type") != "OcrReviewPackage" or package.get("schema_version") != "1.0"
            or not isinstance(package.get("pages"), list) or not package["pages"]):
        raise ValueError("Manifest OcrReviewPackage v1.0 con pagine richiesto.")
    if package.get("output_dir") != str(root) or package.get("report_path") != str(source):
        raise ValueError("Manifest package output_dir/report_path non corrispondenti al file originale.")
    if (package.get("machine_pass") is not False or package.get("auto_validation_enabled") is not False
            or package.get("review_status") != "unreviewed"):
        raise ValueError("Il package deve restare unreviewed senza promozione automatica.")
    batch._artifact(package.get("source_manifest"), "source_manifest")
    batch._artifact(package.get("t37_manifest"), "t37_manifest", root=root)

    derived = deepcopy(package)
    seen_ids: set[str] = set()
    for page in derived["pages"]:
        page_id = page.get("page_id") if isinstance(page, dict) else None
        if not isinstance(page_id, str) or not page_id.strip() or page_id in seen_ids:
            raise ValueError("page_id obbligatori e unici nel package.")
        seen_ids.add(page_id)
        roles = page.get("review_inputs")
        if not isinstance(roles, dict) or set(roles) != set(batch.REVIEW_ROLES):
            raise ValueError(f"{page_id}: review_inputs deve dichiarare tutti e soli i ruoli richiesti.")
        current: dict[str, dict[str, str]] = {}
        for role in batch.REVIEW_ROLES:
            current[role] = _current_artifact(
                roles[role], f"{page_id}/{role}", root=None if role == "image" else root,
                expected_digest=role not in EDITABLE_REVIEW_ROLES)
        for role in EDITABLE_REVIEW_ROLES:
            roles[role] = current[role]

        outputs = page.get("outputs")
        if not isinstance(outputs, list):
            raise ValueError(f"{page_id}: outputs deve essere una lista hash-bound.")
        output_paths: set[str] = set()
        for index, artifact in enumerate(outputs):
            refreshed = _current_artifact(artifact, f"{page_id}/outputs/{index}", root=root,
                                          expected_digest=False)
            old = artifact["sha256"]
            allowed = {current[role]["path"] for role in EDITABLE_REVIEW_ROLES}
            if old != refreshed["sha256"] and refreshed["path"] not in allowed:
                raise ValueError(f"{page_id}: output immutabile modificato: {refreshed['path']}.")
            if refreshed["path"] in output_paths:
                raise ValueError(f"{page_id}: path output duplicato.")
            output_paths.add(refreshed["path"])
            if refreshed["path"] in allowed:
                outputs[index] = refreshed
        if any(current[role]["path"] not in output_paths for role in EDITABLE_REVIEW_ROLES):
            raise ValueError(f"{page_id}: sidecar modificabile non registrato in outputs.")

    derived["output_dir"] = str(root)
    derived["report_path"] = str(final)
    derived["submission_provenance"] = {
        "source_package_manifest": {"path": str(source), "sha256": source_digest},
        "refreshed_review_roles": list(EDITABLE_REVIEW_ROLES),
        "refreshed_page_count": len(derived["pages"]),
    }
    return derived


def finalize_ocr_review_package(*, manifest_path: Path, final_manifest_path: Path,
                                output_path: Path, apply: bool = False) -> dict[str, Any]:
    """Refresh only editable review digests, then run the existing page gates.

    Preview evaluates an in-memory derived manifest and writes nothing. Apply
    publishes a new manifest beside the package inputs and a separate batch
    report; the original package manifest and OCR artifacts remain untouched.
    """
    source = Path(manifest_path).resolve(strict=True)
    package, source_digest = _read_manifest(source)
    root = source.parent
    final = Path(final_manifest_path).absolute().resolve()
    if final.parent != root or final == source or final.is_symlink() or final.exists():
        raise ValueError("Il manifest derivato deve essere un file nuovo nella directory del package.")
    repository_root = Path(__file__).resolve().parents[4]
    if root == repository_root or root.is_relative_to(repository_root):
        raise ValueError("Il package review deve restare esterno al repository.")
    derived = _submission_manifest(source, final, package, source_digest)
    raw = (json.dumps(derived, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    report_path = Path(output_path)

    if not apply:
        report = batch.run_ocr_review_batch(
            manifest_path=final, output_path=report_path, package_payload=derived,
            guard_manifest_path=source, guard_manifest_sha256=source_digest, apply=False)
        return {"@type": "OcrReviewFinalization", "schema_version": "1.0",
                "source_package_manifest": {"path": str(source), "sha256": source_digest},
                "final_package_manifest": {"path": str(final), "sha256": digest},
                "review_batch": report, "operation_status": "preview", "writes_performed": False}

    batch._new_output(report_path, root)
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_digest:
        raise ValueError("Il package originale è cambiato durante la finalizzazione.")
    with final.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(raw.decode("utf-8"))
    report = batch.run_ocr_review_batch(
        manifest_path=final, output_path=report_path, guard_manifest_path=source,
        guard_manifest_sha256=source_digest, apply=True)
    return {"@type": "OcrReviewFinalization", "schema_version": "1.0",
            "source_package_manifest": {"path": str(source), "sha256": source_digest},
            "final_package_manifest": {"path": str(final), "sha256": digest},
            "review_batch": report, "operation_status": "written", "writes_performed": True}
