from __future__ import annotations

import urllib.parse
import urllib.error
import urllib.request

from ..http_utils import (
    extract_hidden_inputs,
    fetch_text_with_opener,
    parse_search_page,
    parse_search_page_html,
    parse_wp_json_search,
    post_form_with_opener,
)
from ..models import Caduto, Source, SourceResult


def build_form_submission_note(source: Source, query: str, search_url: str) -> str:
    method = source.form.get("method", "POST").upper()
    action = source.form.get("action", search_url)
    query_field = source.form.get("query_field", "")
    query_label = source.form.get("query_label", query_field)
    static_pairs = []

    for key, value in source.form.items():
        if key in {"method", "action", "query_field", "query_label"}:
            continue
        static_pairs.append(f"{key}={value}")

    parts = [source.note.strip()] if source.note.strip() else []
    parts.append(f"Invio tramite form {method} verso {action}.")
    if query_field:
        parts.append(f"Compilare `{query_label}` nel campo `{query_field}` con il valore `{query}`.")
    if static_pairs:
        parts.append(f"Campi statici osservati nel form: {', '.join(static_pairs)}.")
    return " ".join(parts)


def run_search_form_post(source: Source, query: str, search_url: str) -> SourceResult:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    form_data = {key: value for key, value in source.form.items() if key not in {"method", "action", "query_field", "query_label", "dynamic_hidden_fields"}}
    query_field = source.form.get("query_field", "")
    if query_field:
        form_data[query_field] = query
    post_url = source.form.get("action", search_url)
    try:
        result_url, html_text = post_form_with_opener(opener, post_url, form_data, timeout=source.timeout)
        title, hits = parse_search_page_html(html_text, result_url, query)
        if hits:
            note = f"{source.note} Titolo pagina: {title}" if title else source.note
            status = "ok"
        else:
            note = (
                f"{source.note} Nessun hit interno estratto dopo submit del form. Titolo pagina: {title}"
                if title
                else f"{source.note} Nessun hit interno estratto dopo submit del form."
            )
            status = "no_results"
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status=status,
            note=note,
            query=query,
            search_url=result_url,
            hits=hits,
        )
    except (urllib.error.URLError, ValueError) as exc:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="error",
            note=f"{build_form_submission_note(source, query, search_url)} Errore durante il submit del form: {exc}.",
            query=query,
            search_url=post_url,
        )


def run_search_form_aspnet(source: Source, query: str, search_url: str) -> SourceResult:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    try:
        initial_html = fetch_text_with_opener(opener, search_url, timeout=source.timeout)
        form_data = extract_hidden_inputs(initial_html)
        form_data.update(
            {
                key: value
                for key, value in source.form.items()
                if key not in {"method", "action", "query_field", "query_label", "dynamic_hidden_fields"}
            }
        )
        query_field = source.form.get("query_field", "")
        if query_field:
            form_data[query_field] = query

        allowed_hidden = {
            key.strip()
            for key in source.form.get("dynamic_hidden_fields", "").split(",")
            if key.strip()
        }
        if allowed_hidden:
            form_data = {
                key: value
                for key, value in form_data.items()
                if key in allowed_hidden or key in source.form or key == query_field
            }

        post_url = source.form.get("action", search_url)
        result_url, html_text = post_form_with_opener(opener, post_url, form_data, timeout=source.timeout)
        title, hits = parse_search_page_html(html_text, result_url, query)
        if hits:
            note = f"{source.note} Titolo pagina: {title}" if title else source.note
            status = "ok"
        else:
            note = (
                f"{source.note} Nessun hit interno estratto dopo submit ASP.NET. Titolo pagina: {title}"
                if title
                else f"{source.note} Nessun hit interno estratto dopo submit ASP.NET."
            )
            status = "no_results"
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status=status,
            note=note,
            query=query,
            search_url=result_url,
            hits=hits,
        )
    except (urllib.error.URLError, ValueError) as exc:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="error",
            note=f"{build_form_submission_note(source, query, search_url)} Errore durante il submit ASP.NET: {exc}.",
            query=query,
            search_url=search_url,
        )


def split_person_name(query: str, order: str) -> tuple[str, str]:
    parts = [part for part in query.split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    if order == "surname_first":
        return " ".join(parts[1:]), parts[0]
    return parts[0], " ".join(parts[1:])


def run_search_form_get_name(source: Source, query: str, search_url: str) -> SourceResult:
    name_order = source.form.get("name_order", "given_first")
    given_name, surname = split_person_name(query, name_order)
    params = {
        key: value
        for key, value in source.form.items()
        if key
        not in {
            "name_field",
            "surname_field",
            "name_order",
            "query_label",
        }
    }
    name_field = source.form.get("name_field", "")
    surname_field = source.form.get("surname_field", "")
    if name_field:
        params[name_field] = given_name
    if surname_field:
        params[surname_field] = surname

    query_string = urllib.parse.urlencode(params)
    result_url = f"{search_url}?{query_string}" if query_string else search_url
    try:
        title, hits = parse_search_page(result_url, timeout=source.timeout, query=query)
        if hits:
            note = f"{source.note} Titolo pagina: {title}" if title else source.note
            status = "ok"
        else:
            note = f"{source.note} Nessun hit interno estratto. Titolo pagina: {title}" if title else source.note
            status = "no_results"
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status=status,
            note=note,
            query=query,
            search_url=result_url,
            hits=hits,
        )
    except (urllib.error.URLError, ValueError) as exc:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="error",
            note=f"{source.note} Errore durante la richiesta GET della form: {exc}.",
            query=query,
            search_url=result_url,
        )


def run_http_source(source: Source, caduto: Caduto, query: str, search_url: str) -> SourceResult:
    if source.kind == "manual":
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="manual_request",
            note=source.note,
            query=query,
            search_url=search_url,
        )

    if source.kind == "search_url_only":
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="search_url_ready",
            note=source.note,
            query=query,
            search_url=search_url,
        )

    if source.kind == "search_form_post":
        return run_search_form_post(source, query, search_url)

    if source.kind == "search_form_aspnet":
        return run_search_form_aspnet(source, query, search_url)

    if source.kind == "search_form_get_name":
        return run_search_form_get_name(source, query, search_url)

    if source.kind == "wp_json":
        hits = parse_wp_json_search(search_url, timeout=source.timeout)
        status = "ok" if hits else "no_results"
        note = source.note if hits else f"{source.note} Nessun risultato restituito dall'endpoint REST."
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status=status,
            note=note,
            query=query,
            search_url=search_url,
            hits=hits,
        )

    if source.kind == "search_page":
        title, hits = parse_search_page(search_url, timeout=source.timeout, query=query)
        if hits:
            note = f"{source.note} Titolo pagina: {title}" if title else source.note
            status = "ok"
        else:
            note = f"{source.note} Nessun hit interno estratto. Titolo pagina: {title}" if title else source.note
            status = "no_results"
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status=status,
            note=note,
            query=query,
            search_url=search_url,
            hits=hits,
        )

    return SourceResult(
        source_id=source.source_id,
        source_name=source.source_name,
        status="skipped",
        note=source.note,
        query=query,
        search_url=search_url,
    )
