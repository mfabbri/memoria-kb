from __future__ import annotations

import hashlib
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.ocr_provisional_threshold import (
    calibrate_provisional_ocr_threshold,
    evaluate_provisional_ocr_threshold,
)
from caduti_fonti_report.document_analysis.ocr_risk_score import SCORE_SPEC
from caduti_fonti_report.memoria_cli import main


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ProvisionalThresholdTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sample_path = self.root / "sample.json"
        self.dataset_path = self.root / "dataset.json"
        self.artifact_path = self.root / "threshold.json"
        self.score_path = self.root / "score.json"
        self.decision_path = self.root / "decision.json"
        self.sample = {
            "@type": "OcrProvisionalThresholdSample", "schema_version": "1.0",
            "policy": "operational_pilot", "frozen_before_review": True,
            "frozen_at": "2026-10-01T10:00:00+00:00",
            "page_ids": [f"p{i}" for i in range(10)],
        }
        self.sample_path.write_text(json.dumps(self.sample), encoding="utf-8")
        cases = []
        for i in range(10):
            document_id = "doc0" if i == 1 else f"doc{i}"
            identity = {
                "source_document_id": document_id, "page_id": f"p{i}",
                "source_image_hash": _sha(f"image{i}"), "engine": "paddle-ocr-v5",
                "language": "ita", "profile": "numbered_report",
                "model": {"name": "PP-OCRv5"}, "source_page": {"frame_index": 0},
                "image_transform": {"id": "original"},
            }
            cases.append({
                "page_id": f"p{i}", "partition": "operational_pilot",
                "review_status": "human_verified", "accuracy_eligible": True,
                "confirmed_at": "2026-10-02T10:00:00+00:00", "source_document_id": document_id,
                "reference_id": f"reference{i}", "source_image_sha256": identity["source_image_hash"],
                "candidate_structure_sha256": _sha(f"structure{i}"),
                "candidate_markdown_sha256": _sha(f"markdown{i}"),
                "reference_evaluation_sha256": _sha(f"evaluation{i}"),
                "score_source_sha256": _sha(f"bundle{i}"),
                "candidate_identity": identity, "profile": "numbered_report", "score": i / 10,
                "material_word_error_count": 1 if i >= 8 else 0,
                "reference_word_count": 40,
                "material_error_categories": ["text"] if i >= 8 else [],
            })
        self.dataset = {
            "@type": "OcrProvisionalThresholdDataset", "schema_version": "1.0",
            "pilot_id": "test-pilot", "reviewed_at": "2026-10-02T12:00:00+00:00",
            "sample_manifest_sha256": hashlib.sha256(self.sample_path.read_bytes()).hexdigest(),
            "score_name": "ocr-coverage-disagreement-max-v1", "score_spec": SCORE_SPEC,
            "cases": cases,
        }
        self._write_json(self.dataset_path, self.dataset)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _write_json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_empirical_cutoff_respects_two_percent_and_preserves_nonvalidation_flags(self):
        report = calibrate_provisional_ocr_threshold(
            dataset_path=self.dataset_path, sample_manifest_path=self.sample_path)
        self.assertEqual(report["threshold"]["cutoff"], 0.7)
        self.assertEqual(report["observed"]["page_limit_breach_count"], 2)
        self.assertTrue(report["provisional_auto_acceptance_enabled"])
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])
        self.assertFalse(report["human_verified"])
        self.assertFalse(report["claim_extraction_allowed"])

    def test_rejects_bad_case_that_ties_accepted_cutoff(self):
        self.dataset["cases"][0]["score"] = 0.8
        self.dataset["cases"][8]["score"] = 0.8
        self._write_json(self.dataset_path, self.dataset)
        report = calibrate_provisional_ocr_threshold(
            dataset_path=self.dataset_path, sample_manifest_path=self.sample_path)
        self.assertEqual(report["threshold"]["cutoff"], 0.7)
        self.assertEqual(report["observed"]["accepted_page_limit_breach_count"], 0)

    def test_rejects_changed_sample_bytes_and_duplicate_pages(self):
        self.sample_path.write_text(json.dumps(self.sample, indent=2), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256 esatto"):
            calibrate_provisional_ocr_threshold(
                dataset_path=self.dataset_path, sample_manifest_path=self.sample_path)
        self.sample["page_ids"][1] = self.sample["page_ids"][0]
        self._write_json(self.sample_path, self.sample)
        self.dataset["sample_manifest_sha256"] = hashlib.sha256(self.sample_path.read_bytes()).hexdigest()
        self._write_json(self.dataset_path, self.dataset)
        with self.assertRaisesRegex(ValueError, "page_id unici"):
            calibrate_provisional_ocr_threshold(
                dataset_path=self.dataset_path, sample_manifest_path=self.sample_path)

    def test_consumer_is_scoped_and_never_marks_human_verified(self):
        threshold = calibrate_provisional_ocr_threshold(
            dataset_path=self.dataset_path, sample_manifest_path=self.sample_path)
        self._write_json(self.artifact_path, threshold)
        score = {
            "@type": "OcrRiskScore", "schema_version": "1.0", "score_status": "diagnostic_only",
            "direction": "lower_is_safer", "risk_score": 0.5,
            "candidate_identity": self.dataset["cases"][0]["candidate_identity"],
            "inputs": {"bundle": {"sha256": _sha("bundle")}},
        }
        self._write_json(self.score_path, score)
        decision = evaluate_provisional_ocr_threshold(
            threshold_path=self.artifact_path, score_path=self.score_path,
            output_path=self.decision_path)
        self.assertEqual(decision["operational_disposition"], "provisional_auto_accept")
        self.assertTrue(decision["provisional_auto_acceptance"])
        self.assertFalse(decision["human_verified"])
        self.assertFalse(decision["auto_validation_enabled"])
        score["candidate_identity"]["profile"] = "leader_list_report"
        self._write_json(self.score_path, score)
        decision = evaluate_provisional_ocr_threshold(
            threshold_path=self.artifact_path, score_path=self.score_path,
            output_path=self.root / "out-of-scope.json")
        self.assertEqual(decision["operational_disposition"], "manual_review_required")

    def test_cli_evaluates_and_writes_scoped_provisional_disposition(self):
        self._write_json(self.artifact_path, calibrate_provisional_ocr_threshold(
            dataset_path=self.dataset_path, sample_manifest_path=self.sample_path))
        self._write_json(self.score_path, {
            "@type": "OcrRiskScore", "schema_version": "1.0", "score_status": "diagnostic_only",
            "direction": "lower_is_safer", "risk_score": 0.4,
            "candidate_identity": self.dataset["cases"][0]["candidate_identity"],
            "inputs": {"bundle": {"sha256": _sha("bundle")}},
        })
        args = ["documents", "ocr-threshold-provisional-evaluate", "--threshold", str(self.artifact_path),
                "--score", str(self.score_path), "--output", str(self.decision_path)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
            self.assertFalse(self.decision_path.exists())
            self.assertEqual(main(args + ["--apply"]), 0)
        decision = json.loads(self.decision_path.read_text(encoding="utf-8"))
        self.assertEqual(decision["operational_disposition"], "provisional_auto_accept")
        self.assertFalse(decision["human_verified"])

    def test_cli_preview_and_apply(self):
        args = ["documents", "ocr-threshold-provisional-calibrate", "--dataset", str(self.dataset_path),
                "--sample-manifest", str(self.sample_path), "--output", str(self.artifact_path)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
            self.assertFalse(self.artifact_path.exists())
            self.assertEqual(main(args + ["--apply"]), 0)
        self.assertTrue(self.artifact_path.exists())


if __name__ == "__main__":
    unittest.main()
