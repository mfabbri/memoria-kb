from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.evidence_store_records import EvidenceStoreRecord  # noqa: E402
from caduti_fonti_report.document_analysis.mvp_consolidated_review_ledger import (  # noqa: E402
    build_mvp_consolidated_review_ledger,
    render_mvp_consolidated_review_ledger_markdown,
)
from caduti_fonti_report.document_analysis.mvp_consolidated_review_ledger_markdown import (  # noqa: E402
    render_mvp_consolidated_review_ledger_markdown as render_ledger_markdown,
)
from caduti_fonti_report.sqlite_store import SQLiteEvidenceStore  # noqa: E402


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


def write_summary(run_dir: Path, *, run_name: str, extra_claim_value: str = "") -> Path:
    document_dir = run_dir / "document_analysis"
    document_dir.mkdir(parents=True)
    claims = [
        {
            "@id": "candidate-claim:birth",
            "profile_id": "person:purocielo:balboni-william",
            "source_document_id": "doc:balboni",
            "source_id": "partigiani_italia",
            "field": "birth.date",
            "value": "6 maggio 1921",
            "normalized_value": "6 maggio 1921",
            "extraction_method": "online_detail_structured_fields",
            "review_status": "unreviewed",
        }
    ]
    if extra_claim_value:
        claims.append(
            {
                "@id": "candidate-claim:formation",
                "profile_id": "person:purocielo:balboni-william",
                "source_document_id": "doc:balboni",
                "source_id": "partigiani_italia",
                "field": "formation.name",
                "value": extra_claim_value,
                "normalized_value": extra_claim_value.casefold(),
                "extraction_method": "online_detail_structured_fields",
                "review_status": "unreviewed",
            }
        )
    payload = {
        "@type": "MvpPilotSummary",
        "run_dir": str(run_dir),
        "document_analysis_dir": str(document_dir),
        "profiles": [
            {
                "profile_id": "person:purocielo:balboni-william",
                "canonical_name": "Balboni William",
            }
        ],
        "documents": [
            {
                "source_document_id": "doc:balboni",
                "source_id": "partigiani_italia",
                "title": f"Scheda Balboni {run_name}",
                "url": "https://example.test/balboni",
                "document_class": "online_detail_text",
                "quality_status": "ready_for_manual_review",
                "review_status": "unreviewed",
            }
        ],
        "candidate_document_person_links": [
            {
                "profile_id": "person:purocielo:balboni-william",
                "canonical_name": "Balboni William",
                "source_document_id": "doc:balboni",
                "source_id": "partigiani_italia",
                "matched_name": "Balboni William",
                "match_kind": "canonical_name",
                "score": 1.0,
                "review_status": "unreviewed",
            }
        ],
        "candidate_evidence_claims": claims,
        "reviewable_document_signals": [
            {
                "profile_id": "person:purocielo:balboni-william",
                "canonical_name": "Balboni William",
                "signals": [
                    {
                        "signal_type": "claim",
                        "source_document_id": "doc:balboni",
                        "summary": "Controllare scheda online acquisita.",
                        "review_status": "unreviewed",
                    }
                ],
            }
        ],
    }
    path = document_dir / "mvp_pilot_summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_evidence_store(db_path: Path) -> None:
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    store.insert_evidence_import_batch(
        {
            "import_batch_id": "evidence-import:run-single:abc123",
            "source_run_id": "run-single",
            "imported_at": "2026-06-13T10:00:00+00:00",
            "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/run-single",
            "record_count": 3,
            "payload_hash": "batch-hash",
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:claim-1",
            "import_batch_id": "evidence-import:run-single:abc123",
            "source_run_id": "run-single",
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:balboni-william",
            "source_document_id": "doc:balboni",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-1",
            "payload": {"@type": "CandidateEvidenceClaim", "profile_id": "person:purocielo:balboni-william"},
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:workflow-1",
            "import_batch_id": "evidence-import:run-single:abc123",
            "source_run_id": "run-single",
            "record_kind": "review_queue_item",
            "subject_id": "",
            "source_document_id": "",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-2",
            "payload": {"@type": "ReviewQueueItem", "subject_kind": "workflow"},
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:other-run",
            "import_batch_id": "evidence-import:run-single:abc123",
            "source_run_id": "other-run",
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:balboni-william",
            "source_document_id": "doc:other",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-3",
            "payload": {"@type": "CandidateEvidenceClaim"},
        }
    )


def write_demo_alignment_summary(run_dir: Path) -> Path:
    document_dir = run_dir / "document_analysis"
    document_dir.mkdir(parents=True)
    payload = {
        "@type": "MvpPilotSummary",
        "run_dir": str(run_dir),
        "document_analysis_dir": str(document_dir),
        "profiles": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
            },
            {
                "profile_id": "person:purocielo:bendini-ateo",
                "canonical_name": "Bendini Ateo",
            },
        ],
        "documents": [
            {
                "source_document_id": "legacy_csv:a4ac96061a2381b5",
                "source_id": "legacy_csv",
                "title": "Riga CSV Andreoli",
                "document_class": "legacy_csv_row",
                "quality_status": "ready_for_manual_review",
                "review_status": "unreviewed",
            },
            {
                "source_document_id": "local_docx:4c2ad1d2ab937913",
                "source_id": "local_docx",
                "title": "Scheda locale Andreoli",
                "document_class": "local_docx",
                "quality_status": "ready_for_manual_review",
                "review_status": "unreviewed",
            },
        ],
        "candidate_document_person_links": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "source_document_id": "legacy_csv:a4ac96061a2381b5",
                "source_id": "legacy_csv",
                "matched_name": "ANDREOLI DINO",
                "match_kind": "intestazione_pdf",
                "score": 0.95,
                "review_status": "unreviewed",
            },
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "source_document_id": "local_docx:4c2ad1d2ab937913",
                "source_id": "local_docx",
                "matched_name": "Andreoli Dino",
                "match_kind": "canonical_name",
                "score": 0.9,
                "review_status": "unreviewed",
            },
        ],
        "candidate_evidence_claims": [
            {
                "@id": "candidate-evidence-claim:outside-local",
                "profile_id": "person:purocielo:bendini-ateo",
                "source_document_id": "local_docx:4c2ad1d2ab937913",
                "source_id": "local_docx",
                "field": "formation.name",
                "value": "36a Brigata Garibaldi",
                "normalized_value": "36a brigata garibaldi",
                "extraction_method": "document_entity_context_rules",
                "review_status": "unreviewed",
            }
        ],
    }
    path = document_dir / "mvp_pilot_summary.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class MvpConsolidatedReviewLedgerTests(unittest.TestCase):
    def test_evidence_store_record_normalizes_nested_payload_and_profile_fallbacks(self) -> None:
        record = EvidenceStoreRecord.from_row(
            {
                "record_id": "evidence-record:nested",
                "source_run_id": "run-a",
                "record_kind": "review_queue_item",
                "subject_id": "",
                "source_document_id": "",
                "review_status": "pending",
                "payload_hash": "hash-nested",
                "payload_json": json.dumps(
                    {
                        "payload": {
                            "item_id": "mvp-review-item:0001",
                            "profile_id": "person:purocielo:andreoli-dino",
                            "source_document_id": "doc-andreoli",
                            "subject_kind": "person",
                        }
                    }
                ),
            }
        )

        self.assertEqual(record.payload["item_id"], "mvp-review-item:0001")
        self.assertEqual(record.primary_profile_id(), "person:purocielo:andreoli-dino")
        self.assertEqual(record.effective_source_document_id, "doc-andreoli")
        self.assertEqual(record.scoped_payload()["review_status"], "pending")
        self.assertEqual(record.store_key("", "doc-andreoli"), "doc-andreoli")

    def test_consolidates_multiple_summary_runs_with_conservative_deduplication(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_a = tmp_dir / "run-a"
            run_b = tmp_dir / "run-b"
            summary_a = write_summary(run_a, run_name="A")
            summary_b = write_summary(run_b, run_name="B", extra_claim_value="36ma brigata Bianconcini Garibaldi")
            output_json = tmp_dir / "ledger.json"
            output_md = tmp_dir / "ledger.md"

            ledger = build_mvp_consolidated_review_ledger(
                summary_json=[summary_a, summary_b],
                output_json=output_json,
                output_md=output_md,
            )
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        self.assertEqual(ledger["@type"], "MvpConsolidatedReviewLedger")
        self.assertEqual(ledger["source_run_count"], 2)
        self.assertEqual(ledger["profile_count"], 1)
        profile = ledger["profiles"][0]
        self.assertEqual(profile["profile_id"], "person:purocielo:balboni-william")
        self.assertEqual(profile["document_count"], 1)
        self.assertEqual(profile["candidate_document_person_link_count"], 1)
        self.assertEqual(profile["candidate_evidence_claim_count"], 2)
        self.assertEqual(profile["reviewable_document_signal_count"], 1)
        self.assertEqual(len(profile["source_runs"]), 2)
        self.assertTrue(all(claim["review_status"] == "unreviewed" for claim in profile["candidate_evidence_claims"]))
        self.assertNotIn('"@type": "EvidenceClaim"', json.dumps(ledger))
        self.assertNotIn("verified_facts", json.dumps(ledger))
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)

    def test_standard_ledger_adds_link_scoped_preview_claims_without_sidecar(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "demo-run"
            summary = write_demo_alignment_summary(run_dir)

            ledger = build_mvp_consolidated_review_ledger(summary_json=[summary])

        profiles = {profile["profile_id"]: profile for profile in ledger["profiles"]}
        andreoli_claims = {
            (claim["source_document_id"], claim["field"]): claim
            for claim in profiles["person:purocielo:andreoli-dino"]["candidate_evidence_claims"]
        }
        legacy_claim = andreoli_claims[("legacy_csv:a4ac96061a2381b5", "identity.canonical_name")]
        local_claim = andreoli_claims[("local_docx:4c2ad1d2ab937913", "formation.name")]

        self.assertEqual(legacy_claim["value"], "ANDREOLI DINO")
        self.assertEqual(legacy_claim["review_status"], "unreviewed")
        self.assertEqual(legacy_claim["extraction_method"], "ledger_standard_from_candidate_document_person_link")
        self.assertEqual(legacy_claim["ledger_derivation_status"], "standard_preview_candidate")
        self.assertEqual(local_claim["value"], "36a Brigata Garibaldi")
        self.assertEqual(local_claim["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(local_claim["ledger_derivation_source_profile_id"], "person:purocielo:bendini-ateo")
        self.assertIn("ledger_standard_projection_from_linked_document_claim", local_claim["extraction_method"])
        self.assertEqual(local_claim["ledger_derivation_status"], "standard_preview_candidate")
        self.assertEqual(profiles["person:purocielo:andreoli-dino"]["candidate_evidence_claim_count"], 2)
        self.assertNotIn('"@type": "EvidenceClaim"', json.dumps(ledger))
        self.assertNotIn("verified_facts", json.dumps(ledger))

    def test_accepts_run_dir_and_renders_markdown(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "run-single"
            write_summary(run_dir, run_name="single")

            ledger = build_mvp_consolidated_review_ledger(run_dir=[run_dir])
            markdown = render_mvp_consolidated_review_ledger_markdown(ledger)

        self.assertEqual(ledger["source_run_count"], 1)
        self.assertTrue(any("Ledger costruito da una sola run" in warning for warning in ledger["warnings"]))
        self.assertIn("# Consolidated Review Ledger MVP", markdown)
        self.assertIn("Balboni William", markdown)
        self.assertIn("online_detail_structured_fields", markdown)

    def test_markdown_renderer_keeps_review_front_matter_and_empty_sections(self) -> None:
        markdown = render_ledger_markdown(
            {
                "review_status": 'needs "curator"',
                "publication_status": "not_publishable_without_curator_review",
                "source_runs": [],
                "profiles": [],
                "warnings": ["Controllo storico richiesto."],
            }
        )

        self.assertIn('review_status: "needs \\"curator\\""', markdown)
        self.assertIn("_Nessuna run sorgente._", markdown)
        self.assertIn("_Nessun profilo consolidato._", markdown)
        self.assertIn("- Controllo storico richiesto.", markdown)

    def test_builds_store_first_ledger_from_evidence_records(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            store.insert_evidence_import_batch(
                {
                    "import_batch_id": "evidence-import:store-first:abc123",
                    "source_run_id": "store-first-run",
                    "imported_at": "2026-06-21T10:00:00+00:00",
                    "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/store-first-run",
                    "record_count": 5,
                    "payload_hash": "batch-hash",
                }
            )
            for record in [
                {
                    "record_id": "evidence-record:link-1",
                    "record_kind": "candidate_document_person_link",
                    "subject_id": "person:purocielo:balboni-william",
                    "source_document_id": "doc:balboni",
                    "review_status": "unreviewed",
                    "payload_hash": "record-hash-link",
                    "payload": {
                        "@type": "CandidateDocumentPersonLink",
                        "profile_id": "person:purocielo:balboni-william",
                        "canonical_name": "Balboni William",
                        "source_document_id": "doc:balboni",
                        "matched_name": "Balboni William",
                        "match_kind": "canonical_name",
                    },
                },
                {
                    "record_id": "evidence-record:claim-1",
                    "record_kind": "candidate_evidence_claim",
                    "subject_id": "person:purocielo:balboni-william",
                    "source_document_id": "doc:balboni",
                    "review_status": "unreviewed",
                    "payload_hash": "record-hash-claim",
                    "payload": {
                        "@type": "CandidateEvidenceClaim",
                        "profile_id": "person:purocielo:balboni-william",
                        "source_document_id": "doc:balboni",
                        "field": "birth.date",
                        "value": "6 maggio 1921",
                    },
                },
                {
                    "record_id": "evidence-record:item-1",
                    "record_kind": "review_queue_item",
                    "subject_id": "",
                    "source_document_id": "doc:balboni",
                    "review_status": "pending",
                    "payload_hash": "record-hash-item",
                    "payload": {
                        "@type": "MvpReviewQueueItem",
                        "item_id": "review:item:balboni",
                        "profile_id": "person:purocielo:balboni-william",
                        "source_document_id": "doc:balboni",
                        "question": "Confermare il collegamento documento-persona?",
                    },
                },
                {
                    "record_id": "evidence-record:decision-1",
                    "record_kind": "review_decision",
                    "subject_id": "person:purocielo:balboni-william",
                    "source_document_id": "doc:balboni",
                    "review_status": "pending",
                    "payload_hash": "record-hash-decision",
                    "payload": {
                        "@type": "MvpReviewDecision",
                        "decision_id": "review-decision:balboni",
                        "item_id": "review:item:balboni",
                        "profile_id": "person:purocielo:balboni-william",
                        "source_document_id": "doc:balboni",
                        "selected_action": "request_more_sources",
                    },
                },
                {
                    "record_id": "evidence-record:historical-decision-1",
                    "record_kind": "historical_review_decision",
                    "subject_id": "person:purocielo:balboni-william",
                    "source_document_id": "doc:balboni",
                    "review_status": "pending",
                    "payload_hash": "record-hash-historical-decision",
                    "payload": {
                        "@type": "HistoricalReviewDecision",
                        "decision_id": "historical-review-decision:balboni",
                        "item_id": "review:item:balboni",
                        "profile_id": "person:purocielo:balboni-william",
                        "source_document_id": "doc:balboni",
                        "selected_action": "confirm",
                        "decision_status": "accepted",
                    },
                },
                {
                    "record_id": "evidence-record:workflow-1",
                    "record_kind": "review_queue_item",
                    "subject_id": "",
                    "source_document_id": "",
                    "review_status": "unreviewed",
                    "payload_hash": "record-hash-workflow",
                    "payload": {"@type": "MvpReviewQueueItem", "subject_kind": "workflow"},
                },
            ]:
                record["import_batch_id"] = "evidence-import:store-first:abc123"
                record["source_run_id"] = "store-first-run"
                store.insert_evidence_record(record)

            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")
            ledger = build_mvp_consolidated_review_ledger(
                evidence_db=db_path,
                evidence_source_run_id=["store-first-run"],
            )
            after_records = store.count("evidence_records")
            after_claims = store.count("evidence_claims")
            markdown = render_mvp_consolidated_review_ledger_markdown(ledger)

        self.assertEqual(before_records, after_records)
        self.assertEqual(before_claims, after_claims)
        self.assertEqual(ledger["ledger_source_mode"], "store_first")
        self.assertEqual(ledger["source_summary_json"], [])
        self.assertEqual(ledger["source_run_count"], 1)
        self.assertEqual(ledger["profile_count"], 1)
        self.assertEqual(ledger["evidence_store_coverage"]["record_count"], 6)
        profile = ledger["profiles"][0]
        self.assertEqual(profile["profile_id"], "person:purocielo:balboni-william")
        self.assertEqual(profile["document_count"], 1)
        self.assertEqual(profile["candidate_document_person_link_count"], 1)
        self.assertEqual(profile["candidate_evidence_claim_count"], 1)
        self.assertEqual(profile["review_item_count"], 1)
        self.assertEqual(profile["review_decision_count"], 2)
        self.assertIn("evidence-record:claim-1", profile["candidate_evidence_claims"][0]["record_ids"])
        self.assertIn("record-hash-claim", profile["candidate_evidence_claims"][0]["payload_hashes"])
        self.assertIn("request_more_sources", json.dumps(profile["review_decisions"], ensure_ascii=False))
        self.assertIn("historical-review-decision:balboni", json.dumps(profile["review_decisions"], ensure_ascii=False))
        historical_decision = [
            decision
            for decision in profile["review_decisions"]
            if decision["decision_id"] == "historical-review-decision:balboni"
        ][0]
        self.assertEqual(historical_decision["review_status"], "accepted")
        self.assertEqual(historical_decision["decision_status"], "accepted")
        self.assertIn("Modalita' sorgente: `store_first`", markdown)
        self.assertNotIn('"@type": "EvidenceClaim"', json.dumps(ledger))
        self.assertNotIn("verified_facts", json.dumps(ledger))

    def test_store_first_requires_explicit_source_run_filter(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()

            with self.assertRaises(ValueError):
                build_mvp_consolidated_review_ledger(evidence_db=db_path)

    def test_adds_read_only_evidence_store_coverage_without_replacing_summary(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "run-single"
            summary = write_summary(run_dir, run_name="single")
            db_path = tmp_dir / "evidence.sqlite"
            write_evidence_store(db_path)

            ledger = build_mvp_consolidated_review_ledger(
                summary_json=[summary],
                evidence_db=db_path,
                evidence_source_run_id=["run-single"],
            )
            markdown = render_mvp_consolidated_review_ledger_markdown(ledger)

        coverage = ledger["evidence_store_coverage"]
        self.assertTrue(coverage["enabled"])
        self.assertEqual(coverage["record_count"], 2)
        self.assertEqual(coverage["profiles_with_records_count"], 1)
        self.assertEqual(coverage["workflow_unscoped_record_count"], 1)
        self.assertEqual(coverage["by_kind"]["candidate_evidence_claim"]["total"], 1)
        self.assertEqual(coverage["by_kind"]["review_queue_item"]["workflow_unscoped"], 1)
        profile = ledger["profiles"][0]
        self.assertEqual(profile["candidate_evidence_claim_count"], 1)
        self.assertEqual(profile["evidence_store_coverage"]["record_count"], 1)
        self.assertEqual(profile["evidence_store_coverage"]["source_document_count"], 1)
        self.assertIn("## Copertura evidence store", markdown)
        self.assertIn("Copertura evidence store:", markdown)
        self.assertNotIn("doc:other", json.dumps(ledger))
        self.assertNotIn('"@type": "EvidenceClaim"', json.dumps(ledger))
        self.assertNotIn("verified_facts", json.dumps(ledger))

    def test_evidence_store_coverage_uses_payload_profile_id_when_subject_is_empty(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "run-single"
            summary = write_summary(run_dir, run_name="single")
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            store.insert_evidence_import_batch(
                {
                    "import_batch_id": "evidence-import:payload-profile:abc123",
                    "source_run_id": "payload-profile-run",
                    "imported_at": "2026-06-28T10:00:00+00:00",
                    "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/payload-profile-run",
                    "record_count": 1,
                    "payload_hash": "batch-hash",
                }
            )
            store.insert_evidence_record(
                {
                    "record_id": "evidence-record:payload-profile-claim",
                    "import_batch_id": "evidence-import:payload-profile:abc123",
                    "source_run_id": "payload-profile-run",
                    "record_kind": "candidate_evidence_claim",
                    "subject_id": "",
                    "source_document_id": "",
                    "review_status": "unreviewed",
                    "payload_hash": "record-hash-payload-profile",
                    "payload": {
                        "@type": "CandidateEvidenceClaim",
                        "profile_id": "person:purocielo:balboni-william",
                        "source_document_id": "doc:balboni",
                        "field": "birth.date",
                        "value": "6 maggio 1921",
                        "review_status": "unreviewed",
                    },
                }
            )
            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")

            ledger = build_mvp_consolidated_review_ledger(
                summary_json=[summary],
                evidence_db=db_path,
                evidence_source_run_id=["payload-profile-run"],
            )

            after_records = store.count("evidence_records")
            after_claims = store.count("evidence_claims")

        self.assertEqual(before_records, after_records)
        self.assertEqual(before_claims, after_claims)
        coverage = ledger["evidence_store_coverage"]
        self.assertEqual(coverage["record_count"], 1)
        self.assertEqual(coverage["profiles_with_records_count"], 1)
        self.assertEqual(coverage["unscoped_record_count"], 0)
        self.assertEqual(coverage["by_kind"]["candidate_evidence_claim"]["with_subject"], 1)
        self.assertEqual(coverage["by_kind"]["candidate_evidence_claim"]["with_source_document"], 1)
        profile = ledger["profiles"][0]
        self.assertEqual(profile["evidence_store_coverage"]["record_count"], 1)
        self.assertEqual(profile["evidence_store_coverage"]["source_document_count"], 1)
        self.assertNotIn('"@type": "EvidenceClaim"', json.dumps(ledger))
        self.assertNotIn("verified_facts", json.dumps(ledger))

    def test_evidence_store_workflow_only_records_are_reported_as_warning(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "run-single"
            summary = write_summary(run_dir, run_name="single")
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            store.insert_evidence_import_batch(
                {
                    "import_batch_id": "evidence-import:workflow-only:abc123",
                    "source_run_id": "workflow-only",
                    "imported_at": "2026-06-13T10:00:00+00:00",
                    "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/workflow-only",
                    "record_count": 1,
                    "payload_hash": "batch-hash",
                }
            )
            store.insert_evidence_record(
                {
                    "record_id": "evidence-record:workflow-only",
                    "import_batch_id": "evidence-import:workflow-only:abc123",
                    "source_run_id": "workflow-only",
                    "record_kind": "review_queue_item",
                    "subject_id": "",
                    "source_document_id": "",
                    "review_status": "unreviewed",
                    "payload_hash": "record-hash",
                    "payload": {"@type": "ReviewQueueItem", "subject_kind": "workflow"},
                }
            )

            ledger = build_mvp_consolidated_review_ledger(
                summary_json=[summary],
                evidence_db=db_path,
                evidence_source_run_id=["workflow-only"],
            )

        self.assertEqual(ledger["evidence_store_coverage"]["record_count"], 1)
        self.assertTrue(any("solo record workflow" in warning for warning in ledger["warnings"]))


if __name__ == "__main__":
    unittest.main()
