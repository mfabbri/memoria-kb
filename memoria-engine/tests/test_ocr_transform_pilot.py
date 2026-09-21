from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from caduti_fonti_report.document_analysis.ocr_transform_pilot import create_local_paddle_ocr_v5_runner, run_ocr_transform_pilot
from caduti_fonti_report.document_analysis.document_structure import reconstruct_document_structure
from caduti_fonti_report.document_analysis.ocr_reference_metrics import evaluate_page_reference


MODEL = {
    "ocr_version": "PP-OCRv5",
    "text_detection_model_name": "PP-OCRv5_server_det",
    "text_recognition_model_name": "latin_PP-OCRv5_mobile_rec",
}


class _PaddleResult:
    def __init__(self, payload: dict[str, object]) -> None:
        self.json = payload


class _ArrayLike:
    def __init__(self, value: list[int]) -> None:
        self._value = value

    def tolist(self) -> list[int]:
        return self._value


class _ForbiddenImage:
    def tolist(self) -> list[int]:
        raise AssertionError("L'immagine intermedia Paddle non deve essere serializzata.")


class OcrTransformPilotTests(unittest.TestCase):
    def test_creates_named_variants_tiles_provenance_and_source_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first, second = root / "first.tif", root / "second.tif"
            Image.new("RGB", (5, 4), "white").save(first)
            Image.new("RGB", (5, 4), "black").save(second)
            first_hash = self._sha256(first)

            result = run_ocr_transform_pilot(
                input_tiffs=[first, second], output_dir=root / "new-output", language="deu", model=MODEL,
                prediction_runner=self._runner, tile_width=3, tile_height=3, tile_overlap=1,
            )

            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["review_status"], "unreviewed")
            self.assertEqual(manifest["accuracy_claim"], "none_without_human_reference")
            self.assertEqual(manifest["tiling"]["coordinate_convention"], "left_top_inclusive_right_bottom_exclusive")
            self.assertEqual(manifest["tiling"]["variant_id"], "raw")
            self.assertEqual(manifest["runtime"]["enable_mkldnn"], False)
            self.assertEqual(manifest["runtime"]["text_det_limit_side_len"], 8192)
            self.assertEqual(manifest["runtime"]["text_det_limit_type"], "max")
            self.assertIn("max_side_limit=4000", manifest["runtime"]["full_page_caveat"])
            self.assertEqual(manifest["runtime"]["paddle_excluded_prediction_fields"], ["doc_preprocessor_res.output_img", "vis_fonts"])
            self.assertEqual(self._sha256(first), first_hash)
            page = manifest["pages"][0]
            self.assertEqual(page["source"]["sha256"], first_hash)
            self.assertEqual([variant["variant_id"] for variant in page["variants"]], ["raw", "grayscale", "contrast", "threshold"])
            raw = page["variants"][0]
            grayscale = page["variants"][1]
            self.assertEqual(raw["sha256"], first_hash)
            self.assertEqual(len(raw["tiles"]), 4)
            for variant in page["variants"][1:]:
                self.assertEqual(variant["tiles"], [])
                self.assertEqual([output["target"] for output in variant["ocr_outputs"]], ["full_page"])
            tile_output = next(output for output in raw["ocr_outputs"] if output["tile_id"] == "tile-r000-c001")
            full_output = raw["ocr_outputs"][0]
            self.assertEqual(full_output["structured_evidence"]["page_id"], "first")
            self.assertEqual(tile_output["structured_evidence"]["page_id"], "first")
            anchor = tile_output["structured_evidence"]["source_page"]["original_page"]
            self.assertEqual(anchor["page_id"], "first")
            self.assertEqual(anchor["source_image_hash"], first_hash)
            self.assertEqual(anchor["source_dimensions"], {"width": 5, "height": 4})
            region = tile_output["structured_evidence"]["regions"][0]
            self.assertEqual(tile_output["source_bbox"], [2, 0, 5, 3])
            self.assertEqual(region["geometry"]["source_page_polygon"], [[3, 2], [5, 2], [5, 4], [3, 4]])
            self.assertEqual(region["geometry"]["source_page_bbox"], [3, 2, 5, 4])
            self.assertEqual(tile_output["raw_prediction"][0]["res"]["rec_texts"], ["Vecohis"])
            self.assertEqual(tile_output["raw_prediction"][0]["res"]["rec_boxes"], [[1, 2, 3, 4]])
            raw_fields = tile_output["raw_prediction"][0]["res"]
            self.assertEqual(raw_fields["input_path"], "fixture-input.tif")
            self.assertEqual(raw_fields["page_index"], 0)
            self.assertEqual(raw_fields["text_det_params"], {"max_side_limit": 4000})
            self.assertNotIn("doc_preprocessor_res", raw_fields)
            self.assertNotIn("vis_fonts", raw_fields)
            report = Path(result["report_path"]).read_text(encoding="utf-8")
            self.assertIn("[Crop o immagine OCR](pages/first/tiles/raw/tile-r000-c001.png)", report)
            self.assertIn("tile e OCR dei tile sono eseguiti soltanto su `raw`", report)

            reference = {
                "@type": "OcrPageReference", "reference_id": "synthetic-first", "origin": "human_verified",
                "review_status": "verified", "page": {"page_id": "first", "source_image_hash": first_hash,
                "original_page": anchor}, "text": "Vecohis", "blocks": [{"kind": "unknown", "text": "Vecohis"}],
                "audit": {"reviewer": "test", "decision_reference": "test-decision", "verified_at": "2026-09-21T00:00:00Z"},
            }
            grayscale_output = grayscale["ocr_outputs"][0]
            for output in (full_output, grayscale_output, tile_output):
                evidence = output["structured_evidence"]
                structure = reconstruct_document_structure(evidence=evidence, profile="leader_list_report")
                self.assertTrue(evaluate_page_reference(reference=reference, evidence=evidence, structure=structure)["accuracy_eligible"])
            other_evidence = manifest["pages"][1]["variants"][0]["ocr_outputs"][0]["structured_evidence"]
            other_structure = reconstruct_document_structure(evidence=other_evidence, profile="leader_list_report")
            self.assertFalse(evaluate_page_reference(reference=reference, evidence=other_evidence, structure=other_structure)["accuracy_eligible"])

    def test_refuses_existing_output_or_other_than_two_tiffs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first, second = root / "first.tif", root / "second.tif"
            Image.new("L", (1, 1), 255).save(first)
            Image.new("L", (1, 1), 255).save(second)
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(FileExistsError, "directory output.*nuova"):
                run_ocr_transform_pilot(
                    input_tiffs=[first, second], output_dir=existing, language="ita", model=MODEL, prediction_runner=self._runner,
                )
            with self.assertRaisesRegex(ValueError, "esattamente due TIFF"):
                run_ocr_transform_pilot(
                    input_tiffs=[first], output_dir=root / "new", language="ita", model=MODEL, prediction_runner=self._runner,
                )

    def test_local_runner_passes_native_resolution_runtime_kwargs_to_paddle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            detection, recognition = root / "det", root / "rec"
            for directory in (detection, recognition):
                directory.mkdir()
                for name in ("inference.json", "inference.pdiparams", "inference.yml"):
                    (directory / name).write_text("fixture", encoding="utf-8")
            captured: dict[str, object] = {}

            class PaddleStub:
                def __init__(self, **kwargs: object) -> None:
                    captured.update(kwargs)

                def predict(self, _: str) -> list[_PaddleResult]:
                    return OcrTransformPilotTests._runner(Path("unused"), "deu")

            runner = create_local_paddle_ocr_v5_runner(
                language="deu", text_detection_model_dir=detection, text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_dir=recognition, text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
                paddle_ocr_factory=PaddleStub, paddle_version="3.3.0-test", paddleocr_version="3.7.0-test",
            )
            self.assertIsInstance(runner(root / "image.tif", "deu"), list)
            self.assertFalse(captured["enable_mkldnn"])
            self.assertEqual(captured["text_det_limit_side_len"], 8192)
            self.assertEqual(captured["text_det_limit_type"], "max")
            provenance = runner.runtime_provenance  # type: ignore[attr-defined]
            self.assertEqual(provenance["paddle_version"], "3.3.0-test")
            self.assertEqual(provenance["paddleocr_version"], "3.7.0-test")
            self.assertEqual(
                {entry["path"] for entry in provenance["models"]["text_detection"]["files"]},
                {"inference.json", "inference.pdiparams", "inference.yml"},
            )

    @staticmethod
    def _runner(_: Path, __: str) -> list[_PaddleResult]:
        return [_PaddleResult({"res": {
            "input_path": "fixture-input.tif", "page_index": 0, "dt_polys": [[[1, 2], [3, 2], [3, 4], [1, 4]]],
            "rec_texts": ["Vecohis"], "rec_scores": [0.91], "rec_polys": [[[1, 2], [3, 2], [3, 4], [1, 4]]],
            "rec_boxes": [_ArrayLike([1, 2, 3, 4])], "textline_orientation_angles": [0],
            "text_det_params": {"max_side_limit": 4000}, "model_settings": {"det": "fixture"}, "text_type": "general",
            "text_rec_score_thresh": 0.0, "return_word_box": False,
            "doc_preprocessor_res": {"output_img": _ForbiddenImage()}, "vis_fonts": _ForbiddenImage(),
        }})]

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
