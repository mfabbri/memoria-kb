from __future__ import annotations

import sys
import urllib.parse
from datetime import datetime

from ..models import Caduto, SearchHit, Source, SourceResult
from .http_sources import split_person_name


def _log_cwgc_progress(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    encoding = sys.stdout.encoding or "utf-8"
    line = f"[{timestamp}]     CWGC: {message}"
    safe_line = line.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
    print(safe_line, flush=True)


def _parse_positive_int(value: str, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def build_cwgc_search_url(
    base_url: str,
    *,
    surname: str = "",
    forename: str = "",
    initials: str = "",
    war_select: str = "2",
) -> str:
    params = {
        "Surname": surname,
        "Forename": forename,
        "Initials": initials,
        "ServiceNum": "",
        "Regiment": "",
        "WarSelect": war_select,
        "CountryCommemoratedIn": "null",
        "Cemetery": "",
        "Unit": "",
        "Rank": "",
        "SecondaryRegiment": "",
        "SecondaryUnit": "",
        "AgeOfDeath": "0",
        "DateDeathFromDay": "1",
        "DateDeathFromMonth": "January",
        "DateDeathFromYear": "",
        "DateDeathToDay": "1",
        "DateDeathToMonth": "January",
        "DateDeathToYear": "",
        "DateOfDeath": "",
        "Honours": "null",
        "AdditionalInfo": "",
        "Page": "1",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def _build_cwgc_search_url(
    base_url: str,
    *,
    surname: str = "",
    forename: str = "",
    initials: str = "",
    war_select: str = "2",
) -> str:
    return build_cwgc_search_url(
        base_url,
        surname=surname,
        forename=forename,
        initials=initials,
        war_select=war_select,
    )


def _build_cwgc_search_attempts(source: Source, caduto: Caduto) -> list[dict[str, str]]:
    name_order = source.form.get("name_order", "surname_first")
    given_name, surname = split_person_name(caduto.nome, name_order)
    war_select = source.form.get("war_select", "2").strip() or "2"
    attempts: list[dict[str, str]] = []

    if surname and given_name:
        attempts.append(
            {
                "label": "cognome-nome-ww2",
                "surname": surname,
                "forename": given_name,
                "initials": "",
                "war_select": war_select,
            }
        )
        attempts.append(
            {
                "label": "solo-cognome-ww2",
                "surname": surname,
                "forename": "",
                "initials": "",
                "war_select": war_select,
            }
        )
    elif given_name:
        attempts.append(
            {
                "label": "mononimo-come-cognome-ww2",
                "surname": given_name,
                "forename": "",
                "initials": "",
                "war_select": war_select,
            }
        )
        attempts.append(
            {
                "label": "mononimo-come-nome-ww2",
                "surname": "",
                "forename": given_name,
                "initials": "",
                "war_select": war_select,
            }
        )

    return attempts


def _attempt_query_description(attempt: dict[str, str]) -> str:
    parts = [attempt["label"]]
    if attempt["surname"]:
        parts.append(f'Surname="{attempt["surname"]}"')
    if attempt["forename"]:
        parts.append(f'Forename="{attempt["forename"]}"')
    if attempt["initials"]:
        parts.append(f'Initials="{attempt["initials"]}"')
    if attempt["war_select"]:
        parts.append(f'WarSelect="{attempt["war_select"]}"')
    return "; ".join(parts)


def run_cwgc_source(source: Source, caduto: Caduto, query: str, search_url: str) -> SourceResult:
    base_url = source.form.get(
        "results_base_url",
        "https://www.cwgc.org/find-records/find-war-dead/search-results/",
    ).strip()
    max_attempts = _parse_positive_int(source.form.get("max_attempts", "2"), 2)
    attempts = _build_cwgc_search_attempts(source, caduto)[:max_attempts]
    if not attempts:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="search_url_ready",
            note=f"{source.note} Nominativo non sufficiente per costruire una ricerca CWGC.",
            query=query,
            search_url=search_url,
        )

    _log_cwgc_progress(f"{caduto.intestazione_pdf}: preparo {len(attempts)} URL da find-war-dead.")
    hits: list[SearchHit] = []
    for attempt_index, attempt in enumerate(attempts, start=1):
        description = _attempt_query_description(attempt)
        url = _build_cwgc_search_url(
            base_url,
            surname=attempt["surname"],
            forename=attempt["forename"],
            initials=attempt["initials"],
            war_select=attempt["war_select"],
        )
        _log_cwgc_progress(f"{caduto.intestazione_pdf}: URL {attempt_index}/{len(attempts)} - {description}")
        hits.append(
            SearchHit(
                title=description,
                url=url,
                snippet="URL CWGC Find War Dead pronto per verifica manuale/interattiva.",
            )
        )

    note = (
        f"{source.note} Generati {len(hits)} URL dalla ricerca Find War Dead CWGC. "
        "Per rispetto dei limiti dichiarati dal sito, il connettore prepara i link senza scaricare automaticamente i risultati."
    )
    return SourceResult(
        source_id=source.source_id,
        source_name=source.source_name,
        status="search_url_ready",
        note=note,
        query=" | ".join(_attempt_query_description(attempt) for attempt in attempts),
        search_url=hits[0].url,
        hits=hits,
    )
