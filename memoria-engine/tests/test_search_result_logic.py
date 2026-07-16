from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.search_result_logic import (
    CandidateLink,
    SearchResultInterpreter,
    SearchResultSignals,
    load_source_result_logic,
)


class SearchResultLogicTests(unittest.TestCase):
    def test_load_real_cwgc_result_logic(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        definition = load_source_result_logic(repo_root.parent / "memoria-sources" / "source_result_logic" / "cwgc.yaml")

        self.assertEqual(definition.source_id, "cwgc")
        self.assertEqual(definition.engine, "cwgc_find_war_dead")
        self.assertEqual(definition.candidate_limit, 10)
        self.assertEqual(definition.too_broad_threshold, 50)

    def test_interpreter_classifies_no_results_from_heading(self) -> None:
        definition = load_source_result_logic(Path(__file__).resolve().parents[2] / "memoria-sources" / "source_result_logic" / "cwgc.yaml")
        interpreter = SearchResultInterpreter(definition)

        assessment = interpreter.interpret(
            SearchResultSignals(
                source_id="cwgc",
                heading="No search results",
                metadata={"active_result_tab": "exact_matches"},
            )
        )

        self.assertEqual(assessment.assessment, "no_results")
        self.assertFalse(assessment.review_required)
        self.assertEqual(assessment.candidate_links, [])

    def test_interpreter_does_not_treat_close_matches_tab_as_no_results(self) -> None:
        definition = load_source_result_logic(Path(__file__).resolve().parents[2] / "memoria-sources" / "source_result_logic" / "cwgc.yaml")
        interpreter = SearchResultInterpreter(definition)

        assessment = interpreter.interpret(
            SearchResultSignals(
                source_id="cwgc",
                heading="No search results",
                shown_results=2,
                total_results=2,
                candidate_links=[
                    CandidateLink(title="ANDREOLI DINO", url="https://www.cwgc.org/a"),
                    CandidateLink(title="ANDREOLA DINO", url="https://www.cwgc.org/b"),
                ],
                metadata={"active_result_tab": "close_matches"},
            )
        )

        self.assertEqual(assessment.assessment, "candidate_results")
        self.assertEqual(len(assessment.candidate_links), 2)

    def test_interpreter_keeps_short_candidate_list(self) -> None:
        definition = load_source_result_logic(Path(__file__).resolve().parents[2] / "memoria-sources" / "source_result_logic" / "cwgc.yaml")
        interpreter = SearchResultInterpreter(definition)

        assessment = interpreter.interpret(
            SearchResultSignals(
                source_id="cwgc",
                heading="Your Search Results",
                shown_results=2,
                total_results=2,
                candidate_links=[
                    CandidateLink(title="PETER PANOS", url="https://www.cwgc.org/a"),
                    CandidateLink(title="PANO THABENG", url="https://www.cwgc.org/b"),
                ],
            )
        )

        self.assertEqual(assessment.assessment, "candidate_results")
        self.assertTrue(assessment.review_required)
        self.assertEqual([link.title for link in assessment.candidate_links], ["PETER PANOS", "PANO THABENG"])

    def test_interpreter_truncates_medium_candidate_list(self) -> None:
        definition = load_source_result_logic(Path(__file__).resolve().parents[2] / "memoria-sources" / "source_result_logic" / "cwgc.yaml")
        interpreter = SearchResultInterpreter(definition)

        assessment = interpreter.interpret(
            SearchResultSignals(
                source_id="cwgc",
                heading="Your Search Results",
                shown_results=10,
                total_results=26,
                candidate_links=[CandidateLink(title=f"Candidate {index}", url=f"https://example.test/{index}") for index in range(12)],
            )
        )

        self.assertEqual(assessment.assessment, "candidate_results_truncated")
        self.assertEqual(len(assessment.candidate_links), 10)

    def test_interpreter_can_mark_huge_mononym_as_too_broad(self) -> None:
        definition = load_source_result_logic(Path(__file__).resolve().parents[2] / "memoria-sources" / "source_result_logic" / "cwgc.yaml")
        interpreter = SearchResultInterpreter(definition)

        assessment = interpreter.interpret(
            SearchResultSignals(
                source_id="cwgc",
                heading="Your Search Results",
                shown_results=10,
                total_results=104,
                metadata={"query_is_mononym": "true"},
            )
        )

        self.assertEqual(assessment.assessment, "too_broad")
        self.assertEqual(assessment.candidate_links, [])

    def test_storia_memoria_bo_logic_can_use_detail_link_count(self) -> None:
        definition = load_source_result_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_result_logic" / "storia_memoria_bo.yaml"
        )
        interpreter = SearchResultInterpreter(definition)

        assessment = interpreter.interpret(
            SearchResultSignals(
                source_id="storia_memoria_bo",
                engine="storia_memoria_bo_advanced_people",
                candidate_links=[
                    CandidateLink(title="Andreoli Dino", url="https://www.storiaememoriadibologna.it/andreoli-dino"),
                ],
            )
        )

        self.assertEqual(assessment.assessment, "candidate_results")
        self.assertTrue(assessment.review_required)
        self.assertEqual(assessment.candidate_links[0].title, "Andreoli Dino")

    def test_partigiani_italia_logic_can_use_detail_link_count(self) -> None:
        definition = load_source_result_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_result_logic" / "partigiani_italia.yaml"
        )
        interpreter = SearchResultInterpreter(definition)

        assessment = interpreter.interpret(
            SearchResultSignals(
                source_id="partigiani_italia",
                engine="partigiani_italia_public_search",
                candidate_links=[
                    CandidateLink(title="ANDREOLI DINO", url="https://partigianiditalia.cultura.gov.it/example"),
                ],
            )
        )

        self.assertEqual(assessment.assessment, "candidate_results")
        self.assertTrue(assessment.review_required)
        self.assertEqual(assessment.candidate_links[0].title, "ANDREOLI DINO")

    def test_tna_wo417_logic_can_use_detail_link_count(self) -> None:
        definition = load_source_result_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_result_logic" / "tna_wo417.yaml"
        )
        interpreter = SearchResultInterpreter(definition)

        assessment = interpreter.interpret(
            SearchResultSignals(
                source_id="tna_wo417",
                engine="tna_discovery_advanced_search",
                candidate_links=[
                    CandidateLink(title="WO 417 record", url="https://discovery.nationalarchives.gov.uk/details/r/example"),
                ],
            )
        )

        self.assertEqual(assessment.assessment, "candidate_results")
        self.assertTrue(assessment.review_required)
        self.assertEqual(assessment.candidate_links[0].title, "WO 417 record")


if __name__ == "__main__":
    unittest.main()
