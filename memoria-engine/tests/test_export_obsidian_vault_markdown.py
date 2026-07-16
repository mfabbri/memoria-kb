from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.export_obsidian_vault_markdown import _mvp_document_markdown


class ExportObsidianVaultMarkdownTests(unittest.TestCase):
    def test_mvp_document_markdown_preserves_observable_shape(self) -> None:
        markdown = _mvp_document_markdown(
            document={
                "source_document_id": "doc-andreoli-1",
                "title": "Scheda Andreoli Dino",
                "document_class": "html_document",
                "quality_status": "ready_for_manual_review",
                "quality_path": "processed/doc-andreoli-1.quality.json",
                "review_status": "unreviewed",
            },
            payload={
                "review_status": "package_unreviewed",
            },
        )

        self.assertIn("type: mvp_pilot_document_review", markdown)
        self.assertIn('source_document_id: "doc-andreoli-1"', markdown)
        self.assertIn('review_status: "unreviewed"', markdown)
        self.assertIn("# Scheda Andreoli Dino", markdown)
        self.assertIn("- Classe: `html_document`", markdown)
        self.assertIn("- Stato qualita': `ready_for_manual_review`", markdown)
        self.assertIn("<!-- BEGIN AUTO-GENERATED -->", markdown)
        self.assertIn("<!-- END AUTO-GENERATED -->", markdown)


if __name__ == "__main__":
    unittest.main()
