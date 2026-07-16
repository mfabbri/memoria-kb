from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..models import PersonQuery, Source


@dataclass(frozen=True)
class SearchAttempt:
    attempt_id: str
    label: str
    query_text: str
    fields: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)


class SourceSearchStrategy(Protocol):
    def build_attempts(self, *, source: Source, query: PersonQuery) -> list[SearchAttempt]:
        ...


class SingleQuerySearchStrategy:
    def build_attempts(self, *, source: Source, query: PersonQuery) -> list[SearchAttempt]:
        query_text = query.full_name.strip()
        if not query_text:
            return []
        return [
            SearchAttempt(
                attempt_id="canonical-name",
                label="Nome canonico",
                query_text=query_text,
                fields={"full_name": query_text},
                metadata={"source_id": source.source_id},
            )
        ]
