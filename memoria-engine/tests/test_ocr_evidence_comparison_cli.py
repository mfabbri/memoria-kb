from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.memoria_cli import main  # noqa: E402


def evidence(engine: str, region_id: str, text: str, bbox: list[int]) -> dict:
    digest = "a" * 64
    return {
        "@type": "OcrPageEvidence", "page_id": "synthetic-page", "source_image_hash": digest,
        "engine": engine, "model": {"name": engine}, "language": "deu",
        "transform_id": "raw", "image_transform": {"name": "raw"},
        "source_page": {"original_page": {
            "page_id": "synthetic-page", "source_image_hash": digest,
            "source_file": "synthetic.tif", "source_dimensions": {"width": 100, "height": 50},
        }},
        "regions": [{"region_id": region_id, "text": text, "geometry": {"bbox": bbox}}],
    }


class OcrEvidenceComparisonCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.left_path = self.root / "left.json"
        self.right_path = self.root / "right.json"
        self.output_path = self.root / "comparison.json"
        self.left = evidence("engine-a", "left-1", "REPORT", [5, 5, 50, 20])
        self.right = evidence("engine-b", "right-1", "REPPROT", [6, 5, 51, 20])
        self._write(self.left_path, self.left)
        self._write(self.right_path, self.right)

    @staticmethod
    def _write(path: Path, value: dict) -> bytes:
        raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path.write_bytes(raw)
        return raw

    def _run(self, *, apply: bool = False) -> tuple[int, dict, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        args = ["documents", "ocr-evidence-compare", "--left", str(self.left_path),
                "--right", str(self.right_path), "--output", str(self.output_path)]
        if apply:
            args.append("--apply")
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(args)
        return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, stderr.getvalue()

    def test_preview_reports_provenance_without_writing_or_authorizing_validation(self) -> None:
        left_raw, right_raw = self.left_path.read_bytes(), self.right_path.read_bytes()
        code, report, stderr = self._run()
        self.assertEqual((code, stderr), (0, ""))
        self.assertFalse(self.output_path.exists())
        self.assertEqual(report["operation_status"], "preview")
        self.assertEqual(report["disagreements"][0]["left_text"], "REPORT")
        self.assertEqual(report["disagreements"][0]["right_text"], "REPPROT")
        self.assertEqual(report["inputs"]["left"]["sha256"], hashlib.sha256(left_raw).hexdigest())
        self.assertEqual(report["inputs"]["right"]["sha256"], hashlib.sha256(right_raw).hexdigest())
        self.assertTrue(report["diagnostic_only"])
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])
        self.assertEqual(report["semantic_accuracy_status"], "not_attested")
        self.assertEqual(report["review_status"], "unreviewed")
        self.assertEqual(report["promotion_status"], "unreviewed")
        self.assertEqual((self.left_path.read_bytes(), self.right_path.read_bytes()), (left_raw, right_raw))

    def test_apply_writes_report_once_and_refuses_existing_output(self) -> None:
        code, report, stderr = self._run(apply=True)
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(report["operation_status"], "written")
        persisted = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["operation_status"], "written")
        self.assertEqual(persisted["left_evidence"]["page_id"], "synthetic-page")
        self.output_path.write_text("keep", encoding="utf-8")
        code, _, stderr = self._run(apply=True)
        self.assertEqual(code, 1)
        self.assertIn("File exists", stderr)
        self.assertEqual(self.output_path.read_text(encoding="utf-8"), "keep")

    def test_incompatible_evidence_fails_before_creating_report(self) -> None:
        incompatible = evidence("engine-b", "right-1", "REPPROT", [6, 5, 51, 20])
        incompatible["page_id"] = "other-page"
        incompatible["source_page"]["original_page"]["page_id"] = "other-page"
        self._write(self.right_path, incompatible)
        code, report, stderr = self._run(apply=True)
        self.assertEqual(code, 1)
        self.assertEqual(report, {})
        self.assertIn("Incompatible OCR evidence page_id", stderr)
        self.assertFalse(self.output_path.exists())


if __name__ == "__main__":
    unittest.main()
