from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_funding_dossier import (  # noqa: E402
    build_mvp_funding_dossier,
    render_mvp_funding_dossier_markdown,
)
from caduti_fonti_report.document_analysis.mvp_package_readiness import build_mvp_package_readiness  # noqa: E402
from tests.test_mvp_package_readiness import build_review_fixture, write_demo_vault  # noqa: E402


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


class MvpFundingDossierTests(unittest.TestCase):
    def test_builds_funding_dossier_from_ready_package_without_promoting_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "run"
            (run_dir / "document_analysis").mkdir(parents=True)
            summary_json, queue_json, decisions_summary_json = build_review_fixture(run_dir)
            vault_dir = write_demo_vault(tmp_dir)
            readiness_json = run_dir / "mvp_package_readiness.json"
            build_mvp_package_readiness(
                summary_json=summary_json,
                review_queue_json=queue_json,
                review_decisions_summary_json=decisions_summary_json,
                vault_dir=vault_dir,
                output_json=readiness_json,
                output_md=run_dir / "mvp_package_readiness.md",
            )
            output_json = run_dir / "mvp_funding_dossier.json"
            output_md = run_dir / "mvp_funding_dossier.md"

            dossier = build_mvp_funding_dossier(
                package_readiness_json=readiness_json,
                summary_json=summary_json,
                review_decisions_summary_json=decisions_summary_json,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False) + markdown

        self.assertEqual(dossier["@type"], "MvpFundingDossier")
        self.assertEqual(persisted["readiness_status"], "ready_for_demo")
        self.assertEqual(persisted["publication_candidate_count"], 1)
        self.assertIn("# Dossier finanziamento MVP Purocielo", markdown)
        self.assertIn("## Obiettivo culturale", markdown)
        self.assertIn("## Stato demo", markdown)
        self.assertIn("## Materiali disponibili", markdown)
        self.assertIn("## Vincoli editoriali", markdown)
        self.assertIn("not_publishable_without_curator_review", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_dossier_lists_blockers_and_next_actions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            readiness_json = tmp_dir / "mvp_package_readiness.json"
            summary_json = tmp_dir / "mvp_pilot_summary.json"
            decisions_json = tmp_dir / "review_decisions_summary.json"
            source_coverage_json = tmp_dir / "source_coverage_summary.json"
            ledger_json = tmp_dir / "mvp_consolidated_review_ledger.json"
            verified_preview_json = tmp_dir / "historian_review" / "verified_facts.preview.json"
            readiness_json.write_text(
                json.dumps(
                    {
                        "@type": "MvpPackageReadiness",
                        "readiness_status": "needs_document_intake",
                        "profile_count": 1,
                        "ready_profile_count": 0,
                        "publication_candidate_count": 0,
                        "review_queue_item_count": 2,
                        "blockers": [{"blocker_type": "document_intake", "message": "OCR mancante."}],
                        "next_actions": ["Completare OCR dei documenti pilota."],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            summary_json.write_text(
                json.dumps(
                    {
                        "profile_readiness": [],
                        "mvp_signal_diagnostics": {
                            "@type": "MvpSignalDiagnostics",
                            "document_count": 4,
                            "estimated_unique_document_count": 2,
                            "duplicate_document_group_count": 1,
                            "candidate_document_person_link_count": 3,
                            "weak_nominal_link_count": 2,
                            "profiles_with_links_no_claims_count": 1,
                            "mvp_blockers": ["2 link persona-documento sono match nominali deboli."],
                            "next_action": "Rafforzare i link con contesto segmentato.",
                            "review_status": "unreviewed",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            decisions_json.write_text(json.dumps({"review_status": "pending"}, ensure_ascii=False), encoding="utf-8")
            source_coverage_json.write_text(
                json.dumps(
                    {
                        "@type": "SourceCoverageSummary",
                        "source_count": 1,
                        "profile_count": 2,
                        "entry_count": 2,
                        "review_status": "unreviewed",
                        "publication_status": "not_publishable_without_human_review",
                        "sources": [
                            {
                                "source_id": "storia_memoria_bo",
                                "source_name": "Storia e Memoria di Bologna",
                                "profile_count": 2,
                                "candidate_profile_count": 1,
                                "detail_profile_count": 1,
                                "no_results_profile_count": 1,
                                "document_count": 1,
                                "claim_count": 1,
                                "recommended_action": "review_detail_documents",
                                "review_status": "unreviewed",
                            }
                        ],
                        "warnings": [
                            "Il riepilogo misura copertura operativa, non assenza o presenza storica."
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            ledger_json.write_text(
                json.dumps(
                    {
                        "@type": "MvpConsolidatedReviewLedger",
                        "profile_count": 3,
                        "document_count": 12,
                        "candidate_document_person_link_count": 8,
                        "candidate_evidence_claim_count": 5,
                        "reviewable_document_signal_count": 4,
                        "evidence_store_coverage": {
                            "enabled": True,
                            "record_count": 17,
                            "profiles_with_records_count": 3,
                            "unscoped_record_count": 2,
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            verified_preview_json.parent.mkdir(parents=True, exist_ok=True)
            verified_preview_json.write_text(
                json.dumps(
                    {
                        "@type": "VerifiedFactsPreview",
                        "review_status": "preview-only",
                        "publication_status": "not_publishable_without_editorial_review",
                        "preview_only": True,
                        "fact_count": 1,
                        "excluded_decision_count": 3,
                        "counts_by_profile": {"person:purocielo:andreoli-dino": 1},
                        "facts": [
                            {
                                "profile_id": "person:purocielo:andreoli-dino",
                                "field": "death.place",
                                "value": "Purocielo",
                                "source_document_id": "source-document:doc-1",
                                "source_decision_record_id": "evidence-record:decision-1",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            dossier = build_mvp_funding_dossier(
                package_readiness_json=readiness_json,
                summary_json=summary_json,
                review_decisions_summary_json=decisions_json,
                source_coverage_summary_json=source_coverage_json,
                consolidated_ledger_json=ledger_json,
                verified_facts_preview_json=verified_preview_json,
            )
            markdown = render_mvp_funding_dossier_markdown(dossier)

        self.assertIn("OCR mancante", markdown)
        self.assertIn("Completare OCR", markdown)
        self.assertIn("Diagnostica segnale", markdown)
        self.assertIn("Documenti unici stimati: `2`", markdown)
        self.assertIn("Link nominali deboli: `2` / `3`", markdown)
        self.assertEqual(dossier["signal_diagnostics"]["estimated_unique_document_count"], 2)
        self.assertIn("Copertura fonti", markdown)
        self.assertIn("storia_memoria_bo", markdown)
        self.assertIn("review_detail_documents", markdown)
        self.assertEqual(dossier["source_coverage"]["source_count"], 1)
        self.assertEqual(dossier["readiness_status"], "needs_document_intake")
        self.assertIn("Raccordo step 2 storico", markdown)
        self.assertIn("Sintesi ledger", markdown)
        self.assertIn("Profili nel ledger: `3`", markdown)
        self.assertIn("Record store: `17`", markdown)
        self.assertIn("Verified facts preview", markdown)
        self.assertIn("Fatti preview: `1`", markdown)
        self.assertIn("Decisioni escluse: `3`", markdown)
        self.assertIn("non e' dataset canonico", markdown)
        self.assertEqual(dossier["step2_historical_raccordo"]["ledger_profile_count"], 3)
        self.assertEqual(dossier["step2_historical_raccordo"]["evidence_store_record_count"], 17)
        self.assertEqual(dossier["step2_historical_raccordo"]["verified_facts_preview"]["fact_count"], 1)

    def test_dossier_marks_skipped_verified_facts_preview(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            readiness_json = tmp_dir / "mvp_package_readiness.json"
            summary_json = tmp_dir / "mvp_pilot_summary.json"
            decisions_json = tmp_dir / "review_decisions_summary.json"
            verified_preview_json = tmp_dir / "historian_review" / "verified_facts.preview.json"
            readiness_json.write_text(json.dumps({"readiness_status": "ready_for_demo"}), encoding="utf-8")
            summary_json.write_text(json.dumps({}), encoding="utf-8")
            decisions_json.write_text(json.dumps({"review_status": "pending"}), encoding="utf-8")
            verified_preview_json.parent.mkdir(parents=True, exist_ok=True)
            verified_preview_json.write_text(
                json.dumps(
                    {
                        "type": "verified_facts_preview",
                        "status": "skipped",
                        "reason": "skip_evidence_import",
                        "note": "Preview saltata per evitare letture stale.",
                    }
                ),
                encoding="utf-8",
            )

            dossier = build_mvp_funding_dossier(
                package_readiness_json=readiness_json,
                summary_json=summary_json,
                review_decisions_summary_json=decisions_json,
                verified_facts_preview_json=verified_preview_json,
            )
            markdown = render_mvp_funding_dossier_markdown(dossier)

        preview = dossier["step2_historical_raccordo"]["verified_facts_preview"]
        self.assertFalse(preview["available"])
        self.assertEqual(preview["status"], "skipped")
        self.assertIn("Stato: `skipped`", markdown)
        self.assertIn("letture stale", markdown)


if __name__ == "__main__":
    unittest.main()
