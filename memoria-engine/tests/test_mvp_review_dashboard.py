from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_review_dashboard import (  # noqa: E402
    build_mvp_review_dashboard,
    render_mvp_review_dashboard_markdown,
)
from caduti_fonti_report.document_analysis.mvp_review_dashboard_markdown import (  # noqa: E402
    render_mvp_review_dashboard_markdown as render_dashboard_markdown,
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


def write_dashboard_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    review_session_json = write_json(
        root / "historian_review" / "review_session.json",
        {
            "@type": "MvpReviewSessionPack",
            "review_status": "unreviewed",
            "publication_status": "not_publishable_without_curator_review",
            "profile_count": 1,
            "review_focus": {
                "profiles": [
                    {
                        "profile_id": "person:purocielo:andreoli-dino",
                        "canonical_name": "Andreoli Dino",
                        "items": [
                            {
                                "item_id": "mvp-review-item:0001",
                                "item_type": "person_document_link_review",
                                "subject_kind": "person",
                                "source_document_id": "doc-andreoli",
                                "question": "Questo documento riguarda davvero Andreoli Dino?",
                                "decision_status": "pending",
                                "selected_action": "pending",
                            }
                        ],
                    }
                ],
            },
            "review_focus_decisions_template": {
                "decisions": [{"item_id": "mvp-review-item:0001", "selected_action": ""}]
            },
            "profiles": [
                {
                    "profile_id": "person:purocielo:andreoli-dino",
                    "canonical_name": "Andreoli Dino",
                    "pilot_card_status": "ready_for_review",
                    "model_card_review_status": "in_historical_review",
                    "review_session_status": "not_started",
                    "review_item_count": 2,
                    "pending_decision_count": 2,
                    "accepted_decision_count": 0,
                    "invalid_decision_count": 0,
                    "document_count": 2,
                    "candidate_evidence_claim_count": 1,
                    "reviewable_document_signal_count": 1,
                    "candidate_card_path": "vault/40_Publication_Candidates/andreoli-dino.md",
                    "next_action": "Completare la review storica.",
                    "review_focus_items": [
                        {
                            "item_id": "mvp-review-item:0001",
                            "item_type": "person_document_link_review",
                            "subject_kind": "person",
                            "source_document_id": "doc-andreoli",
                            "question": "Questo documento riguarda davvero Andreoli Dino?",
                            "decision_status": "pending",
                            "selected_action": "pending",
                        }
                    ],
                }
            ],
        },
    )
    review_queue_json = write_json(
        root / "historian_review" / "review_queue.json",
        {
            "@type": "HistorianReviewQueue",
            "item_count": 2,
            "items": [
                {
                    "item_id": "mvp-review-item:0001",
                    "item_type": "person_document_link_review",
                    "subject_kind": "person",
                    "priority": "high",
                    "profile_id": "person:purocielo:andreoli-dino",
                },
                {
                    "item_id": "mvp-review-item:0002",
                    "item_type": "candidate_claim_review",
                    "subject_kind": "date",
                    "priority": "medium",
                    "profile_id": "person:purocielo:andreoli-dino",
                },
            ],
        },
    )
    decisions_json = write_json(
        root / "historian_review" / "review_decisions_summary.json",
        {
            "@type": "MvpReviewDecisionsSummary",
            "review_status": "pending_review",
            "pending_count": 2,
            "accepted_count": 0,
            "invalid_count": 0,
            "review_session": {"session_status": "not_started"},
        },
    )
    ledger_json = write_json(
        root / "mvp_consolidated_review_ledger.json",
        {
            "@type": "MvpConsolidatedReviewLedger",
            "evidence_store_coverage": {
                "enabled": True,
                "record_count": 4,
                "profiles_with_records_count": 1,
                "unscoped_record_count": 0,
            },
        },
    )
    return review_session_json, review_queue_json, decisions_json, ledger_json


class MvpReviewDashboardTests(unittest.TestCase):
    def test_builds_preview_only_dashboard_without_promoting_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, review_queue_json, decisions_json, ledger_json = write_dashboard_fixture(tmp_dir)
            output_json = tmp_dir / "historian_review" / "review_dashboard.json"
            output_md = tmp_dir / "historian_review" / "review_dashboard.md"

            dashboard = build_mvp_review_dashboard(
                review_session_json=review_session_json,
                review_queue_json=review_queue_json,
                review_decisions_summary_json=decisions_json,
                consolidated_ledger_json=ledger_json,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False) + markdown

        self.assertEqual(dashboard["@type"], "MvpReviewDashboard")
        self.assertEqual(persisted["review_status"], "unreviewed")
        self.assertEqual(persisted["publication_status"], "not_publishable_without_human_review")
        self.assertEqual(persisted["profile_count"], 1)
        self.assertEqual(persisted["review_queue_item_count"], 2)
        self.assertEqual(persisted["pending_decision_count"], 2)
        self.assertEqual(persisted["subject_kind_counts"]["person"], 1)
        self.assertEqual(persisted["subject_kind_counts"]["date"], 1)
        self.assertEqual(persisted["profiles"][0]["model_card_review_status"], "in_historical_review")
        self.assertTrue(persisted["output_policy"]["preview_only"])
        self.assertFalse(persisted["output_policy"]["applies_review_decisions"])
        self.assertFalse(persisted["output_policy"]["creates_validated_facts"])
        self.assertFalse(persisted["output_policy"]["modifies_profiles"])
        self.assertIn("Review dashboard MVP", markdown)
        self.assertIn("Decisioni pending: `2`", markdown)
        self.assertIn("Oggetti da decidere", markdown)
        self.assertIn("Andreoli Dino", markdown)
        self.assertIn("Questo documento riguarda davvero Andreoli Dino?", markdown)
        self.assertIn("Le decisioni vuote restano `pending`", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_markdown_handles_empty_dashboard(self) -> None:
        markdown = render_mvp_review_dashboard_markdown({"profiles": [], "work_files": []})

        self.assertIn("Review dashboard MVP", markdown)
        self.assertIn("_Nessun profilo nella dashboard._", markdown)
        self.assertIn("Dashboard generata automaticamente", markdown)

    def test_markdown_renderer_keeps_front_matter_counts_and_warnings(self) -> None:
        markdown = render_dashboard_markdown(
            {
                "review_status": 'needs "historian"',
                "publication_status": "not_publishable_without_human_review",
                "subject_kind_counts": {"person": "2"},
                "profiles": [],
                "work_files": [{"label": "Sessione", "path": "historian_review/review_session.json"}],
                "warnings": ["Le decisioni vuote restano pending."],
            }
        )

        self.assertIn('review_status: "needs \\"historian\\""', markdown)
        self.assertIn("- Sessione: `historian_review/review_session.json`", markdown)
        self.assertIn("| `person` | 2 |", markdown)
        self.assertIn("- Le decisioni vuote restano pending.", markdown)

    def test_dashboard_summarizes_verified_facts_preview_when_present(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, review_queue_json, decisions_json, ledger_json = write_dashboard_fixture(tmp_dir)
            verified_preview_json = write_json(
                tmp_dir / "historian_review" / "verified_facts.preview.json",
                {
                    "@type": "VerifiedFactsPreview",
                    "review_status": "preview-only",
                    "publication_status": "not_publishable_without_editorial_review",
                    "preview_only": True,
                    "fact_count": 1,
                    "excluded_decision_count": 2,
                    "counts_by_profile": {"person:purocielo:andreoli-dino": 1},
                    "facts": [
                        {
                            "fact_id": "verified-fact-preview:andreoli:death.place",
                            "profile_id": "person:purocielo:andreoli-dino",
                            "field": "death.place",
                            "value": "Purocielo",
                            "source_document_id": "source-document:doc-1",
                            "source_decision_record_id": "evidence-record:decision-1",
                        }
                    ],
                },
            )

            dashboard = build_mvp_review_dashboard(
                review_session_json=review_session_json,
                review_queue_json=review_queue_json,
                review_decisions_summary_json=decisions_json,
                consolidated_ledger_json=ledger_json,
                verified_facts_preview_json=verified_preview_json,
            )
            markdown = render_mvp_review_dashboard_markdown(dashboard)

        preview = dashboard["verified_facts_preview"]
        self.assertTrue(preview["available"])
        self.assertEqual(preview["fact_count"], 1)
        self.assertEqual(preview["excluded_decision_count"], 2)
        self.assertEqual(preview["facts"][0]["source_decision_record_id"], "evidence-record:decision-1")
        self.assertIn("Verified facts preview", markdown)
        self.assertIn("Fatti preview: `1`", markdown)
        self.assertIn("Purocielo", markdown)

    def test_dashboard_marks_skipped_verified_facts_preview_without_failing(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, review_queue_json, decisions_json, ledger_json = write_dashboard_fixture(tmp_dir)
            verified_preview_json = write_json(
                tmp_dir / "historian_review" / "verified_facts.preview.json",
                {
                    "type": "verified_facts_preview",
                    "status": "skipped",
                    "reason": "skip_evidence_import",
                    "note": "Preview saltata per evitare letture stale.",
                },
            )

            dashboard = build_mvp_review_dashboard(
                review_session_json=review_session_json,
                review_queue_json=review_queue_json,
                review_decisions_summary_json=decisions_json,
                consolidated_ledger_json=ledger_json,
                verified_facts_preview_json=verified_preview_json,
            )
            markdown = render_mvp_review_dashboard_markdown(dashboard)

        preview = dashboard["verified_facts_preview"]
        self.assertFalse(preview["available"])
        self.assertEqual(preview["status"], "skipped")
        self.assertIn("Stato: `skipped`", markdown)
        self.assertIn("letture stale", markdown)

    def test_dashboard_summarizes_profile_patch_preview_and_sandbox_when_present(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, review_queue_json, decisions_json, ledger_json = write_dashboard_fixture(tmp_dir)
            profile_patch_preview_json = write_json(
                tmp_dir / "historian_review" / "profile_patch.preview.json",
                {
                    "@type": "ProfilePatchPreviewBatch",
                    "review_status": "preview-only",
                    "publication_status": "not_publishable_without_editorial_review",
                    "preview_only": True,
                    "patch_count": 1,
                    "operation_count": 2,
                    "skipped_fact_count": 1,
                    "profile_patches": [
                        {
                            "@type": "ProfilePatch",
                            "profile_id": "person:purocielo:andreoli-dino",
                            "operations": [
                                {"op": "set", "path": "/birth/date", "value": "1918"},
                                {"op": "set", "path": "/death/place", "value": "Purocielo"},
                            ],
                        }
                    ],
                },
            )
            sandbox_dir = tmp_dir / "historian_review" / "profile_patch_sandbox"
            write_json(
                sandbox_dir / "person-purocielo-andreoli-dino.sandbox.promotion.json",
                {
                    "status": "sandbox",
                    "sandbox": True,
                    "profile_id": "person:purocielo:andreoli-dino",
                    "writes_canonical_profile": False,
                },
            )
            write_json(sandbox_dir / "person-purocielo-andreoli-dino.sandbox.audit.json", {"changed": True})
            write_json(
                sandbox_dir / "person-purocielo-andreoli-dino.sandbox.profile.jsonld",
                {"@id": "person:purocielo:andreoli-dino", "name": "Andreoli Dino"},
            )

            dashboard = build_mvp_review_dashboard(
                review_session_json=review_session_json,
                review_queue_json=review_queue_json,
                review_decisions_summary_json=decisions_json,
                consolidated_ledger_json=ledger_json,
                profile_patch_preview_json=profile_patch_preview_json,
                profile_patch_sandbox_dir=sandbox_dir,
            )
            markdown = render_mvp_review_dashboard_markdown(dashboard)

        preview = dashboard["profile_patch_preview"]
        sandbox = dashboard["profile_patch_sandbox"]
        self.assertTrue(preview["available"])
        self.assertEqual(preview["patch_count"], 1)
        self.assertEqual(preview["operation_count"], 2)
        self.assertEqual(preview["skipped_fact_count"], 1)
        self.assertEqual(preview["profile_ids"], ["person:purocielo:andreoli-dino"])
        self.assertTrue(sandbox["available"])
        self.assertEqual(sandbox["status"], "sandbox")
        self.assertEqual(sandbox["sandbox_profile_count"], 1)
        self.assertEqual(sandbox["audit_count"], 1)
        self.assertEqual(sandbox["promotion_count"], 1)
        self.assertFalse(sandbox["writes_canonical_profile"])
        self.assertIn("ProfilePatch preview", markdown)
        self.assertIn("ProfilePatch: `1`", markdown)
        self.assertIn("ProfilePatch sandbox", markdown)
        self.assertIn("Profili derivati: `1`", markdown)


if __name__ == "__main__":
    unittest.main()
