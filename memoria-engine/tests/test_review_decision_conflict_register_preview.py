from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.review_decision_conflict_register_preview import (  # noqa: E402
    build_review_decision_conflict_register_preview,
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


def populated_store(db_path: Path) -> SQLiteEvidenceStore:
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    store.insert_evidence_import_batch(
        {
            "import_batch_id": "evidence-import:mvp-run:decision-register",
            "source_run_id": "mvp-run-pipeline",
            "imported_at": "2026-06-26T10:00:00+00:00",
            "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/mvp-run-pipeline",
            "record_count": 5,
            "payload_hash": "batch-hash",
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:historical-approved",
            "import_batch_id": "evidence-import:mvp-run:decision-register",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "historical_review_decision",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-1",
            "review_status": "approved",
            "payload_hash": "record-hash-approved",
            "payload": {
                "@type": "HistoricalReviewDecision",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "source_item_id": "review:item:1",
                "selected_action": "confirm",
                "decision_status": "approved",
                "reviewer": "storico",
                "reviewed_at": "2026-06-26",
                "candidate": {"field": "death.place", "value": "Purocielo"},
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:historical-conflict",
            "import_batch_id": "evidence-import:mvp-run:decision-register",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "historical_review_decision",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-2",
            "review_status": "pending",
            "payload_hash": "record-hash-conflict",
            "payload": {
                "@type": "HistoricalReviewDecision",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-2",
                "source_item_id": "review:item:2",
                "selected_action": "conflict_open",
                "decision_status": "conflict_open",
                "reviewer": "storico",
                "reviewed_at": "2026-06-26",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:workflow-decision",
            "import_batch_id": "evidence-import:mvp-run:decision-register",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "review_decision",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-3",
            "review_status": "pending",
            "payload_hash": "record-hash-workflow",
            "payload": {
                "@type": "ReviewDecision",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-3",
                "subject_kind": "workflow",
                "selected_action": "needs_better_ocr",
                "decision_status": "pending",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:other-profile",
            "import_batch_id": "evidence-import:mvp-run:decision-register",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "historical_review_decision",
            "subject_id": "person:purocielo:balboni-ugo",
            "source_document_id": "source-document:doc-4",
            "review_status": "approved",
            "payload_hash": "record-hash-other",
            "payload": {
                "@type": "HistoricalReviewDecision",
                "profile_id": "person:purocielo:balboni-ugo",
                "source_document_id": "source-document:doc-4",
                "selected_action": "confirm",
                "decision_status": "approved",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:claim-not-decision",
            "import_batch_id": "evidence-import:mvp-run:decision-register",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-5",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-claim",
            "payload": {"profile_id": "person:purocielo:andreoli-dino"},
        }
    )
    return store


class ReviewDecisionConflictRegisterPreviewTests(unittest.TestCase):
    def test_builds_preview_register_without_writing_store(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = populated_store(db_path)
            output_json = tmp_dir / "review_decision_conflict_register.preview.json"
            output_md = tmp_dir / "review_decision_conflict_register.preview.md"
            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")

            payload = build_review_decision_conflict_register_preview(
                evidence_db=db_path,
                evidence_source_run_id=["mvp-run-pipeline"],
                profile_id=["person:purocielo:andreoli-dino"],
                output_json=output_json,
                output_md=output_md,
            )
            after_records = store.count("evidence_records")
            after_claims = store.count("evidence_claims")
            written = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(before_records, after_records)
        self.assertEqual(before_claims, after_claims)
        self.assertEqual(payload["@type"], "ReviewDecisionConflictRegisterPreview")
        self.assertTrue(payload["preview_only"])
        self.assertEqual(payload["decision_count"], 3)
        self.assertEqual(payload["historical_decision_count"], 2)
        self.assertEqual(payload["operational_decision_count"], 1)
        self.assertEqual(payload["open_conflict_count"], 2)
        self.assertEqual(payload["eligible_for_verified_fact_preview_count"], 1)
        self.assertEqual(payload["counts_by_state"]["approved"], 1)
        self.assertEqual(payload["counts_by_state"]["conflict_open"], 1)
        self.assertEqual(payload["counts_by_state"]["request_more_sources"], 1)
        approved = next(item for item in payload["decisions"] if item["record_id"] == "evidence-record:historical-approved")
        self.assertTrue(approved["eligible_for_verified_fact_preview"])
        self.assertEqual(approved["provenance"]["payload_hash"], "record-hash-approved")
        workflow = next(item for item in payload["decisions"] if item["record_id"] == "evidence-record:workflow-decision")
        self.assertEqual(workflow["decision_scope"], "operational_or_workflow")
        self.assertFalse(workflow["eligible_for_verified_fact_preview"])
        self.assertEqual(written["decision_count"], 3)
        self.assertIn("preview-only", markdown)
        self.assertIn("Non risolve conflitti storici", markdown)
        self.assertNotIn("balboni", json.dumps(payload, ensure_ascii=False))

    def test_empty_run_is_explicit(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            output_json = tmp_dir / "review_decision_conflict_register.preview.json"
            output_md = tmp_dir / "review_decision_conflict_register.preview.md"

            payload = build_review_decision_conflict_register_preview(
                evidence_db=db_path,
                evidence_source_run_id=["empty-run"],
                output_json=output_json,
                output_md=output_md,
            )
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(payload["decision_count"], 0)
        self.assertEqual(payload["decisions"], [])
        self.assertEqual(payload["open_conflicts"], [])
        self.assertIn("Nessuna decisione", markdown)

    def test_requires_explicit_source_run_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()

            with self.assertRaises(ValueError):
                build_review_decision_conflict_register_preview(
                    evidence_db=db_path,
                    evidence_source_run_id=[],
                )


if __name__ == "__main__":
    unittest.main()
