from __future__ import annotations

from typing import Any


def render_go_no_go_markdown(checklist: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_go_no_go_checklist",
        f"review_status: {_yaml_value(checklist.get('review_status', 'unreviewed'))}",
        f"publication_status: {_yaml_value(checklist.get('publication_status', 'not_publishable_without_human_review'))}",
        f"overall_status: {_yaml_value(checklist.get('overall_status', ''))}",
        "---",
        "",
        "# Go/no-go MVP finanziamento",
        "",
        "Checklist preview-only: misura se il pacchetto e' presentabile come demo finanziabile, non se le schede sono pubblicabili.",
        "",
        "## Esito",
        "",
        f"- Stato complessivo: `{checklist.get('overall_status', '')}`",
        f"- Quality gate mirato: `{checklist.get('quality_gate_status', '')}`",
        f"- Descriptor demo: `{checklist.get('demo_descriptor_json', '')}`",
        f"- Stato descriptor: `{checklist.get('demo_status', '')}`",
        f"- Profili demo: `{checklist.get('profile_count', 0)}`",
        f"- Documenti fonte demo: `{checklist.get('source_document_count', 0)}`",
        f"- Famiglie fonte demo: `{checklist.get('source_family_count', 0)}`",
        f"- Profili ready_for_review: `{checklist.get('ready_profile_count', 0)}`",
        f"- Schede modello: `{checklist.get('model_card_count', 0)}`",
        f"- Item review queue: `{checklist.get('review_queue_item_count', 0)}`",
        f"- Decisioni pending: `{checklist.get('pending_review_count', 0)}`",
        "",
        "## Checklist",
        "",
        "| Voce | Stato | Evidenza | Nota |",
        "|---|---|---|---|",
    ]
    for item in _list_items(checklist.get("checks")):
        lines.append(
            "| "
            f"{item.get('label', '')} "
            f"| `{item.get('status', '')}` "
            f"| `{item.get('evidence', '')}` "
            f"| {item.get('note', '')} |"
        )
    lines.extend(["", "## Prossime azioni", ""])
    lines.extend(f"- {action}" for action in _list_strings(checklist.get("next_actions")))
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Non approva decisioni storiche.",
            "- Non modifica profili JSON-LD.",
            "- Non trasforma claim candidati in fatti.",
            "- Non rende pubblicabile alcuna scheda senza revisione umana.",
            "",
        ]
    )
    return "\n".join(lines)


def render_funding_package_index_markdown(index: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: funding_package_index",
        f"review_status: {_yaml_value(index.get('review_status', 'unreviewed'))}",
        f"publication_status: {_yaml_value(index.get('publication_status', 'not_publishable_without_human_review'))}",
        "---",
        "",
        "# Pacchetto finanziatore Me.Mo.Ri.a",
        "",
        "Pagina di ingresso preview-only per leggere la demo finanziabile senza attraversare i JSON tecnici.",
        "",
        "## Esito rapido",
        "",
        f"- Stato go/no-go: `{index.get('overall_status', '')}`",
        f"- Run: `{index.get('run_dir', '')}`",
        f"- Descriptor demo: `{index.get('demo_descriptor_json', '')}`",
        f"- Profili demo: `{index.get('profile_count', 0)}`",
        f"- Documenti fonte demo: `{index.get('source_document_count', 0)}`",
        f"- Famiglie fonte demo: `{index.get('source_family_count', 0)}`",
        f"- Schede modello: `{index.get('model_card_count', 0)}`",
        f"- Decisioni pending: `{index.get('pending_review_count', 0)}`",
        "",
        "## Aprire in questo ordine",
        "",
    ]
    for number, item in enumerate(_list_items(index.get("reading_order")), start=1):
        lines.append(f"{number}. {item.get('label', '')}: `{item.get('path', '')}`")
    lines.extend(["", "## Materiali", ""])
    lines.extend(["| Materiale | Stato | Percorso |", "|---|---|---|"])
    for item in _list_items(index.get("materials")):
        lines.append(f"| {item.get('label', '')} | `{item.get('status', '')}` | `{item.get('path', '')}` |")
    lines.extend(
        [
            "",
            "## Messaggio chiave",
            "",
            "Me.Mo.Ri.a non promette biografie generate automaticamente: mostra un metodo verificabile per collegare persone, fonti, documenti, evidenze e decisioni di revisione.",
            "",
            "## Vincoli editoriali",
            "",
            "- Tutti gli output automatici restano preview-only, unreviewed o pending.",
            "- Le schede modello sono esempi di dossier di revisione, non biografie pubblicabili.",
            "- Il finanziamento serve a completare revisione, trattamento documentale e confezionamento museale.",
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


def _yaml_value(value: object) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'
