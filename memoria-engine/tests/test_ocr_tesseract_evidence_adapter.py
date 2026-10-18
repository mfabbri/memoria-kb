from __future__ import annotations

from copy import deepcopy
import unittest

from caduti_fonti_report.document_analysis.ocr_evidence_comparison import compare_ocr_page_evidence
from caduti_fonti_report.document_analysis.ocr_tesseract import _layout_payload, _parse_tesseract_tsv, _run_provenance
from caduti_fonti_report.document_analysis.ocr_tesseract_evidence_adapter import adapt_tesseract_page_evidence


class TesseractEvidenceAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = {"page_id": "synthetic-page", "source_file": "synthetic.tif",
                       "source_image_hash": "a" * 64, "source_dimensions": {"width": 300, "height": 160}}
        self.primary = {
            "@type": "OcrPageEvidence", "page_id": "synthetic-page", "source_image_hash": "a" * 64,
            "engine": "PP-OCRv5", "model": {"name": "synthetic-pp-model"}, "language": "deu",
            "transform_id": "original", "image_transform": None, "source_page": {"original_page": self.anchor},
            "regions": [{"region_id": "pp-1", "text": "REPORT", "geometry": {"bbox": [10, 10, 100, 30]}}],
        }
        tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
               "1\t1\t0\t0\t0\t0\t0\t0\t300\t160\t-1\t\n"
               "5\t1\t1\t1\t1\t1\t10\t10\t90\t20\t88\tREPORT\n")
        quality = _layout_payload(records=_parse_tesseract_tsv(tsv), source_document_id="synthetic-document")
        probe = {"status": "probed", "frame_count": 1, "frames": [{"frame_index": 0, "width": 300, "height": 160}]}
        run = _run_provenance(
            source_document_id="synthetic-document", source_sha256_before="a" * 64, source_sha256_after="a" * 64,
            source_probe=probe, language="deu", tesseract_path="tesseract", requested_psm="6", engine_mode="", dpi="",
            selected={"input_probe": probe, "quality": quality, "preprocessing_report": None,
                      "input_kind": "original", "input_sha256": "a" * 64, "page_segmentation_mode": "6",
                      "attempts": [{"candidate_id": "original-psm-6", "input": "original", "page_segmentation_mode": "6",
                                    "status": "selected", "quality_score": 88, "word_count": 1, "line_count": 1,
                                    "input_sha256": "a" * 64}]},
        )
        self.payload = {"@type": "ProcessedDocumentText", "source_document_id": "synthetic-document",
                        "transcription_method": "external_ocr_unreviewed", "ocr_engine": "tesseract",
                        "ocr_quality_gate_status": "accepted",
                        "ocr_language": "deu", "ocr_effective_page_segmentation_mode": "6",
                        "ocr_run_provenance": run, **quality}

    def adapt(self, **kwargs) -> dict:
        return adapt_tesseract_page_evidence(processed_text=self.payload, primary_evidence=self.primary,
                                              original_page=self.anchor, **kwargs)

    def test_producer_shape_adapts_and_compares_without_mutation(self) -> None:
        before = deepcopy((self.payload, self.primary, self.anchor))
        evidence = self.adapt()
        result = compare_ocr_page_evidence(left=self.primary, right=evidence)
        self.assertEqual(len(result["agreements"]), 1)
        self.assertFalse(result["machine_pass_allowed"])
        line = self.payload["ocr_layout_lines"][0]
        self.assertEqual(evidence["regions"][0]["region_id"], line["region_id"])
        self.assertEqual(evidence["regions"][0]["source_tsv_line"], line)
        self.assertEqual(evidence["regions"][0]["confidence"], 88)
        self.assertEqual(evidence["ocr_run_provenance"], self.payload["ocr_run_provenance"])
        evidence["ocr_run_provenance"]["configuration"]["language"] = "changed"
        evidence["source_page"]["original_page"]["source_file"] = "changed"
        self.assertEqual((self.payload, self.primary, self.anchor), before)

    def test_equivalent_paddle_and_tesseract_language_codes_are_accepted(self) -> None:
        self.primary["language"] = "de"
        evidence = self.adapt()
        self.assertEqual(evidence["language"], "de")

    def test_byte_copy_primary_frame_is_supported_with_exact_identity(self) -> None:
        self.primary.update(transform_id="pilot-v1:raw", image_transform={
            "id": "pilot-v1:raw", "parameters": {"operation": "byte_copy", "source_mode": "L"}})
        self.primary["source_page"].update(variant_id="raw", target="full_page", tile_id=None)
        evidence = self.adapt()
        self.assertEqual(evidence["image_transform"], self.primary["image_transform"])
        self.assertEqual(len(compare_ocr_page_evidence(left=self.primary, right=evidence)["agreements"]), 1)

    def test_t36_engine_spelling_is_accepted_without_relabeling_primary(self) -> None:
        self.primary["engine"] = "paddle-ocr-v5"
        self.primary.update(transform_id="pilot-v1:raw", image_transform={
            "id": "pilot-v1:raw", "parameters": {"operation": "byte_copy"}})
        self.primary["source_page"].update(variant_id="raw", target="full_page", tile_id=None)
        original = deepcopy(self.primary)
        evidence = self.adapt()
        self.assertEqual(self.primary, original)
        comparison = compare_ocr_page_evidence(left=self.primary, right=evidence)
        self.assertEqual(comparison["left_evidence"]["engine"], "paddle-ocr-v5")
        self.assertEqual(len(comparison["agreements"]), 1)

    def test_registration_pairing_must_attest_same_run(self) -> None:
        registration = {"@type": "DocumentOcrRegistration", "source_document_id": "synthetic-document",
                        "transcription_method": "external_ocr_unreviewed", "ocr_run_provenance": deepcopy(self.payload["ocr_run_provenance"])}
        self.adapt(registration=registration)
        registration["ocr_run_provenance"]["configuration"]["dpi"] = "300"
        with self.assertRaisesRegex(ValueError, "Registration"):
            self.adapt(registration=registration)

    def test_missing_historical_or_falsely_ready_provenance_fails_closed(self) -> None:
        original = deepcopy(self.payload)
        mutations = [
            lambda p: p.pop("ocr_run_provenance"),
            lambda p: p["ocr_run_provenance"].update(adapter_ready=False),
            lambda p: p["ocr_run_provenance"].update(reasons=["tsv_dimensions_inconsistent"]),
            lambda p: p["ocr_run_provenance"]["source_image"].update(sha256_before="b" * 64),
            lambda p: p["ocr_run_provenance"]["source_image"].update(sha256_after="b" * 64),
            lambda p: p["ocr_run_provenance"]["selected_input"].update(sha256="b" * 64),
            lambda p: p["ocr_run_provenance"]["source_image"]["probe"].update(frame_count=2),
            lambda p: p["ocr_run_provenance"].update(tsv_pages=[{"page_number": 2, "width": 300, "height": 160}]),
            lambda p: p["ocr_run_provenance"].update(tsv_word_page_numbers=[1, 2]),
            lambda p: p["ocr_run_provenance"]["tsv_pages"][0].update(page_number=True),
            lambda p: p["ocr_run_provenance"]["source_image"]["probe"].update(frame_count=True),
            lambda p: p["ocr_run_provenance"]["attempts"][0].update(input_sha256="b" * 64),
            lambda p: p["ocr_run_provenance"]["configuration"].pop("executable"),
            lambda p: p.update(ocr_language="ita"),
            lambda p: p.update(ocr_quality_gate_status="rejected"),
            lambda p: p["ocr_run_provenance"]["attempts"][0].update(status="usable"),
            lambda p: p.update(ocr_line_count=2),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.payload = deepcopy(original)
                mutation(self.payload)
                with self.assertRaises(ValueError):
                    self.adapt()

    def test_photometric_transform_cannot_borrow_primary_identity(self) -> None:
        self.payload["ocr_run_provenance"]["selected_input"].update(
            kind="temporary_preprocessed", transform="photometric_only", preprocessing={"method": "dark_foreground_binary"})
        with self.assertRaisesRegex(ValueError, "photometric/input transform"):
            self.adapt()

    def test_primary_anchor_frame_and_engine_mismatch_fails_closed(self) -> None:
        original = deepcopy(self.primary)
        mutations = [
            lambda p: p.update(engine="tesseract"),
            lambda p: p.update(image_transform={"operation": "contrast"}),
            lambda p: p.update(transform_id="unknown"),
            lambda p: p["source_page"].update(crop={"left": 0, "top": 0, "right": 200, "bottom": 100}),
            lambda p: p["source_page"].update(target="tile", tile_id="tile-1"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.primary = deepcopy(original)
                mutation(self.primary)
                with self.assertRaises(ValueError):
                    self.adapt()
        self.primary = original
        with self.assertRaisesRegex(ValueError, "anchor"):
            adapt_tesseract_page_evidence(processed_text=self.payload, primary_evidence=self.primary,
                                          original_page={**self.anchor, "source_file": "other.tif"})

    def test_malformed_geometry_mapping_ids_and_confidence_fail_closed(self) -> None:
        original = deepcopy(self.payload)
        for updates in ({"left": -1}, {"width": 0}, {"top": 150}, {"height": float("nan")},
                        {"width": True}, {"confidence": 101}, {"confidence": None},
                        {"text": None}, {"region_id": ""}, {"page_number": 2},
                        {"source_document_id": "other"}):
            with self.subTest(updates=updates):
                self.payload = deepcopy(original)
                self.payload["ocr_layout_lines"][0].update(updates)
                with self.assertRaises(ValueError):
                    self.adapt()
        self.payload = original
        self.payload["ocr_layout_lines"].append(deepcopy(self.payload["ocr_layout_lines"][0]))
        self.payload["ocr_line_count"] = 2
        with self.assertRaisesRegex(ValueError, "unique"):
            self.adapt()


if __name__ == "__main__":
    unittest.main()
