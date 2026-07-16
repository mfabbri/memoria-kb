from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ALLOWED_LIST_PATHS = {
    "/evidence_claim_ids/-": "evidence_claim_ids",
    "/conflicts/-": "conflicts",
    "/searched_sources/-": "searched_sources",
    "/next_research/-": "next_research",
    "/search_hints/-": "search_hints",
}

STRUCTURAL_REVIEW_PATHS = {
    "/birth/date": ("birth", "date"),
    "/birth/place": ("birth", "place"),
    "/death/date": ("death", "date"),
    "/death/place": ("death", "place"),
}


def apply_profile_patch(
    *,
    profile_jsonld: Path,
    patch_json: Path,
    output_jsonld: Path,
    audit_json: Path,
    audit_md: Path,
    backup_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not profile_jsonld.exists():
        raise FileNotFoundError(f"Profilo non trovato: {profile_jsonld}")
    if not patch_json.exists():
        raise FileNotFoundError(f"Patch non trovata: {patch_json}")

    profile_payload = _load_json_object(profile_jsonld, label="profilo")
    patch_payload = _load_json_object(patch_json, label="patch")
    _validate_profile_patch(profile_payload, patch_payload)

    original_payload = json.loads(json.dumps(profile_payload))
    audit = _new_audit(profile_jsonld=profile_jsonld, patch_json=patch_json, output_jsonld=output_jsonld, dry_run=dry_run)

    for operation in patch_payload.get("operations", []):
        if not isinstance(operation, dict):
            audit["skipped_operations"].append({"reason": "invalid_operation_payload", "operation": operation})
            continue
        result = _apply_operation(profile_payload, operation)
        audit[f"{result['status']}_operations"].append(result)

    audit["changed"] = profile_payload != original_payload

    backup_path = ""
    if not dry_run and audit["changed"]:
        backup_path = str(_write_backup(profile_jsonld=profile_jsonld, backup_dir=backup_dir))
        output_jsonld.parent.mkdir(parents=True, exist_ok=True)
        output_jsonld.write_text(json.dumps(profile_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    audit["backup_path"] = backup_path

    audit_json.parent.mkdir(parents=True, exist_ok=True)
    audit_md.parent.mkdir(parents=True, exist_ok=True)
    audit_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    audit_md.write_text(render_apply_profile_patch_audit_markdown(audit), encoding="utf-8")
    return audit


def render_apply_profile_patch_audit_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# ProfilePatch application audit",
        "",
        f"- Profilo: `{audit['profile_jsonld']}`",
        f"- Patch: `{audit['patch_json']}`",
        f"- Output: `{audit['output_jsonld']}`",
        f"- Dry run: `{str(audit['dry_run']).lower()}`",
        f"- Modificato: `{str(audit['changed']).lower()}`",
        f"- Backup: `{audit.get('backup_path') or '(non creato)'}`",
        f"- Operazioni applicate: `{len(audit['applied_operations'])}`",
        f"- Conflitti registrati: `{len(audit['conflict_operations'])}`",
        f"- Operazioni saltate: `{len(audit['skipped_operations'])}`",
        "",
        "## Operazioni applicate",
        "",
    ]
    _append_operation_lines(lines, audit["applied_operations"])
    lines.extend(["", "## Conflitti", ""])
    _append_operation_lines(lines, audit["conflict_operations"])
    lines.extend(["", "## Operazioni saltate", ""])
    _append_operation_lines(lines, audit["skipped_operations"])
    return "\n".join(lines).rstrip() + "\n"


def _apply_operation(profile_payload: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    if _is_explicitly_rejected(operation):
        return _result("skipped", operation, reason="decision_not_accepted")

    path = str(operation.get("path", "")).strip()
    op = str(operation.get("op", "")).strip() or "set"
    value = operation.get("value", "")

    if path.startswith("/verified_facts/"):
        return _apply_verified_fact(profile_payload, operation, path=path, value=value)

    if path in ALLOWED_LIST_PATHS:
        return _append_allowed_list_value(profile_payload, operation, path=path, value=value)

    if path in STRUCTURAL_REVIEW_PATHS:
        return _review_structural_path(profile_payload, operation, path=path, value=value)

    return _result("skipped", operation, reason="path_not_allowed")


def _apply_verified_fact(profile_payload: dict[str, Any], operation: dict[str, Any], *, path: str, value: Any) -> dict[str, Any]:
    key = path.removeprefix("/verified_facts/").replace("~1", "/").replace("~0", "~").strip()
    if not key:
        return _result("skipped", operation, reason="empty_verified_fact_key")

    source_claim_ids = _string_list(operation.get("source_claim_ids"))
    source_document_ids = _string_list(operation.get("source_document_ids"))
    if not source_claim_ids or not source_document_ids:
        return _result("skipped", operation, reason="verified_fact_requires_claims_and_documents")

    verified_facts = profile_payload.setdefault("verified_facts", {})
    if not isinstance(verified_facts, dict):
        return _result("skipped", operation, reason="verified_facts_not_object")

    new_fact = {
        "value": str(value),
        "source_claim_ids": source_claim_ids,
        "source_document_ids": source_document_ids,
        "review_status": "reviewed",
        "provenance": _operation_provenance(operation),
    }
    existing = verified_facts.get(key)
    if existing not in (None, "", new_fact) and _existing_value(existing) != str(value):
        conflict = _conflict_payload(operation, path=path, current_value=existing, candidate_value=value)
        _append_unique(profile_payload.setdefault("conflicts", []), conflict)
        return _result("conflict", operation, reason="existing_verified_fact_differs", conflict=conflict)

    verified_facts[key] = new_fact
    _append_many_unique(profile_payload.setdefault("evidence_claim_ids", []), source_claim_ids)
    return _result("applied", operation, reason="verified_fact_applied")


def _append_allowed_list_value(profile_payload: dict[str, Any], operation: dict[str, Any], *, path: str, value: Any) -> dict[str, Any]:
    field = ALLOWED_LIST_PATHS[path]
    items = profile_payload.setdefault(field, [])
    if not isinstance(items, list):
        return _result("skipped", operation, reason=f"{field}_not_list")

    if field == "evidence_claim_ids":
        values = _string_list(value)
        if not values:
            values = _string_list(operation.get("source_claim_ids"))
        if not values:
            return _result("skipped", operation, reason="empty_evidence_claim_ids")
        _append_many_unique(items, values)
        return _result("applied", operation, reason="evidence_claim_ids_appended")

    if field == "search_hints":
        if not isinstance(value, dict):
            return _result("skipped", operation, reason="search_hint_value_must_be_object")
        if not str(value.get("provenance", "")).strip():
            return _result("skipped", operation, reason="search_hint_requires_provenance")
        value.setdefault("review_status", "unreviewed")

    _append_unique(items, value)
    return _result("applied", operation, reason=f"{field}_appended")


def _review_structural_path(profile_payload: dict[str, Any], operation: dict[str, Any], *, path: str, value: Any) -> dict[str, Any]:
    first, second = STRUCTURAL_REVIEW_PATHS[path]
    container = profile_payload.setdefault(first, {})
    if not isinstance(container, dict):
        return _result("skipped", operation, reason=f"{first}_not_object")

    current_value = str(container.get(second, "")).strip()
    candidate_value = str(value).strip()
    if not candidate_value:
        return _result("skipped", operation, reason="empty_structural_value")
    if not current_value:
        container[second] = candidate_value
        _append_many_unique(profile_payload.setdefault("evidence_claim_ids", []), _string_list(operation.get("source_claim_ids")))
        return _result("applied", operation, reason="empty_structural_field_filled")
    if current_value == candidate_value:
        _append_many_unique(profile_payload.setdefault("evidence_claim_ids", []), _string_list(operation.get("source_claim_ids")))
        return _result("applied", operation, reason="structural_value_confirmed")

    conflict = _conflict_payload(operation, path=path, current_value=current_value, candidate_value=candidate_value)
    _append_unique(profile_payload.setdefault("conflicts", []), conflict)
    return _result("conflict", operation, reason="structural_value_differs", conflict=conflict)


def _validate_profile_patch(profile_payload: dict[str, Any], patch_payload: dict[str, Any]) -> None:
    if str(patch_payload.get("@type", "")) != "ProfilePatch":
        raise ValueError("Patch non valida: @type deve essere ProfilePatch.")
    if "operations" not in patch_payload or not isinstance(patch_payload.get("operations"), list):
        raise ValueError("Patch non valida: operations deve essere una lista.")

    profile_id = str(profile_payload.get("profile_id") or profile_payload.get("@id") or "").strip()
    patch_profile_id = str(patch_payload.get("profile_id", "")).strip()
    if patch_profile_id and profile_id and patch_profile_id != profile_id:
        raise ValueError(f"Patch non valida: profile_id divergente ({patch_profile_id} != {profile_id}).")


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} JSON non valido: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON non valido: il payload deve essere un oggetto.")
    return payload


def _write_backup(*, profile_jsonld: Path, backup_dir: Path | None) -> Path:
    destination_dir = backup_dir if backup_dir is not None else profile_jsonld.parent
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = destination_dir / f"{profile_jsonld.stem}.{timestamp}.backup{profile_jsonld.suffix}"
    shutil.copy2(profile_jsonld, backup_path)
    return backup_path


def _new_audit(*, profile_jsonld: Path, patch_json: Path, output_jsonld: Path, dry_run: bool) -> dict[str, Any]:
    return {
        "@type": "ApplyProfilePatchAudit",
        "generated_at": datetime.now(UTC).isoformat(),
        "profile_jsonld": str(profile_jsonld),
        "patch_json": str(patch_json),
        "output_jsonld": str(output_jsonld),
        "dry_run": dry_run,
        "changed": False,
        "backup_path": "",
        "applied_operations": [],
        "conflict_operations": [],
        "skipped_operations": [],
    }


def _result(status: str, operation: dict[str, Any], *, reason: str, conflict: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "reason": reason,
        "path": str(operation.get("path", "")),
        "op": str(operation.get("op", "")),
        "candidate_update_id": str(operation.get("candidate_update_id", "")),
        "source_claim_ids": _string_list(operation.get("source_claim_ids")),
        "source_document_ids": _string_list(operation.get("source_document_ids")),
    }
    if conflict is not None:
        payload["conflict"] = conflict
    return payload


def _conflict_payload(operation: dict[str, Any], *, path: str, current_value: Any, candidate_value: Any) -> dict[str, Any]:
    return {
        "field": path.strip("/").replace("/", "."),
        "current_value": _existing_value(current_value),
        "candidate_value": str(candidate_value),
        "candidate_update_id": str(operation.get("candidate_update_id", "")),
        "source_claim_ids": _string_list(operation.get("source_claim_ids")),
        "source_document_ids": _string_list(operation.get("source_document_ids")),
        "review_status": "needs_review",
        "provenance": _operation_provenance(operation),
    }


def _operation_provenance(operation: dict[str, Any]) -> str:
    update_id = str(operation.get("candidate_update_id", "")).strip()
    if update_id:
        return f"ProfilePatch:{update_id}"
    return "ProfilePatch"


def _append_operation_lines(lines: list[str], operations: list[dict[str, Any]]) -> None:
    if not operations:
        lines.extend(["Nessuna.", ""])
        return
    for operation in operations:
        lines.extend(
            [
                f"- `{operation.get('path', '')}`: {operation.get('reason', '')}",
            ]
        )


def _is_explicitly_rejected(operation: dict[str, Any]) -> bool:
    decision = str(operation.get("decision", operation.get("review_status", ""))).strip()
    return decision in {"rejected", "uncertain", "pending"}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _append_many_unique(items: list[Any], values: list[Any]) -> None:
    for value in values:
        _append_unique(items, value)


def _append_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def _existing_value(value: Any) -> str:
    if isinstance(value, dict) and "value" in value:
        return str(value.get("value", ""))
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Applica in modo controllato una ProfilePatch a un profilo JSON-LD.")
    parser.add_argument("--profile-jsonld", required=True)
    parser.add_argument("--patch-json", required=True)
    parser.add_argument("--output-jsonld", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--audit-md", required=True)
    parser.add_argument("--backup-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    audit = apply_profile_patch(
        profile_jsonld=Path(args.profile_jsonld),
        patch_json=Path(args.patch_json),
        output_jsonld=Path(args.output_jsonld),
        audit_json=Path(args.audit_json),
        audit_md=Path(args.audit_md),
        backup_dir=Path(args.backup_dir) if args.backup_dir else None,
        dry_run=args.dry_run,
    )
    print(f"Operazioni applicate: {len(audit['applied_operations'])}")
    print(f"Conflitti registrati: {len(audit['conflict_operations'])}")
    print(f"Operazioni saltate: {len(audit['skipped_operations'])}")
    print(f"Audit JSON: {args.audit_json}")
    print(f"Audit Markdown: {args.audit_md}")
    if audit.get("backup_path"):
        print(f"Backup: {audit['backup_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
