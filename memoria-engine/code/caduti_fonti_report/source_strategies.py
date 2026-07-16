from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml

from .models import PersonQuery, Source
from .source_profiles import SourceSearchProfile
from .connectors.search_strategy import SearchAttempt


@dataclass
class SourceSearchAttemptTemplate:
    template_id: str
    label: str = ""
    when: str = "always"
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class SourcePlaceMapping:
    mapping_id: str
    match_terms: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    provenance: str = ""
    review_status: str = "unreviewed"
    warnings: list[str] = field(default_factory=list)


@dataclass
class SourceSearchStrategyDefinition:
    source_id: str
    engine: str
    profile_path: str = ""
    max_attempts: int = 0
    attempts: list[SourceSearchAttemptTemplate] = field(default_factory=list)
    place_mappings: list[SourcePlaceMapping] = field(default_factory=list)


def load_source_search_strategy(path: Path | str) -> SourceSearchStrategyDefinition:
    raw_payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if "search_strategy" in raw_payload and isinstance(raw_payload["search_strategy"], dict):
        raw_payload = raw_payload["search_strategy"]
    if not isinstance(raw_payload, dict):
        raise ValueError("Strategia fonte non valida: atteso mapping YAML.")
    return source_search_strategy_from_dict(raw_payload)


def source_search_strategy_from_dict(payload: dict[str, Any]) -> SourceSearchStrategyDefinition:
    attempts: list[SourceSearchAttemptTemplate] = []
    for item in payload.get("attempts", []) or []:
        if not isinstance(item, dict):
            continue
        attempts.append(
            SourceSearchAttemptTemplate(
                template_id=str(item.get("id") or item.get("template_id") or ""),
                label=str(item.get("label", "")),
                when=str(item.get("when", "always")),
                fields={str(key): str(value) for key, value in (item.get("fields", {}) or {}).items()},
            )
        )

    place_mappings: list[SourcePlaceMapping] = []
    for item in payload.get("place_mappings", []) or []:
        if not isinstance(item, dict):
            continue
        place_mappings.append(
            SourcePlaceMapping(
                mapping_id=str(item.get("id") or item.get("mapping_id") or ""),
                match_terms=[str(value) for value in (item.get("match_terms", []) or [])],
                fields={str(key): str(value) for key, value in (item.get("fields", {}) or {}).items()},
                labels={str(key): str(value) for key, value in (item.get("labels", {}) or {}).items()},
                provenance=str(item.get("provenance", "")),
                review_status=str(item.get("review_status", "unreviewed")),
                warnings=[str(value) for value in (item.get("warnings", []) or [])],
            )
        )

    return SourceSearchStrategyDefinition(
        source_id=str(payload.get("source_id", "")),
        engine=str(payload.get("engine", "")),
        profile_path=str(payload.get("profile_path", "")),
        max_attempts=_as_non_negative_int(payload.get("max_attempts", 0)),
        attempts=attempts,
        place_mappings=place_mappings,
    )


def build_attempts_from_strategy_definition(
    *,
    definition: SourceSearchStrategyDefinition,
    source: Source,
    query: PersonQuery,
    profile: SourceSearchProfile | None = None,
) -> list[SearchAttempt]:
    context, context_metadata = _query_context(query, place_mappings=definition.place_mappings)
    attempts: list[SearchAttempt] = []
    for template in definition.attempts:
        if not template.template_id or not _condition_matches(template.when, context):
            continue
        fields = {
            field_id: _resolve_field_value(
                source=source,
                profile=profile,
                query=query,
                context=context,
                field_id=field_id,
                expression=expression,
            )
            for field_id, expression in template.fields.items()
        }
        fields = {key: value for key, value in fields.items() if value}
        attempts.append(
            SearchAttempt(
                attempt_id=template.template_id,
                label=template.label or template.template_id,
                query_text=_attempt_query_description(attempt_id=template.template_id, fields=fields),
                fields=fields,
                metadata={
                    "source_id": source.source_id,
                    "engine": definition.engine,
                    **_metadata_for_fields(context_metadata=context_metadata, fields=fields),
                },
            )
        )

    max_attempts = definition.max_attempts or len(attempts)
    return attempts[:max_attempts]


def _query_context(
    query: PersonQuery,
    *,
    place_mappings: list[SourcePlaceMapping] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    full_name = query.full_name.strip()
    given_name = query.given_name.strip()
    family_name = query.family_name.strip()
    reversed_full_name = " ".join(part for part in [given_name, family_name] if part)
    all_words_name = " ".join(part.casefold() for part in [family_name, given_name] if part)
    place_context, place_metadata = _source_place_context(query, place_mappings or [])
    context = {
        "full_name": full_name,
        "full_name_lc": full_name.casefold(),
        "given_name": given_name,
        "family_name": family_name,
        "reversed_full_name": reversed_full_name,
        "all_words_name": all_words_name,
        "birth_date": query.birth_date.strip(),
        "birth_date_iso": _extract_iso_date(query.birth_date),
        "birth_day": _extract_day(query.birth_date),
        "birth_month": _extract_month(query.birth_date),
        "birth_year": _extract_year(query.birth_date),
        "death_date": query.death_date.strip(),
        "death_date_iso": _extract_iso_date(query.death_date),
        "death_day": _extract_day(query.death_date),
        "death_month": _extract_year_month(query.death_date),
        "death_year": _extract_year(query.death_date),
        **place_context,
    }
    return context, place_metadata


def _condition_matches(condition: str, context: dict[str, str]) -> bool:
    if condition == "always":
        return True
    if condition == "has_family_and_given_name":
        return bool(context["family_name"] and context["given_name"])
    if condition == "has_family_name":
        return bool(context["family_name"])
    if condition == "has_given_name":
        return bool(context["given_name"])
    if condition == "has_family_given_and_birth_date":
        return bool(context["family_name"] and context["given_name"] and context["birth_date_iso"])
    if condition == "has_family_given_and_death_date":
        return bool(context["family_name"] and context["given_name"] and context["death_date_iso"])
    if condition == "has_family_given_and_death_year":
        return bool(context["family_name"] and context["given_name"] and context["death_year"])
    if condition == "mononym":
        return bool(context["full_name"] and not context["family_name"])
    return False


def _resolve_field_value(
    *,
    source: Source,
    profile: SourceSearchProfile | None,
    query: PersonQuery,
    context: dict[str, str],
    field_id: str,
    expression: str,
) -> str:
    if expression in context:
        return context[expression]
    if expression == "profile_default":
        return _profile_default(source=source, profile=profile, field_id=field_id)
    if expression.startswith("source_hint:"):
        return _source_hint_value(query=query, expression=expression)
    return expression


def _source_hint_value(*, query: PersonQuery, expression: str) -> str:
    parts = expression.split(":", 2)
    if len(parts) != 3:
        return ""
    _prefix, source_id, field = parts
    source_id = source_id.strip()
    field = field.strip()
    if not source_id or not field:
        return ""
    return query.source_hints.get(f"{source_id}:{field}", "").strip()


def _profile_default(*, source: Source, profile: SourceSearchProfile | None, field_id: str) -> str:
    source_override_key = _source_form_override_key(field_id)
    if source_override_key and source.form.get(source_override_key, "").strip():
        return source.form[source_override_key].strip()
    if profile is not None:
        for field in profile.fields:
            if field.field_id == field_id and field.default.strip():
                return field.default.strip()
    return ""


def _source_form_override_key(field_id: str) -> str:
    if field_id == "WarSelect":
        return "war_select"
    return ""


def _attempt_query_description(*, attempt_id: str, fields: dict[str, str]) -> str:
    parts = [attempt_id]
    for field_id, value in fields.items():
        if value:
            parts.append(f'{field_id}="{value}"')
    return "; ".join(parts)


def _metadata_for_fields(*, context_metadata: dict[str, str], fields: dict[str, str]) -> dict[str, str]:
    if not context_metadata:
        return {}
    mapped_fields = [field_id for field_id in context_metadata.get("field_resolution.context_fields", "").split(";") if field_id]
    if not any(field_id in fields for field_id in mapped_fields):
        return {}
    return context_metadata


def _as_non_negative_int(value: Any) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return 0
    return parsed if parsed >= 0 else 0


ITALIAN_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}


def _extract_iso_date(value: str) -> str:
    normalized = " ".join((value or "").strip().lower().split())
    if not normalized or "non reperito" in normalized or "ignoto" in normalized:
        return ""

    direct_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", normalized)
    if direct_match:
        return direct_match.group(0)

    italian_match = re.search(r"\b(\d{1,2})\s+([a-zà]+)\s+(\d{4})\b", normalized)
    if not italian_match:
        return ""

    day = int(italian_match.group(1))
    month = ITALIAN_MONTHS.get(italian_match.group(2))
    year = int(italian_match.group(3))
    if month is None:
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def _extract_year(value: str) -> str:
    match = re.search(r"\b(18[0-9]{2}|19[0-9]{2}|20[0-9]{2})\b", value or "")
    return match.group(1) if match else ""


def _extract_day(value: str) -> str:
    iso_date = _extract_iso_date(value)
    if not iso_date:
        return ""
    return iso_date.split("-")[2]


def _extract_month(value: str) -> str:
    iso_date = _extract_iso_date(value)
    if not iso_date:
        return ""
    return iso_date.split("-")[1]


def _extract_year_month(value: str) -> str:
    iso_date = _extract_iso_date(value)
    if not iso_date:
        return ""
    return "-".join(iso_date.split("-")[:2])


def _source_place_context(query: PersonQuery, place_mappings: list[SourcePlaceMapping]) -> tuple[dict[str, str], dict[str, str]]:
    text = " ".join([query.death_place, query.death_date, query.event_hint, query.place_hint]).casefold()
    for mapping in place_mappings:
        matched_terms = [term for term in mapping.match_terms if term.casefold() in text]
        if not matched_terms:
            continue
        context_fields = {f"atlante_{key}": value for key, value in mapping.fields.items() if value}
        metadata = {
            "field_resolution.kind": "source_place_mapping",
            "field_resolution.id": mapping.mapping_id,
            "field_resolution.review_status": mapping.review_status or "unreviewed",
            "field_resolution.provenance": mapping.provenance,
            "field_resolution.matched_terms": "; ".join(matched_terms),
            "field_resolution.context_fields": ";".join(mapping.fields),
            "field_resolution.output_fields": "; ".join(f"{key}={value}" for key, value in mapping.fields.items() if value),
            "field_resolution.labels": "; ".join(f"{key}={value}" for key, value in mapping.labels.items() if value),
            "field_resolution.warnings": "; ".join(mapping.warnings),
        }
        return context_fields, metadata
    return {}, {}
