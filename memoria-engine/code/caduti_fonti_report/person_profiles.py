from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .adapters import matches_name_filter, person_queries_from_caduti
from .config import load_caduti
from .legacy_sources import is_legacy_profile_seed_source
from .models import (
    PersonQuery,
    PersonResearchProfile,
    ProfileIdentity,
    ProfileSearchHint,
    ProfileSeed,
    to_json_safe,
)


JSONLD_CONTEXT = {
    "crm": "http://www.cidoc-crm.org/cidoc-crm/",
    "schema": "https://schema.org/",
    "ca": "https://ca-di-malanca.local/ontology/",
    "PersonResearchProfile": "ca:PersonResearchProfile",
    "ProfileSearchHint": "ca:ProfileSearchHint",
    "EvidenceClaim": "ca:EvidenceClaim",
}


def profile_id_from_name(name: str) -> str:
    slug = _slugify(name)
    return f"person:purocielo:{slug or 'unknown'}"


def profile_slug(profile: PersonResearchProfile) -> str:
    return profile.profile_id.rsplit(":", 1)[-1] or _slugify(profile.identity.canonical_name)


def profile_from_person_query(
    query: PersonQuery,
    *,
    seed_source: str = "csv",
    imported_at: str = "",
) -> PersonResearchProfile:
    seed_payload = dict(query.metadata)
    if not seed_payload:
        seed_payload = to_json_safe(query)
    identity = ProfileIdentity(
        canonical_name=query.full_name,
        given_name=query.given_name,
        family_name=query.family_name,
        aliases=list(query.aliases),
        name_forms=_dedupe([query.full_name, query.family_name, query.given_name, *query.aliases]),
    )
    search_hints = _search_hints_from_query(query)
    return PersonResearchProfile(
        profile_id=profile_id_from_name(query.full_name),
        identity=identity,
        seed=ProfileSeed(
            source=seed_source,
            source_id=str(query.metadata.get("intestazione_pdf", "")),
            imported_at=imported_at,
            payload=seed_payload,
        ),
        birth=_date_place_dict(query.birth_date, query.birth_place),
        death=_date_place_dict(query.death_date, query.death_place),
        formations=[query.formation] if query.formation.strip() else [],
        events=[query.event_hint] if query.event_hint.strip() else [],
        places=[query.place_hint] if query.place_hint.strip() else [],
        search_hints=search_hints,
        metadata={"model_version": "person_research_profile.v1"},
    )


def person_query_from_profile(profile: PersonResearchProfile) -> PersonQuery:
    inferred_family_name, inferred_given_name = _fallback_family_given_from_canonical_name(
        profile.identity.canonical_name,
        family_name=profile.identity.family_name,
        given_name=profile.identity.given_name,
    )
    return PersonQuery(
        full_name=profile.identity.canonical_name,
        given_name=inferred_given_name,
        family_name=inferred_family_name,
        aliases=list(profile.identity.aliases),
        birth_date=profile.birth.get("date", ""),
        birth_place=profile.birth.get("place", ""),
        death_date=profile.death.get("date", ""),
        death_place=profile.death.get("place", ""),
        formation=profile.formations[0] if profile.formations else "",
        event_hint=profile.events[0] if profile.events else "",
        place_hint=profile.places[0] if profile.places else "",
        source_hints={
            f"{hint.source_id}:{hint.field}": hint.value
            for hint in profile.search_hints
            if hint.source_id and hint.field and hint.value
        },
        metadata={
            "profile_id": profile.profile_id,
            "profile_source_file": profile.metadata.get("profile_source_file", ""),
            "seed_source": profile.seed.source,
            **{str(key): str(value) for key, value in profile.seed.payload.items()},
        },
    )


def _fallback_family_given_from_canonical_name(
    canonical_name: str,
    *,
    family_name: str,
    given_name: str,
) -> tuple[str, str]:
    family_name = family_name.strip()
    given_name = given_name.strip()
    if family_name or given_name:
        return family_name, given_name

    tokens = [token for token in canonical_name.strip().split() if token]
    if len(tokens) < 2:
        return family_name, given_name
    return tokens[0], " ".join(tokens[1:])


def profile_to_jsonld(profile: PersonResearchProfile) -> dict[str, Any]:
    payload = to_json_safe(profile)
    payload["@context"] = JSONLD_CONTEXT
    payload["@type"] = "PersonResearchProfile"
    payload["@id"] = profile.profile_id
    return payload


def profile_from_jsonld(payload: dict[str, Any]) -> PersonResearchProfile:
    identity_payload = _dict(payload.get("identity"))
    seed_payload = _dict(payload.get("seed"))
    return PersonResearchProfile(
        profile_id=str(payload.get("profile_id") or payload.get("@id") or ""),
        identity=ProfileIdentity(
            canonical_name=str(identity_payload.get("canonical_name", "")),
            given_name=str(identity_payload.get("given_name", "")),
            family_name=str(identity_payload.get("family_name", "")),
            aliases=_string_list(identity_payload.get("aliases")),
            name_forms=_string_list(identity_payload.get("name_forms")),
        ),
        seed=ProfileSeed(
            source=str(seed_payload.get("source", "")),
            source_id=str(seed_payload.get("source_id", "")),
            imported_at=str(seed_payload.get("imported_at", "")),
            payload=_string_dict(seed_payload.get("payload")),
        ),
        birth=_string_dict(payload.get("birth")),
        death=_string_dict(payload.get("death")),
        formations=_string_list(payload.get("formations")),
        events=_string_list(payload.get("events")),
        places=_string_list(payload.get("places")),
        search_hints=[_search_hint_from_payload(item) for item in payload.get("search_hints", []) if isinstance(item, dict)],
        evidence_claim_ids=_string_list(payload.get("evidence_claim_ids")),
        verified_facts=_string_dict(payload.get("verified_facts")),
        conflicts=[_string_dict(item) for item in payload.get("conflicts", []) if isinstance(item, dict)],
        searched_sources=_string_list(payload.get("searched_sources")),
        next_research=_string_list(payload.get("next_research")),
        metadata=_string_dict(payload.get("metadata")),
    )


def write_profile(profile: PersonResearchProfile, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"purocielo-{profile_slug(profile)}.jsonld"
    path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_profile(path: Path) -> PersonResearchProfile:
    return profile_from_jsonld(json.loads(path.read_text(encoding="utf-8")))


def write_profile_index(profiles: list[PersonResearchProfile], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    items = [
        {
            "@id": profile.profile_id,
            "file": f"purocielo-{profile_slug(profile)}.jsonld",
            "canonical_name": profile.identity.canonical_name,
        }
        for profile in profiles
    ]
    path = output_dir / "purocielo.index.jsonld"
    path.write_text(
        json.dumps(
            {
                "@context": JSONLD_CONTEXT,
                "@type": "ca:PersonResearchProfileIndex",
                "generated_at": datetime.now(UTC).isoformat(),
                "count": len(items),
                "profiles": items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def build_profiles_from_csv(
    *,
    csv_path: Path,
    limit: int = 0,
    name_filter: str = "",
    imported_at: str = "",
    allow_legacy_csv: bool = False,
) -> list[PersonResearchProfile]:
    if is_legacy_profile_seed_source(str(csv_path)) and not allow_legacy_csv:
        raise ValueError(
            "caduti_purocielo.csv e' una sorgente legacy dismessa: non usarla per generare profili operativi."
        )
    caduti = load_caduti(csv_path)
    if name_filter.strip():
        requested_name = name_filter.strip()
        caduti = [caduto for caduto in caduti if matches_name_filter(requested_name, caduto.nome, caduto.intestazione_pdf)]
    if limit > 0:
        caduti = caduti[:limit]
    queries = person_queries_from_caduti(caduti)
    timestamp = imported_at or datetime.now(UTC).isoformat()
    return [profile_from_person_query(query, seed_source=str(csv_path), imported_at=timestamp) for query in queries]


def write_profiles_from_csv(
    *,
    csv_path: Path,
    output_dir: Path,
    limit: int = 0,
    name_filter: str = "",
    allow_legacy_csv: bool = False,
) -> list[Path]:
    profiles = build_profiles_from_csv(
        csv_path=csv_path,
        limit=limit,
        name_filter=name_filter,
        allow_legacy_csv=allow_legacy_csv,
    )
    paths = [write_profile(profile, output_dir) for profile in profiles]
    write_profile_index(profiles, output_dir)
    return paths


def _search_hints_from_query(query: PersonQuery) -> list[ProfileSearchHint]:
    hints: list[ProfileSearchHint] = []
    if query.full_name.strip():
        hints.append(_hint("identity.full_name", query.full_name, provenance="seed.full_name"))
    if query.family_name.strip():
        hints.append(_hint("identity.family_name", query.family_name, provenance="seed.family_name"))
    if query.given_name.strip():
        hints.append(_hint("identity.given_name", query.given_name, provenance="seed.given_name"))
    for alias in query.aliases:
        hints.append(_hint("identity.alias", alias, provenance="seed.alias"))
    if query.birth_date.strip():
        hints.append(_hint("birth.date", query.birth_date, provenance="seed.birth_date", confidence=0.45))
    if query.death_date.strip():
        hints.append(_hint("death.date", query.death_date, provenance="seed.death_date", confidence=0.45))
    return hints


def _hint(field: str, value: str, *, provenance: str, confidence: float = 0.5) -> ProfileSearchHint:
    hint_id = f"hint:{_slugify(field)}:{_slugify(value)[:48]}"
    return ProfileSearchHint(
        hint_id=hint_id,
        source_id="seed",
        field=field,
        value=value,
        confidence=confidence,
        provenance=provenance,
    )


def _date_place_dict(date_value: str, place_value: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    if date_value.strip():
        payload["date"] = date_value
    if place_value.strip():
        payload["place"] = place_value
    return payload


def _search_hint_from_payload(payload: dict[str, Any]) -> ProfileSearchHint:
    return ProfileSearchHint(
        hint_id=str(payload.get("hint_id", "")),
        source_id=str(payload.get("source_id", "")),
        field=str(payload.get("field", "")),
        value=str(payload.get("value", "")),
        confidence=_float_or_default(payload.get("confidence"), 0.0),
        provenance=str(payload.get("provenance", "")),
        review_status=str(payload.get("review_status", "unreviewed")),
    )


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold())
    return text.strip("-")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = value.strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea PersonResearchProfile JSON-LD dal CSV dei caduti.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=0, help="Numero massimo di profili da creare; 0 = tutti.")
    parser.add_argument("--name", default="", help="Filtra per nome/intestazione PDF.")
    parser.add_argument("--allow-legacy-csv", action="store_true", help="Consente solo un export storico esplicito da caduti_purocielo.csv.")
    args = parser.parse_args()

    paths = write_profiles_from_csv(
        csv_path=Path(args.csv),
        output_dir=Path(args.output_dir),
        limit=args.limit,
        name_filter=args.name,
        allow_legacy_csv=args.allow_legacy_csv,
    )
    print(f"Profili persona scritti: {len(paths)}")
    print(f"Output directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
