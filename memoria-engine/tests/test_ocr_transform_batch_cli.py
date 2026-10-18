from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.memoria_cli import main


class OcrTransformBatchCliTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        pages = []
        for index in range(3):
            source = self.root / f"scan{index}.tif"
            Image.new("L", (8, 8), 255).save(source)
            pages.append({"page_id": f"p{index}", "path": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
        self.manifest = self.root / "input.json"
        self.manifest.write_text(json.dumps({"schema_version": "1.0", "pages": pages}))
        self.output = self.root / "output"
        self.det, self.rec = self.root / "det", self.root / "rec"
        for path in (self.det, self.rec):
            path.mkdir()
            for name in ("inference.json", "inference.pdiparams", "inference.yml"):
                (path / name).write_bytes(b"synthetic model")

    def args(self):
        return ["documents", "ocr-transform-batch", "--manifest", str(self.manifest),
                "--output-dir", str(self.output), "--language", "deu",
                "--text-detection-model-dir", str(self.det), "--text-detection-model-name", "PP-OCRv5_server_det",
                "--text-recognition-model-dir", str(self.rec), "--text-recognition-model-name", "latin_PP-OCRv5_mobile_rec",
                "--retry-limit", "0"]

    def invoke(self, extra=()):
        with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
            code = main(self.args() + list(extra))
        return code, json.loads(stdout.getvalue()) if stdout.getvalue() else None, stderr.getvalue()

    def test_preview_never_initializes_runtime_or_writes(self):
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner") as factory:
            code, report, error = self.invoke()
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(report["status"], "preview")
        self.assertEqual(report["pending_page_count"], 3)
        self.assertFalse(self.output.exists())
        factory.assert_not_called()

    def test_partial_then_resume_reuses_completed_pages_and_full_resume_skips_runtime(self):
        calls = []
        def runner(path, language):
            calls.append(path)
            return [{"rec_texts": ["offline"], "rec_scores": [0.8]}]
        def failing(path, language):
            if "p1" in path.parts:
                raise RuntimeError("offline failure")
            return runner(path, language)
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner", side_effect=[failing, runner]) as factory:
            code, report, error = self.invoke(["--apply"])
            self.assertEqual((code, error), (1, ""))
            self.assertEqual(report["status"], "partial_unreviewed")
            code, preview, error = self.invoke(["--resume"])
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(preview["reused_page_count"], 2)
            self.assertEqual(factory.call_count, 1)
            code, report, error = self.invoke(["--apply", "--resume"])
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(report["status"], "completed_unreviewed")
            self.assertEqual(report["metrics"]["current_run_ocr_attempt_count"], 5)
            self.assertFalse(report["machine_pass"])
            self.assertFalse(report["auto_validation_enabled"])
            code, report, error = self.invoke(["--apply", "--resume"])
            self.assertEqual((code, error), (0, ""))
            self.assertTrue(report["checkpoint_reused"])
            self.assertEqual(factory.call_count, 2)
            self.assertEqual(len(calls), 15)

    def test_changed_weights_fail_resume_before_runtime(self):
        def runner(path, language):
            return [{"rec_texts": ["offline"], "rec_scores": [0.8]}]
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner", return_value=runner) as factory:
            self.assertEqual(self.invoke(["--apply"])[0], 0)
            (self.det / "inference.pdiparams").write_bytes(b"changed weights")
            code, report, error = self.invoke(["--apply", "--resume"])
            self.assertEqual(code, 1)
            self.assertIn("non coincide", error)
            factory.assert_called_once()

    def test_bad_input_and_repository_output_rejected_before_runtime(self):
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner") as factory:
            payload = json.loads(self.manifest.read_text())
            payload["pages"][1]["page_id"] = "P0"
            self.manifest.write_text(json.dumps(payload))
            self.assertEqual(self.invoke(["--apply"])[0], 1)
            self.assertFalse(self.output.exists())
            payload["pages"][1]["page_id"] = "p1"
            self.manifest.write_text(json.dumps(payload))
            self.output = Path(__file__).resolve().parents[1] / ".batch-test-output"
            code, report, error = self.invoke(["--apply"])
            self.assertEqual(code, 1)
            self.assertIn("esterna al repository", error)
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
