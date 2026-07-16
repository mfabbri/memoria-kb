from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.cwgc_strategy import CwgcSearchStrategy, CwgcUrlSearchExecutor
from caduti_fonti_report.models import PersonQuery, Source
from caduti_fonti_report.queries import default_query
from caduti_fonti_report.source_profiles import load_source_search_profile
from caduti_fonti_report.source_strategies import load_source_search_strategy


def make_cwgc_source(form: dict[str, str] | None = None) -> Source:
    return Source(
        source_id="cwgc",
        source_name="CWGC",
        kind="cwgc",
        build_query=default_query,
        search_url_builder=lambda query: "https://www.cwgc.org/find-records/find-war-dead/",
        form={
            "results_base_url": "https://www.cwgc.org/find-records/find-war-dead/search-results/",
            "name_order": "surname_first",
            **(form or {}),
        },
        note="Ricerca pubblica Find War Dead.",
    )


class CwgcSearchStrategyTests(unittest.TestCase):
    def test_two_token_name_generates_name_and_surname_attempts(self) -> None:
        strategy = CwgcSearchStrategy()

        attempts = strategy.build_attempts(
            source=make_cwgc_source(),
            query=PersonQuery(full_name="PANOV SERGIO"),
        )

        self.assertEqual([attempt.attempt_id for attempt in attempts], ["cognome-nome-ww2", "solo-cognome-ww2"])
        self.assertEqual(attempts[0].fields["Surname"], "PANOV")
        self.assertEqual(attempts[0].fields["Forename"], "SERGIO")
        self.assertEqual(attempts[0].fields["WarSelect"], "2")
        self.assertEqual(attempts[1].fields["Surname"], "PANOV")
        self.assertEqual(attempts[1].fields["Forename"], "")

    def test_mononym_generates_surname_and_forename_attempts(self) -> None:
        strategy = CwgcSearchStrategy()

        attempts = strategy.build_attempts(source=make_cwgc_source(), query=PersonQuery(full_name="GIORGIO"))

        self.assertEqual(
            [attempt.attempt_id for attempt in attempts],
            ["mononimo-come-cognome-ww2", "mononimo-come-nome-ww2"],
        )
        self.assertEqual(attempts[0].fields["Surname"], "GIORGIO")
        self.assertEqual(attempts[0].fields["Forename"], "")
        self.assertEqual(attempts[1].fields["Surname"], "")
        self.assertEqual(attempts[1].fields["Forename"], "GIORGIO")

    def test_war_select_default_can_come_from_live_source_profile(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_source_search_profile(repo_root.parent / "memoria-sources" / "source_profiles" / "cwgc.yaml")
        strategy = CwgcSearchStrategy(profile=profile)

        attempts = strategy.build_attempts(source=make_cwgc_source(), query=PersonQuery(full_name="PANOV SERGIO"))

        self.assertEqual(attempts[0].fields["WarSelect"], "1")

    def test_source_form_war_select_overrides_profile_default(self) -> None:
        profile = load_source_search_profile(Path(__file__).resolve().parents[2] / "memoria-sources" / "source_profiles" / "cwgc.yaml")
        strategy = CwgcSearchStrategy(profile=profile)

        attempts = strategy.build_attempts(
            source=make_cwgc_source({"war_select": "2"}),
            query=PersonQuery(full_name="PANOV SERGIO"),
        )

        self.assertEqual(attempts[0].fields["WarSelect"], "2")

    def test_max_attempts_limits_generated_attempts(self) -> None:
        strategy = CwgcSearchStrategy()

        attempts = strategy.build_attempts(
            source=make_cwgc_source({"max_attempts": "1"}),
            query=PersonQuery(full_name="PANOV SERGIO"),
        )

        self.assertEqual([attempt.attempt_id for attempt in attempts], ["cognome-nome-ww2"])

    def test_url_executor_builds_cwgc_search_result_without_fetching(self) -> None:
        strategy = CwgcSearchStrategy()
        source = make_cwgc_source()
        attempt = strategy.build_attempts(source=source, query=PersonQuery(full_name="PANOV SERGIO"))[0]
        executor = CwgcUrlSearchExecutor()

        results = executor.execute(source=source, attempt=attempt)

        self.assertEqual(len(results), 1)
        self.assertIs(results[0].attempt, attempt)
        self.assertEqual(results[0].status, "search_url_ready")
        self.assertIn("/find-records/find-war-dead/search-results/", results[0].url)
        self.assertIn("Surname=PANOV", results[0].url)
        self.assertIn("Forename=SERGIO", results[0].url)
        self.assertIn("WarSelect=2", results[0].url)
        self.assertEqual(results[0].payload["access_mode"], "url_only")

    def test_can_use_declarative_strategy_definition(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        profile = load_source_search_profile(repo_root.parent / "memoria-sources" / "source_profiles" / "cwgc.yaml")
        definition = load_source_search_strategy(repo_root.parent / "memoria-sources" / "source_strategies" / "cwgc.yaml")
        strategy = CwgcSearchStrategy(profile=profile, strategy_definition=definition)

        attempts = strategy.build_attempts(
            source=make_cwgc_source({"war_select": "2"}),
            query=PersonQuery(full_name="PANOV SERGIO"),
        )

        self.assertEqual([attempt.attempt_id for attempt in attempts], ["cognome-nome-ww2", "solo-cognome-ww2"])
        self.assertEqual(attempts[0].fields["Surname"], "PANOV")
        self.assertEqual(attempts[0].fields["Forename"], "SERGIO")
        self.assertEqual(attempts[0].fields["WarSelect"], "2")


if __name__ == "__main__":
    unittest.main()
