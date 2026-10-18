from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_ocr_review_orchestrator as fixtures
from caduti_fonti_report.document_analysis.ocr_review_batch import REVIEW_ROLES, run_ocr_review_batch
from caduti_fonti_report.memoria_cli import main


class OcrReviewBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / "package"
        self.package.mkdir()
        self.manifest = self.package / "package-manifest.json"
        self.output = self.root / "batch.json"
        self.payload = {"@type": "OcrReviewPackage", "schema_version": "1.0",
            "output_dir": str(self.package), "report_path": str(self.manifest), "pages": [],
            "machine_pass": False, "auto_validation_enabled": False, "review_status": "unreviewed"}
        for role in ("source_manifest", "t37_manifest"):
            path = self.package / (role + ".json")
            path.write_text("{}", encoding="utf-8")
            self.payload[role] = self.artifact(path)
        for page_id in ("p1", "p2"):
            folder = self.package / page_id
            folder.mkdir()
            roles = {}
            for role in REVIEW_ROLES:
                path = folder / (role + ".json")
                path.write_text(json.dumps({"page_id": page_id}), encoding="utf-8")
                roles[role] = self.artifact(path)
            self.payload["pages"].append({"page_id": page_id, "review_inputs": roles})
        self.sync()

    def artifact(self, path):
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def sync(self):
        self.manifest.write_text(json.dumps(self.payload), encoding="utf-8")

    def run_batch(self, **kwargs):
        return run_ocr_review_batch(manifest_path=self.manifest, output_path=self.output, **kwargs)

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_good_multi_page_preview_is_read_only_and_links_all_hashes(self):
        before = self.snapshot()
        with patch("caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review",
                   side_effect=[{"status": "candidate_ready"}, {"status": "needs_review"}]) as gate:
            report = self.run_batch()
        self.assertEqual(gate.call_count, 2)
        for call, page in zip(gate.call_args_list, self.payload["pages"]):
            self.assertEqual(call.kwargs, {role + "_path": Path(record["path"])
                                          for role, record in page["review_inputs"].items()})
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["counts"], {"candidate_ready": 1, "needs_review": 1})
        self.assertEqual(report["package_manifest"], self.artifact(self.manifest))
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.output.exists())
        for row in [report, *report["pages"]]:
            self.assertFalse(row["machine_pass"])
            self.assertFalse(row["auto_validation_enabled"])
            self.assertEqual(row["promotion_status"], "unreviewed")
        for row in report["pages"]:
            for record in row["inputs"].values():
                self.assertEqual(record, self.artifact(Path(record["path"])))

    def test_blocked_or_error_page_does_not_skip_next_page(self):
        for first in ({"status": "blocked"}, ValueError("bad page")):
            with self.subTest(first=first), patch(
                    "caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review",
                    side_effect=[first, {"status": "candidate_ready"}]) as gate:
                report = self.run_batch()
                self.assertEqual(gate.call_count, 2)
                self.assertEqual(report["status"], "blocked")
                self.assertEqual(report["pages"][1]["status"], "candidate_ready")
                self.assertEqual(report["pages"][0]["status"],
                                 "error" if isinstance(first, Exception) else "blocked")

    def test_invalid_package_rejected_before_any_page_gate(self):
        original = copy.deepcopy(self.payload)
        mutations = [
            lambda p: p.update(schema_version="2.0"),
            lambda p: p.update(machine_pass=True),
            lambda p: p["pages"][1].update(page_id="p1"),
            lambda p: p["pages"][1]["review_inputs"].pop("ledger"),
            lambda p: p["pages"][1]["review_inputs"]["image"].pop("sha256"),
            lambda p: p["pages"][1]["review_inputs"]["evidence"].update(sha256="0" * 64),
            lambda p: p["source_manifest"].update(sha256="0" * 64),
            lambda p: p["t37_manifest"].update(sha256="0" * 64),
            lambda p: p["pages"][1]["review_inputs"]["ledger"].update(path="relative.json"),
        ]
        outside = self.root / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        mutations.append(lambda p: p["pages"][1]["review_inputs"].update(ledger=self.artifact(outside)))
        for mutation in mutations:
            self.payload = copy.deepcopy(original)
            mutation(self.payload)
            self.sync()
            with self.subTest(mutation=mutation), patch(
                    "caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review") as gate:
                with self.assertRaises(ValueError):
                    self.run_batch(apply=True)
                gate.assert_not_called()
                self.assertFalse(self.output.exists())

    def test_apply_creates_only_report_and_refuses_existing_or_unsafe_destinations(self):
        before = self.snapshot()
        with patch("caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review",
                   return_value={"status": "candidate_ready"}):
            report = self.run_batch(apply=True)
        after = self.snapshot()
        self.assertEqual(set(after) - set(before), {"batch.json"})
        self.assertEqual({key: after[key] for key in before}, before)
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8")), report)
        for apply in (False, True):
            with self.assertRaises(FileExistsError):
                self.run_batch(apply=apply)
        for path in (self.package / "new.json", self.root / "missing" / "report.json",
                     Path(__file__).resolve().parent / "batch-new.json"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                run_ocr_review_batch(manifest_path=self.manifest, output_path=path, apply=True)

    def test_manifest_changed_during_gate_never_writes_linked_report(self):
        def mutate(**kwargs):
            self.manifest.write_bytes(self.manifest.read_bytes() + b"\n")
            return {"status": "candidate_ready"}
        with patch("caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "manifest package"):
                self.run_batch(apply=True)
        self.assertFalse(self.output.exists())

    def test_real_gate_on_complete_synthetic_inputs_and_cli(self):
        temporary_directory = tempfile.TemporaryDirectory
        names = dict(zip(REVIEW_ROLES, ("page.tiff", "evidence.json", "structure.json", "page.md",
            "review.json", "layout.json", "ledger.json", "dispositions.json", "comparison.json", "tesseract.json")))
        self.payload["pages"] = []
        for page_id in ("p1", "p2"):
            class PageFixture(fixtures.OcrReviewOrchestratorTest):
                def write(inner, name, payload):
                    if name == "evidence.json":
                        payload["page_id"] = page_id
                        payload["source_page"]["original_page"]["page_id"] = page_id
                    payload = json.loads(json.dumps(payload).replace('"p1"', json.dumps(page_id)))
                    super().write(name, payload)
            fixture = PageFixture()
            self.addCleanup(fixture.doCleanups)
            with patch.object(fixtures.tempfile, "TemporaryDirectory",
                              side_effect=lambda: temporary_directory(dir=self.package)):
                fixture.setUp()
            self.payload["pages"].append({"page_id": page_id, "review_inputs": {
                role: self.artifact(fixture.root / name) for role, name in names.items()}})
        self.sync()
        before = self.snapshot()
        report = self.run_batch()
        self.assertEqual([row["status"] for row in report["pages"]], ["candidate_ready"] * 2)
        self.assertEqual(before, self.snapshot())
        output, error = io.StringIO(), io.StringIO()
        args = ["documents", "ocr-review-batch", "--manifest", str(self.manifest), "--output", str(self.output)]
        with redirect_stdout(output), redirect_stderr(error):
            self.assertEqual(main(args + ["--apply"]), 0)
            self.assertEqual(main(args), 1)
        self.assertEqual(json.loads(output.getvalue())["operation_status"], "written")
        self.assertIn("nuovo", error.getvalue())
        # A validly hash-bound, semantically invalid page blocks only its gate.
        self.output = self.root / "blocked.json"
        layout = self.payload["pages"][0]["review_inputs"]["layout"]
        path = Path(layout["path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["reading_order"] = []
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.payload["pages"][0]["review_inputs"]["layout"] = self.artifact(path)
        self.sync()
        report = self.run_batch()
        self.assertEqual([row["status"] for row in report["pages"]], ["blocked", "candidate_ready"])

    def test_wrong_page_identity_is_an_isolated_error(self):
        self.payload["pages"][0]["page_id"] = "wrong-page"
        self.sync()
        with patch("caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review",
                   return_value={"status": "candidate_ready"}) as gate:
            report = self.run_batch()
        self.assertEqual(gate.call_count, 1)
        self.assertEqual([row["status"] for row in report["pages"]], ["error", "candidate_ready"])

    def test_input_changed_by_later_page_invalidates_earlier_result(self):
        calls = []
        def gate(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                calls[0]["ledger_path"].write_text("changed", encoding="utf-8")
            return {"status": "candidate_ready"}
        with patch("caduti_fonti_report.document_analysis.ocr_review_batch.run_ocr_review", side_effect=gate):
            report = self.run_batch()
        self.assertEqual([row["status"] for row in report["pages"]], ["error", "candidate_ready"])
        self.assertNotIn("review", report["pages"][0])


if __name__ == "__main__":
    unittest.main()
