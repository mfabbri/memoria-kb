from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.cwgc_result_parser import extract_cwgc_result_signals
from caduti_fonti_report.connectors.cwgc_source_connector import CwgcSourceConnector
from caduti_fonti_report.models import PersonQuery, Source
from caduti_fonti_report.queries import default_query
from caduti_fonti_report.search_result_logic import SearchResultInterpreter, load_source_result_logic
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
            "war_select": "2",
            **(form or {}),
        },
        note="Ricerca pubblica Find War Dead.",
    )


def no_results_html() -> str:
    return """
    <html><body>
      <h1>No search results</h1>
    </body></html>
    """


def candidate_results_html(total: int = 2) -> str:
    return f"""
    <html><body>
      <h1>Your Search Results</h1>
      <h2>SHOW 2 OF {total} WAR DEAD</h2>
      <table>
        <tr>
          <td><strong>PETER PANOS</strong></td>
          <td><a href="/find-records/find-war-dead/casualty-details/123/peter-panos/">More details</a></td>
        </tr>
        <tr>
          <td><strong>PANO THABENG</strong></td>
          <td><a href="/find-records/find-war-dead/casualty-details/456/pano-thabeng/">More details</a></td>
        </tr>
      </table>
    </body></html>
    """


def close_matches_results_html(total: int = 2) -> str:
    return f"""
    <html><body>
      <h1>No search results</h1>
      <nav class="tabs">
        <a class="tab" href="/find-records/find-war-dead/search-results/exact/">EXACT MATCHES</a>
        <a class="tab active" href="/find-records/find-war-dead/search-results/close/">CLOSE MATCHES</a>
        <a class="tab" href="/find-records/find-war-dead/search-results/all/">ALL MATCHES</a>
      </nav>
      <h2>SHOW 2 OF {total} WAR DEAD</h2>
      <table>
        <tr>
          <td><strong>ANDREOLI DINO</strong></td>
          <td><a href="/find-records/find-war-dead/casualty-details/123/andreoli-dino/">More details</a></td>
        </tr>
        <tr>
          <td><strong>ANDREOLA DINO</strong></td>
          <td><a href="/find-records/find-war-dead/casualty-details/456/andreola-dino/">More details</a></td>
        </tr>
      </table>
    </body></html>
    """


def connector(html_by_url_substring: dict[str, str]) -> CwgcSourceConnector:
    repo_root = Path(__file__).resolve().parents[1]

    def html_provider(execution_result):
        url = execution_result.url.casefold()
        for substring, html in html_by_url_substring.items():
            if substring.casefold() in url:
                return html
        return no_results_html()

    return CwgcSourceConnector(
        make_cwgc_source(),
        profile=load_source_search_profile(repo_root.parent / "memoria-sources" / "source_profiles" / "cwgc.yaml"),
        strategy_definition=load_source_search_strategy(repo_root.parent / "memoria-sources" / "source_strategies" / "cwgc.yaml"),
        result_logic=load_source_result_logic(repo_root.parent / "memoria-sources" / "source_result_logic" / "cwgc.yaml"),
        html_provider=html_provider,
        run_id="cwgc-test",
        now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
    )


class CwgcSourceConnectorTests(unittest.TestCase):
    def test_result_parser_extracts_counts_and_candidate_links(self) -> None:
        signals = extract_cwgc_result_signals(
            html_text=candidate_results_html(total=2),
            result_url="https://www.cwgc.org/find-records/find-war-dead/search-results/",
        )

        self.assertEqual(signals.heading, "Your Search Results")
        self.assertEqual(signals.shown_results, 2)
        self.assertEqual(signals.total_results, 2)
        self.assertEqual([link.title for link in signals.candidate_links], ["PETER PANOS", "PANO THABENG"])
        self.assertTrue(signals.candidate_links[0].url.startswith("https://www.cwgc.org/find-records/"))

    def test_result_parser_can_read_close_matches_tab_declaratively(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result_logic = load_source_result_logic(repo_root.parent / "memoria-sources" / "source_result_logic" / "cwgc.yaml")
        interpreter = SearchResultInterpreter(result_logic)

        signals = extract_cwgc_result_signals(
            html_text=close_matches_results_html(total=2),
            result_url="https://www.cwgc.org/find-records/find-war-dead/search-results/close/",
            result_logic=result_logic,
        )
        assessment = interpreter.interpret(signals)

        self.assertEqual(signals.metadata["active_result_tab"], "close_matches")
        self.assertEqual(signals.total_results, 2)
        self.assertEqual(assessment.assessment, "candidate_results")
        self.assertEqual([link.title for link in assessment.candidate_links], ["ANDREOLI DINO", "ANDREOLA DINO"])

    def test_connector_interprets_cwgc_results_without_creating_claims(self) -> None:
        cwgc = connector(
            {
                "Surname=Panov&Forename=Sergio": no_results_html(),
                "Surname=Panov&Forename=&": candidate_results_html(total=2),
            }
        )

        results = cwgc.search_person(PersonQuery(full_name="PANOV SERGIO"))

        self.assertEqual([result.status for result in results], ["no_results", "candidate_results"])
        self.assertEqual(len(results[1].hits), 2)
        self.assertEqual([hit.title for hit in results[1].hits], ["PETER PANOS", "PANO THABENG"])

        documents = cwgc.fetch_detail(results[1])
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].source_id, "cwgc")
        self.assertEqual(documents[0].access_date, "2026-05-01")
        self.assertEqual(documents[0].metadata["access_mode"], "reference_only")
        self.assertEqual(documents[0].metadata["document_type"], "candidate_reference")
        self.assertEqual(cwgc.extract_evidence(documents[0]), [])

    def test_connector_marks_truncated_candidate_results(self) -> None:
        cwgc = connector({"Surname=Gianni&Forename=&": candidate_results_html(total=26)})

        results = cwgc.search_person(PersonQuery(full_name="GIANNI", given_name="GIANNI"))

        self.assertEqual(results[0].status, "candidate_results_truncated")
        self.assertEqual(len(results[0].hits), 2)

    def test_connector_marks_huge_mononym_as_too_broad(self) -> None:
        cwgc = connector({"Surname=&Forename=Willi": candidate_results_html(total=104)})

        results = cwgc.search_person(PersonQuery(full_name="WILLI", given_name="WILLI"))

        self.assertEqual([result.status for result in results], ["no_results", "too_broad"])
        self.assertEqual(results[1].hits, [])

    def test_fetch_detail_keeps_no_result_search_page_as_reference(self) -> None:
        cwgc = connector({"Surname=Sadavich&Forename=Carlo": no_results_html()})

        result = cwgc.search_person(PersonQuery(full_name="SADAVICH CARLO"))[0]
        documents = cwgc.fetch_detail(result)

        self.assertEqual(result.status, "no_results")
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].metadata["document_type"], "search_result_reference")
        self.assertEqual(documents[0].metadata["source_result_status"], "no_results")


if __name__ == "__main__":
    unittest.main()
