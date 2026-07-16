from __future__ import annotations

from typing import Any


def render_mvp_consolidated_review_ledger_markdown(ledger: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_consolidated_review_ledger",
        f"review_status: {_yaml_value(ledger.get('review_status', 'unreviewed'))}",
        f"publication_status: {_yaml_value(ledger.get('publication_status', 'not_publishable_without_curator_review'))}",
        "---",
        "",
        "# Consolidated Review Ledger MVP",
        "",
        "Output preview-only: raccoglie segnali da run MVP senza validare fatti storici.",
        "",
        "## Sintesi",
        "",
        f"- Run sorgenti: `{ledger.get('source_run_count', 0)}`",
        f"- Profili consolidati: `{ledger.get('profile_count', 0)}`",
        f"- Documenti collegati: `{ledger.get('document_count', 0)}`",
        f"- Link persona-documento candidati: `{ledger.get('candidate_document_person_link_count', 0)}`",
        f"- Claim candidati: `{ledger.get('candidate_evidence_claim_count', 0)}`",
        f"- Piste documentali: `{ledger.get('reviewable_document_signal_count', 0)}`",
        f"- Modalita' sorgente: `{ledger.get('ledger_source_mode', 'summary_fallback')}`",
        "",
        "## Run sorgenti",
        "",
    ]
    source_runs = _list_items(ledger.get("source_runs"))
    if source_runs:
        for item in source_runs:
            lines.append(f"- `{item.get('run_dir', '')}` da `{item.get('summary_json', '')}`")
    else:
        lines.append("_Nessuna run sorgente._")

    coverage = ledger.get("evidence_store_coverage")
    if isinstance(coverage, dict) and coverage.get("enabled"):
        lines.extend(
            [
                "",
                "## Copertura evidence store",
                "",
                f"- Database: `{coverage.get('db', '')}`",
                f"- Run filtrate: `{', '.join(_list_strings(coverage.get('source_run_ids'))) or 'tutte'}`",
                f"- Record letti: `{coverage.get('record_count', 0)}`",
                f"- Profili con record nello store: `{coverage.get('profiles_with_records_count', 0)}`",
                f"- Record non scopiati: `{coverage.get('unscoped_record_count', 0)}`",
                f"- Workflow non scopiati: `{coverage.get('workflow_unscoped_record_count', 0)}`",
                "",
                "| Tipo record | Totale | Con soggetto | Con documento | Workflow non scopiati |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for kind, item in sorted(_dict_items(coverage.get("by_kind")).items()):
            lines.append(
                "| "
                f"{kind} "
                f"| {item.get('total', 0)} "
                f"| {item.get('with_subject', 0)} "
                f"| {item.get('with_source_document', 0)} "
                f"| {item.get('workflow_unscoped', 0)} |"
            )

    lines.extend(["", "## Profili", ""])
    profiles = _list_items(ledger.get("profiles"))
    if profiles:
        lines.extend(
            [
                "| Profilo | Run | Documenti | Link | Claim | Piste |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for profile in profiles:
            lines.append(
                "| "
                f"{profile.get('canonical_name') or profile.get('profile_id', '')} "
                f"| {len(_list_strings(profile.get('source_runs')))} "
                f"| {profile.get('document_count', 0)} "
                f"| {profile.get('candidate_document_person_link_count', 0)} "
                f"| {profile.get('candidate_evidence_claim_count', 0)} "
                f"| {profile.get('reviewable_document_signal_count', 0)} |"
            )
    else:
        lines.append("_Nessun profilo consolidato._")

    for profile in profiles:
        lines.extend(["", f"## {profile.get('canonical_name') or profile.get('profile_id', '')}", ""])
        lines.append(f"- ProfileId: `{profile.get('profile_id', '')}`")
        lines.append(f"- Run sorgenti: `{', '.join(_list_strings(profile.get('source_runs')))}`")
        lines.extend(["", "Documenti:"])
        documents = _list_items(profile.get("documents"))
        if documents:
            for document in documents[:10]:
                lines.append(f"- `{document.get('source_document_id', '')}` - {document.get('title', '')}")
        else:
            lines.append("- Nessun documento collegato.")
        lines.extend(["", "Claim candidati:"])
        claims = _list_items(profile.get("candidate_evidence_claims"))
        if claims:
            for claim in claims[:10]:
                lines.append(
                    f"- `{claim.get('field', '')}`: {claim.get('value', '')} | "
                    f"documento `{claim.get('source_document_id', '')}` | metodo `{claim.get('extraction_method', '')}`"
                )
        else:
            lines.append("- Nessun claim candidato.")
        lines.extend(["", "Piste documentali:"])
        signals = _list_items(profile.get("reviewable_document_signals"))
        if signals:
            for signal in signals[:10]:
                lines.append(f"- `{signal.get('signal_type', '')}` su `{signal.get('source_document_id', '')}`: {signal.get('summary', '')}")
        else:
            lines.append("- Nessuna pista documentale.")
        review_items = _list_items(profile.get("review_items"))
        if review_items:
            lines.extend(["", "Review items:"])
            for item in review_items[:10]:
                lines.append(
                    f"- `{item.get('item_id') or item.get('record_id', '')}` "
                    f"su `{item.get('source_document_id', '')}`: {item.get('question', '')}"
                )
        review_decisions = _list_items(profile.get("review_decisions"))
        if review_decisions:
            lines.extend(["", "Decisioni:"])
            for decision in review_decisions[:10]:
                lines.append(
                    f"- `{decision.get('decision_id') or decision.get('record_id', '')}` "
                    f"azione `{decision.get('selected_action', '')}` | stato `{decision.get('review_status', '')}`"
                )
        profile_coverage = profile.get("evidence_store_coverage")
        if isinstance(profile_coverage, dict) and profile_coverage.get("record_count", 0):
            lines.extend(["", "Copertura evidence store:"])
            lines.append(f"- Record store: `{profile_coverage.get('record_count', 0)}`")
            lines.append(f"- Documenti distinti nello store: `{profile_coverage.get('source_document_count', 0)}`")
            by_kind = _dict_items(profile_coverage.get("by_kind"))
            if by_kind:
                lines.append("- Tipi record: " + ", ".join(f"`{kind}` `{count}`" for kind, count in sorted(by_kind.items())))
            by_status = _dict_items(profile_coverage.get("by_review_status"))
            if by_status:
                lines.append("- Stati review: " + ", ".join(f"`{status}` `{count}`" for status, count in sorted(by_status.items())))

    warnings = _list_strings(ledger.get("warnings"))
    if warnings:
        lines.extend(["", "## Warning", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Il ledger e' derivato da summary MVP e run tecniche.",
            "- Non modifica profili JSON-LD canonici, raw archive, cache o documenti originali.",
            "- Non applica decisioni di review.",
            "- Nessun claim candidato viene trattato come fatto verificato.",
            "",
        ]
    )
    return "\n".join(lines)


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, set):
        value = sorted(value)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _dict_items(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _yaml_value(value: Any) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'
