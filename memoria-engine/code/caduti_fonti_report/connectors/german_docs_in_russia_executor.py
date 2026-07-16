from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urljoin

from ..http_utils import fetch_text
from ..models import Source
from .search_executor import SearchExecutionResult
from .search_strategy import SearchAttempt


class GermanDocsInRussiaSearchExecutor:
    """Hierarchy-oriented executor for German Docs in Russia.

    The public site is primarily an archival hierarchy (fond -> opis -> delo ->
    pages), not a person search engine. This executor therefore resolves the
    bounded hierarchy URL described by the source strategy and fetches that page
    so the normal result/detail logic can classify candidate nodes and create
    reviewable SourceDocument records.

    Page-image download remains a downstream detail acquisition/document
    processing step; this executor does not run OCR and does not create claims.
    """

    def __init__(self, *, fetcher: Callable[[str, int], str] | None = None) -> None:
        self.fetcher = fetcher or fetch_text

    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        url = _attempt_url(source=source, attempt=attempt)
        if not url:
            return [
                SearchExecutionResult(
                    attempt=attempt,
                    title=attempt.label,
                    url=source.search_url_builder(attempt.query_text),
                    status="manual_review_required",
                    payload={
                        "error": "No hierarchy URL available for German Docs in Russia attempt.",
                        "source_id": source.source_id,
                        "attempt_fields": dict(attempt.fields),
                    },
                )
            ]
        try:
            html_text = self.fetcher(url, source.timeout)
        except Exception as exc:  # noqa: BLE001 - executor must convert fetch failures to source results
            return [
                SearchExecutionResult(
                    attempt=attempt,
                    title=attempt.label,
                    url=url,
                    status="error",
                    payload={
                        "error": f"{type(exc).__name__}: {exc}",
                        "source_id": source.source_id,
                        "attempt_fields": dict(attempt.fields),
                    },
                )
            ]
        return [
            SearchExecutionResult(
                attempt=attempt,
                title=attempt.label,
                url=url,
                status="ok",
                payload={
                    "html": html_text,
                    "source_id": source.source_id,
                    "attempt_fields": dict(attempt.fields),
                    "access_mode": "archival_hierarchy_fetch",
                },
            )
        ]


def _attempt_url(*, source: Source, attempt: SearchAttempt) -> str:
    explicit_url = _clean(attempt.fields.get("hierarchy_url", ""))
    if explicit_url:
        return explicit_url

    # Optional registry convention for future bounded strategies:
    #   form:
    #     inventory_urls:
    #       "12475": "https://.../nodes/..."
    inventory = _clean(attempt.fields.get("inventory", ""))
    inventory_urls = source.form.get("inventory_urls")
    if inventory and isinstance(inventory_urls, dict):
        inventory_url = _clean(str(inventory_urls.get(inventory, "")))
        if inventory_url:
            return inventory_url

    for key in ("delo_url", "opis_url", "fund_url", "fund_500_url", "browse_root_url"):
        value = _clean(attempt.fields.get(key, "") or source.form.get(key, ""))
        if value:
            return value

    base_url = source.search_url_builder("")
    relative_path = _clean(attempt.fields.get("path", ""))
    if base_url and relative_path:
        return urljoin(base_url, relative_path)
    return base_url


def _clean(value: str) -> str:
    return str(value or "").strip()
