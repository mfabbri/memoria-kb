from __future__ import annotations

from typing import Any

from .preview_payloads import dict_object, list_items, list_strings, yaml_value


CONTRACT_VERSION = "memoria_mvp_demo.v1"


def render_mvp_demo_reconciliation_markdown(payload: dict[str, Any]) -> str:
    reconciliation = dict_object(payload.get("reconciliation"))
    rows = list_items(reconciliation.get("rows"))
    lines = [
        "---",
        "type: mvp_demo_reconciliation_table",
        f"contract_version: {yaml_value(payload.get('contract_version', CONTRACT_VERSION))}",
        f"run_id: {yaml_value(payload.get('run_id', ''))}",
        "preview_only: true",
        f"publication_status: {yaml_value(payload.get('publication_status', 'not_publishable_without_human_review'))}",
        "---",
        "",
        "# MVP demo reconciliation table",
        "",
        "Tabella preview-only: mostra claim, fonte e compatibilita' senza creare verified facts canonici e senza applicare ProfilePatch.",
        "",
        "## Sintesi",
        "",
        f"- Run: `{payload.get('run_id', '')}`",
        f"- Profili principali: `{', '.join(list_strings(payload.get('primary_profile_ids')))}`",
        f"- Profili contrasto: `{', '.join(list_strings(payload.get('contrast_profile_ids')))}`",
        f"- Righe: `{len(rows)}`",
        f"- Famiglie fonte: `{', '.join(list_strings(payload.get('source_families')))}`",
        f"- Readiness: `{dict_object(payload.get('readiness')).get('status', 'unknown')}`",
        "",
    ]
    readiness = dict_object(payload.get("readiness"))
    errors = list_strings(readiness.get("errors"))
    warnings = list_strings(readiness.get("warnings"))
    if errors or warnings:
        lines.extend(["## Readiness", ""])
        for error in errors:
            lines.append(f"- ERROR: {error}")
        for warning in warnings:
            lines.append(f"- WARNING: {warning}")
        next_actions = list_strings(readiness.get("next_actions"))
        if next_actions:
            lines.append("")
            lines.append("Azioni successive:")
            for action in next_actions:
                lines.append(f"- {action}")
        _append_readiness_tables(lines=lines, readiness=readiness)
        lines.append("")
    lines.extend(["## Riconciliazione", ""])
    if not rows:
        lines.append("_Nessun claim selezionato nel ledger._")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Profilo | Campo | Valore | Documento | Fonte | Metodo | Review | Compatibilita' |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(row.get("profile_id")),
                    _md_cell(row.get("field")),
                    _md_cell(row.get("value")),
                    _md_cell(row.get("source_document_id")),
                    _md_cell(row.get("source_family")),
                    _md_cell(row.get("extraction_method")),
                    _md_cell(row.get("review_status")),
                    _md_cell(row.get("compatibility")),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _append_readiness_tables(*, lines: list[str], readiness: dict[str, Any]) -> None:
    document_diagnostics = list_items(readiness.get("document_diagnostics"))
    if document_diagnostics:
        lines.extend(
            [
                "",
                "Famiglie T29:",
                "",
                "| Famiglia | Stato | Blocco | Documenti selezionati | Documenti coperti | Documenti mancanti |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in list_items(readiness.get("source_family_diagnostics")):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(item.get("source_family")),
                        _md_cell(item.get("coverage_status")),
                        _md_cell(item.get("blocking_reason")),
                        _md_cell(item.get("selected_document_count")),
                        _md_cell(item.get("covered_document_count")),
                        _md_cell(item.get("missing_document_count")),
                    ]
                )
                + " |"
            )
        lines.extend(
            [
                "",
                "Documenti T29:",
                "",
                "| Documento | Famiglia | Riconciliazione | Profilo demo | Claim | Blocco |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in document_diagnostics:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(item.get("source_document_id")),
                        _md_cell(item.get("source_family")),
                        _md_cell(item.get("reconciliation_status")),
                        _md_cell(item.get("profile_scope_status")),
                        _md_cell(item.get("candidate_claim_status")),
                        _md_cell(item.get("blocking_reason")),
                    ]
                )
                + " |"
            )
    alignment_plan = list_items(readiness.get("alignment_plan"))
    if alignment_plan:
        lines.extend(
            [
                "",
                "Piano riallineamento preview:",
                "",
                "| Passo | Azione | Documento | Famiglia | Motivo |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for item in alignment_plan:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(item.get("step")),
                        _md_cell(item.get("action")),
                        _md_cell(item.get("source_document_id")),
                        _md_cell(item.get("source_family")),
                        _md_cell(item.get("reason")),
                    ]
                )
                + " |"
            )


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value).replace("\n", " ").strip()
    return text.replace("|", "\\|")
