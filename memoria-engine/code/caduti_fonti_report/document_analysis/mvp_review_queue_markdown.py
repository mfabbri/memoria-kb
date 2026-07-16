from __future__ import annotations

from collections import Counter
from typing import Any


def render_mvp_review_queue_markdown(queue: dict[str, Any]) -> str:
    lines = [
        "# Review queue MVP",
        "",
        f"- Source summary: `{queue.get('source_summary_json', '')}`",
        f"- Stato revisione: `{queue.get('review_status', '')}`",
        f"- Stato pubblicazione: `{queue.get('publication_status', '')}`",
        f"- Item: `{queue.get('item_count', 0)}`",
        "",
        "## Conteggi per oggetto",
        "",
    ]
    counts_by_subject = Counter(str(item.get("subject_kind", "")) for item in _list_items(queue.get("items")))
    if counts_by_subject:
        for subject_kind, count in sorted(counts_by_subject.items()):
            lines.append(f"- `{subject_kind}`: {count}")
    else:
        lines.append("_Nessun oggetto di revisione generato._")
    lines.extend(
        [
            "",
            "## Coda",
            "",
        ]
    )
    items = _list_items(queue.get("items"))
    if not items:
        lines.append("_Nessun item di revisione generato._")
    for item in items:
        lines.extend(
            [
                f"### {item.get('item_id', '')}",
                "",
                f"- Tipo: `{item.get('item_type', '')}`",
                f"- Oggetto: `{item.get('subject_kind', '')}`",
                f"- Priorita': `{item.get('priority', '')}`",
                f"- Rischio: `{item.get('risk', '')}`",
                f"- Profilo: `{item.get('profile_id', '')}` {item.get('canonical_name', '')}",
                f"- Documento: `{item.get('source_document_id', '')}`",
                f"- Domanda: {item.get('question', '')}",
                f"- Decisioni ammesse: {', '.join(_list_strings(item.get('allowed_decisions')))}",
                f"- Stato: `{item.get('review_status', '')}`",
                "",
            ]
        )
        raw_file = str(item.get("raw_file", "")).strip()
        metadata_file = str(item.get("metadata_file", "")).strip()
        document_reference_note = str(item.get("document_reference_note", "")).strip()
        if raw_file:
            lines.insert(-1, f"- File sorgente: `{raw_file}`")
        if metadata_file:
            lines.insert(-1, f"- Metadata: `{metadata_file}`")
        if document_reference_note:
            lines.insert(-1, f"- Nota documento: {document_reference_note}")
        context = str(item.get("context", "")).strip()
        if context:
            lines.extend(["> " + context, ""])
        reasons = _list_strings(item.get("reasons"))
        if reasons:
            lines.append("Motivi:")
            lines.extend(f"- {reason}" for reason in reasons)
            lines.append("")

    lines.extend(
        [
            "## Vincoli",
            "",
            "- La queue e' preview-only.",
            "- `confirm` conferma solo l'item in revisione, non crea `verified_facts`.",
            "- `accept_for_search` abilita solo una pista di ricerca, non valida un fatto.",
            "- Le decisioni vanno importate o applicate solo con workflow espliciti futuri.",
            "",
        ]
    )
    return "\n".join(lines)


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
