from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .config import load_source_registry, load_sources_from_yaml
from .models import PersonQuery, PersonResearchProfile, Source, to_json_safe
from .person_profiles import person_query_from_profile
from .planned_search_attempts import PlannedSearchAttempt, planned_search_attempts_to_dict
from .profile_repository import ProfileRepository
from .source_definitions import SourceDefinition, load_source_definition
from .source_strategies import build_attempts_from_strategy_definition
from .source_catalog import resolve_source_registry_path
from .validate_sources_registry import validate_sources_registry_file


def plan_profile_search(
    *,
    profile: PersonResearchProfile,
    source: Source,
    source_definition: SourceDefinition,
) -> list[PlannedSearchAttempt]:
    query = person_query_from_profile(profile)
    if source_definition.strategy_definition is None:
        return [
            PlannedSearchAttempt(
                source_id=source.source_id,
                attempt_id="strategy-missing",
                priority=1,
                skip_reason="missing_strategy_definition",
                reason=f"Nessuna strategia dichiarativa caricata per {source.source_id}.",
            )
        ]

    search_attempts = build_attempts_from_strategy_definition(
        definition=source_definition.strategy_definition,
        source=source,
        query=query,
        profile=source_definition.profile,
    )
    planned: list[PlannedSearchAttempt] = []
    for priority, attempt in enumerate(search_attempts, start=1):
        metadata = {
            "profile_id": profile.profile_id,
            "profile_source_file": profile.metadata.get("profile_source_file", ""),
            "strategy_path": source_definition.strategy_path,
            "profile_path": source_definition.profile_path,
            "engine": source_definition.strategy_definition.engine,
        }
        metadata.update({key: value for key, value in attempt.metadata.items() if key not in {"source_id", "engine"}})
        planned.append(
            PlannedSearchAttempt(
                source_id=source.source_id,
                attempt_id=attempt.attempt_id,
                priority=priority,
                query_text=attempt.query_text,
                query_fields=dict(attempt.fields),
                identity_basis=_identity_basis(attempt.fields, query),
                used_profile_fields=_used_profile_fields(attempt.fields, query),
                used_search_hints=_used_search_hints(attempt.fields, query),
                expected_result_level=_expected_result_level(source_definition),
                risk_level=_risk_level(source=source, attempt_id=attempt.attempt_id),
                manual_review_required=_manual_review_required(source=source, source_definition=source_definition),
                reason=_reason(source=source, source_definition=source_definition, attempt_label=attempt.label),
                metadata=metadata,
            )
        )
    if planned:
        return planned
    return [
        PlannedSearchAttempt(
            source_id=source.source_id,
            attempt_id="no-search-attempts",
            priority=1,
            expected_result_level=_expected_result_level(source_definition),
            risk_level=_risk_level(source=source, attempt_id="no-search-attempts"),
            manual_review_required=True,
            skip_reason="no_matching_strategy_template",
            reason="La strategia dichiarativa non ha prodotto tentativi per i campi disponibili nel profilo.",
            metadata={
                "profile_id": profile.profile_id,
                "profile_source_file": profile.metadata.get("profile_source_file", ""),
                "strategy_path": source_definition.strategy_path,
            },
        )
    ]


def build_profile_search_plan(
    *,
    profiles_index: Path,
    sources_yaml: Path,
    profile_id: str,
    source_id: str,
    repo_root: Path | None = None,
) -> dict[str, object]:
    repo_root = repo_root or _repo_root_from_sources_yaml(sources_yaml)
    repository = ProfileRepository(profiles_index)
    profiles = repository.load_profiles(profile_id=profile_id, limit=1)
    if not profiles:
        return _error_payload("profile_not_found", profiles_index=profiles_index, sources_yaml=sources_yaml)

    source_registry = load_source_registry(sources_yaml)
    source_selection = load_sources_from_yaml(sources_yaml, source_registry, only_source_id=source_id)
    if not source_selection.selected_sources:
        return _error_payload("source_not_found", profiles_index=profiles_index, sources_yaml=sources_yaml)

    selected_source_ids = {source.source_id for source in source_selection.selected_sources}
    validation = validate_sources_registry_file(sources_yaml, only_source_ids=selected_source_ids)
    if not validation.valid:
        return {
            **_error_payload("invalid_sources_registry", profiles_index=profiles_index, sources_yaml=sources_yaml),
            "validation_errors": list(validation.errors),
        }

    profile = profiles[0]
    source = source_selection.selected_sources[0]
    source_definition = load_source_definition(source, repo_root=repo_root)
    attempts = plan_profile_search(profile=profile, source=source, source_definition=source_definition)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_mode": "person_profiles_jsonld",
        "profiles_index": str(profiles_index),
        "sources_yaml": str(sources_yaml),
        "profile": {
            "profile_id": profile.profile_id,
            "profile_source_file": profile.metadata.get("profile_source_file", ""),
            "canonical_name": profile.identity.canonical_name,
            "person_query": to_json_safe(person_query_from_profile(profile)),
        },
        "source": {
            "source_id": source.source_id,
            "source_name": source.source_name,
            "kind": source.kind,
            "definition": {
                "profile_path": source_definition.profile_path,
                "strategy_path": source_definition.strategy_path,
                "result_logic_path": source_definition.result_logic_path,
                "detail_logic_path": source_definition.detail_logic_path,
                "detail_fetch_mode": source_definition.detail_fetch_mode,
                "claim_extraction_mode": source_definition.claim_extraction_mode,
            },
        },
        "planned_attempts": planned_search_attempts_to_dict(attempts),
        "error": "",
    }


def write_profile_search_plan(
    *,
    profiles_index: Path,
    sources_yaml: Path,
    profile_id: str,
    source_id: str,
    output_json: Path,
    repo_root: Path | None = None,
) -> dict[str, object]:
    payload = build_profile_search_plan(
        profiles_index=profiles_index,
        sources_yaml=sources_yaml,
        profile_id=profile_id,
        source_id=source_id,
        repo_root=repo_root,
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _identity_basis(fields: dict[str, str], query: PersonQuery) -> str:
    values = {value.casefold() for value in fields.values() if value}
    if query.full_name and query.full_name.casefold() in values:
        return "canonical_name"
    if query.family_name and query.given_name and query.family_name.casefold() in values and query.given_name.casefold() in values:
        return "family_given_name"
    if query.family_name and query.family_name.casefold() in values:
        return "family_name"
    if any(value.casefold() in values for value in query.aliases):
        return "alias"
    if _used_search_hints(fields, query):
        return "search_hint"
    return "unknown"


def _used_profile_fields(fields: dict[str, str], query: PersonQuery) -> list[str]:
    checks = [
        ("identity.canonical_name", query.full_name),
        ("identity.given_name", query.given_name),
        ("identity.family_name", query.family_name),
        ("birth.date", query.birth_date),
        ("death.date", query.death_date),
        ("birth.place", query.birth_place),
        ("death.place", query.death_place),
        ("formation.name", query.formation),
        ("event.hint", query.event_hint),
        ("place.hint", query.place_hint),
    ]
    field_values = [value.casefold() for value in fields.values() if value]
    used: list[str] = []
    for field_name, value in checks:
        text = value.strip()
        if text and any(text.casefold() == field_value or text.casefold() in field_value for field_value in field_values):
            used.append(field_name)
    for alias in query.aliases:
        if alias.strip() and alias.casefold() in field_values:
            used.append("identity.alias")
            break
    return _dedupe(used)


def _used_search_hints(fields: dict[str, str], query: PersonQuery) -> list[str]:
    field_values = {value.strip().casefold() for value in fields.values() if value.strip()}
    used: list[str] = []
    for key, value in query.source_hints.items():
        text = value.strip()
        if text and text.casefold() in field_values:
            used.append(key)
    return _dedupe(used)


def _expected_result_level(source_definition: SourceDefinition) -> str:
    if source_definition.detail_fetch_mode == "detail_page":
        return "detail_document_candidate"
    return "candidate_results"


def _risk_level(*, source: Source, attempt_id: str) -> str:
    text = " ".join([source.kind, source.note, attempt_id]).casefold()
    if source.credentials or "credentialed" in text or "authenticated" in text or "autenticata" in text:
        return "high"
    if "manual" in text or "manuale" in text or "solo-cognome" in text or "family-name" in text:
        return "medium"
    return "low"


def _manual_review_required(*, source: Source, source_definition: SourceDefinition) -> bool:
    text = " ".join([source.kind, source.note, source_definition.detail_fetch_mode, source_definition.claim_extraction_mode]).casefold()
    return (
        bool(source.credentials)
        or bool(source.auth)
        or "manual" in text
        or "manuale" in text
        or source_definition.claim_extraction_mode != "none"
    )


def _reason(*, source: Source, source_definition: SourceDefinition, attempt_label: str) -> str:
    return (
        f"Tentativo generato dalla strategia dichiarativa {source_definition.strategy_path} "
        f"per la fonte {source.source_id}: {attempt_label}. Output candidato, soggetto a revisione."
    )


def _repo_root_from_sources_yaml(sources_yaml: Path) -> Path:
    resolved = sources_yaml.resolve()
    if resolved.parent.name == "ricerche":
        return resolved.parent.parent
    if resolved.parent.name == "registry" and resolved.parent.parent.name == "memoria-sources":
        engine_root = resolved.parent.parent.parent / "memoria-engine"
        if engine_root.exists():
            return engine_root
        return resolved.parent.parent
    return resolved.parent


def _error_payload(error: str, *, profiles_index: Path, sources_yaml: Path) -> dict[str, object]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_mode": "person_profiles_jsonld",
        "profiles_index": str(profiles_index),
        "sources_yaml": str(sources_yaml),
        "planned_attempts": [],
        "error": error,
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Pianifica tentativi di ricerca da PersonResearchProfile JSON-LD senza eseguirli.")
    parser.add_argument("--profiles-index", required=True)
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-json", default="risultati/profile_search_plan.json")
    args = parser.parse_args()
    sources_yaml = Path(args.sources_yaml)
    if args.sources_yaml == "ricerche/camalanca_fonti.yaml":
        sources_yaml = resolve_source_registry_path(Path.cwd())

    payload = write_profile_search_plan(
        profiles_index=Path(args.profiles_index),
        sources_yaml=sources_yaml,
        profile_id=args.profile_id,
        source_id=args.source,
        output_json=Path(args.output_json),
    )
    print(f"Piano ricerca scritto in {args.output_json}")
    print(f"Tentativi pianificati: {len(payload.get('planned_attempts', []))}")
    if payload.get("error"):
        print(f"Errore: {payload['error']}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
