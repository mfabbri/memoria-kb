from __future__ import annotations

from typing import Any


def render_mvp_review_session_markdown(session: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_review_session",
        f"review_status: {_yaml_value(session.get('review_status', 'unreviewed'))}",
        f"publication_status: {_yaml_value(session.get('publication_status', 'not_publishable_without_curator_review'))}",
        "---",
        "",
        "# Sessione revisione MVP",
        "",
        "Output preview-only per organizzare una sessione storica/curatoriale sulle schede pilota.",
        "",
        "## Sintesi",
        "",
        f"- Profili in sessione: `{session.get('profile_count', 0)}`",
        f"- Item review queue: `{session.get('review_queue_item_count', 0)}`",
        f"- Stato decisioni: `{session.get('decision_review_status', '')}`",
        f"- Stato sessione decisioni: `{session.get('decision_session_status', '')}`",
        f"- Schede candidate pubblicazione: `{session.get('publication_candidate_count', 0)}`",
        f"- Schede pronte per review: `{session.get('ready_for_review_count', 0)}`",
        f"- Schede con OCR da migliorare: `{session.get('needs_better_ocr_count', 0)}`",
        f"- Schede con segnale documentale insufficiente: `{session.get('needs_document_signal_count', 0)}`",
        "",
        "## File di lavoro",
        "",
        f"- Summary MVP: `{session.get('source_summary_json', '')}`",
        f"- Digest schede: `{session.get('source_digest_json', '')}`",
        f"- Review queue: `{session.get('source_review_queue_json', '')}`",
        f"- Riepilogo decisioni: `{session.get('source_review_decisions_summary_json', '')}`",
        f"- Ledger consolidato: `{session.get('source_consolidated_ledger_json', '')}`",
        "",
        "## Profili",
        "",
    ]
    ledger_coverage = _dict_object(session.get("ledger_evidence_store_coverage"))
    if ledger_coverage.get("enabled"):
        lines.extend(
            [
                "## Copertura ledger / evidence store",
                "",
                "Vista diagnostica derivata dal ledger: aiuta a leggere la tracciabilita' nello store generale, non valida fatti storici.",
                "",
                f"- Record store letti dal ledger: `{ledger_coverage.get('record_count', 0)}`",
                f"- Profili con record nello store: `{ledger_coverage.get('profiles_with_records_count', 0)}`",
                f"- Record non scopiati: `{ledger_coverage.get('unscoped_record_count', 0)}`",
                f"- Workflow non scopiati: `{ledger_coverage.get('workflow_unscoped_record_count', 0)}`",
                "",
            ]
        )
        by_kind = _dict_object(ledger_coverage.get("by_kind"))
        if by_kind:
            lines.extend(
                [
                    "| Tipo record | Totale | Con soggetto | Con documento | Workflow non scopiati |",
                    "|---|---:|---:|---:|---:|",
                ]
            )
            for kind, item in sorted(by_kind.items()):
                item_dict = _dict_object(item)
                lines.append(
                    "| "
                    f"{kind} "
                    f"| {item_dict.get('total', 0)} "
                    f"| {item_dict.get('with_subject', 0)} "
                    f"| {item_dict.get('with_source_document', 0)} "
                    f"| {item_dict.get('workflow_unscoped', 0)} |"
                )
            lines.append("")
    profiles = _list_items(session.get("profiles"))
    if profiles:
        lines.extend(
            [
                "| Profilo | Stato scheda | Documenti | Link | Claim | Piste | Item | Prossima azione |",
                "|---|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for profile in profiles:
            lines.append(
                "| "
                f"{profile.get('canonical_name', '')} "
                f"| `{profile.get('pilot_card_status', '')}` "
                f"| {profile.get('document_count', 0)} "
                f"| {profile.get('candidate_document_person_link_count', 0)} "
                f"| {profile.get('candidate_evidence_claim_count', 0)} "
                f"| {profile.get('reviewable_document_signal_count', 0)} "
                f"| {profile.get('review_item_count', 0)} "
                f"| {profile.get('next_action', '')} |"
            )
    else:
        lines.append("_Nessun profilo nella sessione._")

    lines.extend(["", "## Schede modello in revisione", ""])
    if profiles:
        lines.extend(
            [
                "| Profilo | Stato review | Approvate | Respinte | Incerte | Pending | Invalidi | Pubblicabilita' |",
                "|---|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for profile in profiles:
            lines.append(
                "| "
                f"{profile.get('canonical_name', '')} "
                f"| `{profile.get('model_card_review_status', '')}` "
                f"| {profile.get('approved_decision_count', 0)} "
                f"| {profile.get('rejected_decision_count', 0)} "
                f"| {profile.get('uncertain_decision_count', 0)} "
                f"| {profile.get('pending_decision_count', 0)} "
                f"| {profile.get('invalid_decision_count', 0)} "
                f"| `{profile.get('publication_status', '')}` |"
            )
    else:
        lines.append("_Nessuna scheda modello revisionabile nella sessione._")

    lines.extend(["", "## Percorso review schede modello", ""])
    review_focus = _dict_object(session.get("review_focus"))
    focus_profiles = _list_items(review_focus.get("profiles"))
    if focus_profiles:
        lines.append(
            "Vista operativa preview-only: mostra gli item da compilare, non propone decisioni storiche."
        )
        for focus_profile in focus_profiles:
            lines.extend(["", f"### {focus_profile.get('canonical_name', '')}", ""])
            lines.extend(
                [
                    "| Item | Tipo | Oggetto | Stato | Azione corrente | Azioni ammesse | Documento | Domanda |",
                    "|---|---|---|---|---|---|---|---|",
                ]
            )
            for item in _list_items(focus_profile.get("items")):
                allowed = ", ".join(_list_strings(item.get("allowed_decisions"))) or "pending"
                document_parts = [f"`{item.get('source_document_id', '')}`"]
                raw_file = str(item.get("raw_file", "")).strip()
                metadata_file = str(item.get("metadata_file", "")).strip()
                document_reference_note = str(item.get("document_reference_note", "")).strip()
                if raw_file:
                    document_parts.append(f"file `{raw_file}`")
                if metadata_file:
                    document_parts.append(f"metadata `{metadata_file}`")
                if document_reference_note:
                    document_parts.append(document_reference_note)
                lines.append(
                    "| "
                    f"`{item.get('item_id', '')}` "
                    f"| `{item.get('item_type', '')}` "
                    f"| `{item.get('subject_kind', '')}` "
                    f"| `{item.get('decision_status', '')}` "
                    f"| `{item.get('selected_action', '')}` "
                    f"| {allowed} "
                    f"| {'<br>'.join(document_parts)} "
                    f"| {item.get('question', '')} |"
                )
    else:
        lines.append("_Nessun percorso review guidato disponibile._")

    lines.extend(["", "## Template decisioni focus", ""])
    focus_template = _dict_object(session.get("review_focus_decisions_template"))
    focus_decisions = _list_items(focus_template.get("decisions"))
    if focus_decisions:
        lines.extend(
            [
                "Sottoinsieme compilabile degli item focus. Copiare le decisioni in un file JSON compilato e validarlo con il riepilogo decisioni; gli item non inclusi restano pending.",
                "",
                "| Item | Tipo | Oggetto | Azione | Azioni ammesse | Revisore | Note |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for decision in focus_decisions:
            allowed = ", ".join(_list_strings(decision.get("allowed_decisions"))) or "pending"
            lines.append(
                "| "
                f"`{decision.get('item_id', '')}` "
                f"| `{decision.get('item_type', '')}` "
                f"| `{decision.get('subject_kind', '')}` "
                f"| `{decision.get('selected_action', '')}` "
                f"| {allowed} "
                f"| `{decision.get('reviewer', '')}` "
                f"| {decision.get('notes', '')} |"
            )
    else:
        lines.append("_Nessun template decisioni focus disponibile._")

    for profile in profiles:
        lines.extend(["", f"## {profile.get('canonical_name') or profile.get('profile_id', '')}", ""])
        lines.append(f"- ProfileId: `{profile.get('profile_id', '')}`")
        lines.append(f"- Stato scheda: `{profile.get('pilot_card_status', '')}`")
        lines.append(f"- Stato scheda modello in revisione: `{profile.get('model_card_review_status', '')}`")
        lines.append(f"- Readiness automatica: `{profile.get('readiness_status', '')}`")
        lines.append(f"- Stato sessione storici: `{profile.get('review_session_status', '')}`")
        lines.append(f"- Decisioni approvate: `{profile.get('approved_decision_count', 0)}`")
        lines.append(f"- Decisioni respinte: `{profile.get('rejected_decision_count', 0)}`")
        lines.append(f"- Decisioni incerte/conflitti: `{profile.get('uncertain_decision_count', 0)}`")
        lines.append(f"- Decisioni pending: `{profile.get('pending_decision_count', 0)}`")
        lines.append(f"- Decisioni invalide: `{profile.get('invalid_decision_count', 0)}`")
        coverage = _dict_object(profile.get("ledger_evidence_store_coverage"))
        if coverage:
            lines.append(f"- Record store nel ledger: `{coverage.get('record_count', 0)}`")
            lines.append(f"- Documenti distinti nello store: `{coverage.get('source_document_count', 0)}`")
            by_kind = _dict_int_counts(coverage.get("by_kind"))
            if by_kind:
                lines.append("- Tipi record store: " + ", ".join(f"`{kind}` `{count}`" for kind, count in sorted(by_kind.items())))
            by_status = _dict_int_counts(coverage.get("by_review_status"))
            if by_status:
                lines.append("- Stati review store: " + ", ".join(f"`{status}` `{count}`" for status, count in sorted(by_status.items())))
        lines.append(f"- Scheda candidata: `{profile.get('candidate_card_path', '')}`")
        lines.append(f"- Vincolo pubblicazione: {profile.get('publication_constraint', '')}")
        lines.append(f"- Prossima azione: {profile.get('next_action', '')}")
        items = _list_items(profile.get("priority_review_items"))
        lines.extend(["", "Item prioritari:"])
        if items:
            for item in items:
                lines.append(
                    f"- `{item.get('item_id', '')}` `{item.get('item_type', '')}`: {item.get('question', '')}"
                )
        else:
            lines.append("- Nessun item di review associato al profilo.")

    warnings = _list_strings(session.get("warnings"))
    if warnings:
        lines.extend(["", "## Warning", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- La sessione e' un derivato operativo preview-only.",
            "- Non applica decisioni e non crea fatti verificati.",
            "- Non modifica profili JSON-LD canonici, raw archive, cache o documenti originali.",
            "- Obsidian resta un layer editoriale, non la fonte canonica.",
            "- La review session consolida la lettura delle schede modello: non genera mvp_model_cards_reviewed.md/json.",
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
    return [str(item) for item in value if str(item)]


def _dict_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value


def _dict_int_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for key, item in value.items():
        try:
            result[str(key)] = int(item)
        except (TypeError, ValueError):
            result[str(key)] = 0
    return result


def _yaml_value(value: object) -> str:
    return '"' + str(value).replace('"', '\\"') + '"'
