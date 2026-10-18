from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.ocr_tesseract_page_batch import run_tesseract_page_batch
from caduti_fonti_report.memoria_cli import main


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def ref(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture(base):
    pages, sources = [], []
    for index in (1, 2):
        raw, sidecar, metadata = (base / f"p{index}{suffix}" for suffix in (".tiff", ".yaml", ".metadata.json"))
        Image.new("RGB", (100, 100), "white").save(raw)
        write(sidecar, {"source_id": "archive", "document_id": f"doc{index}", "local_path": str(raw)})
        write(metadata, {"@type": "ProcessedDocumentMetadata", "source_id": "archive",
                         "source_document_id": f"doc{index}", "document_class": "image_scan",
                         "raw_file": raw.name, "sidecar_file": sidecar.name,
                         "sha256": ref(raw)["sha256"], "claim_eligible": False})
        pages.append({"page_id": f"p{index}", "source_id": "archive", "source_document_id": f"doc{index}",
                      "raw_tiff": ref(raw), "sidecar": ref(sidecar), "metadata": ref(metadata)})
        sources.append({"page_id": f"p{index}", "status": "completed",
                        "source": {"path": str(raw), "sha256": ref(raw)["sha256"]}})
    t36 = base / "t36.json"
    write(t36, {"@type": "OcrTransformPilot", "schema_version": "1.0", "review_status": "unreviewed",
                "accuracy_claim": "none_without_human_reference", "pages": sources})
    manifest = {"@type": "TesseractPageBatchManifest", "schema_version": "1.0", "root_dir": ".",
                "t36_manifest": ref(t36), "pages": pages}
    path = base / "batch.json"
    write(path, manifest)
    return path, manifest


def fake_runner(command):
    if command[-1] == "tsv":
        text = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
                "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t92\tTesto\n"
                "5\t1\t1\t1\t1\t2\t12\t0\t10\t10\t91\tvalido\n")
    else:
        text = "Testo valido"
    return subprocess.CompletedProcess(command, 0, stdout=text, stderr="")


class TesseractPageBatchTests(unittest.TestCase):
    def run_batch(self, path, runner, **kwargs):
        return run_tesseract_page_batch(manifest_path=path, output_dir=path.parent / "out",
                                        report_path=path.parent / "report.json", command_runner=runner, **kwargs)

    def test_preview_is_read_only_and_has_exact_output_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path, _ = fixture(base)
            before = sorted(str(item) for item in base.rglob("*"))
            runner = Mock(side_effect=AssertionError("preview called OCR"))
            report = self.run_batch(path, runner)
            self.assertEqual(report["summary"], {"ready": 2, "success": 0, "error": 0})
            self.assertEqual(sorted(str(item) for item in base.rglob("*")), before)
            self.assertEqual(report["pages"][0]["output_path"], str(base / "out/archive/doc1.text.json"))
            runner.assert_not_called()

    def test_apply_uses_existing_ocr_and_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path, _ = fixture(base)
            runner = Mock(side_effect=fake_runner)
            report = self.run_batch(path, runner, apply=True)
            self.assertEqual(report["summary"]["success"], 2)
            self.assertTrue(runner.called)
            payload = json.loads((base / "out/archive/doc1.text.json").read_text())
            self.assertEqual(payload["review_status"], "unreviewed")
            self.assertEqual(payload["source_document_id"], "doc1")
            self.assertEqual(payload["ocr_run_provenance"]["engine"], "tesseract")
            self.assertNotIn("adapter_ready", payload)
            self.assertTrue(payload["diagnostic_only"])
            self.assertTrue(report["diagnostic_only"])
            self.assertEqual(json.loads((base / "report.json").read_text()), report)

    def test_runtime_failure_isolated_and_later_page_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path, _ = fixture(base)
            def runner(command):
                if "p1.tiff" in str(command):
                    raise RuntimeError("fake runtime failure")
                return fake_runner(command)
            report = self.run_batch(path, runner, apply=True)
            self.assertEqual([page["status"] for page in report["pages"]], ["error", "success"])
            self.assertFalse((base / "out/archive/doc1.text.json").exists())
            self.assertTrue((base / "out/archive/doc2.text.json").exists())

    def test_t36_mutation_during_ocr_prevents_publishing(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path, _ = fixture(base)
            def runner(command):
                (base / "t36.json").write_text("{}")
                return fake_runner(command)
            report = self.run_batch(path, runner, apply=True)
            self.assertEqual(report["summary"]["error"], 2)
            self.assertFalse((base / "out").exists())

    def test_concurrent_output_creation_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path, _ = fixture(base)
            target = base / "out/archive/doc1.text.json"
            def runner(command):
                if "p1.tiff" in str(command):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("keep concurrent output")
                return fake_runner(command)
            report = self.run_batch(path, runner, apply=True)
            self.assertEqual([page["status"] for page in report["pages"]], ["error", "success"])
            self.assertEqual(target.read_text(), "keep concurrent output")

    def test_invalid_manifest_and_bindings_abort_before_all_ocr_and_writes(self):
        cases = ("type", "top_missing", "top_unknown", "coverage", "duplicate_page", "case_page", "tuple", "missing_field",
                 "unknown_field", "t36_hash", "raw_hash", "sidecar_hash", "metadata_hash",
                 "identity", "t36_raw_path", "t36_incomplete", "metadata_identity", "metadata_path",
                 "sidecar_identity", "metadata_class", "input_alias", "output_collision", "unsafe_identity")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                path, manifest = fixture(base)
                p1, p2 = manifest["pages"]
                if case == "type": manifest["@type"] = "Other"
                elif case == "top_missing": manifest.pop("root_dir")
                elif case == "top_unknown": manifest["langauge"] = "ita"
                elif case == "coverage": manifest["pages"].pop()
                elif case == "duplicate_page": p2["page_id"] = p1["page_id"]
                elif case == "case_page": p2["page_id"] = "P1"
                elif case == "tuple": p2["source_document_id"] = p1["source_document_id"]
                elif case == "missing_field": p2.pop("metadata")
                elif case == "unknown_field": p2["other"] = True
                elif case == "t36_hash": manifest["t36_manifest"]["sha256"] = "0" * 64
                elif case in ("raw_hash", "sidecar_hash", "metadata_hash"):
                    p2[{"raw_hash": "raw_tiff", "sidecar_hash": "sidecar", "metadata_hash": "metadata"}[case]]["sha256"] = "0" * 64
                elif case == "identity": p2["source_id"] = "other"
                elif case in ("t36_raw_path", "t36_incomplete"):
                    t36 = base / "t36.json"
                    value = json.loads(t36.read_text())
                    if case == "t36_raw_path": value["pages"][1]["source"]["path"] = str(base / "p1.tiff")
                    else: value["pages"][1]["status"] = "error"
                    write(t36, value)
                    manifest["t36_manifest"] = ref(t36)
                elif case.startswith("metadata_"):
                    metadata = base / p2["metadata"]["path"]
                    value = json.loads(metadata.read_text())
                    key, replacement = {"metadata_identity": ("source_document_id", "other"),
                                        "metadata_path": ("raw_file", "p1.tiff"),
                                        "metadata_class": ("document_class", "other")}[case]
                    value[key] = replacement
                    write(metadata, value)
                    p2["metadata"] = ref(metadata)
                elif case == "sidecar_identity":
                    sidecar = base / p2["sidecar"]["path"]
                    value = json.loads(sidecar.read_text())
                    value["document_id"] = "other"
                    write(sidecar, value)
                    p2["sidecar"] = ref(sidecar)
                elif case == "input_alias":
                    p2["metadata"] = copy.deepcopy(p1["metadata"])
                elif case == "output_collision":
                    # Different identities become the same registrar-safe filename.
                    for page, document in ((p1, "doc?"), (p2, "doc*")):
                        page["source_document_id"] = document
                        for role, key in (("metadata", "source_document_id"), ("sidecar", "document_id")):
                            target = base / page[role]["path"]
                            value = json.loads(target.read_text())
                            value[key] = document
                            write(target, value)
                            page[role] = ref(target)
                elif case == "unsafe_identity":
                    p2["source_id"] = ".."
                    for role in ("metadata", "sidecar"):
                        target = base / p2[role]["path"]
                        value = json.loads(target.read_text())
                        value["source_id"] = ".."
                        write(target, value)
                        p2[role] = ref(target)
                write(path, manifest)
                before = sorted(str(item) for item in base.rglob("*"))
                runner = Mock(side_effect=AssertionError("invalid preflight called OCR"))
                with self.assertRaises((ValueError, OSError)):
                    self.run_batch(path, runner, apply=True)
                runner.assert_not_called()
                self.assertEqual(sorted(str(item) for item in base.rglob("*")), before)

    def test_report_alias_existing_outputs_and_windows_collisions_rejected(self):
        for case in ("manifest", "input", "target", "parent", "existing", "case_existing"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                path, _ = fixture(base)
                target = base / "out/archive/doc1.text.json"
                report = {"manifest": path, "input": base / "p1.tiff", "target": target,
                          "parent": base / "out/archive", "existing": base / "report.json",
                          "case_existing": base / "report.json"}[case]
                if case == "existing": report.write_text("untouched")
                if case == "case_existing": (base / "REPORT.JSON").write_text("untouched")
                runner = Mock()
                with self.assertRaises((ValueError, OSError)):
                    run_tesseract_page_batch(manifest_path=path, output_dir=base / "out",
                                             report_path=report, command_runner=runner, apply=True)
                runner.assert_not_called()
                self.assertFalse(target.exists())

    def test_duplicate_keys_in_manifests_metadata_and_sidecar_fail_before_ocr(self):
        for role in ("manifest", "t36", "metadata", "sidecar"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                path, manifest = fixture(base)
                if role == "manifest":
                    text = path.read_text()
                    path.write_text('{"root_dir":".",' + text[1:])
                elif role == "t36":
                    target = base / "t36.json"
                    text = target.read_text()
                    target.write_text('{"schema_version":"1.0",' + text[1:])
                    manifest["t36_manifest"] = ref(target)
                    write(path, manifest)
                elif role == "metadata":
                    target = base / manifest["pages"][1]["metadata"]["path"]
                    text = target.read_text()
                    target.write_text('{"source_id":"ambiguous",' + text[1:])
                    manifest["pages"][1]["metadata"] = ref(target)
                    write(path, manifest)
                else:
                    target = base / manifest["pages"][1]["sidecar"]["path"]
                    target.write_text("source_id: ambiguous\nsource_id: archive\ndocument_id: doc2\n"
                                      + "local_path: " + json.dumps(str(base / "p2.tiff")) + "\n")
                    manifest["pages"][1]["sidecar"] = ref(target)
                    write(path, manifest)
                before = sorted(str(item) for item in base.rglob("*"))
                runner = Mock(side_effect=AssertionError("duplicate input reached OCR"))
                with self.assertRaises(ValueError):
                    self.run_batch(path, runner, apply=True)
                runner.assert_not_called()
                self.assertEqual(sorted(str(item) for item in base.rglob("*")), before)

    def test_repository_output_and_report_are_rejected_before_writes(self):
        repository = Path(__file__).resolve().parents[2]
        for role in ("output", "report"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                path, _ = fixture(base)
                output = repository / "forbidden-tesseract-output" if role == "output" else base / "out"
                report = repository / "forbidden-tesseract-report.json" if role == "report" else base / "report.json"
                runner = Mock(side_effect=AssertionError("repository target reached OCR"))
                with self.assertRaisesRegex(ValueError, "esterni al repository"):
                    run_tesseract_page_batch(manifest_path=path, output_dir=output,
                                             report_path=report, command_runner=runner, apply=True)
                runner.assert_not_called()
                self.assertFalse(output.exists())
                self.assertFalse(report.exists())

    def test_cli_help(self):
        with self.assertRaises(SystemExit) as result:
            main(["documents", "ocr-tesseract-page-batch", "--help"])
        self.assertEqual(result.exception.code, 0)

    def test_cli_forwards_all_supported_ocr_options(self):
        with patch("caduti_fonti_report.document_analysis.ocr_tesseract_page_batch.run_tesseract_page_batch") as runner:
            runner.return_value = {"summary": {"error": 0}}
            self.assertEqual(main(["documents", "ocr-tesseract-page-batch", "--manifest", "batch.json",
                                   "--output-dir", "out", "--report", "report.json", "--psm", "6",
                                   "--oem", "1", "--dpi", "300", "--preprocess-before-ocr",
                                   "--enable-region-ocr", "--apply"]), 0)
            self.assertEqual(runner.call_args.kwargs["page_segmentation_mode"], "6")
            self.assertEqual(runner.call_args.kwargs["engine_mode"], "1")
            self.assertEqual(runner.call_args.kwargs["dpi"], "300")
            self.assertTrue(runner.call_args.kwargs["preprocess_before_ocr"])
            self.assertTrue(runner.call_args.kwargs["enable_region_ocr"])

    def test_core_forwards_options_without_changing_review_or_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, _ = fixture(Path(temporary))
            with patch("caduti_fonti_report.document_analysis.ocr_tesseract_page_batch.run_document_ocr",
                       side_effect=RuntimeError("stop after observing call")) as runner:
                report = self.run_batch(path, Mock(), apply=True, page_segmentation_mode="6", engine_mode="1",
                                        dpi="300", preprocess_before_ocr=True, enable_region_ocr=True,
                                        tesseract_path="fake-tesseract", language="eng")
            self.assertEqual(runner.call_count, 2)
            self.assertEqual(report["summary"]["error"], 2)
            self.assertEqual(report["configuration"], {
                "tesseract_path": "fake-tesseract", "language": "eng", "page_segmentation_mode": "6",
                "engine_mode": "1", "dpi": "300", "preprocess_before_ocr": True, "enable_region_ocr": True,
            })
            for call in runner.call_args_list:
                self.assertEqual(call.kwargs["page_segmentation_mode"], "6")
                self.assertEqual(call.kwargs["engine_mode"], "1")
                self.assertEqual(call.kwargs["dpi"], "300")
                self.assertTrue(call.kwargs["preprocess_before_ocr"])
                self.assertTrue(call.kwargs["enable_region_ocr"])
                self.assertEqual(call.kwargs["review_status"], "unreviewed")
                self.assertFalse(call.kwargs["overwrite"])


if __name__ == "__main__":
    unittest.main()
