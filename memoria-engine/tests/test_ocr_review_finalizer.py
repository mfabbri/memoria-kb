from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from caduti_fonti_report.document_analysis.ocr_review_batch import REVIEW_ROLES
from caduti_fonti_report.document_analysis.ocr_review_finalizer import (
    EDITABLE_REVIEW_ROLES,
    finalize_ocr_review_package,
)
from caduti_fonti_report.memoria_cli import main


class OcrReviewFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package_root = self.root / "package"
        self.package_root.mkdir()
        self.source_manifest = self.package_root / "package-manifest.json"
        self.final_manifest = self.package_root / "finalized-package-manifest.json"
        self.report_path = self.root / "review-report.json"
        package_inputs = {}
        for role in ("source_manifest", "t37_manifest"):
            path = self.package_root / f"{role}.json"
            path.write_text("{}", encoding="utf-8")
            package_inputs[role] = self.artifact(path)
        self.page = {"page_id": "p1", "review_inputs": {}, "outputs": []}
        for role in REVIEW_ROLES:
            path = self.package_root / "p1" / f"{role}.json"
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps({"page_id": "p1", "role": role}), encoding="utf-8")
            record = self.artifact(path)
            self.page["review_inputs"][role] = record
            if role != "image":
                self.page["outputs"].append(record)
        extra_output = self.package_root / "p1" / "crop.png"
        extra_output.write_bytes(b"synthetic crop")
        self.extra_output = extra_output
        self.page["outputs"].append(self.artifact(extra_output))
        self.package = {
            "@type": "OcrReviewPackage", "schema_version": "1.0",
            **package_inputs, "pages": [self.page], "status": "template_incomplete",
            "review_status": "unreviewed", "machine_pass": False,
            "auto_validation_enabled": False, "output_dir": str(self.package_root),
            "report_path": str(self.source_manifest),
        }
        self.write_source_manifest()
        self.edit_review_sidecars()

    def artifact(self, path):
        return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def write_source_manifest(self):
        self.source_manifest.write_text(json.dumps(self.package, ensure_ascii=False), encoding="utf-8")

    def edit_review_sidecars(self):
        for role in EDITABLE_REVIEW_ROLES:
            path = Path(self.page["review_inputs"][role]["path"])
            path.write_text(json.dumps({"page_id": "p1", "role": role, "reviewed": True}), encoding="utf-8")

    def finalize(self, **kwargs):
        return finalize_ocr_review_package(
            manifest_path=self.source_manifest, final_manifest_path=self.final_manifest,
            output_path=self.report_path, **kwargs)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_preview_refreshes_only_review_hashes_and_is_read_only(self):
        before = self.snapshot()
        with patch("caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review",
                   return_value={"status": "candidate_ready"}) as gate:
            report = self.finalize()
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(report["operation_status"], "preview")
        self.assertFalse(report["writes_performed"])
        self.assertEqual(report["review_batch"]["status"], "completed")
        self.assertEqual(report["review_batch"]["pages"][0]["status"], "candidate_ready")
        self.assertFalse(self.final_manifest.exists())
        self.assertFalse(self.report_path.exists())
        self.assertEqual(before, self.snapshot())
        for role in EDITABLE_REVIEW_ROLES:
            refreshed = report["review_batch"]["pages"][0]["inputs"][role]
            self.assertEqual(refreshed, self.artifact(Path(refreshed["path"])))

    def test_apply_writes_new_manifest_and_batch_report_without_mutating_source(self):
        source_before = self.source_manifest.read_bytes()
        with patch("caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review",
                   return_value={"status": "needs_review"}):
            report = self.finalize(apply=True)
        self.assertEqual(report["operation_status"], "written")
        self.assertTrue(report["writes_performed"])
        self.assertEqual(self.source_manifest.read_bytes(), source_before)
        final_payload = json.loads(self.final_manifest.read_text(encoding="utf-8"))
        self.assertEqual(final_payload["submission_provenance"]["source_package_manifest"], self.artifact(self.source_manifest))
        self.assertEqual(final_payload["submission_provenance"]["refreshed_review_roles"], list(EDITABLE_REVIEW_ROLES))
        for role in EDITABLE_REVIEW_ROLES:
            record = final_payload["pages"][0]["review_inputs"][role]
            self.assertEqual(record, self.artifact(Path(record["path"])))
        batch_report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(batch_report["package_manifest"], self.artifact(self.final_manifest))
        self.assertEqual(batch_report["counts"], {"needs_review": 1})
        self.assertFalse(batch_report["machine_pass"])
        self.assertFalse(batch_report["auto_validation_enabled"])

    def test_immutable_input_tampering_rejected_before_gate(self):
        path = Path(self.page["review_inputs"]["evidence"]["path"])
        path.write_text("tampered", encoding="utf-8")
        with patch("caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review") as gate:
            with self.assertRaisesRegex(ValueError, "immutabile"):
                self.finalize(apply=True)
        gate.assert_not_called()
        self.assertFalse(self.final_manifest.exists())
        self.assertFalse(self.report_path.exists())

    def test_non_review_output_tampering_rejected(self):
        self.extra_output.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "output immutabile"):
            self.finalize()

    def test_manifest_change_during_preview_invalidates_result(self):
        def mutate(**kwargs):
            self.source_manifest.write_bytes(self.source_manifest.read_bytes() + b"\n")
            return {"status": "candidate_ready"}
        with patch("caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "manifest package sorgente"):
                self.finalize()
        self.assertFalse(self.final_manifest.exists())
        self.assertFalse(self.report_path.exists())

    def test_cli_dispatches_preview_and_apply(self):
        expected = {"review_batch": {"status": "completed"}, "operation_status": "preview"}
        args = ["documents", "ocr-review-finalize", "--manifest", str(self.source_manifest),
                "--final-manifest", str(self.final_manifest), "--output", str(self.report_path)]
        output = io.StringIO()
        with patch("caduti_fonti_report.memoria_cli.finalize_ocr_review_package",
                   return_value=expected) as finalize, redirect_stdout(output):
            self.assertEqual(main(args), 0)
        finalize.assert_called_once_with(manifest_path=self.source_manifest,
                                         final_manifest_path=self.final_manifest,
                                         output_path=self.report_path, apply=False)
        self.assertEqual(json.loads(output.getvalue()), expected)


if __name__ == "__main__":
    unittest.main()
