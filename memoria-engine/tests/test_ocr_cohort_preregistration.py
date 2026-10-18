from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.document_analysis.ocr_cohort_preregistration import (  # noqa: E402
    validate_ocr_cohort_preregistration,
)
from caduti_fonti_report.memoria_cli import main  # noqa: E402


class OcrCohortPreregistrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest_path = self.root / "manifest.json"
        self.receipt_path = self.root / "receipt.json"
        self.output_path = self.root / "reports" / "report.json"

    @staticmethod
    def manifest() -> dict:
        definition = {"language": "deu", "readability": "medium", "layout": "prose"}
        return {
            "@type": "OcrCohortPreregistration", "schema_version": "1.0",
            "cohort_id": "synthetic-cohort", "state": "prepared", "prepared_at": "2026-01-01T00:00:00Z",
            "sampling_design": {"frame": "synthetic-frame", "method": "stratified-random", "independence_unit": "source_document_id"},
            "required_strata": ["deu-prose"], "stratum_definitions": {"deu-prose": definition},
            "pages": [
                {"page_id": f"synthetic-{index}", "source_document_id": f"document-{index}",
                 "source_image_sha256": f"{index:064x}", "partition": partition,
                 "stratum": "deu-prose", **definition, "selector": "synthetic-selector",
                 "selection_reason": "synthetic document sample before OCR",
                 "prior_engine_exposure": [{"engine": "synthetic-engine", "status": "unknown"}],
                 "transformations": []}
                for index, partition in enumerate(("calibration", "holdout"))
            ],
        }

    def write_manifest(self, manifest: dict) -> None:
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def freeze(self) -> None:
        manifest = self.manifest()
        manifest.update(state="frozen", frozen_at="2026-01-02T00:00:00+00:00")
        self.write_manifest(manifest)
        receipt = {"manifest_sha256": hashlib.sha256(self.manifest_path.read_bytes()).hexdigest(),
                   "record_id": "synthetic-receipt", "storage_reference": "synthetic-external-store",
                   "recorded_at": "2026-01-02T01:00:00Z"}
        self.receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    def validate(self, receipt: bool = False) -> dict:
        return validate_ocr_cohort_preregistration(
            manifest_path=self.manifest_path, freeze_receipt_path=self.receipt_path if receipt else None
        )

    def cli(self, *args: str) -> tuple[int, dict | None]:
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            status = main(["documents", "ocr-cohort-preregistration", "--manifest", str(self.manifest_path),
                           "--output", str(self.output_path), *args])
        return status, json.loads(output.getvalue()) if output.getvalue() else None

    def test_prepared_valid_report_metadata_only(self) -> None:
        manifest = self.manifest()
        self.write_manifest(manifest)
        report = self.validate()
        self.assertEqual(report["page_count"], 2)
        self.assertEqual(report["partitions"]["holdout"]["strata"], {"deu-prose": 1})
        for field in ("machine_pass", "auto_validation_enabled", "freeze_receipt_binding_verified",
                      "external_immutability_certified", "statistical_independence_certified"):
            self.assertIs(report[field], False)
        serialized = json.dumps(report)
        for forbidden in ("synthetic-0", "document-0", "synthetic-selector", "source_image", str(self.manifest_path)):
            self.assertNotIn(forbidden, serialized)

    def test_reads_only_explicit_manifest_and_receipt(self) -> None:
        self.freeze()
        opened = []
        original = Path.read_bytes
        def guarded(path):
            self.assertIn(path, (self.manifest_path, self.receipt_path))
            opened.append(path)
            return original(path)
        with patch.object(Path, "read_bytes", guarded):
            self.validate(receipt=True)
        self.assertEqual(opened, [self.manifest_path, self.receipt_path])

    def test_frozen_binding_and_no_certification(self) -> None:
        self.freeze()
        report = self.validate(receipt=True)
        self.assertIs(report["freeze_receipt_binding_verified"], True)
        self.assertIs(report["external_immutability_certified"], False)
        self.assertIs(report["statistical_independence_certified"], False)

    def test_frozen_requires_receipt_and_exact_raw_bytes(self) -> None:
        self.freeze()
        with self.assertRaises(ValueError):
            self.validate()
        self.manifest_path.write_bytes(self.manifest_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Digest"):
            self.validate(receipt=True)

    def test_prepared_rejects_receipt_without_opening_it(self) -> None:
        self.write_manifest(self.manifest())
        with self.assertRaises(ValueError):
            self.validate(receipt=True)
        self.assertFalse(self.receipt_path.exists())

    def test_duplicate_identities_within_and_across_partitions(self) -> None:
        for field in ("page_id", "source_document_id", "source_image_sha256"):
            for same_partition in (True, False):
                with self.subTest(field=field, same_partition=same_partition):
                    manifest = self.manifest()
                    if same_partition:
                        extra = deepcopy(manifest["pages"][0])
                        extra.update(page_id="extra", source_document_id="extra", source_image_sha256="a" * 64)
                        extra[field] = manifest["pages"][0][field]
                        manifest["pages"].append(extra)
                    else:
                        manifest["pages"][1][field] = manifest["pages"][0][field]
                    self.write_manifest(manifest)
                    with self.assertRaises(ValueError):
                        self.validate()
        manifest = self.manifest()
        manifest["pages"][0]["source_image_sha256"] = "A" * 64
        manifest["pages"][1]["source_image_sha256"] = "a" * 64
        self.write_manifest(manifest)
        with self.assertRaises(ValueError):
            self.validate()

    def test_missing_manifest_and_page_fields_fail_closed(self) -> None:
        for field in self.manifest():
            with self.subTest(manifest_field=field):
                manifest = self.manifest()
                del manifest[field]
                self.write_manifest(manifest)
                with self.assertRaises(ValueError):
                    self.validate()
        for field in self.manifest()["pages"][0]:
            with self.subTest(page_field=field):
                manifest = self.manifest()
                del manifest["pages"][0][field]
                self.write_manifest(manifest)
                with self.assertRaises(ValueError):
                    self.validate()

    def test_invalid_schema_sampling_strata_exposure_and_transformations(self) -> None:
        mutations = [
            lambda m: m.update({"@type": "other"}), lambda m: m.update(schema_version="1.1"),
            lambda m: m.update(state="other"), lambda m: m.update(prepared_at="2026-01-01"),
            lambda m: m.update(prepared_at="2026-01-01T00:00:00"),
            lambda m: m.update(prepared_at="2026-02-31T00:00:00Z"),
            lambda m: m.update(frozen_at="2026-01-02T00:00:00Z"),
            lambda m: m["sampling_design"].update(independence_unit="page_id"),
            lambda m: m["sampling_design"].update(frame=""),
            lambda m: m["sampling_design"].update(method=""),
            lambda m: m["required_strata"].append("deu-prose"),
            lambda m: m["stratum_definitions"].update(extra={}),
            lambda m: m["stratum_definitions"]["deu-prose"].update(language=""),
            lambda m: m["pages"][0].update(stratum="other"),
            lambda m: m["pages"][0].update(language="ita"),
            lambda m: m["pages"][0].update(source_image_sha256="bad"),
            lambda m: m["pages"][0].update(partition="other"),
            lambda m: m["pages"][0].update(partition="holdout"),
            lambda m: m["pages"][0].update(prior_engine_exposure=[]),
            lambda m: m["pages"][0].update(prior_engine_exposure=[{"engine": "x", "status": "other"}]),
            lambda m: m["pages"][0].update(prior_engine_exposure=[{"engine": "", "status": "exposed"}]),
            lambda m: m["pages"][0].update(transformations=[{}]),
            lambda m: m["pages"][0].update(transformations=[{"name": "rotate", "applied": True, "output_sha256": "bad"}]),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                manifest = self.manifest()
                mutate(manifest)
                self.write_manifest(manifest)
                with self.assertRaises(ValueError):
                    self.validate()

    def test_receipt_missing_fields_bad_timestamps_and_repository_location(self) -> None:
        for field in ("manifest_sha256", "record_id", "storage_reference", "recorded_at"):
            self.freeze()
            receipt = json.loads(self.receipt_path.read_text())
            del receipt[field]
            self.receipt_path.write_text(json.dumps(receipt))
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(receipt=True)
        for timestamp in ("2026-01-02T00:00:00", "2025-01-01T00:00:00Z"):
            self.freeze()
            receipt = json.loads(self.receipt_path.read_text())
            receipt["recorded_at"] = timestamp
            self.receipt_path.write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):
                self.validate(receipt=True)
        self.freeze()
        with self.assertRaisesRegex(ValueError, "esterno"):
            validate_ocr_cohort_preregistration(manifest_path=self.manifest_path, freeze_receipt_path=ROOT_DIR / "receipt.json")

    def test_responsible_alias_and_valid_transformations(self) -> None:
        manifest = self.manifest()
        for page in manifest["pages"]:
            page["responsible"] = page.pop("selector")
            page["transformations"] = [{"name": "synthetic", "applied": False, "output_sha256": None}]
        self.write_manifest(manifest)
        self.validate()

    def test_unknown_fields_and_duplicate_engine_exposure_fail_closed(self) -> None:
        mutations = [
            lambda m: m.update(ocr_text="synthetic forbidden OCR"),
            lambda m: m["pages"][1].update(reference_text="synthetic forbidden reference"),
            lambda m: m["sampling_design"].update(labels=[]),
            lambda m: m["stratum_definitions"]["deu-prose"].update(score=0.1),
            lambda m: m["pages"][0]["prior_engine_exposure"][0].update(ocr_text="forbidden"),
            lambda m: m["pages"][0]["prior_engine_exposure"].append({"engine": "synthetic-engine", "status": "exposed"}),
            lambda m: m["pages"][0].update(transformations=[{"name": "x", "applied": False, "text": "forbidden"}]),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                manifest = self.manifest()
                mutate(manifest)
                self.write_manifest(manifest)
                with self.assertRaises(ValueError):
                    self.validate()
        self.freeze()
        receipt = json.loads(self.receipt_path.read_text())
        receipt["ocr_text"] = "synthetic forbidden OCR"
        self.receipt_path.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError):
            self.validate(receipt=True)

    def test_frozen_requires_all_strata_per_partition_but_prepared_can_be_incomplete(self) -> None:
        manifest = self.manifest()
        manifest["required_strata"].append("ita-table")
        manifest["stratum_definitions"]["ita-table"] = {
            "language": "ita", "readability": "low", "layout": "table",
        }
        self.write_manifest(manifest)
        self.assertEqual(self.validate()["partitions"]["holdout"]["strata"]["ita-table"], 0)
        manifest.update(state="frozen", frozen_at="2026-01-02T00:00:00Z")
        self.write_manifest(manifest)
        with self.assertRaisesRegex(ValueError, "tutti gli strati"):
            self.validate(receipt=True)

    def test_json_duplicate_keys_and_malformed_inputs_fail_closed(self) -> None:
        for raw in (b"[]", b"{", b"\xff", b'{"state":"prepared","state":"frozen"}'):
            self.manifest_path.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.validate()

    def test_cli_preview_apply_idempotent_conflict_and_input_protection(self) -> None:
        self.write_manifest(self.manifest())
        status, report = self.cli()
        self.assertEqual(status, 0)
        self.assertEqual(report["operation_status"], "preview")
        self.assertFalse(self.output_path.parent.exists())
        status, report = self.cli("--apply")
        self.assertEqual((status, report["operation_status"]), (0, "written"))
        original = self.output_path.read_bytes()
        status, report = self.cli("--apply")
        self.assertEqual((status, report["operation_status"]), (0, "skipped_existing"))
        self.assertEqual(self.output_path.read_bytes(), original)
        self.output_path.write_text("different")
        self.assertEqual(self.cli("--apply")[0], 1)
        self.assertEqual(self.output_path.read_text(), "different")
        self.output_path = self.manifest_path
        self.assertEqual(self.cli("--apply")[0], 1)

    def test_cli_frozen_receipt_and_repository_output(self) -> None:
        self.freeze()
        self.assertEqual(self.cli()[0], 1)
        status, report = self.cli("--freeze-receipt", str(self.receipt_path))
        self.assertEqual(status, 0)
        self.assertIs(report["freeze_receipt_binding_verified"], True)
        self.output_path = ROOT_DIR / "should-not-exist-preregistration.json"
        self.assertEqual(self.cli("--apply")[0], 1)
        self.assertFalse(self.output_path.exists())

    def test_repository_manifest_rejected_before_read(self) -> None:
        with patch.object(Path, "read_bytes", side_effect=AssertionError("Manifest must not be opened")):
            with self.assertRaisesRegex(ValueError, "esterno"):
                validate_ocr_cohort_preregistration(manifest_path=ROOT_DIR / "synthetic-manifest.json")


if __name__ == "__main__":
    unittest.main()
