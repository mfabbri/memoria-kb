from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caduti_fonti_report.candidate_profile_updates import UPDATE_PATHS
from caduti_fonti_report.document_analysis.preview_payloads import (
    list_items,
    list_strings,
    load_json_object,
    write_json,
    write_markdown,
    yaml_value,
)


def build_verified_facts_profile_patch_preview(
    *,
    verified_facts_preview_json: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
    profile_id: list[str] | None = None,
    limit: int = 0,
) -> dict[str, Any]:
    if not verified_facts_preview_json.is_file():
        raise FileNotFoundError(f"Verified facts preview non trovato: {verified_facts_preview_json}")
    preview = load_json_object(verified_facts_preview_json)
    profile_filter = [value for value in profile_id or [] if str(value).strip()]
    facts = _selected_facts(preview, profile_filter=profile_filter)
    if limit > 0:
        facts = facts[:limit]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped: list[dict[str, str]] = []
    for fact in facts:
        operation, reason = _operation_from_fact(fact)
        if operation is None:
            skipped.append(_skipped_fact(fact, reason))
            continue
        grouped[str(fact.get("profile_id", "")).strip()].append(operation)

    generated_at = datetime.now(UTC).isoformat()
    patches = [
        {
            "@type": "ProfilePatch",
            "generated_at": generated_at,
            "profile_id": profile,
            "profile_source_file": "",
            "source_verified_facts_preview": str(verified_facts_preview_json),
            "apply_policy": "requires_explicit_apply_profile_patch_command",
            "review_status": "preview-only",
            "publication_status": "not_publishable_without_editorial_review",
            "preview_only": True,
            "operations": sorted(operations, key=lambda item: (item["path"], item["value"], item["verified_fact_preview_id"])),
            "accepted_decisions": [],
        }
        for profile, operations in sorted(grouped.items())
    ]
    payload: dict[str, Any] = {
        "@type": "ProfilePatchPreviewBatch",
        "generated_at": generated_at,
        "source_verified_facts_preview": str(verified_facts_preview_json),
        "profile_ids": profile_filter,
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "apply_policy": "requires_explicit_apply_profile_patch_command",
        "patch_count": len(patches),
        "operation_count": sum(len(patch["operations"]) for patch in patches),
        "skipped_fact_count": len(skipped),
        "profile_patches": patches,
        "skipped_facts": skipped,
        "safety_notes": [
            "Preview derivata da VerifiedFactPreview gia' approvati nello store.",
            "Non modifica profili JSON-LD e non applica ProfilePatch.",
            "Ogni applicazione richiede comando esplicito, backup e audit separato.",
        ],
    }

    if output_json is not None:
        write_json(output_json, payload)
    if output_md is not None:
        write_markdown(output_md, render_verified_facts_profile_patch_preview_markdown(payload))
    return payload


def render_verified_facts_profile_patch_preview_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: profile_patch_preview_batch",
        f"review_status: {yaml_value(payload.get('review_status', 'preview-only'))}",
        f"publication_status: {yaml_value(payload.get('publication_status', 'not_publishable_without_editorial_review'))}",
        "preview_only: true",
        "---",
        "",
        "# ProfilePatch preview da VerifiedFactPreview",
        "",
        "Proposta tecnica preview-only. Non applica modifiche ai profili JSON-LD.",
        "",
        "## Sintesi",
        "",
        f"- Patch profilo: `{payload.get('patch_count', 0)}`",
        f"- Operazioni: `{payload.get('operation_count', 0)}`",
        f"- Fatti saltati: `{payload.get('skipped_fact_count', 0)}`",
        f"- Sorgente: `{payload.get('source_verified_facts_preview', '')}`",
        f"- Policy: `{payload.get('apply_policy', '')}`",
        "",
    ]
    patches = list_items(payload.get("profile_patches"))
    if not patches:
        lines.extend(["_Nessuna patch preview generata._", ""])
    for patch in patches:
        lines.extend(["## Profilo", "", f"- Profile ID: `{patch.get('profile_id', '')}`", ""])
        operations = list_items(patch.get("operations"))
        if not operations:
            lines.extend(["Nessuna operazione.", ""])
            continue
        for operation in operations:
            lines.extend(
                [
                    f"### {operation.get('path', '')}",
                    "",
                    f"- Op: `{operation.get('op', '')}`",
                    f"- Valore: {operation.get('value', '')}",
                    f"- VerifiedFactPreview: `{operation.get('verified_fact_preview_id', '')}`",
                    f"- Documento: `{operation.get('source_document_id', '')}`",
                    f"- Decisione: `{operation.get('source_decision_record_id', '')}`",
                    f"- Revisore: `{operation.get('reviewer', '')}`",
                    f"- Data review: `{operation.get('reviewed_at', '')}`",
                    "",
                ]
            )
    skipped = list_items(payload.get("skipped_facts"))
    lines.extend(["## Fatti saltati", ""])
    if not skipped:
        lines.extend(["_Nessun fatto saltato._", ""])
    for item in skipped:
        lines.append(f"- `{item.get('fact_id', '')}`: {item.get('reason', '')}")
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Output automatico preview-only.",
            "- Non modifica profili JSON-LD.",
            "- Non scrive nello evidence store.",
            "- Non applica ProfilePatch.",
            "",
        ]
    )
    return "\n".join(lines)


def _selected_facts(preview: dict[str, Any], *, profile_filter: list[str]) -> list[dict[str, Any]]:
    if preview.get("type") == "verified_facts_preview" and preview.get("status") == "skipped":
        return []
    if str(preview.get("@type", "")) != "VerifiedFactsPreview":
        return []
    facts = []
    for fact in list_items(preview.get("facts")):
        if str(fact.get("@type", "")) != "VerifiedFactPreview":
            continue
        if profile_filter and str(fact.get("profile_id", "")).strip() not in profile_filter:
            continue
        facts.append(fact)
    return facts


def _operation_from_fact(fact: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    for key in ("fact_id", "profile_id", "field", "value", "source_document_id", "source_decision_record_id"):
        if not str(fact.get(key, "")).strip():
            return None, f"campo_mancante:{key}"
    field = str(fact.get("field", "")).strip()
    path = UPDATE_PATHS.get(field) or f"/verified_facts/{field}"
    value = str(fact.get("value", "")).strip()
    return (
        {
            "op": "add" if path.endswith("/-") or "/verified_facts/" in path else "set",
            "path": path,
            "value": value,
            "verified_fact_preview_id": str(fact.get("fact_id", "")).strip(),
            "source_document_id": str(fact.get("source_document_id", "")).strip(),
            "source_run_id": str(fact.get("source_run_id", "")).strip(),
            "source_decision_record_id": str(fact.get("source_decision_record_id", "")).strip(),
            "source_item_id": str(fact.get("source_item_id", "")).strip(),
            "item_id": str(fact.get("item_id", "")).strip(),
            "reviewer": str(fact.get("reviewer", "")).strip(),
            "reviewed_at": str(fact.get("reviewed_at", "")).strip(),
            "provenance": list_strings(fact.get("provenance")),
            "operation_id": _operation_id(fact, path=path),
        },
        "",
    )


def _skipped_fact(fact: dict[str, Any], reason: str) -> dict[str, str]:
    return {
        "fact_id": str(fact.get("fact_id", "")),
        "profile_id": str(fact.get("profile_id", "")),
        "field": str(fact.get("field", "")),
        "reason": reason,
    }


def _operation_id(fact: dict[str, Any], *, path: str) -> str:
    parts = {
        "fact_id": fact.get("fact_id", ""),
        "profile_id": fact.get("profile_id", ""),
        "path": path,
        "value": fact.get("value", ""),
        "source_decision_record_id": fact.get("source_decision_record_id", ""),
    }
    digest = hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"profile-patch-preview-operation:{digest}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera ProfilePatch preview da verified_facts.preview.json.")
    parser.add_argument("--verified-facts-preview-json", required=True)
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    try:
        payload = build_verified_facts_profile_patch_preview(
            verified_facts_preview_json=Path(args.verified_facts_preview_json),
            profile_id=args.profile_id,
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            limit=args.limit,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc))
        return 2
    print(f"ProfilePatch preview: {args.output_md}")
    print(f"Patch profilo: {payload['patch_count']}")
    print(f"Operazioni: {payload['operation_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
