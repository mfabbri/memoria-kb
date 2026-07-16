from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.config import load_caduti
from caduti_fonti_report.models import person_query_from_caduto
from caduti_fonti_report.person_profiles import (
    build_profiles_from_csv,
    person_query_from_profile,
    profile_from_jsonld,
    profile_from_person_query,
    profile_to_jsonld,
    read_profile,
    write_profile,
    write_profile_index,
)
from caduti_fonti_report.queries import default_query
from caduti_fonti_report.source_profiles import load_source_search_profile
from caduti_fonti_report.source_strategies import build_attempts_from_strategy_definition, load_source_search_strategy
from caduti_fonti_report.models import Source


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


def write_caduti_fixture(path: Path) -> None:
    csv_text = (
        "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
        "profilo_biografico,episodio_documentato\n"
        'ANDREOLI DINO,Andreoli Dino,Italia,"17 maggio 1920","11 ottobre 1944",partigiano,Fonte A,"Profilo A","Episodio A"\n'
        'GIORGIO,Giorgio,U.R.S.S.,non reperito,non reperito,"partigiano sovietico",,"",""\n'
    )
    path.write_text(csv_text, encoding="utf-8-sig")


class PersonResearchProfileTests(unittest.TestCase):
    def test_profile_from_person_query_preserves_seed_without_verified_facts(self) -> None:
        caduto = load_caduti_from_text_fixture()[0]
        query = person_query_from_caduto(caduto)

        profile = profile_from_person_query(query, seed_source="fixture.csv", imported_at="2026-05-09T10:00:00+00:00")

        self.assertEqual(profile.profile_id, "person:purocielo:andreoli-dino")
        self.assertEqual(profile.identity.canonical_name, "Andreoli Dino")
        self.assertEqual(profile.seed.source, "fixture.csv")
        self.assertEqual(profile.seed.payload["intestazione_pdf"], "ANDREOLI DINO")
        self.assertEqual(profile.verified_facts, {})
        self.assertTrue(any(hint.field == "identity.full_name" for hint in profile.search_hints))

    def test_profile_jsonld_round_trip(self) -> None:
        caduto = load_caduti_from_text_fixture()[0]
        profile = profile_from_person_query(person_query_from_caduto(caduto), seed_source="fixture.csv")

        payload = profile_to_jsonld(profile)
        loaded = profile_from_jsonld(json.loads(json.dumps(payload)))

        self.assertEqual(payload["@type"], "PersonResearchProfile")
        self.assertEqual(payload["@id"], "person:purocielo:andreoli-dino")
        self.assertEqual(loaded.identity.family_name, "Andreoli")
        self.assertEqual(loaded.search_hints[0].review_status, "unreviewed")

    def test_profile_can_be_used_as_person_query_input(self) -> None:
        caduto = load_caduti_from_text_fixture()[0]
        profile = profile_from_person_query(person_query_from_caduto(caduto), seed_source="fixture.csv")

        query = person_query_from_profile(profile)

        self.assertEqual(query.full_name, "Andreoli Dino")
        self.assertEqual(query.family_name, "Andreoli")
        self.assertEqual(query.metadata["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(query.source_hints["seed:death.date"], "11 ottobre 1944")

    def test_profile_query_infers_family_and_given_name_from_two_token_canonical_name(self) -> None:
        payload = {
            "@id": "person:purocielo:balboni-william",
            "identity": {
                "canonical_name": "Balboni William",
                "given_name": "",
                "family_name": "",
                "aliases": [],
                "name_forms": ["Balboni William"],
            },
            "seed": {"source": "candidate_profile_review", "payload": {}},
        }
        profile = profile_from_jsonld(payload)

        query = person_query_from_profile(profile)

        self.assertEqual(query.full_name, "Balboni William")
        self.assertEqual(query.family_name, "Balboni")
        self.assertEqual(query.given_name, "William")

    def test_inferred_profile_name_builds_partigiani_family_given_attempt(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        payload = {
            "@id": "person:purocielo:balboni-william",
            "identity": {"canonical_name": "Balboni William", "given_name": "", "family_name": ""},
            "seed": {"source": "candidate_profile_review", "payload": {}},
        }
        query = person_query_from_profile(profile_from_jsonld(payload))
        strategy = load_source_search_strategy(repo_root.parent / "memoria-sources" / "source_strategies" / "partigiani_italia.yaml")
        source_profile = load_source_search_profile(repo_root.parent / "memoria-sources" / "source_profiles" / "partigiani_italia.yaml")
        source = Source(
            source_id="partigiani_italia",
            source_name="I Partigiani d'Italia",
            kind="search_form_get_name",
            build_query=default_query,
            search_url_builder=lambda value: "https://partigianiditalia.cultura.gov.it/cerca/",
        )

        attempts = build_attempts_from_strategy_definition(definition=strategy, source=source, query=query, profile=source_profile)

        self.assertEqual(attempts[0].attempt_id, "cognome-nome-contains")
        self.assertEqual(attempts[0].fields["cognome"], "Balboni")
        self.assertEqual(attempts[0].fields["nome"], "William")

    def test_write_profiles_and_index_from_csv(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            csv_path = tmp_dir / "caduti.csv"
            output_dir = tmp_dir / "person_profiles"
            write_caduti_fixture(csv_path)
            profiles = build_profiles_from_csv(csv_path=csv_path, limit=1, imported_at="2026-05-09T10:00:00+00:00")
            profile_path = write_profile(profiles[0], output_dir)
            index_path = write_profile_index(profiles, output_dir)
            loaded = read_profile(profile_path)
            index_payload = json.loads(index_path.read_text(encoding="utf-8"))

        self.assertEqual(loaded.profile_id, "person:purocielo:andreoli-dino")
        self.assertEqual(index_payload["count"], 1)
        self.assertEqual(index_payload["profiles"][0]["file"], "purocielo-andreoli-dino.jsonld")

    def test_legacy_caduti_purocielo_csv_is_blocked_by_default(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            csv_path = tmp_dir / "caduti_purocielo.csv"
            write_caduti_fixture(csv_path)

            with self.assertRaisesRegex(ValueError, "sorgente legacy dismessa"):
                build_profiles_from_csv(csv_path=csv_path)


def load_caduti_from_text_fixture():
    with workspace_temp_dir() as tmp_dir:
        csv_path = tmp_dir / "caduti.csv"
        write_caduti_fixture(csv_path)
        return load_caduti(csv_path)


if __name__ == "__main__":
    unittest.main()
