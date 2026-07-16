from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.review_store_preview import (  # noqa: E402
    ReviewStoreDecisionPreview,
    build_review_store_preview,
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


def write_register(path: Path) -> None:
    payload = {
        "@type": "ReviewDecisionConflictRegisterPreview",
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "source_run_ids": ["mvp-run-pipeline"],
        "decisions": [
            {
                "record_id": "evidence-record:historical-approved",
                "source_run_id": "mvp-run-pipeline",
                "record_kind": "historical_review_decision",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "selected_action": "confirm",
                "decision_status": "approved",
                "normalized_state": "approved",
                "decision_scope": "historical_substantive",
                "reviewer": "storico",
                "reviewed_at": "2026-06-26",
                "provenance": {
                    "record_id": "evidence-record:historical-approved",
                    "source_run_id": "mvp-run-pipeline",
                    "payload_hash": "record-hash-approved",
                },
            },
            {
                "record_id": "evidence-record:historical-superseded",
                "source_run_id": "mvp-run-pipeline",
                "record_kind": "historical_review_decision",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "selected_action": "superseded",
                "decision_status": "superseded",
                "normalized_state": "superseded",
                "decision_scope": "historical_substantive",
                "supersedes": ["review-decision-preview:evidence-record-historical-approved"],
                "provenance": {
                    "record_id": "evidence-record:historical-superseded",
                    "source_run_id": "mvp-run-pipeline",
                    "payload_hash": "record-hash-superseded",
                },
            },
            {
                "record_id": "evidence-record:historical-uncertain",
                "source_run_id": "mvp-run-pipeline",
                "record_kind": "historical_review_decision",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-3",
                "selected_action": "uncertain",
                "decision_status": "uncertain",
                "normalized_state": "uncertain",
                "decision_scope": "historical_substantive",
                "reviewer": "",
                "reviewed_at": "",
                "provenance": {
                    "record_id": "evidence-record:historical-uncertain",
                    "source_run_id": "mvp-run-pipeline",
                    "payload_hash": "record-hash-uncertain",
                },
            },
            {
                "record_id": "evidence-record:other-profile",
                "source_run_id": "mvp-run-pipeline",
                "record_kind": "historical_review_decision",
                "profile_id": "person:purocielo:balboni-ugo",
                "source_document_id": "source-document:doc-2",
                "selected_action": "confirm",
                "decision_status": "approved",
                "normalized_state": "approved",
                "decision_scope": "historical_substantive",
                "provenance": {"record_id": "evidence-record:other-profile"},
            },
        ],
        "open_conflicts": [
            {
                "@type": "ConflictCasePreview",
                "conflict_id": "conflict-preview:evidence-record-historical-conflict",
                "source_decision_record_id": "evidence-record:historical-approved",
                "source_run_id": "mvp-run-pipeline",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "normalized_state": "conflict_open",
                "resolution_policy": "requires_human_review",
                "provenance": {"record_id": "evidence-record:historical-approved"},
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def populated_store(db_path: Path) -> SQLiteEvidenceStore:
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    store.insert_evidence_import_batch(
        {
            "import_batch_id": "evidence-import:mvp-run:review-store",
            "source_run_id": "mvp-run-pipeline",
            "imported_at": "2026-06-26T10:00:00+00:00",
            "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/mvp-run-pipeline",
            "record_count": 2,
            "payload_hash": "batch-hash",
        }
    )
    for record_id, payload_hash in (
        ("evidence-record:historical-approved", "record-hash-approved"),
        ("evidence-record:historical-superseded", "record-hash-superseded"),
        ("evidence-record:historical-uncertain", "record-hash-uncertain"),
    ):
        store.insert_evidence_record(
            {
                "record_id": record_id,
                "import_batch_id": "evidence-import:mvp-run:review-store",
                "source_run_id": "mvp-run-pipeline",
                "record_kind": "historical_review_decision",
                "subject_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "review_status": "approved",
                "payload_hash": payload_hash,
                "payload": {"profile_id": "person:purocielo:andreoli-dino"},
            }
        )
    return store


class ReviewStorePreviewTests(unittest.TestCase):
    def test_decision_preview_contract_normalizes_state_and_preserves_provenance(self) -> None:
        decision = ReviewStoreDecisionPreview.from_register_decision(
            {
                "record_id": "evidence-record:historical-weird-state",
                "source_run_id": "mvp-run-pipeline",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "source-document:doc-1",
                "normalized_state": "needs_editorial_magic",
                "decision_scope": "historical_substantive",
                "review_item_id": "review-item:1",
                "selected_action": "confirm",
                "decision_status": "approved",
                "reviewer": "storico",
                "reviewed_at": "2026-06-27",
                "supersedes": ["review-decision-preview:old", ""],
                "superseded_by": "review-decision-preview:new",
                "provenance": {
                    "record_id": "evidence-record:historical-weird-state",
                    "source_run_id": "mvp-run-pipeline",
                    "payload_hash": "record-hash",
                },
            }
        )

        payload = decision.to_payload()

        self.assertEqual(payload["@type"], "ReviewDecisionStoreEntryPreview")
        self.assertEqual(payload["decision_id"], "review-decision-preview:evidence-record-historical-weird-state")
        self.assertEqual(payload["version"], "v1")
        self.assertEqual(payload["state"], "unknown")
        self.assertEqual(payload["review_item_id"], "review-item:1")
        self.assertEqual(payload["supersedes"], ["review-decision-preview:old"])
        self.assertEqual(payload["superseded_by"], ["review-decision-preview:new"])
        self.assertEqual(payload["provenance"]["payload_hash"], "record-hash")
        self.assertEqual(payload["versioning_policy"], "append_new_version_for_corrections")
        self.assertEqual(payload["superseding_policy"], "requires_explicit_human_decision_link")

    def test_builds_review_store_preview_without_writing_store(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            register_json = tmp_dir / "review_decision_conflict_register.preview.json"
            db_path = tmp_dir / "evidence.sqlite"
            output_json = tmp_dir / "review_store.preview.json"
            output_md = tmp_dir / "review_store.preview.md"
            write_register(register_json)
            store = populated_store(db_path)
            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")

            payload = build_review_store_preview(
                review_register_json=register_json,
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
        self.assertEqual(payload["@type"], "ReviewStorePreview")
        self.assertTrue(payload["preview_only"])
        self.assertEqual(payload["decision_count"], 3)
        self.assertEqual(payload["conflict_count"], 1)
        self.assertEqual(payload["review_decisions"][0]["version"], "v1")
        self.assertEqual(payload["review_decisions"][0]["state"], "approved")
        self.assertEqual(payload["review_decisions"][1]["state"], "superseded")
        self.assertEqual(payload["review_decisions"][1]["supersedes"], ["review-decision-preview:evidence-record-historical-approved"])
        self.assertEqual(payload["review_decisions"][2]["state"], "uncertain")
        self.assertEqual(payload["counts_by_state"]["approved"], 1)
        self.assertEqual(payload["counts_by_state"]["superseded"], 1)
        self.assertEqual(payload["counts_by_state"]["uncertain"], 1)
        self.assertEqual(payload["counts_by_state"]["unknown"], 0)
        self.assertEqual(payload["terminal_decision_count"], 2)
        self.assertEqual(payload["open_decision_count"], 1)
        self.assertEqual(payload["unknown_state_count"], 0)
        self.assertEqual(payload["missing_reviewer_count"], 2)
        self.assertEqual(payload["missing_reviewed_at_count"], 2)
        self.assertEqual(payload["conflicts"][0]["resolution_policy"], "requires_human_review")
        self.assertEqual(payload["conflicts"][0]["linked_decision_ids"], ["review-decision-preview:evidence-record-historical-approved"])
        self.assertEqual(payload["evidence_validation"]["status"], "checked")
        self.assertEqual(payload["evidence_validation"]["missing_record_ids"], [])
        self.assertEqual(written["decision_count"], 3)
        self.assertEqual(written["counts_by_state"]["uncertain"], 1)
        self.assertIn("preview-only", markdown)
        self.assertIn("## Copertura stati", markdown)
        self.assertIn("- `uncertain`: `1`", markdown)
        self.assertIn("Decisioni senza revisore: `2`", markdown)
        self.assertIn("Non crea tabelle canoniche", markdown)
        self.assertNotIn("balboni", json.dumps(payload, ensure_ascii=False))

    def test_empty_register_is_explicit(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            register_json = tmp_dir / "review_decision_conflict_register.preview.json"
            output_json = tmp_dir / "review_store.preview.json"
            output_md = tmp_dir / "review_store.preview.md"
            register_json.write_text(
                json.dumps({"@type": "ReviewDecisionConflictRegisterPreview", "decisions": [], "open_conflicts": []}),
                encoding="utf-8",
            )

            payload = build_review_store_preview(
                review_register_json=register_json,
                output_json=output_json,
                output_md=output_md,
            )
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(payload["decision_count"], 0)
        self.assertEqual(payload["conflict_count"], 0)
        self.assertEqual(payload["evidence_validation"]["status"], "not_requested")
        self.assertIn("Nessuna decisione", markdown)

    def test_requires_source_run_when_validating_evidence_db(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            register_json = tmp_dir / "review_decision_conflict_register.preview.json"
            db_path = tmp_dir / "evidence.sqlite"
            write_register(register_json)
            store = populated_store(db_path)

            with self.assertRaises(ValueError):
                build_review_store_preview(
                    review_register_json=register_json,
                    evidence_db=db_path,
                    evidence_source_run_id=[],
                )


if __name__ == "__main__":
    unittest.main()
