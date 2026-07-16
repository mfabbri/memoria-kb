from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.dataset_export_preview import build_dataset_export_preview
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
            "import_batch_id": "evidence-import:mvp-run:dataset-export",
            "source_run_id": "mvp-run-pipeline",
            "imported_at": "2026-06-25T10:00:00+00:00",
            "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/mvp-run-pipeline",
            "record_count": 4,
            "payload_hash": "batch-hash",
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:claim-1",
            "import_batch_id": "evidence-import:mvp-run:dataset-export",
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
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:historical-decision-1",
            "import_batch_id": "evidence-import:mvp-run:dataset-export",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "historical_review_decision",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-1",
            "review_status": "approved",
            "payload_hash": "record-hash-2",
            "payload": {
                "@type": "HistoricalReviewDecision",
                "decision_id": "historical-review-decision:1",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "source_item_id": "review:item:1",
                "selected_action": "confirm",
                "decision_status": "approved",
                "reviewer": "storico",
                "reviewed_at": "2026-06-25",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:review-decision-1",
            "import_batch_id": "evidence-import:mvp-run:dataset-export",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "review_decision",
            "subject_id": "person:purocielo:andreoli-dino",
            "source_document_id": "source-document:doc-1",
            "review_status": "pending",
            "payload_hash": "record-hash-3",
            "payload": {
                "@type": "ReviewDecision",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "selected_action": "request_more_sources",
                "decision_status": "pending",
            },
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:other-profile-1",
            "import_batch_id": "evidence-import:mvp-run:dataset-export",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:balboni-ugo",
            "source_document_id": "source-document:doc-2",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-4",
            "payload": {
                "@type": "CandidateEvidenceClaim",
                "profile_id": "person:purocielo:balboni-ugo",
                "source_document_id": "source-document:doc-2",
            },
        }
    )
    return store


def write_verified_facts_preview(path: Path) -> None:
    payload = {
        "@type": "VerifiedFactsPreview",
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "fact_count": 2,
        "excluded_decision_count": 0,
        "facts": [
            {
                "@type": "VerifiedFactPreview",
                "fact_id": "verified-fact-preview:andreoli:death-place",
                "profile_id": "person:purocielo:andreoli-dino",
                "field": "death.place",
                "value": "Purocielo",
                "source_document_id": "source-document:doc-1",
                "source_run_id": "mvp-run-pipeline",
                "source_decision_record_id": "evidence-record:historical-decision-1",
                "reviewer": "storico",
                "reviewed_at": "2026-06-25",
                "provenance": [
                    "historical_review_decision_record_id=evidence-record:historical-decision-1",
                    "source_run_id=mvp-run-pipeline",
                    "source_document_id=source-document:doc-1",
                    "payload_hash=record-hash-2",
                ],
            },
            {
                "@type": "VerifiedFactPreview",
                "fact_id": "verified-fact-preview:balboni:death-place",
                "profile_id": "person:purocielo:balboni-ugo",
                "field": "death.place",
                "value": "Monte",
                "source_document_id": "source-document:doc-2",
                "source_run_id": "mvp-run-pipeline",
                "source_decision_record_id": "evidence-record:other-decision",
                "provenance": [],
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_profile_patch_preview(path: Path) -> None:
    payload = {
        "@type": "ProfilePatchPreviewBatch",
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "apply_policy": "requires_explicit_apply_profile_patch_command",
        "patch_count": 2,
        "operation_count": 2,
        "profile_patches": [
            {
                "@type": "ProfilePatch",
                "profile_id": "person:purocielo:andreoli-dino",
                "review_status": "preview-only",
                "publication_status": "not_publishable_without_editorial_review",
                "apply_policy": "requires_explicit_apply_profile_patch_command",
                "operations": [
                    {
                        "operation_id": "profile-patch-preview-operation:1",
                        "op": "set",
                        "path": "/death/place",
                        "value": "Purocielo",
                        "verified_fact_preview_id": "verified-fact-preview:andreoli:death-place",
                        "source_document_id": "source-document:doc-1",
                        "source_run_id": "mvp-run-pipeline",
                        "source_decision_record_id": "evidence-record:historical-decision-1",
                        "provenance": ["payload_hash=record-hash-2"],
                    }
                ],
            },
            {
                "@type": "ProfilePatch",
                "profile_id": "person:purocielo:balboni-ugo",
                "operations": [
                    {
                        "operation_id": "profile-patch-preview-operation:2",
                        "op": "set",
                        "path": "/death/place",
                        "value": "Monte",
                    }
                ],
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class DatasetExportPreviewTests(unittest.TestCase):
    def test_builds_preview_dataset_from_store_and_preview_files(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = populated_store(db_path)
            verified_path = tmp_dir / "verified_facts.preview.json"
            patch_path = tmp_dir / "profile_patch.preview.json"
            output_json = tmp_dir / "dataset_export.preview.json"
            output_md = tmp_dir / "dataset_export.preview.md"
            write_verified_facts_preview(verified_path)
            write_profile_patch_preview(patch_path)
            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")

            payload = build_dataset_export_preview(
                evidence_db=db_path,
                evidence_source_run_id=["mvp-run-pipeline"],
                profile_id=["person:purocielo:andreoli-dino"],
                verified_facts_preview_json=verified_path,
                profile_patch_preview_json=patch_path,
                output_json=output_json,
                output_md=output_md,
            )
            after_records = store.count("evidence_records")
            after_claims = store.count("evidence_claims")
            written = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(before_records, after_records)
        self.assertEqual(before_claims, after_claims)
        self.assertEqual(payload["@type"], "DatasetExportPreview")
        self.assertTrue(payload["preview_only"])
        self.assertEqual(payload["publication_status"], "not_publishable_without_editorial_review")
        self.assertEqual(payload["record_count"], 3)
        self.assertEqual(len(payload["persons"]), 1)
        self.assertEqual(payload["persons"][0]["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(payload["source_documents"][0]["source_document_id"], "source-document:doc-1")
        self.assertEqual(len(payload["review_decisions"]), 2)
        self.assertEqual(payload["review_decisions"][0]["payload_hash"], "record-hash-2")
        self.assertEqual(payload["verified_facts_preview"]["fact_count"], 1)
        self.assertEqual(payload["profile_patch_preview"]["patch_count"], 1)
        self.assertEqual(payload["profile_patch_preview"]["operation_count"], 1)
        self.assertIn("evidence-record:claim-1", payload["provenance"]["record_ids"])
        self.assertEqual(written["record_count"], 3)
        self.assertIn("preview-only", markdown)
        self.assertIn("Non e' un dataset canonico", markdown)
        self.assertNotIn("balboni", json.dumps(payload, ensure_ascii=False))

    def test_empty_run_is_explicit_and_does_not_fail(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            output_json = tmp_dir / "dataset_export.preview.json"
            output_md = tmp_dir / "dataset_export.preview.md"

            payload = build_dataset_export_preview(
                evidence_db=db_path,
                evidence_source_run_id=["empty-run"],
                output_json=output_json,
                output_md=output_md,
            )
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(payload["record_count"], 0)
        self.assertEqual(payload["persons"], [])
        self.assertEqual(payload["source_documents"], [])
        self.assertEqual(payload["review_decisions"], [])
        self.assertEqual(payload["verified_facts_preview"]["status"], "not_provided")
        self.assertIn("Nessuna persona", markdown)
        self.assertIn("Nessuna decisione review", markdown)

    def test_requires_explicit_source_run_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()

            with self.assertRaises(ValueError):
                build_dataset_export_preview(
                    evidence_db=db_path,
                    evidence_source_run_id=[],
                )


if __name__ == "__main__":
    unittest.main()
