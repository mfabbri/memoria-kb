from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from caduti_fonti_report.document_analysis.ocr_visual_review_ledger import audit_ocr_visual_review_ledger
from caduti_fonti_report.memoria_cli import main


class OcrVisualReviewLedgerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "page.tiff"
        Image.new("L", (20, 10), 255).save(self.image)
        self.crop = self.root / "crop.png"
        Image.new("L", (20, 10), 255).save(self.crop)
        image_hash = self.digest(self.image).removeprefix("sha256:")
        self.evidence = {
            "@type": "OcrPageEvidence", "page_id": "synthetic-1", "source_image_hash": image_hash,
            "source_page": {"frame_index": 0, "original_page": {
                "page_id": "synthetic-1", "source_image_hash": image_hash, "source_file": "page.tiff",
                "source_dimensions": {"width": 20, "height": 10}}},
            "transform_id": "original", "image_transform": None, "engine": "fixture",
            "model": {"name": "fixture"}, "language": "deu",
            "regions": [{"region_id": "r1", "text": "Text", "geometry": {"bbox": [0, 0, 20, 10]}}],
        }
        self.structure = {
            "@type": "DocumentStructure", "schema_version": "1.0", "page_id": "synthetic-1",
            "source_evidence": {k: v for k, v in self.evidence.items() if k not in ("@type", "regions")},
            "blocks": [{"block_id": "b1", "text": "Text", "source_region_ids": ["r1"]}],
        }
        self.write("evidence.json", self.evidence)
        self.write("structure.json", self.structure)
        self.ledger = {
            "@type": "OcrVisualReviewLedger", "schema_version": "1.0", "page_id": "synthetic-1",
            "source_image_hash": image_hash, "source_page": deepcopy(self.evidence["source_page"]),
            "frame_index": 0, "source_dimensions": {"width": 20, "height": 10},
            "source_evidence_digest": self.digest(self.root / "evidence.json"),
            "source_structure_digest": self.digest(self.root / "structure.json"),
            "review_tiles": [{"tile_id": "t1", "bbox": [0, 0, 20, 10]}],
            "observations": [self.observation("tile", "t1"), self.observation("block", "b1"),
                             self.observation("region", "r1")],
        }

    def observation(self, kind, key):
        result = {"observation_id": kind + ":" + key, "unit_type": kind, "unit_id": key,
                  "bbox": [0, 0, 20, 10], "outcome": "readable", "text": "Text",
                  "candidate_text": "Text", "crop_artifact": {"path": "crop.png", "digest": self.digest(self.crop)},
                  "observer": {"observer_id": "synthetic-observer", "model": "fixture-v1",
                               "configuration": "raw-v1", "observed_at": "2026-10-16T10:00:00Z"}}
        if kind == "block":
            result["source_region_ids"] = ["r1"]
        return result

    @staticmethod
    def digest(path):
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    def write(self, name, payload):
        (self.root / name).write_text(json.dumps(payload), encoding="utf-8")

    def audit(self):
        self.write("ledger.json", self.ledger)
        return audit_ocr_visual_review_ledger(ledger_path=self.root / "ledger.json", image_path=self.image,
            evidence_path=self.root / "evidence.json", structure_path=self.root / "structure.json")

    def assertBlocked(self, code):
        result = self.audit()
        self.assertEqual(result["processability_status"], "blocked")
        self.assertEqual(result["visual_coverage_status"], "blocked")
        self.assertIn(code, {i["code"] for i in result["checks"]["issues"]})

    def test_complete_fixture_is_coverage_only(self):
        result = self.audit()
        self.assertEqual(result["checks"]["issues"], [])
        self.assertEqual(result["visual_coverage_status"], "complete_for_declared_units")
        self.assertEqual(result["semantic_accuracy_status"], "not_attested")
        for field in ("human_review_request_allowed", "machine_pass", "human_verified", "gold_promotion_allowed"):
            self.assertFalse(result[field])
        self.assertTrue(result["preview_only"])

    def test_tiles_can_partition_page(self):
        self.ledger["review_tiles"] = [{"tile_id": "t1", "bbox": [0, 0, 10, 10]},
                                        {"tile_id": "t2", "bbox": [10, 0, 20, 10]}]
        self.ledger["observations"][0]["bbox"] = [0, 0, 10, 10]
        extra = self.observation("tile", "t2")
        extra["bbox"] = [10, 0, 20, 10]
        for observation, name, bbox in ((self.ledger["observations"][0], "tile-1.png", (0, 0, 10, 10)),
                                        (extra, "tile-2.png", (10, 0, 20, 10))):
            crop_path = self.root / name
            with Image.open(self.image) as image:
                image.crop(bbox).save(crop_path)
            observation["crop_artifact"] = {"path": name, "digest": self.digest(crop_path)}
        self.ledger["observations"].append(extra)
        self.assertEqual(self.audit()["checks"]["issues"], [])

    def test_gap_blocks(self):
        self.ledger["review_tiles"][0]["bbox"] = [0, 0, 19, 10]
        self.assertBlocked("tile_coverage_gap_or_excess")

    def test_overlap_blocks_even_when_total_area_equals_page(self):
        self.ledger["review_tiles"] = [{"tile_id": "a", "bbox": [0, 0, 10, 10]},
                                        {"tile_id": "b", "bbox": [5, 0, 15, 10]}]
        self.assertBlocked("tile_overlap")

    def test_duplicate_and_missing_block_observations(self):
        block = self.ledger["observations"][1]
        self.ledger["observations"].append(block | {"observation_id": "another"})
        self.assertBlocked("observation_coverage_mismatch")
        self.ledger["observations"] = [o for o in self.ledger["observations"] if o["unit_type"] != "block"]
        self.assertBlocked("observation_coverage_mismatch")

    def test_missing_region_and_extra_observations(self):
        self.ledger["observations"].pop()
        self.assertBlocked("observation_coverage_mismatch")
        self.ledger["observations"].append(self.observation("region", "unknown"))
        self.assertBlocked("unexpected_observation")

    def test_duplicate_ids_block(self):
        self.ledger["observations"].append(deepcopy(self.ledger["observations"][0]))
        self.assertBlocked("duplicate_unit")

    def test_stale_candidate_digest_blocks(self):
        self.structure["blocks"][0]["text"] = "Changed"
        self.write("structure.json", self.structure)
        self.assertBlocked("stale_input")

    def test_image_hash_and_frame_mismatch(self):
        self.ledger["source_image_hash"] = "0" * 64
        self.assertBlocked("image_hash_mismatch")
        self.ledger["frame_index"] = 1
        self.assertBlocked("unverifiable_image_frame")

    def test_page_identity_mismatch(self):
        self.ledger["page_id"] = "another-page"
        self.assertBlocked("page_identity_mismatch")

    def test_missing_crop_and_provenance(self):
        self.ledger["observations"][0].pop("crop_artifact")
        self.assertBlocked("missing_crop_artifact")
        self.ledger["observations"][1]["observer"] = True
        self.assertBlocked("missing_observer_provenance")

    def test_modified_crop_digest(self):
        self.crop.write_bytes(b"changed")
        self.assertBlocked("crop_hash_mismatch")

    def test_valid_crop_digest_does_not_substitute_for_source_pixel_match(self):
        Image.new("L", (20, 10), 0).save(self.crop)
        self.ledger["observations"][0]["crop_artifact"]["digest"] = self.digest(self.crop)
        self.assertBlocked("crop_pixel_mismatch")

    def test_empty_outcome_or_text_is_not_evidence(self):
        for field, value in (("outcome", True), ("text", " ")):
            with self.subTest(field=field):
                original = self.ledger["observations"][0][field]
                self.ledger["observations"][0][field] = value
                self.assertBlocked("empty_or_invalid_reading")
                self.ledger["observations"][0][field] = original

    def test_invalid_bbox_and_unsupported_frame_block(self):
        self.ledger["observations"][0]["bbox"] = [False, 0, 21, 10]
        self.assertBlocked("invalid_bbox")
        self.evidence["transform_id"] = "rotated"
        self.write("evidence.json", self.evidence)
        self.assertBlocked("unsupported_coordinate_frame")

    def test_missing_input_and_boolean_ledger_block(self):
        self.write("ledger.json", True)
        result = audit_ocr_visual_review_ledger(ledger_path=self.root / "ledger.json", image_path=self.image,
            evidence_path=self.root / "evidence.json", structure_path=self.root / "structure.json")
        self.assertEqual(result["processability_status"], "blocked")
        (self.root / "evidence.json").unlink()
        self.assertBlocked("unreadable_input")

    def test_duplicate_json_fields_block(self):
        self.audit()
        path = self.root / "ledger.json"
        path.write_text('{"@type":"OcrVisualReviewLedger","@type":true}', encoding="utf-8")
        result = audit_ocr_visual_review_ledger(ledger_path=path, image_path=self.image,
            evidence_path=self.root / "evidence.json", structure_path=self.root / "structure.json")
        self.assertEqual(result["processability_status"], "blocked")

    def test_missing_explicit_frame_blocks(self):
        self.evidence["source_page"].pop("frame_index")
        self.write("evidence.json", self.evidence)
        self.assertBlocked("frame_identity_mismatch")

    def test_candidate_text_links_and_observer_timestamp_are_bound(self):
        self.ledger["observations"][1]["candidate_text"] = "Stale"
        self.assertBlocked("candidate_observation_mismatch")
        self.ledger["observations"][0]["observer"]["observed_at"] = "2026-10-16T10:00:00"
        self.assertBlocked("invalid_observer_timestamp")

    def test_cli_preview_does_not_write_or_mutate_inputs(self):
        self.audit()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["documents", "ocr-visual-review-audit", "--ledger", str(self.root / "ledger.json"),
                         "--image", str(self.image), "--evidence", str(self.root / "evidence.json"),
                         "--structure", str(self.root / "structure.json")])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["operation_status"], "preview")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})


if __name__ == "__main__":
    unittest.main()
