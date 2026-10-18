from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from caduti_fonti_report.document_analysis.document_structure import reconstruct_document_structure, render_document_structure_markdown
from caduti_fonti_report.document_analysis.ocr_candidate_assessment import build_ocr_candidate_assessment
from caduti_fonti_report.memoria_cli import main


class OcrCandidateAssessmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.evidence_path = self.root / "page.evidence.json"
        self.structure_path = self.root / "structure.json"
        self.markdown_path = self.root / "page.md"
        self.lexicon_path = self.root / "lexicon-review.json"
        self.output_path = self.root / "assessment.json"
        self.evidence = {
            "@type": "OcrPageEvidence", "page_id": "page-1", "source_document_id": "doc-1",
            "source_image_hash": "image-sha", "transform_id": "identity", "engine": "ppocr",
            "language": "deu", "source_page": {"number": 1}, "model": {"name": "fixture"},
            "image_transform": None,
            "regions": [{"region_id": "r1", "text": "Unbekannte Xyz", "geometry": {"bbox": [0, 0, 100, 20]}}],
        }
        self.write(self.evidence_path, self.evidence)
        self.structure = reconstruct_document_structure(evidence=self.evidence, profile="numbered_report").to_dict()
        self.write(self.structure_path, self.structure)
        self.markdown_path.write_text(
            render_document_structure_markdown(reconstruct_document_structure(evidence=self.evidence, profile="numbered_report")),
            encoding="utf-8",
        )
        structure_bytes = self.structure_path.read_bytes()
        block = self.structure["blocks"][0]
        self.lexicon = {
            "@type": "OcrDocumentLexiconReview", "schema_version": "1.0",
            "source_structure_digest": "sha256:" + hashlib.sha256(structure_bytes).hexdigest(),
            "blocks": [{"page_id": "page-1", "block_id": block["block_id"], "text": block["text"],
                        "source_region_ids": block["source_region_ids"],
                        "tokens": [{"raw_token": word, "status": "not_found", "needs_human_review": True}
                                   for word in ("Unbekannte", "Xyz")] }],
        }
        self.write(self.lexicon_path, self.lexicon)

    @staticmethod
    def write(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def assess(self, **kwargs):
        return build_ocr_candidate_assessment(
            structure_path=self.structure_path, markdown_path=self.markdown_path,
            evidence_path=self.evidence_path, lexicon_review_path=self.lexicon_path,
            output_path=self.output_path, **kwargs,
        )

    def test_unknown_words_are_alerts_grouped_without_manual_action_count(self) -> None:
        report = self.assess()
        self.assertEqual(report["processability_status"], "diagnostic_only")
        self.assertEqual(report["diagnostics"]["lexical_alert_count"], 2)
        self.assertEqual(report["diagnostics"]["pending_classification_group_count"], 1)
        self.assertEqual(report["diagnostics"]["groups"][0]["status"], "pending_classification")
        self.assertIsNone(report["manual_action_count"])
        self.assertEqual(report["routing_status"], "not_calibrated")
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["human_verified"])

    def test_complete_region_coverage_is_only_ocr_evidence_coverage(self) -> None:
        # A fully represented OCR result says nothing about text the OCR omitted
        # from the image, including omissions shared by independent engines.
        report = self.assess()
        self.assertEqual(report["diagnostics"]["region_coverage"], {
            "scope": "ocr_evidence_regions_only",
            "evidence_region_count": 1,
            "represented_region_count": 1,
            "unrepresented_region_ids": [],
            "coverage_ratio": 1.0,
        })
        self.assertEqual(report["processability_status"], "diagnostic_only")
        self.assertEqual(report["routing_status"], "not_calibrated")
        self.assertFalse(report["machine_pass"])
        self.assertEqual(report["review_preparation_status"], "incomplete")
        self.assertFalse(report["human_review_request_allowed"])
        self.assertEqual(report["visual_coverage_status"], "not_assessed")

    def test_region_repeated_within_one_block_blocks_assessment(self) -> None:
        block = self.structure["blocks"][0] | {"source_region_ids": ["r1", "r1"]}
        self.write(self.structure_path, self.structure | {"blocks": [block]})
        report = self.assess()
        self.assertEqual(report["processability_status"], "blocked")
        self.assertIn("duplicate_region_link", {issue["code"] for issue in report["checks"]["issues"]})

    def test_region_shared_between_blocks_blocks_assessment(self) -> None:
        first = self.structure["blocks"][0]
        second = first | {"block_id": "block-second"}
        self.write(self.structure_path, self.structure | {"blocks": [first, second]})
        report = self.assess()
        shared = [issue for issue in report["checks"]["issues"]
                  if issue["code"] == "multiple_region_owners"]
        self.assertEqual(report["processability_status"], "blocked")
        self.assertEqual(shared, [{"code": "multiple_region_owners", "region_id": "r1",
                                   "block_ids": [first["block_id"], "block-second"]}])

    def test_empty_evidence_regions_block_assessment(self) -> None:
        empty_evidence = self.evidence | {"regions": []}
        empty_structure = reconstruct_document_structure(evidence=empty_evidence, profile="numbered_report")
        self.write(self.evidence_path, empty_evidence)
        self.write(self.structure_path, empty_structure.to_dict())
        self.markdown_path.write_text(render_document_structure_markdown(empty_structure), encoding="utf-8")
        self.write(self.lexicon_path, self.lexicon | {
            "source_structure_digest": "sha256:" + hashlib.sha256(self.structure_path.read_bytes()).hexdigest(),
            "blocks": [],
        })
        report = self.assess()
        self.assertEqual(report["processability_status"], "blocked")
        self.assertIn("empty_evidence_regions", {issue["code"] for issue in report["checks"]["issues"]})

    def test_unrepresented_ocr_regions_block_assessment(self) -> None:
        extra = [{"region_id": region_id, "text": "Extra",
                  "geometry": {"bbox": [0, 30, 100, 50]}}
                 for region_id in ("r3", "r2")]
        self.write(self.evidence_path, self.evidence | {"regions": self.evidence["regions"] + extra})
        report = self.assess()
        coverage = report["diagnostics"]["region_coverage"]
        self.assertEqual(coverage["evidence_region_count"], 3)
        self.assertEqual(coverage["represented_region_count"], 1)
        self.assertEqual(coverage["unrepresented_region_ids"], ["r2", "r3"])
        self.assertAlmostEqual(coverage["coverage_ratio"], 1 / 3)
        self.assertEqual(report["processability_status"], "blocked")
        self.assertEqual(report["checks"]["issues"], [{"code": "unrepresented_evidence_regions"}])
        self.assertFalse(report["machine_pass"])

    def test_zero_ocr_regions_have_undefined_coverage(self) -> None:
        empty_evidence = self.evidence | {"regions": []}
        empty_structure = reconstruct_document_structure(evidence=empty_evidence, profile="numbered_report")
        self.write(self.evidence_path, empty_evidence)
        self.write(self.structure_path, empty_structure.to_dict())
        self.markdown_path.write_text(render_document_structure_markdown(empty_structure), encoding="utf-8")
        self.write(self.lexicon_path, self.lexicon | {
            "source_structure_digest": "sha256:" + hashlib.sha256(self.structure_path.read_bytes()).hexdigest(),
            "blocks": [],
        })
        report = self.assess()
        self.assertEqual(report["diagnostics"]["region_coverage"], {
            "scope": "ocr_evidence_regions_only",
            "evidence_region_count": 0,
            "represented_region_count": 0,
            "unrepresented_region_ids": [],
            "coverage_ratio": None,
        })
        self.assertEqual(report["routing_status"], "not_calibrated")
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["human_review_request_allowed"])

    def test_stale_or_missing_lexical_review_blocks_routing(self) -> None:
        self.write(self.lexicon_path, self.lexicon | {"source_structure_digest": "sha256:stale"})
        self.assertIn("stale_lexicon_review", {i["code"] for i in self.assess()["checks"]["issues"]})
        self.lexicon_path.unlink()
        report = self.assess()
        self.assertEqual(report["processability_status"], "blocked")
        self.assertIn("missing_input", {i["code"] for i in report["checks"]["issues"]})

    def test_changed_candidate_cannot_use_review_from_previous_structure(self) -> None:
        self.write(self.structure_path, self.structure | {"profile": "changed"})
        report = self.assess()
        self.assertIn("stale_lexicon_review", {i["code"] for i in report["checks"]["issues"]})

    def test_markdown_mismatch_and_invalid_region_links_are_reported(self) -> None:
        self.markdown_path.write_text("manually edited", encoding="utf-8")
        bad_block = self.structure["blocks"][0] | {"source_region_ids": ["absent"]}
        self.write(self.structure_path, self.structure | {"blocks": [bad_block]})
        report = self.assess()
        issue_codes = {issue["code"] for issue in report["checks"]["issues"]}
        self.assertIn("markdown_mismatch", issue_codes)
        self.assertIn("invalid_region_link", issue_codes)
        self.assertEqual(report["processability_status"], "blocked")

    def test_evidence_identity_mismatch_blocks_assessment(self) -> None:
        self.write(self.evidence_path, self.evidence | {"source_image_hash": "other-image"})
        report = self.assess()
        self.assertIn("evidence_identity_mismatch", {i["code"] for i in report["checks"]["issues"]})

    def test_missing_identity_cannot_match_another_missing_identity(self) -> None:
        structure = self.structure | {"source_evidence": self.structure["source_evidence"] | {"source_image_hash": ""}}
        self.write(self.structure_path, structure)
        self.write(self.evidence_path, self.evidence | {"source_image_hash": ""})
        report = self.assess()
        self.assertEqual(report["processability_status"], "blocked")
        self.assertIn("missing_evidence_identity", {i["code"] for i in report["checks"]["issues"]})

    def test_top_level_page_identity_is_bound_to_evidence(self) -> None:
        self.write(self.structure_path, self.structure | {"page_id": "another-page"})
        report = self.assess()
        self.assertIn("candidate_page_identity_mismatch", {i["code"] for i in report["checks"]["issues"]})

    def test_null_provenance_cannot_match_other_null_provenance(self) -> None:
        self.write(self.structure_path, self.structure | {"source_evidence": self.structure["source_evidence"] | {"model": None}})
        self.write(self.evidence_path, self.evidence | {"model": None})
        report = self.assess()
        self.assertEqual(report["processability_status"], "blocked")
        self.assertIn("missing_evidence_identity", {i["code"] for i in report["checks"]["issues"]})

    def test_duplicate_blocks_cannot_silently_discard_diagnostics(self) -> None:
        duplicate = self.lexicon["blocks"][0] | {"tokens": []}
        self.write(self.lexicon_path, self.lexicon | {"blocks": self.lexicon["blocks"] + [duplicate]})
        report = self.assess()
        self.assertEqual(report["processability_status"], "blocked")
        self.assertIn("duplicate_lexicon_block", {i["code"] for i in report["checks"]["issues"]})
        self.assertEqual(report["diagnostics"]["lexical_alert_count"], 2)

    def test_missing_or_malformed_tokens_block_assessment(self) -> None:
        for tokens in (None, {}, [None], [{"raw_token": "Xyz", "status": []}]):
            with self.subTest(tokens=tokens):
                checked = self.lexicon["blocks"][0] | {"tokens": tokens}
                self.write(self.lexicon_path, self.lexicon | {"blocks": [checked]})
                report = self.assess()
                self.assertEqual(report["processability_status"], "blocked")
                self.assertIn("invalid_lexicon_tokens", {i["code"] for i in report["checks"]["issues"]})

    def test_duplicate_structure_blocks_and_evidence_regions_block_assessment(self) -> None:
        self.write(self.structure_path, self.structure | {"blocks": self.structure["blocks"] * 2})
        self.write(self.evidence_path, self.evidence | {"regions": self.evidence["regions"] * 2})
        report = self.assess()
        codes = {i["code"] for i in report["checks"]["issues"]}
        self.assertIn("duplicate_candidate_block", codes)
        self.assertIn("duplicate_evidence_region", codes)
        self.assertEqual(report["processability_status"], "blocked")

    def test_preview_does_not_create_output_directory(self) -> None:
        self.output_path = self.root / "new-directory" / "assessment.json"
        self.assess()
        self.assertFalse(self.output_path.parent.exists())

    def test_apply_is_idempotent_and_rejects_conflicting_output(self) -> None:
        self.assertEqual(self.assess(apply=True)["operation_status"], "written")
        saved = self.output_path.read_bytes()
        self.assertEqual(self.assess(apply=True)["operation_status"], "skipped_existing")
        self.assertEqual(saved, self.output_path.read_bytes())
        self.output_path.write_text("different", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "diverso"):
            self.assess(apply=True)

    def test_cli_defaults_to_preview(self) -> None:
        args = ["documents", "candidate-assessment", "--structure", str(self.structure_path),
                "--markdown", str(self.markdown_path), "--evidence", str(self.evidence_path),
                "--lexicon-review", str(self.lexicon_path), "--output", str(self.output_path)]
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(stream.getvalue())["operation_status"], "preview")
        self.assertFalse(self.output_path.exists())


if __name__ == "__main__":
    unittest.main()
