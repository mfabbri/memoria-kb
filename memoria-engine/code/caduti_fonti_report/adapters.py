from __future__ import annotations

from .models import Caduto, PersonQuery, person_query_from_caduto


def person_queries_from_caduti(caduti: list[Caduto]) -> list[PersonQuery]:
    return [person_query_from_caduto(caduto) for caduto in caduti]


def matches_name_filter(filter_text: str, *candidate_values: str) -> bool:
    filter_tokens = [token for token in filter_text.casefold().split() if token]
    if not filter_tokens:
        return True

    for candidate in candidate_values:
        candidate_tokens = candidate.casefold().split()
        if all(token in candidate_tokens for token in filter_tokens):
            return True
    return False
