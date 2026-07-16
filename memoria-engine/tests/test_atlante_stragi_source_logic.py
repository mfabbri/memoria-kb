from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.generic_result_parser import extract_generic_result_signals
from caduti_fonti_report.connectors.search_executor import PostFormSearchExecutor
from caduti_fonti_report.config import load_source_registry
from caduti_fonti_report.models import PersonQuery
from caduti_fonti_report.search_result_logic import SearchResultInterpreter, load_source_result_logic
from caduti_fonti_report.source_definitions import load_source_definition
from caduti_fonti_report.source_strategies import build_attempts_from_strategy_definition


class AtlanteStragiSourceLogicTests(unittest.TestCase):
    def test_registry_search_url_uses_advanced_search_page(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = load_source_registry(repo_root / "ricerche" / "camalanca_fonti.yaml")["atlante_stragi"]

        url = source.search_url_builder("")

        self.assertEqual(url, "https://www.straginazifasciste.it/?page_id=349")

    def test_strategy_uses_advanced_date_place_filters_not_person_name_search(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = load_source_registry(repo_root / "ricerche" / "camalanca_fonti.yaml")["atlante_stragi"]
        definition = load_source_definition(source, repo_root=repo_root)

        attempts = build_attempts_from_strategy_definition(
            definition=definition.strategy_definition,
            source=source,
            query=PersonQuery(
                full_name="Andreoli Dino",
                given_name="Dino",
                family_name="Andreoli",
                death_date="11 ottobre 1944, battaglia di Purocielo/Ca Marcone",
            ),
            profile=definition.profile,
        )

        self.assertEqual(attempts[0].fields["giornoin"], "11")
        self.assertEqual(attempts[0].fields["mese_in"], "1944-10")
        self.assertEqual(attempts[0].fields["giornofin"], "11")
        self.assertEqual(attempts[0].fields["mese_fin"], "1944-10")
        self.assertEqual(attempts[0].fields["comune"], "4030")
        self.assertEqual(attempts[0].fields["tipo_vittima"], "partigiani")
        self.assertNotIn("s", attempts[0].fields)
        self.assertEqual(attempts[0].metadata["field_resolution.kind"], "source_place_mapping")
        self.assertEqual(attempts[0].metadata["field_resolution.id"], "atlante-place-purocielo-ca-marcone")
        self.assertEqual(attempts[0].metadata["field_resolution.review_status"], "unreviewed")
        self.assertIn("comune=4030", attempts[0].metadata["field_resolution.output_fields"])

    def test_post_form_executor_submits_advanced_filters(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = load_source_registry(repo_root / "ricerche" / "camalanca_fonti.yaml")["atlante_stragi"]
        seen: dict[str, object] = {}

        def fake_fetcher(url: str, form_data: dict[str, str], timeout: int):
            seen["url"] = url
            seen["form_data"] = form_data
            return url, "<html><body>Nessun risultato</body></html>"

        executor = PostFormSearchExecutor(fetcher=fake_fetcher)
        attempt = build_attempts_from_strategy_definition(
            definition=load_source_definition(source, repo_root=repo_root).strategy_definition,
            source=source,
            query=PersonQuery(
                full_name="Andreoli Dino",
                given_name="Dino",
                family_name="Andreoli",
                death_date="11 ottobre 1944, battaglia di Purocielo/Ca Marcone",
            ),
        )[0]

        result = executor.execute(source=source, attempt=attempt)[0]

        self.assertEqual(result.status, "ok")
        self.assertEqual(seen["url"], "https://www.straginazifasciste.it/?page_id=349")
        self.assertEqual(seen["form_data"]["mese_in"], "1944-10")
        self.assertEqual(seen["form_data"]["comune"], "4030")

    def test_result_logic_filters_wordpress_navigation_noise(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result_logic = load_source_result_logic(repo_root.parent / "memoria-sources" / "source_result_logic" / "atlante_stragi.yaml")
        fixture = repo_root / "tests" / "fixtures" / "source_results" / "atlante_stragi" / "wordpress_search_results.html"

        signals = extract_generic_result_signals(
            source_id="atlante_stragi",
            engine=result_logic.engine,
            html_text=fixture.read_text(encoding="utf-8"),
            result_url="https://www.straginazifasciste.it/?page_id=349&lang=en",
            result_logic=result_logic,
        )
        assessment = SearchResultInterpreter(result_logic).interpret(signals)

        self.assertEqual(assessment.assessment, "candidate_results")
        self.assertTrue(assessment.review_required)
        self.assertEqual(
            [link.title for link in assessment.candidate_links],
            ["TEBANO FAENZA 06.10.1944", "SAN BERNARDINO LUGO DI ROMAGNA 09.10.1944"],
        )
        self.assertTrue(all("id_strage=" in link.url for link in assessment.candidate_links))


if __name__ == "__main__":
    unittest.main()
