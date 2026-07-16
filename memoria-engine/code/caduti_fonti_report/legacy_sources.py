from __future__ import annotations

LEGACY_PROFILE_SEED_FILENAMES = {"caduti_purocielo.csv"}


def is_legacy_profile_seed_source(source: str) -> bool:
    normalized = source.replace("\\", "/").casefold().strip()
    return any(normalized.endswith(f"/{filename}") or normalized == filename for filename in LEGACY_PROFILE_SEED_FILENAMES)
