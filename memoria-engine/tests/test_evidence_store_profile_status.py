from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.evidence_store_profile_status import (
    build_evidence_store_profile_status,
    render_evidence_store_profile_status_markdown,
)
from caduti_fonti_report.sqlite_store import SQLiteEvidenceStore


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


def populated_store(db_path: Path) -> SQLiteEvidenceStore:
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    store.insert_evidence_import_batch(
        {
            "import_batch_id": "evidence-import:mvp-run:profile-status",
            "source_run_id": "mvp-run-pipeline",
            "imported_at": "2026-06-21T10:00:00+00:00",
            "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/mvp-run-pipeline",
            "record_count": 5,
            "payload_hash": "batch-hash",
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:claim-1",
            "import_batch_id": "evidence-import:mvp-run:profile-status",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-1",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-1",
            "payload": {
                "@type": "CandidateEvidenceClaim",
                "profile_id": "person:purocielo:andreoli-dino",
                "field": "death.place",
                "value": "Purocielo",
                "source_document_id": "source-document:doc-1",
                "review_status": "unreviewed",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:item-1",
            "import_batch_id": "evidence-import:mvp-run:profile-status",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "review_queue_item",
            "subject_id": "",
            "source_document_id": "source-document:doc-1",
            "review_status": "pending",
            "payload_hash": "record-hash-2",
            "payload": {
                "@type": "ReviewQueueItem",
                "item_id": "review:item:1",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "review_status": "pending",
                "question": "Confermare il collegamento documento-persona?",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:decision-1",
            "import_batch_id": "evidence-import:mvp-run:profile-status",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "review_decision",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-1",
            "review_status": "pending",
            "payload_hash": "record-hash-3",
            "payload": {
                "@type": "ReviewDecision",
                "decision_id": "review-decision:1",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "review_status": "pending",
                "selected_action": "request_more_sources",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:historical-decision-1",
            "import_batch_id": "evidence-import:mvp-run:profile-status",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "historical_review_decision",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-1",
            "review_status": "approved",
            "payload_hash": "record-hash-5",
            "payload": {
                "@type": "HistoricalReviewDecision",
                "decision_id": "historical-review-decision:1",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "review_status": "approved",
                "selected_action": "confirm",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:workflow-1",
            "import_batch_id": "evidence-import:mvp-run:profile-status",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "review_queue_item",
            "subject_id": "",
            "source_document_id": "",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-4",
            "payload": {
                "@type": "ReviewQueueItem",
                "subject_kind": "workflow",
                "review_status": "unreviewed",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:signal-1",
            "import_batch_id": "evidence-import:mvp-run:profile-status",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "reviewable_document_signal",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-2",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-6",
            "payload": {
                "@type": "ReviewableDocumentSignal",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-2",
                "review_status": "unreviewed",
                "reason": "weak_profile_document_signal",
            },
        }
    )
    return store


def insert_older_profile_record(store: SQLiteEvidenceStore) -> None:
    store.insert_evidence_import_batch(
        {
            "import_batch_id": "evidence-import:older-run:profile-status",
            "source_run_id": "older-run",
            "imported_at": "2026-06-20T10:00:00+00:00",
            "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/older-run",
            "record_count": 1,
            "payload_hash": "older-batch-hash",
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:older-claim-1",
            "import_batch_id": "evidence-import:older-run:profile-status",
            "source_run_id": "older-run",
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:older-doc",
            "review_status": "unreviewed",
            "payload_hash": "older-record-hash",
            "payload": {
                "@type": "CandidateEvidenceClaim",
                "profile_id": "person:purocielo:andreoli-dino",
                "field": "death.place",
                "value": "Older Purocielo",
                "source_document_id": "source-document:older-doc",
                "review_status": "unreviewed",
            },
        }
    )


def insert_other_profile_record(store: SQLiteEvidenceStore, *, source_run_id: str = "mvp-run-pipeline") -> None:
    store.insert_evidence_record(
        {
            "record_id": f"evidence-record:other-profile:{source_run_id}",
            "import_batch_id": "evidence-import:mvp-run:profile-status",
            "source_run_id": source_run_id,
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:altro",
            "source_document_id": "source-document:other-doc",
            "review_status": "unreviewed",
            "payload_hash": f"other-record-hash:{source_run_id}",
            "payload": {
                "@type": "CandidateEvidenceClaim",
                "profile_id": "person:purocielo:altro",
                "field": "birth.date",
                "value": "1920",
                "source_document_id": "source-document:other-doc",
            },
        }
    )


class EvidenceStoreProfileStatusTests(unittest.TestCase):
    def test_builds_read_only_profile_status_from_evidence_records(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = populated_store(db_path)
            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")
            output_json = tmp_dir / "profile_status.json"
            output_md = tmp_dir / "profile_status.md"

            status = build_evidence_store_profile_status(
                db_path=db_path,
                profile_id="person:purocielo:andreoli-dino",
                output_json=output_json,
                output_md=output_md,
            )
            after_records = store.count("evidence_records")
            after_claims = store.count("evidence_claims")
            written = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(before_records, after_records)
        self.assertEqual(before_claims, after_claims)
        self.assertEqual(status["@type"], "EvidenceStoreProfileStatus")
        self.assertEqual(status["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(status["record_count"], 5)
        self.assertEqual(status["counts_by_record_kind"]["candidate_evidence_claim"], 1)
        self.assertEqual(status["counts_by_record_kind"]["review_queue_item"], 1)
        self.assertEqual(status["counts_by_record_kind"]["review_decision"], 1)
        self.assertEqual(status["counts_by_record_kind"]["historical_review_decision"], 1)
        self.assertEqual(status["counts_by_record_kind"]["reviewable_document_signal"], 1)
        self.assertEqual(status["source_documents"][0]["source_document_id"], "source-document:doc-1")
        self.assertEqual(status["source_documents"][0]["document_review_state"], "decision_available")
        self.assertEqual(status["source_documents"][0]["candidate_claim_count"], 1)
        self.assertEqual(status["source_documents"][0]["review_item_count"], 1)
        self.assertEqual(status["source_documents"][0]["review_decision_count"], 2)
        self.assertEqual(
            status["source_documents"][0]["review_decision_record_ids"],
            ["evidence-record:decision-1", "evidence-record:historical-decision-1"],
        )
        self.assertEqual(status["source_documents"][1]["source_document_id"], "source-document:doc-2")
        self.assertEqual(status["source_documents"][1]["document_review_state"], "needs_review_item")
        self.assertEqual(status["document_review_coverage"]["document_count"], 2)
        self.assertEqual(status["document_review_coverage"]["documents_with_candidate_claims_count"], 1)
        self.assertEqual(status["document_review_coverage"]["documents_with_skipped_signals_count"], 1)
        self.assertEqual(status["document_review_coverage"]["documents_with_review_items_count"], 1)
        self.assertEqual(status["document_review_coverage"]["documents_with_review_decisions_count"], 1)
        self.assertEqual(status["document_review_coverage"]["documents_without_review_decisions_count"], 1)
        self.assertEqual(status["document_review_coverage"]["counts_by_document_review_state"]["decision_available"], 1)
        self.assertEqual(status["document_review_coverage"]["counts_by_document_review_state"]["needs_review_item"], 1)
        self.assertEqual(len(status["candidate_claims"]), 1)
        self.assertEqual(len(status["skipped_signals"]), 1)
        self.assertEqual(len(status["review_items"]), 1)
        self.assertEqual(len(status["review_decisions"]), 2)
        self.assertEqual(status["profile_evidence_review_state"], "approved_decision_available")
        self.assertIn("Valutare una preview dei fatti approvati", status["next_action"])
        self.assertEqual(written["record_count"], 5)
        self.assertIn("preview-only", markdown)
        self.assertIn("source-document:doc-1", markdown)
        self.assertIn("source-document:doc-2", markdown)
        self.assertIn("Copertura documenti", markdown)
        self.assertIn("decision_available", markdown)
        self.assertIn("needs_review_item", markdown)
        self.assertIn("Segnali scartati", markdown)
        self.assertIn("evidence-record:claim-1", markdown)
        self.assertIn("evidence-record:historical-decision-1", markdown)
        self.assertNotIn("workflow-1", json.dumps(status, ensure_ascii=False))

    def test_can_filter_profile_status_by_source_run_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = populated_store(db_path)
            insert_older_profile_record(store)
            before_records = store.count("evidence_records")
            output_json = tmp_dir / "profile_status.filtered.json"
            output_md = tmp_dir / "profile_status.filtered.md"

            status = build_evidence_store_profile_status(
                db_path=db_path,
                profile_id="person:purocielo:andreoli-dino",
                evidence_source_run_id=["mvp-run-pipeline"],
                output_json=output_json,
                output_md=output_md,
            )
            after_records = store.count("evidence_records")
            written = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(status, ensure_ascii=False)

        self.assertEqual(before_records, after_records)
        self.assertEqual(status["source_run_ids"], ["mvp-run-pipeline"])
        self.assertEqual(status["record_count"], 5)
        self.assertEqual(status["counts_by_source_run_id"], {"mvp-run-pipeline": 5})
        self.assertEqual(written["source_run_ids"], ["mvp-run-pipeline"])
        self.assertIn("mvp-run-pipeline", markdown)
        self.assertNotIn("older-run", serialized)
        self.assertNotIn("source-document:older-doc", serialized)

    def test_unfiltered_profile_status_keeps_append_only_history(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = populated_store(db_path)
            insert_older_profile_record(store)

            status = build_evidence_store_profile_status(
                db_path=db_path,
                profile_id="person:purocielo:andreoli-dino",
            )

        self.assertEqual(status["record_count"], 6)
        self.assertEqual(status["counts_by_source_run_id"]["mvp-run-pipeline"], 5)
        self.assertEqual(status["counts_by_source_run_id"]["older-run"], 1)

    def test_profile_match_can_use_candidate_profile_ids_inside_payload(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            store.insert_evidence_import_batch(
                {
                    "import_batch_id": "evidence-import:mvp-run:profile-status",
                    "source_run_id": "mvp-run-pipeline",
                    "imported_at": "2026-06-21T10:00:00+00:00",
                    "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/mvp-run-pipeline",
                    "record_count": 1,
                    "payload_hash": "batch-hash",
                }
            )
            store.insert_evidence_record(
                {
                    "record_id": "evidence-record:skipped-1",
                    "import_batch_id": "evidence-import:mvp-run:profile-status",
                    "source_run_id": "mvp-run-pipeline",
                    "record_kind": "skipped_candidate_claim",
                    "subject_id": "",
                    "source_document_id": "source-document:doc-2",
                    "review_status": "unreviewed",
                    "payload_hash": "record-hash",
                    "payload": {
                        "@type": "SkippedCandidateClaim",
                        "candidate_profile_ids": ["person:purocielo:andreoli-dino"],
                        "source_document_id": "source-document:doc-2",
                        "reason": "segment_too_crowded",
                    },
                }
            )

            status = build_evidence_store_profile_status(
                db_path=db_path,
                profile_id="person:purocielo:andreoli-dino",
            )

        self.assertEqual(status["record_count"], 1)
        self.assertEqual(status["candidate_claims"][0]["record_kind"], "skipped_candidate_claim")
        self.assertEqual(status["skipped_signals"][0]["record_kind"], "skipped_candidate_claim")
        self.assertEqual(status["profile_evidence_review_state"], "needs_historical_review_targets")
        self.assertIn("Generare o aggiornare target storici", status["next_action"])

    def test_profile_status_marks_pending_review_state_without_approved_decisions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            store.insert_evidence_import_batch(
                {
                    "import_batch_id": "evidence-import:mvp-run:profile-status",
                    "source_run_id": "mvp-run-pipeline",
                    "imported_at": "2026-06-21T10:00:00+00:00",
                    "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/mvp-run-pipeline",
                    "record_count": 1,
                    "payload_hash": "batch-hash",
                }
            )
            store.insert_evidence_record(
                {
                    "record_id": "evidence-record:item-1",
                    "import_batch_id": "evidence-import:mvp-run:profile-status",
                    "source_run_id": "mvp-run-pipeline",
                    "record_kind": "review_queue_item",
                    "subject_id": "person:purocielo:andreoli-dino",
                    "source_document_id": "source-document:doc-1",
                    "review_status": "pending",
                    "payload_hash": "record-hash",
                    "payload": {
                        "@type": "ReviewQueueItem",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "source_document_id": "source-document:doc-1",
                        "review_status": "pending",
                    },
                }
            )

            status = build_evidence_store_profile_status(
                db_path=db_path,
                profile_id="person:purocielo:andreoli-dino",
            )

        self.assertEqual(status["profile_evidence_review_state"], "pending_historical_review")

    def test_render_empty_status_is_explicit(self) -> None:
        payload = {
            "profile_id": "person:purocielo:missing",
            "review_status": "preview-only",
            "publication_status": "not_publishable_without_human_review",
            "record_count": 0,
            "source_documents": [],
            "candidate_claims": [],
            "review_items": [],
            "review_decisions": [],
            "skipped_signals": [],
            "profile_evidence_review_state": "no_evidence_records",
            "counts_by_record_kind": {},
            "empty_result_diagnostics": {
                "status": "store_empty",
                "evidence_store_record_count": 0,
                "requested_run_record_count": 0,
                "profile_record_count_all_runs": 0,
                "runs_with_profile": [],
                "profiles_in_requested_runs": [],
                "diagnostic_next_action": "Importare una run nello Evidence Store prima di usare profile-status.",
            },
            "document_review_coverage": {
                "document_count": 0,
                "documents_with_candidate_claims_count": 0,
                "documents_with_skipped_signals_count": 0,
                "documents_with_review_items_count": 0,
                "documents_with_review_decisions_count": 0,
                "documents_without_review_decisions_count": 0,
                "counts_by_document_review_state": {},
            },
            "next_action": "Importare una run utile nello evidence store per questo profilo.",
        }

        markdown = render_evidence_store_profile_status_markdown(payload)

        self.assertIn("Nessun record scopiato", markdown)
        self.assertIn("Nessun documento scopiato", markdown)
        self.assertIn("Diagnostica risultato vuoto", markdown)
        self.assertIn("store_empty", markdown)
        self.assertIn("Importare una run utile", markdown)

    def test_empty_status_points_to_other_run_when_profile_exists_elsewhere(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = populated_store(db_path)
            insert_older_profile_record(store)
            insert_other_profile_record(store)

            status = build_evidence_store_profile_status(
                db_path=db_path,
                profile_id="person:purocielo:andreoli-dino",
                evidence_source_run_id=["run-without-profile"],
            )
            markdown = render_evidence_store_profile_status_markdown(status)

        diagnostics = status["empty_result_diagnostics"]
        self.assertEqual(status["record_count"], 0)
        self.assertEqual(diagnostics["status"], "profile_available_in_other_runs")
        self.assertEqual(diagnostics["requested_run_record_count"], 0)
        self.assertEqual(diagnostics["profile_record_count_all_runs"], 6)
        self.assertEqual(diagnostics["runs_with_profile"][0]["source_run_id"], "mvp-run-pipeline")
        self.assertIn("run alternative", diagnostics["diagnostic_next_action"])
        self.assertIn("Diagnostica risultato vuoto", markdown)
        self.assertIn("mvp-run-pipeline", markdown)

    def test_empty_status_lists_profiles_present_in_requested_run(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = populated_store(db_path)
            insert_other_profile_record(store)

            status = build_evidence_store_profile_status(
                db_path=db_path,
                profile_id="person:purocielo:missing",
                evidence_source_run_id=["mvp-run-pipeline"],
            )

        diagnostics = status["empty_result_diagnostics"]
        self.assertEqual(status["record_count"], 0)
        self.assertEqual(diagnostics["status"], "requested_runs_have_other_profiles")
        self.assertEqual(diagnostics["requested_run_record_count"], 7)
        self.assertEqual(diagnostics["profile_record_count_all_runs"], 0)
        profile_ids = [item["profile_id"] for item in diagnostics["profiles_in_requested_runs"]]
        self.assertIn("person:purocielo:andreoli-dino", profile_ids)
        self.assertIn("person:purocielo:altro", profile_ids)


if __name__ == "__main__":
    unittest.main()
