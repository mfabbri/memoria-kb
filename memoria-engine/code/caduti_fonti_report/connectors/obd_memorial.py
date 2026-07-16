from __future__ import annotations

import re
import sys
import unicodedata
import urllib.error
import urllib.parse
from datetime import datetime

from ..http_utils import fetch_text, strip_tags
from ..models import Caduto, SearchHit, Source, SourceResult


LATIN_TO_CYRILLIC_DIGRAPHS = (
    ("shch", "щ"),
    ("sch", "щ"),
    ("yo", "ё"),
    ("yu", "ю"),
    ("ya", "я"),
    ("ye", "е"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("ju", "ю"),
    ("ja", "я"),
    ("ij", "ий"),
)

LATIN_TO_CYRILLIC_CHARS = {
    "a": "а",
    "b": "б",
    "c": "к",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "ы",
    "z": "з",
}

RUSSIAN_GIVEN_NAME_VARIANTS = {
    "alessandro": ["александр"],
    "andrea": ["андрей"],
    "antonio": ["антон", "антонио"],
    "carlo": ["карл"],
    "dino": ["дино"],
    "giorgio": ["георгий", "жорж"],
    "giovanni": ["иван"],
    "mario": ["марио"],
    "michele": ["михаил", "микеле"],
    "nicola": ["николай", "никола"],
    "paolo": ["павел", "паоло"],
    "renato": ["ренат", "ренато"],
    "roberto": ["роберт", "роберто"],
    "sergio": ["сергей", "сергио"],
    "stefano": ["степан", "стефан"],
    "ugo": ["уго"],
}

NOISE_NAME_TOKENS = {"il", "lo", "la", "memo", "v"}
OBD_NO_RESULTS_MARKERS = (
    "\u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432",
    "\u043f\u043e \u0432\u0430\u0448\u0435\u043c\u0443 \u0437\u0430\u043f\u0440\u043e\u0441\u0443",
)
SOVIET_RELEVANCE_MARKERS = ("u.r.s.s", "urss", "soviet", "sovietico", "sovietica", "unione sovietica")


def _log_obd_progress(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    encoding = sys.stdout.encoding or "utf-8"
    line = f"[{timestamp}]     OBD-Memorial: {message}"
    safe_line = line.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
    print(safe_line, flush=True)


def _parse_positive_int(value: str, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _normalize_latin_token(value: str) -> str:
    value = _strip_accents(value).lower()
    value = value.replace("'", " ")
    value = re.sub(r"[^a-z]+", " ", value)
    return " ".join(value.split())


def _title_cyrillic(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value


def transliterate_latin_to_russian(value: str) -> str:
    token = _normalize_latin_token(value).replace(" ", "")
    if not token:
        return ""

    pieces: list[str] = []
    index = 0
    while index < len(token):
        for latin, cyrillic in LATIN_TO_CYRILLIC_DIGRAPHS:
            if token.startswith(latin, index):
                pieces.append(cyrillic)
                index += len(latin)
                break
        else:
            pieces.append(LATIN_TO_CYRILLIC_CHARS.get(token[index], token[index]))
            index += 1
    return _title_cyrillic("".join(pieces))


def _clean_name_parts(name: str) -> list[str]:
    parts: list[str] = []
    for raw_part in re.split(r"\s+", name):
        cleaned = _normalize_latin_token(raw_part)
        if not cleaned or cleaned in NOISE_NAME_TOKENS:
            continue
        if cleaned not in parts:
            parts.append(cleaned)
    return parts


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        key = clean.casefold()
        if not clean or key in seen:
            continue
        seen.add(key)
        deduped.append(clean)
    return deduped


def _given_name_variants(given_name: str) -> list[str]:
    normalized = _normalize_latin_token(given_name).replace(" ", "")
    variants = [_title_cyrillic(value) for value in RUSSIAN_GIVEN_NAME_VARIANTS.get(normalized, [])]
    transliterated = transliterate_latin_to_russian(given_name)
    if transliterated:
        variants.append(transliterated)
    return _dedupe(variants)


def _build_obd_search_url(base_url: str, *, surname: str = "", given_name: str = "", patronymic: str = "", year: str = "") -> str:
    params = {
        "f": surname,
        "n": given_name,
        "s": patronymic,
        "y": year,
        "r": "",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def _extract_birth_year(caduto: Caduto) -> str:
    match = re.search(r"\b(18[0-9]{2}|19[0-9]{2}|20[0-9]{2})\b", caduto.nascita or "")
    return match.group(1) if match else ""


def _add_attempt(
    attempts: list[dict[str, str]],
    seen: set[tuple[str, str, str, str]],
    *,
    label: str,
    surname: str = "",
    given_name: str = "",
    patronymic: str = "",
    year: str = "",
) -> None:
    signature = (surname.casefold(), given_name.casefold(), patronymic.casefold(), year)
    if not surname and not given_name:
        return
    if signature in seen:
        return
    seen.add(signature)
    attempts.append(
        {
            "label": label,
            "surname": surname,
            "given_name": given_name,
            "patronymic": patronymic,
            "year": year,
        }
    )


def _build_obd_memorial_search_attempts(source: Source, caduto: Caduto) -> list[dict[str, str]]:
    parts = _clean_name_parts(caduto.nome)
    year = _extract_birth_year(caduto)
    attempts: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()

    if len(parts) >= 2:
        surname = parts[0]
        given_name = parts[1]
        cyrillic_surname = transliterate_latin_to_russian(surname)
        given_variants = _given_name_variants(given_name)

        for index, cyrillic_given in enumerate(given_variants):
            _add_attempt(
                attempts,
                seen,
                label="cognome-nome-cirillico" if index == 0 else "cognome-nome-variante-cirillica",
                surname=cyrillic_surname,
                given_name=cyrillic_given,
                year=year,
            )
        _add_attempt(
            attempts,
            seen,
            label="solo-cognome-cirillico",
            surname=cyrillic_surname,
            year=year,
        )
        _add_attempt(
            attempts,
            seen,
            label="fallback-latino",
            surname=surname.title(),
            given_name=given_name.title(),
            year=year,
        )
    elif parts:
        mononym = parts[0]
        cyrillic_variants = _given_name_variants(mononym)
        cyrillic_variants.append(transliterate_latin_to_russian(mononym))
        for index, cyrillic_name in enumerate(_dedupe(cyrillic_variants)):
            _add_attempt(
                attempts,
                seen,
                label="mononimo-cirillico" if index == 0 else "mononimo-variante-cirillica",
                surname=cyrillic_name,
                year=year,
            )
            _add_attempt(
                attempts,
                seen,
                label="nome-cirillico",
                given_name=cyrillic_name,
                year=year,
            )
        _add_attempt(
            attempts,
            seen,
            label="fallback-latino",
            surname=mononym.title(),
            year=year,
        )

    return attempts


def _attempt_query_description(attempt: dict[str, str]) -> str:
    parts = [attempt["label"]]
    if attempt["surname"]:
        parts.append(f'f="{attempt["surname"]}"')
    if attempt["given_name"]:
        parts.append(f'n="{attempt["given_name"]}"')
    if attempt["patronymic"]:
        parts.append(f's="{attempt["patronymic"]}"')
    if attempt["year"]:
        parts.append(f'y="{attempt["year"]}"')
    return "; ".join(parts)


def _obd_page_has_no_results(html_text: str) -> bool:
    page_text = strip_tags(html_text).casefold()
    return all(marker in page_text for marker in OBD_NO_RESULTS_MARKERS)


def _is_probably_soviet_caduto(caduto: Caduto) -> bool:
    context = " ".join(
        [
            caduto.origine_sulla_lapide,
            caduto.ruolo_affiliazione,
            caduto.profilo_biografico,
            caduto.episodio_documentato,
        ]
    ).casefold()
    return any(marker in context for marker in SOVIET_RELEVANCE_MARKERS)


def run_obd_memorial_source(source: Source, caduto: Caduto, query: str, search_url: str) -> SourceResult:
    if not _is_probably_soviet_caduto(caduto):
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="skipped",
            note=f"{source.note} Fonte saltata: il caduto non risulta sovietico dai campi CSV.",
            query=query,
            search_url="",
        )

    base_url = source.form.get("search_base_url", "https://obd-memorial.ru/html/search.htm").strip()
    max_attempts = _parse_positive_int(source.form.get("max_attempts", "4"), 4)
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

    hits: list[SearchHit] = []
    checked_attempts = 0
    empty_attempts = 0
    failed_attempts: list[str] = []
    _log_obd_progress(f"{caduto.intestazione_pdf}: {len(attempts)} tentativi, timeout {source.timeout}s.")
    for attempt_index, attempt in enumerate(attempts, start=1):
        url = _build_obd_search_url(
            base_url,
            surname=attempt["surname"],
            given_name=attempt["given_name"],
            patronymic=attempt["patronymic"],
            year=attempt["year"],
        )
        description = _attempt_query_description(attempt)
        _log_obd_progress(f"{caduto.intestazione_pdf}: tentativo {attempt_index}/{len(attempts)} - {description}")
        try:
            html_text = fetch_text(url, timeout=source.timeout)
            checked_attempts += 1
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            failed_attempts.append(f"{description}: {type(exc).__name__}")
            _log_obd_progress(f"{caduto.intestazione_pdf}: tentativo {attempt_index}/{len(attempts)} fallito ({type(exc).__name__}).")
            continue

        if _obd_page_has_no_results(html_text):
            empty_attempts += 1
            _log_obd_progress(f"{caduto.intestazione_pdf}: tentativo {attempt_index}/{len(attempts)} senza documenti.")
            continue

        _log_obd_progress(f"{caduto.intestazione_pdf}: tentativo {attempt_index}/{len(attempts)} da verificare.")
        hits.append(
            SearchHit(
                title=description,
                url=url,
                snippet="Pagina OBD-Memorial da verificare: non contiene il messaggio standard di nessun documento trovato.",
            )
        )

    query_description = " | ".join(_attempt_query_description(attempt) for attempt in attempts)
    first_url = _build_obd_search_url(
        base_url,
        surname=attempts[0]["surname"],
        given_name=attempts[0]["given_name"],
        patronymic=attempts[0]["patronymic"],
        year=attempts[0]["year"],
    )
    if hits:
        note = (
            f"{source.note} Verificati {checked_attempts} tentativi OBD; "
            f"{empty_attempts} pagine con messaggio standard di nessun documento sono state escluse."
        )
        if failed_attempts:
            note = f"{note} Tentativi non verificati: {', '.join(failed_attempts[:3])}."
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="search_url_ready",
            note=note,
            query=query_description,
            search_url=hits[0].url,
            hits=hits,
        )

    if checked_attempts:
        note = (
            f"{source.note} Verificati {checked_attempts} tentativi OBD: tutte le pagine controllate "
            "riportano il messaggio standard di nessun documento trovato, quindi non vengono mostrate come hit."
        )
        if failed_attempts:
            note = f"{note} Tentativi non verificati: {', '.join(failed_attempts[:3])}."
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="no_results",
            note=note,
            query=query_description,
            search_url="",
        )

    note = (
        f"{source.note} Non e' stato possibile verificare i tentativi OBD via HTTP; "
        "nessun link e' mostrato come hit finche' non viene escluso il messaggio standard di nessun risultato."
    )
    if failed_attempts:
        note = f"{note} Errori: {', '.join(failed_attempts[:3])}."
    return SourceResult(
        source_id=source.source_id,
        source_name=source.source_name,
        status="error",
        note=note,
        query=query_description,
        search_url=first_url,
    )
