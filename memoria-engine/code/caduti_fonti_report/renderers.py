from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from .models import Caduto, SourceResult, SourceSelection


def render_markdown(
    caduti: list[Caduto],
    results: dict[str, list[SourceResult]],
    source_selection: SourceSelection,
    detailed_results: dict[str, list[dict[str, object]]] | None = None,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Report fonti caduti di Purocielo",
        "",
        f"Generato il: {now}",
        "",
        f"File fonti usato come source of truth: `{source_selection.source_file}`",
        f"Fonti selezionate: {', '.join(source_selection.selected_source_ids)}",
        "",
        "Questo file raccoglie, per ogni caduto del CSV, l'esito dell'interrogazione automatica o lo stato operativo della fonte.",
        "",
        "Legenda stati:",
        "- `ok`: trovati hit o risultati estraibili.",
        "- `no_results`: la ricerca e' stata eseguita ma non ha prodotto hit utili.",
        "- `search_url_ready`: generato link di ricerca, ma il sito richiede consultazione interattiva.",
        "- `needs_credentials`: servono credenziali o dati di accesso non presenti nella configurazione.",
        "- `manual_request`: fonte da consultare manualmente o via richiesta archivistica.",
        "- `error`: errore tecnico durante la richiesta.",
        "",
    ]

    if source_selection.unresolved_source_ids:
        lines.append("ID fonte presenti nel YAML ma non trovati nel registry:")
        for source_id in source_selection.unresolved_source_ids:
            lines.append(f"- {source_id}")
        lines.append("")

    if source_selection.used_fallback:
        lines.append("Nota: nessuna fonte valida selezionata nel YAML, quindi e' stato usato il set completo definito nel file di configurazione.")
        lines.append("")

    for caduto in caduti:
        lines.extend(
            [
                f"## {caduto.intestazione_pdf}",
                "",
                f"- Nome: {caduto.nome}",
                f"- Origine lapide: {caduto.origine_sulla_lapide}",
                f"- Nascita: {caduto.nascita}",
                f"- Morte: {caduto.morte}",
                f"- Ruolo: {caduto.ruolo_affiliazione}",
                "",
            ]
        )
        for source_result in results[caduto.intestazione_pdf]:
            lines.append(f"### {source_result.source_name}")
            lines.append("")
            lines.append(f"- Stato: `{source_result.status}`")
            lines.append(f"- Query: `{source_result.query}`")
            if source_result.search_url:
                lines.append(f"- Ricerca: {source_result.search_url}")
            lines.append(f"- Nota: {source_result.note}")
            if source_result.hits:
                lines.append("- Hit:")
                for hit in source_result.hits:
                    lines.append(f"  - [{hit.title}]({hit.url})")
                    if hit.snippet:
                        lines.append(f"    - Estratto risultati: {hit.snippet}")
                    if hit.content:
                        lines.append(f"    - Contenuto scheda: {hit.content}")
            detail_entry = _find_detail_entry(source_result, (detailed_results or {}).get(caduto.intestazione_pdf, []))
            if detail_entry is not None:
                _append_search_plan_audit(lines, detail_entry)
                _append_detail_documents(lines, detail_entry)
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def slugify(value: str) -> str:
    value = value.lower()
    replacements = {
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
        "ª": "a",
        "°": "",
        "“": "",
        "”": "",
        '"': "",
        "'": "",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "caduto"


def render_single_caduto_markdown(
    caduto: Caduto,
    source_results: list[SourceResult],
    detailed_results: list[dict[str, object]] | None = None,
) -> str:
    lines = [
        f"# {caduto.intestazione_pdf}",
        "",
        f"- Nome: {caduto.nome}",
        f"- Origine lapide: {caduto.origine_sulla_lapide}",
        f"- Nascita: {caduto.nascita}",
        f"- Morte: {caduto.morte}",
        f"- Ruolo: {caduto.ruolo_affiliazione}",
        f"- Fonti richiamate nel CSV: {caduto.fonti_richiamate}",
        "",
        "## Risultati per fonte",
        "",
    ]
    for source_result in source_results:
        lines.append(f"### {source_result.source_name}")
        lines.append("")
        lines.append(f"- Stato: `{source_result.status}`")
        lines.append(f"- Query: `{source_result.query}`")
        if source_result.search_url:
            lines.append(f"- Ricerca: {source_result.search_url}")
        lines.append(f"- Nota: {source_result.note}")
        if source_result.hits:
            lines.append("- Hit:")
            for hit in source_result.hits:
                lines.append(f"  - [{hit.title}]({hit.url})")
                if hit.snippet:
                    lines.append(f"    - Estratto risultati: {hit.snippet}")
                if hit.content:
                    lines.append(f"    - Contenuto scheda: {hit.content}")
        detail_entry = _find_detail_entry(source_result, detailed_results or [])
        if detail_entry is not None:
            _append_search_plan_audit(lines, detail_entry)
            _append_detail_documents(lines, detail_entry)
        lines.append("")
    return "\n".join(lines)


def _find_detail_entry(source_result: SourceResult, detailed_results: list[dict[str, object]]) -> dict[str, object] | None:
    for entry in detailed_results:
        result = entry.get("result")
        if not isinstance(result, dict):
            continue
        if result.get("query") == source_result.query and result.get("search_url") == source_result.search_url:
            return entry
    return None


def _append_detail_documents(lines: list[str], detail_entry: dict[str, object]) -> None:
    documents = detail_entry.get("documents", [])
    claims = detail_entry.get("claims", [])
    if isinstance(documents, list) and documents:
        lines.append("- Documenti di dettaglio:")
        for document in documents:
            if not isinstance(document, dict):
                continue
            title = str(document.get("title", "")).strip() or "Documento"
            url = str(document.get("url", "")).strip()
            if url:
                lines.append(f"  - [{title}]({url})")
            else:
                lines.append(f"  - {title}")
            metadata = document.get("metadata", {})
            extracted_fields: dict[str, str] = {}
            if isinstance(metadata, dict):
                detail_assessment = str(metadata.get("detail_assessment", "")).strip()
                if detail_assessment:
                    lines.append(f"    - Valutazione dettaglio: `{detail_assessment}`")
                extracted_fields = _metadata_extracted_fields(metadata)
            if extracted_fields:
                lines.append("    - Campi estratti:")
                for field_id, value in extracted_fields.items():
                    lines.append(f"      - `{field_id}`: {value}")
            raw_text = _detail_excerpt(str(document.get("raw_text", "")), title=title)
            if raw_text:
                lines.append(f"    - Estratto scheda: {raw_text}")
    if isinstance(claims, list) and claims:
        lines.append("- Claim candidati:")
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            field = str(claim.get("field", "")).strip()
            value = str(claim.get("value", "")).strip()
            confidence = claim.get("confidence", "")
            confidence_text = _confidence_text(confidence)
            if field and value:
                lines.append(f"  - `{field}`: {value}{confidence_text}")


def _append_search_plan_audit(lines: list[str], detail_entry: dict[str, object]) -> None:
    planned_attempts = detail_entry.get("planned_attempts", [])
    matched_status = str(detail_entry.get("matched_planned_attempt_status", "")).strip()
    if not matched_status and not isinstance(planned_attempts, list):
        return
    if isinstance(planned_attempts, list) and not planned_attempts and not matched_status:
        return

    lines.append("- Audit piano ricerca:")
    execution_mode = str(detail_entry.get("planned_execution_mode", "")).strip()
    if execution_mode:
        lines.append(f"  - Modalita': `{execution_mode}`")
    execution_limit = detail_entry.get("planned_attempt_execution_limit", "")
    if execution_limit != "":
        lines.append(f"  - Limite tentativi eseguiti: `{execution_limit}`")
    if matched_status:
        lines.append(f"  - Stato match tentativo: `{matched_status}`")

    matched_attempt = _matched_planned_attempt(detail_entry, planned_attempts)
    if matched_attempt:
        attempt_id = str(matched_attempt.get("attempt_id", "")).strip()
        priority = matched_attempt.get("priority", "")
        query_text = str(matched_attempt.get("query_text", "")).strip()
        if attempt_id:
            lines.append(f"  - Tentativo: `{attempt_id}`")
        if priority != "":
            lines.append(f"  - Priorita': `{priority}`")
        if query_text:
            lines.append(f"  - Query pianificata: `{query_text}`")
        _append_field_resolution(lines, matched_attempt)
    elif isinstance(planned_attempts, list) and planned_attempts:
        lines.append("  - Tentativo: non riconciliato con il risultato prodotto")
        first_attempt = planned_attempts[0]
        if isinstance(first_attempt, dict):
            attempt_id = str(first_attempt.get("attempt_id", "")).strip()
            query_text = str(first_attempt.get("query_text", "")).strip()
            if attempt_id:
                lines.append(f"  - Primo tentativo pianificato: `{attempt_id}`")
            if query_text:
                lines.append(f"  - Prima query pianificata: `{query_text}`")
            _append_field_resolution(lines, first_attempt)


def _append_field_resolution(lines: list[str], attempt: dict[object, object]) -> None:
    metadata = attempt.get("metadata", {})
    if not isinstance(metadata, dict):
        return
    kind = str(metadata.get("field_resolution.kind", "")).strip()
    if kind != "source_place_mapping":
        return
    resolution_id = str(metadata.get("field_resolution.id", "")).strip()
    output_fields = str(metadata.get("field_resolution.output_fields", "")).strip()
    review_status = str(metadata.get("field_resolution.review_status", "")).strip()
    matched_terms = str(metadata.get("field_resolution.matched_terms", "")).strip()
    labels = str(metadata.get("field_resolution.labels", "")).strip()
    if resolution_id:
        lines.append(f"  - Risoluzione campi fonte: `{resolution_id}`")
    if matched_terms:
        lines.append(f"  - Termini luogo usati: `{matched_terms}`")
    if output_fields:
        lines.append(f"  - Campi fonte risolti: `{output_fields}`")
    if labels:
        lines.append(f"  - Label fonte: `{labels}`")
    if review_status:
        lines.append(f"  - Stato revisione mapping: `{review_status}`")


def _matched_planned_attempt(
    detail_entry: dict[str, object],
    planned_attempts: object,
) -> dict[object, object] | None:
    if not isinstance(planned_attempts, list):
        return None
    matched_attempt_id = str(detail_entry.get("matched_planned_attempt_id", "")).strip()
    if not matched_attempt_id:
        return None
    for attempt in planned_attempts:
        if not isinstance(attempt, dict):
            continue
        if str(attempt.get("attempt_id", "")).strip() == matched_attempt_id:
            return attempt
    return None


def _metadata_extracted_fields(metadata: dict[object, object]) -> dict[str, str]:
    raw_value = metadata.get("detail_extracted_fields_json", "")
    if not isinstance(raw_value, str) or not raw_value.strip():
        return {}
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    fields: dict[str, str] = {}
    for key, value in payload.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if key_text and value_text:
            fields[key_text] = value_text
    return fields


def _confidence_text(value: object) -> str:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return ""
    if confidence <= 0:
        return ""
    return f" — confidenza {confidence:.2f}"


def _detail_excerpt(raw_text: str, limit: int = 700, *, title: str = "") -> str:
    compact = " ".join(raw_text.split())
    if not compact:
        return ""
    normalized_title = " ".join(title.split()).strip()
    if normalized_title and len(normalized_title) >= 4:
        idx = compact.casefold().find(normalized_title.casefold())
        if idx > 0:
            compact = compact[idx:].strip()
    return compact[:limit].rstrip() + ("..." if len(compact) > limit else "")
