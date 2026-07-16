from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.config import load_source_registry
from caduti_fonti_report.models import PersonQuery, ProfileSearchHint
from caduti_fonti_report.person_profiles import profile_from_person_query, profile_to_jsonld
from caduti_fonti_report.search_strategy_planner import build_profile_search_plan, plan_profile_search
from caduti_fonti_report.source_definitions import load_source_definition


def workspace_temp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"planner-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    return tmp_dir


def make_profile(query: PersonQuery):
    return profile_from_person_query(query, seed_source="fixture.csv", imported_at="2026-05-17T00:00:00+00:00")


def write_profile_index(root: Path, query: PersonQuery) -> Path:
    profiles_dir = root / "person_profiles"
    profiles_dir.mkdir()
    profile = make_profile(query)
    profile_path = profiles_dir / "purocielo-andreoli-dino.jsonld"
    profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False, indent=2), encoding="utf-8")
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_path.write_text(
        json.dumps(
            {
                "@type": "PersonResearchProfileIndex",
                "count": 1,
                "profiles": [
                    {
                        "@id": profile.profile_id,
                        "file": profile_path.name,
                        "canonical_name": profile.identity.canonical_name,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return index_path


class SearchStrategyPlannerTests(unittest.TestCase):
    def test_plans_partigiani_italia_attempts_from_profile_jsonld(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = load_source_registry(repo_root / "ricerche" / "camalanca_fonti.yaml")["partigiani_italia"]
        definition = load_source_definition(source, repo_root=repo_root)
        profile = make_profile(
            PersonQuery(
                full_name="ANDREOLI DINO",
                family_name="ANDREOLI",
                given_name="DINO",
                birth_date="17 maggio 1920, San Lazzaro di Savena",
            )
        )

        planned = plan_profile_search(profile=profile, source=source, source_definition=definition)

        self.assertEqual(
            [attempt.attempt_id for attempt in planned],
            ["cognome-nome-contains", "cognome-nome-nascita", "solo-cognome-contains"],
        )
        self.assertEqual(planned[0].priority, 1)
        self.assertEqual(planned[0].identity_basis, "family_given_name")
        self.assertIn("identity.family_name", planned[0].used_profile_fields)
        self.assertIn("identity.given_name", planned[0].used_profile_fields)
        self.assertEqual(planned[0].expected_result_level, "detail_document_candidate")
        self.assertTrue(planned[0].manual_review_required)
        self.assertEqual(planned[0].metadata["strategy_path"], "memoria-sources/source_strategies/partigiani_italia.yaml")

    def test_memorie_locali_plan_is_prudent_and_manual_review(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = load_source_registry(repo_root / "ricerche" / "camalanca_fonti.yaml")["memorie_locali"]
        definition = load_source_definition(source, repo_root=repo_root)
        profile = make_profile(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))

        planned = plan_profile_search(profile=profile, source=source, source_definition=definition)

        self.assertEqual([attempt.attempt_id for attempt in planned], ["nome-completo", "cognome-nome", "solo-cognome"])
        self.assertTrue(all(attempt.manual_review_required for attempt in planned))
        self.assertIn(planned[-1].risk_level, {"medium", "high"})
        self.assertEqual(planned[0].expected_result_level, "detail_document_candidate")

    def test_bundesarchiv_plan_marks_authenticated_archival_source_high_risk(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = load_source_registry(repo_root / "ricerche" / "camalanca_fonti.yaml")["bundesarchiv_invenio"]
        definition = load_source_definition(source, repo_root=repo_root)
        profile = make_profile(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))

        planned = plan_profile_search(profile=profile, source=source, source_definition=definition)

        self.assertIn("simple-keyword-full-name", [attempt.attempt_id for attempt in planned])
        self.assertTrue(all(attempt.manual_review_required for attempt in planned))
        self.assertTrue(all(attempt.risk_level == "high" for attempt in planned))
        self.assertTrue(all("candidate" in attempt.expected_result_level for attempt in planned))

    def test_source_hints_are_reported_as_hints_not_verified_facts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = load_source_registry(repo_root / "ricerche" / "camalanca_fonti.yaml")["tna_wo417"]
        definition = load_source_definition(source, repo_root=repo_root)
        profile = make_profile(
            PersonQuery(
                full_name="GUAZZALOCA LAURA",
                family_name="GUAZZALOCA",
                given_name="LAURA",
            )
        )
        profile.search_hints.append(
            ProfileSearchHint(
                hint_id="hint:tna:archive-reference",
                source_id="tna_wo417",
                field="archive.reference",
                value="WO 417",
                confidence=0.4,
                provenance="fixture",
                review_status="unreviewed",
            )
        )

        planned = plan_profile_search(profile=profile, source=source, source_definition=definition)

        self.assertIn("tna_wo417:archive.reference", planned[0].used_search_hints)
        self.assertEqual(profile.verified_facts, {})

    def test_atlante_place_resolution_is_reported_as_unreviewed_search_metadata(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = load_source_registry(repo_root / "ricerche" / "camalanca_fonti.yaml")["atlante_stragi"]
        definition = load_source_definition(source, repo_root=repo_root)
        profile = make_profile(
            PersonQuery(
                full_name="ANDREOLI DINO",
                family_name="ANDREOLI",
                given_name="DINO",
                death_date="11 ottobre 1944, battaglia di Purocielo/Ca Marcone",
            )
        )

        planned = plan_profile_search(profile=profile, source=source, source_definition=definition)

        self.assertEqual(planned[0].query_fields["comune"], "4030")
        self.assertEqual(planned[0].metadata["field_resolution.kind"], "source_place_mapping")
        self.assertEqual(planned[0].metadata["field_resolution.id"], "atlante-place-purocielo-ca-marcone")
        self.assertEqual(planned[0].metadata["field_resolution.review_status"], "unreviewed")
        self.assertIn("Purocielo", planned[0].metadata["field_resolution.matched_terms"])
        self.assertEqual(profile.verified_facts, {})

    def test_build_profile_search_plan_returns_controlled_profile_error(self) -> None:
        tmp_dir = workspace_temp_dir()
        try:
            index_path = write_profile_index(
                tmp_dir,
                PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"),
            )

            payload = build_profile_search_plan(
                profiles_index=index_path,
                sources_yaml=Path(__file__).resolve().parents[1] / "ricerche" / "camalanca_fonti.yaml",
                profile_id="person:purocielo:missing",
                source_id="partigiani_italia",
            )

            self.assertEqual(payload["error"], "profile_not_found")
            self.assertEqual(payload["planned_attempts"], [])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
