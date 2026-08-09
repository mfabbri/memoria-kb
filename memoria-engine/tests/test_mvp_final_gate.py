from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_final_gate import (  # noqa: E402
    build_mvp_final_gate_report,
    render_mvp_final_gate_markdown,
)


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


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_text(path: Path, text: str = "preview-only\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_t33_candidate(root: Path) -> tuple[Path, Path, Path]:
    run_dir = root / "risultati" / "runs" / "funding-demo-golden-3cases-v1-pipeline"
    for relative in [
        "mvp_consolidated_review_ledger.json",
        "historian_review/review_decisions_summary.json",
        "historian_review/verified_facts.preview.json",
        "historian_review/profile_patch.preview.json",
        "mvp_go_no_go_checklist.json",
    ]:
        write_json(run_dir / relative, {"@type": "PreviewArtifact"})
    for relative in [
        "mvp_demo_reconciliation_table.md",
        "mvp_package_readiness.md",
        "mvp_go_no_go_checklist.md",
        "funding_package_index.md",
        "mvp_funding_dossier.md",
        "historian_review/feedback_loop_outcome.t31-demo.md",
    ]:
        write_text(run_dir / relative)
    checklist = {
        "@type": "MvpGoNoGoChecklist",
        "overall_status": "go_with_review_blockers",
        "pending_review_count": 68,
    }
    write_json(run_dir / "mvp_go_no_go_checklist.json", checklist)
    descriptor = {
        "contract_version": "memoria_mvp_demo.v1",
        "status": "ready_for_internal_demo",
        "preview_only": True,
        "publication_status": "not_publishable_without_human_review",
        "run_id": "funding-demo-golden-3cases-v1-pipeline",
        "run_dir": str(run_dir),
        "primary_profile_ids": ["person:purocielo:andreoli-dino"],
        "contrast_profile_ids": [
            "person:purocielo:balboni-william",
            "person:purocielo:bendini-ateo",
        ],
        "source_document_ids": [
            "legacy_csv:a4ac96061a2381b5",
            "local_docx:4c2ad1d2ab937913",
            "partigiani_italia:b45553cd6b1673d8",
            "partigiani_italia:b6b3c9e526723a27",
            "partigiani_italia:dadc75fad9db03ae",
        ],
        "source_families": ["legacy_csv", "local_docx", "partigiani_italia"],
        "readiness": {
            "selected_document_count": 5,
            "covered_document_count": 5,
            "missing_source_families": [],
        },
        "safety": {
            "publication_ready": False,
            "modifies_canonical_profiles": False,
            "applies_profile_patch": False,
            "creates_canonical_verified_facts": False,
        },
        "artifacts": {
            "ledger": str(run_dir / "mvp_consolidated_review_ledger.json"),
            "reconciliation_table": str(run_dir / "mvp_demo_reconciliation_table.md"),
            "review_decisions_summary": str(run_dir / "historian_review" / "review_decisions_summary.json"),
            "verified_facts_preview": str(run_dir / "historian_review" / "verified_facts.preview.json"),
            "profile_patch_preview": str(run_dir / "historian_review" / "profile_patch.preview.json"),
            "readiness_report": str(run_dir / "mvp_package_readiness.md"),
        },
    }
    candidate_descriptor = write_json(run_dir / "memoria_mvp_demo.candidate.json", descriptor)
    active_descriptor = write_json(
        root / "database" / "memoria_mvp_demo.active.json",
        {
            "contract_version": "memoria_mvp_demo.v1",
            "run_id": "prova-preview-profili-5-reviewed-01-pipeline",
            "status": "ready_for_internal_demo",
        },
    )
    return run_dir, candidate_descriptor, active_descriptor


class MvpFinalGateTests(unittest.TestCase):
    def test_ready_candidate_returns_human_gate_status_without_allowing_promotion(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir, candidate_descriptor, active_descriptor = write_t33_candidate(tmp_dir)

            report = build_mvp_final_gate_report(
                run_dir=run_dir,
                candidate_descriptor_json=candidate_descriptor,
                active_descriptor_json=active_descriptor,
            )
            markdown = render_mvp_final_gate_markdown(report)

        self.assertEqual(report["gate_status"], "ready_for_human_approval")
        self.assertTrue(report["human_approval_required"])
        self.assertFalse(report["promotion_allowed_by_report"])
        self.assertEqual(report["blocker_count"], 0)
        self.assertEqual(report["review_blocker_count"], 1)
        checks = {item["id"]: item["status"] for item in report["checks"]}
        self.assertEqual(checks["candidate_scope_profiles"], "go")
        self.assertEqual(checks["candidate_scope_documents"], "go")
        self.assertEqual(checks["candidate_artifacts_present"], "go")
        self.assertEqual(checks["active_descriptor_still_separate"], "go")
        self.assertEqual(checks["pending_review_decisions"], "review_blocker")
        self.assertIn("ready_for_human_approval", markdown)
        self.assertIn("promotion_allowed_by_report: false", markdown)
        self.assertIn("Non modifica `memoria_mvp_demo.active.json`", markdown)

    def test_blocks_when_candidate_would_modify_canonical_profiles(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir, candidate_descriptor, active_descriptor = write_t33_candidate(tmp_dir)
            payload = json.loads(candidate_descriptor.read_text(encoding="utf-8"))
            payload["safety"]["modifies_canonical_profiles"] = True
            candidate_descriptor.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            report = build_mvp_final_gate_report(
                run_dir=run_dir,
                candidate_descriptor_json=candidate_descriptor,
                active_descriptor_json=active_descriptor,
            )

        checks = {item["id"]: item["status"] for item in report["checks"]}
        self.assertEqual(report["gate_status"], "blocked_for_human_approval")
        self.assertGreater(report["blocker_count"], 0)
        self.assertEqual(checks["candidate_preview_only"], "blocker")

    def test_blocks_when_artifact_points_outside_candidate_run(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir, candidate_descriptor, active_descriptor = write_t33_candidate(tmp_dir)
            outside = write_json(tmp_dir / "other-run" / "ledger.json", {})
            payload = json.loads(candidate_descriptor.read_text(encoding="utf-8"))
            payload["artifacts"]["ledger"] = str(outside)
            candidate_descriptor.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            report = build_mvp_final_gate_report(
                run_dir=run_dir,
                candidate_descriptor_json=candidate_descriptor,
                active_descriptor_json=active_descriptor,
            )

        checks = {item["id"]: item["status"] for item in report["checks"]}
        self.assertEqual(report["gate_status"], "blocked_for_human_approval")
        self.assertEqual(checks["candidate_artifacts_present"], "blocker")


if __name__ == "__main__":
    unittest.main()
