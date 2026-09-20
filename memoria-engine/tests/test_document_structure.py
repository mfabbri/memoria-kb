from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from caduti_fonti_report.document_analysis.document_structure import (
    reconstruct_document_structure,
    render_document_structure_markdown,
)


FIXTURE = Path(__file__).parent / "fixtures" / "document_structure" / "t37-golden.json"


class DocumentStructureTest(unittest.TestCase):
    def test_synthetic_golden_profiles_preserve_provenance(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertTrue(payload["synthetic"])
        for case in payload["cases"]:
            with self.subTest(case=case["name"]):
                structure = reconstruct_document_structure(evidence=case["evidence"], profile=case["profile"])
                expected = case["expected"]
                self.assertEqual([block.kind for block in structure.blocks], expected["kinds"])
                self.assertEqual([list(block.source_region_ids) for block in structure.blocks], expected["sources"])
                self.assertEqual([block.status for block in structure.blocks], expected["statuses"])
                self.assertTrue(all(block.source_region_ids for block in structure.blocks))
                self.assertNotIn("confidence", structure.to_dict()["blocks"][0])
                markdown = render_document_structure_markdown(structure)
                for fragment in expected["markdown_fragments"]:
                    self.assertIn(fragment, markdown)
                for sources in expected["sources"]:
                    self.assertIn(", ".join(sources), markdown)
                self.assertIn('"source_page":{"page_number":', markdown)
                self.assertIn('"model":{"name":"synthetic"}', markdown)
                self.assertIn('"image_transform":', markdown)

    def test_renderer_rejects_non_structure_and_parser_rejects_non_evidence(self) -> None:
        with self.assertRaisesRegex(TypeError, "DocumentStructure"):
            render_document_structure_markdown(object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "OcrPageEvidence"):
            reconstruct_document_structure(evidence={"page_id": "synthetic"}, profile="numbered_report")

    def test_evidence_reference_distinguishes_transforms_with_same_region_ids(self) -> None:
        evidence = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"][0]["evidence"]
        raw = deepcopy(evidence)
        raw["transform_id"] = "raw"
        raw["image_transform"] = {"name": "raw"}
        contrast_structure = reconstruct_document_structure(evidence=evidence, profile="leader_list_report")
        raw_structure = reconstruct_document_structure(evidence=raw, profile="leader_list_report")
        self.assertEqual(contrast_structure.blocks[0].source_region_ids, raw_structure.blocks[0].source_region_ids)
        self.assertNotEqual(contrast_structure.source_evidence, raw_structure.source_evidence)
        self.assertEqual(contrast_structure.to_dict()["source_evidence"]["transform_id"], "contrast-x1.8")
        self.assertIn("Evidence transform ID: `raw`", render_document_structure_markdown(raw_structure))

    def test_geometry_less_region_is_uncertain_without_spatial_inference(self) -> None:
        evidence = deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"][1]["evidence"])
        evidence["regions"][1]["geometry"]["bbox"] = None
        structure = reconstruct_document_structure(evidence=evidence, profile="numbered_report")
        block = next(block for block in structure.blocks if block.source_region_ids == ("r-first",))
        self.assertEqual((block.kind, block.status, block.structure_confidence), ("unknown", "uncertain", 0.0))
        self.assertEqual(block.text, "This is a report paragraph")

    def test_same_region_dot_leader_and_duplicate_ids(self) -> None:
        evidence = deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"][0]["evidence"])
        evidence["regions"] = [{"region_id": "r-dot", "text": "Label .... 42", "confidence": 0.01,
                                "geometry": {"bbox": [10, 10, 200, 30]}}]
        structure = reconstruct_document_structure(evidence=evidence, profile="leader_list_report")
        self.assertEqual(structure.blocks[0].kind, "key_value")
        self.assertEqual((structure.blocks[0].text, structure.blocks[0].value), ("Label", "42"))
        evidence["regions"].append(deepcopy(evidence["regions"][0]))
        with self.assertRaisesRegex(ValueError, "duplicato"):
            reconstruct_document_structure(evidence=evidence, profile="leader_list_report")

    def test_alphanumeric_region_without_aligned_value_is_unrecognized(self) -> None:
        evidence = deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"][0]["evidence"])
        evidence["regions"] = [{"region_id": "r-alone", "text": "Unpaired label", "confidence": 0.99,
                                "geometry": {"bbox": [10, 10, 150, 30]}}]
        structure = reconstruct_document_structure(evidence=evidence, profile="leader_list_report")
        block = structure.blocks[0]
        self.assertEqual((block.kind, block.status, block.source_region_ids), ("unknown", "unrecognized", ("r-alone",)))
        self.assertIn("[illeggibile]", render_document_structure_markdown(structure))


if __name__ == "__main__":
    unittest.main()
