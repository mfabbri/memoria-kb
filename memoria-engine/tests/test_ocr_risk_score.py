from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from caduti_fonti_report.document_analysis.ocr_risk_score import SCORE_SPEC, build_ocr_risk_score
from caduti_fonti_report.memoria_cli import main


class OcrRiskScoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "bundle.json"
        self.output = self.root / "score.json"
        self.bundle = {
            "@type": "OcrRiskFeatureBundle", "schema_version": "1.1", "feature_version": "1.1",
            "processability_status": "diagnostic_only",
            "candidate_identity": {
                "source_document_id": "synthetic-document", "page_id": "synthetic-page",
                "source_image_hash": "a" * 64, "transform_id": "raw", "engine": "synthetic",
                "language": "deu", "model": {"name": "synthetic"}, "image_transform": {"name": "raw"},
                "source_page": {"original_page": {"page_id": "synthetic-page"}},
            },
            "features": {
                "assessment_issue_count": 0,
                "disagreement_pair_count": 1, "one_to_one_pair_count": 10,
                "normalized_agreement_pair_count": 9, "exact_agreement_pair_count": 8,
                "left_region_count": 12, "right_region_count": 10,
                "unmatched_left_region_count": 2, "unmatched_right_region_count": 0,
                "evidence_region_count": 12, "represented_region_count": 9,
                "evidence_region_coverage_ratio": .75, "disagreement_pair_ratio": .1,
            },
        }

    def build(self, **kwargs):
        self.source.write_text(json.dumps(self.bundle), encoding="utf-8")
        return build_ocr_risk_score(bundle_path=self.source, output_path=self.output, **kwargs)

    def test_formula_provenance_and_no_preview_writes(self):
        report = self.build()
        self.assertEqual(report, self.build())
        self.assertEqual(report["components"], {"D": .1, "C": .25})
        self.assertEqual(report["feature_version"], "1.1")
        self.assertEqual(report["risk_score"], .25)
        self.assertEqual(report["inputs"]["bundle"], {
            "path": str(self.source), "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()})
        canonical = json.dumps(SCORE_SPEC, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(report["score_spec_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        self.assertEqual(report["candidate_identity"], self.bundle["candidate_identity"])
        self.assertFalse(self.output.exists())
        self.assertIsNone(report["cutoff"])
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])

    def test_monotonic_disagreement(self):
        previous = self.build()["risk_score"]
        for count in range(2, 11):
            self.bundle["features"].update(disagreement_pair_count=count,
                normalized_agreement_pair_count=10-count, exact_agreement_pair_count=0,
                disagreement_pair_ratio=count / 10)
            score = self.build()["risk_score"]
            self.assertGreaterEqual(score, previous)
            previous = score

    def test_hash_binds_exact_bytes_even_when_json_content_is_unchanged(self):
        original = self.build()
        self.source.write_bytes(self.source.read_bytes() + b"\n")
        changed = build_ocr_risk_score(bundle_path=self.source, output_path=self.output)
        self.assertEqual(changed["risk_score"], original["risk_score"])
        self.assertNotEqual(changed["inputs"]["bundle"]["sha256"], original["inputs"]["bundle"]["sha256"])
        self.assertNotEqual(changed["@id"], original["@id"])

    def test_unmatched_regions_do_not_change_two_component_formula(self):
        for unmatched in (3, 10, 30):
            self.bundle["features"].update(left_region_count=10+unmatched, right_region_count=10+unmatched,
                unmatched_left_region_count=unmatched, unmatched_right_region_count=unmatched,
                evidence_region_count=10+unmatched, represented_region_count=10+unmatched,
                evidence_region_coverage_ratio=1)
            score = self.build()["risk_score"]
            self.assertEqual(score, .1)

    def test_monotonic_coverage_loss(self):
        previous = 0
        for represented in range(12, -1, -1):
            self.bundle["features"].update(represented_region_count=represented,
                evidence_region_coverage_ratio=represented / 12)
            score = self.build()["risk_score"]
            self.assertGreaterEqual(score, previous)
            previous = score

    def test_missing_or_null_features_are_not_scorable(self):
        original = deepcopy(self.bundle)
        for key in original["features"]:
            for remove in (True, False):
                self.bundle = deepcopy(original)
                if remove:
                    del self.bundle["features"][key]
                else:
                    self.bundle["features"][key] = None
                report = self.build()
                self.assertEqual(report["score_status"], "not_scorable", key)
                self.assertIsNone(report["risk_score"])
                self.assertIsNone(report["components"])
                self.assertIn("missing_feature:" + key, report["not_scorable_reasons"])
        self.bundle["features"] = None
        self.assertEqual(self.build()["score_status"], "not_scorable")

    def test_zero_denominators_are_not_zero_risk(self):
        self.bundle["features"] = {key: None if "ratio" in key else 0 for key in self.bundle["features"]}
        report = self.build()
        self.assertEqual(report["score_status"], "not_scorable")
        self.assertIsNone(report["risk_score"])
        self.assertIn("zero_denominator:total_region_count", report["not_scorable_reasons"])

    def test_no_one_to_one_pairs(self):
        self.bundle["features"].update(disagreement_pair_count=0, one_to_one_pair_count=0,
            normalized_agreement_pair_count=0, exact_agreement_pair_count=0,
            disagreement_pair_ratio=None, unmatched_left_region_count=12, unmatched_right_region_count=10)
        self.assertEqual(self.build()["score_status"], "not_scorable")

    def test_blocked_missing_and_unknown_source_status(self):
        self.bundle["processability_status"] = "blocked"
        report = self.build()
        self.assertEqual(report["score_status"], "not_scorable")
        self.assertIsNone(report["risk_score"])
        self.assertIn("source_processability_blocked", report["not_scorable_reasons"])
        self.bundle.pop("processability_status")
        self.assertEqual(self.build()["score_status"], "not_scorable")
        for value in (True, "unknown", {}, "processable"):
            self.bundle["processability_status"] = value
            with self.assertRaises(ValueError):
                self.build()

    def test_source_safety_fields_cannot_claim_acceptance_or_score(self):
        for key, value in (("machine_pass", True), ("auto_validation_enabled", 0), ("risk_score", 0), ("cutoff", .1)):
            with self.subTest(key=key):
                self.bundle[key] = value
                with self.assertRaises(ValueError):
                    self.build(apply=True)
                del self.bundle[key]
        self.assertFalse(self.output.exists())

    def test_actual_feature_producer_bundle_is_compatible(self):
        # Reuse the existing offline fixture builder, without reading any real run.
        from test_ocr_risk_features import OcrRiskFeaturesTest

        fixture = OcrRiskFeaturesTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.bundle = fixture.build()
        report = self.build()
        self.assertEqual(report["score_status"], "diagnostic_only")
        self.assertEqual(report["risk_score"], 1)

    def test_invalid_values_fail_closed(self):
        original = deepcopy(self.bundle)
        for key, values in {
            "assessment_issue_count": [True, -1, 0.0, "0"],
            "disagreement_pair_count": [True, -1, 1.0, "1", [], float("nan")],
            "evidence_region_coverage_ratio": [False, -0.1, 1.1, "0.75", float("nan"), float("inf")],
            "disagreement_pair_ratio": [False, -0.1, 1.1, "0.1", float("nan"), float("inf")],
        }.items():
            for value in values:
                self.bundle = deepcopy(original)
                self.bundle["features"][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.build(apply=True)
                self.assertFalse(self.output.exists())

    def test_inconsistent_counts_and_ratios_fail_closed(self):
        original = deepcopy(self.bundle)
        for changes in ({"disagreement_pair_count": 11}, {"normalized_agreement_pair_count": 8},
                        {"exact_agreement_pair_count": 10}, {"represented_region_count": 13},
                        {"unmatched_left_region_count": 3}, {"unmatched_right_region_count": 1},
                        {"disagreement_pair_ratio": .2}, {"evidence_region_coverage_ratio": .5},
                        {"evidence_region_count": 11, "represented_region_count": 11, "evidence_region_coverage_ratio": 1}):
            self.bundle = deepcopy(original)
            self.bundle["features"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(apply=True)
            self.assertFalse(self.output.exists())

    def test_identity_type_and_version_required(self):
        original = deepcopy(self.bundle)
        for key in original["candidate_identity"]:
            self.bundle = deepcopy(original)
            del self.bundle["candidate_identity"][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.build()
        for key, value in (("@type", "Other"), ("schema_version", "1.0"), ("feature_version", "2.0"), ("features", [])):
            self.bundle = deepcopy(original)
            self.bundle[key] = value
            with self.assertRaises(ValueError):
                self.build()

    def test_unused_signals_do_not_influence_score(self):
        baseline = self.build()["risk_score"]
        self.bundle["features"].update(confidence_by_evidence={"mean": .999}, lexical_alert_count=900,
                                      pending_lexical_group_count=200)
        self.bundle.update(labels={"material_errors": 0}, reference="unused", holdout=True)
        self.assertEqual(self.build()["risk_score"], baseline)

    def test_assessment_issues_fail_closed_even_if_source_status_is_diagnostic(self):
        self.bundle["features"]["assessment_issue_count"] = 1
        report = self.build(apply=True)
        self.assertEqual(report["score_status"], "not_scorable")
        self.assertIsNone(report["risk_score"])
        self.assertIn("assessment_issues_present", report["not_scorable_reasons"])
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])

    def test_shared_omissions_remain_explicit_limitation_at_zero_score(self):
        self.bundle["features"].update(disagreement_pair_count=0, normalized_agreement_pair_count=10,
            disagreement_pair_ratio=0, left_region_count=10, unmatched_left_region_count=0,
            evidence_region_count=10, represented_region_count=10, evidence_region_coverage_ratio=1)
        report = self.build()
        self.assertEqual(report["risk_score"], 0)
        self.assertFalse(report["shared_omission_detection_performed"])
        self.assertIn("Shared omissions", report["score_spec"]["limitations"][0])
        self.assertFalse(report["machine_pass"])

    def test_apply_is_exclusive_idempotent_and_never_overwrites(self):
        self.assertEqual(self.build(apply=True)["operation_status"], "written")
        original = self.output.read_bytes()
        self.assertEqual(self.build(apply=True)["operation_status"], "skipped_existing")
        self.bundle["features"].update(represented_region_count=6, evidence_region_coverage_ratio=.5)
        with self.assertRaises(ValueError):
            self.build(apply=True)
        self.assertEqual(self.output.read_bytes(), original)
        with self.assertRaises(ValueError):
            build_ocr_risk_score(bundle_path=self.source, output_path=self.source, apply=True)

    def test_cli_preview_apply_and_errors(self):
        self.build()
        args = ["documents", "ocr-risk-score", "--bundle", str(self.source), "--output", str(self.output)]
        with redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(stream.getvalue())["operation_status"], "preview")
        self.assertFalse(self.output.exists())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args + ["--apply"]), 0)
        self.bundle["features"]["one_to_one_pair_count"] = True
        self.source.write_text(json.dumps(self.bundle), encoding="utf-8")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 1)

    def test_cli_nonzero_issue_count_emits_no_score_and_failure_status(self):
        self.bundle["features"]["assessment_issue_count"] = 2
        self.source.write_text(json.dumps(self.bundle), encoding="utf-8")
        args = ["documents", "ocr-risk-score", "--bundle", str(self.source), "--output", str(self.output)]
        with redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(main(args), 1)
        report = json.loads(stream.getvalue())
        self.assertIsNone(report["risk_score"])
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
