from __future__ import annotations

import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

from ..models import Source
from .search_executor import SearchExecutionResult
from .search_strategy import SearchAttempt


OESTA_FIELD_SEARCH_URL = "https://www.archivinformationssystem.at/feldsuche.aspx"
OESTA_FULLTEXT_SEARCH_URL = "https://www.archivinformationssystem.at/volltextsuche.aspx"


def _get_playwright_factory():
    from playwright.sync_api import sync_playwright

    return sync_playwright


@dataclass(frozen=True)
class OestaCandidate:
    title: str
    url: str
    snippet: str = ""


class OestaAisFeldsucheExecutor:
    """Dedicated Playwright executor for OeStA AIS/scopeArchiv Feldsuche.

    The public Feldsuche page is an ASP.NET WebForms page. A plain GET returns
    the search form and navigation links, not archival results. This executor
    therefore drives the browser, fills the first field-search criterion, submits
    the form, and returns a sanitized mini HTML page containing only archival
    detail links (``detail.aspx?ID=...``).

    The implementation is deliberately defensive: OeStA/scopeArchiv generated
    control IDs can change, so fields are selected by several heuristics rather
    than by a single hard-coded ASP.NET ID.
    """

    def __init__(self, *, playwright_factory: Callable[[], object] | None = None) -> None:
        self.playwright_factory = playwright_factory or _get_playwright_factory

    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        timeout_ms = max(int(source.timeout or 10), 10) * 1000
        search_url = source.search_url_builder(attempt.query_text).strip() or OESTA_FIELD_SEARCH_URL
        if "feldsuche.aspx" not in search_url.casefold():
            search_url = OESTA_FIELD_SEARCH_URL

        try:
            playwright_factory = self.playwright_factory()
        except ImportError as exc:
            return [self._error_result(source=source, attempt=attempt, url=search_url, exc=exc)]

        result_url = search_url
        diagnostic: dict[str, str] = {
            "executor": "oesta_ais_feldsuche_executor",
            "submitted": "false",
            "fallback": "false",
            "query_text": _query_text_from_attempt(attempt),
        }

        try:
            with playwright_factory as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    locale="en-US",
                    viewport={"width": 1440, "height": 1200},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/135.0.0.0 Safari/537.36"
                    ),
                )
                page = context.new_page()
                page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_ms)
                self._accept_cookies(page, timeout_ms=timeout_ms)
                self._safe_wait_networkidle(page, timeout_ms=timeout_ms)

                query_text = _query_text_from_attempt(attempt)
                if not query_text:
                    raise ValueError("Nessun valore title/query disponibile per la Feldsuche OeStA.")

                fill_info = self._configure_title_contains_search(page, query_text=query_text, timeout_ms=timeout_ms)
                diagnostic.update(fill_info)
                self._apply_time_period_if_present(page, attempt=attempt)
                self._set_results_per_page(page, value=str(source.form.get("results_per_page", "10") or "10"))
                submitted = self._submit_search(page, timeout_ms=timeout_ms)
                diagnostic["submitted"] = "true" if submitted else "false"
                self._safe_wait_networkidle(page, timeout_ms=timeout_ms)

                result_url = page.url
                candidates = self._extract_detail_candidates(page)
                diagnostic["field_search_candidate_count"] = str(len(candidates))
                diagnostic["page_title"] = self._page_title(page)

                # If the Feldsuche returns no detail links, try the public full-text
                # search as a conservative fallback. This is still OeStA AIS and is
                # useful for names that may not occur specifically in Title.
                # The result is marked in diagnostics so the report remains honest.
                if not candidates:
                    fallback_candidates, fallback_url, fallback_title = self._try_fulltext_fallback(
                        page=page,
                        query_text=query_text,
                        timeout_ms=timeout_ms,
                    )
                    if fallback_candidates:
                        candidates = fallback_candidates
                        result_url = fallback_url
                        diagnostic["fallback"] = "true"
                        diagnostic["fallback_page_title"] = fallback_title
                        diagnostic["fulltext_candidate_count"] = str(len(fallback_candidates))

                html_text = _candidate_result_page(
                    source_name=source.source_name,
                    attempt=attempt,
                    result_url=result_url,
                    candidates=candidates,
                    raw_title=diagnostic.get("fallback_page_title") or diagnostic.get("page_title", ""),
                    diagnostic=diagnostic,
                )
                context.close()
                browser.close()
        except Exception as exc:  # noqa: BLE001
            return [self._error_result(source=source, attempt=attempt, url=result_url or search_url, exc=exc, diagnostic=diagnostic)]

        return [
            SearchExecutionResult(
                attempt=attempt,
                title=attempt.label,
                url=result_url,
                status="ok",
                payload={
                    "html": html_text,
                    "candidate_count": len(candidates),
                    "executor": "oesta_ais_feldsuche_executor",
                    "diagnostic_note": _diagnostic_note(diagnostic, candidate_count=len(candidates)),
                    "diagnostic": diagnostic,
                },
            )
        ]

    def _configure_title_contains_search(self, page, *, query_text: str, timeout_ms: int) -> dict[str, str]:
        # Try to set the first criterion row to Title + contains. The method is
        # resilient to control-ID changes: it selects options by visible text and
        # fills a free-text criterion input while excluding period/result fields.
        title_selected = self._select_first_option_containing(page, option_patterns=["title", "titel"])
        contains_selected = self._select_first_option_containing(
            page,
            option_patterns=["contains", "enthält", "contient", "contiene"],
            skip_selected_text_patterns=["title", "titel", "ref. code", "signatur"],
        )

        filled = self._fill_best_field_search_text_input(page, query_text=query_text, timeout_ms=timeout_ms)
        if not filled:
            raise ValueError("Impossibile trovare un campo testo adatto nella Feldsuche OeStA.")
        return {
            "title_selected": "true" if title_selected else "false",
            "contains_selected": "true" if contains_selected else "false",
            "filled_control": filled,
        }

    def _fill_best_field_search_text_input(self, page, *, query_text: str, timeout_ms: int) -> str:
        candidates = page.evaluate(
            """() => Array.from(document.querySelectorAll('input:not([type]), input[type="text"], textarea'))
                .filter(el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style && style.visibility !== 'hidden' && style.display !== 'none'
                        && rect.width > 0 && rect.height > 0 && !el.disabled && !el.readOnly;
                })
                .map((el, index) => {
                    const rect = el.getBoundingClientRect();
                    const rowText = (el.closest('tr')?.innerText || el.parentElement?.innerText || '').trim();
                    const aria = el.getAttribute('aria-label') || '';
                    const title = el.getAttribute('title') || '';
                    const placeholder = el.getAttribute('placeholder') || '';
                    const name = el.getAttribute('name') || '';
                    const id = el.getAttribute('id') || '';
                    const type = el.getAttribute('type') || '';
                    return { index, id, name, type, aria, title, placeholder, rowText,
                             x: rect.x, y: rect.y, width: rect.width, height: rect.height };
                })"""
        )
        if not candidates:
            return ""

        excluded_tokens = [
            "zeitraum", "time period", "periodo", "date", "datum", "from", "bis", "to",
            "resultate", "results per page", "treffer", "page", "seite", "stufen", "levels",
            "archive user", "archivbenutzer", "workbook", "login", "password",
        ]
        positive_tokens = ["title", "titel", "such", "search", "begriff", "text", "keyword"]

        def score(item: dict[str, object]) -> int:
            haystack = " ".join(str(item.get(key, "")) for key in ["id", "name", "aria", "title", "placeholder", "rowText"]).casefold()
            y = float(item.get("y", 0) or 0)
            value = 1000
            if any(token in haystack for token in excluded_tokens):
                value -= 1000
            if any(token in haystack for token in positive_tokens):
                value += 150
            # Criterion rows are near the top, while period/result filters are lower.
            if y < 650:
                value += 80
            else:
                value -= 80
            # Prefer the first criterion-like input rather than later restriction fields.
            value -= int(y / 10)
            return value

        ranked = sorted(candidates, key=score, reverse=True)
        for item in ranked:
            if score(item) <= 0:
                continue
            selector = _selector_for_control(item)
            if not selector:
                continue
            try:
                page.locator(selector).first.fill(query_text, timeout=timeout_ms)
                return selector
            except Exception:  # noqa: BLE001
                continue
        return ""

    def _apply_time_period_if_present(self, page, *, attempt: SearchAttempt) -> None:
        # Deliberately disabled by default for OeStA Feldsuche because the field
        # names are generated and filling the wrong period field can trigger the
        # "time period invalid" validation branch. Re-enable only after profiling
        # the exact controls with fixtures.
        return

    def _set_results_per_page(self, page, *, value: str) -> None:
        value = value.strip()
        if not value.isdigit():
            return
        inputs = page.locator('input[type="number"]:visible, input[type="text"]:visible')
        for index in range(inputs.count()):
            candidate = inputs.nth(index)
            try:
                attrs = candidate.evaluate(
                    """el => ({
                        id: el.id || '', name: el.name || '', value: el.value || '',
                        title: el.title || '', aria: el.getAttribute('aria-label') || '',
                        rowText: el.closest('tr')?.innerText || el.parentElement?.innerText || ''
                    })"""
                )
            except Exception:  # noqa: BLE001
                continue
            haystack = " ".join(str(attrs.get(key, "")) for key in attrs).casefold()
            if "results per page" in haystack or "resultate" in haystack or "treffer" in haystack:
                try:
                    candidate.fill(value)
                    return
                except Exception:  # noqa: BLE001
                    return

    def _submit_search(self, page, *, timeout_ms: int) -> bool:
        # Prefer explicit search controls. Generic submit controls may belong to
        # navigation/login areas in WebForms pages.
        selectors = [
            'input[value="Search"]:visible',
            'input[value="Suchen"]:visible',
            'input[value*="Search"]:visible',
            'input[value*="Suchen"]:visible',
            'button:has-text("Search")',
            'button:has-text("Suchen")',
            'a:has-text("Search")',
            'a:has-text("Suchen")',
            'input[type="image"][title*="Search"]:visible',
            'input[type="image"][title*="Suchen"]:visible',
            'input[type="image"][alt*="Search"]:visible',
            'input[type="image"][alt*="Suchen"]:visible',
        ]
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count() <= 0:
                continue
            try:
                locator.first.click(timeout=timeout_ms)
                self._safe_wait_networkidle(page, timeout_ms=timeout_ms)
                return True
            except Exception:  # noqa: BLE001
                continue

        try:
            page.keyboard.press("Enter")
            self._safe_wait_networkidle(page, timeout_ms=timeout_ms)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _try_fulltext_fallback(self, *, page, query_text: str, timeout_ms: int) -> tuple[list[OestaCandidate], str, str]:
        try:
            page.goto(OESTA_FULLTEXT_SEARCH_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            self._accept_cookies(page, timeout_ms=timeout_ms)
            self._safe_wait_networkidle(page, timeout_ms=timeout_ms)
            filled = False
            selectors = [
                'input[name="ctl00$cphMainArea$txtMitAllenWoertern"]',
                'input[id*="txtMitAllenWoertern"]',
                'input[type="text"]:visible',
            ]
            for selector in selectors:
                locator = page.locator(selector)
                if locator.count() <= 0:
                    continue
                try:
                    locator.first.fill(query_text, timeout=timeout_ms)
                    filled = True
                    break
                except Exception:  # noqa: BLE001
                    continue
            if not filled:
                return [], page.url, self._page_title(page)
            self._set_results_per_page(page, value="10")
            self._submit_search(page, timeout_ms=timeout_ms)
            self._safe_wait_networkidle(page, timeout_ms=timeout_ms)
            return self._extract_detail_candidates(page), page.url, self._page_title(page)
        except Exception:  # noqa: BLE001
            return [], page.url, self._page_title(page)

    def _select_first_option_containing(
        self,
        page,
        *,
        option_patterns: list[str],
        skip_selected_text_patterns: list[str] | None = None,
    ) -> bool:
        patterns = [pattern.casefold() for pattern in option_patterns if pattern.strip()]
        skip_patterns = [pattern.casefold() for pattern in (skip_selected_text_patterns or []) if pattern.strip()]
        selects = page.locator("select:visible")
        for select_index in range(selects.count()):
            select = selects.nth(select_index)
            try:
                current_text = select.evaluate("el => el.options[el.selectedIndex]?.text || ''")
                if skip_patterns and any(pattern in current_text.casefold() for pattern in skip_patterns):
                    continue
                options = select.locator("option")
                for option_index in range(options.count()):
                    option = options.nth(option_index)
                    text = option.inner_text().strip()
                    value = option.get_attribute("value") or ""
                    haystack = f"{text} {value}".casefold()
                    if any(pattern in haystack for pattern in patterns):
                        select.select_option(value=value)
                        return True
            except Exception:  # noqa: BLE001
                continue
        return False

    def _extract_detail_candidates(self, page) -> list[OestaCandidate]:
        candidates_payload = page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]')).map(a => ({
                title: (a.innerText || a.textContent || a.getAttribute('title') || '').trim(),
                href: a.href || a.getAttribute('href') || '',
                rowText: (a.closest('tr')?.innerText || a.parentElement?.innerText || '').trim()
            }))"""
        )
        candidates: list[OestaCandidate] = []
        seen: set[str] = set()
        for item in candidates_payload:
            url = str(item.get("href", "")).strip()
            if "detail.aspx?id=" not in url.casefold():
                continue
            absolute_url = urljoin(OESTA_FIELD_SEARCH_URL, url)
            if absolute_url in seen:
                continue
            seen.add(absolute_url)
            title = _clean_text(str(item.get("title", ""))) or _title_from_detail_url(absolute_url)
            snippet = _clean_text(str(item.get("rowText", "")))
            candidates.append(OestaCandidate(title=title, url=absolute_url, snippet=snippet))
        return candidates

    def _accept_cookies(self, page, *, timeout_ms: int) -> None:
        for selector in ['button:has-text("Accept")', 'a:has-text("Accept")', 'input[value="Accept"]']:
            locator = page.locator(selector)
            if locator.count() <= 0:
                continue
            try:
                locator.first.click(timeout=min(timeout_ms, 3000))
                return
            except Exception:  # noqa: BLE001
                continue

    def _safe_wait_networkidle(self, page, *, timeout_ms: int) -> None:
        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 10000))
        except Exception:  # noqa: BLE001
            return

    def _page_title(self, page) -> str:
        try:
            return page.title().strip()
        except Exception:  # noqa: BLE001
            return ""

    def _error_result(
        self,
        *,
        source: Source,
        attempt: SearchAttempt,
        url: str,
        exc: Exception,
        diagnostic: dict[str, str] | None = None,
    ) -> SearchExecutionResult:
        diagnostic = diagnostic or {"executor": "oesta_ais_feldsuche_executor"}
        diagnostic["error"] = f"{type(exc).__name__}: {exc}"
        return SearchExecutionResult(
            attempt=attempt,
            title=attempt.label,
            url=url,
            status="error",
            payload={
                "error": diagnostic["error"],
                "executor": "oesta_ais_feldsuche_executor",
                "diagnostic_note": _diagnostic_note(diagnostic, candidate_count=0),
                "diagnostic": diagnostic,
            },
        )


def _query_text_from_attempt(attempt: SearchAttempt) -> str:
    for key in ["title", "full_name", "q", "s"]:
        value = attempt.fields.get(key, "").strip()
        if value:
            return value
    return attempt.query_text.strip()


def _selector_for_control(item: dict[str, object]) -> str:
    element_id = str(item.get("id", "")).strip()
    name = str(item.get("name", "")).strip()
    if element_id:
        return f"#{_css_escape(element_id)}"
    if name:
        escaped = name.replace('"', '\\"')
        return f'input[name="{escaped}"], textarea[name="{escaped}"]'
    index = item.get("index")
    if isinstance(index, int):
        return f'(input:not([type]), input[type="text"], textarea) >> nth={index}'
    return ""


def _css_escape(value: str) -> str:
    # Good enough for ASP.NET IDs such as ctl00_cphMainArea_txtSomething.
    return re.sub(r"([^A-Za-z0-9_-])", lambda match: "\\" + match.group(1), value)


def _candidate_result_page(
    *,
    source_name: str,
    attempt: SearchAttempt,
    result_url: str,
    candidates: list[OestaCandidate],
    raw_title: str = "",
    diagnostic: dict[str, str] | None = None,
) -> str:
    diagnostic = diagnostic or {}
    escaped_title = html.escape(raw_title or f"{source_name} - OeStA Feldsuche results")
    escaped_query = html.escape(attempt.query_text)
    escaped_url = html.escape(result_url, quote=True)
    diagnostic_items = "".join(
        f"<li><strong>{html.escape(str(key))}</strong>: {html.escape(str(value))}</li>"
        for key, value in sorted(diagnostic.items())
    )
    if not candidates:
        return f"""<!doctype html>
<html><head><title>{escaped_title}</title></head>
<body>
<h1>{escaped_title}</h1>
<p>Query: {escaped_query}</p>
<p>Result URL: {escaped_url}</p>
<p>No results found</p>
<h2>OeStA diagnostic</h2>
<ul>{diagnostic_items}</ul>
</body></html>"""

    items = []
    for candidate in candidates:
        title = html.escape(candidate.title)
        url = html.escape(candidate.url, quote=True)
        snippet = html.escape(candidate.snippet)
        items.append(f'<li><a href="{url}">{title}</a><p>{snippet}</p></li>')
    return f"""<!doctype html>
<html><head><title>{escaped_title}</title></head>
<body>
<h1>{escaped_title}</h1>
<p>Query: {escaped_query}</p>
<p>Result URL: {escaped_url}</p>
<h2>OeStA diagnostic</h2>
<ul>{diagnostic_items}</ul>
<ol>
{''.join(items)}
</ol>
</body></html>"""


def _diagnostic_note(diagnostic: dict[str, str], *, candidate_count: int) -> str:
    parts = [
        "OeStA executor",
        f"submitted={diagnostic.get('submitted', 'unknown')}",
        f"fallback={diagnostic.get('fallback', 'false')}",
        f"candidates={candidate_count}",
    ]
    if diagnostic.get("filled_control"):
        parts.append(f"filled={diagnostic['filled_control']}")
    if diagnostic.get("error"):
        parts.append(f"error={diagnostic['error']}")
    return "; ".join(parts) + "."


def _clean_text(value: str) -> str:
    return " ".join(html.unescape(value or "").split())


def _title_from_detail_url(url: str) -> str:
    match = re.search(r"[?&]ID=(\d+)", url, flags=re.I)
    if match:
        return f"OeStA detail {match.group(1)}"
    return "OeStA detail"
