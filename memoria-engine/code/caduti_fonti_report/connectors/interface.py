from __future__ import annotations

from typing import Protocol

from ..models import EvidenceClaim, PersonQuery, SourceDocument, SourceResult


class SourceConnector(Protocol):
    source_id: str

    def search_person(self, query: PersonQuery) -> list[SourceResult]:
        ...

    def fetch_detail(self, result: SourceResult) -> list[SourceDocument]:
        ...

    def extract_evidence(self, document: SourceDocument) -> list[EvidenceClaim]:
        ...
