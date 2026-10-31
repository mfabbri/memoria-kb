from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis import ocr_workflow as workflow


class OcrWorkflowTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        pages = []
        for index in range(2):
            source = self.root / f"scan{index}.tif"
            Image.new("L", (16, 16), 255).save(source)
            pages.append({"page_id": f"p{index}", "path": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
        self.inputs = self.root / "inputs.json"
        self.inputs.write_text(json.dumps({"schema_version": "1.0", "pages": pages}))
        for directory in ("det", "rec"):
            folder = self.root / directory
            folder.mkdir()
            for name in ("inference.json", "inference.pdiparams", "inference.yml"):
                (folder / name).write_bytes(b"synthetic model")
        self.payload = {
            "@type": "OcrWorkflow", "schema_version": "1.0",
            "t36": {"input_manifest": {"path": "inputs.json", "sha256": hashlib.sha256(self.inputs.read_bytes()).hexdigest()},
                    "language": "deu", "model": {"ocr_version": "PP-OCRv5",
                    "text_detection_model_name": "PP-OCRv5_server_det", "text_recognition_model_name": "latin_PP-OCRv5_mobile_rec",
                    "text_detection_model_dir": "det", "text_recognition_model_dir": "rec"},
                    "runtime": {"device": "cpu", "enable_mkldnn": False, "text_det_limit_side_len": 8192,
                                "text_det_limit_type": "max", "tile_width": 2400, "tile_height": 2400,
                                "tile_overlap": 200, "retry_limit": 0}},
            "t37": {"variant_id": "raw", "page_profiles": {"p0": "numbered_report", "p1": "leader_list_report"}}}
        self.manifest = self.root / "workflow.json"
        self.write_manifest()
        self.output = self.root / "output"
        self.calls = []

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.payload))

    def runner(self, path, language):
        self.calls.append(path)
        return [{"rec_texts": ["1. Synthetic report"], "rec_scores": [0.9],
                 "rec_boxes": [[1, 1, 14, 10]]}]

    def run_workflow(self, **kwargs):
        options = dict(manifest_path=self.manifest, output_dir=self.output, apply=True,
                       runner_factory=lambda: self.runner)
        options.update(kwargs)
        return workflow.run_ocr_workflow(**options)

    def snapshot(self):
        return {p.relative_to(self.output).as_posix(): p.read_bytes() for p in self.output.rglob("*") if p.is_file()}

    def test_preview_no_writes_or_runtime_and_relative_paths(self):
        factory = Mock(side_effect=AssertionError("no runtime"))
        report = self.run_workflow(apply=False, runner_factory=factory)
        self.assertEqual(report["status"], "preview")
        self.assertEqual(report["page_count"], 2)
        self.assertFalse(report["writes_performed"])
        self.assertFalse(self.output.exists())
        factory.assert_not_called()

    def test_success_and_resume_preserve_all_stage_bytes_and_times(self):
        report = self.run_workflow()
        self.assertEqual(report["status"], "completed_unreviewed")
        self.assertEqual(len(self.calls), 10)
        self.assertTrue((self.output / "t37" / "markdown" / "p0.md").is_file())
        self.assertFalse(report["machine_pass"])
        self.assertEqual(report["review_status"], "unreviewed")
        before = self.snapshot()
        times = {p: p.stat().st_mtime_ns for folder in ("t36", "t37") for p in (self.output / folder).rglob("*") if p.is_file()}
        factory = Mock(side_effect=AssertionError("no runtime"))
        report = self.run_workflow(resume=True, runner_factory=factory)
        self.assertEqual(report["status"], "completed_unreviewed")
        self.assertTrue(report["t37"]["reused"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(times, {p: p.stat().st_mtime_ns for p in times})
        factory.assert_not_called()

    def test_partial_blocks_t37_then_resumes_only_failed_page(self):
        def failure(path, language):
            if "p1" in path.parts:
                raise RuntimeError("synthetic failure")
            return self.runner(path, language)
        with patch.object(workflow.structure, "export_ocr_transform_structure") as exporter:
            report = self.run_workflow(runner_factory=lambda: failure)
            exporter.assert_not_called()
        self.assertEqual(report["status"], "partial_unreviewed")
        self.assertFalse((self.output / "t37").exists())
        self.assertEqual(len(self.calls), 5)
        report = self.run_workflow(resume=True)
        self.assertEqual(report["status"], "completed_unreviewed")
        self.assertEqual(len(self.calls), 10)
        self.assertEqual(report["t36"]["metrics"]["reused_page_count"], 1)

    def assert_rejected_unchanged(self):
        before = self.snapshot()
        factory = Mock()
        with self.assertRaises((ValueError, OSError)):
            self.run_workflow(resume=True, runner_factory=factory)
        factory.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_t37_output_tamper_and_extra_artifacts_rejected(self):
        self.run_workflow()
        (self.output / "t37" / "markdown" / "p0.md").write_text("tampered")
        self.assert_rejected_unchanged()

    def test_t36_output_tamper_rejected(self):
        self.run_workflow()
        (self.output / "t36" / "review.md").write_text("tampered")
        self.assert_rejected_unchanged()

    def test_request_or_weights_change_rejected(self):
        self.run_workflow()
        self.payload["t37"]["variant_id"] = "contrast"
        self.write_manifest()
        self.assert_rejected_unchanged()
        self.payload["t37"]["variant_id"] = "raw"
        self.write_manifest()
        (self.root / "det" / "inference.pdiparams").write_bytes(b"changed weights")
        self.assert_rejected_unchanged()

    def test_bad_hash_profiles_and_runtime_fail_before_write(self):
        original = json.dumps(self.payload)
        mutations = [lambda: self.payload["t36"]["input_manifest"].update(sha256="0" * 64),
                     lambda: self.payload["t37"]["page_profiles"].pop("p1"),
                     lambda: self.payload["t36"]["runtime"].update(retry_limit=2),
                     lambda: self.payload["t37"].update(variant_id="inferred")]
        for mutate in mutations:
            self.payload = json.loads(original)
            mutate()
            self.write_manifest()
            with self.assertRaises(ValueError):
                self.run_workflow()
            self.assertFalse(self.output.exists())

    def test_t36_and_t37_publish_checkpoint_crash_gaps_fail_closed(self):
        real_write = workflow.batch._write
        def crash(path, payload):
            if path.name == "workflow-state.json" and "t36" in payload["stages"]:
                raise RuntimeError("crash after publish")
            return real_write(path, payload)
        with patch.object(workflow.batch, "_write", side_effect=crash):
            with self.assertRaises(RuntimeError):
                self.run_workflow()
        self.assertTrue((self.output / "t36" / "pilot-manifest.json").exists())
        self.assert_rejected_unchanged()
        # A second root exercises the same gap after the T37 atomic publish.
        self.output = self.root / "output2"
        def crash_t37(path, payload):
            if path.name == "workflow-state.json" and "t37" in payload["stages"]:
                raise RuntimeError("crash after T37 publish")
            return real_write(path, payload)
        with patch.object(workflow.batch, "_write", side_effect=crash_t37):
            with self.assertRaises(RuntimeError):
                self.run_workflow()
        self.assertTrue((self.output / "t37" / "run-manifest.json").exists())
        self.assert_rejected_unchanged()

    def test_interrupted_t36_before_aggregate_can_resume_its_page_checkpoints(self):
        real_write = workflow.batch._write
        def crash(path, payload):
            if path.name == "pilot-manifest.json":
                raise RuntimeError("crash before aggregate")
            return real_write(path, payload)
        with patch.object(workflow.batch, "_write", side_effect=crash):
            with self.assertRaises(RuntimeError):
                self.run_workflow()
        count = len(self.calls)
        report = self.run_workflow(resume=True, runner_factory=Mock(side_effect=AssertionError("no runtime")))
        self.assertEqual(report["status"], "completed_unreviewed")
        self.assertEqual(len(self.calls), count)


class OcrWorkflowJpegTests(unittest.TestCase):
    """Exercise the real stage orchestration with synthetic JPEGs and fake OCR."""

    def setUp(self):
        self.fixture = OcrWorkflowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def use_jpeg(self, suffix=".jpg", orientation=None, actual_format="JPEG"):
        from PIL import Image
        fixture = self.fixture
        source = fixture.root / f"scan0{suffix}"
        exif = Image.Exif()
        if orientation is not None:
            exif[274] = orientation
        Image.new("RGB", (16, 16), "white").save(source, format=actual_format, exif=exif)
        inputs = json.loads(fixture.inputs.read_text())
        inputs["pages"][0].update(path=source.name, sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        fixture.inputs.write_text(json.dumps(inputs))
        fixture.payload["t36"]["input_manifest"]["sha256"] = hashlib.sha256(fixture.inputs.read_bytes()).hexdigest()
        fixture.write_manifest()
        return source

    def test_jpeg_outputs_preserve_bytes_coordinates_and_resume(self):
        fixture = self.fixture
        source = self.use_jpeg()
        preview_factory = Mock(side_effect=AssertionError("no runtime"))
        self.assertEqual(fixture.run_workflow(apply=False, runner_factory=preview_factory)["status"], "preview")
        preview_factory.assert_not_called()
        self.assertFalse(fixture.output.exists())
        report = fixture.run_workflow()
        self.assertEqual(report["status"], "completed_unreviewed")
        raw = fixture.output / "t36/pages/p0/variants/raw.jpg"
        self.assertEqual(raw.read_bytes(), source.read_bytes())
        self.assertFalse(raw.with_suffix(".tif").exists())
        evidence = json.loads((fixture.output / "t37/evidence/p0.evidence.json").read_text())
        self.assertEqual(evidence["@type"], "OcrPageEvidence")
        self.assertEqual(evidence["source_image_hash"], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(evidence["source_page"]["original_page"]["source_dimensions"], {"width": 16, "height": 16})
        self.assertEqual(evidence["source_page"]["target"], "full_page")
        self.assertEqual(evidence["regions"][0]["geometry"]["bbox"], [1, 1, 14, 10])
        structure = json.loads((fixture.output / "t37/structure/p0.structure.json").read_text())
        self.assertEqual(structure["@type"], "DocumentStructure")
        self.assertIn("Synthetic report", (fixture.output / "t37/markdown/p0.md").read_text())
        before = fixture.snapshot()
        factory = Mock(side_effect=AssertionError("no runtime on resume"))
        fixture.run_workflow(resume=True, runner_factory=factory)
        factory.assert_not_called()
        self.assertEqual(fixture.snapshot(), before)
        self.assertFalse(report["machine_pass"])

    def test_jpeg_long_extension_and_explicit_orientation_one(self):
        source = self.use_jpeg(suffix=".JPEG", orientation=1)
        self.fixture.run_workflow()
        self.assertEqual((self.fixture.output / "t36/pages/p0/variants/raw.jpeg").read_bytes(), source.read_bytes())

    def test_invalid_jpeg_rejected_before_runtime_and_writes(self):
        fixture = self.fixture
        for orientation, actual_format in [(value, "JPEG") for value in range(2, 9)] + [(None, "PNG")]:
            with self.subTest(orientation=orientation, actual_format=actual_format):
                self.use_jpeg(orientation=orientation, actual_format=actual_format)
                factory = Mock()
                with self.assertRaises(ValueError):
                    fixture.run_workflow(runner_factory=factory)
                factory.assert_not_called()
                self.assertFalse(fixture.output.exists())

    def test_jpeg_source_tamper_fails_before_runtime(self):
        source = self.use_jpeg()
        source.write_bytes(source.read_bytes() + b"changed")
        factory = Mock()
        with self.assertRaisesRegex(ValueError, "SHA-256 input non valido"):
            self.fixture.run_workflow(runner_factory=factory)
        factory.assert_not_called()
        self.assertFalse(self.fixture.output.exists())

    def test_multiframe_file_with_jpeg_extension_is_rejected(self):
        from PIL import Image
        source = self.use_jpeg()
        Image.new("RGB", (16, 16)).save(source, format="TIFF", save_all=True,
                                      append_images=[Image.new("RGB", (16, 16))])
        factory = Mock()
        with self.assertRaisesRegex(ValueError, "JPEG reale a frame singolo"):
            self.fixture.run_workflow(runner_factory=factory)
        factory.assert_not_called()
        self.assertFalse(self.fixture.output.exists())

    def test_jpeg_rejected_by_tesseract_workflow_versions_before_runtime(self):
        self.use_jpeg()
        fixture = self.fixture
        for version in ("1.1", "1.2"):
            fixture.payload["schema_version"] = version
            fixture.payload["tesseract"] = {}
            if version == "1.2":
                fixture.payload["review"] = {}
            fixture.write_manifest()
            factory = Mock()
            with self.assertRaisesRegex(ValueError, "JPEG richiede v1.0 o v1.3"):
                fixture.run_workflow(runner_factory=factory)
            factory.assert_not_called()
            self.assertFalse(fixture.output.exists())


class OcrWorkflowV11Tests(unittest.TestCase):
    write_manifest = OcrWorkflowTests.write_manifest
    runner = OcrWorkflowTests.runner
    snapshot = OcrWorkflowTests.snapshot

    def setUp(self):
        OcrWorkflowTests.setUp(self)
        self.payload["schema_version"] = "1.1"
        bound = []
        self.tesseract_calls = []
        for index in range(2):
            raw = self.root / f"scan{index}.tif"
            sidecar = self.root / f"scan{index}.yaml"
            metadata = self.root / f"scan{index}.metadata.json"
            sidecar.write_text(json.dumps({"source_id": "archive", "document_id": f"doc{index}", "local_path": str(raw)}))
            metadata.write_text(json.dumps({"@type": "ProcessedDocumentMetadata", "source_id": "archive",
                "source_document_id": f"doc{index}", "document_class": "image_scan", "raw_file": raw.name,
                "sidecar_file": sidecar.name, "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "claim_eligible": False}))
            bound.append({"page_id": f"p{index}", "source_id": "archive", "source_document_id": f"doc{index}",
                          "sidecar": self.ref(sidecar), "metadata": self.ref(metadata)})
        self.payload["tesseract"] = {"root_dir": ".", "language": "ita", "tesseract_path": "fake-tesseract",
            "page_segmentation_mode": "6", "engine_mode": "1", "dpi": "300",
            "preprocess_before_ocr": False, "enable_region_ocr": False, "pages": bound}
        self.write_manifest()

    def ref(self, path):
        return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def tesseract(self, command):
        self.tesseract_calls.append(command)
        text = "Testo valido"
        if command[-1] == "tsv":
            text = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                    "1\t1\t0\t0\t0\t0\t0\t0\t16\t16\t-1\t\n"
                    "5\t1\t1\t1\t1\t1\t0\t0\t5\t5\t92\tTesto\n"
                    "5\t1\t1\t1\t1\t2\t6\t0\t5\t5\t91\tvalido\n")
        return subprocess.CompletedProcess(command, 0, stdout=text, stderr="")

    def run_workflow(self, **kwargs):
        return OcrWorkflowTests.run_workflow(self, **({"command_runner": self.tesseract} | kwargs))

    def test_preview_validates_all_bindings_without_runtime_or_writes(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        factory, command = Mock(side_effect=AssertionError("no Paddle")), Mock(side_effect=AssertionError("no Tesseract"))
        report = self.run_workflow(apply=False, runner_factory=factory, command_runner=command)
        self.assertEqual(report["schema_version"], "1.1")
        self.assertEqual(report["tesseract"]["preflight"]["summary"]["ready"], 2)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        factory.assert_not_called()
        command.assert_not_called()

    def test_single_apply_and_complete_resume_preserve_all_artifacts(self):
        report = self.run_workflow()
        self.assertEqual(report["status"], "completed_unreviewed")
        self.assertEqual(len(self.calls), 10)
        self.assertTrue(self.tesseract_calls)
        self.assertEqual(report["tesseract"]["summary"]["success"], 2)
        self.assertTrue((self.output / "t37/markdown/p0.md").is_file())
        text = json.loads((self.output / "tesseract/texts/archive/doc0.text.json").read_text())
        self.assertTrue(text["diagnostic_only"])
        self.assertEqual(text["review_status"], "unreviewed")
        diagnostic_manifest = json.loads((self.output / "tesseract/page-batch-manifest.json").read_text())
        self.assertEqual(diagnostic_manifest["t36_manifest"]["sha256"],
                         hashlib.sha256((self.output / "t36/pilot-manifest.json").read_bytes()).hexdigest())
        before = self.snapshot()
        times = {p: p.stat().st_mtime_ns for p in self.output.rglob("*") if p.is_file()}
        factory, command = Mock(side_effect=AssertionError("no Paddle")), Mock(side_effect=AssertionError("no Tesseract"))
        report = self.run_workflow(resume=True, runner_factory=factory, command_runner=command)
        self.assertEqual(report["status"], "completed_unreviewed")
        self.assertTrue(report["tesseract"]["reused"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(times, {p: p.stat().st_mtime_ns for p in times})
        factory.assert_not_called()
        command.assert_not_called()

    def test_t36_partial_blocks_both_later_stages(self):
        def failure(path, language):
            if "p1" in path.parts:
                raise RuntimeError("synthetic Paddle failure")
            return self.runner(path, language)
        command = Mock(side_effect=AssertionError("no Tesseract"))
        report = self.run_workflow(runner_factory=lambda: failure, command_runner=command)
        self.assertEqual(report["status"], "partial_unreviewed")
        self.assertEqual(report["blocked_stages"], ["t37", "tesseract"])
        self.assertFalse((self.output / "t37").exists())
        self.assertFalse((self.output / "tesseract").exists())
        command.assert_not_called()

    def test_invalid_bindings_abort_before_either_engine_or_writes(self):
        original = json.dumps(self.payload)
        cases = ("missing_page", "duplicate_identity", "metadata_hash", "sidecar_hash", "identity", "class", "raw_path",
                 "sidecar_path", "local_path", "metadata_duplicate", "sidecar_duplicate", "input_duplicate",
                 "raw_hash", "output_alias", "bad_option", "root_file")
        for case in cases:
            with self.subTest(case=case):
                self.payload = json.loads(original)
                pages = self.payload["tesseract"]["pages"]
                metadata = self.root / pages[0]["metadata"]["path"]
                sidecar = self.root / pages[0]["sidecar"]["path"]
                bound_files = [self.root / page[role]["path"] for page in pages for role in ("metadata", "sidecar")]
                saved = {p: p.read_bytes() for p in (*bound_files, self.inputs)}
                if case == "missing_page": pages.pop()
                elif case == "duplicate_identity": pages[1]["source_document_id"] = pages[0]["source_document_id"]
                elif case == "metadata_hash": pages[0]["metadata"]["sha256"] = "0" * 64
                elif case == "sidecar_hash": pages[0]["sidecar"]["sha256"] = "0" * 64
                elif case == "identity": pages[0]["source_id"] = "other"
                elif case in ("class", "raw_path", "sidecar_path"):
                    value = json.loads(metadata.read_text())
                    value[{"class": "document_class", "raw_path": "raw_file", "sidecar_path": "sidecar_file"}[case]] = "other"
                    metadata.write_text(json.dumps(value))
                    pages[0]["metadata"] = self.ref(metadata)
                elif case == "local_path":
                    value = json.loads(sidecar.read_text())
                    value["local_path"] = str(self.root / "other.tif")
                    sidecar.write_text(json.dumps(value))
                    pages[0]["sidecar"] = self.ref(sidecar)
                elif case == "metadata_duplicate":
                    metadata.write_text(metadata.read_text()[:-1] + ', "source_id": "archive"}')
                    pages[0]["metadata"] = self.ref(metadata)
                elif case == "sidecar_duplicate":
                    sidecar.write_text('source_id: archive\nsource_id: archive\ndocument_id: doc0\nlocal_path: ' + str(self.root / "scan0.tif"))
                    pages[0]["sidecar"] = self.ref(sidecar)
                elif case == "input_duplicate":
                    self.inputs.write_text(self.inputs.read_text()[:-1] + ', "schema_version": "1.0"}')
                    self.payload["t36"]["input_manifest"] = self.ref(self.inputs)
                elif case == "raw_hash":
                    value = json.loads(self.inputs.read_text())
                    value["pages"][0]["sha256"] = "0" * 64
                    self.inputs.write_text(json.dumps(value))
                    self.payload["t36"]["input_manifest"] = self.ref(self.inputs)
                elif case == "output_alias":
                    # Distinct identities alias the same target on Windows.
                    pages[1]["source_id"] = "archive."
                    pages[1]["source_document_id"] = "doc0"
                    for role, key in (("metadata", "source_document_id"), ("sidecar", "document_id")):
                        path = self.root / pages[1][role]["path"]
                        value = json.loads(path.read_text())
                        value["source_id"] = "archive."
                        value[key] = "doc0"
                        path.write_text(json.dumps(value))
                        pages[1][role] = self.ref(path)
                elif case == "bad_option": self.payload["tesseract"]["preprocess_before_ocr"] = "false"
                elif case == "root_file": self.payload["tesseract"]["root_dir"] = "inputs.json"
                self.write_manifest()
                factory = Mock(side_effect=AssertionError("preflight reached Paddle"))
                command = Mock(side_effect=AssertionError("preflight reached Tesseract"))
                try:
                    with self.assertRaises((ValueError, OSError)):
                        self.run_workflow(runner_factory=factory, command_runner=command)
                    factory.assert_not_called()
                    command.assert_not_called()
                    self.assertFalse(self.output.exists())
                finally:
                    for path, data in saved.items(): path.write_bytes(data)

    def test_tesseract_runtime_partial_is_isolated_and_resume_is_immutable(self):
        def fail_first(command):
            if "scan0.tif" in str(command):
                raise RuntimeError("synthetic Tesseract failure")
            return self.tesseract(command)
        report = self.run_workflow(command_runner=fail_first)
        self.assertEqual(report["status"], "partial_unreviewed")
        self.assertEqual(report["tesseract"]["summary"], {"ready": 0, "success": 1, "error": 1})
        self.assertTrue((self.output / "t37/markdown/p0.md").is_file())
        self.assertFalse((self.output / "tesseract/texts/archive/doc0.text.json").exists())
        self.assertTrue((self.output / "tesseract/texts/archive/doc1.text.json").is_file())
        before = self.snapshot()
        factory, command = Mock(side_effect=AssertionError("no Paddle")), Mock(side_effect=AssertionError("no Tesseract"))
        report = self.run_workflow(resume=True, runner_factory=factory, command_runner=command)
        self.assertEqual(report["status"], "partial_unreviewed")
        self.assertTrue(report["tesseract"]["reused"])
        self.assertEqual(before, self.snapshot())
        factory.assert_not_called()
        command.assert_not_called()

    def test_tesseract_crash_gap_and_tampered_report_fail_closed(self):
        real_write = workflow.batch._write
        def crash(path, payload):
            if path.name == "workflow-state.json" and "tesseract" in payload["stages"]:
                raise RuntimeError("crash after Tesseract publish")
            return real_write(path, payload)
        with patch.object(workflow.batch, "_write", side_effect=crash):
            with self.assertRaises(RuntimeError): self.run_workflow()
        self.assertTrue((self.output / "tesseract/report.json").exists())
        OcrWorkflowTests.assert_rejected_unchanged(self)
        self.output = self.root / "output2"
        self.run_workflow()
        (self.output / "tesseract/report.json").write_text("{}")
        OcrWorkflowTests.assert_rejected_unchanged(self)


class OcrWorkflowV12Tests(unittest.TestCase):
    write_manifest = OcrWorkflowTests.write_manifest
    runner = OcrWorkflowTests.runner
    snapshot = OcrWorkflowTests.snapshot
    ref = OcrWorkflowV11Tests.ref
    tesseract = OcrWorkflowV11Tests.tesseract
    run_workflow = OcrWorkflowV11Tests.run_workflow

    def setUp(self):
        OcrWorkflowV11Tests.setUp(self)
        self.payload["schema_version"] = "1.2"
        self.payload["t36"]["language"] = "de"
        self.payload["tesseract"]["language"] = "deu"
        lexicon = self.root / "lexicon.json"
        lexicon.write_text(json.dumps({"@type": "OcrLanguageLexicon", "schema_version": "1.0",
            "@id": "fixture:de", "version": "1", "language": "deu",
            "entries": [{"term": "Synthetic", "category": "word"}]}))
        glossary = self.root / "glossary.json"
        glossary.write_text(json.dumps({"@type": "MilitaryGlossary", "@id": "fixture:empty-glossary",
            "version": "1", "entries": []}))
        self.payload["review"] = {"lexicons": {f"p{i}": self.ref(lexicon) for i in range(2)},
            "glossaries": {f"p{i}": self.ref(glossary) for i in range(2)}}
        self.write_manifest()

    def test_preview_apply_resume_without_repeating_inference(self):
        factory, command = Mock(side_effect=AssertionError("no Paddle")), Mock(side_effect=AssertionError("no Tesseract"))
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        preview = self.run_workflow(apply=False, runner_factory=factory, command_runner=command)
        self.assertEqual(preview["review"]["status"], "preview")
        self.assertFalse(preview["writes_performed"])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        factory.assert_not_called()
        command.assert_not_called()
        report = self.run_workflow()
        self.assertEqual(report["status"], "awaiting_review")
        self.assertEqual(report["review"]["status"], "template_incomplete")
        self.assertEqual(len(self.calls), 10)
        package = workflow._read(self.output / "review/package-manifest.json")
        self.assertEqual(package["review_status"], "unreviewed")
        self.assertFalse(package["human_review_request_allowed"])
        for page in package["pages"]:
            for artifact in [*page["review_inputs"].values(), *page["outputs"], *page["inputs"].values()]:
                self.assertEqual(artifact["sha256"], hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest())
            ledger = workflow._read(Path(page["review_inputs"]["ledger"]["path"]))
            self.assertEqual(ledger["template_status"], "incomplete")
            self.assertTrue(all(not row["text"] and not row["outcome"] and not row["observer"] for row in ledger["observations"]))
            dispositions = workflow._read(Path(page["review_inputs"]["dispositions"]["path"]))
            self.assertEqual(dispositions["source_lexicon_review_digest"], "sha256:" + page["review_inputs"]["lexicon_review"]["sha256"])
        before, counts = self.snapshot(), (len(self.calls), len(self.tesseract_calls))
        times = {p: p.stat().st_mtime_ns for p in self.output.rglob("*") if p.is_file()}
        report = self.run_workflow(resume=True, runner_factory=factory, command_runner=command)
        self.assertEqual(report["status"], "awaiting_review")
        self.assertTrue(report["review"]["reused"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(times, {p: p.stat().st_mtime_ns for p in times})
        self.assertEqual(counts, (len(self.calls), len(self.tesseract_calls)))
        factory.assert_not_called()
        command.assert_not_called()

    def test_invalid_review_preflight_rejects_before_runtime_or_write(self):
        original = json.dumps(self.payload)
        lexicon_path = self.root / "lexicon.json"
        resource = lexicon_path.read_bytes()
        for case in ("missing", "extra", "hash", "path", "resource", "entries", "language", "duplicate", "variant", "preprocess", "regions", "engine_language", "glossary", "missing_glossary"):
            with self.subTest(case=case):
                self.payload = json.loads(original)
                mapping = self.payload["review"]["lexicons"]
                if case == "missing": mapping.pop("p1")
                elif case == "extra": mapping["other"] = mapping["p0"]
                elif case == "hash": mapping["p0"]["sha256"] = "0" * 64
                elif case == "path": mapping["p0"]["path"] = "absent.json"
                elif case in ("resource", "entries", "language"):
                    data = json.loads(resource)
                    data[{"resource": "@type", "entries": "entries", "language": "language"}[case]] = {
                        "resource": "other", "entries": [], "language": "eng"}[case]
                    lexicon_path.write_text(json.dumps(data))
                    self.payload["review"]["lexicons"] = {f"p{i}": self.ref(lexicon_path) for i in range(2)}
                elif case == "duplicate":
                    lexicon_path.write_text(resource.decode()[:-1] + ', "language":"deu"}')
                    self.payload["review"]["lexicons"] = {f"p{i}": self.ref(lexicon_path) for i in range(2)}
                elif case == "variant": self.payload["t37"]["variant_id"] = "grayscale"
                elif case == "preprocess": self.payload["tesseract"]["preprocess_before_ocr"] = True
                elif case == "regions": self.payload["tesseract"]["enable_region_ocr"] = True
                elif case == "engine_language": self.payload["tesseract"]["language"] = "ita"
                elif case == "glossary": self.payload["review"]["glossaries"] = {}
                elif case == "missing_glossary": self.payload["review"].pop("glossaries")
                self.write_manifest()
                factory, command = Mock(), Mock()
                try:
                    with self.assertRaises((ValueError, OSError)):
                        self.run_workflow(runner_factory=factory, command_runner=command)
                    factory.assert_not_called()
                    command.assert_not_called()
                    self.assertFalse(self.output.exists())
                finally:
                    lexicon_path.write_bytes(resource)

    def test_required_glossaries_are_bound_in_package(self):
        path = self.root / "glossary.json"
        path.write_text(json.dumps({"@type": "MilitaryGlossary", "@id": "fixture:military", "version": "1",
            "entries": [{"@id": "fixture:unit", "term": "Unit", "abbreviations": ["U."]}]}))
        self.payload["review"]["glossaries"] = {f"p{i}": self.ref(path) for i in range(2)}
        self.write_manifest()
        self.run_workflow()
        package = workflow._read(self.output / "review/package-manifest.json")
        self.assertTrue(all(page["inputs"]["glossary"]["sha256"] == self.ref(path)["sha256"] for page in package["pages"]))
        path.write_text("{}")
        OcrWorkflowTests.assert_rejected_unchanged(self)

    def test_tesseract_partial_blocks_review_and_resume_keeps_failure(self):
        report = self.run_workflow(command_runner=lambda command: (_ for _ in ()).throw(RuntimeError("failure")))
        self.assertEqual(report["status"], "partial_unreviewed")
        self.assertEqual(report["blocked_stages"], ["tesseract-evidence", "review"])
        self.assertFalse((self.output / "tesseract-evidence").exists())
        self.assertFalse((self.output / "review").exists())
        before = self.snapshot()
        self.run_workflow(resume=True, runner_factory=Mock(side_effect=AssertionError()), command_runner=Mock(side_effect=AssertionError()))
        self.assertEqual(before, self.snapshot())

    def test_review_checkpoint_gap_and_tampering_fail_closed(self):
        real_write = workflow.batch._write
        def crash(path, payload):
            if path.name == "workflow-state.json" and "review" in payload["stages"]:
                raise RuntimeError("crash after review publish")
            return real_write(path, payload)
        with patch.object(workflow.batch, "_write", side_effect=crash), self.assertRaises(RuntimeError):
            self.run_workflow()
        OcrWorkflowTests.assert_rejected_unchanged(self)
        self.output = self.root / "output2"
        self.run_workflow()
        (self.output / "review/package-manifest.json").write_text("{}")
        OcrWorkflowTests.assert_rejected_unchanged(self)

    def test_resume_finishes_package_from_checkpointed_evidence_without_ocr(self):
        with patch.object(workflow.review_package, "build_ocr_review_package", side_effect=RuntimeError("interrupted")):
            with self.assertRaises(RuntimeError): self.run_workflow()
        self.assertTrue((self.output / "tesseract-evidence/run-manifest.json").exists())
        self.assertFalse((self.output / "review").exists())
        report = self.run_workflow(resume=True, runner_factory=Mock(side_effect=AssertionError()), command_runner=Mock(side_effect=AssertionError()))
        self.assertEqual(report["status"], "awaiting_review")

    def test_changed_checkpoint_dependencies_reject_before_runtime(self):
        self.run_workflow()
        path = self.output / "workflow-state.json"
        original = path.read_bytes()
        for name in ("tesseract-evidence", "review"):
            with self.subTest(stage=name):
                state = json.loads(original)
                state["stages"][name]["source_bindings"]["t36/pilot-manifest.json"] = "0" * 64
                path.write_text(json.dumps(state))
                OcrWorkflowTests.assert_rejected_unchanged(self)
                path.write_bytes(original)

    def test_evidence_checkpoint_gap_rejects_without_overwrite(self):
        real_write = workflow.batch._write
        def crash(path, payload):
            if path.name == "workflow-state.json" and "tesseract-evidence" in payload["stages"]:
                raise RuntimeError("crash after evidence publish")
            return real_write(path, payload)
        with patch.object(workflow.batch, "_write", side_effect=crash), self.assertRaises(RuntimeError):
            self.run_workflow()
        self.assertTrue((self.output / "tesseract-evidence/run-manifest.json").exists())
        self.assertFalse((self.output / "review").exists())
        OcrWorkflowTests.assert_rejected_unchanged(self)

    def test_t36_partial_blocks_review_without_tesseract(self):
        def failure(path, language):
            if "p1" in path.parts:
                raise RuntimeError("failure")
            return self.runner(path, language)
        command = Mock(side_effect=AssertionError("no Tesseract"))
        report = self.run_workflow(runner_factory=lambda: failure, command_runner=command)
        self.assertEqual(report["blocked_stages"], ["t37", "tesseract", "tesseract-evidence", "review"])
        self.assertFalse((self.output / "review").exists())
        command.assert_not_called()


class OcrWorkflowV13Tests(unittest.TestCase):
    write_manifest = OcrWorkflowTests.write_manifest
    runner = OcrWorkflowTests.runner
    snapshot = OcrWorkflowTests.snapshot
    ref = OcrWorkflowV11Tests.ref
    tesseract = OcrWorkflowV11Tests.tesseract
    run_workflow = OcrWorkflowV11Tests.run_workflow
    test_preview_apply_resume_without_repeating_inference = OcrWorkflowV12Tests.test_preview_apply_resume_without_repeating_inference
    test_invalid_review_preflight_rejects_before_runtime_or_write = OcrWorkflowV12Tests.test_invalid_review_preflight_rejects_before_runtime_or_write

    def setUp(self):
        OcrWorkflowV12Tests.setUp(self)
        self.payload["schema_version"] = "1.3"
        for index, suffix in ((0, ".jpg"), (1, ".JPEG")):
            self.use_source(index, suffix=suffix)

    def use_source(self, index=0, *, suffix=".jpg", orientation=None, actual_format="JPEG", corrupt=False):
        from PIL import Image
        source = self.root / f"scan{index}{suffix}"
        options = {}
        if orientation is not None:
            exif = Image.Exif()
            exif[274] = orientation
            options["exif"] = exif
        Image.new("RGB", (16, 16), "white").save(source, format=actual_format, **options)
        if corrupt:
            source.write_bytes(source.read_bytes()[:70])
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        inputs = json.loads(self.inputs.read_text())
        inputs["pages"][index].update(path=source.name, sha256=digest)
        self.inputs.write_text(json.dumps(inputs))
        self.payload["t36"]["input_manifest"] = self.ref(self.inputs)
        binding = self.payload["tesseract"]["pages"][index]
        for role in ("sidecar", "metadata"):
            path = self.root / binding[role]["path"]
            payload = json.loads(path.read_text())
            if role == "sidecar": payload["local_path"] = str(source)
            else: payload.update(raw_file=source.name, sha256=digest)
            path.write_text(json.dumps(payload))
            binding[role] = self.ref(path)
        self.write_manifest()
        return source

    def test_native_contract_raw_bytes_coordinates_and_truthful_review_locator(self):
        report = self.run_workflow()
        self.assertEqual(report["schema_version"], "1.3")
        self.assertEqual(report["status"], "awaiting_review")
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])
        manifest = workflow._read(self.output / "tesseract/page-batch-manifest.json")
        self.assertEqual(manifest["schema_version"], "1.1")
        self.assertTrue(all("raw_image" in page and "raw_tiff" not in page for page in manifest["pages"]))
        package = workflow._read(self.output / "review/package-manifest.json")
        for index, suffix in ((0, ".jpg"), (1, ".jpeg")):
            source = self.root / f"scan{index}{'.JPEG' if index else suffix}"
            raw = self.output / f"t36/pages/p{index}/variants/raw{suffix}"
            self.assertEqual(source.read_bytes(), raw.read_bytes())
            text = workflow._read(self.output / f"tesseract/texts/archive/doc{index}.text.json")
            self.assertEqual(text["ocr_retry_policy"], "raw_pixels_only")
            self.assertFalse(text["ocr_preprocessing_enabled"])
            evidence = workflow._read(self.output / f"tesseract-evidence/evidence/p{index}.json")
            self.assertEqual(evidence["source_image_hash"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(evidence["source_document_id"], f"doc{index}")
            self.assertEqual(evidence["source_page"]["original_page"]["source_dimensions"], {"width": 16, "height": 16})
        self.assertTrue(all(page["source_media_type"] == "image/jpeg" for page in package["pages"]))
        self.assertTrue(all(page["frame_locator"]["basis"] == "verified_single_frame_jpeg" for page in package["pages"]))

    def test_invalid_native_source_rejects_before_runtime_and_writes(self):
        for options in ({"orientation": 6}, {"actual_format": "PNG"}, {"actual_format": "TIFF"}, {"corrupt": True}):
            with self.subTest(options=options):
                self.use_source(**options)
                factory, command = Mock(), Mock()
                with self.assertRaises((ValueError, OSError)):
                    self.run_workflow(runner_factory=factory, command_runner=command)
                factory.assert_not_called()
                command.assert_not_called()
                self.assertFalse(self.output.exists())

    def test_mutated_request_or_bound_source_is_never_reused(self):
        self.run_workflow()
        original = json.dumps(self.payload)
        self.payload["tesseract"]["page_segmentation_mode"] = "3"
        self.write_manifest()
        OcrWorkflowTests.assert_rejected_unchanged(self)
        self.payload = json.loads(original)
        self.write_manifest()
        self.use_source(orientation=1)  # Valid native image with a changed hash.
        OcrWorkflowTests.assert_rejected_unchanged(self)

    def test_native_v13_mixed_tiff_and_jpeg_keeps_media_and_raw_contract(self):
        self.use_source(index=1, suffix=".tif", actual_format="TIFF")
        report = self.run_workflow()
        self.assertEqual(report["status"], "awaiting_review")
        package = workflow._read(self.output / "review/package-manifest.json")
        self.assertEqual([page["source_media_type"] for page in package["pages"]], ["image/jpeg", "image/tiff"])
        self.assertEqual(workflow._read(self.output / "tesseract/page-batch-manifest.json")["schema_version"], "1.1")
    def test_insufficient_raw_result_blocks_evidence_and_review_without_reinference(self):
        def low_quality(command):
            result = self.tesseract(command)
            if command[-1] == "tsv":
                result.stdout = result.stdout.replace("92\t", "1\t").replace("91\t", "2\t")
            return result
        with patch("caduti_fonti_report.document_analysis.ocr_tesseract.preprocess_dark_foreground_for_ocr",
                   side_effect=AssertionError("hidden preprocessing")):
            report = self.run_workflow(command_runner=low_quality)
        self.assertEqual(report["status"], "partial_unreviewed")
        self.assertEqual(report["block_reason"], "tesseract_diagnostic_not_comparable")
        self.assertEqual(report["blocked_page_ids"], ["p0", "p1"])
        self.assertFalse((self.output / "tesseract-evidence").exists())
        self.assertFalse((self.output / "review").exists())
        text = workflow._read(self.output / "tesseract/texts/archive/doc0.text.json")
        self.assertEqual(text["ocr_quality_gate_status"], "diagnostic_insufficient")
        self.assertFalse(text["ocr_run_provenance"]["adapter_ready"])
        before = self.snapshot()
        factory, command = Mock(side_effect=AssertionError("Paddle repeated")), Mock(side_effect=AssertionError("Tesseract repeated"))
        resumed = self.run_workflow(resume=True, runner_factory=factory, command_runner=command)
        self.assertEqual(resumed["status"], "partial_unreviewed")
        self.assertEqual(self.snapshot(), before)
        factory.assert_not_called()
        command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
