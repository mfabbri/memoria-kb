from __future__ import annotations

import unittest

from caduti_fonti_report.document_analysis.ocr_visual_ambiguity_resolver import (
    build_visual_resolver_preview,
)


class OcrVisualAmbiguityResolverTest(unittest.TestCase):
    def _build(self, resolver):
        return build_visual_resolver_preview(
            page_id="synthetic-page",
            source_image_hash="hash-page",
            variant_id="contrast-x1.8",
            source_bbox=[10, 20, 110, 60],
            crop_artifact="synthetic-crop.png",
            candidate_ocr="degraded OCR",
            resolver=resolver,
        )

    def test_preview_preserves_candidate_and_provenance(self) -> None:
        result = self._build(lambda request: {"text": "visible text"})
        self.assertEqual(result["candidate_ocr"], "degraded OCR")
        self.assertEqual(result["resolver_output"], {"text": "visible text"})
        self.assertEqual(result["source_page"]["source_bbox"], [10, 20, 110, 60])
        self.assertEqual(result["review_status"], "preview-only")
        self.assertEqual(result["promotion_status"], "unreviewed")
        self.assertEqual(result["temperature"], 0.0)

    def test_illegible_is_a_valid_schema_constrained_output(self) -> None:
        result = self._build(lambda request: {"text": "[illeggibile]"})
        self.assertEqual(result["resolver_output"]["text"], "[illeggibile]")
        self.assertEqual(result["accuracy_claim"], "none")

    def test_rejects_extra_fields_and_invalid_bbox(self) -> None:
        with self.assertRaises(ValueError):
            self._build(lambda request: {"text": "guess", "confidence": 0.99})
        with self.assertRaises(ValueError):
            build_visual_resolver_preview(
                page_id="page", source_image_hash="hash", variant_id="raw",
                source_bbox=[0, 0, 0, 10], crop_artifact="crop.png",
                candidate_ocr="text", resolver=lambda request: {"text": "x"},
            )

    def test_rejects_empty_or_non_mapping_resolver_output(self) -> None:
        with self.assertRaises(ValueError):
            self._build(lambda request: {"text": " "})
        with self.assertRaises(ValueError):
            self._build(lambda request: "text")


if __name__ == "__main__":
    unittest.main()
