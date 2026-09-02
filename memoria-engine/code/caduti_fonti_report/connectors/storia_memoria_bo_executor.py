from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Callable
from urllib.parse import urlencode, urljoin, urlparse

from ..http_utils import page_title, strip_tags
from ..models import Source
from .search_executor import SearchExecutionResult
from .search_strategy import SearchAttempt


def _get_playwright_factory():
    from playwright.sync_api import sync_playwright

    return sync_playwright()


class StoriaMemoriaBoSearchExecutor:
    """Executor dedicato per Storia e Memoria di Bologna.

    La ricerca avanzata del sito e' fragile in esecuzione automatica. Per una
    ricerca persona con nome+cognome la risorsa piu' stabile e' il permalink:
    /archivio/persone/{cognome}-{nome}. L'executor tenta prima di validarlo live;
    se la validazione non riesce, puo' comunque emettere il permalink come
    candidato non verificato. Il fetch del dettaglio resta poi responsabile di
    leggere davvero la scheda e produrre claim.
    """

    def __init__(self, *, playwright_factory: Callable[[], object] | None = None) -> None:
        self.playwright_factory = playwright_factory or _get_playwright_factory

    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        timeout_ms = source.timeout * 1000
        advanced_search_url = source.auth.get(
            "advanced_search_url",
            source.search_url_builder(attempt.query_text),
        ).strip()
        browser_channel = source.auth.get("browser_channel", "").strip() or None
        browser_user_agent = source.auth.get(
            "browser_user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        ).strip()
        emit_unverified = _as_bool(source.auth.get("emit_unverified_permalink_candidates", "true"))
        skip_advanced_form = _as_bool(source.auth.get("skip_advanced_form_after_permalink", "false"))

        slugs = _candidate_person_slugs(attempt)
        permalink_candidates = [
            _person_url_for_slug(source=source, slug=slug)
            for slug in slugs
            if slug
        ]

        try:
            playwright_factory = self.playwright_factory()
        except ImportError as exc:
            if emit_unverified and permalink_candidates:
                return [
                    _unverified_permalink_result(
                        source=source,
                        attempt=attempt,
                        search_url=advanced_search_url,
                        person_url=permalink_candidates[0],
                        reason=f"Playwright non installato: {type(exc).__name__}: {exc}",
                    )
                ]
            return [
                SearchExecutionResult(
                    attempt=attempt,
                    title=attempt.label,
                    url=advanced_search_url,
                    status="error",
                    payload={"error": f"{type(exc).__name__}: {exc}"},
                )
            ]

        diagnostics: list[str] = []
        try:
            with playwright_factory as playwright:
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

                direct_result = self._try_direct_person_urls(
                    page=page,
                    source=source,
                    attempt=attempt,
                    timeout_ms=timeout_ms,
                    search_url=advanced_search_url,
                    diagnostics=diagnostics,
                )
                if direct_result is not None:
                    context.close()
                    browser.close()
                    return [direct_result]

                if emit_unverified and permalink_candidates and skip_advanced_form:
                    context.close()
                    browser.close()
                    return [
                        _unverified_permalink_result(
                            source=source,
                            attempt=attempt,
                            search_url=advanced_search_url,
                            person_url=permalink_candidates[0],
                            reason="; ".join(diagnostics) or "validazione live non conclusiva",
                        )
                    ]

                if skip_advanced_form:
                    context.close()
                    browser.close()
                    return [
                        SearchExecutionResult(
                            attempt=attempt,
                            title=attempt.label,
                            url=advanced_search_url,
                            status="ok",
                            payload={"html": _empty_result_html("nessun permalink candidato costruibile")},
                        )
                    ]

                self._run_advanced_form(page=page, source=source, attempt=attempt, timeout_ms=timeout_ms)
                result_url = page.url
                html_text = page.content()
                context.close()
                browser.close()
        except Exception as exc:  # noqa: BLE001
            if emit_unverified and permalink_candidates:
                return [
                    _unverified_permalink_result(
                        source=source,
                        attempt=attempt,
                        search_url=advanced_search_url,
                        person_url=permalink_candidates[0],
                        reason=f"errore Playwright prima della validazione: {type(exc).__name__}: {exc}",
                    )
                ]
            return [
                SearchExecutionResult(
                    attempt=attempt,
                    title=attempt.label,
                    url=advanced_search_url,
                    status="error",
                    payload={"error": f"{type(exc).__name__}: {exc}"},
                )
            ]

        return [
            SearchExecutionResult(
                attempt=attempt,
                title=attempt.label,
                url=result_url,
                status="ok",
                payload={"html": html_text},
            )
        ]

    def _try_direct_person_urls(
        self,
        *,
        page,
        source: Source,
        attempt: SearchAttempt,
        timeout_ms: int,
        search_url: str,
        diagnostics: list[str],
    ) -> SearchExecutionResult | None:
        for slug in _candidate_person_slugs(attempt):
            person_url = _person_url_for_slug(source=source, slug=slug)
            try:
                response = page.goto(person_url, wait_until="domcontentloaded", timeout=timeout_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=timeout_ms)
                except Exception:  # noqa: BLE001
                    pass
                status = response.status if response is not None else 0
                detail_html = page.content()
                diagnostics.append(f"direct={person_url} status={status} title={page_title(detail_html)[:80]}")
            except Exception as exc:  # noqa: BLE001
                diagnostics.append(f"direct={person_url} error={type(exc).__name__}: {exc}")
                continue

            if not _looks_like_person_detail(detail_html=detail_html, expected_slug=slug, status=status):
                continue

            title = _first_heading(detail_html) or page_title(detail_html) or _title_from_attempt(attempt)
            synthetic_html = _synthetic_result_html(
                title=title,
                url=person_url,
                snippet="Permalink persona validato via Playwright. " + strip_tags(detail_html)[:500],
            )
            return SearchExecutionResult(
                attempt=attempt,
                title=attempt.label,
                url=search_url,
                status="ok",
                payload={
                    "html": synthetic_html,
                    "detail_html_by_url": {person_url: _clean_person_detail_html(detail_html)},
                    "storia_memoria_bo_resolution": "direct_person_permalink_validated",
                    "storia_memoria_bo_slug": slug,
                },
            )
        return None

    def _run_advanced_form(self, *, page, source: Source, attempt: SearchAttempt, timeout_ms: int) -> None:
        advanced_search_url = source.auth.get(
            "advanced_search_url",
            source.search_url_builder(attempt.query_text),
        ).strip()
        form_selector = source.auth.get("form_selector", "#views-exposed-form-persone-block-2").strip()
        submit_selector = source.auth.get("submit_selector", "#edit-submit-persone").strip()

        page.goto(advanced_search_url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:  # noqa: BLE001
            pass
        self._open_people_tab_if_needed(page, source=source, timeout_ms=timeout_ms)

        form = _first_visible_locator(page.locator(form_selector))
        if form is None:
            query = {
                key: value
                for key, value in attempt.fields.items()
                if value
            }
            query_url = f"{advanced_search_url}?{urlencode(query)}"
            page.goto(query_url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:  # noqa: BLE001
                pass
            return

        for field_name, value in attempt.fields.items():
            selector = f'input[name="{field_name}"]'
            locator = _first_visible_locator(form.locator(selector))
            if locator is not None:
                locator.fill(value)

        submit = _first_visible_locator(form.locator(submit_selector))
        if submit is not None:
            submit.click()
        else:
            first_input = form.locator("input").first
            first_input.press("Enter")
        try:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:  # noqa: BLE001
            pass

    def _open_people_tab_if_needed(self, page, *, source: Source, timeout_ms: int) -> None:
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
                page.goto(urljoin(page.url, href), wait_until="domcontentloaded", timeout=timeout_ms)
            else:
                tab.click()
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:  # noqa: BLE001
                pass


def _first_visible_locator(locator):
    count = locator.count()
    for index in range(count):
        try:
            candidate = locator.nth(index)
            if candidate.is_visible():
                return candidate
        except AttributeError:
            return locator.first
    return None


def _candidate_person_slugs(attempt: SearchAttempt) -> list[str]:
    candidates: list[str] = []
    given_name = attempt.fields.get("nom", "").strip()
    family_name = attempt.fields.get("cog", "").strip()
    free_text = attempt.fields.get("s", "").strip()

    if family_name and given_name:
        candidates.append(_slugify(f"{family_name} {given_name}"))

    if free_text:
        parts = [part for part in free_text.split() if part]
        if len(parts) >= 2:
            candidates.append(_slugify(" ".join([parts[-1], *parts[:-1]])))
        candidates.append(_slugify(free_text))

    return _dedupe([candidate for candidate in candidates if candidate])


def _person_url_for_slug(*, source: Source, slug: str) -> str:
    base_url = source.auth.get(
        "direct_person_base_url",
        "https://www.storiaememoriadibologna.it/archivio/persone",
    ).strip().rstrip("/")
    return f"{base_url}/{slug}"


def _slugify(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = ascii_text.casefold()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return cleaned.strip("-")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _looks_like_person_detail(*, detail_html: str, expected_slug: str, status: int) -> bool:
    if status and status >= 400:
        return False
    text = " ".join(strip_tags(detail_html).split()).casefold()
    if not text:
        return False
    negative_markers = ["pagina non trovata", "not found", "access denied", "forbidden", "errore 404"]
    if any(marker in text for marker in negative_markers):
        return False
    title = (_first_heading(detail_html) or page_title(detail_html)).casefold()
    expected_tokens = [token for token in expected_slug.split("-") if token]
    if title and all(token in _slugify(title) for token in expected_tokens[:2]):
        return True
    # Alcune versioni della pagina mettono il link canonico solo nei metadati.
    parsed_links = re.findall(r'href=["\']([^"\']*?/archivio/persone/[^"\']+)["\']', detail_html, flags=re.I)
    return any(expected_slug in link.casefold() for link in parsed_links)


def _first_heading(html_text: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.I | re.S)
    return strip_tags(match.group(1)).strip() if match else ""


def _title_from_attempt(attempt: SearchAttempt) -> str:
    given_name = attempt.fields.get("nom", "").strip()
    family_name = attempt.fields.get("cog", "").strip()
    if given_name or family_name:
        return " ".join(part for part in [given_name, family_name] if part)
    return attempt.fields.get("s", "").strip() or attempt.label


def _synthetic_result_html(*, title: str, url: str, snippet: str) -> str:
    return (
        "<html><body><main>"
        f'<a href="{html.escape(url)}" title="{html.escape(title)}">{html.escape(title)}</a>'
        f"<p>{html.escape(snippet)}</p>"
        "</main></body></html>"
    )


def _empty_result_html(reason: str) -> str:
    return f"<html><body><main><p>{html.escape(reason)}</p></main></body></html>"


def _unverified_permalink_result(
    *,
    source: Source,
    attempt: SearchAttempt,
    search_url: str,
    person_url: str,
    reason: str,
) -> SearchExecutionResult:
    title = _title_from_attempt(attempt)
    snippet = (
        "Permalink persona costruito deterministicamente dal nome/cognome; "
        "da verificare nella fase detail. "
        f"Diagnostica: {reason}"
    )
    return SearchExecutionResult(
        attempt=attempt,
        title=attempt.label,
        url=search_url,
        status="ok",
        payload={
            "html": _synthetic_result_html(title=title, url=person_url, snippet=snippet),
            "storia_memoria_bo_resolution": "direct_person_permalink_unverified",
            "storia_memoria_bo_permalink": person_url,
        },
    )


def _as_bool(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "si", "sì"}



def _clean_person_detail_html(html_text: str) -> str:
    """Reduce Storia e Memoria person pages to their reviewable content area.

    This is intentionally source-specific: the generic detail parser must remain
    layout-agnostic, while this connector knows that Storia e Memoria pages can
    prepend global header/navigation text and append global footer blocks before
    the biographical content is interpreted.
    """
    if not html_text.strip():
        return html_text

    working = html_text
    for tag_name in ("header", "nav", "footer", "script", "style", "noscript"):
        working = re.sub(
            rf"<{tag_name}\b[^>]*>.*?</{tag_name}>",
            " ",
            working,
            flags=re.I | re.S,
        )

    # Prefer semantic containers used by Drupal/person pages.  Keep the HTML
    # tags so the common detail parser can still extract heading and fields.
    for pattern in (
        r"<main\b[^>]*>(.*?)</main>",
        r"<article\b[^>]*>(.*?)</article>",
        r"<div[^>]+class=[\"'][^\"']*(?:region-content|layout-content|node--type-person|field--name-body)[^\"']*[\"'][^>]*>(.*?)</div>",
    ):
        match = re.search(pattern, working, flags=re.I | re.S)
        if match:
            candidate = match.group(1)
            if _person_content_is_useful(candidate):
                working = candidate
                break

    h1_match = re.search(r"<h1\b[^>]*>.*?</h1>", working, flags=re.I | re.S)
    if h1_match and h1_match.start() > 0:
        working = working[h1_match.start():]

    for marker in (
        "Seguici su Facebook",
        "Contenuto inserito il",
        "Ultimo aggiornamento",
        "Torna su",
    ):
        marker_match = re.search(re.escape(marker), working, flags=re.I)
        if marker_match and marker_match.start() > 500:
            working = working[:marker_match.start()]
            break

    return f"<html><body><main>{working}</main></body></html>"


def _person_content_is_useful(html_fragment: str) -> bool:
    text = " ".join(strip_tags(html_fragment).split()).casefold()
    return bool(text) and (
        "/archivio/persone/" in html_fragment.casefold()
        or "brigata" in text
        or "nato il" in text
        or re.search(r"\b[0-9]{1,2}\s+[a-zà-ÿ]+\s+[0-9]{4}\b", text, flags=re.I) is not None
    )

def fetch_storia_memoria_bo_detail_html(
    url: str,
    *,
    timeout: int,
    browser_channel: str = "",
    browser_user_agent: str = "",
    playwright_factory: Callable[[], object] | None = None,
) -> str:
    """Fetch detail page with a browser-like request, then Playwright fallback.

    Storia e Memoria di Bologna can reject generic bot user agents. The uniform
    connector uses this helper only for the detail page of this source.
    """
    import urllib.request

    user_agent = browser_user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return _clean_person_detail_html(response.read().decode(charset, errors="ignore"))
    except Exception as http_exc:  # noqa: BLE001
        try:
            factory = playwright_factory or _get_playwright_factory()
        except Exception as pw_import_exc:  # noqa: BLE001
            raise RuntimeError(
                f"HTTP detail fetch failed ({type(http_exc).__name__}: {http_exc}); "
                f"Playwright unavailable ({type(pw_import_exc).__name__}: {pw_import_exc})"
            ) from http_exc

        timeout_ms = timeout * 1000
        try:
            with factory as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    channel=browser_channel.strip() or None,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    user_agent=user_agent,
                    locale="it-IT",
                    viewport={"width": 1440, "height": 1200},
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=timeout_ms)
                except Exception:  # noqa: BLE001
                    pass
                html_text = _clean_person_detail_html(page.content())
                context.close()
                browser.close()
                return html_text
        except Exception as pw_exc:  # noqa: BLE001
            raise RuntimeError(
                f"HTTP detail fetch failed ({type(http_exc).__name__}: {http_exc}); "
                f"Playwright detail fetch failed ({type(pw_exc).__name__}: {pw_exc})"
            ) from http_exc
