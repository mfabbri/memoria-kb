from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.document_analysis.document_structure import reconstruct_document_structure  # noqa: E402
from caduti_fonti_report.document_analysis.ocr_reference_metrics import (  # noqa: E402
    evaluate_page_reference,
    load_page_reference,
)


FIXTURE = ROOT_DIR / "tests" / "fixtures" / "ocr_reference" / "t38-synthetic.json"


class OcrReferenceMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertTrue(payload["synthetic"])
        self.reference = payload["reference"]
        self.evidence = payload["evidence"]
        self.structure = reconstruct_document_structure(evidence=self.evidence, profile="leader_list_report")

    def test_synthetic_reference_reports_deterministic_metrics_but_is_not_accuracy_eligible(self) -> None:
        first = evaluate_page_reference(reference=self.reference, evidence=self.evidence, structure=self.structure)
        second = evaluate_page_reference(reference=self.reference, evidence=self.evidence, structure=self.structure)
        self.assertEqual(first, second)
        self.assertFalse(first["accuracy_eligible"])
        self.assertEqual(first["accuracy_ineligibility_reasons"], ["reference_origin_is_not_human_verified"])
        self.assertEqual(first["text_metrics"]["character_error_rate"], 0.0)
        self.assertEqual(first["text_metrics"]["word_error_rate"], 0.0)
        self.assertEqual(first["text_metrics"]["reference_token_coverage"], 1.0)
        self.assertEqual(first["text_metrics"]["invention_rate"], 0.0)
        self.assertEqual(first["structural_metrics"]["reading_order_recall"], 1.0)
        self.assertEqual(first["structural_metrics"]["label_value_pair_f1"], 1.0)

    def test_verified_human_reference_requires_matching_original_page_identity(self) -> None:
        reference = deepcopy(self.reference)
        reference["origin"] = "human_verified"
        reference["audit"] = {"reviewer": "synthetic-reviewer", "decision_reference": "synthetic-decision", "verified_at": "2026-09-21T00:00:00+02:00"}
        report = evaluate_page_reference(reference=reference, evidence=self.evidence, structure=self.structure)
        self.assertTrue(report["accuracy_eligible"])

        mismatched = deepcopy(reference)
        mismatched["page"]["source_image_hash"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "corrispondere"):
            evaluate_page_reference(reference=mismatched, evidence=self.evidence, structure=self.structure)

    def test_draft_reference_and_mismatched_structure_cannot_be_accuracy_eligible(self) -> None:
        reference = deepcopy(self.reference)
        reference["origin"] = "human_verified"
        reference["audit"] = {"reviewer": "synthetic-reviewer", "decision_reference": "synthetic-decision", "verified_at": "2026-09-21T00:00:00+02:00"}
        reference["review_status"] = "draft"
        report = evaluate_page_reference(reference=reference, evidence=self.evidence, structure=self.structure)
        self.assertFalse(report["accuracy_eligible"])
        self.assertIn("reference_review_is_not_verified", report["accuracy_ineligibility_reasons"])

        other_evidence = deepcopy(self.evidence)
        other_evidence["transform_id"] = "raw"
        other_evidence["image_transform"] = {"name": "raw"}
        report = evaluate_page_reference(reference=reference, evidence=other_evidence, structure=self.structure)
        self.assertFalse(report["identity_checks"]["structure_evidence_matches"])
        self.assertFalse(report["accuracy_eligible"])

    def test_structure_metrics_penalize_extra_missing_reordered_and_duplicate_pairs(self) -> None:
        reference = deepcopy(self.reference)
        reference["blocks"].append({"kind": "key_value", "text": "Population", "value": "42"})
        reference["text"] += " Population 42"
        report = evaluate_page_reference(reference=reference, evidence=self.evidence, structure=self.structure)
        metrics = report["structural_metrics"]
        self.assertLess(metrics["reading_order_recall"], 1.0)
        self.assertLess(metrics["label_value_pair_recall"], 1.0)

        reordered = deepcopy(self.structure)
        object.__setattr__(reordered, "blocks", tuple(reversed(reordered.blocks)))
        report = evaluate_page_reference(reference=self.reference, evidence=self.evidence, structure=reordered)
        self.assertLess(report["structural_metrics"]["reading_order_recall"], 1.0)

        extra = deepcopy(self.structure)
        object.__setattr__(extra, "blocks", self.structure.blocks + (self.structure.blocks[0],))
        report = evaluate_page_reference(reference=self.reference, evidence=self.evidence, structure=extra)
        self.assertLess(report["structural_metrics"]["reading_order_precision"], 1.0)

    def test_full_structure_provenance_and_audit_are_required(self) -> None:
        reference = deepcopy(self.reference)
        reference["origin"] = "human_verified"
        reference["review_status"] = "verified"
        with self.assertRaisesRegex(ValueError, "audit"):
            evaluate_page_reference(reference=reference, evidence=self.evidence, structure=self.structure)
        reference["audit"] = {"reviewer": "synthetic-reviewer", "decision_reference": "synthetic-decision", "verified_at": "2026-09-21T00:00:00+02:00"}
        for field, value in (("engine", "other-engine"), ("language", "eng")):
            changed = deepcopy(self.evidence)
            changed[field] = value
            report = evaluate_page_reference(reference=reference, evidence=changed, structure=self.structure)
            self.assertFalse(report["accuracy_eligible"])
        changed = deepcopy(self.evidence)
        changed["model"] = {"name": "other"}
        report = evaluate_page_reference(reference=reference, evidence=changed, structure=self.structure)
        self.assertFalse(report["accuracy_eligible"])
        changed = deepcopy(self.evidence)
        changed["image_transform"] = {"name": "raw"}
        report = evaluate_page_reference(reference=reference, evidence=changed, structure=self.structure)
        self.assertFalse(report["accuracy_eligible"])

        variant = deepcopy(self.evidence)
        variant["source_page"]["crop"] = {"left": 10, "top": 10, "right": 200, "bottom": 120}
        variant["transform_id"] = "contrast-x2"
        variant["image_transform"] = {"name": "contrast", "factor": 2.0}
        variant_structure = reconstruct_document_structure(evidence=variant, profile="leader_list_report")
        report = evaluate_page_reference(reference=reference, evidence=variant, structure=variant_structure)
        self.assertTrue(report["accuracy_eligible"])

    def test_contract_rejects_invalid_reference_and_evidence(self) -> None:
        invalid = deepcopy(self.reference)
        invalid["page"]["source_image_hash"] = "not-a-hash"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            load_page_reference(invalid)
        with self.assertRaisesRegex(ValueError, "OcrPageEvidence"):
            evaluate_page_reference(reference=self.reference, evidence={}, structure=self.structure)

    def test_contract_rejects_empty_original_anchor_and_impossible_audit_timestamp(self) -> None:
        evidence = deepcopy(self.evidence)
        evidence["source_page"]["original_page"] = {}
        with self.assertRaisesRegex(ValueError, "original_page.page_id"):
            evaluate_page_reference(reference=self.reference, evidence=evidence, structure=self.structure)
        reference = deepcopy(self.reference)
        reference["origin"] = "human_verified"
        reference["audit"] = {"reviewer": "synthetic-reviewer", "decision_reference": "synthetic-decision", "verified_at": "2026-02-30T00:00:00Z"}
        with self.assertRaisesRegex(ValueError, "timestamp ISO-8601 valido"):
            evaluate_page_reference(reference=reference, evidence=self.evidence, structure=self.structure)

    def test_contract_rejects_nested_original_identity_contradictions(self) -> None:
        for field, value in (("page_id", "another-page"), ("source_image_hash", "b" * 64)):
            with self.subTest(reference_field=field):
                reference = deepcopy(self.reference)
                reference["page"]["original_page"][field] = value
                with self.assertRaisesRegex(ValueError, "corrispondere"):
                    load_page_reference(reference)
            with self.subTest(evidence_field=field):
                evidence = deepcopy(self.evidence)
                evidence["source_page"]["original_page"][field] = value
                with self.assertRaisesRegex(ValueError, "corrispondere"):
                    evaluate_page_reference(reference=self.reference, evidence=evidence, structure=self.structure)


if __name__ == "__main__":
    unittest.main()
