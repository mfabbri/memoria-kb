from __future__ import annotations

import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from PIL import Image

from caduti_fonti_report.document_analysis.ocr_evidence_comparison import compare_ocr_page_evidence
from caduti_fonti_report.document_analysis.ocr_tesseract import _layout_payload, _parse_tesseract_tsv, _run_provenance
from caduti_fonti_report.document_analysis import ocr_tesseract_from_t36 as bridge
from caduti_fonti_report.document_analysis.ocr_tesseract_page_batch import run_tesseract_page_batch
from caduti_fonti_report.memoria_cli import main


class TesseractFromT36Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "source.tif"
        Image.new("L", (300, 160), 255).save(self.image)
        self.raw = self.root / "raw.tif"
        self.raw.write_bytes(self.image.read_bytes())
        digest = self.digest(self.image)
        self.primary = {
            "@type": "OcrPageEvidence", "schema_version": "1.0", "page_id": "p1",
            "source_image_hash": digest, "transform_id": "t36:raw", "engine": "paddle-ocr-v5",
            "language": "deu", "model": {"name": "synthetic"},
            "image_transform": {"id": "t36:raw", "parameters": {"operation": "byte_copy"}},
            "source_page": {"variant_id": "raw", "target": "full_page", "tile_id": None,
                "original_page": {"page_id": "p1", "source_file": str(self.image),
                    "source_image_hash": digest, "source_dimensions": {"width": 300, "height": 160}}},
            "regions": [{"region_id": "pp-1", "text": "REPORT", "geometry": {"bbox": [10, 10, 100, 30]}}]}
        self.page = {"page_id": "p1", "source": {"path": str(self.image), "sha256": digest,
            "image_dimensions": {"width": 300, "height": 160}}, "variants": [{"variant_id": "raw",
                "path": "raw.tif", "sha256": digest, "transform": copy.deepcopy(self.primary["image_transform"]),
                "ocr_outputs": [{"target": "full_page", "artifact": "raw.tif", "artifact_sha256": digest,
                    "source_bbox": [0, 0, 300, 160], "structured_evidence": self.primary}]}]}
        self.manifest_data = {"@type": "OcrTransformPilot", "schema_version": "1.0", "language": "deu",
            "review_status": "unreviewed", "accuracy_claim": "none_without_human_reference", "pages": [self.page]}
        tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
               "1\t1\t0\t0\t0\t0\t0\t0\t300\t160\t-1\t\n"
               "5\t1\t1\t1\t1\t1\t10\t10\t90\t20\t88\tREPORT\n")
        quality = _layout_payload(records=_parse_tesseract_tsv(tsv), source_document_id="synthetic")
        probe = {"status": "probed", "frame_count": 1, "frames": [{"frame_index": 0, "width": 300, "height": 160}]}
        run = _run_provenance(source_document_id="synthetic", source_sha256_before=digest, source_sha256_after=digest,
            source_probe=probe, language="deu", tesseract_path="tesseract", requested_psm="6", engine_mode="", dpi="",
            selected={"input_probe": probe, "quality": quality, "preprocessing_report": None, "input_kind": "original",
                "input_sha256": digest, "page_segmentation_mode": "6", "attempts": [{"candidate_id": "original-psm-6",
                "input": "original", "page_segmentation_mode": "6", "status": "selected", "quality_score": 88,
                "word_count": 1, "line_count": 1, "input_sha256": digest}]})
        self.payload = {"@type": "ProcessedDocumentText", "source_document_id": "synthetic", "text": "REPORT",
            "text_sha256": hashlib.sha256(b"REPORT").hexdigest(), "transcription_method": "external_ocr_unreviewed",
            "ocr_engine": "tesseract", "ocr_quality_gate_status": "accepted", "ocr_language": "deu",
            "ocr_effective_page_segmentation_mode": "6", "ocr_run_provenance": run, **quality}
        self.manifest = self.root / "pilot-manifest.json"
        self.text = self.root / "processed-text.json"
        self.output = self.root / "output"
        self.sync()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def sync(self):
        self.manifest.write_text(json.dumps(self.manifest_data), encoding="utf-8")
        self.text.write_text(json.dumps(self.payload), encoding="utf-8")

    def run_bridge(self, **overrides):
        args = dict(manifest_path=self.manifest, processed_text={"p1": self.text}, output_dir=self.output)
        args.update(overrides)
        return bridge.export_tesseract_from_t36(**args)

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def use_jpeg(self, orientation=None):
        old_image, old_raw, old_hash = self.image, self.raw, self.digest(self.image)
        self.image, self.raw = self.root / "source.jpg", self.root / "raw.jpg"
        options = {}
        if orientation is not None:
            exif = Image.Exif()
            exif[274] = orientation
            options["exif"] = exif
        Image.new("RGB", (300, 160), "white").save(self.image, **options)
        self.raw.write_bytes(self.image.read_bytes())
        for attr in ("manifest_data", "payload"):
            serialized = json.dumps(getattr(self, attr))
            for old, new in ((old_hash, self.digest(self.image)), (str(old_image), str(self.image)),
                             (old_raw.name, self.raw.name)):
                # JSON escaping also works for Windows paths.
                serialized = serialized.replace(json.dumps(old)[1:-1], json.dumps(new)[1:-1])
            setattr(self, attr, json.loads(serialized))
        self.sync()

    def test_native_jpeg_batch_to_evidence_without_intermediate_tiff(self):
        self.use_jpeg(orientation=1)
        self.manifest_data["pages"][0]["status"] = "completed"
        self.sync()
        sidecar, metadata, batch = (self.root / name for name in ("source.yaml", "metadata.json", "batch.json"))
        sidecar.write_text(json.dumps({"source_id": "archive", "document_id": "synthetic",
                                      "local_path": str(self.image)}))
        metadata.write_text(json.dumps({"@type": "ProcessedDocumentMetadata", "source_id": "archive",
            "source_document_id": "synthetic", "document_class": "image_scan", "raw_file": self.image.name,
            "sidecar_file": sidecar.name, "sha256": self.digest(self.image), "claim_eligible": False}))
        def ref(path):
            return {"path": path.name, "sha256": self.digest(path)}
        batch.write_text(json.dumps({"@type": "TesseractPageBatchManifest", "schema_version": "1.1",
            "root_dir": ".", "t36_manifest": ref(self.manifest), "pages": [{"page_id": "p1",
            "source_id": "archive", "source_document_id": "synthetic", "raw_image": ref(self.image),
            "metadata": ref(metadata), "sidecar": ref(sidecar)}]}))
        commands = []
        def runner(command):
            commands.append(command)
            text = "REPORT VALID"
            if command[-1] == "tsv":
                text = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t300\t160\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t10\t10\t90\t20\t88\tREPORT\n"
                        "5\t1\t1\t1\t1\t2\t110\t10\t90\t20\t88\tVALID\n")
            return subprocess.CompletedProcess(command, 0, stdout=text, stderr="")
        tiffs_before = set(self.root.rglob("*.tif"))
        originals = self.image.read_bytes(), self.raw.read_bytes()
        with patch("caduti_fonti_report.document_analysis.ocr_tesseract.preprocess_dark_foreground_for_ocr",
                   side_effect=AssertionError("hidden preprocessing")):
            batch_report = run_tesseract_page_batch(manifest_path=batch, output_dir=self.root / "texts",
                report_path=self.root / "batch-report.json", language="deu", apply=True, command_runner=runner)
        self.assertEqual(batch_report["summary"]["success"], 1)
        processed = Path(batch_report["pages"][0]["output_path"])
        report = self.run_bridge(processed_text={"p1": processed}, apply=True)
        evidence = json.loads(Path(report["pages"][0]["evidence"]["path"]).read_text())
        self.assertEqual(evidence["@type"], "OcrPageEvidence")
        self.assertEqual(evidence["source_image_hash"], self.digest(self.image))
        self.assertEqual(evidence["regions"][0]["geometry"]["bbox"], [10, 10, 200, 30])
        self.assertFalse(evidence["machine_pass"])
        self.assertFalse(evidence["auto_validation_enabled"])
        self.assertEqual({command[1] for command in commands}, {str(self.image)})
        self.assertEqual(set(self.root.rglob("*.tif")), tiffs_before)
        self.assertEqual((self.image.read_bytes(), self.raw.read_bytes()), originals)

    def test_jpeg_orientation_and_mislabeled_raw_fail_before_output(self):
        for orientation in (6, 1):
            with self.subTest(orientation=orientation):
                self.use_jpeg(orientation)
                if orientation == 1:
                    raw = self.manifest_data["pages"][0]["variants"][0]
                    raw["path"] = "raw.tif"
                    (self.root / "raw.tif").write_bytes(self.raw.read_bytes())
                    raw["ocr_outputs"][0]["artifact"] = "raw.tif"
                    self.sync()
                with self.assertRaises(ValueError):
                    self.run_bridge(apply=True)
                self.assertFalse(self.output.exists())

    def test_preview_is_read_only_and_deterministic(self):
        before = self.snapshot()
        with patch.object(bridge.tempfile, "TemporaryDirectory", side_effect=AssertionError("preview wrote")):
            first = self.run_bridge()
            self.assertEqual(first, self.run_bridge())
        self.assertEqual(first["operation_status"], "preview")
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.output.exists())

    def test_apply_preserves_provenance_hashes_final_paths_and_comparison(self):
        before = self.snapshot()
        report = self.run_bridge(apply=True)
        self.assertEqual(report, json.loads((self.output / "run-manifest.json").read_text()))
        entry = report["pages"][0]
        self.assertEqual(report["source_manifest"]["sha256"], self.digest(self.manifest))
        for role in ("source_image", "variant_image", "processed_text", "primary_evidence", "evidence"):
            artifact = entry[role]
            self.assertEqual(artifact["sha256"], self.digest(Path(artifact["path"])))
        primary = json.loads(Path(entry["primary_evidence"]["path"]).read_text())
        evidence = json.loads(Path(entry["evidence"]["path"]).read_text())
        self.assertEqual(primary, self.primary)
        self.assertEqual(evidence["ocr_run_provenance"], self.payload["ocr_run_provenance"])
        self.assertEqual(evidence["source_page"], self.primary["source_page"])
        self.assertEqual(len(compare_ocr_page_evidence(left=primary, right=evidence)["agreements"]), 1)
        for obj in (report, evidence):
            self.assertFalse(obj["machine_pass"])
            self.assertFalse(obj["auto_validation_enabled"])
            self.assertEqual(obj["review_status"], "unreviewed")
        self.assertNotIn(".ocr-tesseract-from-t36-", json.dumps(report))
        for path, data in before.items():
            self.assertEqual((self.root / path).read_bytes(), data)
        self.assertFalse(list(self.root.glob(".ocr-tesseract-from-t36-*")))

    def test_map_must_cover_exactly_every_page(self):
        for mapping in ({}, {"wrong": self.text}, {"p1": self.text, "extra": self.text}):
            with self.subTest(mapping=mapping), self.assertRaisesRegex(ValueError, "esattamente"):
                self.run_bridge(processed_text=mapping, apply=True)
        self.assertFalse(self.output.exists())

    def test_manifest_identity_raw_transform_and_anchor_fail_closed(self):
        original = copy.deepcopy(self.manifest_data)
        mutations = [
            lambda: self.manifest_data.update(schema_version="2.0"),
            lambda: self.manifest_data.update(review_status="reviewed"),
            lambda: self.manifest_data["pages"].append(copy.deepcopy(self.manifest_data["pages"][0])),
            lambda: self.manifest_data["pages"][0]["variants"].append(copy.deepcopy(self.manifest_data["pages"][0]["variants"][0])),
            lambda: self.manifest_data["pages"][0]["source"].update(sha256="b" * 64),
            lambda: self.manifest_data["pages"][0]["source"].update(image_dimensions={"width": 1, "height": 1}),
            lambda: self.manifest_data["pages"][0]["variants"][0].update(sha256="b" * 64),
            lambda: self.manifest_data["pages"][0]["variants"][0]["transform"]["parameters"].update(operation="contrast"),
            lambda: self.manifest_data["pages"][0]["variants"][0]["ocr_outputs"].append(copy.deepcopy(self.manifest_data["pages"][0]["variants"][0]["ocr_outputs"][0])),
        ]
        for mutate in mutations:
            self.manifest_data = copy.deepcopy(original)
            mutate()
            self.sync()
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                self.run_bridge(apply=True)
            self.assertFalse(self.output.exists())
        for updates in ({"engine": "tesseract"}, {"image_transform": {}}, {"page_id": "wrong"}):
            self.manifest_data = copy.deepcopy(original)
            self.manifest_data["pages"][0]["variants"][0]["ocr_outputs"][0]["structured_evidence"].update(updates)
            self.sync()
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.run_bridge(apply=True)

    def test_changed_source_raw_text_and_run_hash_rejected(self):
        for path in (self.image, self.raw):
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.run_bridge(apply=True)
            path.write_bytes(original)
        self.payload["text"] = "changed"
        self.sync()
        with self.assertRaisesRegex(ValueError, "SHA-256 del testo"):
            self.run_bridge(apply=True)
        self.payload["text"] = "REPORT"
        self.payload["ocr_run_provenance"]["source_image"]["sha256_before"] = "b" * 64
        self.sync()
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.run_bridge(apply=True)
        self.assertFalse(self.output.exists())

    def test_invalid_late_page_leaves_no_output(self):
        page = copy.deepcopy(self.page)
        page["page_id"] = "p2"
        self.manifest_data["pages"].append(page)
        self.sync()
        with self.assertRaises(ValueError):
            self.run_bridge(processed_text={"p1": self.text, "p2": self.text}, apply=True)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".ocr-tesseract-from-t36-*")))

    def test_artifact_name_collision_rejected(self):
        second = copy.deepcopy(self.page)
        second["page_id"] = "P1"
        self.manifest_data["pages"].append(second)
        self.sync()
        with self.assertRaisesRegex(ValueError, "collisioni"):
            self.run_bridge(processed_text={"p1": self.text, "P1": self.text}, apply=True)
        self.assertFalse(self.output.exists())

    def test_adapter_rejects_wrong_anchor_crop_quality_and_selected_hash(self):
        original_manifest = copy.deepcopy(self.manifest_data)
        original_text = copy.deepcopy(self.payload)
        for role in ("anchor", "crop", "quality", "selected_hash"):
            self.manifest_data = copy.deepcopy(original_manifest)
            self.payload = copy.deepcopy(original_text)
            primary = self.manifest_data["pages"][0]["variants"][0]["ocr_outputs"][0]["structured_evidence"]
            if role == "anchor":
                primary["source_page"]["original_page"]["source_file"] = "other.tif"
            elif role == "crop":
                primary["source_page"]["crop"] = {"left": 0, "top": 0, "right": 100, "bottom": 100}
            elif role == "quality":
                self.payload["ocr_quality_gate_status"] = "rejected"
            else:
                self.payload["ocr_run_provenance"]["selected_input"]["sha256"] = "b" * 64
            self.sync()
            with self.subTest(role=role), self.assertRaises(ValueError):
                self.run_bridge(apply=True)
            self.assertFalse(self.output.exists())

    def test_destination_created_during_apply_is_preserved(self):
        hash_file = bridge._sha256_file

        def create_destination_before_publish(path):
            if path == self.text:
                self.output.mkdir()
                (self.output / "other.txt").write_bytes(b"other writer")
            return hash_file(path)

        with patch.object(bridge, "_sha256_file", side_effect=create_destination_before_publish):
            with self.assertRaises(FileExistsError):
                self.run_bridge(apply=True)
        self.assertEqual(list(self.output.iterdir()), [self.output / "other.txt"])
        self.assertEqual((self.output / "other.txt").read_bytes(), b"other writer")
        self.assertFalse(list(self.root.glob(".ocr-tesseract-from-t36-*")))

    def test_changed_input_during_apply_aborts_and_cleans_staging(self):
        hash_file = bridge._sha256_file

        def change_text_before_final_hash(path):
            if path == self.text:
                self.text.write_bytes(self.text.read_bytes() + b" ")
            return hash_file(path)

        with patch.object(bridge, "_sha256_file", side_effect=change_text_before_final_hash):
            with self.assertRaisesRegex(ValueError, "Input modificato"):
                self.run_bridge(apply=True)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".ocr-tesseract-from-t36-*")))

    def test_publish_failure_cleans_staging(self):
        before = self.snapshot()
        with patch.object(bridge.os, "rename", side_effect=OSError("publish failed")):
            with self.assertRaisesRegex(OSError, "publish failed"):
                self.run_bridge(apply=True)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".ocr-tesseract-from-t36-*")))

    def test_existing_and_in_repository_output_rejected(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.run_bridge()
        with self.assertRaisesRegex(ValueError, "esterna"):
            self.run_bridge(output_dir=Path(__file__).resolve().parents[1] / "new-tesseract-output")

    def test_cli_preview_apply_and_invalid_duplicate_mapping(self):
        args = ["documents", "ocr-tesseract-from-t36", "--manifest", str(self.manifest),
                "--processed-text", f"p1={self.text}", "--source-document-id", "p1=synthetic",
                "--output-dir", str(self.output)]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["operation_status"], "preview")
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            self.assertEqual(main(args + ["--processed-text", f"p1={self.text}"]), 1)
            self.assertEqual(main(args + ["--processed-text", "malformed"]), 1)
            self.assertEqual(main(args + ["--source-document-id", "p1="]), 1)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args + ["--apply"]), 0)
        evidence = json.loads((self.output / "evidence/p1.json").read_text(encoding="utf-8"))
        report = json.loads((self.output / "run-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["source_document_id"], "synthetic")
        self.assertEqual(report["pages"][0]["source_document_id"], "synthetic")


if __name__ == "__main__":
    unittest.main()
