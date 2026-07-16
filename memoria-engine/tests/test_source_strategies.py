from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.models import PersonQuery, Source
from caduti_fonti_report.queries import default_query
from caduti_fonti_report.source_profiles import load_source_search_profile
from caduti_fonti_report.source_strategies import (
    build_attempts_from_strategy_definition,
    load_source_search_strategy,
    source_search_strategy_from_dict,
)


def make_source(form: dict[str, str] | None = None) -> Source:
    return Source(
        source_id="cwgc",
        source_name="CWGC",
        kind="cwgc",
        build_query=default_query,
        search_url_builder=lambda query: "https://www.cwgc.org/find-records/find-war-dead/",
        form={"name_order": "surname_first", "war_select": "2", **(form or {})},
        note="Ricerca pubblica Find War Dead.",
    )


class SourceStrategiesTests(unittest.TestCase):
    def test_load_real_cwgc_strategy(self) -> None:
        sources_root = Path(__file__).resolve().parents[2] / "memoria-sources"

        strategy = load_source_search_strategy(sources_root / "source_strategies" / "cwgc.yaml")

        self.assertEqual(strategy.source_id, "cwgc")
        self.assertEqual(strategy.engine, "cwgc_find_war_dead")
        self.assertEqual(strategy.profile_path, "source_profiles/cwgc.yaml")
        self.assertEqual(strategy.max_attempts, 2)
        self.assertEqual([attempt.template_id for attempt in strategy.attempts[:2]], ["cognome-nome-ww2", "solo-cognome-ww2"])

    def test_strategy_definition_builds_two_token_cwgc_attempts(self) -> None:
        sources_root = Path(__file__).resolve().parents[2] / "memoria-sources"
        strategy = load_source_search_strategy(sources_root / "source_strategies" / "cwgc.yaml")
        profile = load_source_search_profile(sources_root / "source_profiles" / "cwgc.yaml")

        attempts = build_attempts_from_strategy_definition(
            definition=strategy,
            source=make_source(),
            query=PersonQuery(full_name="PANOV SERGIO", family_name="PANOV", given_name="SERGIO"),
            profile=profile,
        )

        self.assertEqual([attempt.attempt_id for attempt in attempts], ["cognome-nome-ww2", "solo-cognome-ww2"])
        self.assertEqual(attempts[0].fields["Surname"], "PANOV")
        self.assertEqual(attempts[0].fields["Forename"], "SERGIO")
        self.assertEqual(attempts[0].fields["WarSelect"], "2")
        self.assertEqual(attempts[1].fields["Surname"], "PANOV")
        self.assertEqual(attempts[1].fields["WarSelect"], "2")

    def test_strategy_definition_builds_mononym_cwgc_attempts(self) -> None:
        sources_root = Path(__file__).resolve().parents[2] / "memoria-sources"
        strategy = load_source_search_strategy(sources_root / "source_strategies" / "cwgc.yaml")
        profile = load_source_search_profile(sources_root / "source_profiles" / "cwgc.yaml")

        attempts = build_attempts_from_strategy_definition(
            definition=strategy,
            source=make_source(),
            query=PersonQuery(full_name="GIORGIO", given_name="GIORGIO"),
            profile=profile,
        )

        self.assertEqual(
            [attempt.attempt_id for attempt in attempts],
            ["mononimo-come-cognome-ww2", "mononimo-come-nome-ww2"],
        )
        self.assertEqual(attempts[0].fields["Surname"], "GIORGIO")
        self.assertEqual(attempts[1].fields["Forename"], "GIORGIO")

    def test_source_form_can_override_live_profile_default(self) -> None:
        sources_root = Path(__file__).resolve().parents[2] / "memoria-sources"
        strategy = load_source_search_strategy(sources_root / "source_strategies" / "cwgc.yaml")
        profile = load_source_search_profile(sources_root / "source_profiles" / "cwgc.yaml")

        attempts = build_attempts_from_strategy_definition(
            definition=strategy,
            source=make_source({"war_select": "2"}),
            query=PersonQuery(full_name="PANOV SERGIO", family_name="PANOV", given_name="SERGIO"),
            profile=profile,
        )

        self.assertEqual(attempts[0].fields["WarSelect"], "2")

    def test_strategy_definition_can_use_source_specific_profile_hint(self) -> None:
        strategy = source_search_strategy_from_dict(
            {
                "source_id": "tna_wo417",
                "engine": "test_engine",
                "attempts": [
                    {
                        "id": "hint-reference",
                        "label": "Reference from profile hint",
                        "fields": {
                            "_cr": "source_hint:tna_wo417:archive.reference",
                            "_ep": "full_name",
                        },
                    }
                ],
            }
        )

        attempts = build_attempts_from_strategy_definition(
            definition=strategy,
            source=Source(
                source_id="tna_wo417",
                source_name="TNA Discovery - WO 417",
                kind="credentialed",
                build_query=default_query,
                search_url_builder=lambda query: "https://discovery.nationalarchives.gov.uk/",
            ),
            query=PersonQuery(
                full_name="GUAZZALOCA LAURA",
                family_name="GUAZZALOCA",
                given_name="LAURA",
                source_hints={"tna_wo417:archive.reference": "WO 417"},
            ),
        )

        self.assertEqual(attempts[0].fields["_cr"], "WO 417")
        self.assertEqual(attempts[0].fields["_ep"], "GUAZZALOCA LAURA")
        self.assertIn('_cr="WO 417"', attempts[0].query_text)

    def test_missing_source_hint_omits_field_without_breaking_attempt(self) -> None:
        strategy = source_search_strategy_from_dict(
            {
                "source_id": "tna_wo417",
                "engine": "test_engine",
                "attempts": [
                    {
                        "id": "optional-hint",
                        "label": "Optional source hint",
                        "fields": {
                            "_cr": "source_hint:tna_wo417:archive.reference",
                            "_ep": "full_name",
                        },
                    }
                ],
            }
        )

        attempts = build_attempts_from_strategy_definition(
            definition=strategy,
            source=Source(
                source_id="tna_wo417",
                source_name="TNA Discovery - WO 417",
                kind="credentialed",
                build_query=default_query,
                search_url_builder=lambda query: "https://discovery.nationalarchives.gov.uk/",
            ),
            query=PersonQuery(full_name="GUAZZALOCA LAURA", family_name="GUAZZALOCA", given_name="LAURA"),
        )

        self.assertNotIn("_cr", attempts[0].fields)
        self.assertEqual(attempts[0].fields["_ep"], "GUAZZALOCA LAURA")

    def test_storia_memoria_bo_strategy_builds_date_fallbacks(self) -> None:
        sources_root = Path(__file__).resolve().parents[2] / "memoria-sources"
        strategy = load_source_search_strategy(sources_root / "source_strategies" / "storia_memoria_bo.yaml")
        profile = load_source_search_profile(sources_root / "source_profiles" / "storia_memoria_bo.yaml")

        attempts = build_attempts_from_strategy_definition(
            definition=strategy,
            source=Source(
                source_id="storia_memoria_bo",
                source_name="Storia e Memoria di Bologna",
                kind="storia_memoria_bo",
                build_query=default_query,
                search_url_builder=lambda query: "https://www.storiaememoriadibologna.it/ricerca-avanzata",
                form={"name_order": "surname_first"},
            ),
            query=PersonQuery(
                full_name="ANDREOLI DINO",
                family_name="ANDREOLI",
                given_name="DINO",
                birth_date="17 maggio 1920, San Lazzaro di Savena",
                death_date="11 ottobre 1944, battaglia di Purocielo",
            ),
            profile=profile,
        )

        self.assertEqual(
            [attempt.attempt_id for attempt in attempts],
            ["nome-cognome", "testo-libero-nome-completo"],
        )
        self.assertEqual(attempts[0].fields["nom"], "DINO")
        self.assertEqual(attempts[0].fields["cog"], "ANDREOLI")
        self.assertEqual(attempts[1].fields["s"], "DINO ANDREOLI")
        self.assertNotIn("nom", attempts[1].fields)
        self.assertNotIn("cog", attempts[1].fields)
        self.assertNotIn("1920-05-17", [value for attempt in attempts for value in attempt.fields.values()])
        self.assertNotIn("1944-10-11", [value for attempt in attempts for value in attempt.fields.values()])

    def test_partigiani_italia_strategy_builds_name_year_and_surname_attempts(self) -> None:
        sources_root = Path(__file__).resolve().parents[2] / "memoria-sources"
        strategy = load_source_search_strategy(sources_root / "source_strategies" / "partigiani_italia.yaml")
        profile = load_source_search_profile(sources_root / "source_profiles" / "partigiani_italia.yaml")

        attempts = build_attempts_from_strategy_definition(
            definition=strategy,
            source=Source(
                source_id="partigiani_italia",
                source_name="I Partigiani d'Italia - ricerca pubblica",
                kind="search_form_get_name",
                build_query=default_query,
                search_url_builder=lambda query: "https://partigianiditalia.cultura.gov.it/cerca/",
                form={"name_order": "surname_first"},
            ),
            query=PersonQuery(
                full_name="ANDREOLI DINO",
                family_name="ANDREOLI",
                given_name="DINO",
                birth_date="17 maggio 1920, San Lazzaro di Savena",
            ),
            profile=profile,
        )

        self.assertEqual(
            [attempt.attempt_id for attempt in attempts],
            ["cognome-nome-contains", "cognome-nome-nascita", "solo-cognome-contains"],
        )
        self.assertEqual(attempts[0].fields["cognome"], "ANDREOLI")
        self.assertEqual(attempts[0].fields["nome"], "DINO")
        self.assertEqual(attempts[0].fields["lm"], "20")
        self.assertEqual(attempts[1].fields["data_nasc_da"], "1920")
        self.assertEqual(attempts[1].fields["data_nasc_a"], "1920")
        self.assertEqual(attempts[2].fields["cognome"], "ANDREOLI")
        self.assertNotIn("nome", attempts[2].fields)

    def test_tna_wo417_strategy_builds_exact_reversed_and_year_attempts(self) -> None:
        sources_root = Path(__file__).resolve().parents[2] / "memoria-sources"
        strategy = load_source_search_strategy(sources_root / "source_strategies" / "tna_wo417.yaml")
        profile = load_source_search_profile(sources_root / "source_profiles" / "tna_wo417.yaml")

        attempts = build_attempts_from_strategy_definition(
            definition=strategy,
            source=Source(
                source_id="tna_wo417",
                source_name="TNA Discovery - WO 417",
                kind="credentialed",
                build_query=default_query,
                search_url_builder=lambda query: "https://discovery.nationalarchives.gov.uk/",
            ),
            query=PersonQuery(
                full_name="ANDREOLI DINO",
                family_name="ANDREOLI",
                given_name="DINO",
                death_date="11 ottobre 1944, Purocielo",
            ),
            profile=profile,
        )

        self.assertEqual(
            [attempt.attempt_id for attempt in attempts[:4]],
            [
                "exact-original-wo417",
                "exact-original-wo417-death-year",
                "exact-reversed-wo417",
                "all-words-name-wo417",
            ],
        )
        self.assertEqual(attempts[0].fields["_ep"], "ANDREOLI DINO")
        self.assertEqual(attempts[0].fields["_cr"], "WO 417")
        self.assertEqual(attempts[1].fields["_sd"], "1944")
        self.assertEqual(attempts[1].fields["_ed"], "1944")
        self.assertEqual(attempts[2].fields["_ep"], "DINO ANDREOLI")
        self.assertEqual(attempts[3].fields["_aq"], "andreoli dino")

    def test_fondazione_fossoli_strategy_uses_structured_form_fields(self) -> None:
        sources_root = Path(__file__).resolve().parents[2] / "memoria-sources"
        strategy = load_source_search_strategy(sources_root / "source_strategies" / "fondazione_fossoli.yaml")
        profile = load_source_search_profile(sources_root / "source_profiles" / "fondazione_fossoli.yaml")

        attempts = build_attempts_from_strategy_definition(
            definition=strategy,
            source=Source(
                source_id="fondazione_fossoli",
                source_name="Fondazione Fossoli - I Nomi di Fossoli",
                kind="search_page",
                build_query=default_query,
                search_url_builder=lambda query: "https://www.fondazionefossoli.org/centro-studi/i-nomi-di-fossoli/",
            ),
            query=PersonQuery(
                full_name="Guazzaloca Laura",
                family_name="Guazzaloca",
                given_name="Laura",
                birth_date="28 gennaio 1920, Bologna",
            ),
            profile=profile,
        )

        self.assertEqual([attempt.attempt_id for attempt in attempts], ["nome-cognome", "nome-cognome-nascita", "solo-cognome"])
        self.assertEqual(attempts[0].fields["nome"], "Laura")
        self.assertEqual(attempts[0].fields["cognome"], "Guazzaloca")
        self.assertEqual(attempts[1].fields["giorno_nascita"], "28")
        self.assertEqual(attempts[1].fields["mese_nascita"], "01")
        self.assertEqual(attempts[1].fields["anno_nascita"], "1920")
        self.assertEqual(attempts[2].fields["cognome"], "Guazzaloca")


if __name__ == "__main__":
    unittest.main()
