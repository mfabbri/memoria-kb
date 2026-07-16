from __future__ import annotations

import urllib.error
import urllib.parse
from collections.abc import Callable

from ..http_utils import fetch_text
from ..models import Source
from .search_executor import SearchExecutionResult
from .search_strategy import SearchAttempt


class HttpGetFormSearchExecutor:
    def __init__(self, *, fetcher: Callable[[str, int], str] | None = None) -> None:
        self.fetcher = fetcher or fetch_text

    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        base_url = source.search_url_builder(attempt.query_text)
        query_string = urllib.parse.urlencode(attempt.fields)
        result_url = f"{base_url}?{query_string}" if query_string else base_url

        try:
            html_text = self.fetcher(result_url, source.timeout)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            return [
                SearchExecutionResult(
                    attempt=attempt,
                    title=attempt.label,
                    url=result_url,
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
