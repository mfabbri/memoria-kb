from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.document_analysis.ocr_comparison import compare_manifest_file  # noqa: E402


FIXTURE = ROOT_DIR / "tests" / "fixtures" / "ocr_reference" / "t38-synthetic.json"


class OcrComparisonTest(unittest.TestCase):
    def test_manifest_comparison_is_deterministic_and_keeps_synthetic_reference_ineligible(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reference.json").write_text(json.dumps(payload["reference"]), encoding="utf-8")
            (root / "evidence.json").write_text(json.dumps(payload["evidence"]), encoding="utf-8")
            manifest = {
                "@type": "OcrComparisonManifest",
                "schema_version": "1.0",
                "cases": [{
                    "case_id": "synthetic-00028-contrast",
                    "profile": "leader_list_report",
                    "reference_path": "reference.json",
                    "evidence_path": "evidence.json",
                }],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            first = compare_manifest_file(root / "manifest.json")
            second = compare_manifest_file(root / "manifest.json")
        self.assertEqual(first, second)
        self.assertEqual(first["case_count"], 1)
        self.assertEqual(first["accuracy_eligible_case_count"], 0)
        self.assertFalse(first["results"][0]["evaluation"]["accuracy_eligible"])

    def test_manifest_rejects_duplicate_case_ids_before_partial_report(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reference.json").write_text(json.dumps(payload["reference"]), encoding="utf-8")
            (root / "evidence.json").write_text(json.dumps(payload["evidence"]), encoding="utf-8")
            manifest = {
                "@type": "OcrComparisonManifest",
                "schema_version": "1.0",
                "cases": [{
                    "case_id": "duplicate",
                    "profile": "leader_list_report",
                    "reference_path": "reference.json",
                    "evidence_path": "evidence.json",
                }, {
                    "case_id": "duplicate",
                    "profile": "leader_list_report",
                    "reference_path": "reference.json",
                    "evidence_path": "evidence.json",
                }],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "case_id duplicato"):
                compare_manifest_file(root / "manifest.json")


if __name__ == "__main__":
    unittest.main()
