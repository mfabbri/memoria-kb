from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.verified_facts_preview import (  # noqa: E402
    build_verified_facts_preview,
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


def insert_batch(store: SQLiteEvidenceStore) -> None:
    store.insert_evidence_import_batch(
        {
            "import_batch_id": "evidence-import:verified-facts-preview",
            "source_run_id": "verified-preview-run",
            "imported_at": "2026-06-21T10:00:00+00:00",
            "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/verified-preview-run",
            "record_count": 4,
            "payload_hash": "batch-hash",
        }
    )


def decision_record(
    *,
    record_id: str,
    selected_action: str,
    decision_status: str = "accepted",
    source_document_id: str = "source-document:doc-1",
    candidate: dict[str, str] | None = None,
    subject_kind: str = "claim",
) -> dict[str, object]:
    return {
        "record_id": record_id,
        "import_batch_id": "evidence-import:verified-facts-preview",
        "source_run_id": "verified-preview-run",
        "record_kind": "historical_review_decision",
        "subject_id": "person:purocielo:andreoli-dino",
        "source_document_id": source_document_id,
        "review_status": "pending",
        "payload_hash": f"hash-{record_id}",
        "payload": {
            "@type": "HistoricalReviewDecision",
            "decision_id": record_id.replace("evidence-record:", "historical-review-decision:"),
            "item_id": "mvp-review-item:0001",
            "source_item_id": "candidate-evidence-claim:andreoli",
            "profile_id": "person:purocielo:andreoli-dino",
            "source_document_id": source_document_id,
            "subject_kind": subject_kind,
            "selected_action": selected_action,
            "decision_status": decision_status,
            "reviewer": "storico-test",
            "reviewed_at": "2026-06-21",
            "candidate": candidate if candidate is not None else {"field": "death.place", "value": "Purocielo"},
        },
    }


def non_historical_decision_record() -> dict[str, object]:
    record = decision_record(record_id="evidence-record:decision-non-historical", selected_action="confirm")
    record["record_kind"] = "review_decision"
    payload = record["payload"]
    assert isinstance(payload, dict)
    payload["@type"] = "ReviewDecision"
    return record


class VerifiedFactsPreviewTests(unittest.TestCase):
    def test_builds_preview_facts_only_from_confirmed_historical_decisions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            insert_batch(store)
            for record in [
                decision_record(record_id="evidence-record:decision-confirm", selected_action="confirm"),
                non_historical_decision_record(),
                decision_record(record_id="evidence-record:decision-search", selected_action="accept_for_search"),
                decision_record(record_id="evidence-record:decision-workflow", selected_action="confirm", subject_kind="workflow"),
                decision_record(record_id="evidence-record:decision-no-doc", selected_action="confirm", source_document_id=""),
                decision_record(record_id="evidence-record:decision-no-candidate", selected_action="confirm", candidate={}),
            ]:
                store.insert_evidence_record(record)
            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")
            output_json = tmp_dir / "verified_facts.preview.json"
            output_md = tmp_dir / "verified_facts.preview.md"

            preview = build_verified_facts_preview(
                evidence_db=db_path,
                evidence_source_run_id=["verified-preview-run"],
                output_json=output_json,
                output_md=output_md,
            )
            after_records = store.count("evidence_records")
            after_claims = store.count("evidence_claims")
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False)

        self.assertEqual(before_records, after_records)
        self.assertEqual(before_claims, after_claims)
        self.assertEqual(preview["@type"], "VerifiedFactsPreview")
        self.assertTrue(preview["preview_only"])
        self.assertEqual(persisted["fact_count"], 1)
        self.assertEqual(persisted["excluded_decision_count"], 4)
        fact = persisted["facts"][0]
        self.assertEqual(fact["@type"], "VerifiedFactPreview")
        self.assertEqual(fact["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(fact["field"], "death.place")
        self.assertEqual(fact["value"], "Purocielo")
        self.assertEqual(fact["source_document_id"], "source-document:doc-1")
        self.assertEqual(fact["source_decision_record_id"], "evidence-record:decision-confirm")
        self.assertIn("historical_review_decision_record_id=evidence-record:decision-confirm", fact["provenance"])
        self.assertIn("azione_non_fattuale:accept_for_search", serialized)
        self.assertIn("decisione_workflow", serialized)
        self.assertIn("campo_mancante:source_document_id", serialized)
        self.assertIn("campo_mancante:field", serialized)
        self.assertIn("preview-only", markdown)
        self.assertIn("accept_for_search", markdown)
        self.assertNotIn("decision-non-historical", serialized)
        self.assertNotIn('"ProfilePatch"', serialized)

    def test_filters_preview_by_profile_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            insert_batch(store)
            store.insert_evidence_record(decision_record(record_id="evidence-record:decision-confirm", selected_action="confirm"))

            preview = build_verified_facts_preview(
                evidence_db=db_path,
                evidence_source_run_id=["verified-preview-run"],
                profile_id=["person:purocielo:balboni-william"],
            )

        self.assertEqual(preview["fact_count"], 0)
        self.assertEqual(preview["excluded_decision_count"], 0)

    def test_requires_explicit_source_run_filter(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()

            with self.assertRaises(ValueError):
                build_verified_facts_preview(evidence_db=db_path, evidence_source_run_id=[])


if __name__ == "__main__":
    unittest.main()
