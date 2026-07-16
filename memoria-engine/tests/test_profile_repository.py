from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.models import PersonQuery
from caduti_fonti_report.person_profiles import profile_from_person_query, profile_to_jsonld
from caduti_fonti_report.profile_repository import ProfileRepository, is_legacy_seed_source


@contextmanager
def workspace_temp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"test-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def write_profile_fixture(root: Path) -> Path:
    profiles_dir = root / "person_profiles"
    profiles_dir.mkdir()
    profile = profile_from_person_query(
        PersonQuery(
            full_name="Andreoli Dino",
            given_name="Dino",
            family_name="Andreoli",
            death_date="11 ottobre 1944",
            place_hint="Italia",
        ),
        seed_source="fixture.csv",
        imported_at="2026-05-09T10:00:00+00:00",
    )
    profile_path = profiles_dir / "purocielo-andreoli-dino.jsonld"
    profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False, indent=2), encoding="utf-8")
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_payload = {
        "@context": {"@vocab": "https://schema.cadimalanca.local/research#"},
        "@type": "PersonResearchProfileIndex",
        "count": 1,
        "profiles": [
            {
                "@id": "person:purocielo:andreoli-dino",
                "file": "purocielo-andreoli-dino.jsonld",
                "canonical_name": "Andreoli Dino",
            }
        ],
    }
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def write_legacy_profile_fixture(root: Path) -> Path:
    profiles_dir = root / "person_profiles"
    profiles_dir.mkdir()
    profile = profile_from_person_query(
        PersonQuery(full_name="Andreoli Dino", given_name="Dino", family_name="Andreoli"),
        seed_source="ricerche\\caduti_purocielo.csv",
        imported_at="2026-05-09T10:00:00+00:00",
    )
    profile_path = profiles_dir / "purocielo-andreoli-dino.jsonld"
    profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False, indent=2), encoding="utf-8")
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_path.write_text(
        json.dumps(
            {
                "@type": "PersonResearchProfileIndex",
                "profiles": [
                    {
                        "@id": "person:purocielo:andreoli-dino",
                        "file": "purocielo-andreoli-dino.jsonld",
                        "canonical_name": "Andreoli Dino",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return index_path


class ProfileRepositoryTests(unittest.TestCase):
    def test_loads_profiles_from_index_without_csv(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            repository = ProfileRepository(index_path)
            profiles = repository.load_profiles()

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].profile_id, "person:purocielo:andreoli-dino")
        self.assertIn("profile_source_file", profiles[0].metadata)
        self.assertIn("profiles_index", profiles[0].metadata)

    def test_filters_by_profile_id_file_stem_and_name(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            repository = ProfileRepository(index_path)

            by_id = repository.load_profiles(profile_id="person:purocielo:andreoli-dino")
            by_stem = repository.load_profiles(profile_id="purocielo-andreoli-dino")
            by_name = repository.load_profiles(name_filter="Dino Andreoli")

        self.assertEqual([profile.profile_id for profile in by_id], ["person:purocielo:andreoli-dino"])
        self.assertEqual([profile.profile_id for profile in by_stem], ["person:purocielo:andreoli-dino"])
        self.assertEqual([profile.profile_id for profile in by_name], ["person:purocielo:andreoli-dino"])

    def test_returns_empty_list_for_unknown_profile(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            repository = ProfileRepository(index_path)

            profiles = repository.load_profiles(profile_id="person:purocielo:missing")

        self.assertEqual(profiles, [])

    def test_excludes_legacy_csv_seed_profiles_by_default(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_legacy_profile_fixture(tmp_dir)
            repository = ProfileRepository(index_path)

            profiles = repository.load_profiles(profile_id="person:purocielo:andreoli-dino")
            legacy_profiles = repository.load_profiles(
                profile_id="person:purocielo:andreoli-dino",
                include_legacy_seed=True,
            )

        self.assertEqual(profiles, [])
        self.assertEqual([profile.profile_id for profile in legacy_profiles], ["person:purocielo:andreoli-dino"])
        self.assertTrue(is_legacy_seed_source("ricerche\\caduti_purocielo.csv"))


if __name__ == "__main__":
    unittest.main()
