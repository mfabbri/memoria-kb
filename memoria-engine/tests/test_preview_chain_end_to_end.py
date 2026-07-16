from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.dataset_export_preview import build_dataset_export_preview  # noqa: E402
from caduti_fonti_report.document_analysis.review_decision_conflict_register_preview import (  # noqa: E402
    build_review_decision_conflict_register_preview,
)
from caduti_fonti_report.document_analysis.review_store_preview import build_review_store_preview  # noqa: E402
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
            "import_batch_id": "evidence-import:mvp-run:preview-chain",
            "source_run_id": "mvp-run-pipeline",
            "imported_at": "2026-06-28T10:00:00+00:00",
            "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/mvp-run-pipeline",
            "record_count": 3,
            "payload_hash": "batch-hash",
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:historical-approved",
            "import_batch_id": "evidence-import:mvp-run:preview-chain",
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
                "source_item_id": "review:item:approved",
                "selected_action": "confirm",
                "decision_status": "approved",
                "reviewer": "storico",
                "reviewed_at": "2026-06-28",
                "candidate": {"field": "death.place", "value": "Purocielo"},
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:historical-conflict",
            "import_batch_id": "evidence-import:mvp-run:preview-chain",
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
                "source_item_id": "review:item:conflict",
                "selected_action": "conflict_open",
                "decision_status": "conflict_open",
                "reviewer": "storico",
                "reviewed_at": "2026-06-28",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:candidate-context",
            "import_batch_id": "evidence-import:mvp-run:preview-chain",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-3",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-candidate",
            "payload": {
                "@type": "CandidateEvidenceClaim",
                "profile_id": "person:purocielo:andreoli-dino",
                "field": "death.place",
                "value": "Purocielo",
                "source_document_id": "source-document:doc-3",
            },
        }
    )
    return store


class PreviewChainEndToEndTests(unittest.TestCase):
    def test_register_review_store_and_dataset_export_keep_preview_provenance(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = populated_store(db_path)
            register_json = tmp_dir / "review_decision_conflict_register.preview.json"
            register_md = tmp_dir / "review_decision_conflict_register.preview.md"
            review_store_json = tmp_dir / "review_store.preview.json"
            review_store_md = tmp_dir / "review_store.preview.md"
            dataset_json = tmp_dir / "dataset_export.preview.json"
            dataset_md = tmp_dir / "dataset_export.preview.md"
            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")

            register_payload = build_review_decision_conflict_register_preview(
                evidence_db=db_path,
                evidence_source_run_id=["mvp-run-pipeline"],
                profile_id=["person:purocielo:andreoli-dino"],
                output_json=register_json,
                output_md=register_md,
            )
            review_store_payload = build_review_store_preview(
                review_register_json=register_json,
                evidence_db=db_path,
                evidence_source_run_id=["mvp-run-pipeline"],
                profile_id=["person:purocielo:andreoli-dino"],
                output_json=review_store_json,
                output_md=review_store_md,
            )
            dataset_payload = build_dataset_export_preview(
                evidence_db=db_path,
                evidence_source_run_id=["mvp-run-pipeline"],
                profile_id=["person:purocielo:andreoli-dino"],
                output_json=dataset_json,
                output_md=dataset_md,
            )
            after_records = store.count("evidence_records")
            after_claims = store.count("evidence_claims")
            written_review_store = json.loads(review_store_json.read_text(encoding="utf-8"))
            written_dataset = json.loads(dataset_json.read_text(encoding="utf-8"))

        self.assertEqual(before_records, after_records)
        self.assertEqual(before_claims, after_claims)
        self.assertTrue(register_payload["preview_only"])
        self.assertTrue(review_store_payload["preview_only"])
        self.assertTrue(dataset_payload["preview_only"])

        approved_register = next(
            item for item in register_payload["decisions"] if item["record_id"] == "evidence-record:historical-approved"
        )
        approved_store = next(
            item
            for item in review_store_payload["review_decisions"]
            if item["source_record_id"] == "evidence-record:historical-approved"
        )
        approved_dataset = next(
            item for item in dataset_payload["review_decisions"] if item["record_id"] == "evidence-record:historical-approved"
        )

        self.assertEqual(register_payload["decision_count"], 2)
        self.assertEqual(register_payload["open_conflict_count"], 1)
        self.assertEqual(review_store_payload["decision_count"], 2)
        self.assertEqual(review_store_payload["conflict_count"], 1)
        self.assertEqual(dataset_payload["record_count"], 3)
        self.assertEqual(len(dataset_payload["review_decisions"]), 2)
        self.assertEqual(dataset_payload["verified_facts_preview"]["status"], "not_provided")

        self.assertEqual(approved_register["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(approved_store["profile_id"], approved_register["profile_id"])
        self.assertEqual(approved_dataset["profile_id"], approved_register["profile_id"])
        self.assertEqual(approved_store["source_document_id"], "source-document:doc-1")
        self.assertEqual(approved_dataset["source_document_id"], "source-document:doc-1")
        self.assertEqual(approved_register["source_run_id"], "mvp-run-pipeline")
        self.assertEqual(approved_store["source_run_id"], "mvp-run-pipeline")
        self.assertEqual(approved_dataset["source_run_id"], "mvp-run-pipeline")
        self.assertEqual(approved_register["provenance"]["payload_hash"], "record-hash-approved")
        self.assertEqual(approved_store["provenance"]["payload_hash"], "record-hash-approved")
        self.assertEqual(approved_dataset["payload_hash"], "record-hash-approved")

        conflict = review_store_payload["conflicts"][0]
        self.assertEqual(conflict["source_record_id"], "evidence-record:historical-conflict")
        self.assertEqual(conflict["state"], "conflict_open")
        self.assertEqual(conflict["resolution_policy"], "requires_human_review")
        self.assertEqual(conflict["linked_decision_ids"], ["review-decision-preview:evidence-record-historical-conflict"])

        self.assertIn("evidence-record:candidate-context", dataset_payload["provenance"]["record_ids"])
        self.assertNotIn("evidence-record:candidate-context", [item["record_id"] for item in register_payload["decisions"]])
        self.assertEqual(written_review_store["decision_count"], 2)
        self.assertEqual(written_dataset["record_count"], 3)


if __name__ == "__main__":
    unittest.main()
