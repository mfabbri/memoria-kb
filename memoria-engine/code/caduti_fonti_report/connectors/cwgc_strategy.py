from __future__ import annotations

from .cwgc import build_cwgc_search_url
from .http_sources import split_person_name
from .search_executor import SearchExecutionResult
from .search_strategy import SearchAttempt
from ..models import PersonQuery, Source
from ..source_profiles import SourceSearchProfile
from ..source_strategies import SourceSearchStrategyDefinition, build_attempts_from_strategy_definition


DEFAULT_CWGC_RESULTS_BASE_URL = "https://www.cwgc.org/find-records/find-war-dead/search-results/"


class CwgcSearchStrategy:
    def __init__(
        self,
        profile: SourceSearchProfile | None = None,
        strategy_definition: SourceSearchStrategyDefinition | None = None,
    ) -> None:
        self.profile = profile
        self.strategy_definition = strategy_definition

    def build_attempts(self, *, source: Source, query: PersonQuery) -> list[SearchAttempt]:
        if self.strategy_definition is not None:
            attempts = build_attempts_from_strategy_definition(
                definition=self.strategy_definition,
                source=source,
                query=_query_with_name_parts(source, query),
                profile=self.profile,
            )
            return attempts[: _max_attempts(source, default=len(attempts))]

        given_name, surname = _name_parts(source, query)
        war_select = _war_select_default(source, self.profile)
        attempts: list[SearchAttempt] = []

        if surname and given_name:
            attempts.append(
                _attempt(
                    source=source,
                    attempt_id="cognome-nome-ww2",
                    label="Cognome + nome, Seconda guerra mondiale",
                    surname=surname,
                    forename=given_name,
                    war_select=war_select,
                )
            )
            attempts.append(
                _attempt(
                    source=source,
                    attempt_id="solo-cognome-ww2",
                    label="Solo cognome, Seconda guerra mondiale",
                    surname=surname,
                    forename="",
                    war_select=war_select,
                )
            )
        elif given_name:
            attempts.append(
                _attempt(
                    source=source,
                    attempt_id="mononimo-come-cognome-ww2",
                    label="Mononimo nel campo cognome, Seconda guerra mondiale",
                    surname=given_name,
                    forename="",
                    war_select=war_select,
                )
            )
            attempts.append(
                _attempt(
                    source=source,
                    attempt_id="mononimo-come-nome-ww2",
                    label="Mononimo nel campo nome, Seconda guerra mondiale",
                    surname="",
                    forename=given_name,
                    war_select=war_select,
                )
            )

        return attempts[: _max_attempts(source, default=len(attempts))]


class CwgcUrlSearchExecutor:
    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        base_url = source.form.get("results_base_url", DEFAULT_CWGC_RESULTS_BASE_URL).strip()
        url = build_cwgc_search_url(
            base_url,
            surname=attempt.fields.get("Surname", ""),
            forename=attempt.fields.get("Forename", ""),
            initials=attempt.fields.get("Initials", ""),
            war_select=attempt.fields.get("WarSelect", "2"),
        )
        return [
            SearchExecutionResult(
                attempt=attempt,
                title=attempt.query_text,
                url=url,
                snippet="URL CWGC Find War Dead pronto per verifica manuale/interattiva.",
                status="search_url_ready",
                payload={"access_mode": "url_only", "source_id": source.source_id},
            )
        ]


def _attempt(
    *,
    source: Source,
    attempt_id: str,
    label: str,
    surname: str,
    forename: str,
    war_select: str,
) -> SearchAttempt:
    fields = {
        "Surname": surname,
        "Forename": forename,
        "Initials": "",
        "WarSelect": war_select,
    }
    return SearchAttempt(
        attempt_id=attempt_id,
        label=label,
        query_text=_attempt_query_description(attempt_id=attempt_id, fields=fields),
        fields=fields,
        metadata={"source_id": source.source_id, "engine": "cwgc_find_war_dead"},
    )


def _attempt_query_description(*, attempt_id: str, fields: dict[str, str]) -> str:
    parts = [attempt_id]
    if fields.get("Surname"):
        parts.append(f'Surname="{fields["Surname"]}"')
    if fields.get("Forename"):
        parts.append(f'Forename="{fields["Forename"]}"')
    if fields.get("Initials"):
        parts.append(f'Initials="{fields["Initials"]}"')
    if fields.get("WarSelect"):
        parts.append(f'WarSelect="{fields["WarSelect"]}"')
    return "; ".join(parts)


def _name_parts(source: Source, query: PersonQuery) -> tuple[str, str]:
    if query.given_name or query.family_name:
        return query.given_name.strip(), query.family_name.strip()
    return split_person_name(query.full_name, source.form.get("name_order", "surname_first"))


def _query_with_name_parts(source: Source, query: PersonQuery) -> PersonQuery:
    given_name, family_name = _name_parts(source, query)
    return PersonQuery(
        full_name=query.full_name,
        given_name=given_name,
        family_name=family_name,
        aliases=query.aliases,
        birth_date=query.birth_date,
        birth_place=query.birth_place,
        death_date=query.death_date,
        death_place=query.death_place,
        formation=query.formation,
        event_hint=query.event_hint,
        place_hint=query.place_hint,
        source_hints=query.source_hints,
        metadata=query.metadata,
    )


def _war_select_default(source: Source, profile: SourceSearchProfile | None) -> str:
    if source.form.get("war_select", "").strip():
        return source.form["war_select"].strip()
    if profile is not None:
        for field in profile.fields:
            if field.field_id == "WarSelect" and field.default.strip():
                return field.default.strip()
    return "2"


def _max_attempts(source: Source, *, default: int) -> int:
    value = source.form.get("max_attempts", "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
