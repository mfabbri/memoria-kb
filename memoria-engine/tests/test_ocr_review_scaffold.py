from __future__ import annotations

import hashlib
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from caduti_fonti_report.document_analysis.ocr_alert_dispositions import audit_ocr_alert_dispositions
from caduti_fonti_report.document_analysis.ocr_page_layout import audit_ocr_page_layout
from caduti_fonti_report.document_analysis.ocr_review_scaffold import scaffold_ocr_review
from caduti_fonti_report.document_analysis.ocr_visual_review_ledger import audit_ocr_visual_review_ledger
from caduti_fonti_report.document_analysis.document_structure import reconstruct_document_structure
from caduti_fonti_report.memoria_cli import main


class OcrReviewScaffoldTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "page.tiff"
        Image.new("L", (20, 10), 255).save(self.image)
        image_hash = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.evidence = {
            "@type": "OcrPageEvidence", "page_id": "synthetic-1", "source_image_hash": image_hash,
            "source_page": {"frame_index": 0, "original_page": {"page_id": "synthetic-1",
                "source_image_hash": image_hash, "source_file": "page.tiff",
                "source_dimensions": {"width": 20, "height": 10}}},
            "transform_id": "original", "image_transform": None, "engine": "paddle-ocr-v5",
            "model": {"name": "fixture"}, "language": "deu",
            "regions": [{"region_id": "r1", "text": "Unbekannt", "geometry": {"bbox": [0, 0, 20, 10]}}],
        }
        self.structure = reconstruct_document_structure(evidence=self.evidence, profile="numbered_report").to_dict()
        self._write("evidence.json", self.evidence)
        self.tesseract = copy.deepcopy(self.evidence)
        self.tesseract.update(engine="tesseract", model={"name": "tesseract"})
        self.tesseract["regions"][0]["text"] = "Alternative"
        self._write("tesseract.json", self.tesseract)
        self._make_comparison()
        self._write("structure.json", self.structure)
        self._write("lexicon.json", {"@type": "OcrLanguageLexicon", "schema_version": "1.0",
            "@id": "fixture:de", "version": "1", "language": "deu",
            "entries": [{"term": "Bekannt", "category": "word", "source_id": "fixture", "version": "1"}]})
        (self.root / "page.md").write_text("Unbekannt\n", encoding="utf-8")
        self.output = self.root / "scaffold"

    def _write(self, name, payload):
        (self.root / name).write_text(json.dumps(payload), encoding="utf-8")

    def _make_comparison(self, reverse=False):
        left, right = ("tesseract.json", "evidence.json") if reverse else ("evidence.json", "tesseract.json")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["documents", "ocr-evidence-compare", "--left", str(self.root / left),
                "--right", str(self.root / right), "--output", str(self.root / "comparison.json")]), 0)
        self._write("comparison.json", json.loads(output.getvalue()))

    def _scaffold(self, apply=False, variant_image_path=None):
        return scaffold_ocr_review(image_path=self.image, evidence_path=self.root / "evidence.json",
            structure_path=self.root / "structure.json", markdown_path=self.root / "page.md",
            tesseract_evidence_path=self.root / "tesseract.json", comparison_path=self.root / "comparison.json",
            lexicon_path=self.root / "lexicon.json", output_dir=self.output, apply=apply, tile_size=128,
            variant_image_path=variant_image_path)

    def test_raw_byte_copy_requires_actual_matching_variant(self):
        self.evidence["source_page"].update(variant_id="raw", target="full_page", tile_id=None)
        self.evidence.update(transform_id="t36:raw", image_transform={"id": "t36:raw", "parameters": {"operation": "byte_copy"}})
        self.tesseract["source_page"] = copy.deepcopy(self.evidence["source_page"])
        self.tesseract.update(transform_id=self.evidence["transform_id"], image_transform=self.evidence["image_transform"])
        self._write("evidence.json", self.evidence)
        self._write("tesseract.json", self.tesseract)
        self._write("structure.json", reconstruct_document_structure(evidence=self.evidence, profile="numbered_report").to_dict())
        self._make_comparison()
        with self.assertRaisesRegex(ValueError, "byte-identica"):
            self._scaffold()
        variant = self.root / "variant.tiff"
        variant.write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "byte-identica"):
            self._scaffold(variant_image_path=variant)
        variant.write_bytes(self.image.read_bytes())
        self.assertEqual(self._scaffold(variant_image_path=variant)["status"], "template_incomplete")

    def test_preview_writes_nothing_and_never_authorizes_review(self):
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        report = self._scaffold()
        self.assertEqual(report["operation_status"], "preview")
        self.assertFalse(self.output.exists())
        self.assertFalse(report["authorizations"]["human_review_request_allowed"])
        self.assertEqual(report["crop_count"], report["observation_count"])
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_apply_writes_image_bound_incomplete_templates(self):
        report = self._scaffold(apply=True)
        self.assertEqual(report["operation_status"], "written")
        ledger = json.loads((self.output / "visual-ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["template_status"], "incomplete")
        self.assertTrue((self.output / "scaffold-manifest.json").is_file())
        manifest = json.loads((self.output / "scaffold-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "template_incomplete")
        for key, name in (("tesseract_evidence", "tesseract.json"), ("comparison", "comparison.json")):
            self.assertEqual(manifest["inputs"][key + "_path"], str(self.root / name))
            self.assertEqual(manifest["inputs"][key + "_digest"],
                             "sha256:" + hashlib.sha256((self.root / name).read_bytes()).hexdigest())
        self.assertFalse(manifest["authorizations"]["machine_pass"])
        self.assertFalse(manifest["authorizations"]["auto_validation_enabled"])
        self.assertEqual(len(list((self.output / "crops").glob("*.png"))), report["crop_count"])
        visual = audit_ocr_visual_review_ledger(ledger_path=self.output / "visual-ledger.json",
            image_path=self.image, evidence_path=self.root / "evidence.json", structure_path=self.root / "structure.json")
        self.assertEqual(visual["processability_status"], "blocked")
        self.assertIn("incomplete_template", {issue["code"] for issue in visual["checks"]["issues"]})
        visual_issue_codes = {issue["code"] for issue in visual["checks"]["issues"]}
        self.assertNotIn("crop_hash_mismatch", visual_issue_codes)
        self.assertNotIn("crop_pixel_mismatch", visual_issue_codes)
        self.assertNotIn("tile_coverage_gap_or_excess", visual_issue_codes)
        self.assertFalse(visual["human_review_request_allowed"])
        visual_path = self.output / "visual-audit.json"
        visual_path.write_text(json.dumps(visual), encoding="utf-8")
        layout_audit = audit_ocr_page_layout(layout_path=self.output / "layout.json",
            evidence_path=self.root / "evidence.json", visual_audit_path=visual_path)
        self.assertIn("incomplete_template", {issue["code"] for issue in layout_audit["checks"]["issues"]})
        disposition_audit = audit_ocr_alert_dispositions(
            structure_path=self.root / "structure.json", lexicon_review_path=self.output / "lexicon-review.json",
            visual_audit_path=visual_path, ledger_path=self.output / "visual-ledger.json",
            dispositions_path=self.output / "dispositions.json")
        self.assertIn("incomplete_template", {issue["code"] for issue in disposition_audit["checks"]["issues"]})

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "deve essere nuova"):
            self._scaffold(apply=True)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_bad_evidence_hash_fails_before_writing(self):
        self.evidence["source_image_hash"] = "0" * 64
        self._write("evidence.json", self.evidence)
        with self.assertRaisesRegex(ValueError, "Hash TIFF"):
            self._scaffold(apply=True)
        self.assertFalse(self.output.exists())

    def test_reverse_comparison_is_valid_without_authorizing_review(self):
        self._make_comparison(reverse=True)
        report = self._scaffold()
        self.assertEqual(report["status"], "template_incomplete")
        self.assertFalse(report["authorizations"]["human_review_request_allowed"])

    def test_missing_inputs_fail_before_creating_outputs(self):
        for name in ("tesseract.json", "comparison.json"):
            for apply in (False, True):
                with self.subTest(input=name, apply=apply):
                    path = self.root / name
                    raw = path.read_bytes()
                    path.unlink()
                    try:
                        with self.assertRaises(OSError):
                            self._scaffold(apply=apply)
                    finally:
                        path.write_bytes(raw)
                    self.assertFalse(self.output.exists())

    def test_stale_evidence_digests_fail_before_creating_outputs(self):
        for name in ("evidence.json", "tesseract.json"):
            for apply in (False, True):
                with self.subTest(input=name, apply=apply):
                    path = self.root / name
                    raw = path.read_bytes()
                    path.write_bytes(raw + b" ")
                    try:
                        with self.assertRaisesRegex(ValueError, "paths/digests"):
                            self._scaffold(apply=apply)
                    finally:
                        path.write_bytes(raw)
                    self.assertFalse(self.output.exists())

    def test_invalid_comparison_fails_before_creating_outputs(self):
        original = json.loads((self.root / "comparison.json").read_text(encoding="utf-8"))
        mutations = [
            lambda report: report.update(schema_version="2.0"),
            lambda report: report.update(machine_pass=True),
            lambda report: report.update(review_status="reviewed"),
            lambda report: report["inputs"]["left"].update(path=str(self.root / "other.json")),
            lambda report: report["right_evidence"].update(page_id="other-page"),
            lambda report: report.update(disagreements=[]),
        ]
        for index, mutate in enumerate(mutations):
            for apply in (False, True):
                with self.subTest(mutation=index, apply=apply):
                    comparison = copy.deepcopy(original)
                    mutate(comparison)
                    self._write("comparison.json", comparison)
                    with self.assertRaises(ValueError):
                        self._scaffold(apply=apply)
                    self.assertFalse(self.output.exists())

    def test_fresh_digest_cannot_hide_incompatible_page(self):
        self.tesseract["source_page"]["frame_index"] = 1
        self._write("tesseract.json", self.tesseract)
        comparison = json.loads((self.root / "comparison.json").read_text(encoding="utf-8"))
        comparison["inputs"]["right"]["sha256"] = hashlib.sha256((self.root / "tesseract.json").read_bytes()).hexdigest()
        self._write("comparison.json", comparison)
        with self.assertRaisesRegex(ValueError, "Incompatible"):
            self._scaffold(apply=True)
        self.assertFalse(self.output.exists())

    def test_cli_requires_both_comparison_inputs(self):
        base = ["documents", "ocr-review-scaffold", "--image", str(self.image),
                "--evidence", str(self.root / "evidence.json"), "--structure", str(self.root / "structure.json"),
                "--markdown", str(self.root / "page.md"), "--lexicon", str(self.root / "lexicon.json"),
                "--output-dir", str(self.output)]
        for flag, name in (("--comparison", "comparison.json"), ("--tesseract-evidence", "tesseract.json")):
            with self.subTest(missing=flag), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(base + [flag, str(self.root / name)])
            self.assertEqual(error.exception.code, 2)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(base + ["--comparison", str(self.root / "comparison.json"),
                "--tesseract-evidence", str(self.root / "tesseract.json")]), 0)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
