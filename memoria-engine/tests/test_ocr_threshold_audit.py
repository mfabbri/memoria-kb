from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.document_analysis.ocr_threshold_audit import (  # noqa: E402
    audit_ocr_auto_validation_threshold,
)
from caduti_fonti_report.memoria_cli import main  # noqa: E402


class OcrThresholdAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dataset_path = self.root / "holdout.json"
        self.cohort_manifest_path = self.root / "holdout-cohort.json"
        self.output_path = self.root / "audit.json"

    @staticmethod
    def dataset(
        *,
        per_stratum: dict[str, int] | None = None,
        word_errors: dict[int, int] | None = None,
        cutoff: float = 0.5,
        reference_words: int = 300,
    ) -> dict:
        per_stratum = per_stratum or {"deu-prose": 59}
        word_errors = word_errors or {}
        cases = []
        index = 0
        for stratum, count in per_stratum.items():
            for _ in range(count):
                error_count = word_errors.get(index, 0)
                cases.append({
                    "page_id": f"synthetic-{index:04d}",
                    "source_document_id": f"synthetic-document-{index:04d}",
                    "source_image_sha256": f"{index:064x}",
                    "stratum": stratum,
                    "partition": "holdout",
                    "review_status": "human_verified",
                    "accuracy_eligible": True,
                    "score": 0.25,
                    "material_word_error_count": error_count,
                    "reference_word_count": reference_words,
                    "material_error_categories": ["number_or_name"] if error_count else [],
                    "reference_id": f"synthetic-reference-{index:04d}",
                    "reference_evaluation_sha256": "b" * 64,
                    "score_source_sha256": "c" * 64,
                })
                index += 1
        return {
            "@type": "OcrAutoValidationHoldout",
            "schema_version": "1.2",
            "cohort_id": "synthetic-holdout-v1",
            "cohort_manifest_sha256": "0" * 64,
            "policy": {
                "max_page_material_word_error_rate": 0.01,
                "target_false_accept_page_rate": 0.05,
                "confidence_level": 0.95,
            },
            "threshold": {
                "score_name": "synthetic_review_risk",
                "direction": "lower_is_safer",
                "cutoff": cutoff,
                "calibration_id": "synthetic-calibration-v1",
                "calibration_sha256": "a" * 64,
                "frozen_before_holdout": True,
                "frozen_at": "2026-01-02T00:00:00Z",
            },
            "required_strata": list(per_stratum),
            "cases": cases,
        }

    def write_dataset(self, dataset: dict) -> None:
        manifest = {
            "@type": "OcrAutoValidationHoldoutCohort",
            "schema_version": "1.1",
            "cohort_id": dataset["cohort_id"],
            "partition": "holdout",
            "frozen_at": "2026-01-01T00:00:00Z",
            "frozen_before_threshold": True,
            "required_strata": dataset["required_strata"],
            "sampling_design": {
                "frame": "synthetic-frame-v1",
                "method": "synthetic_stratified_document_sample",
                "independence_unit": "source_document_id",
            },
            "stratum_definitions": {
                stratum: {"language": stratum.split("-")[0], "readability": "medium", "layout": stratum.split("-")[1]}
                for stratum in dataset["required_strata"]
            },
            "pages": [
                {
                    "page_id": case["page_id"],
                    "source_document_id": case["source_document_id"],
                    "source_image_sha256": case["source_image_sha256"],
                    "stratum": case["stratum"],
                    "language": case["stratum"].split("-")[0],
                    "readability": "medium",
                    "layout": case["stratum"].split("-")[1],
                    "selection_reason": "synthetic deterministic fixture",
                    "prior_engine_exposure": [{"engine": "synthetic-ocr-v1", "status": "exposed"}],
                    "transformations": [],
                }
                for case in dataset["cases"]
            ],
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.cohort_manifest_path.write_bytes(manifest_bytes)
        dataset["cohort_manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        self.write_dataset_only(dataset)

    def write_dataset_only(self, dataset: dict) -> None:
        self.dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    def audit(self) -> dict:
        return audit_ocr_auto_validation_threshold(
            dataset_path=self.dataset_path,
            cohort_manifest_path=self.cohort_manifest_path,
        )

    def run_cli(self, *, apply: bool = False) -> tuple[int, dict]:
        args = [
            "documents", "ocr-threshold-audit",
            "--dataset", str(self.dataset_path),
            "--cohort-manifest", str(self.cohort_manifest_path),
            "--output", str(self.output_path),
        ]
        if apply:
            args.append("--apply")
        stream = io.StringIO()
        with redirect_stdout(stream):
            exit_code = main(args)
        return exit_code, json.loads(stream.getvalue())

    def test_59_pages_with_no_threshold_breaches_support_target_but_never_enable_machine_pass(self) -> None:
        self.write_dataset(self.dataset())

        report = self.audit()

        self.assertTrue(report["pilot_activation_eligible"])
        self.assertLessEqual(report["holdout"]["one_sided_95_percent_upper_bound"], 0.05)
        self.assertTrue(report["holdout"]["strata"]["deu-prose"]["meets_5_percent_false_accept_target"])
        self.assertFalse(report["auto_validation_enabled"])
        self.assertFalse(report["machine_pass"])
        self.assertEqual(report["dataset"]["sha256"], hashlib.sha256(self.dataset_path.read_bytes()).hexdigest())
        self.assertEqual(report["cohort"]["cohort_id"], "synthetic-holdout-v1")
        self.assertEqual(report["cohort"]["registered_page_count"], 59)
        self.assertEqual(
            report["cohort"]["manifest_sha256"],
            hashlib.sha256(self.cohort_manifest_path.read_bytes()).hexdigest(),
        )

    def test_58_zero_error_pages_are_insufficient(self) -> None:
        self.write_dataset(self.dataset(per_stratum={"deu-prose": 58}))

        report = self.audit()

        self.assertFalse(report["pilot_activation_eligible"])
        self.assertGreater(report["holdout"]["one_sided_95_percent_upper_bound"], 0.05)

    def test_stratum_bounds_use_familywise_bonferroni_adjustment(self) -> None:
        self.write_dataset(self.dataset(per_stratum={"deu-prose": 59, "ita-prose": 59}))

        report = self.audit()

        self.assertEqual(report["policy"]["stratum_multiplicity_adjustment"], "bonferroni_familywise_95_percent")
        self.assertGreater(
            report["holdout"]["strata"]["deu-prose"]["bonferroni_familywise_95_percent_upper_bound"],
            0.05,
        )
        self.assertFalse(report["pilot_activation_eligible"])

    def test_one_material_word_error_of_300_does_not_breach_page_limit(self) -> None:
        self.write_dataset(self.dataset(word_errors={0: 1}))

        report = self.audit()

        self.assertEqual(report["policy"]["max_page_material_word_error_rate"], 0.01)
        self.assertEqual(report["holdout"]["pages_over_page_word_error_limit"], 0)
        self.assertEqual(report["holdout"]["observed_false_accept_page_rate"], 0.0)
        self.assertTrue(report["pilot_activation_eligible"])

    def test_more_than_one_percent_material_word_errors_breaches_page_limit(self) -> None:
        self.write_dataset(self.dataset(word_errors={0: 4}))

        report = self.audit()

        self.assertEqual(report["holdout"]["pages_over_page_word_error_limit"], 1)
        self.assertEqual(report["holdout"]["observed_false_accept_page_rate"], 1 / 59)
        self.assertFalse(report["pilot_activation_eligible"])

    def test_pages_above_cutoff_do_not_enter_auto_accepted_denominator(self) -> None:
        dataset = self.dataset()
        for case in dataset["cases"]:
            case["score"] = 0.75
        dataset["cases"][0]["score"] = 0.25
        self.write_dataset(dataset)

        report = self.audit()

        self.assertEqual(report["holdout"]["case_count"], 59)
        self.assertEqual(report["holdout"]["auto_accepted_page_count"], 1)
        self.assertFalse(report["pilot_activation_eligible"])

    def test_non_holdout_or_ineligible_cases_are_rejected(self) -> None:
        for update in ({"partition": "calibration"}, {"accuracy_eligible": False}):
            with self.subTest(update=update):
                dataset = self.dataset()
                dataset["cases"][0].update(update)
                self.write_dataset(dataset)
                with self.assertRaises(ValueError):
                    self.audit()

    def test_duplicate_pages_and_bad_provenance_digests_are_rejected(self) -> None:
        dataset = self.dataset()
        dataset["cases"][1]["page_id"] = dataset["cases"][0]["page_id"]
        self.write_dataset(dataset)
        with self.assertRaisesRegex(ValueError, "duplicato"):
            self.audit()

        dataset = self.dataset()
        dataset["cases"][0]["score_source_sha256"] = "not-a-digest"
        self.write_dataset(dataset)
        with self.assertRaisesRegex(ValueError, "digest della sorgente"):
            self.audit()

    def test_material_error_label_requires_a_valid_category(self) -> None:
        dataset = self.dataset(word_errors={0: 1})
        dataset["cases"][0]["material_error_categories"] = []
        self.write_dataset(dataset)

        with self.assertRaisesRegex(ValueError, "material_error_categories"):
            self.audit()

        dataset = self.dataset()
        dataset["cases"][0]["reference_word_count"] = 0
        self.write_dataset(dataset)
        with self.assertRaisesRegex(ValueError, "reference_word_count"):
            self.audit()

        dataset = self.dataset()
        dataset["cases"][0]["source_document_id"] = ""
        self.write_dataset(dataset)
        with self.assertRaisesRegex(ValueError, "source_document_id"):
            self.audit()

    def test_missing_or_extra_case_is_rejected_against_frozen_cohort(self) -> None:
        dataset = self.dataset()
        self.write_dataset(dataset)
        dataset["cases"].pop()
        self.write_dataset_only(dataset)
        with self.assertRaisesRegex(ValueError, "mancanti=.*synthetic-0058"):
            self.audit()

        dataset = self.dataset()
        self.write_dataset(dataset)
        extra = dict(dataset["cases"][-1])
        extra.update({
            "page_id": "synthetic-extra",
            "source_document_id": "synthetic-document-extra",
            "source_image_sha256": "d" * 64,
            "reference_id": "synthetic-reference-extra",
            "score_source_sha256": "c" * 64,
        })
        dataset["cases"].append(extra)
        self.write_dataset_only(dataset)
        with self.assertRaisesRegex(ValueError, "extra=.*synthetic-extra"):
            self.audit()

    def test_case_identity_and_stratum_must_match_manifest(self) -> None:
        for field, value in (("source_image_sha256", "e" * 64), ("stratum", "ita-prose")):
            with self.subTest(field=field):
                dataset = self.dataset(per_stratum={"deu-prose": 1, "ita-prose": 1})
                self.write_dataset(dataset)
                dataset["cases"][0][field] = value
                self.write_dataset_only(dataset)
                with self.assertRaisesRegex(ValueError, field):
                    self.audit()

    def test_manifest_digest_and_frozen_status_are_required(self) -> None:
        dataset = self.dataset()
        self.write_dataset(dataset)
        self.cohort_manifest_path.write_bytes(self.cohort_manifest_path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "digest del manifest"):
            self.audit()

        dataset = self.dataset()
        self.write_dataset(dataset)
        manifest = json.loads(self.cohort_manifest_path.read_text(encoding="utf-8"))
        manifest["frozen_before_threshold"] = False
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.cohort_manifest_path.write_bytes(encoded)
        dataset["cohort_manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
        self.write_dataset_only(dataset)
        with self.assertRaisesRegex(ValueError, "frozen_before_threshold"):
            self.audit()

        dataset = self.dataset()
        dataset["threshold"]["frozen_at"] = "2025-12-31T23:59:59Z"
        self.write_dataset(dataset)
        with self.assertRaisesRegex(ValueError, "prima del cutoff"):
            self.audit()

        dataset = self.dataset()
        dataset["threshold"]["frozen_at"] = "2026-01-02T00:00:00"
        self.write_dataset(dataset)
        with self.assertRaisesRegex(ValueError, "fuso orario"):
            self.audit()

    def test_manifest_requires_sampling_strata_and_exposure_provenance(self) -> None:
        dataset = self.dataset()
        self.write_dataset(dataset)
        manifest = json.loads(self.cohort_manifest_path.read_text(encoding="utf-8"))
        del manifest["sampling_design"]
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.cohort_manifest_path.write_bytes(encoded)
        dataset["cohort_manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
        self.write_dataset_only(dataset)
        with self.assertRaisesRegex(ValueError, "sampling_design"):
            self.audit()

        dataset = self.dataset()
        self.write_dataset(dataset)
        manifest = json.loads(self.cohort_manifest_path.read_text(encoding="utf-8"))
        manifest["pages"][0]["prior_engine_exposure"] = [{"engine": "", "status": "unknown"}]
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.cohort_manifest_path.write_bytes(encoded)
        dataset["cohort_manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
        self.write_dataset_only(dataset)
        with self.assertRaisesRegex(ValueError, "prior_engine_exposure"):
            self.audit()

        dataset = self.dataset()
        self.write_dataset(dataset)
        manifest = json.loads(self.cohort_manifest_path.read_text(encoding="utf-8"))
        manifest["pages"][0]["prior_engine_exposure"] = []
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.cohort_manifest_path.write_bytes(encoded)
        dataset["cohort_manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
        self.write_dataset_only(dataset)
        with self.assertRaisesRegex(ValueError, "prior_engine_exposure"):
            self.audit()

    def test_manifest_rejects_duplicate_image_or_document_independence_units(self) -> None:
        dataset = self.dataset(per_stratum={"deu-prose": 2})
        self.write_dataset(dataset)
        manifest = json.loads(self.cohort_manifest_path.read_text(encoding="utf-8"))
        manifest["pages"][1]["source_document_id"] = manifest["pages"][0]["source_document_id"]
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.cohort_manifest_path.write_bytes(encoded)
        dataset["cohort_manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
        self.write_dataset_only(dataset)
        with self.assertRaisesRegex(ValueError, "source_document_id duplicato"):
            self.audit()

        dataset = self.dataset(per_stratum={"deu-prose": 2})
        self.write_dataset(dataset)
        manifest = json.loads(self.cohort_manifest_path.read_text(encoding="utf-8"))
        manifest["pages"][1]["source_image_sha256"] = manifest["pages"][0]["source_image_sha256"]
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self.cohort_manifest_path.write_bytes(encoded)
        dataset["cohort_manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
        self.write_dataset_only(dataset)
        with self.assertRaisesRegex(ValueError, "SHA-256 TIFF duplicato"):
            self.audit()

    def test_cli_preview_and_apply_are_idempotent_and_return_no_go_status(self) -> None:
        self.write_dataset(self.dataset())
        exit_code, preview = self.run_cli()
        self.assertEqual(exit_code, 0)
        self.assertEqual(preview["operation_status"], "preview")
        self.assertFalse(self.output_path.exists())

        exit_code, written = self.run_cli(apply=True)
        self.assertEqual(exit_code, 0)
        self.assertEqual(written["operation_status"], "written")
        saved = self.output_path.read_bytes()
        exit_code, existing = self.run_cli(apply=True)
        self.assertEqual(exit_code, 0)
        self.assertEqual(existing["operation_status"], "skipped_existing")
        self.assertEqual(saved, self.output_path.read_bytes())

        self.write_dataset(self.dataset(per_stratum={"deu-prose": 58}))
        exit_code, no_go = self.run_cli()
        self.assertEqual(exit_code, 2)
        self.assertFalse(no_go["pilot_activation_eligible"])


if __name__ == "__main__":
    unittest.main()
