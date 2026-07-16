from __future__ import annotations

from typing import Any

from .preview_payloads import list_items, list_strings, yaml_value


def render_mvp_historical_review_targets_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_historical_review_targets",
        f"review_status: {yaml_value(payload.get('review_status', 'pending_historian_review'))}",
        f"publication_status: {yaml_value(payload.get('publication_status', 'not_publishable_without_human_review'))}",
        "preview_only: true",
        "---",
        "",
        "# Target storici revisionabili MVP",
        "",
        "Lista corta di oggetti storici da leggere in sessione di revisione. Non applica decisioni e non crea fatti verificati.",
        "",
        "## Sintesi",
        "",
        f"- Target: `{payload.get('target_count', 0)}`",
        f"- Modalita' sorgente: `{payload.get('source_mode', '')}`",
        f"- Review queue: `{payload.get('source_review_queue_json', '')}`",
        f"- Evidence DB: `{payload.get('source_evidence_db', '')}`",
        f"- Run store: `{', '.join(list_strings(payload.get('source_run_ids')))}`",
        f"- Review session: `{payload.get('source_review_session_json', '')}`",
        f"- Stato revisione: `{payload.get('review_status', '')}`",
        f"- Stato pubblicazione: `{payload.get('publication_status', '')}`",
        "",
        "## Target",
        "",
    ]
    targets = list_items(payload.get("targets"))
    if not targets:
        lines.append("_Nessun target storico revisionabile generato._")
    for target in targets:
        lines.extend(
            [
                f"### {target.get('target_id', '')}",
                "",
                f"- Profilo: `{target.get('profile_id', '')}` {target.get('canonical_name', '')}",
                f"- Documento/fonte: `{target.get('source_document_id', '')}`",
                f"- Tipo item: `{target.get('item_type', '')}` / `{target.get('subject_kind', '')}`",
                f"- Stato: `{target.get('review_status', '')}`",
                f"- Decisione corrente: `{target.get('current_selected_action', '')}` / `{target.get('current_decision_status', '')}`",
                f"- Azioni ammesse: {', '.join(list_strings(target.get('allowed_decisions')))}",
                f"- Domanda per storico: {target.get('historian_question', '')}",
                "",
            ]
        )
        context = str(target.get("context", "")).strip()
        if context:
            lines.extend(["> " + context, ""])
        provenance = list_strings(target.get("provenance"))
        if provenance:
            lines.append("Provenance:")
            lines.extend(f"- {item}" for item in provenance)
            lines.append("")
        lines.extend(
            [
                "Vincolo:",
                f"- {target.get('safety_note', '')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Vincoli",
            "",
            "- Output automatico preview-only.",
            "- Le azioni ammesse non modificano profili o fatti verificati.",
            "- Usare i converter/summary esistenti per produrre decisioni JSON compilate.",
            "",
        ]
    )
    return "\n".join(lines)
