from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.memoria_cli import main  # noqa: E402


class OcrTransformPilotCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = [self.root / "00026.tif", self.root / "00028.tiff"]
        for path in self.inputs:
            path.write_bytes(b"synthetic TIFF placeholder")
        self.det_dir = self.root / "det"
        self.rec_dir = self.root / "rec"
        self.det_dir.mkdir()
        self.rec_dir.mkdir()
        for directory in (self.det_dir, self.rec_dir):
            for name in ("inference.json", "inference.pdiparams", "inference.yml"):
                (directory / name).write_text("offline fake model", encoding="utf-8")
        self.output = self.root / "new-run"

    def _args(self, *, apply: bool = False) -> list[str]:
        args = ["documents", "ocr-transform-pilot"]
        for path in self.inputs:
            args.extend(["--input", str(path)])
        args.extend([
            "--output-dir", str(self.output), "--language", "deu",
            "--text-detection-model-dir", str(self.det_dir),
            "--text-detection-model-name", "PP-OCRv5_server_det",
            "--text-recognition-model-dir", str(self.rec_dir),
            "--text-recognition-model-name", "latin_PP-OCRv5_mobile_rec",
        ])
        if apply:
            args.append("--apply")
        return args

    def test_preview_checks_inputs_without_loading_runtime_or_writing(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner") as make_runner, \
             patch("caduti_fonti_report.memoria_cli.run_ocr_transform_pilot") as run_pilot, \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(self._args())
        report = json.loads(stdout.getvalue())
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        self.assertEqual(report["status"], "preview")
        self.assertFalse(report["inference_performed"])
        self.assertFalse(report["writes_performed"])
        self.assertEqual(report["retry_limit"], 1)
        self.assertFalse(self.output.exists())
        make_runner.assert_not_called()
        run_pilot.assert_not_called()

    def test_apply_calls_local_runner_and_reports_unreviewed_package(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner", return_value="runner") as make_runner, \
             patch("caduti_fonti_report.memoria_cli.run_ocr_transform_pilot", return_value={
                 "manifest_path": str(self.output / "pilot-manifest.json"),
                 "report_path": str(self.output / "review.md"),
             }) as run_pilot, redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(self._args(apply=True))
        report = json.loads(stdout.getvalue())
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        make_runner.assert_called_once()
        run_pilot.assert_called_once()
        self.assertEqual(report["status"], "completed_unreviewed")
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])
        self.assertEqual(report["semantic_accuracy_status"], "not_attested")
        self.assertIn("non esegue ancora T37", report["next_step"])
        self.assertEqual(run_pilot.call_args.kwargs["retry_limit"], 1)

    def test_preview_zero_retry_and_invalid_retry_do_not_load_runtime(self) -> None:
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner") as make_runner, \
             patch("caduti_fonti_report.memoria_cli.run_ocr_transform_pilot") as run_pilot:
            with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()):
                self.assertEqual(main(self._args() + ["--retry-limit", "0"]), 0)
            self.assertEqual(json.loads(stdout.getvalue())["retry_limit"], 0)
            for invalid in ("-1", "2"):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    main(self._args(apply=True) + ["--retry-limit", invalid])
                self.assertEqual(raised.exception.code, 2)
            make_runner.assert_not_called()
            run_pilot.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_partial_real_run_reports_failure_and_resume_rejected_without_runtime(self) -> None:
        from PIL import Image
        for path in self.inputs:
            Image.new("L", (8, 8), 255).save(path)
        calls = []
        def fake_runner(path, language):
            calls.append(path)
            if self.inputs[0].stem in path.parts:
                raise RuntimeError("offline permanent")
            return [{"rec_texts": ["offline"], "rec_scores": [0.8]}]
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner", return_value=fake_runner) as make_runner:
            with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(self._args(apply=True) + ["--retry-limit", "0"]), 1, stderr.getvalue())
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["status"], "partial_unreviewed")
            self.assertEqual(report["metrics"]["completed_page_count"], 1)
            self.assertEqual(report["metrics"]["ocr_attempt_count"], 6)
            self.assertEqual(len(calls), 6)
            for apply in (False, True):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as stderr:
                    self.assertEqual(main(self._args(apply=apply) + ["--retry-limit", "0", "--resume"]), 1)
                self.assertIn("Checkpoint T36 non valido", stderr.getvalue())
            make_runner.assert_called_once()
            self.assertEqual(len(calls), 6)

    def test_resume_does_not_construct_runtime_and_preview_does_not_write(self) -> None:
        self.output.mkdir()
        before = list(self.output.iterdir())
        for apply in (False, True):
            with self.subTest(apply=apply), \
                 patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner") as make_runner, \
                 patch("caduti_fonti_report.memoria_cli.run_ocr_transform_pilot", return_value={
                     "manifest_path": str(self.output / "pilot-manifest.json"),
                     "report_path": str(self.output / "review.md"), "reused": True,
                 }) as run_pilot, redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()):
                self.assertEqual(main(self._args(apply=apply) + ["--resume"]), 0)
                report = json.loads(stdout.getvalue())
                self.assertTrue(report["checkpoint_reused"] if apply else report["checkpoint_validated"])
                make_runner.assert_not_called()
                run_pilot.assert_called_once()
                self.assertIsNone(run_pilot.call_args.kwargs["prediction_runner"])
                self.assertTrue(run_pilot.call_args.kwargs["resume"])
                self.assertEqual(list(self.output.iterdir()), before)

    def test_resume_missing_checkpoint_fails_without_runtime(self) -> None:
        self.output.mkdir()
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner") as make_runner, \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(self._args(apply=True) + ["--resume"]), 1)
        make_runner.assert_not_called()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_apply_then_resume_with_real_checkpoint_and_changed_weights(self) -> None:
        from PIL import Image
        for path in self.inputs:
            Image.new("L", (8, 8), 255).save(path)
        calls = []
        def fake_runner(path, language):
            calls.append(path)
            return [{"rec_texts": ["offline"], "rec_scores": [0.8]}]
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner", return_value=fake_runner) as make_runner:
            for resume, apply in ((False, True), (True, False), (True, True)):
                with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                    self.assertEqual(main(self._args(apply=apply) + (["--resume"] if resume else [])), 0, stderr.getvalue())
                report = json.loads(stdout.getvalue())
                if apply:
                    self.assertEqual(report["checkpoint_reused"], resume)
                    self.assertEqual(report["metrics"]["ocr_target_count"], 10)
            self.assertEqual(len(calls), 10)
            make_runner.assert_called_once()
            (self.det_dir / "inference.pdiparams").write_text("changed weights")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(main(self._args(apply=True) + ["--resume"]), 1)
            self.assertIn("Checkpoint T36 non valido", stderr.getvalue())
            make_runner.assert_called_once()
            self.assertEqual(len(calls), 10)

    def test_refuses_invalid_page_count_and_repository_output_before_inference(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        args = ["documents", "ocr-transform-pilot", "--input", str(self.inputs[0]),
                "--output-dir", str(self.output), "--language", "deu",
                "--text-detection-model-dir", str(self.det_dir),
                "--text-detection-model-name", "PP-OCRv5_server_det",
                "--text-recognition-model-dir", str(self.rec_dir),
                "--text-recognition-model-name", "latin_PP-OCRv5_mobile_rec"]
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner") as make_runner, \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(args)
        self.assertEqual(code, 1)
        self.assertIn("esattamente due TIFF", stderr.getvalue())
        make_runner.assert_not_called()

        repo_output = Path(__file__).resolve().parents[2] / ".tmp-ocr-transform-cli"
        args = self._args()
        args[args.index("--output-dir") + 1] = str(repo_output)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("caduti_fonti_report.memoria_cli.create_local_paddle_ocr_v5_runner") as make_runner, \
             redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(args)
        self.assertEqual(code, 1)
        self.assertIn("esterna al repository", stderr.getvalue())
        make_runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
