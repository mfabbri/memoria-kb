from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .apply_profile_patch import apply_profile_patch


def promote_profile_patch_preview(
    *,
    workspace_root: Path,
    profile_patch_preview_json: Path,
    profile_id: str,
    output_dir: Path,
    profiles_index: Path | None = None,
    apply: bool = False,
    sandbox: bool = False,
) -> dict[str, Any]:
    if apply and sandbox:
        raise ValueError("Usare apply oppure sandbox, non entrambi.")
    profile_id = profile_id.strip()
    if not profile_id:
        raise ValueError("Specificare ProfileId.")
    if not profile_patch_preview_json.is_file():
        raise FileNotFoundError(f"ProfilePatch preview non trovata: {profile_patch_preview_json}")

    resolved_profiles_index = profiles_index or workspace_root / "ricerche" / "person_profiles" / "purocielo.index.jsonld"
    profile_jsonld = _resolve_profile_jsonld(profiles_index=resolved_profiles_index, profile_id=profile_id)
    selected_patch = _normalized_patch(_select_profile_patch(profile_patch_preview_json, profile_id=profile_id))

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug(profile_id)
    selected_patch_json = output_dir / f"{slug}.selected_profile_patch.json"
    mode = "apply" if apply else "sandbox" if sandbox else "dry_run"
    audit_json = output_dir / f"{slug}.{mode}.audit.json"
    audit_md = output_dir / f"{slug}.{mode}.audit.md"
    if apply:
        output_jsonld = profile_jsonld
    elif sandbox:
        output_jsonld = output_dir / f"{slug}.sandbox.profile.jsonld"
    else:
        output_jsonld = output_dir / f"{slug}.dry_run.profile.jsonld"
    backup_dir = output_dir / "backups"

    selected_patch_json.write_text(json.dumps(selected_patch, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = apply_profile_patch(
        profile_jsonld=profile_jsonld,
        patch_json=selected_patch_json,
        output_jsonld=output_jsonld,
        audit_json=audit_json,
        audit_md=audit_md,
        backup_dir=backup_dir,
        dry_run=not (apply or sandbox),
    )
    promotion = {
        "@type": "ProfilePatchPreviewPromotion",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "applied" if apply else "sandbox" if sandbox else "dry-run",
        "workspace_root": str(workspace_root),
        "profiles_index": str(resolved_profiles_index),
        "profile_id": profile_id,
        "profile_jsonld": str(profile_jsonld),
        "profile_patch_preview_json": str(profile_patch_preview_json),
        "selected_patch_json": str(selected_patch_json),
        "audit_json": str(audit_json),
        "audit_md": str(audit_md),
        "output_jsonld": str(output_jsonld),
        "operation_count": len(_list_items(selected_patch.get("operations"))),
        "applied_operations": len(_list_items(audit.get("applied_operations"))),
        "conflict_operations": len(_list_items(audit.get("conflict_operations"))),
        "skipped_operations": len(_list_items(audit.get("skipped_operations"))),
        "changed": bool(audit.get("changed")),
        "dry_run": not (apply or sandbox),
        "sandbox": sandbox,
        "writes_canonical_profile": apply,
        "safety_notes": [
            "Dry-run by default; sandbox writes only a derived profile copy.",
            "Canonical profile is written only with explicit apply.",
            "Uses an already generated profile_patch.preview.json.",
            "Does not create verified_facts canonici or touch the evidence store.",
        ],
    }
    summary_json = output_dir / f"{slug}.{mode}.promotion.json"
    summary_md = output_dir / f"{slug}.{mode}.promotion.md"
    promotion["summary_json"] = str(summary_json)
    promotion["summary_md"] = str(summary_md)
    summary_json.write_text(json.dumps(promotion, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md.write_text(render_promotion_markdown(promotion), encoding="utf-8")
    return promotion


def render_promotion_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# ProfilePatch preview promotion",
        "",
        f"- Stato: `{payload.get('status', '')}`",
        f"- Dry-run: `{str(bool(payload.get('dry_run'))).lower()}`",
        f"- Profilo: `{payload.get('profile_id', '')}`",
        f"- Profilo JSON-LD: `{payload.get('profile_jsonld', '')}`",
        f"- Preview sorgente: `{payload.get('profile_patch_preview_json', '')}`",
        f"- Patch selezionata: `{payload.get('selected_patch_json', '')}`",
        f"- Audit: `{payload.get('audit_md', '')}`",
        f"- Operazioni patch: `{payload.get('operation_count', 0)}`",
        f"- Operazioni applicabili: `{payload.get('applied_operations', 0)}`",
        f"- Conflitti: `{payload.get('conflict_operations', 0)}`",
        f"- Operazioni saltate: `{payload.get('skipped_operations', 0)}`",
        f"- Modifica rilevata: `{str(bool(payload.get('changed'))).lower()}`",
        "",
        "## Vincoli",
        "",
    ]
    for note in _list_strings(payload.get("safety_notes")):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def _resolve_profile_jsonld(*, profiles_index: Path, profile_id: str) -> Path:
    if not profiles_index.is_file():
        raise FileNotFoundError(f"Indice profili non trovato: {profiles_index}")
    payload = _load_json_object(profiles_index, label="indice profili")
    matches = []
    for item in _list_items(payload.get("profiles")):
        item_id = str(item.get("@id", "")).strip()
        file_name = str(item.get("file", "")).strip()
        if item_id == profile_id:
            matches.append(file_name)
    if not matches:
        raise ValueError(f"Profilo non trovato nell'indice: {profile_id}")
    unique = sorted(set(matches))
    if len(unique) > 1:
        raise ValueError(f"Profilo ambiguo nell'indice: {profile_id}")
    profile_path = profiles_index.parent / unique[0]
    if not profile_path.is_file():
        raise FileNotFoundError(f"Profilo JSON-LD non trovato: {profile_path}")
    return profile_path


def _select_profile_patch(path: Path, *, profile_id: str) -> dict[str, Any]:
    payload = _load_json_object(path, label="profile patch preview")
    if str(payload.get("@type", "")) == "ProfilePatch":
        patch_profile_id = str(payload.get("profile_id", "")).strip()
        if patch_profile_id != profile_id:
            raise ValueError(f"Patch non trovata per ProfileId: {profile_id}")
        return payload
    if str(payload.get("@type", "")) != "ProfilePatchPreviewBatch":
        raise ValueError("ProfilePatch preview non valida: @type deve essere ProfilePatchPreviewBatch o ProfilePatch.")
    patches = [
        patch
        for patch in _list_items(payload.get("profile_patches"))
        if str(patch.get("profile_id", "")).strip() == profile_id
    ]
    if not patches:
        raise ValueError(f"Patch non trovata per ProfileId: {profile_id}")
    if len(patches) > 1:
        raise ValueError(f"Patch ambigua per ProfileId: {profile_id}")
    return patches[0]


def _normalized_patch(patch: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(patch))
    operations = _list_items(normalized.get("operations"))
    normalized["operations"] = operations
    for operation in operations:
        if not _list_strings(operation.get("source_document_ids")):
            source_document_id = str(operation.get("source_document_id", "")).strip()
            if source_document_id:
                operation["source_document_ids"] = [source_document_id]
        if not _list_strings(operation.get("source_claim_ids")):
            claim_like_ids = [
                str(operation.get("source_item_id", "")).strip(),
                str(operation.get("item_id", "")).strip(),
                str(operation.get("verified_fact_preview_id", "")).strip(),
            ]
            operation["source_claim_ids"] = [value for value in claim_like_ids if value][:1]
    return normalized


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} JSON non valido: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON non valido: il payload deve essere un oggetto.")
    return payload


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "profile"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promuove in modo controllato una ProfilePatch preview.")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--profile-patch-preview-json", required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--profiles-index", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sandbox", action="store_true")
    args = parser.parse_args(argv)

    payload = promote_profile_patch_preview(
        workspace_root=Path(args.workspace_root),
        profile_patch_preview_json=Path(args.profile_patch_preview_json),
        profile_id=args.profile_id,
        output_dir=Path(args.output_dir),
        profiles_index=Path(args.profiles_index) if str(args.profiles_index).strip() else None,
        apply=bool(args.apply),
        sandbox=bool(args.sandbox),
    )
    print(f"ProfilePatch promotion {payload['status']}: {payload['summary_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
