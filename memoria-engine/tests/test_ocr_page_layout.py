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

from caduti_fonti_report.document_analysis.ocr_page_layout import audit_ocr_page_layout
from caduti_fonti_report.document_analysis.ocr_visual_review_ledger import audit_ocr_visual_review_ledger
from caduti_fonti_report.memoria_cli import main


class OcrPageLayoutTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        image = Image.new("L", (100, 100), 255)
        image.save(self.root / "page.tiff")
        image_hash = self.digest("page.tiff").removeprefix("sha256:")
        self.evidence = {
            "@type": "OcrPageEvidence", "page_id": "synthetic-1", "source_image_hash": image_hash,
            "source_page": {"frame_index": 0, "original_page": {
                "page_id": "synthetic-1", "source_image_hash": image_hash, "source_file": "page.tiff",
                "source_dimensions": {"width": 100, "height": 100}}},
            "transform_id": "original", "image_transform": None, "engine": "fixture",
            "model": {"name": "fixture"}, "language": "deu",
            "regions": [{"region_id": key, "text": text, "geometry": {"bbox": box}}
                        for key, text, box in (("a", "Raw", [0, 0, 20, 10]), ("b", "text", [20, 0, 40, 10]),
                            ("c", "Right", [50, 0, 100, 10]), ("d", "Second", [0, 20, 40, 30]),
                            ("e", "Cell", [50, 20, 100, 30]), ("footer", "1", [40, 90, 60, 100]))],
        }
        self.write("evidence.json", self.evidence)
        structure = {"@type": "DocumentStructure", "schema_version": "1.0", "page_id": "synthetic-1",
                     "source_evidence": {k: v for k, v in self.evidence.items() if k not in ("@type", "regions")},
                     "blocks": [{"block_id": r["region_id"], "text": r["text"],
                                 "source_region_ids": [r["region_id"]]} for r in self.evidence["regions"]]}
        self.write("structure.json", structure)
        observations = []
        units = [("tile", "page", [0, 0, 100, 100], "page")]
        units += [(kind, r["region_id"], r["geometry"]["bbox"], r["text"])
                  for kind in ("block", "region") for r in self.evidence["regions"]]
        for kind, key, box, text in units:
            crop_name = kind + key + ".png"
            image.crop(tuple(box)).save(self.root / crop_name)
            observation = {"observation_id": kind + key, "unit_type": kind, "unit_id": key,
                           "bbox": box, "outcome": "readable", "text": text, "candidate_text": text,
                           "crop_artifact": {"path": crop_name, "digest": self.digest(crop_name)},
                           "observer": {"observer_id": "synthetic", "model": "fixture", "configuration": "raw",
                                        "observed_at": "2026-10-16T10:00:00Z"}}
            if kind == "block":
                observation["source_region_ids"] = [key]
            observations.append(observation)
        ledger = {"@type": "OcrVisualReviewLedger", "schema_version": "1.0", "page_id": "synthetic-1",
                  "source_image_hash": image_hash, "source_page": deepcopy(self.evidence["source_page"]),
                  "frame_index": 0, "source_dimensions": {"width": 100, "height": 100},
                  "source_evidence_digest": self.digest("evidence.json"),
                  "source_structure_digest": self.digest("structure.json"),
                  "review_tiles": [{"tile_id": "page", "bbox": [0, 0, 100, 100]}],
                  "observations": observations}
        self.write("ledger.json", ledger)
        self.visual = audit_ocr_visual_review_ledger(ledger_path=self.root / "ledger.json",
            image_path=self.root / "page.tiff", evidence_path=self.root / "evidence.json",
            structure_path=self.root / "structure.json")
        self.assertEqual(self.visual["checks"]["issues"], [])
        self.write("visual.json", self.visual)
        self.layout = {"@type": "OcrPageLayout", "schema_version": "1.0", "page_id": "synthetic-1",
                       "source_image_hash": image_hash, "source_page": deepcopy(self.evidence["source_page"]),
                       "source_evidence_digest": self.digest("evidence.json"),
                       "source_visual_audit_digest": self.digest("visual.json"),
                       "columns": [{"column_id": "left", "column_index": 0},
                                   {"column_id": "right", "column_index": 1}],
                       "rows": [{"row_id": "row1", "row_index": 0, "bbox": [0, 0, 100, 10], "cells": [
                           self.cell("c1", 0, ["a", "b"], "Raw text", [0, 0, 40, 10]),
                           self.cell("c2", 1, ["c"], "Right", [50, 0, 100, 10])]},
                           {"row_id": "row2", "row_index": 1, "bbox": [0, 20, 100, 30], "cells": [
                           self.cell("c3", 0, ["d"], "Second", [0, 20, 40, 30]),
                           self.cell("c4", 1, ["e"], "Cell", [50, 20, 100, 30])]}],
                       "reading_order": ["c1", "c2", "c3", "c4"],
                       "exclusions": [{"region_id": "footer", "reason": "Page counter outside table"}]}

    @staticmethod
    def cell(key, index, links, text, box):
        return {"cell_id": key, "column_index": index, "source_region_ids": links,
                "joiner": " ", "text": text, "bbox": box}

    def digest(self, name):
        return "sha256:" + hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def write(self, name, payload):
        (self.root / name).write_text(json.dumps(payload), encoding="utf-8")

    def audit(self):
        self.write("layout.json", self.layout)
        return audit_ocr_page_layout(layout_path=self.root / "layout.json",
            evidence_path=self.root / "evidence.json", visual_audit_path=self.root / "visual.json")

    def assertBlocked(self, code):
        report = self.audit()
        self.assertEqual(report["processability_status"], "blocked")
        self.assertIn(code, {i["code"] for i in report["checks"]["issues"]})

    def test_two_column_fixture_computes_counts_and_is_only_diagnostic(self):
        report = self.audit()
        self.assertEqual(report["checks"]["issues"], [])
        self.assertEqual(report["counts"], {"rows": 2, "columns": 2, "cells": 4,
            "evidence_regions": 6, "cell_region_links": 5, "excluded_regions": 1})
        self.assertEqual(report["processability_status"], "diagnostic_only")
        self.assertEqual(report["semantic_accuracy_status"], "not_attested")
        for key in ("human_review_request_allowed", "machine_pass", "human_verified",
                    "gold_promotion_allowed", "claim_extraction_allowed"):
            self.assertIs(report[key], False)
        self.assertIs(report["preview_only"], True)

    def test_missing_and_duplicate_ownership(self):
        original = deepcopy(self.layout)
        changes = [lambda: self.layout.update(exclusions=[]),
                   lambda: self.layout["exclusions"].append(deepcopy(self.layout["exclusions"][0])),
                   lambda: self.layout["exclusions"].append({"region_id": "a", "reason": "duplicate"}),
                   lambda: self.layout["rows"][0]["cells"][0]["source_region_ids"].append("a"),
                   lambda: self.layout["rows"][0]["cells"][1]["source_region_ids"].append("a")]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                self.layout = deepcopy(original)
                change()
                self.assertBlocked("region_ownership_mismatch")

    def test_reading_order_permutation_required(self):
        for order in (["c1", "c2", "c3"], ["c1", "c2", "c3", "c3"], ["c1", "c2", "c3", "unknown"],
                      None, [{"cell": "c1"}]):
            with self.subTest(order=order):
                self.layout["reading_order"] = order
                self.assertBlocked("invalid_reading_order")

    def test_indexes_must_be_ordered_unique_contiguous_integers(self):
        original = deepcopy(self.layout)
        for target, field in (("rows", "row_index"), ("columns", "column_index")):
            for indexes in ([0, 0], [1, 0], [0, 2], [False, 1]):
                with self.subTest(target=target, indexes=indexes):
                    self.layout = deepcopy(original)
                    for item, value in zip(self.layout[target], indexes):
                        item[field] = value
                    self.assertBlocked("invalid_indexes")
        self.layout = deepcopy(original)
        self.layout["rows"][0]["cells"][1]["column_index"] = 0
        self.assertBlocked("invalid_indexes")

    def test_boxes_contain_cells_and_regions(self):
        self.layout["rows"][0]["cells"][0]["bbox"] = [0, 0, 19, 10]
        self.assertBlocked("cell_bbox_mismatch")
        self.layout["rows"][0]["bbox"] = [0, 0, 60, 10]
        self.assertBlocked("row_bbox_mismatch")
        self.layout["rows"][0]["cells"][0]["bbox"] = [0, 0, 101, 10]
        self.assertBlocked("invalid_bbox")

    def test_raw_text_and_explicit_allowed_joiner(self):
        cell = self.layout["rows"][0]["cells"][0]
        cell["text"] = "Corrected text"
        self.assertBlocked("cell_text_mismatch")
        cell["joiner"] = "-"
        self.assertBlocked("invalid_joiner")
        cell.pop("joiner")
        self.assertBlocked("invalid_joiner")
        for joiner in ("", " ", "\n"):
            cell.update(joiner=joiner, text=joiner.join(["Raw", "text"]))
            self.assertEqual(self.audit()["checks"]["issues"], [])

    def test_unknown_region_and_invalid_exclusions(self):
        self.layout["rows"][0]["cells"][0]["source_region_ids"] = ["unknown"]
        self.assertBlocked("invalid_region_links")
        self.layout["exclusions"] = [{"region_id": "unknown", "reason": "outside"}]
        self.assertBlocked("invalid_exclusion_region")
        self.layout["exclusions"] = [{"region_id": "footer", "reason": " "}]
        self.assertBlocked("missing_exclusion_reason")

    def test_empty_rows_cells_and_duplicate_ids(self):
        original = deepcopy(self.layout)
        self.layout["rows"][0]["cells"] = []
        self.assertBlocked("missing_units")
        self.layout = deepcopy(original)
        self.layout["rows"][0]["cells"][0]["source_region_ids"] = []
        self.assertBlocked("invalid_region_links")
        self.layout = deepcopy(original)
        self.layout["rows"][0]["cells"][0]["text"] = ""
        self.assertBlocked("cell_text_mismatch")
        for target in ("rows", "columns"):
            self.layout = deepcopy(original)
            self.layout[target].append(deepcopy(self.layout[target][0]))
            self.assertBlocked("duplicate_unit")
        self.layout = deepcopy(original)
        self.layout["rows"][1]["cells"][0]["cell_id"] = "c1"
        self.assertBlocked("duplicate_unit")

    def test_stale_evidence_and_visual_report(self):
        (self.root / "evidence.json").write_text(json.dumps(self.evidence) + "\n", encoding="utf-8")
        self.assertBlocked("stale_input")
        self.layout["source_evidence_digest"] = self.digest("evidence.json")
        self.assertBlocked("visual_audit_identity_mismatch")
        self.write("evidence.json", self.evidence)
        self.layout["source_evidence_digest"] = self.digest("evidence.json")
        (self.root / "visual.json").write_text(json.dumps(self.visual) + "\n", encoding="utf-8")
        self.assertBlocked("stale_input")

    def test_visual_report_must_be_successful_and_same_image(self):
        original = deepcopy(self.visual)
        for field, value in (("processability_status", "blocked"), ("human_review_request_allowed", True),
                             ("visual_coverage_status", "blocked"), ("checks", {"issues": [], "issue_count": 1})):
            with self.subTest(field=field):
                self.visual = deepcopy(original)
                self.visual[field] = value
                self.write("visual.json", self.visual)
                self.layout["source_visual_audit_digest"] = self.digest("visual.json")
                self.assertBlocked("unsuccessful_visual_audit")
        self.visual = deepcopy(original)
        self.visual["inputs"]["image"]["digest"] = "sha256:" + "0" * 64
        self.write("visual.json", self.visual)
        self.layout["source_visual_audit_digest"] = self.digest("visual.json")
        self.assertBlocked("visual_audit_identity_mismatch")

    def test_page_and_frame_identity(self):
        self.layout["source_page"]["frame_index"] = 1
        self.assertBlocked("page_identity_mismatch")
        self.layout["page_id"] = "other"
        self.assertBlocked("page_identity_mismatch")

    def test_bad_json_and_nonobject_inputs_block(self):
        for raw in ('{"rows": [], "rows": []}', '{"rows": NaN}', '[]'):
            (self.root / "visual.json").write_text(raw, encoding="utf-8")
            self.assertBlocked("invalid_input")

    def test_cli_preview_and_blocked_exit_without_writes(self):
        self.audit()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        args = ["documents", "ocr-layout-audit", "--layout", str(self.root / "layout.json"),
                "--evidence", str(self.root / "evidence.json"), "--visual-audit", str(self.root / "visual.json")]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["operation_status"], "preview")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.layout["exclusions"] = []
        self.audit()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 1)


if __name__ == "__main__":
    unittest.main()
