from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ..models import EvidenceClaim, PersonQuery, SearchHit, Source, SourceDocument, SourceResult
from ..search_result_logic import (
    SearchResultAssessment,
    SearchResultInterpreter,
    SearchResultSignals,
    SourceResultLogicDefinition,
    load_source_result_logic,
)
from ..source_catalog import resolve_source_catalog_root, source_level_path
from ..source_profiles import SourceSearchProfile, load_source_search_profile
from ..source_strategies import SourceSearchStrategyDefinition, load_source_search_strategy
from .cwgc_result_parser import extract_cwgc_result_signals
from .cwgc_strategy import CwgcSearchStrategy, CwgcUrlSearchExecutor
from .search_executor import SearchExecutionResult


HtmlProvider = Callable[[SearchExecutionResult], str]


class CwgcSourceConnector:
    def __init__(
        self,
        source: Source,
        *,
        profile: SourceSearchProfile | None = None,
        strategy_definition: SourceSearchStrategyDefinition | None = None,
        result_logic: SourceResultLogicDefinition | None = None,
        executor: CwgcUrlSearchExecutor | None = None,
        html_provider: HtmlProvider | None = None,
        run_id: str = "cwgc-source-connector",
        now_factory: Callable[[], datetime] | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self.source = source
        self.source_id = source.source_id
        self.repo_root = repo_root or Path.cwd()
        catalog_root = resolve_source_catalog_root(self.repo_root)
        self.profile = profile or load_source_search_profile(source_level_path(catalog_root, "source_profiles", "cwgc"))
        self.strategy_definition = strategy_definition or load_source_search_strategy(
            source_level_path(catalog_root, "source_strategies", "cwgc")
        )
        self.result_logic = result_logic or load_source_result_logic(
            source_level_path(catalog_root, "source_result_logic", "cwgc")
        )
        self.strategy = CwgcSearchStrategy(profile=self.profile, strategy_definition=self.strategy_definition)
        self.executor = executor or CwgcUrlSearchExecutor()
        self.interpreter = SearchResultInterpreter(self.result_logic)
        self.html_provider = html_provider
        self.run_id = run_id
        self.now_factory = now_factory or (lambda: datetime.now(UTC))
        self._last_query: PersonQuery | None = None
        self._assessment_by_result_key: dict[str, SearchResultAssessment] = {}

    def search_person(self, query: PersonQuery) -> list[SourceResult]:
        self._last_query = query
        self._assessment_by_result_key = {}

        results: list[SourceResult] = []
        attempts = self.strategy.build_attempts(source=self.source, query=query)
        for attempt in attempts:
            for execution_result in self.executor.execute(source=self.source, attempt=attempt):
                signals = self._signals_from_execution_result(execution_result, query=query)
                assessment = self.interpreter.interpret(signals)
                hits = [
                    SearchHit(title=link.title, url=link.url, snippet=link.snippet)
                    for link in assessment.candidate_links
                ]
                source_result = SourceResult(
                    source_id=self.source.source_id,
                    source_name=self.source.source_name,
                    status=assessment.assessment,
                    note=f"{self.source.note} {assessment.note}".strip(),
                    query=attempt.query_text,
                    search_url=execution_result.url,
                    hits=hits,
                )
                self._assessment_by_result_key[_result_key(source_result)] = assessment
                results.append(source_result)

        if not results:
            return [
                SourceResult(
                    source_id=self.source.source_id,
                    source_name=self.source.source_name,
                    status="no_results",
                    note=f"{self.source.note} Nessun tentativo CWGC generato.",
                    query=query.full_name,
                    search_url=self.source.search_url_builder(query.full_name),
                )
            ]
        return results

    def fetch_detail(self, result: SourceResult) -> list[SourceDocument]:
        assessment = self._assessment_by_result_key.get(_result_key(result))
        access_date = self._utc_now().date().isoformat()
        documents: list[SourceDocument] = []

        if result.hits:
            for index, hit in enumerate(result.hits, start=1):
                documents.append(
                    _reference_document(
                        run_id=self.run_id,
                        source=self.source,
                        title=hit.title,
                        url=hit.url,
                        access_date=access_date,
                        metadata={
                            "document_type": "candidate_reference",
                            "source_result_status": result.status,
                            "result_url": result.search_url,
                            "candidate_index": str(index),
                            "review_required": str(bool(assessment.review_required if assessment else True)).lower(),
                        },
                    )
                )
        else:
            documents.append(
                _reference_document(
                    run_id=self.run_id,
                    source=self.source,
                    title=f"CWGC search result: {result.query}",
                    url=result.search_url,
                    access_date=access_date,
                    metadata={
                        "document_type": "search_result_reference",
                        "source_result_status": result.status,
                        "review_required": str(bool(assessment.review_required if assessment else False)).lower(),
                    },
                )
            )
        return documents

    def extract_evidence(self, document: SourceDocument) -> list[EvidenceClaim]:
        return []

    def _signals_from_execution_result(
        self,
        execution_result: SearchExecutionResult,
        *,
        query: PersonQuery,
    ) -> SearchResultSignals:
        html_text = str(execution_result.payload.get("html", ""))
        if not html_text and self.html_provider is not None:
            try:
                html_text = self.html_provider(execution_result)
            except Exception as exc:  # noqa: BLE001
                return SearchResultSignals(
                    source_id=self.source.source_id,
                    engine=str(execution_result.attempt.metadata.get("engine", "cwgc_find_war_dead")),
                    error=f"{type(exc).__name__}: {exc}",
                    metadata={
                        "result_url": execution_result.url,
                        "query_is_mononym": "true" if _is_mononym(query) else "false",
                    },
                )
        if not html_text:
            return SearchResultSignals(
                source_id=self.source.source_id,
                engine=str(execution_result.attempt.metadata.get("engine", "cwgc_find_war_dead")),
                blocked=True,
                total_results=0,
                metadata={
                    "result_url": execution_result.url,
                    "query_is_mononym": "true" if _is_mononym(query) else "false",
                },
            )
        return extract_cwgc_result_signals(
            html_text=html_text,
            result_url=execution_result.url,
            result_logic=self.result_logic,
            query_is_mononym=_is_mononym(query),
        )

    def _utc_now(self) -> datetime:
        now = self.now_factory()
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)


def _reference_document(
    *,
    run_id: str,
    source: Source,
    title: str,
    url: str,
    access_date: str,
    metadata: dict[str, str],
) -> SourceDocument:
    document_id = _document_id(run_id=run_id, source_id=source.source_id, url=url)
    return SourceDocument(
        document_id=document_id,
        source_id=source.source_id,
        title=title,
        url=url,
        access_date=access_date,
        media_type="text/html",
        metadata={"access_mode": "reference_only", **metadata},
    )


def _document_id(*, run_id: str, source_id: str, url: str) -> str:
    digest = hashlib.sha256(f"{run_id}|{source_id}|{url}".encode("utf-8")).hexdigest()[:16]
    return f"{source_id}:{digest}"


def _result_key(result: SourceResult) -> str:
    return f"{result.query}|{result.search_url}"


def _is_mononym(query: PersonQuery) -> bool:
    if query.family_name.strip():
        return False
    return bool(query.full_name.strip() or query.given_name.strip())
