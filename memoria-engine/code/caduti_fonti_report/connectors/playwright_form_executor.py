from __future__ import annotations

from collections.abc import Callable

from ..models import Source
from .search_executor import SearchExecutionResult
from .search_strategy import SearchAttempt


def _get_playwright_factory():
    from playwright.sync_api import sync_playwright

    return sync_playwright


class PlaywrightFormSearchExecutor:
    def __init__(
        self,
        *,
        playwright_factory: Callable[[], object] | None = None,
    ) -> None:
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

        try:
            playwright_factory = self.playwright_factory()
        except ImportError as exc:
            return [
                SearchExecutionResult(
                    attempt=attempt,
                    title=attempt.label,
                    url=advanced_search_url,
                    status="error",
                    payload={"error": f"{type(exc).__name__}: {exc}"},
                )
            ]

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
                self._run_attempt(page=page, source=source, attempt=attempt, timeout_ms=timeout_ms)
                result_url = page.url
                html_text = page.content()
                context.close()
                browser.close()
        except Exception as exc:  # noqa: BLE001
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

    def _run_attempt(self, *, page, source: Source, attempt: SearchAttempt, timeout_ms: int) -> None:
        advanced_search_url = source.auth.get(
            "advanced_search_url",
            source.search_url_builder(attempt.query_text),
        ).strip()
        form_selector = source.auth.get("form_selector", "#views-exposed-form-persone-block-2").strip()
        submit_selector = source.auth.get("submit_selector", "#edit-submit-persone").strip()

        page.goto(advanced_search_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
        self._open_people_tab_if_needed(page, source=source)

        form = page.locator(form_selector)
        for field_name, value in attempt.fields.items():
            selector = source.auth.get(f"field_selector_{field_name}", "").strip() or f'input[name="{field_name}"]'
            form.locator(selector).fill(value)
        form.locator(submit_selector).click()
        page.wait_for_load_state("networkidle", timeout=timeout_ms)

    def _open_people_tab_if_needed(self, page, *, source: Source) -> None:
        form_selector = source.auth.get("form_selector", "#views-exposed-form-persone-block-2").strip()
        if page.locator(form_selector).count() > 0:
            return

        tab_selector = source.auth.get("people_tab_selector", 'a[href*="/ricerca-avanzata/persone"]').strip()
        if tab_selector and page.locator(tab_selector).count() > 0:
            page.locator(tab_selector).first.click()
            page.wait_for_load_state("networkidle", timeout=60000)
