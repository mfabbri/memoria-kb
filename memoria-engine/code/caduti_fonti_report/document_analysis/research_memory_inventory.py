"""Read-only verification of explicit review receipts and their artifact chains."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def build_research_memory_inventory(*, receipt_paths: list[Path], output_dir: Path) -> dict[str, Any]:
    if not receipt_paths:
        raise ValueError("At least one explicit receipt is required")
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output_dir must be new or empty")
    records = []
    profiles: set[str] = set()
    for receipt_path in receipt_paths:
        path = receipt_path.resolve(strict=True)
        raw = path.read_bytes()
        receipt = _json(raw, "receipt")
        if receipt.get("@type") != "CandidateEvidenceClaimReviewReceipt":
            raise ValueError(f"Unsupported receipt type: {path}")
        if receipt.get("review_status") != "complete" or receipt.get("review_complete") is not True:
            raise ValueError(f"Receipt is not complete: {path}")
        decisions = receipt.get("decisions")
        if not isinstance(decisions, list):
            raise ValueError(f"Receipt decisions must be a list: {path}")
        profile_ids = sorted({str(x.get("profile_id", "")) for x in decisions if isinstance(x, dict) and x.get("profile_id")})
        profiles.update(profile_ids)
        artifact_refs = _artifact_references(receipt)
        checks = [_verify_file(reference, receipt_path=path) for reference in artifact_refs]
        catalog = receipt.get("source_documents_catalog", {})
        catalog_state = _verify_catalog(catalog) if isinstance(catalog, dict) else "unavailable"
        records.append({
            "receipt_path": str(path), "receipt_sha256": hashlib.sha256(raw).hexdigest(),
            "profiles": profile_ids, "decision_count": len(decisions),
            "decision_counts": receipt.get("decision_counts", {}),
            "claim_ids": [str(x.get("claim_id", "")) for x in decisions if isinstance(x, dict)],
            "artifact_checks": checks, "catalog_snapshot_state": catalog_state,
        })
    inventory = {
        "@type": "ResearchMemorySessionInventory", "schema_version": "1.0",
        "profile_ids": sorted(profiles), "receipt_count": len(records),
        "decision_count": sum(x["decision_count"] for x in records),
        "sessions": records, "preview_only": True, "canonical_write_allowed": False,
    }
    encoded = json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "research-memory-inventory.json").write_text(encoded, encoding="utf-8")
    markdown = ["# Research memory session inventory", "", f"- Receipts: {len(records)}", f"- Decisions: {inventory['decision_count']}", f"- Profiles: {', '.join(inventory['profile_ids'])}", "- Canonical writes: disabled", ""]
    for record in records:
        markdown += [f"## {record['receipt_path']}", "", f"- Receipt SHA-256: `{record['receipt_sha256']}`", f"- Decisions: {record['decision_count']} {record['decision_counts']}", f"- Catalog snapshot: `{record['catalog_snapshot_state']}`", ""]
        markdown += [f"- `{c['name']}`: `{c['status']}` ({c.get('detail','')})" for c in record["artifact_checks"]]
        markdown.append("")
    (output_dir / "research-memory-inventory.md").write_text("\n".join(markdown), encoding="utf-8")
    return inventory


def _artifact_references(receipt: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for field in ("preview_manifest", "claims_input"):
        item = receipt.get(field)
        if isinstance(item, dict):
            refs.append({"name": field, "path": str(item.get("path", "")), "sha256": str(item.get("sha256", ""))})
    artifacts = receipt.get("preview_artifacts", {})
    if isinstance(artifacts, dict):
        for name, item in sorted(artifacts.items()):
            if isinstance(item, dict):
                refs.append({"name": str(name), "path": str(item.get("path", "")), "sha256": str(item.get("sha256", ""))})
    return refs


def _verify_file(reference: dict[str, str], *, receipt_path: Path) -> dict[str, str]:
    path = Path(reference["path"]) if reference["path"] else Path(".") / "__missing_reference__"
    expected = reference["sha256"]
    resolved_from = ""
    if not path.is_file():
        relocated = _relocated_path(path, receipt_path=receipt_path, expected_sha256=expected)
        if relocated is None:
            return {**reference, "status": "missing"}
        path, resolved_from = relocated, "artifact-relocation-manifest"
    actual = _hash_file(path)
    return {**reference, "status": "verified" if actual == expected else "hash_mismatch",
            "actual_sha256": actual, "resolved_path": str(path), "resolved_from": resolved_from}


def _relocated_path(original_path: Path, *, receipt_path: Path, expected_sha256: str) -> Path | None:
    for parent in [receipt_path.parent, *list(receipt_path.parents)[:4]]:
        manifest_path = parent / "artifact-relocation-manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = _json(manifest_path.read_bytes(), "artifact relocation manifest")
            source_root = Path(str(manifest["original_directory"]))
            target_root = Path(str(manifest["persistent_directory"]))
            relative = original_path.relative_to(source_root)
        except (KeyError, ValueError, OSError):
            continue
        target_path = target_root / relative
        relative_key = str(relative).replace("/", "\\").casefold()
        listed = manifest.get("files", [])
        expected_listed = any(
            isinstance(item, dict)
            and str(item.get("path", "")).replace("/", "\\").casefold() == relative_key
            and str(item.get("sha256", "")).casefold() == expected_sha256.casefold()
            for item in listed
        ) if isinstance(listed, list) else False
        if expected_listed and target_path.is_file():
            return target_path
    return None


def _verify_catalog(catalog: dict[str, Any]) -> str:
    path = Path(str(catalog.get("path", "")))
    expected = str(catalog.get("database_sha256", catalog.get("sha256", "")))
    if not path.is_file():
        return "snapshot_unavailable"
    actual = _hash_file(path)
    if expected and actual == expected:
        return "current_snapshot_verified"
    return "catalog_drift_since_review"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(raw: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid {name} JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value
