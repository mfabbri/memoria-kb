from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))
try:
    from caduti_fonti_report.document_analysis.mvp_document_intake_preflight import (
        build_mvp_document_intake_preflight,
    )
finally:
    sys.path.pop(0)


class MvpDocumentIntakePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = ROOT_DIR / ".tmp-tests" / self.id().replace(".", "_")
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def test_missing_structure_reports_blockers_without_creating_directories(self) -> None:
        workspace = self.tmp_dir / "workspace"
        workspace.mkdir()

        report = build_mvp_document_intake_preflight(workspace_root=workspace)

        mvp_root = workspace / "documenti_da_processare" / "mvp_purocielo"
        self.assertFalse(mvp_root.exists())
        self.assertEqual(report["document_count"], 0)
        self.assertTrue(any("Manca la root documenti MVP" in blocker for blocker in report["blockers"]))
        self.assertTrue(any("Nessun documento" in blocker for blocker in report["blockers"]))

    def test_ensure_structure_creates_intake_directories_and_writes_outputs(self) -> None:
        workspace = self.tmp_dir / "workspace"
        profiles_dir = workspace / "ricerche" / "mvp"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "pilot_profiles.purocielo.json").write_text(
            "\ufeff" + json.dumps({"profiles": [{"profile_id": "person:purocielo:test"}]}),
            encoding="utf-8",
        )
        output_json = workspace / "risultati" / "preflight.json"
        output_md = workspace / "risultati" / "preflight.md"

        report = build_mvp_document_intake_preflight(
            workspace_root=workspace,
            output_json=output_json,
            output_md=output_md,
            ensure_structure=True,
        )

        self.assertEqual(report["pilot_profile_count"], 1)
        self.assertTrue((workspace / "documenti_da_processare" / "mvp_purocielo" / "html_salvati").is_dir())
        self.assertTrue(output_json.exists())
        self.assertTrue(output_md.exists())
        self.assertIn("P:\\Comune\\Me.Mo.Ri.a", output_md.read_text(encoding="utf-8"))

    def test_counts_documents_and_sidecars(self) -> None:
        workspace = self.tmp_dir / "workspace"
        profiles_dir = workspace / "ricerche" / "mvp"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "pilot_profiles.purocielo.json").write_text(
            json.dumps({"profiles": [{"profile_id": "person:purocielo:test"}]}),
            encoding="utf-8",
        )
        html_dir = workspace / "documenti_da_processare" / "mvp_purocielo" / "html_salvati"
        scan_dir = workspace / "documenti_da_processare" / "mvp_purocielo" / "scansioni"
        html_dir.mkdir(parents=True)
        scan_dir.mkdir(parents=True)
        (html_dir / "lolli.html").write_text("<html></html>", encoding="utf-8")
        (html_dir / "lolli.html.document.yaml").write_text("review_status: unreviewed\n", encoding="utf-8")
        (scan_dir / "page.jpg").write_bytes(b"jpg")

        report = build_mvp_document_intake_preflight(workspace_root=workspace, ensure_structure=True)

        self.assertEqual(report["document_count"], 2)
        self.assertEqual(report["sidecar_count"], 1)
        self.assertEqual(report["text_like_document_count"], 1)
        self.assertEqual(report["image_document_count"], 1)
        self.assertTrue(any("sidecar" in blocker for blocker in report["blockers"]))


if __name__ == "__main__":
    unittest.main()
