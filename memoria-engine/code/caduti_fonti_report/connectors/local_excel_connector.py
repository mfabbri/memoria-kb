from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..extract_table_claims import claim_mappings_from_source, claims_from_row, source_document_from_row
from ..models import EvidenceClaim, PersonQuery, SearchHit, Source, SourceDocument, SourceResult
from .local_excel import build_file_url, build_row_snippet, load_excel_rows, row_matches_query
from .search_executor import SearchExecutionResult
from .search_strategy import SearchAttempt


class LocalExcelSearchStrategy:
    def build_attempts(self, *, source: Source, query: PersonQuery) -> list[SearchAttempt]:
        attempts: list[SearchAttempt] = []
        seen: set[str] = set()

        def add_attempt(attempt_id: str, label: str, query_text: str, fields: dict[str, str]) -> None:
            normalized = " ".join(query_text.split())
            if not normalized or normalized.casefold() in seen:
                return
            seen.add(normalized.casefold())
            attempts.append(
                SearchAttempt(
                    attempt_id=attempt_id,
                    label=label,
                    query_text=normalized,
                    fields=fields,
                    metadata={"source_id": source.source_id},
                )
            )

        add_attempt("canonical-name", "Nome canonico", query.full_name, {"full_name": query.full_name})
        for index, alias in enumerate(query.aliases, start=1):
            add_attempt(f"alias-{index}", "Alias", alias, {"alias": alias})

        return attempts


class LocalExcelSearchExecutor:
    def __init__(self, max_results_per_attempt: int = 3) -> None:
        self.max_results_per_attempt = max_results_per_attempt

    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        workbooks = load_excel_rows(source)
        execution_results: list[SearchExecutionResult] = []

        for workbook_path, sheet_name, rows in workbooks:
            for row in rows:
                if not row_matches_query(row, attempt.query_text, source):
                    continue
                execution_results.append(
                    SearchExecutionResult(
                        attempt=attempt,
                        title=_row_title(source, row, attempt.query_text),
                        url=build_file_url(workbook_path),
                        snippet=f"File {workbook_path.name}; foglio {sheet_name}. {build_row_snippet(row, source)}",
                        payload={
                            "workbook_path": workbook_path,
                            "sheet_name": sheet_name,
                            "row": row,
                        },
                    )
                )
                if len(execution_results) >= self.max_results_per_attempt:
                    return execution_results

        return execution_results


class LocalExcelSourceConnector:
    def __init__(
        self,
        source: Source,
        *,
        strategy: LocalExcelSearchStrategy | None = None,
        executor: LocalExcelSearchExecutor | None = None,
        run_id: str = "local-excel-connector",
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.source = source
        self.source_id = source.source_id
        self.strategy = strategy or LocalExcelSearchStrategy()
        self.executor = executor or LocalExcelSearchExecutor()
        self.run_id = run_id
        self.now_factory = now_factory or (lambda: datetime.now(UTC))
        self._last_query: PersonQuery | None = None
        self._last_execution_results: list[SearchExecutionResult] = []
        self._row_by_document_id: dict[str, dict[str, str]] = {}
        self._person_by_document_id: dict[str, PersonQuery] = {}

    def search_person(self, query: PersonQuery) -> list[SourceResult]:
        self._last_query = query
        self._last_execution_results = []
        self._row_by_document_id = {}
        self._person_by_document_id = {}

        attempts = self.strategy.build_attempts(source=self.source, query=query)
        try:
            for attempt in attempts:
                self._last_execution_results.extend(self.executor.execute(source=self.source, attempt=attempt))
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            return [
                SourceResult(
                    source_id=self.source.source_id,
                    source_name=self.source.source_name,
                    status="error",
                    note=f"{self.source.note} Errore durante la lettura del file Excel locale: {exc}.",
                    query=query.full_name,
                    search_url=self.source.search_url_builder(query.full_name),
                )
            ]

        self._last_execution_results = _dedupe_execution_results(self._last_execution_results)
        hits = [
            SearchHit(
                title=result.title,
                url=result.url,
                snippet=result.snippet,
            )
            for result in self._last_execution_results
        ]
        status = "ok" if hits else "no_results"
        note = self.source.note if hits else f"{self.source.note} Nessuna riga corrispondente trovata nei file Excel locali."
        search_url = hits[0].url if hits else self.source.search_url_builder(query.full_name)
        return [
            SourceResult(
                source_id=self.source.source_id,
                source_name=self.source.source_name,
                status=status,
                note=note,
                query=", ".join(attempt.query_text for attempt in attempts),
                search_url=search_url,
                hits=hits,
            )
        ]

    def fetch_detail(self, result: SourceResult) -> list[SourceDocument]:
        if self._last_query is None or result.status != "ok":
            return []

        access_date = self._utc_now().isoformat()
        documents: list[SourceDocument] = []
        for execution_result in self._last_execution_results:
            workbook_path = Path(execution_result.payload["workbook_path"])
            sheet_name = str(execution_result.payload["sheet_name"])
            row = _string_row(execution_result.payload["row"])
            document = source_document_from_row(
                run_id=self.run_id,
                source=self.source,
                person_query=self._last_query,
                workbook_path=workbook_path,
                sheet_name=sheet_name,
                row=row,
                access_date=access_date,
            )
            documents.append(document)
            self._row_by_document_id[document.document_id] = row
            self._person_by_document_id[document.document_id] = self._last_query
        return documents

    def extract_evidence(self, document: SourceDocument) -> list[EvidenceClaim]:
        row = self._row_by_document_id.get(document.document_id)
        person_query = self._person_by_document_id.get(document.document_id)
        if row is None or person_query is None:
            return []
        return claims_from_row(
            run_id=self.run_id,
            source=self.source,
            person_query=person_query,
            document=document,
            row=row,
            mappings=claim_mappings_from_source(self.source),
            created_at=self._utc_now().isoformat(),
        )

    def _utc_now(self) -> datetime:
        now = self.now_factory()
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)


def _row_title(source: Source, row: dict[str, str], fallback: str) -> str:
    return " ".join(
        part
        for part in [
            row.get(source.local.get("surname_column", "Cognome"), ""),
            row.get(source.local.get("given_name_column", "Nome"), ""),
        ]
        if part
    ).strip() or fallback


def _dedupe_execution_results(results: list[SearchExecutionResult]) -> list[SearchExecutionResult]:
    deduped: list[SearchExecutionResult] = []
    seen: set[tuple[str, str, str]] = set()
    for result in results:
        payload = result.payload
        row = _string_row(payload.get("row", {}))
        key = (
            str(payload.get("workbook_path", "")),
            str(payload.get("sheet_name", "")),
            row.get("__row_number__", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _string_row(row: Any) -> dict[str, str]:
    if not isinstance(row, dict):
        return {}
    return {str(key): str(value) for key, value in row.items()}
