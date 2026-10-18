from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.document_analysis.document_structure import reconstruct_document_structure  # noqa: E402
from caduti_fonti_report.document_analysis.ocr_material_error_draft import (  # noqa: E402
    build_ocr_material_error_draft,
)
from caduti_fonti_report.memoria_cli import main  # noqa: E402


FIXTURE = ROOT_DIR / "tests" / "fixtures" / "ocr_reference" / "t38-synthetic.json"


class OcrMaterialErrorDraftTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.reference = deepcopy(payload["reference"])
        self.evidence = deepcopy(payload["evidence"])
        self.reference["origin"] = "human_verified"
        self.reference["review_status"] = "verified"
        self.reference["audit"] = {
            "reviewer": "fixture-reviewer", "decision_reference": "fixture-decision",
            "verified_at": "2026-10-01T12:00:00Z",
        }
        self.reference["text"] = "REPORT Population 41 Narrative extra note"
        self.image = self.root / "page.tif"
        self.image.write_bytes(b"synthetic image bytes")
        digest = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.reference["page"]["source_image_hash"] = digest
        self.reference["page"]["original_page"]["source_image_hash"] = digest
        self.evidence["source_image_hash"] = digest
        self.evidence["source_page"]["original_page"]["source_image_hash"] = digest
        self.structure = reconstruct_document_structure(evidence=self.evidence, profile="leader_list_report").to_dict()
        self.paths = {
            "reference": self.root / "reference.json",
            "evidence": self.root / "evidence.json",
            "structure": self.root / "structure.json",
            "image": self.image,
            "output": self.root / "material-error-draft.json",
        }
        self.write_json("reference", self.reference)
        self.write_json("evidence", self.evidence)
        self.write_json("structure", self.structure)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, key: str, value: object) -> None:
        self.paths[key].write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def build(self, *, apply: bool = False) -> dict:
        return build_ocr_material_error_draft(
            reference_path=self.paths["reference"], evidence_path=self.paths["evidence"],
            structure_path=self.paths["structure"], image_path=self.paths["image"],
            output_path=self.paths["output"], apply=apply,
        )

    def test_preview_maps_word_differences_without_assigning_materiality(self) -> None:
        result = self.build()
        self.assertEqual(result["operation_status"], "preview")
        self.assertEqual(result["status"], "pending_visual_adjudication")
        self.assertEqual(result["reference_word_count"], 6)
        self.assertEqual(result["candidate_difference_count"], 2)
        substitution, omission = result["candidates"]
        self.assertEqual(substitution["operation"], "substitution")
        self.assertEqual(substitution["reference_token"], "41")
        self.assertEqual(substitution["candidate_token"], "42")
        self.assertEqual(substitution["candidate_source_region_ids"], ["r-value"])
        self.assertEqual(substitution["candidate_bounding_boxes"], [[240, 55, 300, 75]])
        self.assertEqual(omission["operation"], "omission")
        self.assertEqual(omission["reference_token"], "extra")
        self.assertEqual(omission["candidate_source_region_ids"], [])
        self.assertIsNone(substitution["material_word_error"])
        self.assertIsNone(substitution["material_error_category"])
        self.assertIsNone(result["safety"]["material_word_error_count"])
        self.assertFalse(self.paths["output"].exists())

    def test_apply_is_exclusive_and_repeatable(self) -> None:
        self.assertEqual(self.build(apply=True)["operation_status"], "written")
        saved = self.paths["output"].read_bytes()
        self.assertEqual(self.build(apply=True)["operation_status"], "skipped_existing")
        self.assertEqual(self.paths["output"].read_bytes(), saved)
        self.paths["output"].write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "gia' esistente e diverso"):
            self.build(apply=True)

    def test_unicode_canonical_equivalence_is_not_reported_as_a_difference(self) -> None:
        self.reference["text"] = "Cafe\u0301 Population 42 Narrative note"
        self.evidence["regions"][0]["text"] = "Café"
        self.write_json("reference", self.reference)
        self.write_json("evidence", self.evidence)
        self.structure = reconstruct_document_structure(evidence=self.evidence, profile="leader_list_report").to_dict()
        self.write_json("structure", self.structure)
        result = self.build()
        self.assertEqual(result["status"], "no_token_differences")
        self.assertEqual(result["candidate_difference_count"], 0)
        self.assertIsNone(result["safety"]["material_word_error_count"])

    def test_character_alignment_limit_is_checked_before_reference_metrics(self) -> None:
        oversized = "a" * 3200
        self.reference["text"] = oversized
        self.evidence["regions"] = [{
            "region_id": "r-long", "text": oversized,
            "geometry": {"bbox": [0, 0, 10, 10]},
        }]
        self.write_json("reference", self.reference)
        self.write_json("evidence", self.evidence)
        self.structure = reconstruct_document_structure(
            evidence=self.evidence, profile="leader_list_report"
        ).to_dict()
        self.write_json("structure", self.structure)
        with patch(
            "caduti_fonti_report.document_analysis.ocr_material_error_draft.evaluate_page_reference"
        ) as evaluate:
            with self.assertRaisesRegex(ValueError, "limite 10M confronti"):
                self.build()
        evaluate.assert_not_called()

    def test_ordinary_300_word_page_is_within_character_budget(self) -> None:
        text = " ".join(["report"] * 300)
        self.reference["text"] = text
        self.evidence["regions"] = [{
            "region_id": "r-300-words", "text": text,
            "geometry": {"bbox": [0, 0, 100, 100]},
        }]
        self.write_json("reference", self.reference)
        self.write_json("evidence", self.evidence)
        self.structure = reconstruct_document_structure(
            evidence=self.evidence, profile="leader_list_report"
        ).to_dict()
        self.write_json("structure", self.structure)
        result = self.build()
        self.assertEqual(result["reference_word_count"], 300)
        self.assertEqual(result["status"], "no_token_differences")

    def test_unverified_reference_and_stale_structure_are_rejected(self) -> None:
        self.reference["review_status"] = "draft"
        self.write_json("reference", self.reference)
        with self.assertRaisesRegex(ValueError, "human_verified/verified"):
            self.build()
        self.reference["review_status"] = "verified"
        self.write_json("reference", self.reference)
        self.structure["profile"] = "numbered_report"
        self.write_json("structure", self.structure)
        with self.assertRaisesRegex(ValueError, "divergente"):
            self.build()

    def test_image_mismatch_and_repository_output_are_rejected(self) -> None:
        self.image.write_bytes(b"changed image bytes")
        with self.assertRaisesRegex(ValueError, "Hash TIFF"):
            self.build()
        with self.assertRaisesRegex(ValueError, "fuori dal repository"):
            build_ocr_material_error_draft(
                reference_path=self.paths["reference"], evidence_path=self.paths["evidence"],
                structure_path=self.paths["structure"], image_path=self.paths["image"],
                output_path=ROOT_DIR / "should-not-be-created.json", apply=True,
            )

    def test_cli_preview_and_invalid_reference(self) -> None:
        args = ["documents", "ocr-material-error-draft"]
        for option in ("reference", "evidence", "structure", "image", "output"):
            args.extend(["--" + option, str(self.paths[option])])
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(stdout.getvalue())["operation_status"], "preview")
        self.reference["origin"] = "synthetic"
        self.write_json("reference", self.reference)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 1)


if __name__ == "__main__":
    unittest.main()
