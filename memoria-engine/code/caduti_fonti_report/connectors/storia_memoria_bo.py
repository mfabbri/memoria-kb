from __future__ import annotations

import html
import re
import urllib.parse

from ..http_utils import strip_tags
from ..models import Caduto, SearchHit, Source, SourceResult


ITALIAN_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}
ANCHOR_PATTERN = re.compile(r"<a(?P<attrs>[^>]*)>", flags=re.I)
ATTRIBUTE_PATTERN = re.compile(r'(?P<name>[\w:-]+)="(?P<value>[^"]*)"', flags=re.I)


def _get_playwright_factory():
    from playwright.sync_api import sync_playwright

    return sync_playwright


def _extract_iso_date(value: str) -> str:
    normalized = " ".join((value or "").strip().lower().split())
    if not normalized or "non reperito" in normalized or "ignoto" in normalized:
        return ""

    direct_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", normalized)
    if direct_match:
        return direct_match.group(0)

    italian_match = re.search(r"\b(\d{1,2})\s+([a-zà]+)\s+(\d{4})\b", normalized)
    if not italian_match:
        return ""

    day = int(italian_match.group(1))
    month_name = italian_match.group(2)
    year = int(italian_match.group(3))
    month = ITALIAN_MONTHS.get(month_name)
    if month is None:
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def _split_person_name(full_name: str, order: str = "surname_first") -> tuple[str, str]:
    parts = [part for part in full_name.split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    if order == "surname_first":
        return " ".join(parts[1:]), parts[0]
    return parts[0], " ".join(parts[1:])


def _build_storia_memoria_search_attempts(source: Source, caduto: Caduto) -> list[dict[str, str]]:
    given_name, surname = _split_person_name(caduto.nome, source.form.get("name_order", "surname_first"))
    birth_date = _extract_iso_date(caduto.nascita)
    death_date = _extract_iso_date(caduto.morte)

    attempts = [
        {
            "label": "nome-cognome",
            "nom": given_name,
            "cog": surname,
            "nas_min": "",
            "nas_max": "",
            "mor_min": "",
            "mor_max": "",
        }
    ]

    if birth_date:
        attempts.append(
            {
                "label": "nome-cognome-nascita",
                "nom": given_name,
                "cog": surname,
                "nas_min": birth_date,
                "nas_max": birth_date,
                "mor_min": "",
                "mor_max": "",
            }
        )

    if death_date:
        attempts.append(
            {
                "label": "nome-cognome-morte",
                "nom": given_name,
                "cog": surname,
                "nas_min": "",
                "nas_max": "",
                "mor_min": death_date,
                "mor_max": death_date,
            }
        )

    deduped_attempts: list[dict[str, str]] = []
    seen_signatures: set[tuple[str, str, str, str, str, str]] = set()
    for attempt in attempts:
        signature = (
            attempt["nom"],
            attempt["cog"],
            attempt["nas_min"],
            attempt["nas_max"],
            attempt["mor_min"],
            attempt["mor_max"],
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped_attempts.append(attempt)
    return deduped_attempts


def _attempt_query_description(attempt: dict[str, str]) -> str:
    parts = [attempt["label"], f'nom="{attempt["nom"]}"', f'cog="{attempt["cog"]}"']
    if attempt["nas_min"]:
        parts.append(f'nascita="{attempt["nas_min"]}"')
    if attempt["mor_min"]:
        parts.append(f'morte="{attempt["mor_min"]}"')
    return "; ".join(parts)


def _normalize_text(value: str) -> str:
    cleaned = strip_tags(value or "")
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def parse_storia_memoria_people_html(html_text: str, base_url: str, limit: int = 5) -> list[SearchHit]:
    hits: list[SearchHit] = []
    seen_urls: set[str] = set()

    for match in ANCHOR_PATTERN.finditer(html_text):
        attributes = {
            attr_match.group("name").lower(): html.unescape(attr_match.group("value"))
            for attr_match in ATTRIBUTE_PATTERN.finditer(match.group("attrs"))
        }
        classes = attributes.get("class", "")
        if "link-assoluto" not in classes:
            continue
        href = attributes.get("href", "")
        title = strip_tags(attributes.get("title", "")).strip()
        if not href or not title:
            continue
        absolute = urllib.parse.urljoin(base_url, href)
        if absolute in seen_urls:
            continue
        seen_urls.add(absolute)
        context_start = max(0, match.start() - 350)
        context_end = min(len(html_text), match.end() + 350)
        snippet = _normalize_text(html_text[context_start:context_end])
        hits.append(SearchHit(title=title, url=absolute, snippet=snippet[:280]))
        if len(hits) >= limit:
            break

    return hits


def extract_storia_memoria_detail_text(html_text: str) -> str:
    candidates = [
        r"<main\b[^>]*>(?P<body>.*?)</main>",
        r"<article\b[^>]*>(?P<body>.*?)</article>",
        r'<div\b[^>]*class="[^"]*node__content[^"]*"[^>]*>(?P<body>.*?)</div>',
        r'<div\b[^>]*class="[^"]*field--name-body[^"]*"[^>]*>(?P<body>.*?)</div>',
    ]
    for pattern in candidates:
        match = re.search(pattern, html_text, flags=re.I | re.S)
        if match:
            text = _normalize_text(match.group("body"))
            if text:
                return text[:2000]

    text = _normalize_text(html_text)
    return text[:2000]


def _enrich_hits_with_detail(page, hits: list[SearchHit], timeout_ms: int) -> list[SearchHit]:
    enriched_hits: list[SearchHit] = []
    for hit in hits:
        try:
            page.goto(hit.url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
            detail_html = page.content()
            detail_text = extract_storia_memoria_detail_text(detail_html)
            enriched_hits.append(SearchHit(title=hit.title, url=hit.url, snippet=hit.snippet, content=detail_text))
        except Exception:  # noqa: BLE001
            enriched_hits.append(hit)
    return enriched_hits


def _open_people_tab_if_needed(page, source: Source) -> None:
    form_selector = source.auth.get("form_selector", "#views-exposed-form-persone-block-2").strip()
    if _first_visible_locator(page.locator(form_selector)) is not None:
        return

    tab_selector = source.auth.get("people_tab_selector", 'a[href*="/ricerca-avanzata/persone"]').strip()
    tab = _first_visible_locator(page.locator(tab_selector)) if tab_selector else None
    if tab is not None:
        try:
            href = tab.get_attribute("href")
        except AttributeError:
            href = None
        if href:
            page.goto(urllib.parse.urljoin(page.url, href), wait_until="domcontentloaded", timeout=60000)
        else:
            tab.click()
        page.wait_for_load_state("networkidle", timeout=60000)


def _first_visible_locator(locator):
    """Return the first visible match, keeping lightweight test doubles working."""
    count = locator.count()
    for index in range(count):
        try:
            candidate = locator.nth(index)
            if candidate.is_visible():
                return candidate
        except AttributeError:
            return locator.first
    return None


def _visible_field(form, selector: str):
    return _first_visible_locator(form.locator(selector))


def _execute_people_search(page, source: Source, attempt: dict[str, str]) -> tuple[str, str]:
    advanced_search_url = source.auth.get(
        "advanced_search_url",
        "https://www.storiaememoriadibologna.it/ricerca-avanzata",
    ).strip()
    timeout_ms = source.timeout * 1000
    form_selector = source.auth.get("form_selector", "#views-exposed-form-persone-block-2").strip()

    page.goto(advanced_search_url, wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_load_state("networkidle", timeout=timeout_ms)
    _open_people_tab_if_needed(page, source)

    form = _first_visible_locator(page.locator(form_selector))
    if form is None:
        query = {
            key: value
            for key, value in attempt.items()
            if key != "label" and value
        }
        query_url = f"{advanced_search_url}?{urllib.parse.urlencode(query)}"
        page.goto(query_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return page.url, page.content()
    for field_name, value in {
        "s": "",
        "nom": attempt["nom"],
        "cog": attempt["cog"],
        "nas[min]": attempt["nas_min"],
        "nas[max]": attempt["nas_max"],
        "mor[min]": attempt["mor_min"],
        "mor[max]": attempt["mor_max"],
    }.items():
        field = _visible_field(form, f'input[name="{field_name}"]')
        if field is None:
            raise RuntimeError(f"Campo persone non visibile o assente: {field_name}")
        field.fill(value)
    submit = _visible_field(form, source.auth.get("submit_selector", "#edit-submit-persone").strip())
    if submit is None:
        raise RuntimeError("Pulsante invio persone non visibile o assente")
    submit.click()
    page.wait_for_load_state("networkidle", timeout=timeout_ms)

    return page.url, page.content()


def run_storia_memoria_bo_source(source: Source, caduto: Caduto, query: str, search_url: str) -> SourceResult:
    attempts = _build_storia_memoria_search_attempts(source, caduto)
    attempts_summary = [_attempt_query_description(attempt) for attempt in attempts]
    query_summary = " | ".join(attempts_summary)

    try:
        playwright_factory = _get_playwright_factory()
    except ImportError:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="error",
            note=f"{source.note} Playwright non installato nell'ambiente Python corrente.",
            query=query_summary or query,
            search_url=search_url,
        )

    browser_channel = source.auth.get("browser_channel", "").strip() or None
    browser_user_agent = source.auth.get(
        "browser_user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    ).strip()
    last_results_url = search_url
    timeout_ms = source.timeout * 1000

    try:
        with playwright_factory() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                channel=browser_channel,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=browser_user_agent,
                locale="it-IT",
                viewport={"width": 1440, "height": 1200},
            )
            page = context.new_page()
            for attempt in attempts:
                results_url, html_text = _execute_people_search(page, source, attempt)
                last_results_url = results_url
                hits = parse_storia_memoria_people_html(html_text, results_url)
                if hits:
                    hits = _enrich_hits_with_detail(page, hits, timeout_ms)
                    note = f"{source.note} Ricerca avanzata Persone eseguita via Playwright. Query riuscita: {_attempt_query_description(attempt)}."
                    return SourceResult(
                        source_id=source.source_id,
                        source_name=source.source_name,
                        status="ok",
                        note=note,
                        query=query_summary or query,
                        search_url=results_url,
                        hits=hits,
                    )

            return SourceResult(
                source_id=source.source_id,
                source_name=source.source_name,
                status="no_results",
                note=f"{source.note} Ricerca avanzata Persone completata senza risultati utili. Tentativi: {' | '.join(attempts_summary)}.",
                query=query_summary or query,
                search_url=last_results_url,
            )
    except Exception as exc:  # noqa: BLE001
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="error",
            note=f"{source.note} Errore Playwright durante la ricerca avanzata Persone: {type(exc).__name__}: {exc}",
            query=query_summary or query,
            search_url=last_results_url,
        )
