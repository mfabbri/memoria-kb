from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .legacy_sources import is_legacy_profile_seed_source
from .models import PersonResearchProfile
from .person_profiles import profile_from_jsonld


@dataclass(frozen=True)
class ProfileIndexEntry:
    profile_id: str
    file: str
    canonical_name: str = ""


class ProfileRepository:
    def __init__(self, index_path: Path | str) -> None:
        self.index_path = Path(index_path)
        self.root_dir = self.index_path.parent
        self.entries = _load_index_entries(self.index_path)

    def list_entries(self) -> list[ProfileIndexEntry]:
        return list(self.entries)

    def load_profiles(
        self,
        *,
        profile_id: str = "",
        name_filter: str = "",
        limit: int = 0,
        include_legacy_seed: bool = False,
    ) -> list[PersonResearchProfile]:
        entries = self._filter_entries(profile_id=profile_id, name_filter=name_filter)
        profiles: list[PersonResearchProfile] = []
        for entry in entries:
            profile = self.load_entry(entry)
            if not include_legacy_seed and is_legacy_seed_profile(profile):
                continue
            profiles.append(profile)
            if limit > 0 and len(profiles) >= limit:
                break
        return profiles

    def load_entry(self, entry: ProfileIndexEntry) -> PersonResearchProfile:
        profile_path = self.root_dir / entry.file
        if not profile_path.exists():
            raise FileNotFoundError(f"Profilo non trovato: {profile_path}")
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
        profile = profile_from_jsonld(payload)
        profile.metadata.setdefault("profile_source_file", str(profile_path))
        profile.metadata.setdefault("profiles_index", str(self.index_path))
        return profile

    def _filter_entries(self, *, profile_id: str, name_filter: str) -> list[ProfileIndexEntry]:
        profile_id = profile_id.strip()
        name_filter = name_filter.strip()
        entries = self.entries
        if profile_id:
            entries = [
                entry
                for entry in entries
                if entry.profile_id == profile_id or entry.file == profile_id or Path(entry.file).stem == profile_id
            ]
        if name_filter:
            entries = [
                entry
                for entry in entries
                if _matches_name_filter(name_filter, entry.canonical_name, entry.profile_id, entry.file)
            ]
        return entries


def _load_index_entries(index_path: Path) -> list[ProfileIndexEntry]:
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    entries: list[ProfileIndexEntry] = []
    for item in payload.get("profiles", []):
        if not isinstance(item, dict):
            continue
        profile_id = str(item.get("@id", "")).strip()
        file_name = str(item.get("file", "")).strip()
        if not profile_id or not file_name:
            continue
        entries.append(
            ProfileIndexEntry(
                profile_id=profile_id,
                file=file_name,
                canonical_name=str(item.get("canonical_name", "")).strip(),
            )
        )
    return entries


def is_legacy_seed_source(source: str) -> bool:
    return is_legacy_profile_seed_source(source)


def is_legacy_seed_profile(profile: PersonResearchProfile) -> bool:
    return is_legacy_seed_source(profile.seed.source)


def _matches_name_filter(filter_text: str, *candidate_values: str) -> bool:
    filter_tokens = [token for token in filter_text.casefold().split() if token]
    if not filter_tokens:
        return True
    for candidate in candidate_values:
        candidate_tokens = candidate.casefold().replace("-", " ").replace(":", " ").split()
        if all(token in candidate_tokens for token in filter_tokens):
            return True
    return False
