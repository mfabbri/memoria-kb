from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CandidateLink:
    title: str
    url: str
    snippet: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResultSignals:
    source_id: str
    engine: str = ""
    heading: str = ""
    shown_results: int = 0
    total_results: int = 0
    candidate_links: list[CandidateLink] = field(default_factory=list)
    blocked: bool = False
    error: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResultAssessment:
    assessment: str
    review_required: bool = False
    candidate_links: list[CandidateLink] = field(default_factory=list)
    total_results: int = 0
    shown_results: int = 0
    note: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateFilters:
    include_url_patterns: list[str] = field(default_factory=list)
    exclude_url_patterns: list[str] = field(default_factory=list)
    include_title_patterns: list[str] = field(default_factory=list)
    exclude_title_patterns: list[str] = field(default_factory=list)
    min_title_length: int = 0
    require_non_empty_title: bool = True


@dataclass(frozen=True)
class ResultLogicRule:
    rule_id: str
    when: dict[str, Any] = field(default_factory=dict)
    assessment: str = ""
    review_required: bool = False
    collect_candidate_links: bool = False
    max_candidate_links: int = 0


@dataclass(frozen=True)
class SourceResultLogicDefinition:
    source_id: str
    engine: str = ""
    candidate_limit: int = 10
    too_broad_threshold: int = 0
    signals: dict[str, Any] = field(default_factory=dict)
    candidate_filters: CandidateFilters = field(default_factory=CandidateFilters)
    rules: list[ResultLogicRule] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)


def load_source_result_logic(path: Path | str) -> SourceResultLogicDefinition:
    raw_payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if "result_logic" in raw_payload and isinstance(raw_payload["result_logic"], dict):
        raw_payload = raw_payload["result_logic"]
    if not isinstance(raw_payload, dict):
        raise ValueError("Logica risultati fonte non valida: atteso mapping YAML.")
    return source_result_logic_from_dict(raw_payload)


def source_result_logic_from_dict(payload: dict[str, Any]) -> SourceResultLogicDefinition:
    rules: list[ResultLogicRule] = []
    for item in payload.get("rules", []) or []:
        if not isinstance(item, dict):
            continue
        rules.append(
            ResultLogicRule(
                rule_id=str(item.get("id") or item.get("rule_id") or ""),
                when=dict(item.get("when", {}) or {}),
                assessment=str(item.get("assessment", "")),
                review_required=bool(item.get("review_required", False)),
                collect_candidate_links=bool(item.get("collect_candidate_links", False)),
                max_candidate_links=_as_non_negative_int(item.get("max_candidate_links", 0)),
            )
        )
    return SourceResultLogicDefinition(
        source_id=str(payload.get("source_id", "")),
        engine=str(payload.get("engine", "")),
        candidate_limit=_as_positive_int(payload.get("candidate_limit", 10), 10),
        too_broad_threshold=_as_non_negative_int(payload.get("too_broad_threshold", 0)),
        signals=dict(payload.get("signals", {}) or {}),
        candidate_filters=_candidate_filters_from_payload(payload.get("candidate_filters", {}) or {}),
        rules=rules,
        review_notes=[str(item) for item in payload.get("review_notes", []) or []],
    )


def _candidate_filters_from_payload(raw_filters: Any) -> CandidateFilters:
    if not isinstance(raw_filters, dict):
        return CandidateFilters()
    return CandidateFilters(
        include_url_patterns=_as_string_list(raw_filters.get("include_url_patterns", [])),
        exclude_url_patterns=_as_string_list(raw_filters.get("exclude_url_patterns", [])),
        include_title_patterns=_as_string_list(raw_filters.get("include_title_patterns", [])),
        exclude_title_patterns=_as_string_list(raw_filters.get("exclude_title_patterns", [])),
        min_title_length=_as_non_negative_int(raw_filters.get("min_title_length", 0)),
        require_non_empty_title=_as_bool(raw_filters.get("require_non_empty_title", True)),
    )


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


class SearchResultInterpreter:
    def __init__(self, definition: SourceResultLogicDefinition) -> None:
        self.definition = definition

    def interpret(self, signals: SearchResultSignals) -> SearchResultAssessment:
        for rule in self.definition.rules:
            if not rule.assessment or not _rule_matches(rule, signals):
                continue
            return _assessment_from_rule(rule, signals, self.definition)
        return _fallback_assessment(signals, self.definition)


def _rule_matches(rule: ResultLogicRule, signals: SearchResultSignals) -> bool:
    for key, expected in rule.when.items():
        if key == "heading_equals" and signals.heading.strip().casefold() != str(expected).strip().casefold():
            return False
        if key == "total_results_between" and not _between(signals.total_results, expected):
            return False
        if key == "total_results_greater_than" and signals.total_results <= _as_non_negative_int(expected):
            return False
        if key == "detail_link_count_equals" and len(signals.candidate_links) != _as_non_negative_int(expected):
            return False
        if key == "detail_link_count_between" and not _between(len(signals.candidate_links), expected):
            return False
        if key == "detail_link_count_greater_than" and len(signals.candidate_links) <= _as_non_negative_int(expected):
            return False
        if key == "query_is_mononym" and _as_bool(expected) != _as_bool(signals.metadata.get("query_is_mononym", "")):
            return False
        if key == "blocked" and _as_bool(expected) != signals.blocked:
            return False
        if key == "loading" and _as_bool(expected) != _as_bool(signals.metadata.get("loading", "")):
            return False
        if key == "has_error" and _as_bool(expected) != bool(signals.error):
            return False
        if key == "metadata_equals" and not _metadata_equals(signals.metadata, expected):
            return False
        if key == "metadata_in" and not _metadata_in(signals.metadata, expected):
            return False
        if key == "metadata_int_greater_than" and not _metadata_int_greater_than(signals.metadata, expected):
            return False
        if key == "metadata_int_between" and not _metadata_int_between(signals.metadata, expected):
            return False
    return True


def _assessment_from_rule(
    rule: ResultLogicRule,
    signals: SearchResultSignals,
    definition: SourceResultLogicDefinition,
) -> SearchResultAssessment:
    limit = rule.max_candidate_links or definition.candidate_limit
    links = signals.candidate_links[:limit] if rule.collect_candidate_links else []
    return SearchResultAssessment(
        assessment=rule.assessment,
        review_required=rule.review_required,
        candidate_links=links,
        total_results=signals.total_results,
        shown_results=signals.shown_results,
        note=_assessment_note(rule.assessment, signals, len(links)),
        metadata={
            "rule_id": rule.rule_id,
            "source_id": signals.source_id,
            "engine": signals.engine or definition.engine,
        },
    )


def _fallback_assessment(
    signals: SearchResultSignals,
    definition: SourceResultLogicDefinition,
) -> SearchResultAssessment:
    if signals.error:
        assessment = "error"
        review_required = True
        links: list[CandidateLink] = []
    elif signals.blocked:
        assessment = "blocked_or_dynamic"
        review_required = True
        links = []
    elif signals.total_results <= 0:
        assessment = "no_results"
        review_required = False
        links = []
    else:
        assessment = "candidate_results"
        if signals.total_results > definition.candidate_limit:
            assessment = "candidate_results_truncated"
        if definition.too_broad_threshold and signals.total_results > definition.too_broad_threshold:
            assessment = "too_broad"
        review_required = True
        links = signals.candidate_links[: definition.candidate_limit]
    return SearchResultAssessment(
        assessment=assessment,
        review_required=review_required,
        candidate_links=links,
        total_results=signals.total_results,
        shown_results=signals.shown_results,
        note=_assessment_note(assessment, signals, len(links)),
        metadata={"rule_id": "fallback", "source_id": signals.source_id, "engine": signals.engine or definition.engine},
    )


def _assessment_note(assessment: str, signals: SearchResultSignals, collected_count: int) -> str:
    if assessment == "no_results":
        return "Nessun risultato nella pagina di ricerca."
    if assessment == "candidate_results":
        return f"Lista breve di candidati da revisionare: {signals.total_results} risultati."
    if assessment == "candidate_results_truncated":
        return f"Lista candidati troncata: mostrati {collected_count} di {signals.total_results} risultati."
    if assessment == "too_broad":
        return f"Ricerca troppo ampia: {signals.total_results} risultati."
    if assessment == "blocked_or_dynamic":
        return "Pagina risultati bloccata o non interpretabile staticamente."
    if assessment == "error":
        return signals.error
    return assessment


def _between(value: int, expected: Any) -> bool:
    if not isinstance(expected, list | tuple) or len(expected) != 2:
        return False
    low = _as_non_negative_int(expected[0])
    high = _as_non_negative_int(expected[1])
    return low <= value <= high


def _as_bool(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "si", "sì"}


def _as_positive_int(value: Any, default: int) -> int:
    parsed = _as_non_negative_int(value)
    return parsed if parsed > 0 else default


def _as_non_negative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return default
    return parsed if parsed >= 0 else default


def _metadata_equals(metadata: dict[str, str], expected: Any) -> bool:
    if not isinstance(expected, dict):
        return False
    for key, value in expected.items():
        actual = str(metadata.get(str(key), "")).strip().casefold()
        if actual != str(value).strip().casefold():
            return False
    return True


def _metadata_in(metadata: dict[str, str], expected: Any) -> bool:
    if not isinstance(expected, dict):
        return False
    for key, values in expected.items():
        if not isinstance(values, list | tuple):
            return False
        actual = str(metadata.get(str(key), "")).strip().casefold()
        accepted = {str(value).strip().casefold() for value in values}
        if actual not in accepted:
            return False
    return True


def _metadata_int_greater_than(metadata: dict[str, str], expected: Any) -> bool:
    if not isinstance(expected, dict):
        return False
    for key, value in expected.items():
        actual = _as_non_negative_int(metadata.get(str(key), 0))
        if actual <= _as_non_negative_int(value):
            return False
    return True


def _metadata_int_between(metadata: dict[str, str], expected: Any) -> bool:
    if not isinstance(expected, dict):
        return False
    for key, value in expected.items():
        actual = _as_non_negative_int(metadata.get(str(key), 0))
        if not _between(actual, value):
            return False
    return True
