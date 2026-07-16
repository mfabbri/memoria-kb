from __future__ import annotations

import atexit
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
import re
from urllib.parse import urlparse

import yaml

from ..archival_html_cache import ArchivalHtmlCache
from ..authenticated_session import ManualAuthenticatedPlaywrightSession, source_uses_manual_authenticated_session
from ..detail_page_logic import DetailPageAssessment, DetailPageInterpreter, DetailPageSignals, extract_detail_page_signals
from ..http_utils import fetch_text, page_title, strip_tags
from ..models import EvidenceClaim, PersonQuery, SearchHit, Source, SourceDocument, SourceResult
from ..search_result_logic import CandidateLink, SearchResultAssessment, SearchResultInterpreter, SearchResultSignals
from ..source_definitions import SourceDefinition, load_source_definition
from ..source_strategies import build_attempts_from_strategy_definition
from .cwgc_result_parser import extract_cwgc_result_signals
from .cwgc_strategy import CwgcUrlSearchExecutor
from .generic_result_parser import extract_generic_result_signals
from .german_docs_in_russia_executor import GermanDocsInRussiaSearchExecutor
from .http_get_form_executor import HttpGetFormSearchExecutor
from .playwright_form_executor import PlaywrightFormSearchExecutor
from .storia_memoria_bo_executor import StoriaMemoriaBoSearchExecutor, fetch_storia_memoria_bo_detail_html
from .search_executor import PostFormSearchExecutor, ReferenceOnlySearchExecutor, SearchExecutionResult, UrlTemplateFetchSearchExecutor
from .bundesarchiv_invenio_executor import BundesarchivInvenioPlaywrightExecutor


SignalsParser = Callable[[SearchExecutionResult, PersonQuery], SearchResultSignals]
HtmlProvider = Callable[[SearchExecutionResult], str]
DetailHtmlProvider = Callable[[str], str]
AuthenticatedSessionFactory = Callable[[Source, Path], ManualAuthenticatedPlaywrightSession]


class UniformSourceConnector:
    def __init__(
        self,
        source: Source,
        *,
        source_definition: SourceDefinition | None = None,
        executor: HttpGetFormSearchExecutor | CwgcUrlSearchExecutor | PlaywrightFormSearchExecutor | None = None,
        signals_parser: SignalsParser | None = None,
        html_provider: HtmlProvider | None = None,
        detail_html_provider: DetailHtmlProvider | None = None,
        authenticated_session_factory: AuthenticatedSessionFactory | None = None,
        run_id: str = "uniform-source-connector",
        now_factory: Callable[[], datetime] | None = None,
        repo_root: Path | None = None,
        max_search_attempts: int = 0,
    ) -> None:
        self.source = source
        self.source_id = source.source_id
        self.repo_root = repo_root or Path.cwd()
        self.definition = source_definition or load_source_definition(source, repo_root=self.repo_root)
        self.interpreter = SearchResultInterpreter(self.definition.result_logic)
        self.executor = executor or self._build_executor()
        self.signals_parser = signals_parser or self._default_signals_parser
        self.html_provider = html_provider
        self.detail_html_provider = detail_html_provider
        self.authenticated_session_factory = authenticated_session_factory or (
            lambda source, repo_root: ManualAuthenticatedPlaywrightSession(source, repo_root=repo_root)
        )
        self.run_id = run_id
        self.now_factory = now_factory or (lambda: datetime.now(UTC))
        self.max_search_attempts = max(0, int(max_search_attempts))
        self._assessment_by_result_key: dict[str, SearchResultAssessment] = {}
        self._detail_assessment_by_document_id: dict[str, DetailPageAssessment] = {}
        self._claims_by_document_id: dict[str, list[EvidenceClaim]] = {}
        self._authenticated_detail_session: ManualAuthenticatedPlaywrightSession | None = None
        self._authenticated_detail_session_confirmed = False
        self._detail_html_cache_by_url: dict[str, str] = {}
        self._manual_review_detail_urls: set[str] = set()
        self._last_query: PersonQuery | None = None
        atexit.register(self.close)

    def search_person(self, query: PersonQuery) -> list[SourceResult]:
        self._last_query = query
        self._assessment_by_result_key = {}
        self._detail_assessment_by_document_id = {}
        self._claims_by_document_id = {}
        self._detail_html_cache_by_url = {}
        self._manual_review_detail_urls = set()
        results: list[SourceResult] = []
        cached_hits = self._cached_detail_hits_for_query(query)
        if cached_hits:
            status = "candidate_results"
            if len(cached_hits) > self.definition.result_logic.candidate_limit:
                status = "candidate_results_truncated"
            result = SourceResult(
                source_id=self.source.source_id,
                source_name=self.source.source_name,
                status=status,
                note=(
                    f"{self.source.note.strip()} "
                    "Candidati recuperati dalla cache archivistica locale prima della ricerca online."
                ).strip(),
                query=f'cache-lookup; full_name="{query.full_name}"',
                search_url=self.source.search_url_builder(query.full_name),
                hits=cached_hits[: self.definition.result_logic.candidate_limit],
            )
            self._assessment_by_result_key[_result_key(result)] = SearchResultAssessment(
                assessment=status,
                review_required=True,
                candidate_links=[CandidateLink(title=hit.title, url=hit.url, snippet=hit.snippet) for hit in result.hits],
                total_results=len(cached_hits),
                shown_results=min(len(cached_hits), self.definition.result_logic.candidate_limit),
                note="Candidati recuperati da cache archivistica locale.",
                metadata={"rule_id": "archival_cache_lookup", "source_id": self.source.source_id},
            )
            return [result]
        attempts = build_attempts_from_strategy_definition(
            definition=self.definition.strategy_definition,
            source=self.source,
            query=query,
            profile=self.definition.profile,
        )
        if self.max_search_attempts > 0:
            attempts = attempts[: self.max_search_attempts]

        for attempt in attempts:
            for execution_result in self.executor.execute(source=self.source, attempt=attempt):
                self._remember_detail_html_from_execution(execution_result)
                signals = self.signals_parser(execution_result, query)
                assessment = self.interpreter.interpret(signals)
                if self._should_retry_search_with_authenticated_session(assessment):
                    authenticated_html = self._fetch_authenticated_search_html(execution_result.url)
                    authenticated_execution_result = SearchExecutionResult(
                        attempt=execution_result.attempt,
                        title=execution_result.title,
                        url=execution_result.url,
                        status=execution_result.status,
                        payload={"html": authenticated_html},
                    )
                    signals = self.signals_parser(authenticated_execution_result, query)
                    assessment = self.interpreter.interpret(signals)
                hits = [SearchHit(title=link.title, url=link.url, snippet=link.snippet) for link in assessment.candidate_links]
                note = f"{self.source.note.strip()} {assessment.note}".strip()
                result = SourceResult(
                    source_id=self.source.source_id,
                    source_name=self.source.source_name,
                    status=assessment.assessment,
                    note=note,
                    query=attempt.query_text,
                    search_url=execution_result.url,
                    hits=hits,
                )
                self._assessment_by_result_key[_result_key(result)] = assessment
                results.append(result)

        if results:
            return results
        return [
            SourceResult(
                source_id=self.source.source_id,
                source_name=self.source.source_name,
                status="no_results",
                note=f"{self.source.note} Nessun tentativo generato dal motore uniforme.".strip(),
                query=query.full_name,
                search_url=self.source.search_url_builder(query.full_name),
            )
        ]

    def fetch_detail(self, result: SourceResult) -> list[SourceDocument]:
        assessment = self._assessment_by_result_key.get(_result_key(result))
        access_date = self._utc_now().date().isoformat()

        if self.definition.detail_logic is None or not result.hits:
            return _reference_documents(
                run_id=self.run_id,
                source=self.source,
                result=result,
                access_date=access_date,
                assessment=assessment,
                source_definition_id=self.definition.source_id,
                profile_id=self._current_profile_id(),
                profile_source_file=self._current_profile_source_file(),
            )

        detail_interpreter = DetailPageInterpreter(self.definition.detail_logic)
        detail_html_by_url = self._detail_html_by_url(result)
        documents: list[SourceDocument] = []
        for index, hit in enumerate(result.hits, start=1):
            signals = self._detail_signals_from_hit(hit, detail_html_by_url=detail_html_by_url)
            detail_assessment = detail_interpreter.interpret(signals)
            signal_metadata = {key: value for key, value in signals.metadata.items() if key != "result_url"}
            document = _detail_document(
                run_id=self.run_id,
                source=self.source,
                title=signals.heading or hit.title,
                url=hit.url,
                access_date=access_date,
                raw_text=signals.body_text,
                metadata={
                    "document_type": "detail_document",
                    "profile_id": self._current_profile_id(),
                    "profile_source_file": self._current_profile_source_file(),
                    "source_result_status": result.status,
                    "result_url": result.search_url,
                    "candidate_index": str(index),
                    "detail_assessment": detail_assessment.assessment,
                    "review_required": str(detail_assessment.review_required).lower(),
                    "source_definition": self.definition.source_id,
                    "detail_extracted_fields_json": json.dumps(detail_assessment.extracted_fields, ensure_ascii=False),
                    **signal_metadata,
                },
            )
            self._detail_assessment_by_document_id[document.document_id] = detail_assessment
            self._claims_by_document_id[document.document_id] = self._claims_from_detail_assessment(
                document=document,
                detail_assessment=detail_assessment,
            )
            documents.append(document)
        return documents

    def extract_evidence(self, document: SourceDocument) -> list[EvidenceClaim]:
        return list(self._claims_by_document_id.get(document.document_id, []))

    def close(self) -> None:
        executor_close = getattr(self.executor, "close", None)
        if callable(executor_close):
            try:
                executor_close()
            except Exception:
                pass

        if self._authenticated_detail_session is not None:
            try:
                self._authenticated_detail_session.close()
            except Exception as exc:  # noqa: BLE001 - close must not fail the report
                # The authenticated session may already have been closed by
                # Playwright/browser lifecycle events. The source result has
                # already been produced at this point, so cleanup errors are
                # intentionally ignored here.
                print(
                    f"[warning] cleanup autenticato ignorato per {self.source.source_id}: "
                    f"{type(exc).__name__}: {exc}"
                )
            finally:
                self._authenticated_detail_session = None
                self._authenticated_detail_session_confirmed = False

    def _detail_signals_from_hit(self, hit: SearchHit, *, detail_html_by_url: dict[str, str] | None = None) -> DetailPageSignals:
        if hit.url in self._manual_review_detail_urls:
            return DetailPageSignals(
                source_id=self.source.source_id,
                engine=self.definition.detail_logic.engine if self.definition.detail_logic else "",
                heading=hit.title,
                body_text=(
                    "Permalink dettaglio costruito deterministicamente ma non validato live; "
                    "richiede revisione manuale prima di produrre claim."
                ),
                blocked=True,
                metadata={"detail_url": hit.url, "detail_status": "unverified_permalink_manual_review"},
            )
        try:
            html_text = ""
            if detail_html_by_url is not None:
                html_text = detail_html_by_url.get(hit.url, "")
            if not html_text:
                html_text = self._fetch_detail_html(hit.url)
        except Exception as exc:  # noqa: BLE001
            return DetailPageSignals(
                source_id=self.source.source_id,
                engine=self.definition.detail_logic.engine if self.definition.detail_logic else "",
                error=f"{type(exc).__name__}: {exc}",
                metadata={"detail_url": hit.url},
            )

        return extract_detail_page_signals(
            source_id=self.source.source_id,
            engine=self.definition.detail_logic.engine if self.definition.detail_logic else "",
            html_text=html_text,
            detail_logic=self.definition.detail_logic,
            result_url=hit.url,
        )

    def _detail_html_by_url(self, result: SourceResult) -> dict[str, str]:
        if not result.hits:
            return {}
        fetchable_hits = [hit for hit in result.hits if hit.url not in self._manual_review_detail_urls]
        html_by_url: dict[str, str] = {
            hit.url: self._detail_html_cache_by_url[hit.url]
            for hit in fetchable_hits
            if hit.url in self._detail_html_cache_by_url
        }
        if self.detail_html_provider is not None:
            html_by_url.update({hit.url: self.detail_html_provider(hit.url) for hit in fetchable_hits if hit.url not in html_by_url})
            return html_by_url
        if not source_uses_manual_authenticated_session(self.source):
            return html_by_url
        cached_html_by_url = self._cached_html_by_url(fetchable_hits)
        cached_html_by_url.update(html_by_url)
        html_by_url = cached_html_by_url
        missing_hits = [hit for hit in fetchable_hits if hit.url not in html_by_url]
        if not missing_hits:
            return html_by_url

        session = self._ensure_authenticated_detail_session()
        needs_authenticated_fetch = any(not session.has_cached_html(hit.url) for hit in missing_hits)
        if needs_authenticated_fetch and not self._authenticated_detail_session_confirmed:
            session.ensure_authenticated()
            self._authenticated_detail_session_confirmed = True
        for hit in missing_hits:
            html_by_url[hit.url] = session.fetch_html(hit.url)
        return html_by_url

    def _remember_detail_html_from_execution(self, execution_result: SearchExecutionResult) -> None:
        if str(execution_result.payload.get("storia_memoria_bo_resolution", "")) == "direct_person_permalink_unverified":
            permalink = str(execution_result.payload.get("storia_memoria_bo_permalink", "")).strip()
            if permalink:
                self._manual_review_detail_urls.add(permalink)
        detail_html_by_url = execution_result.payload.get("detail_html_by_url")
        if not isinstance(detail_html_by_url, dict):
            return
        for url, html_text in detail_html_by_url.items():
            if isinstance(url, str) and isinstance(html_text, str) and url.strip() and html_text.strip():
                self._detail_html_cache_by_url[url] = html_text

    def _should_retry_search_with_authenticated_session(self, assessment: SearchResultAssessment) -> bool:
        # Dedicated Playwright executors own the browser/session lifecycle.
        # Do not trigger the generic authenticated fallback, otherwise the
        # connector can try to start a second Playwright Sync API context while
        # the executor context is still alive, which on Windows may fail with:
        # "It looks like you are using Playwright Sync API inside the asyncio loop."
        if self.definition.executor_id == "bundesarchiv_invenio_playwright_executor":
            return False
        return (
            assessment.assessment == "blocked_or_dynamic"
            and not assessment.candidate_links
            and source_uses_manual_authenticated_session(self.source)
        )

    def _fetch_detail_html(self, url: str) -> str:
        if self.detail_html_provider is not None:
            return self.detail_html_provider(url)
        if self.source.source_id == "storia_memoria_bo":
            return fetch_storia_memoria_bo_detail_html(
                url,
                timeout=self.source.timeout,
                browser_channel=self.source.auth.get("browser_channel", ""),
                browser_user_agent=self.source.auth.get("browser_user_agent", ""),
            )
        return fetch_text(url, self.source.timeout)

    def _fetch_authenticated_search_html(self, url: str) -> str:
        session = self._ensure_authenticated_detail_session()
        if not self._authenticated_detail_session_confirmed:
            session.ensure_authenticated()
            self._authenticated_detail_session_confirmed = True
        return session.fetch_html(url, allow_cache=False)

    def _cached_html_by_url(self, hits: list[SearchHit]) -> dict[str, str]:
        if _as_bool(self.source.auth.get("force_refresh_authenticated_cache", "false")):
            return {}
        cache = _archival_cache_for_source(self.source, self.repo_root)
        if cache is None:
            return {}
        html_by_url: dict[str, str] = {}
        for hit in hits:
            cached_html = cache.read(hit.url)
            if cached_html is not None:
                html_by_url[hit.url] = cached_html
        return html_by_url

    def _cached_detail_hits_for_query(self, query: PersonQuery) -> list[SearchHit]:
        if not source_uses_manual_authenticated_session(self.source):
            return []
        if _as_bool(self.source.auth.get("force_refresh_authenticated_cache", "false")):
            return []
        cache_root = self.source.auth.get("archival_cache_root", "").strip()
        if not cache_root:
            return []
        host = urlparse(self.source.auth.get("auth_check_url", "").strip() or self.source.search_url_builder("")).netloc
        if not host:
            return []

        cache_host_dir = self.repo_root / cache_root / host
        if not cache_host_dir.exists():
            return []

        normalized_query = _normalize_person_name(query.full_name)
        query_tokens = set(normalized_query.split())
        exact_hits: list[SearchHit] = []
        fuzzy_hits: list[SearchHit] = []
        seen_urls: set[str] = set()

        for document_yaml in sorted(cache_host_dir.rglob("document.yaml")):
            payload = yaml.safe_load(document_yaml.read_text(encoding="utf-8")) or {}
            url = str(payload.get("url", "")).strip()
            if "/persona/" not in url or url in seen_urls:
                continue

            html_path_value = str(payload.get("html_path", "")).strip()
            html_path = Path(html_path_value) if html_path_value else document_yaml.with_name("content.html")
            if not html_path.exists():
                continue
            html_text = html_path.read_text(encoding="utf-8")
            title = page_title(html_text).strip() or _extract_first_heading(html_text)
            if not title:
                continue

            normalized_title = _normalize_person_name(title)
            haystack_tokens = set(f"{normalized_title} {_normalize_person_name(strip_tags(html_text)[:1000])}".split())
            hit = SearchHit(title=title, url=url, snippet="Scheda presente in cache archivistica")

            if normalized_title == normalized_query:
                seen_urls.add(url)
                exact_hits.append(hit)
                continue
            if query_tokens and query_tokens.issubset(haystack_tokens):
                seen_urls.add(url)
                fuzzy_hits.append(hit)

        return exact_hits or fuzzy_hits

    def _ensure_authenticated_detail_session(self) -> ManualAuthenticatedPlaywrightSession:
        if self._authenticated_detail_session is None:
            session = self.authenticated_session_factory(self.source, self.repo_root)
            session.__enter__()
            self._authenticated_detail_session = session
        return self._authenticated_detail_session

    def _claims_from_detail_assessment(
        self,
        *,
        document: SourceDocument,
        detail_assessment: DetailPageAssessment,
    ) -> list[EvidenceClaim]:
        if self.definition.detail_logic is None:
            return []

        created_at = self._utc_now().isoformat()
        claims: list[EvidenceClaim] = []
        for mapping in self.definition.detail_logic.claim_mappings:
            value = detail_assessment.extracted_fields.get(mapping.signal_field, "").strip()
            if not value:
                continue
            subject_name = detail_assessment.extracted_fields.get("person_name", document.title).strip() or document.title
            subject_id = document.metadata.get("profile_id", "").strip() or _subject_id_for_name(subject_name)
            claims.append(
                EvidenceClaim(
                    claim_id=_claim_id(
                        run_id=self.run_id,
                        source_id=self.source.source_id,
                        document_id=document.document_id,
                        subject_id=subject_id,
                        field=mapping.field,
                        value=value,
                    ),
                    subject_id=subject_id,
                    field=mapping.field,
                    value=value,
                    normalized_value=value.casefold(),
                    source_document_id=document.document_id,
                    source_url=document.url,
                    quote=value,
                    extraction_method="detail_logic",
                    confidence=mapping.confidence,
                    review_status="unreviewed",
                    created_at=created_at,
                )
            )
        return claims

    def _current_profile_id(self) -> str:
        if self._last_query is None:
            return ""
        return self._last_query.metadata.get("profile_id", "").strip()

    def _current_profile_source_file(self) -> str:
        if self._last_query is None:
            return ""
        return self._last_query.metadata.get("profile_source_file", "").strip()

    def _build_executor(self) -> HttpGetFormSearchExecutor | CwgcUrlSearchExecutor | PlaywrightFormSearchExecutor | UrlTemplateFetchSearchExecutor | PostFormSearchExecutor | ReferenceOnlySearchExecutor | GermanDocsInRussiaSearchExecutor:
        if self.definition.executor_id == "http_get_form_executor":
            return HttpGetFormSearchExecutor()
        if self.definition.executor_id == "url_only_executor":
            return CwgcUrlSearchExecutor()
        if self.definition.executor_id == "playwright_form_executor":
            return PlaywrightFormSearchExecutor()
        if self.definition.executor_id == "storia_memoria_bo_executor":
            return StoriaMemoriaBoSearchExecutor()
        if self.definition.executor_id == "url_template_fetch_executor":
            return UrlTemplateFetchSearchExecutor()
        if self.definition.executor_id == "post_form_executor":
            return PostFormSearchExecutor()
        if self.definition.executor_id == "reference_only_executor":
            return ReferenceOnlySearchExecutor()
        if self.definition.executor_id == "bundesarchiv_invenio_playwright_executor":
            return BundesarchivInvenioPlaywrightExecutor(repo_root=self.repo_root)
        if self.definition.executor_id == "german_docs_in_russia_executor":
            return GermanDocsInRussiaSearchExecutor()
        raise ValueError(f"Executor non supportato dal motore uniforme: {self.definition.executor_id}")

    def _default_signals_parser(self, execution_result: SearchExecutionResult, query: PersonQuery) -> SearchResultSignals:
        html_text = str(execution_result.payload.get("html", ""))
        if not html_text and self.html_provider is not None:
            try:
                html_text = self.html_provider(execution_result)
            except Exception as exc:  # noqa: BLE001
                return SearchResultSignals(
                    source_id=self.source.source_id,
                    engine=str(execution_result.attempt.metadata.get("engine", self.definition.result_logic.engine)),
                    error=f"{type(exc).__name__}: {exc}",
                    metadata={
                        "result_url": execution_result.url,
                        "query_is_mononym": "true" if _is_mononym(query) else "false",
                    },
                )
        if execution_result.payload.get("error"):
            return SearchResultSignals(
                source_id=self.source.source_id,
                engine=str(execution_result.attempt.metadata.get("engine", self.definition.result_logic.engine)),
                error=str(execution_result.payload["error"]),
                metadata={
                    "result_url": execution_result.url,
                    "query_is_mononym": "true" if _is_mononym(query) else "false",
                },
            )
        if not html_text:
            return SearchResultSignals(
                source_id=self.source.source_id,
                engine=str(execution_result.attempt.metadata.get("engine", self.definition.result_logic.engine)),
                blocked=True,
                metadata={
                    "result_url": execution_result.url,
                    "query_is_mononym": "true" if _is_mononym(query) else "false",
                },
            )
        if self.definition.result_parser_id != "generic_result_page_parser":
            if self.definition.result_parser_id == "cwgc_result_parser":
                return extract_cwgc_result_signals(
                    html_text=html_text,
                    result_url=execution_result.url,
                    result_logic=self.definition.result_logic,
                    query_is_mononym=_is_mononym(query),
                )
            raise ValueError(f"Parser risultati non supportato: {self.definition.result_parser_id}")
        return extract_generic_result_signals(
            source_id=self.source.source_id,
            engine=str(execution_result.attempt.metadata.get("engine", self.definition.result_logic.engine)),
            html_text=html_text,
            result_url=execution_result.url,
            result_logic=self.definition.result_logic,
            query_is_mononym=_is_mononym(query),
        )

    def _utc_now(self) -> datetime:
        now = self.now_factory()
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)


def _reference_documents(
    *,
    run_id: str,
    source: Source,
    result: SourceResult,
    access_date: str,
    assessment: SearchResultAssessment | None,
    source_definition_id: str,
    profile_id: str = "",
    profile_source_file: str = "",
) -> list[SourceDocument]:
    if result.hits:
        return [
            _reference_document(
                run_id=run_id,
                source=source,
                title=hit.title,
                url=hit.url,
                access_date=access_date,
                metadata={
                    "document_type": "candidate_reference",
                    "profile_id": profile_id,
                    "profile_source_file": profile_source_file,
                    "source_result_status": result.status,
                    "result_url": result.search_url,
                    "candidate_index": str(index),
                    "review_required": str(bool(assessment.review_required if assessment else True)).lower(),
                    "source_definition": source_definition_id,
                },
            )
            for index, hit in enumerate(result.hits, start=1)
        ]

    return [
        _reference_document(
            run_id=run_id,
            source=source,
            title=f"{source.source_name}: {result.query}",
            url=result.search_url,
            access_date=access_date,
            metadata={
                "document_type": "search_result_reference",
                "profile_id": profile_id,
                "profile_source_file": profile_source_file,
                "source_result_status": result.status,
                "review_required": str(bool(assessment.review_required if assessment else False)).lower(),
                "source_definition": source_definition_id,
            },
        )
    ]


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


def _detail_document(
    *,
    run_id: str,
    source: Source,
    title: str,
    url: str,
    access_date: str,
    raw_text: str,
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
        raw_text=raw_text,
        metadata={"access_mode": "detail_page", **metadata},
    )


def _document_id(*, run_id: str, source_id: str, url: str) -> str:
    digest = hashlib.sha256(f"{run_id}|{source_id}|{url}".encode("utf-8")).hexdigest()[:16]
    return f"{source_id}:{digest}"


def _claim_id(*, run_id: str, source_id: str, document_id: str, subject_id: str, field: str, value: str) -> str:
    digest = hashlib.sha256(f"{run_id}|{source_id}|{document_id}|{subject_id}|{field}|{value.casefold()}".encode("utf-8")).hexdigest()[:16]
    return f"claim:{source_id}:{digest}"


def _result_key(result: SourceResult) -> str:
    return f"{result.query}|{result.search_url}"


def _subject_id_for_name(name: str) -> str:
    slug = "-".join(token for token in "".join(ch.lower() if ch.isalnum() else "-" for ch in name).split("-") if token)
    return f"person:{slug or 'unknown'}"


def _is_mononym(query: PersonQuery) -> bool:
    if query.family_name.strip():
        return False
    return bool(query.full_name.strip() or query.given_name.strip())


def _as_bool(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "si", "sì"}


def _normalize_person_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.casefold())
    return " ".join(token for token in cleaned.split() if token)


def _extract_first_heading(html_text: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.I | re.S)
    if not match:
        return ""
    return strip_tags(match.group(1)).strip()


def _archival_cache_for_source(source: Source, repo_root: Path) -> ArchivalHtmlCache | None:
    cache_root = source.auth.get("archival_cache_root", "").strip()
    if not cache_root:
        return None
    return ArchivalHtmlCache(repo_root / cache_root)
