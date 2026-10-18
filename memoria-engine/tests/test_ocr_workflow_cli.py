from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.memoria_cli import main as memoria_main  # noqa: E402


class OcrWorkflowCliTests(unittest.TestCase):
    def test_v11_dispatcher_runs_and_resumes_both_engines_offline(self) -> None:
        from test_ocr_workflow import OcrWorkflowV11Tests
        fixture = OcrWorkflowV11Tests()
        self.assert_dispatcher_runs_and_resumes(fixture, "completed_unreviewed")

    def test_v12_dispatcher_prepares_unreviewed_package_and_resumes_offline(self) -> None:
        from test_ocr_workflow import OcrWorkflowV12Tests
        fixture = OcrWorkflowV12Tests()
        self.assert_dispatcher_runs_and_resumes(fixture, "awaiting_review")
        package = json.loads((fixture.output / "review/package-manifest.json").read_text())
        self.assertEqual(package["status"], "template_incomplete")
        self.assertEqual(package["review_status"], "unreviewed")

    def assert_dispatcher_runs_and_resumes(self, fixture, expected_status) -> None:
        from caduti_fonti_report.document_analysis import ocr_workflow as workflow
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        real_batch = workflow.tesseract_batch.run_tesseract_page_batch

        def batch_with_fake_command(**kwargs):
            kwargs["command_runner"] = fixture.tesseract
            return real_batch(**kwargs)

        arguments = ["documents", "process", "--workflow-manifest", str(fixture.manifest),
                     "--output-dir", str(fixture.output)]
        with patch.object(workflow.pilot, "create_local_paddle_ocr_v5_runner", return_value=fixture.runner) as factory, \
                patch.object(workflow.tesseract_batch, "run_tesseract_page_batch", side_effect=batch_with_fake_command):
            output = io.StringIO()
            with redirect_stdout(output):
                result = memoria_main(arguments)
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "preview")
            self.assertFalse(fixture.output.exists())
            factory.assert_not_called()
            self.assertFalse(fixture.tesseract_calls)
            output = io.StringIO()
            with redirect_stdout(output):
                result = memoria_main(arguments + ["--apply"])
            self.assertEqual(result, 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["status"], expected_status)
            self.assertEqual(report["tesseract"]["summary"]["success"], 2)
            self.assertTrue(fixture.calls)
            self.assertTrue(fixture.tesseract_calls)
            before, call_counts = fixture.snapshot(), (len(fixture.calls), len(fixture.tesseract_calls))
            factory.reset_mock()
            output = io.StringIO()
            with redirect_stdout(output):
                result = memoria_main(arguments + ["--apply", "--resume"])
            self.assertEqual(result, 0)
            self.assertTrue(json.loads(output.getvalue())["tesseract"]["reused"])
            self.assertEqual(before, fixture.snapshot())
            self.assertEqual(call_counts, (len(fixture.calls), len(fixture.tesseract_calls)))
            factory.assert_not_called()

    def test_v12_bad_lexicon_digest_rejects_before_runtime_and_write(self) -> None:
        from test_ocr_workflow import OcrWorkflowV12Tests
        fixture = OcrWorkflowV12Tests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.payload["review"]["lexicons"]["p0"]["sha256"] = "0" * 64
        fixture.write_manifest()
        with redirect_stderr(io.StringIO()), patch(
            "caduti_fonti_report.document_analysis.ocr_workflow.pilot.create_local_paddle_ocr_v5_runner"
        ) as factory:
            result = memoria_main(["documents", "process", "--workflow-manifest", str(fixture.manifest),
                                   "--output-dir", str(fixture.output), "--apply"])
        self.assertEqual(result, 1)
        self.assertFalse(fixture.output.exists())
        factory.assert_not_called()

    def test_workflow_preview_dispatches_and_serializes_report(self) -> None:
        report = {"status": "preview", "writes_performed": False, "inference_performed": False}
        output = io.StringIO()
        with redirect_stdout(output), patch(
            "caduti_fonti_report.document_analysis.ocr_workflow.run_ocr_workflow", return_value=report
        ) as run_workflow:
            result = memoria_main([
                "documents", "process", "--workflow-manifest", "workflow.json",
                "--output-dir", "run",
            ])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), report)
        run_workflow.assert_called_once_with(
            manifest_path=Path("workflow.json"), output_dir=Path("run"), apply=False, resume=False
        )

    def test_apply_resume_and_partial_exit_code(self) -> None:
        report = {"status": "partial_unreviewed", "blocked_stage": "t37"}
        output = io.StringIO()
        with redirect_stdout(output), patch(
            "caduti_fonti_report.document_analysis.ocr_workflow.run_ocr_workflow", return_value=report
        ) as run_workflow:
            result = memoria_main([
                "documents", "process", "--workflow-manifest", "workflow.json",
                "--output-dir", "run", "--apply", "--resume",
            ])

        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue()), report)
        run_workflow.assert_called_once_with(
            manifest_path=Path("workflow.json"), output_dir=Path("run"), apply=True, resume=True
        )

    def test_resume_without_workflow_manifest_is_rejected(self) -> None:
        error = io.StringIO()
        with redirect_stderr(error):
            result = memoria_main([
                "documents", "process", "--root", "images", "--output-dir", "run", "--resume"
            ])

        self.assertEqual(result, 1)
        self.assertIn("--resume richiede --workflow-manifest", error.getvalue())


if __name__ == "__main__":
    unittest.main()
