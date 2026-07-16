from __future__ import annotations

import sys
import urllib.parse
from datetime import datetime

from ..models import Caduto, SearchHit, Source, SourceResult
from .obd_memorial import (
    _attempt_query_description,
    _build_obd_memorial_search_attempts,
    _is_probably_soviet_caduto,
    _parse_positive_int,
)


PAMYAT_TYPES = (
    "pamyat_commander:nagrady_nagrad_doc:nagrady_uchet_kartoteka:"
    "nagrady_ubilein_kartoteka:pamyat_voenkomat:potery_vpp:"
    "pamyat_zsp_parts:kld_polit:kld_upk:kld_vmf:"
    "potery_doneseniya_o_poteryah:potery_gospitali:"
    "potery_utochenie_poter:potery_spiski_zahoroneniy:"
    "potery_voennoplen:potery_iskluchenie_iz_spiskov:same_doroga"
)


def _build_pamyat_search_url(
    base_url: str,
    *,
    surname: str = "",
    given_name: str = "",
    patronymic: str = "",
    year: str = "",
) -> str:
    params = {
        "adv_search": "y",
        "last_name": surname,
        "first_name": given_name,
        "middle_name": patronymic,
        "date_birth": year,
        "group": "all",
        "types": PAMYAT_TYPES,
        "page": "1",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def _log_pamyat_progress(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    encoding = sys.stdout.encoding or "utf-8"
    line = f"[{timestamp}]     Pamyat Naroda: {message}"
    safe_line = line.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
    print(safe_line, flush=True)


def run_pamyat_naroda_source(source: Source, caduto: Caduto, query: str, search_url: str) -> SourceResult:
    if not _is_probably_soviet_caduto(caduto):
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="skipped",
            note=f"{source.note} Fonte saltata: il caduto non risulta sovietico dai campi CSV.",
            query=query,
            search_url="",
        )

    base_url = source.form.get("search_base_url", "https://pamyat-naroda.ru/heroes/").strip()
    max_attempts = _parse_positive_int(source.form.get("max_attempts", "3"), 3)
    attempts = _build_obd_memorial_search_attempts(source, caduto)[:max_attempts]
    if not attempts:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="search_url_ready",
            note=f"{source.note} Nominativo non sufficiente per costruire varianti in cirillico.",
            query=query,
            search_url=search_url,
        )

    _log_pamyat_progress(f"{caduto.intestazione_pdf}: preparo {len(attempts)} URL di ricerca.")
    hits: list[SearchHit] = []
    for attempt_index, attempt in enumerate(attempts, start=1):
        description = _attempt_query_description(attempt)
        url = _build_pamyat_search_url(
            base_url,
            surname=attempt["surname"],
            given_name=attempt["given_name"],
            patronymic=attempt["patronymic"],
            year=attempt["year"],
        )
        _log_pamyat_progress(f"{caduto.intestazione_pdf}: URL {attempt_index}/{len(attempts)} - {description}")
        hits.append(
            SearchHit(
                title=description,
                url=url,
                snippet="URL di ricerca Pamyat Naroda pronto per verifica manuale/interattiva.",
            )
        )

    note = (
        f"{source.note} Generati {len(hits)} URL Pamyat Naroda con ricerca avanzata "
        "su cognome, nome, patronimico e anno. Il sito e' dinamico: la verifica dei risultati resta interattiva."
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
