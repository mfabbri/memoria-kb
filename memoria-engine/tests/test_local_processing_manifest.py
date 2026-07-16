from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.local_processing_manifest import (  # noqa: E402
    build_running_step_record,
    build_skipped_step_record,
    duration_text,
    render_run_summary,
)


class LocalProcessingManifestTests(unittest.TestCase):
    def test_build_step_records_preserves_manifest_shape(self) -> None:
        running = build_running_step_record(
            name="metadata_extraction",
            started_at="2026-07-08T07:00:00+00:00",
            output_paths=[Path("run/document_analysis/document_metadata_extraction.json")],
            signature="abc123",
            input_snapshot=[{"path": "raw/a.txt", "sha256": "deadbeef"}],
            input_read_error_count=0,
            input_delta={"status": "changed", "added_count": 1},
        )
        skipped = build_skipped_step_record(
            name="ocr_batch",
            started_at="2026-07-08T07:00:00+00:00",
            finished_at="2026-07-08T07:00:01+00:00",
            status="skipped_not_enabled",
            reason="run_ocr_false",
            output_paths=[Path("run/document_analysis/ocr_batch_report.json")],
        )

        self.assertEqual(running["name"], "metadata_extraction")
        self.assertEqual(running["status"], "running")
        self.assertEqual(running["outputs"], ["run\\document_analysis\\document_metadata_extraction.json"])
        self.assertEqual(running["input_file_count"], 1)
        self.assertEqual(running["input_read_error_count"], 0)
        self.assertEqual(running["input_delta"], {"status": "changed", "added_count": 1})
        self.assertEqual(skipped["status"], "skipped_not_enabled")
        self.assertEqual(skipped["reason"], "run_ocr_false")
        self.assertEqual(skipped["input_snapshot"], [])

    def test_render_run_summary_preserves_observable_lines(self) -> None:
        summary = render_run_summary(
            {
                "run_id": "local-test",
                "status": "completed",
                "inputs": {
                    "root_dir": "raw",
                    "processed_dir": "processed",
                    "force_derived": False,
                    "force_ocr": False,
                },
                "steps": [
                    {
                        "name": "input_processing_plan",
                        "status": "completed",
                        "input_file_count": 2,
                        "input_delta": {
                            "status": "changed",
                            "added_count": 1,
                            "modified_count": 0,
                            "removed_count": 0,
                            "added": ["raw/a.txt"],
                        },
                        "summary": {"document_count": 2, "nested": {"b": 2, "a": 1}},
                    },
                    {
                        "name": "ocr_batch",
                        "status": "skipped_not_enabled",
                        "reason": "run_ocr_false",
                        "input_file_count": 0,
                    },
                ],
            }
        )

        self.assertIn("# Local document processing run", summary)
        self.assertIn("- Run ID: `local-test`", summary)
        self.assertIn("- `input_processing_plan`: `completed`", summary)
        self.assertIn("  - Delta input: changed, aggiunti=1, modificati=0, rimossi=0", summary)
        self.assertIn("  - Aggiunti: `raw/a.txt`", summary)
        self.assertIn("document_count=2, nested={a: 1, b: 2}", summary)
        self.assertIn("- `ocr_batch`: `skipped_not_enabled`", summary)
        self.assertIn("  - Motivo: run_ocr_false", summary)
        self.assertIn("- Il wrapper locale delta non esegue ricerche online automatiche.", summary)

    def test_duration_text_handles_iso_timestamps_and_invalid_values(self) -> None:
        self.assertEqual(
            duration_text("2026-07-08T07:00:00+00:00", "2026-07-08T07:00:01.500000+00:00"),
            "1.50s",
        )
        self.assertEqual(duration_text("not-a-date", "2026-07-08T07:00:01+00:00"), "")


if __name__ == "__main__":
    unittest.main()
