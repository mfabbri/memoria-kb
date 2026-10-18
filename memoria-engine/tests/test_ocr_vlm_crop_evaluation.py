from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from caduti_fonti_report.document_analysis import ocr_vlm_crop_evaluation as evaluation
from caduti_fonti_report.memoria_cli import main


class OcrVlmCropEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image_path = self.root / "page.png"
        image = Image.new("RGB", (24, 18), "white")
        image.save(self.image_path)
        self.reference_path = self.root / "reference.json"
        self.reference_path.write_text(json.dumps({
            "@type": "OcrPageReference",
            "reference_id": "reference-1",
            "origin": "human_verified",
            "review_status": "verified",
            "page": {"page_id": "page-1", "source_image_hash": self._sha(self.image_path)},
            "text": "Area Abzug bleibt sichtbar.",
        }), encoding="utf-8")
        self.case = {
            "case_id": "case-1",
            "source_document_id": "document-1",
            "page_id": "page-1",
            "source_image": "page.png",
            "source_image_sha256": self._sha(self.image_path),
            "frame_index": 0,
            "source_bbox": [2, 3, 20, 15],
            "variant_id": "raw",
            "candidate_ocr": "Abzng",
            "reference_text": "Abzug",
            "reference_status": "verified",
            "reference_id": "reference-1",
            "reference_file": "reference.json",
            "reference_sha256": self._sha(self.reference_path),
            "scale_factor": 2,
        }
        self.manifest_path = self.root / "cohort.json"
        self._write_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps({
            "@type": "OcrVlmCropEvaluationCohort",
            "schema_version": "1.0",
            "cohort_id": "synthetic-cohort",
            "cohort_role": "development",
            "cases": [self.case],
        }), encoding="utf-8")

    def _transport(self, calls: list[tuple[str, str, dict | None, float]]):
        def request(method, url, payload, timeout):
            calls.append((method, url, payload, timeout))
            if url.endswith("/api/version"):
                return {"version": "0.34.2"}
            if url.endswith("/api/tags"):
                return {"models": [{"name": "vision:test", "digest": "d" * 64, "capabilities": ["vision"]}]}
            return {"response": json.dumps({"text": "abzug"})}
        return request

    def test_evaluates_only_verified_cohort_and_reports_provenance(self) -> None:
        calls: list[tuple[str, str, dict | None, float]] = []
        report = evaluation.evaluate_ocr_vlm_crop_cohort(
            manifest_path=self.manifest_path,
            model="vision:test",
            transport=self._transport(calls),
        )

        self.assertEqual(report["evaluation_scope"], "declared_verified_cohort_only")
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])
        self.assertEqual(report["metrics"]["normalized_match_count"], 1)
        self.assertIsNone(report["cases"][0]["confidence"])
        self.assertEqual(report["cases"][0]["confidence_status"], "not_exposed_by_output_contract")
        self.assertEqual(report["cases"][0]["crop"]["crop_dimensions"], [36, 24])
        generation = calls[-1][2]
        self.assertIn("Abzng", generation["prompt"])
        self.assertNotIn("Abzug", generation["prompt"])
        decoded_crop = base64.b64decode(generation["images"][0])
        self.assertEqual(hashlib.sha256(decoded_crop).hexdigest(), report["cases"][0]["crop"]["sha256"])
        self.assertEqual(generation["options"]["temperature"], 0.0)

    def test_unverified_reference_fails_before_any_transport(self) -> None:
        self.case["reference_status"] = "candidate"
        self._write_manifest()
        calls: list[tuple[str, str, dict | None, float]] = []
        with self.assertRaisesRegex(ValueError, "reference_status verified"):
            evaluation.evaluate_ocr_vlm_crop_cohort(
                manifest_path=self.manifest_path, model="vision:test", transport=self._transport(calls)
            )
        self.assertEqual(calls, [])

    def test_holdout_cohort_is_rejected_before_any_transport(self) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["cohort_role"] = "holdout"
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        calls: list[tuple[str, str, dict | None, float]] = []
        with self.assertRaisesRegex(ValueError, "solo coorti development"):
            evaluation.evaluate_ocr_vlm_crop_cohort(
                manifest_path=self.manifest_path, model="vision:test", transport=self._transport(calls)
            )
        self.assertEqual(calls, [])

    def test_image_or_reference_hash_mismatch_fails_before_any_transport(self) -> None:
        self.case["source_image_sha256"] = "0" * 64
        self._write_manifest()
        calls: list[tuple[str, str, dict | None, float]] = []
        with self.assertRaisesRegex(ValueError, "SHA-256 immagine sorgente"):
            evaluation.evaluate_ocr_vlm_crop_cohort(
                manifest_path=self.manifest_path, model="vision:test", transport=self._transport(calls)
            )
        self.assertEqual(calls, [])

    def test_rejects_reference_that_does_not_contain_the_target_text(self) -> None:
        self.case["reference_text"] = "Retreat"
        self._write_manifest()
        calls: list[tuple[str, str, dict | None, float]] = []
        with self.assertRaisesRegex(ValueError, "Reference umana non verificata"):
            evaluation.evaluate_ocr_vlm_crop_cohort(
                manifest_path=self.manifest_path, model="vision:test", transport=self._transport(calls)
            )
        self.assertEqual(calls, [])

    def test_windows_transport_runs_curl_inside_wsl(self) -> None:
        process = type("Completed", (), {"returncode": 0, "stdout": b'{"version":"0.34.2"}', "stderr": b""})()
        with patch.object(evaluation.sys, "platform", "win32"), patch.object(
            evaluation.subprocess, "run", return_value=process
        ) as run:
            result = evaluation._default_wsl_ollama_transport("GET", "http://127.0.0.1:11434/api/version", None, 10)
        self.assertEqual(result["version"], "0.34.2")
        self.assertEqual(run.call_args.args[0][:3], ["wsl.exe", "-e", "curl"])

    def test_wsl_access_denied_is_not_reported_as_missing_runtime(self) -> None:
        def denied(*_args):
            raise RuntimeError("Wsl/Service/CreateInstance/E_ACCESSDENIED")
        with self.assertRaisesRegex(ValueError, "runtime_access_blocked"):
            evaluation._request_json(denied, "http://127.0.0.1:11434/api/version", None, 10, "versione")

    def test_model_output_parser_fails_closed(self) -> None:
        self.assertEqual(evaluation._parse_model_text(""), (None, "empty"))
        self.assertEqual(evaluation._parse_model_text('not json'), (None, "invalid"))
        self.assertEqual(evaluation._parse_model_text('{"text":"[illeggibile]"}'), ("[illeggibile]", "illegible"))

    def test_cli_preview_runs_explicit_evaluation_but_does_not_write_report(self) -> None:
        output_path = self.root / "report.json"
        report = {"@type": "OcrVlmCropEvaluationReport", "auto_validation_enabled": False}
        stdout = StringIO()
        with patch("caduti_fonti_report.memoria_cli.evaluate_ocr_vlm_crop_cohort", return_value=report) as run:
            with redirect_stdout(stdout):
                code = main(["documents", "vlm-crop-evaluate", "--manifest", str(self.manifest_path),
                             "--model", "vision:test", "--output", str(output_path)])
        self.assertEqual(code, 0)
        self.assertFalse(output_path.exists())
        self.assertEqual(json.loads(stdout.getvalue())["operation_status"], "preview")
        run.assert_called_once()

    def test_cli_apply_writes_report_exclusively(self) -> None:
        output_path = self.root / "report.json"
        report = {"@type": "OcrVlmCropEvaluationReport", "auto_validation_enabled": False}
        with patch("caduti_fonti_report.memoria_cli.evaluate_ocr_vlm_crop_cohort", return_value=report):
            with redirect_stdout(StringIO()):
                code = main(["documents", "vlm-crop-evaluate", "--manifest", str(self.manifest_path),
                             "--model", "vision:test", "--output", str(output_path), "--apply"])
        self.assertEqual(code, 0)
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["operation_status"], "written")
        self.assertFalse(saved["auto_validation_enabled"])

    def test_cli_existing_apply_output_fails_before_live_evaluation(self) -> None:
        output_path = self.root / "report.json"
        output_path.write_text("keep", encoding="utf-8")
        stderr = StringIO()
        with patch("caduti_fonti_report.memoria_cli.evaluate_ocr_vlm_crop_cohort") as run:
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                code = main(["documents", "vlm-crop-evaluate", "--manifest", str(self.manifest_path),
                             "--model", "vision:test", "--output", str(output_path), "--apply"])
        self.assertEqual(code, 1)
        self.assertEqual(output_path.read_text(encoding="utf-8"), "keep")
        run.assert_not_called()

    def test_cli_help_labels_live_side_effect_and_wsl_route(self) -> None:
        stdout = StringIO()
        with self.assertRaises(SystemExit) as exit_context:
            with redirect_stdout(stdout):
                main(["documents", "vlm-crop-evaluate", "--help"])
        self.assertEqual(exit_context.exception.code, 0)
        help_text = " ".join(stdout.getvalue().split())
        self.assertIn("l'inferenza live avviene anche in preview", help_text)
        self.assertIn("su Windows le richieste passano da WSL/curl", help_text)


if __name__ == "__main__":
    unittest.main()
