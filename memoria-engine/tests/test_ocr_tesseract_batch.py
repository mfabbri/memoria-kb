from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import test_ocr_tesseract_evidence_adapter as adapter_fixture
from caduti_fonti_report.document_analysis.ocr_tesseract_batch import run_tesseract_evidence_batch
from caduti_fonti_report.memoria_cli import main


class TesseractEvidenceBatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture = adapter_fixture.TesseractEvidenceAdapterTest()
        fixture.setUp()
        self.processed = fixture.payload
        self.primary = fixture.primary
        self.anchor = fixture.anchor
        self.manifest = self.root / "manifests" / "batch.json"
        self.case = {"case_id": "page-1", "processed_text": "../inputs/processed.json",
                     "primary_evidence": "../inputs/primary.json", "original_page": "../inputs/anchor.json"}
        self.write(self.root / "inputs" / "processed.json", self.processed)
        self.write(self.root / "inputs" / "primary.json", self.primary)
        self.write(self.root / "inputs" / "anchor.json", self.anchor)
        self.save_manifest([self.case])

    def write(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def save_manifest(self, cases):
        self.write(self.manifest, {"@type": "TesseractEvidenceBatchManifest", "schema_version": "1.0", "cases": cases})

    def run_batch(self, **kwargs):
        return run_tesseract_evidence_batch(manifest_path=self.manifest,
                                           output_dir=Path("../outputs"), report_path=Path("../report.json"), **kwargs)

    def test_multi_case_apply_resolves_paths_and_preserves_inputs_and_provenance(self):
        self.save_manifest([self.case, {**self.case, "case_id": "page-2"}])
        before = {path: path.read_bytes() for path in self.root.rglob("*.json")}
        report = self.run_batch(apply=True)
        self.assertEqual(report["summary"], {"success": 2, "error": 0})
        self.assertTrue(report["diagnostic_only"])
        self.assertFalse(report["machine_pass_allowed"])
        self.assertFalse(report["visual_coverage_verified"])
        self.assertEqual(json.loads((self.root / "report.json").read_text(encoding="utf-8")), report)
        for record in report["cases"]:
            self.assertTrue(record["written"])
            self.assertEqual(len(record["inputs"]["processed_text"]["sha256"]), 64)
            evidence = json.loads(Path(record["output_path"]).read_text(encoding="utf-8"))
            self.assertEqual(evidence["ocr_run_provenance"], self.processed["ocr_run_provenance"])
            self.assertFalse(evidence["adapter"]["machine_pass_allowed"])
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_preview_writes_nothing_and_allows_no_destinations(self):
        report = self.run_batch()
        self.assertEqual(report["summary"]["success"], 1)
        self.assertFalse(report["cases"][0]["written"])
        self.assertFalse((self.root / "outputs").exists())
        self.assertFalse((self.root / "report.json").exists())
        report = run_tesseract_evidence_batch(manifest_path=self.manifest)
        self.assertIsNone(report["cases"][0]["output_path"])

    def test_adapter_failures_are_isolated_from_later_valid_pages(self):
        bad = {**self.processed, "ocr_run_provenance": {}}
        self.write(self.root / "inputs" / "bad.json", bad)
        self.save_manifest([{**self.case, "case_id": "bad", "processed_text": "../inputs/bad.json"}, self.case])
        report = self.run_batch(apply=True)
        self.assertEqual([case["status"] for case in report["cases"]], ["error", "success"])
        self.assertEqual(report["cases"][0]["error"]["type"], "ValueError")
        self.assertFalse((self.root / "outputs" / "bad.tesseract.evidence.json").exists())
        self.assertTrue((self.root / "outputs" / "page-1.tesseract.evidence.json").exists())

    def test_missing_and_invalid_page_json_are_isolated(self):
        (self.root / "inputs" / "bad.json").write_text("{", encoding="utf-8")
        self.save_manifest([{**self.case, "case_id": "missing", "processed_text": "absent.json"},
                            {**self.case, "case_id": "invalid", "processed_text": "../inputs/bad.json"}, self.case])
        report = self.run_batch()
        self.assertEqual(report["summary"], {"success": 1, "error": 2})

    def test_optional_registration_must_attest_same_run(self):
        registration = {"@type": "DocumentOcrRegistration", "source_document_id": "synthetic-document",
                        "transcription_method": "external_ocr_unreviewed", "ocr_run_provenance": self.processed["ocr_run_provenance"]}
        self.write(self.root / "inputs" / "registration.json", registration)
        self.save_manifest([{**self.case, "registration": "../inputs/registration.json"}])
        self.assertEqual(self.run_batch()["summary"]["success"], 1)
        registration["source_document_id"] = "different"
        self.write(self.root / "inputs" / "registration.json", registration)
        self.assertEqual(self.run_batch()["summary"]["error"], 1)

    def test_duplicate_and_unsafe_case_ids_are_hard_errors(self):
        for bad_id in ("page-1", "PAGE-1", "../escape", "x/y", "x\\y", "", "."):
            with self.subTest(case_id=bad_id):
                self.save_manifest([self.case, {**self.case, "case_id": bad_id}])
                with self.assertRaises(ValueError):
                    self.run_batch(apply=True)
                self.assertFalse((self.root / "outputs").exists())

    def test_malformed_manifests_fail_before_any_output(self):
        valid = {"@type": "TesseractEvidenceBatchManifest", "schema_version": "1.0", "cases": [self.case]}
        for payload in ([], {}, {**valid, "schema_version": "2.0"}, {**valid, "cases": []},
                        {**valid, "cases": {}}, {**valid, "cases": [None]},
                        {**valid, "cases": [{**self.case, "processed_text": None}]},
                        {**valid, "cases": [{**self.case, "original_pgae": "typo.json"}]}):
            with self.subTest(payload=payload):
                self.write(self.manifest, payload)
                with self.assertRaises(ValueError):
                    self.run_batch(apply=True)
                self.assertFalse((self.root / "outputs").exists())
        self.manifest.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_batch()

    def test_existing_later_output_or_report_blocks_all_writes(self):
        self.save_manifest([self.case, {**self.case, "case_id": "page-2"}])
        for target in (self.root / "outputs" / "page-2.tesseract.evidence.json", self.root / "report.json"):
            with self.subTest(target=target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"keep")
                with self.assertRaises(FileExistsError):
                    self.run_batch(apply=True)
                self.assertEqual(target.read_bytes(), b"keep")
                self.assertFalse((self.root / "outputs" / "page-1.tesseract.evidence.json").exists())
                target.unlink()

    def test_report_must_not_alias_inputs_or_evidence(self):
        for report in ("batch.json", "../inputs/processed.json", "../outputs/page-1.tesseract.evidence.json", "../outputs"):
            with self.subTest(report=report):
                with self.assertRaises(ValueError):
                    run_tesseract_evidence_batch(manifest_path=self.manifest, output_dir=Path("../outputs"),
                                                 report_path=Path(report), apply=True)
                self.assertFalse((self.root / "outputs").exists())

    def test_apply_requires_both_explicit_destinations(self):
        for kwargs in ({}, {"output_dir": self.root / "outputs"}, {"report_path": self.root / "report.json"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_tesseract_evidence_batch(manifest_path=self.manifest, apply=True, **kwargs)

    def test_cli_preview_apply_and_failure_exit_status(self):
        args = ["documents", "tesseract-evidence-batch", "--manifest", str(self.manifest),
                "--output-dir", "../outputs", "--report", "../report.json"]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
            self.assertEqual(main(args + ["--apply"]), 0)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(args + ["--apply"]), 1)
        self.save_manifest([{**self.case, "processed_text": "missing.json"}])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args[:4]), 1)


if __name__ == "__main__":
    unittest.main()
