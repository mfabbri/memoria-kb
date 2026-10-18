from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from caduti_fonti_report.document_analysis.document_structure import reconstruct_document_structure, render_document_structure_markdown
from caduti_fonti_report.document_analysis.ocr_candidate_assessment import build_ocr_candidate_assessment
from caduti_fonti_report.document_analysis.ocr_evidence_comparison import compare_ocr_page_evidence
from caduti_fonti_report.document_analysis.ocr_risk_features import build_ocr_risk_features
from caduti_fonti_report.memoria_cli import main


class OcrRiskFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = {name: self.root / (name + ".json") for name in (
            "assessment", "structure", "markdown", "evidence", "lexicon_review", "comparison", "left", "right", "output")}
        self.paths["image"] = self.root / "synthetic.tif"
        Image.new("L", (300, 160), color=255).save(self.paths["image"], format="TIFF")
        image_hash = self.digest("image")
        self.left = {
            "source_document_id": "synthetic-document",
            "@type": "OcrPageEvidence", "page_id": "synthetic-page", "source_image_hash": image_hash,
            "engine": "synthetic-a", "model": {"name": "model-a"}, "language": "deu",
            "transform_id": "raw", "image_transform": {"name": "raw"},
            "source_page": {"original_page": {
                "page_id": "synthetic-page", "source_image_hash": image_hash,
                "source_file": "synthetic.tif", "source_dimensions": {"width": 300, "height": 160},
            }},
            "regions": [{"region_id": "r1", "text": "REPORT", "geometry": {"bbox": [10, 10, 100, 30]},
                          "confidence": 0.2, "confidence_scale": "paddle_native"}],
        }
        self.right = deepcopy(self.left)
        self.right.update(engine="synthetic-b", model={"name": "model-b"})
        self.right["regions"][0].update(text="DIFFERENT", confidence=70.0, confidence_scale="tesseract_0_100")
        self.save("left", self.left)
        self.save("evidence", self.left)
        self.save("right", self.right)
        structure = reconstruct_document_structure(evidence=self.left, profile="numbered_report")
        self.structure = structure.to_dict()
        self.save("structure", self.structure)
        self.paths["markdown"].write_text(render_document_structure_markdown(structure), encoding="utf-8")
        self.save("lexicon_review", {
            "@type": "OcrDocumentLexiconReview", "schema_version": "1.0",
            "source_structure_digest": "sha256:" + self.digest("structure"),
            "blocks": [{"page_id": "synthetic-page", "block_id": block["block_id"],
                        "text": block["text"], "source_region_ids": block["source_region_ids"],
                        "tokens": [{"raw_token": "REPORT", "status": "not_found"}]} for block in self.structure["blocks"]],
        })
        self.refresh_assessment()
        self.refresh_comparison()

    def save(self, name, value):
        self.paths[name].write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def digest(self, name):
        return hashlib.sha256(self.paths[name].read_bytes()).hexdigest()

    def refresh_assessment(self):
        assessment = build_ocr_candidate_assessment(
            **{name + "_path": self.paths[name] for name in ("structure", "markdown", "evidence", "lexicon_review")},
            output_path=self.paths["assessment"],
        )
        self.save("assessment", assessment)

    def refresh_comparison(self):
        report = compare_ocr_page_evidence(left=self.left, right=self.right)
        report["inputs"] = {side: {"path": str(self.paths[side]), "sha256": self.digest(side)} for side in ("left", "right")}
        self.save("comparison", report)

    def build(self, **kwargs):
        return build_ocr_risk_features(**{name + "_path": path for name, path in self.paths.items()}, **kwargs)

    def test_deterministic_descriptive_features_bind_every_input_without_writes(self):
        before = {name: path.read_bytes() for name, path in self.paths.items() if name != "output"}
        result = self.build()
        self.assertEqual(result, self.build())
        self.assertEqual(result["features"]["disagreement_pair_ratio"], 1)
        self.assertEqual(result["features"]["lexical_alert_count"], 1)
        self.assertEqual(result["features"]["evidence_region_coverage_ratio"], 1)
        self.assertEqual(result["score_status"], "not_calibrated")
        self.assertIsNone(result["risk_score"])
        self.assertIsNone(result["cutoff"])
        self.assertFalse(result["machine_pass"])
        self.assertFalse(result["auto_validation_enabled"])
        self.assertEqual(result["candidate_identity"]["page_id"], "synthetic-page")
        self.assertEqual(result["candidate_identity"]["source_document_id"], "synthetic-document")
        self.assertEqual(result["schema_version"], "1.1")
        confidence = result["features"]["confidence_by_evidence"]
        self.assertEqual(confidence["left"]["confidence_scale"], "paddle_native")
        self.assertEqual(confidence["left"]["mean"], 0.2)
        self.assertEqual(confidence["right"]["confidence_scale"], "tesseract_0_100")
        self.assertEqual(confidence["right"]["mean"], 70.0)
        self.assertNotEqual(confidence["left"]["confidence_scale"], confidence["right"]["confidence_scale"])
        self.assertEqual(set(result["inputs"]), set(before))
        self.assertEqual(result["inputs"]["image"]["sha256"], self.digest("image"))
        self.assertFalse(self.paths["output"].exists())
        self.assertEqual(before, {name: self.paths[name].read_bytes() for name in before})

    def test_confidence_absence_is_explicit(self):
        for evidence in (self.left, self.right):
            evidence["regions"][0].pop("confidence")
            evidence["regions"][0].pop("confidence_scale")
        self.save("left", self.left)
        self.save("evidence", self.left)
        self.save("right", self.right)
        self.refresh_assessment()
        self.refresh_comparison()
        summary = self.build()["features"]["confidence_by_evidence"]
        self.assertEqual(summary["left"]["status"], "not_exposed")
        self.assertEqual(summary["left"]["confidence_count"], 0)
        self.assertEqual(summary["left"]["confidence_coverage_ratio"], 0)
        self.assertIsNone(summary["left"]["mean"])

    def test_confidence_without_scale_is_not_aggregated(self):
        self.left["regions"][0].pop("confidence_scale")
        self.save("left", self.left)
        self.save("evidence", self.left)
        self.refresh_assessment()
        self.refresh_comparison()
        summary = self.build()["features"]["confidence_by_evidence"]["left"]
        self.assertEqual(summary["status"], "scale_missing")
        self.assertEqual(summary["missing_scale_count"], 1)
        self.assertIsNone(summary["mean"])

    def test_confidence_mixed_scales_are_not_aggregated(self):
        second = deepcopy(self.left["regions"][0])
        second.update(region_id="r2", confidence=0.8, confidence_scale="paddle_different")
        second["geometry"]["bbox"] = [110, 10, 200, 30]
        self.left["regions"].append(second)
        self.save("left", self.left)
        self.save("evidence", self.left)
        self.refresh_assessment()
        self.refresh_comparison()
        summary = self.build()["features"]["confidence_by_evidence"]["left"]
        self.assertEqual(summary["status"], "mixed_scales")
        self.assertEqual(summary["confidence_scales"], ["paddle_different", "paddle_native"])
        self.assertIsNone(summary["mean"])

    def test_invalid_confidence_values_are_not_aggregated(self):
        self.left["regions"][0]["confidence"] = True
        self.save("left", self.left)
        self.save("evidence", self.left)
        self.refresh_assessment()
        self.refresh_comparison()
        summary = self.build()["features"]["confidence_by_evidence"]["left"]
        self.assertEqual(summary["status"], "invalid_values")
        self.assertEqual(summary["invalid_count"], 1)
        self.assertIsNone(summary["mean"])

    def test_changed_sources_and_forged_assessment_rejected(self):
        for name in ("markdown", "lexicon_review", "structure", "evidence"):
            with self.subTest(name=name):
                original = self.paths[name].read_bytes()
                self.paths[name].write_bytes(original + b" ")
                with self.assertRaises(ValueError):
                    self.build()
                self.paths[name].write_bytes(original)
        report = json.loads(self.paths["assessment"].read_text(encoding="utf-8"))
        report["diagnostics"]["lexical_alert_count"] = 0
        self.save("assessment", report)
        with self.assertRaisesRegex(ValueError, "divergent candidate"):
            self.build()

    def test_forged_comparison_diagnostics_and_input_hashes_rejected(self):
        report = json.loads(self.paths["comparison"].read_text(encoding="utf-8"))
        report["disagreements"] = []
        self.save("comparison", report)
        with self.assertRaisesRegex(ValueError, "divergent evidence"):
            self.build()
        self.refresh_comparison()
        self.paths["right"].write_bytes(self.paths["right"].read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "hashes"):
            self.build()

    def test_cross_page_image_frame_and_same_engine_rejected_after_rehash(self):
        baseline = deepcopy(self.right)
        for field, value in (("page_id", "other"), ("source_image_hash", "b" * 64),
                             ("transform_id", "other-frame"), ("engine", "synthetic-a")):
            with self.subTest(field=field):
                changed = deepcopy(baseline)
                changed[field] = value
                if field == "engine":
                    changed["model"] = self.left["model"]
                self.save("right", changed)
                report = json.loads(self.paths["comparison"].read_text(encoding="utf-8"))
                report["inputs"]["right"]["sha256"] = self.digest("right")
                self.save("comparison", report)
                with self.assertRaises(ValueError):
                    self.build()

    def test_candidate_must_be_exact_comparison_input(self):
        changed = deepcopy(self.left)
        changed["regions"][0]["text"] = "UNBOUND"
        self.save("evidence", changed)
        with self.assertRaisesRegex(ValueError, "exact comparison"):
            self.build()

    def test_source_document_identity_missing_or_mismatched_rejected(self):
        for side in ("evidence", "left", "right"):
            original = self.paths[side].read_bytes()
            for value in (None, "", "other-document"):
                with self.subTest(side=side, value=value):
                    changed = json.loads(original)
                    if value is None:
                        del changed["source_document_id"]
                    else:
                        changed["source_document_id"] = value
                    self.save(side, changed)
                    with self.assertRaisesRegex(ValueError, "source_document_id"):
                        self.build()
                    self.paths[side].write_bytes(original)

    def test_image_bytes_must_match_declared_evidence_hash(self):
        self.paths["image"].write_bytes(self.paths["image"].read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "image bytes"):
            self.build(apply=True)
        self.assertFalse(self.paths["output"].exists())

    def test_image_changed_during_extraction_rejected(self):
        def compare_and_tamper(**kwargs):
            result = compare_ocr_page_evidence(**kwargs)
            self.paths["image"].write_bytes(self.paths["image"].read_bytes() + b"tampered")
            return result

        with patch("caduti_fonti_report.document_analysis.ocr_risk_features.compare_ocr_page_evidence",
                   side_effect=compare_and_tamper):
            with self.assertRaisesRegex(ValueError, "changed during"):
                self.build(apply=True)
        self.assertFalse(self.paths["output"].exists())

    def test_output_cannot_replace_image(self):
        original = self.paths["image"].read_bytes()
        self.paths["output"] = self.paths["image"]
        with self.assertRaisesRegex(ValueError, "replace"):
            self.build(apply=True)
        self.assertEqual(self.paths["image"].read_bytes(), original)

    def test_candidate_can_be_right_input(self):
        self.paths["left"], self.paths["right"] = self.paths["right"], self.paths["left"]
        self.left, self.right = self.right, self.left
        self.refresh_comparison()
        self.assertEqual(self.build()["candidate_identity"]["engine"], "synthetic-a")

    def test_recomputed_candidate_identity_mismatch_rejected(self):
        self.structure["source_evidence"]["transform_id"] = "other-frame"
        self.save("structure", self.structure)
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, "identity"):
            self.build()

    def test_diagnostic_blocked_assessment_keeps_blocked_status(self):
        self.paths["markdown"].write_text("wrong render", encoding="utf-8")
        self.refresh_assessment()
        report = self.build()
        self.assertEqual(report["processability_status"], "blocked")
        self.assertEqual(report["features"]["assessment_issue_count"], 1)
        self.assertFalse(report["machine_pass"])

    def test_ambiguous_or_unmatched_diagnostics_do_not_claim_accuracy(self):
        self.right["regions"][0]["geometry"]["bbox"] = [110, 10, 150, 30]
        self.save("right", self.right)
        self.refresh_comparison()
        report = self.build()
        self.assertIsNone(report["features"]["disagreement_pair_ratio"])
        self.assertEqual(report["features"]["unmatched_left_region_count"], 1)
        self.assertFalse(report["shared_omission_detection_performed"])

    def test_apply_idempotent_preserves_inputs_and_rejects_output_collision(self):
        self.assertEqual(self.build(apply=True)["operation_status"], "written")
        saved = self.paths["output"].read_bytes()
        self.assertEqual(self.build(apply=True)["operation_status"], "skipped_existing")
        self.assertEqual(self.paths["output"].read_bytes(), saved)
        self.paths["output"].write_text("different", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs"):
            self.build(apply=True)
        self.paths["output"] = self.paths["structure"]
        with self.assertRaisesRegex(ValueError, "replace"):
            self.build(apply=True)

    def test_cli_preview_apply_and_error(self):
        args = ["documents", "ocr-risk-features"]
        for name, path in self.paths.items():
            args.extend(["--" + name.replace("_", "-"), str(path)])
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(stdout.getvalue())["operation_status"], "preview")
        self.assertFalse(self.paths["output"].exists())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args + ["--apply"]), 0)
        self.paths["markdown"].write_text("stale", encoding="utf-8")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 1)


if __name__ == "__main__":
    unittest.main()
