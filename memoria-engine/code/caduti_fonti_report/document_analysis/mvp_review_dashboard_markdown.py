from __future__ import annotations

from typing import Any

from .preview_payloads import dict_object, list_items, list_strings, yaml_value


def render_mvp_review_dashboard_markdown(dashboard: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_review_dashboard",
        f"review_status: {yaml_value(dashboard.get('review_status', 'unreviewed'))}",
        f"publication_status: {yaml_value(dashboard.get('publication_status', 'not_publishable_without_human_review'))}",
        "---",
        "",
        "# Review dashboard MVP",
        "",
        "Vista preview-only per aprire la sessione storica senza leggere prima i JSON tecnici.",
        "",
        "## Sintesi",
        "",
        f"- Profili in dashboard: `{dashboard.get('profile_count', 0)}`",
        f"- Item review queue: `{dashboard.get('review_queue_item_count', 0)}`",
        f"- Decisioni pending: `{dashboard.get('pending_decision_count', 0)}`",
        f"- Decisioni accettate: `{dashboard.get('accepted_decision_count', 0)}`",
        f"- Decisioni invalide: `{dashboard.get('invalid_decision_count', 0)}`",
        f"- Stato decisioni: `{dashboard.get('decision_review_status', '')}`",
        f"- Stato sessione: `{dashboard.get('decision_session_status', '')}`",
        f"- Profili nel focus review: `{dashboard.get('focus_profile_count', 0)}`",
        f"- Item nel focus review: `{dashboard.get('focus_item_count', 0)}`",
        "",
        "## File di lavoro",
        "",
    ]
    for item in list_items(dashboard.get("work_files")):
        lines.append(f"- {item.get('label', '')}: `{item.get('path', '')}`")

    lines.extend(["", "## Oggetti da decidere", ""])
    subject_counts = _dict_int_counts(dashboard.get("subject_kind_counts"))
    if subject_counts:
        lines.extend(["| Oggetto | Item |", "|---|---:|"])
        for subject, count in subject_counts.items():
            lines.append(f"| `{subject}` | {count} |")
    else:
        lines.append("_Nessun item classificato per oggetto._")

    lines.extend(["", "## Profili", ""])
    profiles = list_items(dashboard.get("profiles"))
    if profiles:
        lines.extend(
            [
                "| Profilo | Stato scheda | Stato review | Item | Pending | Accettate | Invalide | Prossima azione |",
                "|---|---|---|---:|---:|---:|---:|---|",
            ]
        )
        for profile in profiles:
            lines.append(
                "| "
                f"{profile.get('canonical_name', '')} "
                f"| `{profile.get('pilot_card_status', '')}` "
                f"| `{profile.get('model_card_review_status', '')}` "
                f"| {profile.get('review_item_count', 0)} "
                f"| {profile.get('pending_decision_count', 0)} "
                f"| {profile.get('accepted_decision_count', 0)} "
                f"| {profile.get('invalid_decision_count', 0)} "
                f"| {profile.get('next_action', '')} |"
            )
    else:
        lines.append("_Nessun profilo nella dashboard._")

    lines.extend(["", "## Focus operativo", ""])
    if profiles:
        for profile in profiles:
            focus_items = list_items(profile.get("review_focus_items"))[:5]
            if not focus_items:
                continue
            lines.extend(["", f"### {profile.get('canonical_name', '')}", ""])
            lines.extend(
                [
                    "| Item | Oggetto | Stato | Azione corrente | Documento | Domanda |",
                    "|---|---|---|---|---|---|",
                ]
            )
            for item in focus_items:
                lines.append(
                    "| "
                    f"`{item.get('item_id', '')}` "
                    f"| `{item.get('subject_kind', '')}` "
                    f"| `{item.get('decision_status', '')}` "
                    f"| `{item.get('selected_action', '')}` "
                    f"| `{item.get('source_document_id', '')}` "
                    f"| {item.get('question', '')} |"
                )
    else:
        lines.append("_Nessun focus operativo disponibile._")

    ledger_coverage = dict_object(dashboard.get("ledger_evidence_store_coverage"))
    if ledger_coverage.get("enabled"):
        lines.extend(
            [
                "",
                "## Copertura evidence store",
                "",
                "Copertura diagnostica read-only dal ledger: non valida fatti e non modifica profili.",
                "",
                f"- Record store: `{ledger_coverage.get('record_count', 0)}`",
                f"- Profili con record: `{ledger_coverage.get('profiles_with_records_count', 0)}`",
                f"- Record non scopiati: `{ledger_coverage.get('unscoped_record_count', 0)}`",
            ]
        )

    preview_summary = dict_object(dashboard.get("verified_facts_preview"))
    if preview_summary:
        lines.extend(["", "## Verified facts preview", ""])
        if not preview_summary.get("available"):
            lines.append(
                f"- Stato: `{preview_summary.get('status', 'missing')}` - {preview_summary.get('note', '')}"
            )
        else:
            lines.extend(
                [
                    "Sintesi preview-only da decisioni storiche approvate; non e' dataset canonico.",
                    "",
                    f"- Stato: `{preview_summary.get('status', '')}`",
                    f"- Fatti preview: `{preview_summary.get('fact_count', 0)}`",
                    f"- Decisioni escluse: `{preview_summary.get('excluded_decision_count', 0)}`",
                ]
            )
            facts = list_items(preview_summary.get("facts"))
            if facts:
                lines.extend(["", "| Profilo | Campo | Valore | Documento | Decisione |", "|---|---|---|---|---|"])
                for fact in facts:
                    lines.append(
                        "| "
                        f"`{fact.get('profile_id', '')}` "
                        f"| `{fact.get('field', '')}` "
                        f"| {fact.get('value', '')} "
                        f"| `{fact.get('source_document_id', '')}` "
                        f"| `{fact.get('source_decision_record_id', '')}` |"
                    )

    profile_patch_summary = dict_object(dashboard.get("profile_patch_preview"))
    if profile_patch_summary:
        lines.extend(["", "## ProfilePatch preview", ""])
        if not profile_patch_summary.get("available"):
            lines.append(
                f"- Stato: `{profile_patch_summary.get('status', 'missing')}` - {profile_patch_summary.get('note', '')}"
            )
        else:
            lines.extend(
                [
                    "Sintesi preview-only delle patch profilo proposte; non applica profili canonici.",
                    "",
                    f"- Stato: `{profile_patch_summary.get('status', '')}`",
                    f"- ProfilePatch: `{profile_patch_summary.get('patch_count', 0)}`",
                    f"- Operazioni: `{profile_patch_summary.get('operation_count', 0)}`",
                    f"- Fatti saltati: `{profile_patch_summary.get('skipped_fact_count', 0)}`",
                    f"- Profili: `{', '.join(list_strings(profile_patch_summary.get('profile_ids')))}`",
                ]
            )

    sandbox_summary = dict_object(dashboard.get("profile_patch_sandbox"))
    if sandbox_summary:
        lines.extend(["", "## ProfilePatch sandbox", ""])
        if not sandbox_summary.get("available"):
            lines.append(
                f"- Stato: `{sandbox_summary.get('status', 'missing')}` - {sandbox_summary.get('note', '')}"
            )
        else:
            lines.extend(
                [
                    "Sintesi sandbox: profili derivati e audit, senza scrittura sui profili canonici.",
                    "",
                    f"- Stato: `{sandbox_summary.get('status', '')}`",
                    f"- Directory: `{sandbox_summary.get('source_dir', '')}`",
                    f"- Profili derivati: `{sandbox_summary.get('sandbox_profile_count', 0)}`",
                    f"- Audit: `{sandbox_summary.get('audit_count', 0)}`",
                    f"- Promotion record: `{sandbox_summary.get('promotion_count', 0)}`",
                    f"- Profili: `{', '.join(list_strings(sandbox_summary.get('profile_ids')))}`",
                ]
            )

    warnings = list_strings(dashboard.get("warnings"))
    if warnings:
        lines.extend(["", "## Warning", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Dashboard generata automaticamente come derivato preview-only.",
            "- Le decisioni vuote restano `pending`.",
            "- Non applica patch, non crea fatti verificati e non modifica profili JSON-LD.",
            "- Non rende pubblicabili schede o claim candidati.",
            "",
        ]
    )
    return "\n".join(lines)


def _dict_int_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _int_value(count) for key, count in sorted(value.items())}


def _int_value(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
