from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.document_analysis.ocr_markdown import export_ocr_pages_markdown  # noqa: E402


class OcrMarkdownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = ROOT_DIR / ".tmp-tests" / f"ocr-markdown-{uuid.uuid4().hex}"
        self.tmp_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_preview_is_read_only_and_apply_writes_one_safe_file_per_page(self) -> None:
        root = self.tmp_dir / "ocr"
        output = self.tmp_dir / "markdown"
        self._write_document(root / "source" / "doc-1.text.json", source_document_id="doc-1", lines=[
            self._line(page_id="page-1", line_id="line-1", text="# untrusted\n```\ncontent"),
            self._line(page_id="page-2", line_id="line-2", text="second page", read_order=2),
        ])

        preview = export_ocr_pages_markdown(root_dir=root, output_dir=output)
        self.assertEqual([item["status"] for item in preview["documents"]], ["would_write", "would_write"])
        self.assertFalse(output.exists())

        applied = export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)
        self.assertEqual([item["status"] for item in applied["documents"]], ["written", "written"])
        page = (output / "doc-1" / "page-1.md").read_text(encoding="utf-8")
        self.assertIn("Source document ID: `doc-1`", page)
        self.assertIn("Source file: `raw/scan.jpg`", page)
        self.assertIn("OCR engine: `tesseract`", page)
        self.assertIn("Region ID: `region-1`", page)
        self.assertIn("Bounding box: `left=1; top=2; width=3; height=4`", page)
        self.assertIn("Read order: `1` (inferred; base: `page_top_then_left`)", page)
        self.assertIn("````text\n# untrusted\n```\ncontent\n````", page)

    def test_invalid_empty_existing_and_duplicate_outputs_are_isolated_per_document(self) -> None:
        root = self.tmp_dir / "ocr"
        output = self.tmp_dir / "markdown"
        (root / "bad.text.json").parent.mkdir(parents=True)
        (root / "bad.text.json").write_text("{ invalid", encoding="utf-8")
        self._write_document(root / "empty.text.json", source_document_id="empty", lines=[])
        self._write_document(root / "first.text.json", source_document_id="a/b", lines=[self._line(page_id="p/1", line_id="a")])
        self._write_document(root / "second.text.json", source_document_id="a-b", lines=[self._line(page_id="p-1", line_id="b")])

        report = export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)
        statuses = [item["status"] for item in report["documents"]]
        self.assertIn("skipped_invalid_json", statuses)
        self.assertIn("skipped_empty_layout", statuses)
        self.assertIn("written", statuses)
        self.assertIn("skipped_duplicate_output", statuses)
        rerun = export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)
        self.assertIn("skipped_existing_output", [item["status"] for item in rerun["documents"]])

    def test_preserves_unavailable_ocr_text_as_traceable_marker_in_preview_and_apply(self) -> None:
        root = self.tmp_dir / "ocr"
        output = self.tmp_dir / "markdown"
        rejected = root / "rejected.text.json"
        self._write_document(rejected, source_document_id="rejected", lines=[self._line(page_id="page", line_id="line", text="Testo")])
        rejected_payload = json.loads(rejected.read_text(encoding="utf-8"))
        rejected_payload["ocr_quality_gate_status"] = "insufficient"
        rejected.write_text(json.dumps(rejected_payload), encoding="utf-8")
        self._write_document(root / "mixed.text.json", source_document_id="mixed", lines=[
            self._line(page_id="page", line_id="noise", text="--- ???"),
            self._line(page_id="page", line_id="text", text="Riga valida", read_order=2),
        ])

        preview = export_ocr_pages_markdown(root_dir=root, output_dir=output)

        preview_item = next(item for item in preview["documents"] if item["source_document_id"] == "mixed")
        self.assertEqual(preview_item["status"], "would_write")
        self.assertEqual(preview_item["line_count"], 2)
        self.assertEqual(preview_item["skipped_empty_lines"], 0)
        self.assertEqual(preview_item["unavailable_text_lines"], 1)
        self.assertIn("skipped_insufficient_quality", [item["status"] for item in preview["documents"]])
        self.assertFalse(output.exists())

        report = export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)
        self.assertEqual(next(item for item in report["documents"] if item["source_document_id"] == "mixed")["status"], "written")
        page = (output / "mixed" / "page.md").read_text(encoding="utf-8")
        self.assertIn("Riga valida", page)
        self.assertIn("## OCR line `noise`", page)
        self.assertIn("Region ID: `region-1`", page)
        self.assertIn("Bounding box: `left=1; top=2; width=3; height=4`", page)
        self.assertIn("OCR text (untrusted): `OCR text unavailable`", page)
        self.assertNotIn("--- ???", page)

    def test_page_with_only_unavailable_ocr_rows_is_exported_with_provenance(self) -> None:
        root = self.tmp_dir / "ocr"
        output = self.tmp_dir / "markdown"
        empty = self._line(page_id="blank", line_id="empty", text="")
        whitespace = self._line(page_id="blank", line_id="whitespace", text=" \t\n", read_order=2)
        punctuation = self._line(page_id="blank", line_id="punctuation", text="--- ???", read_order=3)
        absent = self._line(page_id="blank", line_id="absent", text=None, read_order=4)
        for index, line in enumerate([empty, whitespace, punctuation, absent], start=1):
            line.update({"region_id": f"region-{index}", "left": index, "top": index + 1, "width": index + 2, "height": index + 3})
        self._write_document(root / "blank.text.json", source_document_id="blank", lines=[empty, whitespace, punctuation, absent])

        preview = export_ocr_pages_markdown(root_dir=root, output_dir=output)

        self.assertEqual(len(preview["documents"]), 1)
        preview_item = preview["documents"][0]
        self.assertEqual(preview_item["status"], "would_write")
        self.assertEqual(preview_item["line_count"], 4)
        self.assertEqual(preview_item["skipped_empty_lines"], 0)
        self.assertEqual(preview_item["unavailable_text_lines"], 4)
        self.assertFalse(output.exists())

        applied = export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)

        self.assertEqual(applied["documents"][0]["status"], "written")
        page = (output / "blank" / "blank.md").read_text(encoding="utf-8")
        self.assertEqual(page.count("OCR text (untrusted): `OCR text unavailable`"), 4)
        for index, line_id in enumerate(["empty", "whitespace", "punctuation", "absent"], start=1):
            self.assertIn(f"## OCR line `{line_id}`", page)
            self.assertIn(f"Region ID: `region-{index}`", page)
            self.assertIn(f"Bounding box: `left={index}; top={index + 1}; width={index + 2}; height={index + 3}`", page)
        self.assertNotIn("--- ???", page)
        self.assertNotIn("None", page)

    def test_legacy_low_confidence_payload_is_not_exported(self) -> None:
        root = self.tmp_dir / "ocr"
        output = self.tmp_dir / "markdown"
        path = root / "legacy.text.json"
        self._write_document(path, source_document_id="legacy", lines=[self._line(page_id="page", line_id="line", text="Testo incerto")])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["ocr_quality_status"] = "low_confidence"
        path.write_text(json.dumps(payload), encoding="utf-8")

        report = export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)

        self.assertEqual(report["documents"][0]["status"], "skipped_insufficient_quality")
        self.assertFalse(output.exists())

    def test_unknown_quality_gate_is_not_exported_even_with_low_confidence_text(self) -> None:
        root = self.tmp_dir / "ocr"
        output = self.tmp_dir / "markdown"
        path = root / "unknown-gate.text.json"
        self._write_document(path, source_document_id="unknown-gate", lines=[self._line(page_id="page", line_id="line", text="Testo incerto")])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["ocr_quality_status"] = "low_confidence"
        payload["ocr_quality_gate_status"] = "pending_calibration"
        path.write_text(json.dumps(payload), encoding="utf-8")

        report = export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)

        self.assertEqual(report["documents"][0]["status"], "skipped_insufficient_quality")
        self.assertFalse(output.exists())

    def test_metadata_values_cannot_break_inline_markdown(self) -> None:
        root = self.tmp_dir / "ocr"
        output = self.tmp_dir / "markdown"
        self._write_document(root / "doc.text.json", source_document_id="doc`\n# heading", raw_file="x`\n# injected", lines=[self._line(page_id="page", line_id="line`\n# bad")])
        export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)
        page = next(output.rglob("*.md")).read_text(encoding="utf-8")
        self.assertIn("Source document ID: `doc'", page)
        self.assertNotIn("\n# injected", page)
        self.assertIn("## OCR line `line'", page)

    def test_dot_path_components_and_untrusted_numeric_fields_are_safe(self) -> None:
        root = self.tmp_dir / "ocr"
        output = self.tmp_dir / "markdown"
        line = self._line(page_id="..", line_id="line")
        line.update({"left": "1`\n# injected", "confidence": "2`\n# injected", "read_order": "3`\n# injected"})
        self._write_document(root / "doc.text.json", source_document_id=".", lines=[line])
        export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)
        page_path = output / "unknown" / "unknown.md"
        self.assertTrue(page_path.is_file())
        page = page_path.read_text(encoding="utf-8")
        self.assertIn("left=unknown", page)
        self.assertIn("Confidence: `unknown`", page)
        self.assertIn("Read order: `unknown`", page)
        self.assertNotIn("\n# injected", page)

    def test_file_created_after_preflight_is_preserved(self) -> None:
        root = self.tmp_dir / "ocr"
        output = self.tmp_dir / "markdown"
        self._write_document(root / "doc.text.json", source_document_id="doc", lines=[self._line(page_id="page", line_id="line")])
        concurrent_path = output / "doc" / "page.md"

        def concurrent_write(path: Path, text: str) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("concurrent content", encoding="utf-8")
            raise FileExistsError(path)

        with patch("caduti_fonti_report.document_analysis.ocr_markdown._write_exclusive", side_effect=concurrent_write):
            report = export_ocr_pages_markdown(root_dir=root, output_dir=output, apply=True)

        self.assertEqual(report["documents"][0]["status"], "skipped_existing_output")
        self.assertEqual(concurrent_path.read_text(encoding="utf-8"), "concurrent content")

    def _write_document(self, path: Path, *, source_document_id: str, lines: list[dict[str, object]], raw_file: str = "raw/scan.jpg") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"@type": "ProcessedDocumentText", "source_document_id": source_document_id, "raw_file": raw_file, "ocr_engine": "tesseract", "ocr_language": "ita", "ocr_quality_status": "usable_for_preview", "review_status": "unreviewed", "ocr_layout_lines": lines}), encoding="utf-8")

    def _line(self, *, page_id: str, line_id: str, text: object = "text", read_order: int = 1) -> dict[str, object]:
        return {"page_id": page_id, "ocr_line_id": line_id, "region_id": "region-1", "text": text, "left": 1, "top": 2, "width": 3, "height": 4, "confidence": 80.5, "review_status": "unreviewed", "read_order": read_order, "read_order_status": "inferred", "read_order_basis": "page_top_then_left"}


if __name__ == "__main__":
    unittest.main()
