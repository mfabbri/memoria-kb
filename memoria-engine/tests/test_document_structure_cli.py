from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from caduti_fonti_report.document_analysis.structured_markdown import export_structured_pages_markdown
from caduti_fonti_report.memoria_cli import main as memoria_main


def evidence_payload() -> dict[str, object]:
    return {
        "@type": "OcrPageEvidence",
        "source_document_id": "synthetic-document",
        "page_id": "page-1",
        "source_image_hash": "hash-page-1",
        "transform_id": "synthetic:raw",
        "engine": "synthetic-ocr",
        "language": "deu",
        "source_page": {"page_number": 1},
        "model": {"name": "synthetic"},
        "image_transform": {"name": "raw"},
        "regions": [{"region_id": "r-1", "text": "1. Abschnitt", "geometry": {"bbox": [10, 10, 200, 40]}}],
    }


class DocumentStructureCliExportTest(unittest.TestCase):
    def test_preview_then_apply_is_idempotent_and_preserves_structure_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "evidence"
            output = Path(raw) / "markdown"
            root.mkdir()
            (root / "page.evidence.json").write_text(json.dumps(evidence_payload()), encoding="utf-8")

            preview = export_structured_pages_markdown(root_dir=root, output_dir=output, profile="numbered_report")
            self.assertEqual(preview["documents"][0]["status"], "would_write")
            self.assertTrue(preview["checkpoint_id"].startswith("sha256:"))
            self.assertEqual(preview["checkpoint_item_count"], 1)
            self.assertEqual(preview["checkpoint_manifest"]["status"], "would_create")
            self.assertEqual(preview["checkpoint_manifest"]["manifest"]["schema_version"], "1.0")
            self.assertEqual(preview["checkpoint_manifest"]["manifest"]["root"], str(root.resolve()))
            self.assertEqual(preview["checkpoint_manifest"]["manifest"]["profile"], "numbered_report")
            self.assertEqual(preview["checkpoint_manifest"]["manifest"]["item_count"], 1)
            self.assertEqual(preview["summary"]["counts_by_status"]["would_write"], 1)
            self.assertGreaterEqual(preview["duration_ms"], 0.0)
            self.assertGreaterEqual(preview["throughput_items_per_second"], 0.0)
            self.assertFalse(output.exists())

            applied = export_structured_pages_markdown(root_dir=root, output_dir=output, profile="numbered_report", apply=True)
            manifest_path = output / "structured-checkpoint.manifest.json"
            self.assertEqual(applied["checkpoint_manifest"]["status"], "created")
            self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8"))["checkpoint_id"], applied["checkpoint_id"])
            item = applied["documents"][0]
            self.assertEqual(item["status"], "written")
            text = Path(item["output_path"]).read_text(encoding="utf-8")
            self.assertIn("Document structure (unreviewed)", text)
            self.assertIn("Evidence source image hash: `hash-page-1`", text)

            repeated = export_structured_pages_markdown(root_dir=root, output_dir=output, profile="numbered_report", apply=True)
            self.assertEqual(repeated["documents"][0]["status"], "skipped_existing_output")
            self.assertEqual(repeated["checkpoint_id"], applied["checkpoint_id"])
            self.assertEqual(repeated["checkpoint_manifest"]["status"], "existing_compatible")

    def test_existing_mismatched_manifest_is_diagnostic_and_blocks_apply_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "evidence"
            output = Path(raw) / "markdown"
            root.mkdir()
            evidence = root / "page.evidence.json"
            evidence.write_text(json.dumps(evidence_payload()), encoding="utf-8")
            created = export_structured_pages_markdown(root_dir=root, output_dir=output, profile="numbered_report", apply=True)
            manifest_path = output / "structured-checkpoint.manifest.json"
            original_manifest = manifest_path.read_text(encoding="utf-8")
            changed_payload = evidence_payload()
            changed_payload["source_image_hash"] = "changed-hash"
            evidence.write_text(json.dumps(changed_payload), encoding="utf-8")

            preview = export_structured_pages_markdown(root_dir=root, output_dir=output, profile="numbered_report")
            self.assertEqual(preview["checkpoint_manifest"]["status"], "mismatch_existing_manifest")
            self.assertIn("checkpoint_id", preview["checkpoint_manifest"]["mismatches"])
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), original_manifest)

            blocked = export_structured_pages_markdown(root_dir=root, output_dir=output, profile="numbered_report", apply=True)
            self.assertEqual(blocked["checkpoint_manifest"]["status"], "mismatch_existing_manifest")
            self.assertEqual(blocked["documents"], [])
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), original_manifest)

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = memoria_main([
                    "documents", "structure", "--root", str(root), "--output-dir", str(output),
                    "--profile", "numbered_report", "--apply",
                ])
            self.assertEqual(exit_code, 1)
            self.assertIn("Mismatch manifest:", stdout.getvalue())
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), original_manifest)

    def test_checkpoint_changes_when_an_evidence_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            output = Path(temp_dir) / "output"
            root.mkdir()
            evidence = root / "page.evidence.json"
            first_payload = evidence_payload()
            evidence.write_text(json.dumps(first_payload), encoding="utf-8")
            first = export_structured_pages_markdown(root_dir=root, output_dir=output, profile="numbered_report")
            second_payload = dict(first_payload)
            second_payload["source_image_hash"] = "hash-page-2"
            evidence.write_text(json.dumps(second_payload), encoding="utf-8")
            second = export_structured_pages_markdown(root_dir=root, output_dir=output, profile="numbered_report")
            self.assertNotEqual(first["checkpoint_id"], second["checkpoint_id"])

    def test_skips_non_evidence_json_and_invalid_structure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "evidence"
            output = Path(raw) / "markdown"
            root.mkdir()
            (root / "other.evidence.json").write_text(json.dumps({"@type": "Other"}), encoding="utf-8")
            report = export_structured_pages_markdown(root_dir=root, output_dir=output, profile="numbered_report")
            self.assertEqual(report["documents"][0]["status"], "skipped_invalid_evidence")

    def test_cli_structure_is_preview_first(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "evidence"
            output = Path(raw) / "markdown"
            root.mkdir()
            (root / "page.evidence.json").write_text(json.dumps(evidence_payload()), encoding="utf-8")
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = memoria_main([
                    "documents", "structure", "--root", str(root), "--output-dir", str(output),
                    "--profile", "numbered_report",
                ])
            self.assertEqual(exit_code, 0)
            self.assertIn("preview read-only", stdout.getvalue())
            self.assertIn("Manifest checkpoint: would_create", stdout.getvalue())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
