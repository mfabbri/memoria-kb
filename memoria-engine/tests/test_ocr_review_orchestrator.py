from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from caduti_fonti_report.document_analysis.document_structure import (
    reconstruct_document_structure, render_document_structure_markdown,
)
from caduti_fonti_report.document_analysis.ocr_visual_review_ledger import audit_ocr_visual_review_ledger
from caduti_fonti_report.document_analysis.ocr_review_orchestrator import run_ocr_review
from caduti_fonti_report.memoria_cli import main


class OcrReviewOrchestratorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        image = Image.new("L", (32, 20), 255)
        image.save(self.root / "page.tiff")
        image_hash = self.digest("page.tiff").removeprefix("sha256:")
        self.evidence = {"@type": "OcrPageEvidence", "page_id": "p1", "source_document_id": "doc1",
            "source_image_hash": image_hash, "transform_id": "original", "engine": "paddle-ocr-v5",
            "language": "deu", "source_page": {"frame_index": 0, "original_page": {
                "page_id": "p1", "source_image_hash": image_hash, "source_file": "page.tiff",
                "source_dimensions": {"width": 32, "height": 20}}},
            "model": {"name": "fixture"}, "image_transform": None,
            "regions": [{"region_id": "r1", "text": "Xyz", "geometry": {"bbox": [0, 0, 16, 10]}}]}
        self.write("evidence.json", self.evidence)
        self.tesseract = copy.deepcopy(self.evidence)
        self.tesseract.update(engine="tesseract", model={"name": "tesseract"})
        self.tesseract["regions"][0]["text"] = "Xyz alternative"
        self.write("tesseract.json", self.tesseract)
        self._make_comparison()
        self.structure_obj = reconstruct_document_structure(evidence=self.evidence, profile="numbered_report")
        self.structure = self.structure_obj.to_dict()
        self.write("structure.json", self.structure)
        (self.root / "page.md").write_text(render_document_structure_markdown(self.structure_obj), encoding="utf-8")
        self._make_ledger()
        self.rebuild("visually_confirmed_candidate", "Xyz")

    def digest(self, name):
        return "sha256:" + hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def write(self, name, payload):
        (self.root / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _make_comparison(self, reverse=False):
        left, right = ("tesseract.json", "evidence.json") if reverse else ("evidence.json", "tesseract.json")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["documents", "ocr-evidence-compare", "--left", str(self.root / left),
                "--right", str(self.root / right), "--output", str(self.root / "comparison.json")]), 0)
        self.write("comparison.json", json.loads(output.getvalue()))

    def _make_ledger(self):
        image = Image.open(self.root / "page.tiff")
        observations = []
        units = [("tile", "full", [0, 0, 32, 20], "tile")]
        block = self.structure["blocks"][0]
        box = [min(0, 0), min(0, 0), 16, 10]
        units.append(("block", block["block_id"], box, block["text"]))
        units.append(("region", "r1", [0, 0, 16, 10], "Xyz"))
        for kind, unit_id, bbox, observed_text in units:
            crop_name = kind + ".png"
            image.crop(tuple(bbox)).save(self.root / crop_name)
            observation = {"observation_id": "obs-" + kind, "unit_type": kind, "unit_id": unit_id,
                "bbox": bbox, "outcome": "readable", "text": observed_text, "candidate_text": observed_text,
                "crop_artifact": {"path": crop_name, "digest": self.digest(crop_name)},
                "observer": {"observer_id": "fixture", "model": "fixture", "configuration": "raw",
                             "observed_at": "2026-10-16T17:00:00Z"}}
            if kind == "block":
                observation["candidate_text"] = block["text"]
                observation["source_region_ids"] = block["source_region_ids"]
            observations.append(observation)
        image.close()
        ledger = {"@type": "OcrVisualReviewLedger", "schema_version": "1.0", "page_id": "p1",
            "source_image_hash": self.evidence["source_image_hash"],
            "source_page": self.evidence["source_page"], "frame_index": 0,
            "source_dimensions": {"width": 32, "height": 20},
            "source_evidence_digest": self.digest("evidence.json"),
            "source_structure_digest": self.digest("structure.json"),
            "review_tiles": [{"tile_id": "full", "bbox": [0, 0, 32, 20]}], "observations": observations}
        self.write("ledger.json", ledger)

    def rebuild(self, disposition, observed_text, visual_outcome="readable"):
        block = self.structure["blocks"][0]
        review = {"@type": "OcrDocumentLexiconReview", "schema_version": "1.0",
            "source_structure_digest": self.digest("structure.json"),
            "blocks": [{"page_id": "p1", "block_id": block["block_id"], "text": block["text"],
                "source_region_ids": block["source_region_ids"],
                "tokens": [{"raw_token": "Xyz", "start": 0, "end": 3, "status": "not_found"}]}]}
        self.write("review.json", review)
        ledger = json.loads((self.root / "ledger.json").read_text(encoding="utf-8"))
        for observation in ledger["observations"]:
            if observation["unit_type"] == "block":
                observation["text"] = observed_text
                observation["outcome"] = visual_outcome
        self.write("ledger.json", ledger)
        # The crop pixels and crop hashes are unchanged; write the modified observation text.
        visual = audit_ocr_visual_review_ledger(ledger_path=self.root / "ledger.json",
            image_path=self.root / "page.tiff", evidence_path=self.root / "evidence.json",
            structure_path=self.root / "structure.json")
        self.write("visual.json", visual)
        layout = {"@type": "OcrPageLayout", "schema_version": "1.0", "page_id": "p1",
            "source_image_hash": self.evidence["source_image_hash"], "source_page": self.evidence["source_page"],
            "source_evidence_digest": self.digest("evidence.json"),
            "source_visual_audit_digest": self.digest("visual.json"),
            "columns": [{"column_id": "c0", "column_index": 0}],
            "rows": [{"row_id": "row0", "row_index": 0, "bbox": [0, 0, 32, 12], "cells": [
                {"cell_id": "cell0", "column_index": 0, "bbox": [0, 0, 16, 10],
                 "source_region_ids": ["r1"], "joiner": "", "text": "Xyz"}]}],
            "reading_order": ["cell0"], "exclusions": []}
        self.write("layout.json", layout)
        item = {"page_id": "p1", "block_id": block["block_id"], "start": 0, "end": 3, "raw_token": "Xyz",
            "disposition": disposition, "visual_observation_id": "obs-block", "reason": "fixture review"}
        if disposition == "visual_correction_proposed":
            item["replacement_text"] = observed_text
        dispositions = {"@type": "OcrLexicalDispositionLedger", "schema_version": "1.0",
            "source_structure_digest": self.digest("structure.json"),
            "source_lexicon_review_digest": self.digest("review.json"),
            "source_visual_audit_digest": self.digest("visual.json"), "dispositions": [item]}
        self.write("dispositions.json", dispositions)

    def run_review(self):
        return run_ocr_review(image_path=self.root / "page.tiff", evidence_path=self.root / "evidence.json",
            structure_path=self.root / "structure.json", markdown_path=self.root / "page.md",
            lexicon_review_path=self.root / "review.json", layout_path=self.root / "layout.json",
            ledger_path=self.root / "ledger.json", dispositions_path=self.root / "dispositions.json",
            comparison_path=self.root / "comparison.json", tesseract_evidence_path=self.root / "tesseract.json")

    def test_all_gates_run_in_order_and_ready_candidate_requests_no_review(self):
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        report = self.run_review()
        self.assertEqual(report["status"], "candidate_ready")
        self.assertEqual([stage["stage"] for stage in report["stages"]], [
            "input_snapshot", "evidence_comparison", "candidate_assessment", "visual_audit", "layout_audit",
            "alert_dispositions", "review_queue", "input_integrity"])
        self.assertEqual(report["inputs"]["image"]["digest"], self.digest("page.tiff"))
        self.assertFalse(report["human_review_request_allowed"])
        self.assertFalse(report["auto_validation_enabled"])
        self.assertFalse(report["machine_pass"])
        self.assertTrue(report["stages"][1]["diagnostic_only"])
        self.assertEqual(report["semantic_accuracy_status"], "not_attested")
        self.assertEqual(report["inputs"]["tesseract_evidence"]["digest"], self.digest("tesseract.json"))
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_only_complete_pipeline_with_residuals_prepares_human_queue(self):
        self.rebuild("unresolved", "Xyz")
        report = self.run_review()
        self.assertEqual(report["status"], "needs_review")
        self.assertTrue(report["human_review_request_allowed"])
        self.assertEqual(report["manual_action_count"], 1)
        self.assertEqual(report["human_review_queue"][0]["unit_id"], self.structure["blocks"][0]["block_id"])
        self.assertFalse(report["human_verified"])

    def test_visual_correction_proposal_blocks_review_until_candidate_regenerated(self):
        self.rebuild("visual_correction_proposed", "Abc")
        report = self.run_review()
        self.assertEqual(report["status"], "correction_required")
        self.assertFalse(report["human_review_request_allowed"])
        self.assertEqual(report["counts"]["correction_proposals"], 1)
        self.assertEqual(report["human_review_queue"], [])
        self.assertIsNone(report["manual_action_count"])

    def test_any_failed_gate_blocks_queue(self):
        layout = json.loads((self.root / "layout.json").read_text(encoding="utf-8"))
        layout["reading_order"] = []
        self.write("layout.json", layout)
        report = self.run_review()
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["human_review_request_allowed"])
        self.assertEqual(report["stages"][-1]["stage"], "layout_audit")
        self.assertEqual(report["stages"][-1]["status"], "blocked")

    def test_comparison_accepts_reverse_orientation_without_promoting_agreement(self):
        self.tesseract["regions"][0]["text"] = "Xyz"
        self.write("tesseract.json", self.tesseract)
        self._make_comparison(reverse=True)
        self.rebuild("unresolved", "Xyz")
        report = self.run_review()
        self.assertEqual(report["status"], "needs_review")
        self.assertEqual(report["manual_action_count"], 1)
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])

    def test_missing_comparison_or_tesseract_blocks_all_review(self):
        self.rebuild("unresolved", "Xyz")
        for name in ("comparison.json", "tesseract.json"):
            with self.subTest(input=name):
                raw = (self.root / name).read_bytes()
                (self.root / name).unlink()
                report = self.run_review()
                (self.root / name).write_bytes(raw)
                self.assertEqual(report["status"], "blocked")
                self.assertEqual(report["human_review_queue"], [])
                self.assertFalse(report["human_review_request_allowed"])

    def test_stale_evidence_bytes_block_even_when_identity_is_unchanged(self):
        self.rebuild("unresolved", "Xyz")
        for name in ("evidence.json", "tesseract.json"):
            with self.subTest(input=name):
                raw = (self.root / name).read_bytes()
                (self.root / name).write_bytes(raw + b" ")
                report = self.run_review()
                (self.root / name).write_bytes(raw)
                self.assertEqual(report["status"], "blocked")
                self.assertEqual(report["stages"][-1]["stage"], "evidence_comparison")
                self.assertEqual(report["human_review_queue"], [])

    def test_invalid_comparison_schema_status_provenance_or_results_blocks_queue(self):
        self.rebuild("unresolved", "Xyz")
        original = json.loads((self.root / "comparison.json").read_text(encoding="utf-8"))
        mutations = [
            lambda report: report.update(schema_version="2.0"),
            lambda report: report.update(machine_pass=True),
            lambda report: report.update(diagnostic_only=False),
            lambda report: report.update(semantic_accuracy_status="attested"),
            lambda report: report["left_evidence"].update(page_id="other-page"),
            lambda report: report["right_evidence"].update(source_image_hash="a" * 64),
            lambda report: report["inputs"]["left"].update(path=str(self.root / "other.json")),
            lambda report: report["inputs"]["right"].update(sha256="0" * 64),
            lambda report: report.update(disagreements=[]),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                comparison = copy.deepcopy(original)
                mutate(comparison)
                self.write("comparison.json", comparison)
                report = self.run_review()
                self.assertEqual(report["status"], "blocked")
                self.assertEqual(report["stages"][-1]["stage"], "evidence_comparison")
                self.assertEqual(report["human_review_queue"], [])
                self.assertFalse(report["human_review_request_allowed"])

    def test_refreshed_digest_cannot_hide_incompatible_source_page(self):
        comparison = json.loads((self.root / "comparison.json").read_text(encoding="utf-8"))
        self.tesseract["source_page"]["frame_index"] = 1
        self.write("tesseract.json", self.tesseract)
        comparison["inputs"]["right"]["sha256"] = self.digest("tesseract.json").removeprefix("sha256:")
        self.write("comparison.json", comparison)
        report = self.run_review()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["stages"][-1]["stage"], "evidence_comparison")

    def test_other_distinguishable_engine_cannot_replace_pp_ocr_or_tesseract(self):
        for name in ("evidence.json", "tesseract.json"):
            with self.subTest(input=name):
                raw = (self.root / name).read_bytes()
                evidence = json.loads(raw)
                evidence["engine"] = "other-engine"
                self.write(name, evidence)
                self._make_comparison()
                report = self.run_review()
                (self.root / name).write_bytes(raw)
                self.assertEqual(report["status"], "blocked")
                self.assertEqual(report["stages"][-1]["stage"], "evidence_comparison")
                self.assertEqual(report["human_review_queue"], [])

    def test_valid_comparison_for_different_image_cannot_prepare_review(self):
        for name in ("evidence.json", "tesseract.json"):
            evidence = json.loads((self.root / name).read_text(encoding="utf-8"))
            evidence["source_image_hash"] = "a" * 64
            evidence["source_page"]["original_page"]["source_image_hash"] = "a" * 64
            self.write(name, evidence)
        self._make_comparison()
        report = self.run_review()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["stages"][-1]["stage"], "evidence_comparison")
        self.assertEqual(report["human_review_queue"], [])

    def test_cli_runs_preview_and_returns_failure_for_blocked_input(self):
        args = ["documents", "ocr-review", "--image", str(self.root / "page.tiff"),
            "--evidence", str(self.root / "evidence.json"), "--structure", str(self.root / "structure.json"),
            "--markdown", str(self.root / "page.md"), "--lexicon-review", str(self.root / "review.json"),
            "--layout", str(self.root / "layout.json"), "--ledger", str(self.root / "ledger.json"),
            "--dispositions", str(self.root / "dispositions.json"),
            "--comparison", str(self.root / "comparison.json"),
            "--tesseract-evidence", str(self.root / "tesseract.json")]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "candidate_ready")
        (self.root / "ledger.json").write_text("{}", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 1)

    def test_cli_requires_comparison_and_tesseract_inputs(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["documents", "ocr-review", "--image", "page.tiff", "--evidence", "evidence.json",
                "--structure", "structure.json", "--markdown", "page.md", "--lexicon-review", "review.json",
                "--layout", "layout.json", "--ledger", "ledger.json", "--dispositions", "dispositions.json"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
