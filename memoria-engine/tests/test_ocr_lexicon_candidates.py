from __future__ import annotations

import unittest

from caduti_fonti_report.document_analysis.ocr_lexicon_candidates import (
    LexiconEntry,
    rank_ocr_candidates,
)


class OcrLexiconCandidatesTest(unittest.TestCase):
    def test_ranking_is_deterministic_and_preserves_raw_text(self) -> None:
        raw = "Musterwrot Sig-X"
        lexicon = [
            LexiconEntry("Musterwort", "german-like", "fixture-de", "1"),
            LexiconEntry("Sig-A", "military-abbreviation", "fixture-mil", "1"),
        ]
        first = rank_ocr_candidates(raw, lexicon, source_document_id="synthetic-page", source_region_id="region-1", max_distance=2)
        second = rank_ocr_candidates(raw, reversed(lexicon), source_document_id="synthetic-page", source_region_id="region-1", max_distance=2)
        self.assertEqual(first, second)
        self.assertEqual(first["raw_text"], raw)
        self.assertEqual(first["source_document_id"], "synthetic-page")
        self.assertTrue(first["raw_ocr_unchanged"])
        self.assertEqual(first["review_status"], "unreviewed")
        self.assertEqual(first["tokens"][0]["suggestions"][0]["term"], "Musterwort")
        self.assertEqual(first["tokens"][1]["suggestions"][0]["source_id"], "fixture-mil")

    def test_provenance_and_threshold_are_explicit(self) -> None:
        result = rank_ocr_candidates(
            "unrelated",
            [LexiconEntry("Sig-A", "military-abbreviation", "fixture-mil", "2026-09")],
            source_document_id="synthetic-page", source_region_id="region-1",
            max_distance=1,
        )
        suggestion = result["tokens"][0]["suggestions"]
        self.assertEqual(suggestion, [])
        result = rank_ocr_candidates(
            "Sig-X",
            [LexiconEntry("Sig-A", "military-abbreviation", "fixture-mil", "2026-09")],
            source_document_id="synthetic-page", source_region_id="region-1",
            max_distance=1,
        )
        self.assertEqual(result["tokens"][0]["suggestions"][0]["category"], "military-abbreviation")
        self.assertEqual(result["tokens"][0]["suggestions"][0]["version"], "2026-09")
        self.assertEqual(result["tokens"][0]["suggestions"][0]["score_kind"], "lexicon_similarity_not_ocr_confidence")

    def test_invalid_parameters_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            rank_ocr_candidates("text", [], source_document_id="synthetic-page", source_region_id="region-1", max_distance=-1)
        with self.assertRaises(TypeError):
            rank_ocr_candidates("text", ["not-an-entry"], source_document_id="synthetic-page", source_region_id="region-1")


if __name__ == "__main__":
    unittest.main()
