from __future__ import annotations

from typing import Any


def render_mvp_review_decisions_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Decisioni review queue MVP",
        "",
        f"- Review queue: `{summary.get('source_review_queue_json', '')}`",
        f"- Decisioni: `{summary.get('source_decisions_json', '')}`",
        f"- Stato revisione: `{summary.get('review_status', '')}`",
        f"- Stato pubblicazione: `{summary.get('publication_status', '')}`",
        f"- Item: `{summary.get('item_count', 0)}`",
        f"- Accettati: `{summary.get('accepted_count', 0)}`",
        f"- Pending: `{summary.get('pending_count', 0)}`",
        f"- Invalidi: `{summary.get('invalid_count', 0)}`",
        "",
        "## Copertura file decisioni",
        "",
    ]
    decision_file_coverage = _dict_object(summary.get("decision_file_coverage"))
    if decision_file_coverage:
        lines.extend(
            [
                f"- Item in coda: `{decision_file_coverage.get('queue_item_count', 0)}`",
                f"- Decisioni fornite: `{decision_file_coverage.get('provided_decision_count', 0)}`",
                f"- Decisioni con item noto: `{decision_file_coverage.get('provided_known_item_count', 0)}`",
                f"- Decisioni con item sconosciuto: `{decision_file_coverage.get('provided_unknown_item_count', 0)}`",
                f"- Azioni selezionate: `{decision_file_coverage.get('selected_action_count', 0)}`",
                f"- Decisioni vuote: `{decision_file_coverage.get('blank_action_count', 0)}`",
                f"- Item di coda senza decisione fornita: `{decision_file_coverage.get('queue_items_without_provided_decision_count', 0)}`",
            ]
        )
    else:
        lines.append("_Copertura non disponibile._")
    lines.extend(
        [
            "",
            "## Sessione storici",
            "",
        ]
    )
    review_session = _dict_object(summary.get("review_session"))
    lines.extend(
        [
            f"- Stato sessione: `{review_session.get('session_status', 'not_started')}`",
            f"- Profili in sessione: `{review_session.get('profile_count', 0)}`",
            f"- Profili pronti per revisione curatoriale: `{review_session.get('ready_for_curator_review_count', 0)}`",
            "",
            "### Stato per profilo",
            "",
        ]
    )
    profile_sessions = _list_items(review_session.get("profiles"))
    if profile_sessions:
        lines.extend(
            [
                "| Profilo | Item | Accettati | Pending | Invalidi | Stato sessione |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for profile in profile_sessions:
            lines.append(
                "| "
                f"`{profile.get('profile_id', '')}` "
                f"| {profile.get('item_count', 0)} "
                f"| {profile.get('accepted_count', 0)} "
                f"| {profile.get('pending_count', 0)} "
                f"| {profile.get('invalid_count', 0)} "
                f"| `{profile.get('session_status', 'not_started')}` |"
            )
    else:
        lines.append("_Nessun profilo nella sessione._")
    lines.extend(
        [
            "",
            "## Conteggi per azione",
            "",
        ]
    )
    counts_by_action = summary.get("counts_by_action")
    if isinstance(counts_by_action, dict) and counts_by_action:
        for action, count in sorted(counts_by_action.items()):
            lines.append(f"- `{action}`: {count}")
    else:
        lines.append("_Nessuna azione registrata._")
    lines.extend(["", "## Conteggi per oggetto", ""])
    counts_by_subject_kind = summary.get("counts_by_subject_kind")
    if isinstance(counts_by_subject_kind, dict) and counts_by_subject_kind:
        for subject_kind, count in sorted(counts_by_subject_kind.items()):
            lines.append(f"- `{subject_kind}`: {count}")
    else:
        lines.append("_Nessun oggetto registrato._")
    lines.extend(["", "## Errori di validazione", ""])
    errors = _list_items(summary.get("validation_errors"))
    if errors:
        for error in errors:
            lines.append(f"- `{error.get('item_id', '')}`: {error.get('message', '')}")
    else:
        lines.append("_Nessun errore di validazione._")
    lines.extend(["", "## Decisioni", ""])
    decisions = _list_items(summary.get("decisions"))
    if not decisions:
        lines.append("_Nessuna decisione riepilogata._")
    for decision in decisions:
        lines.extend(
            [
                f"### {decision.get('item_id', '')}",
                "",
                f"- Tipo: `{decision.get('item_type', '')}`",
                f"- Oggetto: `{decision.get('subject_kind', '')}`",
                f"- Profilo: `{decision.get('profile_id', '')}`",
                f"- Documento: `{decision.get('source_document_id', '')}`",
                f"- Item sorgente: `{decision.get('source_item_id', '')}`",
                f"- Domanda: {decision.get('question', '')}",
                f"- Azione: `{decision.get('selected_action', '')}`",
                f"- Azioni ammesse: {', '.join(_list_strings(decision.get('allowed_decisions')))}",
                f"- Stato decisione: `{decision.get('decision_status', '')}`",
                f"- Revisore: `{decision.get('reviewer', '')}`",
                f"- Data revisione: `{decision.get('reviewed_at', '')}`",
                f"- Note: {decision.get('notes', '')}",
                "",
            ]
        )
        candidate = _dict_object(decision.get("candidate"))
        if candidate:
            lines.extend(
                [
                    f"- Campo candidato: `{candidate.get('field', '')}`",
                    f"- Valore candidato: {candidate.get('value', '')}",
                    "",
                ]
            )
        context = str(decision.get("context", "")).strip()
        if context:
            lines.extend(["> " + context, ""])
        error = str(decision.get("error", "")).strip()
        if error:
            lines.extend([f"Errore: {error}", ""])
    lines.extend(
        [
            "## Vincoli",
            "",
            "- Questo report non applica patch.",
            "- Questo report non crea fatti verificati.",
            "- Le decisioni vanno applicate solo con workflow espliciti futuri.",
            "",
        ]
    )
    return "\n".join(lines)


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
