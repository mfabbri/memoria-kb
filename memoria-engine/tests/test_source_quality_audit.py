from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.source_quality_audit import render_source_quality_audit_markdown, run_source_quality_audit
from caduti_fonti_report.source_catalog import resolve_source_registry_path


class SourceQualityAuditTests(unittest.TestCase):
    def test_real_registry_quality_audit_runs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        audit = run_source_quality_audit(repo_root=repo_root, registry_path=resolve_source_registry_path(repo_root))

        self.assertGreater(audit.source_count, 0)
        by_id = {item.source_id: item for item in audit.assessments}
        self.assertIn("oesta_ais_feldsuche", by_id)
        self.assertIn(by_id["oesta_ais_feldsuche"].candidate_quality, {"guarded", "good"})
        self.assertEqual(by_id["oesta_ais_feldsuche"].detail_level, "manual_review_only")

    def test_markdown_renders_quality_columns(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        audit = run_source_quality_audit(repo_root=repo_root, registry_path=resolve_source_registry_path(repo_root))

        markdown = render_source_quality_audit_markdown(audit)

        self.assertIn("| Fonte | Qualità candidati | Livello dettaglio |", markdown)
        self.assertIn("`oesta_ais_feldsuche`", markdown)


if __name__ == "__main__":
    unittest.main()
