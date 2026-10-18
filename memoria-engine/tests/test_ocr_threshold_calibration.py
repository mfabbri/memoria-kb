from __future__ import annotations

from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.ocr_threshold_calibration import calibrate_ocr_threshold
from caduti_fonti_report.document_analysis.ocr_threshold_audit import _validate_dataset
from caduti_fonti_report.memoria_cli import main


class OcrThresholdCalibrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "calibration.json"
        self.output = self.path.with_name("artifact.json")
        self.dataset = {
            "@type": "OcrAutoValidationCalibration", "schema_version": "1.0",
            "partition": "calibration", "holdout_not_opened": True,
            "calibration_id": "synthetic-calibration", "score_name": "synthetic-risk",
            "direction": "lower_is_safer", "frozen_at": "2026-01-02T00:00:00Z",
            "required_strata": ["deu-prose"], "cases": [self.case(i) for i in range(59)],
        }

    @staticmethod
    def case(i):
        return {"page_id": f"page-{i}", "source_document_id": f"doc-{i}",
                "source_image_sha256": f"{i:064x}", "stratum": "deu-prose",
                "partition": "calibration", "review_status": "human_verified", "accuracy_eligible": True,
                "score": 0.1, "material_word_error_count": 1, "reference_word_count": 300,
                "material_error_categories": ["text"], "reference_id": f"ref-{i}",
                "reference_evaluation_sha256": "a" * 64, "score_source_sha256": "b" * 64}

    def run_calibration(self):
        self.path.write_text(json.dumps(self.dataset), encoding="utf-8")
        return calibrate_ocr_threshold(dataset_path=self.path)

    def test_selects_largest_safe_tied_cutoff_and_binds_exact_bytes(self):
        bad = self.case(100)
        bad.update(score=0.9, material_word_error_count=30)
        self.dataset["cases"].append(bad)
        report = self.run_calibration()
        self.assertEqual(report["threshold"]["cutoff"], 0.1)
        self.assertEqual(report["threshold"]["calibration_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(report, calibrate_ocr_threshold(dataset_path=self.path))
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])
        payload = dict(report)
        digest = payload.pop("artifact_payload_sha256")
        self.assertEqual(digest, hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest())
        holdout = {"@type": "OcrAutoValidationHoldout", "schema_version": "1.2",
                   "policy": {"max_page_material_word_error_rate": 0.01, "target_false_accept_page_rate": 0.05, "confidence_level": 0.95},
                   "threshold": report["threshold"], "cohort_id": "synthetic", "cohort_manifest_sha256": "c" * 64,
                   "required_strata": ["deu-prose"], "cases": [dict(self.case(999), partition="holdout")]}
        _validate_dataset(holdout)

    def test_rejects_partition_labels_duplicates_and_malformed_scores(self):
        original = copy.deepcopy(self.dataset)
        changes = [("partition", "holdout"), ("partition", "unknown"), ("review_status", "unreviewed"),
                   ("accuracy_eligible", False), ("score", float("nan")), ("score", float("inf")),
                   ("score", True), ("score", 10 ** 400), ("score", "0.1"), ("material_word_error_count", None),
                   ("reference_word_count", 0), ("material_error_categories", []),
                   ("source_document_id", "doc-1"), ("page_id", "page-1"),
                   ("source_image_sha256", f"{1:064x}"), ("stratum", "unknown"),
                   ("reference_evaluation_sha256", "bad"), ("score_source_sha256", None)]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                self.dataset = copy.deepcopy(original)
                self.dataset["cases"][0][field] = value
                with self.assertRaises(ValueError):
                    self.run_calibration()

    def test_rejects_insufficient_strata_and_unopened_holdout_declaration(self):
        for mutation in (lambda d: d["cases"].pop(), lambda d: d["required_strata"].append("missing"),
                         lambda d: d.update(partition="holdout"), lambda d: d.update(holdout_not_opened=False)):
            with self.subTest(mutation=mutation):
                original = copy.deepcopy(self.dataset)
                mutation(self.dataset)
                with self.assertRaises(ValueError):
                    self.run_calibration()
                self.dataset = original

    def test_cli_preview_apply_idempotency_and_no_overwrite(self):
        self.run_calibration()
        args = ["documents", "ocr-threshold-calibration", "--dataset", str(self.path), "--output", str(self.output)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
            self.assertFalse(self.output.exists())
            self.assertEqual(main(args + ["--apply"]), 0)
            frozen = self.output.read_bytes()
            self.assertEqual(main(args + ["--apply"]), 0)
            self.assertEqual(self.output.read_bytes(), frozen)
            self.dataset["score_name"] = "changed"
            self.run_calibration()
            self.assertEqual(main(args + ["--apply"]), 1)
            self.assertEqual(self.output.read_bytes(), frozen)


if __name__ == "__main__":
    unittest.main()
