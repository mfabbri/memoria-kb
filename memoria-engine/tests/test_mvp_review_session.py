from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_review_session import (  # noqa: E402
    build_mvp_review_session,
    render_mvp_review_session_markdown,
)
from caduti_fonti_report.document_analysis.mvp_review_session_markdown import (  # noqa: E402
    render_mvp_review_session_markdown as render_session_markdown,
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


def write_session_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    profile_id = "person:purocielo:andreoli-dino"
    summary_json = write_json(
        root / "document_analysis" / "mvp_pilot_summary.json",
        {
            "@type": "MvpPilotSummary",
            "profiles": [{"profile_id": profile_id, "canonical_name": "Andreoli Dino"}],
            "profile_readiness": [
                {
                    "profile_id": profile_id,
                    "canonical_name": "Andreoli Dino",
                    "readiness_status": "ready_for_review",
                    "document_count": 2,
                    "next_action": "Revisionare documenti, link e claim candidati.",
                }
            ],
        },
    )
    digest_json = write_json(
        root / "mvp_pilot_cards_digest.json",
        {
            "@type": "MvpPilotCardsDigest",
            "cards": [
                {
                    "profile_id": profile_id,
                    "canonical_name": "Andreoli Dino",
                    "candidate_document_person_link_count": 2,
                    "candidate_evidence_claim_count": 1,
                    "reviewable_document_signal_count": 1,
                    "candidate_card_path": str(root / "vault" / "40_Publication_Candidates" / "andreoli-dino.md"),
                    "candidate_card_exists": True,
                }
            ],
        },
    )
    queue_json = write_json(
        root / "historian_review" / "review_queue.json",
        {
            "@type": "HistorianReviewQueue",
            "item_count": 2,
            "items": [
                {
                    "item_id": "mvp-review-item:0001",
                    "item_type": "person_document_link_review",
                    "subject_kind": "person",
                    "profile_id": profile_id,
                    "source_document_id": "doc-andreoli",
                    "raw_file": "documenti_da_processare/andreoli/doc-andreoli.pdf",
                    "metadata_file": "documenti_processati/andreoli/doc-andreoli.metadata.json",
                    "priority": "high",
                    "risk": "medium",
                    "question": "Questo documento riguarda davvero Andreoli Dino?",
                    "allowed_decisions": ["accept_for_search", "reject_false_positive", "uncertain"],
                },
                {
                    "item_id": "mvp-review-item:0002",
                    "item_type": "candidate_claim_review",
                    "subject_kind": "date",
                    "profile_id": profile_id,
                    "source_document_id": "legacy_csv:andreoli",
                    "raw_file": "ricerche/caduti_purocielo.csv",
                    "document_reference_note": "seed legacy CSV, non documento storico verificato.",
                    "priority": "high",
                    "risk": "high",
                    "question": "La data candidata e' supportata dal documento?",
                    "allowed_decisions": ["approve_claim", "reject_claim", "mark_uncertain"],
                },
            ],
        },
    )
    decisions_json = write_json(
        root / "historian_review" / "review_decisions_summary.json",
        {
            "@type": "MvpReviewDecisionsSummary",
            "review_status": "reviewed",
            "pending_count": 0,
            "invalid_count": 0,
            "validation_error_count": 0,
            "review_session": {
                "@type": "MvpReviewSession",
                "session_status": "ready_for_curator_review",
                "profiles": [
                    {
                        "profile_id": profile_id,
                        "session_status": "ready_for_curator_review",
                        "accepted_count": 2,
                        "pending_count": 0,
                        "invalid_count": 0,
                        "counts_by_action": {
                            "approve_claim": 1,
                            "accept_for_search": 1,
                        },
                        "counts_by_status": {
                            "accepted": 2,
                        },
                    }
                ],
            },
            "decisions": [
                {
                    "item_id": "mvp-review-item:0001",
                    "selected_action": "accept_for_search",
                    "decision_status": "accepted",
                    "reviewer": "storico",
                    "notes": "Documento pertinente per la ricerca.",
                },
                {
                    "item_id": "mvp-review-item:0002",
                    "selected_action": "approve_claim",
                    "decision_status": "accepted",
                    "reviewer": "storico",
                    "notes": "Claim supportato dal documento.",
                },
            ],
        },
    )
    return summary_json, digest_json, queue_json, decisions_json


def write_ledger_fixture(root: Path) -> Path:
    profile_id = "person:purocielo:andreoli-dino"
    return write_json(
        root / "mvp_consolidated_review_ledger.json",
        {
            "@type": "MvpConsolidatedReviewLedger",
            "evidence_store_coverage": {
                "enabled": True,
                "db": "P:\\Comune\\Me.Mo.Ri.a\\database\\evidence.sqlite",
                "source_run_ids": ["mvp-test-pipeline"],
                "record_count": 3,
                "profiles_with_records_count": 1,
                "unscoped_record_count": 1,
                "workflow_unscoped_record_count": 1,
                "by_kind": {
                    "candidate_evidence_claim": {
                        "total": 2,
                        "with_subject": 2,
                        "with_source_document": 2,
                        "workflow_unscoped": 0,
                    },
                    "review_queue_item": {
                        "total": 1,
                        "with_subject": 0,
                        "with_source_document": 0,
                        "workflow_unscoped": 1,
                    },
                },
            },
            "profiles": [
                {
                    "profile_id": profile_id,
                    "canonical_name": "Andreoli Dino",
                    "evidence_store_coverage": {
                        "record_count": 2,
                        "source_document_count": 1,
                        "by_kind": {"candidate_evidence_claim": 2},
                        "by_review_status": {"unreviewed": 2},
                    },
                }
            ],
            "warnings": ["Evidence store contiene anche workflow non scopiati."],
        },
    )


class MvpReviewSessionTests(unittest.TestCase):
    def test_builds_review_session_without_promoting_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            summary_json, digest_json, queue_json, decisions_json = write_session_fixture(tmp_dir)
            output_json = tmp_dir / "historian_review" / "review_session.json"
            output_md = tmp_dir / "historian_review" / "review_session.md"

            session = build_mvp_review_session(
                summary_json=summary_json,
                digest_json=digest_json,
                review_queue_json=queue_json,
                review_decisions_summary_json=decisions_json,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False) + markdown

        self.assertEqual(session["@type"], "MvpReviewSessionPack")
        self.assertEqual(persisted["profile_count"], 1)
        self.assertEqual(persisted["publication_candidate_count"], 1)
        self.assertEqual(persisted["profiles"][0]["pilot_card_status"], "publication_candidate")
        self.assertEqual(persisted["profiles"][0]["model_card_review_status"], "ready_for_publication_review")
        self.assertEqual(persisted["profiles"][0]["review_item_count"], 2)
        self.assertEqual(persisted["profiles"][0]["accepted_decision_count"], 2)
        self.assertEqual(persisted["profiles"][0]["approved_decision_count"], 2)
        self.assertEqual(persisted["profiles"][0]["publication_status"], "not_publishable_without_curator_review")
        self.assertEqual(persisted["review_focus"]["profile_count"], 1)
        self.assertEqual(persisted["review_focus"]["item_count"], 2)
        focus_item = persisted["review_focus"]["profiles"][0]["items"][0]
        self.assertEqual(focus_item["item_id"], "mvp-review-item:0001")
        self.assertEqual(focus_item["decision_status"], "accepted")
        self.assertEqual(focus_item["selected_action"], "accept_for_search")
        self.assertIn("reject_false_positive", focus_item["allowed_decisions"])
        self.assertEqual(focus_item["raw_file"], "documenti_da_processare/andreoli/doc-andreoli.pdf")
        self.assertEqual(focus_item["metadata_file"], "documenti_processati/andreoli/doc-andreoli.metadata.json")
        self.assertEqual(
            persisted["profiles"][0]["priority_review_items"][1]["document_reference_note"],
            "seed legacy CSV, non documento storico verificato.",
        )
        focus_template = persisted["review_focus_decisions_template"]
        self.assertEqual(focus_template["template_scope"], "review_focus")
        self.assertEqual(focus_template["item_count"], 2)
        self.assertEqual(focus_template["decisions"][0]["item_id"], "mvp-review-item:0001")
        self.assertEqual(focus_template["decisions"][0]["selected_action"], "")
        self.assertEqual(focus_template["decisions"][0]["reviewer"], "")
        self.assertEqual(focus_template["decisions"][0]["notes"], "")
        self.assertIn("reject_false_positive", focus_template["decisions"][0]["allowed_decisions"])
        self.assertFalse(persisted["output_policy"]["new_model_cards_reviewed_artifacts"])
        self.assertIn("Sessione revisione MVP", markdown)
        self.assertIn("Schede modello in revisione", markdown)
        self.assertIn("Percorso review schede modello", markdown)
        self.assertIn("Template decisioni focus", markdown)
        self.assertIn("documenti_da_processare/andreoli/doc-andreoli.pdf", markdown)
        self.assertIn("documenti_processati/andreoli/doc-andreoli.metadata.json", markdown)
        self.assertIn("seed legacy CSV, non documento storico verificato", markdown)
        self.assertIn("accept_for_search", markdown)
        self.assertIn("Andreoli Dino", markdown)
        self.assertIn("publication_candidate", markdown)
        self.assertIn("ready_for_publication_review", markdown)
        self.assertIn("non genera mvp_model_cards_reviewed.md/json", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_marks_pending_ready_profile_as_ready_for_review(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            summary_json, digest_json, queue_json, decisions_json = write_session_fixture(tmp_dir)
            decisions = json.loads(decisions_json.read_text(encoding="utf-8"))
            decisions["review_status"] = "pending_review"
            decisions["pending_count"] = 2
            decisions["review_session"]["session_status"] = "not_started"
            decisions["review_session"]["profiles"][0]["session_status"] = "not_started"
            decisions["review_session"]["profiles"][0]["accepted_count"] = 0
            decisions["review_session"]["profiles"][0]["pending_count"] = 2
            decisions_json.write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")

            session = build_mvp_review_session(
                summary_json=summary_json,
                digest_json=digest_json,
                review_queue_json=queue_json,
                review_decisions_summary_json=decisions_json,
            )

        self.assertEqual(session["ready_for_review_count"], 1)
        self.assertEqual(session["profiles"][0]["pilot_card_status"], "ready_for_review")
        self.assertEqual(session["profiles"][0]["model_card_review_status"], "in_historical_review")
        self.assertTrue(any("decisioni pending" in warning for warning in session["warnings"]))

    def test_includes_ledger_evidence_store_coverage_when_available(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            summary_json, digest_json, queue_json, decisions_json = write_session_fixture(tmp_dir)
            ledger_json = write_ledger_fixture(tmp_dir)

            session = build_mvp_review_session(
                summary_json=summary_json,
                digest_json=digest_json,
                review_queue_json=queue_json,
                review_decisions_summary_json=decisions_json,
                consolidated_ledger_json=ledger_json,
            )
            markdown = render_mvp_review_session_markdown(session)
            serialized = json.dumps(session, ensure_ascii=False) + markdown

        coverage = session["ledger_evidence_store_coverage"]
        self.assertTrue(coverage["enabled"])
        self.assertEqual(coverage["record_count"], 3)
        self.assertEqual(coverage["profiles_with_records_count"], 1)
        self.assertEqual(coverage["workflow_unscoped_record_count"], 1)
        self.assertEqual(session["source_consolidated_ledger_json"], str(ledger_json))
        profile_coverage = session["profiles"][0]["ledger_evidence_store_coverage"]
        self.assertEqual(profile_coverage["record_count"], 2)
        self.assertEqual(profile_coverage["source_document_count"], 1)
        self.assertEqual(profile_coverage["by_kind"]["candidate_evidence_claim"], 2)
        self.assertIn("Copertura ledger / evidence store", markdown)
        self.assertIn("Record store nel ledger", markdown)
        self.assertIn("Tipi record store", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_without_ledger_keeps_disabled_coverage(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            summary_json, digest_json, queue_json, decisions_json = write_session_fixture(tmp_dir)

            session = build_mvp_review_session(
                summary_json=summary_json,
                digest_json=digest_json,
                review_queue_json=queue_json,
                review_decisions_summary_json=decisions_json,
            )

        self.assertEqual(session["source_consolidated_ledger_json"], "")
        self.assertEqual(session["ledger_evidence_store_coverage"], {"enabled": False})
        self.assertEqual(session["profiles"][0]["ledger_evidence_store_coverage"], {})

    def test_markdown_handles_empty_session(self) -> None:
        markdown = render_mvp_review_session_markdown({"profiles": []})

        self.assertIn("Nessun profilo", markdown)
        self.assertIn("Non applica decisioni", markdown)

    def test_markdown_renderer_keeps_front_matter_warnings_and_coverage(self) -> None:
        markdown = render_session_markdown(
            {
                "review_status": 'needs "curator"',
                "publication_status": "not_publishable_without_curator_review",
                "profiles": [],
                "ledger_evidence_store_coverage": {
                    "enabled": True,
                    "record_count": 1,
                    "profiles_with_records_count": 0,
                    "unscoped_record_count": 1,
                    "workflow_unscoped_record_count": 1,
                    "by_kind": {"review_queue_item": {"total": 1, "workflow_unscoped": 1}},
                },
                "warnings": ["Controllare workflow non scopiati."],
            }
        )

        self.assertIn('review_status: "needs \\"curator\\""', markdown)
        self.assertIn("Copertura ledger / evidence store", markdown)
        self.assertIn("| review_queue_item | 1 | 0 | 0 | 1 |", markdown)
        self.assertIn("_Nessun profilo nella sessione._", markdown)
        self.assertIn("- Controllare workflow non scopiati.", markdown)


if __name__ == "__main__":
    unittest.main()
