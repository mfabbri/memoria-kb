from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.quality_gate_baseline import build_quality_gate_baseline  # noqa: E402


@contextmanager
def workspace_temp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"test-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class QualityGateBaselineTests(unittest.TestCase):
    def test_builds_preview_only_baseline_for_passed_targeted_gate(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            result = build_quality_gate_baseline(
                output_dir=tmp_dir,
                run_id="mvp-quality-gate-baseline",
                test_suite="Targeted",
                status="passed",
                command=".\\scripts\\run_quality_gate.ps1 -TestSuite Targeted",
                audit_output_json="risultati/source_quality_audit.json",
                audit_output_md="risultati/source_quality_audit.md",
                registry_validation_status="passed",
                source_quality_audit_status="passed",
            )
            payload = json.loads((tmp_dir / "quality_gate_baseline.json").read_text(encoding="utf-8"))
            markdown = (tmp_dir / "quality_gate_baseline.md").read_text(encoding="utf-8")
            serialized = json.dumps(payload, ensure_ascii=False) + markdown

        self.assertEqual(payload["@type"], "MvpQualityGateBaseline")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["test_suite"], "Targeted")
        self.assertEqual(payload["output_policy"], "preview-only")
        self.assertEqual(payload["review_status"], "unreviewed")
        self.assertEqual(payload["mvp_indicator"], "quality_gate_targeted_green")
        self.assertIn("quality_gate_baseline_json", result)
        self.assertIn("Baseline quality gate MVP", markdown)
        self.assertIn("risultati/source_quality_audit.json", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)


if __name__ == "__main__":
    unittest.main()
