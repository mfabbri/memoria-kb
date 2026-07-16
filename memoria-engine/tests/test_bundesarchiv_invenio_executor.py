from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.bundesarchiv_invenio_executor import (
    _extract_tree_node_candidates,
    _synthetic_results_html,
)
from caduti_fonti_report.connectors.bundesarchiv_invenio_parsing import (
    extract_tree_node_candidates,
)
from caduti_fonti_report.connectors.generic_result_parser import extract_generic_result_signals
from caduti_fonti_report.search_result_logic import SearchResultInterpreter, load_source_result_logic


class BundesarchivInvenioExecutorTests(unittest.TestCase):
    def test_expanded_tektonik_response_marks_record_like_nodes(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        fixture = repo_root / "tests" / "fixtures" / "bundesarchiv_invenio" / "full_tektonik_response.xml"
        xml_text = fixture.read_text(encoding="utf-8")

        candidates = _extract_tree_node_candidates(
            html_text=xml_text,
            base_url="https://invenio.bundesarchiv.de/invenio/main.xhtml",
            response_index=1,
        )

        self.assertEqual(len(candidates), 2)
        self.assertIn("#invenio-tektonik-0_1", candidates[0].url)
        self.assertIn("intermediate_candidate", candidates[0].snippet)
        self.assertIn("#invenio-record-0_1_7", candidates[1].url)
        self.assertIn("record_candidate", candidates[1].snippet)
        self.assertIn("BArch R 70", candidates[1].title)

    def test_parsing_helper_extracts_tree_nodes_without_playwright(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        fixture = repo_root / "tests" / "fixtures" / "bundesarchiv_invenio" / "full_tektonik_response.xml"

        candidates = extract_tree_node_candidates(
            html_text=fixture.read_text(encoding="utf-8"),
            base_url="https://invenio.bundesarchiv.de/invenio/main.xhtml",
            response_index=1,
        )

        self.assertEqual(len(candidates), 2)
        self.assertIn("intermediate_candidate", candidates[0].snippet)
        self.assertIn("record_candidate", candidates[1].snippet)

    def test_synthetic_record_candidates_pass_bundesarchiv_result_logic(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result_logic = load_source_result_logic(repo_root.parent / "memoria-sources" / "source_result_logic" / "bundesarchiv_invenio.yaml")
        interpreter = SearchResultInterpreter(result_logic)
        fixture = repo_root / "tests" / "fixtures" / "bundesarchiv_invenio" / "full_tektonik_response.xml"
        candidates = _extract_tree_node_candidates(
            html_text=fixture.read_text(encoding="utf-8"),
            base_url="https://invenio.bundesarchiv.de/invenio/main.xhtml",
            response_index=1,
        )
        html_text = _synthetic_results_html(
            candidates=candidates,
            page_url="https://invenio.bundesarchiv.de/invenio/main.xhtml",
            actual_html="",
        )

        signals = extract_generic_result_signals(
            source_id="bundesarchiv_invenio",
            engine=result_logic.engine,
            html_text=html_text,
            result_url="https://invenio.bundesarchiv.de/invenio/main.xhtml",
            result_logic=result_logic,
        )
        assessment = interpreter.interpret(signals)

        self.assertEqual(assessment.assessment, "candidate_results")
        self.assertEqual(len(assessment.candidate_links), 2)
        self.assertTrue(any("#invenio-record-" in link.url for link in assessment.candidate_links))


if __name__ == "__main__":
    unittest.main()
