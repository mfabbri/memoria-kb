from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
import urllib.error
import urllib.parse
import urllib.request

from ..models import Source
from .search_strategy import SearchAttempt


@dataclass
class SearchExecutionResult:
    attempt: SearchAttempt
    title: str
    url: str
    snippet: str = ""
    status: str = "ok"
    payload: dict[str, Any] = field(default_factory=dict)


class SearchExecutor(Protocol):
    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        ...


class UrlTemplateFetchSearchExecutor:
    def __init__(self, *, fetcher=None) -> None:
        from ..http_utils import fetch_text
        self.fetcher = fetcher or fetch_text

    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        url = source.search_url_builder(attempt.fields.get("q", "") or attempt.fields.get("s", "") or attempt.query_text)
        try:
            html_text = self.fetcher(url, source.timeout)
        except Exception as exc:  # noqa: BLE001
            return [SearchExecutionResult(attempt=attempt, title=attempt.label, url=url, status="error", payload={"error": f"{type(exc).__name__}: {exc}"})]
        return [SearchExecutionResult(attempt=attempt, title=attempt.label, url=url, status="ok", payload={"html": html_text})]


class PostFormSearchExecutor:
    def __init__(self, *, fetcher=None) -> None:
        self.fetcher = fetcher or self._post_form

    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        url = source.search_url_builder("")
        form_data = {key: value for key, value in attempt.fields.items() if value}
        try:
            result_url, html_text = self.fetcher(url, form_data, source.timeout)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            return [
                SearchExecutionResult(
                    attempt=attempt,
                    title=attempt.label,
                    url=url,
                    status="error",
                    payload={"error": f"{type(exc).__name__}: {exc}", "form_data": form_data},
                )
            ]
        return [
            SearchExecutionResult(
                attempt=attempt,
                title=attempt.label,
                url=result_url,
                status="ok",
                payload={"html": html_text, "form_data": form_data},
            )
        ]

    @staticmethod
    def _post_form(url: str, form_data: dict[str, str], timeout: int) -> tuple[str, str]:
        from ..http_utils import USER_AGENT

        encoded = urllib.parse.urlencode(form_data).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.geturl(), response.read().decode(charset, errors="ignore")


class ReferenceOnlySearchExecutor:
    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        url = source.search_url_builder(attempt.fields.get("q", "") or attempt.fields.get("s", "") or attempt.query_text)
        return [
            SearchExecutionResult(
                attempt=attempt,
                title=attempt.label,
                url=url,
                snippet="URL di ricerca o riferimento pronto per verifica manuale.",
                status="search_url_ready",
                payload={"access_mode": "reference_only", "source_id": source.source_id},
            )
        ]
