from __future__ import annotations

import hashlib
import json
import sys
from unittest.mock import Mock
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

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


class OcrTransformPilotCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = [self.root / "one.tif", self.root / "two.tif"]
        for source in self.sources:
            Image.new("L", (8, 8), 255).save(source)
        self.output = self.root / "run"
        self.runner = Mock(return_value=[{"rec_texts": ["offline"], "rec_scores": [0.8]}])
        # Mock invents attributes on access; declare real provenance explicitly.
        self.runner.runtime_provenance = None
        self.options = dict(input_tiffs=self.sources, output_dir=self.output, language="deu",
                            model={"ocr_version": "PP-OCRv5", "text_detection_model_name": "PP-OCRv5_det",
                                   "text_recognition_model_name": "PP-OCRv5_rec"},
                            tile_width=16, tile_height=16, tile_overlap=2,
                            runtime_identity={"model_files": [{"sha256": "offline-model"}]})

    def run_pilot(self, **kwargs):
        return run_ocr_transform_pilot(**(self.options | {"prediction_runner": self.runner} | kwargs))

    def snapshot(self):
        return {str(path.relative_to(self.output)): path.read_bytes()
                for path in self.output.rglob("*") if path.is_file()}

    def test_completed_checkpoint_reused_without_runner_or_writes(self):
        result = self.run_pilot()
        self.assertFalse(result["reused"])
        self.assertEqual(self.runner.call_count, 10)
        before = self.snapshot()
        result = self.run_pilot(resume=True, prediction_runner=None)
        self.assertTrue(result["reused"])
        self.assertEqual(self.runner.call_count, 10)
        self.assertEqual(self.snapshot(), before)

    def test_mismatched_configuration_or_inputs_fails_without_writes(self):
        self.run_pilot()
        for changes in ({"language": "ita"}, {"tile_overlap": 1}, {"device": "gpu"}, {"retry_limit": 0},
                        {"enable_mkldnn": True}, {"text_det_limit_side_len": 4000},
                        {"runtime_identity": {"model_files": [{"sha256": "changed"}]}},
                        {"model": self.options["model"] | {"text_recognition_model_name": "PP-OCRv5_other"}}):
            before = self.snapshot()
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.run_pilot(resume=True, prediction_runner=None, **changes)
            self.assertEqual(self.snapshot(), before)
        self.sources[0].write_bytes(b"changed input")
        with self.assertRaises(ValueError):
            self.run_pilot(resume=True, prediction_runner=None)
        self.assertEqual(self.runner.call_count, 10)

    def test_modified_missing_and_extra_artifacts_fail_closed(self):
        self.run_pilot()
        review = self.output / "review.md"
        original = review.read_bytes()
        for mutation in (lambda: review.write_text("tampered"), lambda: review.unlink(),
                         lambda: (self.output / "extra.txt").write_text("unexpected")):
            review.write_bytes(original)
            mutation()
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.run_pilot(resume=True, prediction_runner=None)
            self.assertEqual(self.snapshot(), before)

    def test_manifest_corruption_and_incomplete_checkpoint_are_rejected(self):
        self.run_pilot()
        manifest_path = self.output / "pilot-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["pages"] = []
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.run_pilot(resume=True, prediction_runner=None)
        (self.output / "checkpoint.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_pilot(resume=True, prediction_runner=None)

    def test_changed_image_artifact_is_rejected(self):
        self.run_pilot()
        image = self.output / "pages/one/variants/raw.tif"
        image.write_bytes(b"altered derived image")
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.run_pilot(resume=True, prediction_runner=None)
        self.assertEqual(self.snapshot(), before)

    def test_source_changed_during_run_does_not_publish_checkpoint(self):
        def mutate_source(path, language):
            with self.sources[0].open("ab") as handle:
                handle.write(b"changed")
            return [{"rec_texts": ["offline"], "rec_scores": [0.8]}]
        with self.assertRaisesRegex(ValueError, "modificato durante"):
            self.run_pilot(prediction_runner=mutate_source)
        self.assertFalse((self.output / "checkpoint.json").exists())

    def test_runner_weights_identity_must_match_request(self):
        self.runner.runtime_provenance = {"models": {"text_detection": {"sha256": "other"}}}
        with self.assertRaisesRegex(ValueError, "Identita'"):
            self.run_pilot()
        self.assertFalse(self.output.exists())

    def test_existing_output_requires_explicit_resume_and_missing_run_is_not_created(self):
        with self.assertRaises(FileNotFoundError):
            self.run_pilot(resume=True, prediction_runner=None)
        self.assertFalse(self.output.exists())
        self.run_pilot()
        before = self.snapshot()
        with self.assertRaises(FileExistsError):
            self.run_pilot()
        self.assertEqual(self.snapshot(), before)

    def test_runtime_metrics_use_clock_and_include_lazy_prediction_consumption(self):
        # 1 tick start, 2 ticks per target, 1 tick end: ten OCR targets.
        ticks = iter(range(22))
        state = {"consumed": False}
        def generator_runner(path, language):
            state["consumed"] = False
            def results():
                state["consumed"] = True
                yield {"rec_texts": ["offline"], "rec_scores": [0.8]}
            return results()
        calls = 0
        def clock():
            nonlocal calls
            if calls > 0 and calls % 2 == 0:
                self.assertTrue(state["consumed"])
            calls += 1
            return next(ticks)
        metrics = self.run_pilot(clock=clock, prediction_runner=generator_runner)["manifest"]["metrics"]
        self.assertEqual(metrics["duration_seconds"], 21)
        self.assertEqual(metrics["page_count"], 2)
        self.assertEqual(metrics["ocr_target_count"], 10)
        self.assertEqual(metrics["p95_target_latency_ms"], 1000)
        self.assertAlmostEqual(metrics["throughput_pages_per_second"], 2 / 21)
        self.assertAlmostEqual(metrics["throughput_ocr_targets_per_second"], 10 / 21)
        self.assertIsNone(metrics["cost"])
        self.assertIsNone(metrics["human_review_seconds"])

    def test_nearest_rank_p95_with_twenty_six_targets(self):
        # A 3x3 raw tiling gives 9 tiles + 4 full-page targets per page: 26.
        ticks = [0.0]
        now = 0.0
        for latency in range(1, 27):
            ticks.extend([now, now + latency / 1000])
            now += latency / 1000
        ticks.append(now)
        clock = iter(ticks).__next__
        metrics = self.run_pilot(clock=clock, tile_width=4, tile_height=4)["manifest"]["metrics"]
        self.assertEqual(metrics["ocr_target_count"], 26)
        self.assertEqual(metrics["p95_target_latency_ms"], 25)

    def test_transient_runner_failure_retries_once_and_preserves_audit(self):
        valid = [{"rec_texts": ["offline"], "rec_scores": [0.8]}]
        self.runner.side_effect = [RuntimeError("transient")] + [valid] * 10
        manifest = self.run_pilot()["manifest"]
        self.assertEqual(self.runner.call_count, 11)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["metrics"]["ocr_target_count"], 10)
        self.assertEqual(manifest["metrics"]["ocr_attempt_count"], 11)
        self.assertEqual(manifest["metrics"]["failed_ocr_attempt_count"], 1)
        first = manifest["pages"][0]["variants"][0]["ocr_outputs"][0]
        self.assertEqual(first["attempt_count"], 2)
        self.assertEqual([item["attempt"] for item in manifest["ocr_attempts"][:2]], [1, 2])
        self.assertEqual(manifest["ocr_attempts"][0]["error"], {"type": "RuntimeError", "message": "transient"})
        self.assertIn("transient", (self.output / "review.md").read_text(encoding="utf-8"))
        self.assertTrue(self.run_pilot(resume=True, prediction_runner=None)["reused"])

    def test_lazy_materialization_failure_is_retried(self):
        calls = 0
        def runner(path, language):
            nonlocal calls
            calls += 1
            def prediction():
                if calls == 1:
                    raise RuntimeError("lazy failure")
                yield {"rec_texts": ["offline"], "rec_scores": [0.8]}
            return prediction()
        manifest = self.run_pilot(prediction_runner=runner)["manifest"]
        self.assertEqual(calls, 11)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["ocr_attempts"][0]["error"]["message"], "lazy failure")

    def test_permanent_page_failure_cleans_artifacts_continues_and_blocks_resume_and_consumers(self):
        from caduti_fonti_report.document_analysis.ocr_transform_structure import export_ocr_transform_structure
        from caduti_fonti_report.document_analysis.ocr_tesseract_from_t36 import export_tesseract_from_t36
        calls = []
        def runner(path, language):
            calls.append(path)
            # Fail after raw full-page and tile succeeded: partial artifacts and evidence must disappear.
            if "one" in path.parts and path.name == "grayscale.png":
                raise RuntimeError("permanent")
            return [{"rec_texts": ["offline"], "rec_scores": [0.8]}]
        result = self.run_pilot(prediction_runner=runner)
        manifest = result["manifest"]
        self.assertEqual([page["status"] for page in manifest["pages"]], ["failed", "completed"])
        self.assertEqual(manifest["status"], "partial")
        self.assertEqual(manifest["pages"][0]["variants"], [])
        self.assertFalse((self.output / "pages/one").exists())
        self.assertTrue((self.output / "pages/two/variants/threshold-160.png").is_file())
        self.assertEqual(manifest["pages"][0]["ocr_attempt_count"], 4)
        self.assertEqual(manifest["metrics"]["completed_page_count"], 1)
        self.assertEqual(manifest["metrics"]["failed_page_count"], 1)
        self.assertEqual(manifest["metrics"]["ocr_target_count"], 5)
        self.assertEqual(manifest["metrics"]["ocr_attempt_count"], 9)
        checkpoint = json.loads((self.output / "checkpoint.json").read_text())
        self.assertEqual(checkpoint["status"], "partial")
        self.assertFalse(any(item["path"].startswith("pages/one/") for item in checkpoint["artifacts"]))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.run_pilot(resume=True, prediction_runner=None)
        self.assertEqual(self.snapshot(), before)
        for consumer in (
            lambda: export_ocr_transform_structure(manifest_path=Path(result["manifest_path"]), variant_id="raw",
                page_profiles={"one": "leader_list_report", "two": "leader_list_report"}, output_dir=self.root / "t37"),
            lambda: export_tesseract_from_t36(manifest_path=Path(result["manifest_path"]),
                processed_text={"one": self.root / "one.json", "two": self.root / "two.json"}, output_dir=self.root / "bridge"),
        ):
            with self.assertRaisesRegex(ValueError, "raw.*mancante"):
                consumer()
        self.assertFalse((self.root / "t37").exists())
        self.assertFalse((self.root / "bridge").exists())

    def test_zero_retry_and_all_failed_pages_have_no_usable_artifacts(self):
        self.runner.side_effect = RuntimeError("unavailable")
        manifest = self.run_pilot(retry_limit=0)["manifest"]
        self.assertEqual(self.runner.call_count, 2)
        self.assertEqual(manifest["status"], "partial")
        self.assertEqual(manifest["metrics"]["ocr_target_count"], 0)
        self.assertEqual(manifest["metrics"]["ocr_attempt_count"], 2)
        self.assertIsNone(manifest["metrics"]["p95_target_latency_ms"])
        self.assertEqual(list((self.output / "pages").iterdir()), [])

    def test_deterministic_prediction_validation_is_not_retried(self):
        self.runner.return_value = [object()]
        manifest = self.run_pilot()["manifest"]
        self.assertEqual(self.runner.call_count, 2)
        self.assertEqual(manifest["status"], "partial")
        self.assertEqual([page["error"]["type"] for page in manifest["pages"]], ["ValueError", "ValueError"])

    def test_retry_limit_invalid_before_output_or_runtime(self):
        for value in (-1, 2, True, 1.0, "1"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "retry_limit"):
                self.run_pilot(retry_limit=value)
        self.assertFalse(self.output.exists())
        self.runner.assert_not_called()

    def test_casefold_colliding_page_ids_rejected_before_output_or_runtime(self):
        # Separate parent directories permit both fixtures on Windows too.
        first_parent, second_parent = self.root / "first", self.root / "second"
        first_parent.mkdir()
        second_parent.mkdir()
        sources = [first_parent / "Name.tif", second_parent / "name.tif"]
        for source in sources:
            Image.new("L", (8, 8), 255).save(source)
        with self.assertRaisesRegex(ValueError, "page_id.*distinti"):
            self.run_pilot(input_tiffs=sources)
        self.assertFalse(self.output.exists())
        self.runner.assert_not_called()

    def test_retry_limit_changes_fingerprint(self):
        first = self.run_pilot(retry_limit=0)["manifest"]
        second = self.run_pilot(retry_limit=1, output_dir=self.root / "other")["manifest"]
        self.assertNotEqual(first["request_fingerprint"], second["request_fingerprint"])
        self.assertEqual(first["checkpoint_request"]["retry_limit"], 0)
        self.assertEqual(second["checkpoint_request"]["retry_limit"], 1)


if __name__ == "__main__":
    unittest.main()
