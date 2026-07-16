from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.generic_result_parser import extract_generic_result_signals
from caduti_fonti_report.search_result_logic import source_result_logic_from_dict


class GenericResultParserCandidateFiltersTests(unittest.TestCase):
    def test_candidate_filters_remove_navigation_noise_from_generic_anchors(self) -> None:
        definition = source_result_logic_from_dict(
            {
                "source_id": "oesta_ais_feldsuche",
                "engine": "test",
                "signals": {"result_link_selector": "a[href]"},
                "candidate_filters": {
                    "exclude_url_patterns": ["javascript:", "#", "login", "language="],
                    "exclude_title_patterns": ["Login", "Deutsch", "Home"],
                    "min_title_length": 3,
                    "require_non_empty_title": True,
                },
            }
        )
        html = """
        <html><body>
          <a href="javascript:void(0)">Print</a>
          <a href="#main">Home</a>
          <a href="/login">Login</a>
          <a href="/feldsuche/detail/AT-OeSTA-KA-FA-AOK-1">Rossi Mario, fascicolo</a>
        </body></html>
        """

        signals = extract_generic_result_signals(
            source_id="oesta_ais_feldsuche",
            engine="test",
            html_text=html,
            result_url="https://www.archivinformationssystem.at/feldsuche.aspx",
            result_logic=definition,
        )

        self.assertEqual(len(signals.candidate_links), 1)
        self.assertEqual(signals.candidate_links[0].title, "Rossi Mario, fascicolo")

    def test_candidate_filters_can_require_specific_url_fragment(self) -> None:
        definition = source_result_logic_from_dict(
            {
                "source_id": "tna_hs9",
                "engine": "test",
                "signals": {"result_link_selector": "a[href]"},
                "candidate_filters": {
                    "include_url_patterns": ["/details/r/"],
                    "exclude_url_patterns": ["login", "help"],
                    "min_title_length": 4,
                },
            }
        )
        html = """
        <html><body>
          <a href="/help">Help</a>
          <a href="/browse/r/hierarchy">Browse</a>
          <a href="/details/r/C123456">HS 9/123/1 Rossi Mario</a>
        </body></html>
        """

        signals = extract_generic_result_signals(
            source_id="tna_hs9",
            engine="test",
            html_text=html,
            result_url="https://discovery.nationalarchives.gov.uk/results/r",
            result_logic=definition,
        )

        self.assertEqual([link.url for link in signals.candidate_links], ["https://discovery.nationalarchives.gov.uk/details/r/C123456"])


if __name__ == "__main__":
    unittest.main()
