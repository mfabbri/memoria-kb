from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_package_readiness import (  # noqa: E402
    build_mvp_package_readiness,
)
from caduti_fonti_report.document_analysis.mvp_review_decisions import (  # noqa: E402
    build_mvp_review_decisions_summary,
)
from caduti_fonti_report.document_analysis.mvp_review_queue import build_mvp_review_queue  # noqa: E402
from tests.test_mvp_review_queue import write_mvp_summary  # noqa: E402


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


def build_review_fixture(root: Path) -> tuple[Path, Path, Path]:
    summary_json = write_mvp_summary(root / "document_analysis")
    review_dir = root / "historian_review"
    queue_json = review_dir / "review_queue.json"
    decisions_template_json = review_dir / "review_decisions.template.json"
    decisions_summary_json = review_dir / "review_decisions_summary.json"
    build_mvp_review_queue(
        summary_json=summary_json,
        output_json=queue_json,
        output_md=review_dir / "review_queue.md",
        decisions_template_json=decisions_template_json,
    )
    build_mvp_review_decisions_summary(
        review_queue_json=queue_json,
        decisions_json=decisions_template_json,
        output_json=decisions_summary_json,
        output_md=review_dir / "review_decisions_summary.md",
    )
    return summary_json, queue_json, decisions_summary_json


def write_demo_vault(root: Path) -> Path:
    vault_dir = root / "demo-vault"
    output_dir = vault_dir / "10_Output"
    publication_dir = vault_dir / "40_Publication_Candidates"
    output_dir.mkdir(parents=True)
    publication_dir.mkdir(parents=True)
    (output_dir / "MVP_Pilot_Review.md").write_text("# MVP Pilot Review\n", encoding="utf-8")
    (output_dir / "mvp_curatorial_brief.md").write_text("# Brief curatoriale\n", encoding="utf-8")
    (publication_dir / "andreoli-dino.md").write_text("# Andreoli Dino\n", encoding="utf-8")
    return vault_dir


class MvpPackageReadinessTests(unittest.TestCase):
    def test_reports_ready_for_demo_without_promoting_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "run"
            (run_dir / "document_analysis").mkdir(parents=True)
            summary_json, queue_json, decisions_summary_json = build_review_fixture(run_dir)
            vault_dir = write_demo_vault(tmp_dir)
            output_json = run_dir / "mvp_package_readiness.json"
            output_md = run_dir / "mvp_package_readiness.md"

            report = build_mvp_package_readiness(
                summary_json=summary_json,
                review_queue_json=queue_json,
                review_decisions_summary_json=decisions_summary_json,
                vault_dir=vault_dir,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False)

        self.assertEqual(report["@type"], "MvpPackageReadiness")
        self.assertEqual(persisted["readiness_status"], "ready_for_demo")
        self.assertEqual(persisted["missing_required_output_count"], 0)
        self.assertGreater(persisted["review_queue_item_count"], 0)
        self.assertEqual(persisted["publication_candidate_count"], 1)
        self.assertIn("Readiness pacchetto MVP", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)
        self.assertTrue(all(item["exists"] for item in persisted["required_outputs"]))

    def test_missing_outputs_are_reported_as_blockers(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            output_json = tmp_dir / "mvp_package_readiness.json"

            report = build_mvp_package_readiness(
                summary_json=tmp_dir / "missing-summary.json",
                review_queue_json=tmp_dir / "missing-queue.json",
                review_decisions_summary_json=tmp_dir / "missing-decisions.json",
                vault_dir=tmp_dir / "missing-vault",
                output_json=output_json,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(report["readiness_status"], "missing_required_outputs")
        self.assertGreaterEqual(persisted["missing_required_output_count"], 4)
        self.assertIn("missing_required_output", json.dumps(persisted, ensure_ascii=False))

    def test_document_intake_blockers_take_precedence_after_artifacts_exist(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "run"
            (run_dir / "document_analysis").mkdir(parents=True)
            summary_json, queue_json, decisions_summary_json = build_review_fixture(run_dir)
            summary = json.loads(summary_json.read_text(encoding="utf-8"))
            summary["document_intake_readiness"] = {
                "@type": "DocumentIntakeReadiness",
                "mvp_blockers": ["OCR mancante per documenti pilota."],
            }
            summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            vault_dir = write_demo_vault(tmp_dir)

            report = build_mvp_package_readiness(
                summary_json=summary_json,
                review_queue_json=queue_json,
                review_decisions_summary_json=decisions_summary_json,
                vault_dir=vault_dir,
            )

        self.assertEqual(report["readiness_status"], "needs_document_intake")
        self.assertEqual(report["document_intake_blockers"][0]["blocker_type"], "document_intake")

    def test_neutral_document_intake_message_does_not_block_demo_readiness(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "run"
            (run_dir / "document_analysis").mkdir(parents=True)
            summary_json, queue_json, decisions_summary_json = build_review_fixture(run_dir)
            summary = json.loads(summary_json.read_text(encoding="utf-8"))
            summary["document_intake_readiness"] = {
                "@type": "DocumentIntakeReadiness",
                "mvp_blockers": [
                    "Nessun blocco documentale evidente: passare alla revisione di link e claim candidati."
                ],
            }
            summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            vault_dir = write_demo_vault(tmp_dir)

            report = build_mvp_package_readiness(
                summary_json=summary_json,
                review_queue_json=queue_json,
                review_decisions_summary_json=decisions_summary_json,
                vault_dir=vault_dir,
            )

        self.assertEqual(report["readiness_status"], "ready_for_demo")
        self.assertEqual(report["document_intake_blockers"], [])


if __name__ == "__main__":
    unittest.main()
