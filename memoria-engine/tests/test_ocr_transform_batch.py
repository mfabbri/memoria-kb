from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.ocr_transform_batch import run_ocr_transform_batch


class OcrTransformBatchTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.items = []
        for i in range(3):
            source = self.root / f"scan{i}.tif"
            Image.new("L", (8, 8), 255).save(source)
            self.items.append({"page_id": f"page{i}", "path": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
        self.manifest = self.root / "input.json"
        self.write_input()
        self.output = self.root / "batch"
        self.calls = []

    def write_input(self):
        self.manifest.write_text(json.dumps({"schema_version": "1.0", "pages": self.items}))

    def runner(self, path, language):
        self.calls.append(path)
        return [{"rec_texts": ["synthetic"], "rec_scores": [0.8]}]

    def run_batch(self, **kwargs):
        options = dict(manifest_path=self.manifest, output_dir=self.output, language="deu",
                       model={"ocr_version": "PP-OCRv5", "text_detection_model_name": "PP-OCRv5_server_det",
                              "text_recognition_model_name": "latin_PP-OCRv5_mobile_rec"},
                       prediction_runner=self.runner, retry_limit=0)
        options.update(kwargs)
        return run_ocr_transform_batch(**options)

    def test_three_pages_preserve_provenance_and_resume_without_runner(self):
        result = self.run_batch()
        manifest = result["manifest"]
        self.assertEqual(manifest["@type"], "OcrTransformPilot")
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(len(self.calls), 15)
        self.assertEqual([p["page_id"] for p in manifest["pages"]], ["page0", "page1", "page2"])
        self.assertEqual(manifest["pages"][0]["variants"][0]["ocr_outputs"][0]["structured_evidence"]["source_page"]["original_page"]["page_id"], "page0")
        factory = Mock(side_effect=AssertionError("runtime must not initialize"))
        preview = self.run_batch(resume=True, apply=False, prediction_runner=None, runner_factory=factory)
        self.assertEqual(preview["reused_page_count"], 3)
        result = self.run_batch(resume=True, prediction_runner=None, runner_factory=factory)
        self.assertTrue(result["reused"])
        self.assertEqual(result["manifest"]["metrics"]["current_run_ocr_attempt_count"], 0)
        self.assertEqual(result["manifest"]["metrics"]["throughput_ocr_targets_per_second"], 0)
        factory.assert_not_called()

    def test_failed_page_isolated_and_resume_only_retries_it_with_audit(self):
        def failure(path, language):
            if "page1" in path.parts:
                raise RuntimeError("offline failure")
            return self.runner(path, language)
        result = self.run_batch(prediction_runner=failure)
        self.assertEqual(result["manifest"]["status"], "partial")
        self.assertEqual(result["manifest"]["pages"][1]["variants"], [])
        self.assertFalse((self.output / "pages" / "page1").exists())
        self.assertEqual(len(self.calls), 10)
        factory = Mock(return_value=self.runner)
        result = self.run_batch(resume=True, prediction_runner=None, runner_factory=factory)
        self.assertEqual(result["manifest"]["status"], "completed")
        self.assertEqual(result["manifest"]["metrics"]["reused_page_count"], 2)
        self.assertEqual(len(self.calls), 15)
        factory.assert_called_once()
        checkpoint = json.loads((self.output / "checkpoints" / "page1.json").read_text())
        self.assertEqual(checkpoint["prior_runs"][0]["status"], "failed")
        self.assertEqual(checkpoint["prior_runs"][0]["ocr_attempts"][0]["error"]["message"], "offline failure")

    def test_corrupt_artifact_fails_before_runtime_or_writes(self):
        self.run_batch()
        (self.output / "pages" / "page2" / "variants" / "raw.tif").write_bytes(b"tampered")
        self.assert_resume_rejected()

    def assert_resume_rejected(self, **kwargs):
        before = {p: p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        factory = Mock()
        with self.assertRaises((ValueError, OSError)):
            self.run_batch(resume=True, prediction_runner=None, runner_factory=factory, **kwargs)
        factory.assert_not_called()
        self.assertEqual(before, {p: p.read_bytes() for p in self.output.rglob("*") if p.is_file()})

    def test_changed_request_and_checkpoint_fail_closed(self):
        self.run_batch()
        self.assert_resume_rejected(language="ita")
        self.assert_resume_rejected(runtime_identity={"weights": "changed"})
        path = self.output / "checkpoints" / "page0.json"
        checkpoint = json.loads(path.read_text())
        checkpoint["page"]["variants"][0]["ocr_outputs"][0]["raw_prediction"] = "changed"
        path.write_text(json.dumps(checkpoint))
        self.assert_resume_rejected()

    def test_missing_checkpoint_reruns_only_interrupted_page(self):
        self.run_batch()
        (self.output / "checkpoints" / "page1.json").unlink()
        (self.output / "checkpoints" / "page1.json.tmp").write_text("interrupted checkpoint serialization")
        self.calls.clear()
        result = self.run_batch(resume=True)
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(result["manifest"]["metrics"]["reused_page_count"], 2)
        self.assertFalse((self.output / "checkpoints" / "page1.json.tmp").exists())

    def test_invalid_manifest_ids_hash_and_output_fail_before_runtime(self):
        original = list(self.items)
        invalid_items = [[], [original[0], original[0] | {"page_id": "PAGE0"}],
                         [original[0] | {"page_id": "../escape"}], [original[0] | {"page_id": "CON.tif"}],
                         [original[0] | {"page_id": "trailing."}], [original[0] | {"sha256": "0" * 64}],
                         [original[0], original[0] | {"page_id": "other"}]]
        factory = Mock()
        for items in invalid_items:
            with self.subTest(items=items):
                self.items = items
                self.write_input()
                with self.assertRaises(ValueError):
                    self.run_batch(prediction_runner=None, runner_factory=factory)
                self.assertFalse(self.output.exists())
        self.items = original
        self.write_input()
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.run_batch(prediction_runner=None, runner_factory=factory)
        factory.assert_not_called()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_preview_validates_without_writing_or_runtime(self):
        factory = Mock()
        result = self.run_batch(apply=False, prediction_runner=None, runner_factory=factory)
        self.assertEqual(result["pending_page_count"], 3)
        self.assertFalse(result["writes_performed"])
        self.assertFalse(self.output.exists())
        factory.assert_not_called()

    def test_single_page_and_bounded_retry(self):
        self.items = self.items[:1]
        self.write_input()
        calls = []
        def transient(path, language):
            calls.append(path)
            if len(calls) == 1:
                raise RuntimeError("transient")
            return self.runner(path, language)
        result = self.run_batch(prediction_runner=transient, retry_limit=1)
        self.assertEqual(result["manifest"]["status"], "completed")
        self.assertEqual(len(calls), 6)
        self.assertEqual(result["manifest"]["pages"][0]["ocr_attempt_count"], 6)

    def test_repository_output_rejected(self):
        with self.assertRaisesRegex(ValueError, "esterna al repository"):
            self.run_batch(output_dir=Path(__file__).resolve().parents[1] / ".batch-output")


if __name__ == "__main__":
    unittest.main()
