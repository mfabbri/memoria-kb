from __future__ import annotations

from copy import deepcopy
import json
import unittest

from caduti_fonti_report.document_analysis.ocr_evidence_comparison import compare_ocr_page_evidence


def region(region_id: str, text: str, box: list[int]) -> dict:
    return {"region_id": region_id, "text": text, "geometry": {"bbox": box}}


def evidence(engine: str, regions: list[dict]) -> dict:
    return {
        "@type": "OcrPageEvidence", "page_id": "synthetic-page", "source_image_hash": "a" * 64,
        "engine": engine, "model": {"name": "synthetic-model"}, "language": "deu",
        "transform_id": "raw", "image_transform": {"name": "raw"},
        "source_page": {"original_page": {
            "page_id": "synthetic-page", "source_image_hash": "a" * 64,
            "source_file": "synthetic.tif", "source_dimensions": {"width": 300, "height": 160},
        }},
        "regions": regions,
    }


class OcrEvidenceComparisonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.left = evidence("synthetic-a", [region("a", "REPORT", [10, 10, 100, 30])])
        self.right = evidence("synthetic-b", [region("b", "REPORT", [11, 10, 101, 30])])

    def compare(self) -> dict:
        return compare_ocr_page_evidence(left=self.left, right=self.right)

    def test_exact_agreement_preserves_source_ids_text_and_provenance_without_mutation(self) -> None:
        before = deepcopy((self.left, self.right))
        result = self.compare()
        self.assertEqual(result["agreements"], [{
            "left_region_id": "a", "right_region_id": "b", "left_text": "REPORT", "right_text": "REPORT",
            "overlap_area": 1780.0, "exact_agreement": True, "normalized_agreement": True,
        }])
        self.assertEqual(result["left_evidence"]["source_page"], self.left["source_page"])
        self.assertEqual((self.left, self.right), before)
        result["left_evidence"]["source_page"]["original_page"]["source_file"] = "changed"
        self.assertEqual((self.left, self.right), before)
        self.assertEqual(result["disagreements"], [])
        self.assertEqual(result["unmatched_left_region_ids"], [])

    def test_normalized_equivalence_is_distinct_from_exact_agreement(self) -> None:
        self.left["regions"][0]["text"] = "  ＲＥＰＯＲＴ\n Straße "
        self.right["regions"][0]["text"] = "report strasse"
        pair = self.compare()["agreements"][0]
        self.assertFalse(pair["exact_agreement"])
        self.assertTrue(pair["normalized_agreement"])
        self.assertEqual(pair["left_text"], "  ＲＥＰＯＲＴ\n Straße ")

    def test_disagreement_does_not_correct_punctuation_or_accent(self) -> None:
        for right_text in ("REPORT!", "REPÖRT", "OTHER"):
            with self.subTest(text=right_text):
                self.right["regions"][0]["text"] = right_text
                result = self.compare()
                self.assertEqual(result["agreements"], [])
                pair = result["disagreements"][0]
                self.assertFalse(pair["normalized_agreement"])
                self.assertEqual(pair["right_text"], right_text)

    def test_polygon_envelope_aligns_with_bbox(self) -> None:
        self.right["regions"][0]["geometry"] = {
            "polygon": [[11, 10], [101, 10], [101, 30], [11, 30]],
        }
        self.assertEqual(len(self.compare()["agreements"]), 1)
        self.right["regions"][0]["geometry"]["polygon"].append([11, 10])
        self.assertEqual(len(self.compare()["agreements"]), 1)

    def test_touching_edges_are_unmatched_and_any_positive_overlap_is_reported(self) -> None:
        self.right["regions"][0]["geometry"]["bbox"] = [100, 10, 200, 30]
        result = self.compare()
        self.assertEqual(result["agreements"], [])
        self.assertEqual(result["unmatched_left_region_ids"], ["a"])
        self.assertEqual(result["unmatched_right_region_ids"], ["b"])
        self.right["regions"][0]["geometry"]["bbox"][0] = 99.999
        self.assertGreater(self.compare()["agreements"][0]["overlap_area"], 0)

    def test_split_merge_and_many_to_many_are_ambiguous_and_unmatched(self) -> None:
        self.left["regions"] = [region("whole", "ONE TWO", [10, 10, 110, 30])]
        self.right["regions"] = [region("word-1", "ONE", [10, 10, 55, 30]),
                                 region("word-2", "TWO", [60, 10, 110, 30])]
        for swap in (False, True):
            with self.subTest(swap=swap):
                result = compare_ocr_page_evidence(
                    left=self.right if swap else self.left, right=self.left if swap else self.right)
                self.assertEqual(result["agreements"], [])
                self.assertEqual(result["disagreements"], [])
                self.assertEqual(len(result["ambiguous_overlaps"]), 1)
                self.assertEqual(len(result["ambiguous_overlaps"][0]["overlaps"]), 2)
                self.assertEqual(len(result["unmatched_left_region_ids"]), 2 if swap else 1)
        self.left["regions"].append(region("overlapping-line", "OTHER", [15, 10, 105, 30]))
        self.assertEqual(len(self.compare()["ambiguous_overlaps"][0]["overlaps"]), 4)

    def test_deterministic_order_is_independent_of_region_input_order_and_text(self) -> None:
        self.left["regions"] += [region("z", "Z", [10, 80, 100, 100]),
                                  region("unmatched", "U", [200, 100, 220, 120])]
        self.right["regions"] += [region("y", "Z", [11, 80, 101, 100])]
        expected = self.compare()
        self.left["regions"].reverse()
        self.right["regions"].reverse()
        self.assertEqual(self.compare(), expected)
        self.right["regions"][0]["text"] = "REPORT"
        self.assertEqual(self.compare()["disagreements"][0]["left_region_id"], "z")

    def test_distinguishable_model_is_accepted_but_transform_or_language_is_not(self) -> None:
        self.right["engine"] = self.left["engine"]
        with self.assertRaisesRegex(ValueError, "engine/model"):
            self.compare()
        self.right["model"]["name"] = "another-synthetic-model"
        self.assertEqual(len(self.compare()["agreements"]), 1)

    def test_same_region_ids_and_matching_crop_retain_distinct_reading_provenance(self) -> None:
        self.right["regions"][0]["region_id"] = "a"
        for item in (self.left, self.right):
            item["source_page"]["crop"] = {"left": 10, "top": 10, "right": 200, "bottom": 100}
        result = self.compare()
        self.assertEqual(result["agreements"][0]["left_region_id"], "a")
        self.assertEqual(result["agreements"][0]["right_region_id"], "a")
        self.assertNotEqual(result["left_evidence"]["engine"], result["right_evidence"]["engine"])

    def test_identity_and_frame_mismatches_fail_closed(self) -> None:
        mutations = [
            lambda item: item.update({"@type": "Other"}),
            lambda item: item.update({"page_id": "other"}),
            lambda item: item.update({"source_image_hash": "b" * 64}),
            lambda item: item.update({"language": "ita"}),
            lambda item: item.update({"transform_id": "resized"}),
            lambda item: item.update({"image_transform": {"name": "resize", "scale": 2}}),
            lambda item: item["source_page"]["original_page"].update({"source_file": "other.tif"}),
            lambda item: item["source_page"]["original_page"]["source_dimensions"].update({"width": 301}),
            lambda item: item["source_page"].update({"crop": {"left": 0, "top": 0, "right": 200, "bottom": 100}}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                other = deepcopy(self.right)
                mutation(other)
                with self.assertRaises(ValueError):
                    compare_ocr_page_evidence(left=self.left, right=other)

    def test_malformed_identity_is_rejected_even_when_both_inputs_match(self) -> None:
        mutations = [
            lambda item: item.update({"model": {}}),
            lambda item: item.update({"image_transform": {"scale": float("nan")}}),
            lambda item: item["source_page"]["original_page"]["source_dimensions"].update({"width": True}),
            lambda item: item["source_page"].update({"crop": {"left": 0, "top": 0, "right": 301, "bottom": 160}}),
            lambda item: item["source_page"].pop("original_page"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                left, right = deepcopy(self.left), deepcopy(self.right)
                mutation(left)
                mutation(right)
                with self.assertRaises(ValueError):
                    compare_ocr_page_evidence(left=left, right=right)

    def test_invalid_geometry_fails_closed(self) -> None:
        values = [None, {}, {"bbox": [1, 2, 3]}, {"bbox": [1, 2, 1, 4]},
                  {"bbox": [3, 2, 1, 4]}, {"bbox": [-1, 2, 3, 4]},
                  {"bbox": [True, 2, 3, 4]}, {"bbox": [1, 2, float("inf"), 4]},
                  {"bbox": [1, float("nan"), 3, 4]}, {"bbox": [0, 0, 1e308, 1e308]},
                  {"polygon": [[1, 2], [3, 4]]},
                  {"polygon": [[1, 2], [2, 3], [3, 4]]},
                  {"polygon": [[10, 10], [100, 30], [10, 30], [80, 10]]},
                  {"polygon": [[10, 10], [100, 10], [100, 10], [10, 30]]},
                  {"polygon": [[1, 2], [3, 2], [3, True]]},
                  {"bbox": [1, 2, 3, 4], "polygon": [[1, 2], [4, 2], [4, 4], [1, 4]]}]
        for value in values:
            with self.subTest(geometry=value):
                self.right["regions"][0]["geometry"] = value
                with self.assertRaises(ValueError):
                    self.compare()

    def test_invalid_region_identity_and_text_fail_closed(self) -> None:
        for field, value in (("region_id", ""), ("region_id", None), ("text", None)):
            other = deepcopy(self.right)
            other["regions"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                compare_ocr_page_evidence(left=self.left, right=other)
        self.right["regions"].append(deepcopy(self.right["regions"][0]))
        with self.assertRaises(ValueError):
            self.compare()

    def test_diagnostic_flags_do_not_certify_visual_coverage_or_machine_pass(self) -> None:
        self.left["regions"] = []
        self.right["regions"] = []
        result = self.compare()
        self.assertTrue(result["diagnostic_only"])
        for flag in ("text_correction_performed", "visual_coverage_verified",
                     "shared_omission_detection_performed", "machine_pass_allowed"):
            self.assertFalse(result[flag])
        self.assertEqual(result["agreements"], [])
        self.assertNotIn("accuracy", result)
        self.assertNotIn("coverage", result)
        self.assertNotIn("routing", result)
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
