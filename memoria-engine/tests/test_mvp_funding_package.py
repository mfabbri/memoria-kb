from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_funding_package import build_mvp_funding_package  # noqa: E402


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


def write_ready_run(root: Path) -> Path:
    run_dir = root / "run"
    write_json(
        run_dir / "mvp_package_readiness.json",
        {
            "@type": "MvpPackageReadiness",
            "readiness_status": "ready_for_demo",
            "profile_count": 3,
            "ready_profile_count": 3,
            "review_queue_item_count": 12,
            "pending_review_count": 12,
            "blockers": [],
        },
    )
    write_json(
        run_dir / "mvp_funding_dossier.json",
        {
            "@type": "MvpFundingDossier",
            "profile_count": 3,
            "ready_profile_count": 3,
            "review_queue_item_count": 12,
            "pending_review_count": 12,
        },
    )
    write_json(
        run_dir / "mvp_run_index.json",
        {
            "profile_ids": [
                "person:purocielo:andreoli-dino",
                "person:purocielo:balboni-william",
                "person:purocielo:bendini-ateo",
            ],
            "artifacts": [{"name": "vault_dir", "status": "present"}],
            "recommended_reading_order": [],
        },
    )
    write_json(
        run_dir / "schede_modello" / "manifest.json",
        {
            "@type": "MvpModelCardsBuild",
            "model_card_count": 3,
        },
    )
    for relative in [
        "mvp_run_index.md",
        "historian_review/review_queue.md",
        "mvp_pilot_cards_digest.md",
        "mvp_funding_dossier.md",
        "mvp_package_readiness.md",
        "schede_modello/README.md",
        "funding_excerpts/andreoli-dino.md",
        "historian_review/review_session.md",
        "historian_review/review_dashboard.md",
    ]:
        write_text(run_dir / relative)
    return run_dir


def write_descriptor_ready_run(root: Path) -> tuple[Path, Path]:
    run_dir = write_ready_run(root)
    write_json(
        run_dir / "schede_modello" / "manifest.json",
        {
            "@type": "MvpModelCardsBuild",
            "model_card_count": 0,
        },
    )
    for relative in [
        "mvp_consolidated_review_ledger.json",
        "mvp_demo_reconciliation_table.md",
        "historian_review/review_decisions_summary.json",
        "historian_review/verified_facts.preview.json",
        "historian_review/profile_patch.preview.json",
        "mvp_package_readiness.md",
        "historian_review/feedback_loop_outcome.t31-demo.md",
    ]:
        if relative.endswith(".json"):
            write_json(run_dir / relative, {"@type": "PreviewArtifact"})
        else:
            write_text(run_dir / relative)
    descriptor = {
        "run_id": "prova-preview-profili-5-reviewed-01-pipeline",
        "status": "ready_for_internal_demo",
        "preview_only": True,
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
    descriptor_path = write_json(root / "memoria_mvp_demo.active.json", descriptor)
    return run_dir, descriptor_path


class MvpFundingPackageTests(unittest.TestCase):
    def test_builds_go_with_review_blockers_for_ready_demo_with_pending_decisions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = write_ready_run(tmp_dir)

            result = build_mvp_funding_package(run_dir=run_dir, quality_gate_status="passed")
            checklist = json.loads((run_dir / "mvp_go_no_go_checklist.json").read_text(encoding="utf-8"))
            checklist_md = (run_dir / "mvp_go_no_go_checklist.md").read_text(encoding="utf-8")
            index_md = (run_dir / "funding_package_index.md").read_text(encoding="utf-8")
            serialized = json.dumps(checklist, ensure_ascii=False) + checklist_md + index_md

        self.assertEqual(result["overall_status"], "go_with_review_blockers")
        self.assertEqual(checklist["overall_status"], "go_with_review_blockers")
        self.assertEqual(checklist["model_card_count"], 3)
        self.assertIn("pending_review_decisions", serialized)
        self.assertIn("Pacchetto finanziatore Me.Mo.Ri.a", index_md)
        self.assertIn("Go/no-go checklist", index_md)
        self.assertIn("not_publishable_without_human_review", serialized)
        self.assertNotIn("ProfilePatch", serialized)
        self.assertNotIn("verified_facts", serialized)

    def test_descriptor_mode_uses_t33_scope_instead_of_legacy_pilot_cards(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir, descriptor_path = write_descriptor_ready_run(tmp_dir)

            result = build_mvp_funding_package(
                run_dir=run_dir,
                quality_gate_status="passed",
                demo_descriptor_json=descriptor_path,
            )
            checks = result["checklist"]["checks"]
            check_ids = {item["id"]: item["status"] for item in checks}
            index_md = (run_dir / "funding_package_index.md").read_text(encoding="utf-8")

        self.assertEqual(result["overall_status"], "go_with_review_blockers")
        self.assertEqual(result["checklist"]["profile_count"], 3)
        self.assertEqual(result["checklist"]["source_document_count"], 5)
        self.assertEqual(result["checklist"]["source_family_count"], 3)
        self.assertEqual(check_ids["demo_descriptor_ready"], "go")
        self.assertEqual(check_ids["demo_multi_source_coverage"], "go")
        self.assertNotIn("pilot_scope", check_ids)
        self.assertNotIn("model_cards", check_ids)
        self.assertIn("mvp_demo_reconciliation_table.md", index_md)
        self.assertIn("feedback_loop_outcome.t31-demo.md", index_md)

    def test_reports_no_go_when_required_outputs_are_missing(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = write_ready_run(tmp_dir)
            (run_dir / "mvp_funding_dossier.md").unlink()

            result = build_mvp_funding_package(run_dir=run_dir, quality_gate_status="passed")
            checklist = result["checklist"]
            blockers = [item for item in checklist["checks"] if item["status"] == "blocker"]

        self.assertEqual(result["overall_status"], "no_go_missing_outputs")
        self.assertTrue(any(item["id"] == "funding_dossier" for item in blockers))

    def test_quality_gate_not_recorded_is_a_blocker(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = write_ready_run(tmp_dir)

            result = build_mvp_funding_package(run_dir=run_dir)
            blockers = [item for item in result["checklist"]["checks"] if item["status"] == "blocker"]

        self.assertEqual(result["overall_status"], "no_go_missing_outputs")
        self.assertTrue(any(item["id"] == "quality_gate_targeted_green" for item in blockers))


if __name__ == "__main__":
    unittest.main()
