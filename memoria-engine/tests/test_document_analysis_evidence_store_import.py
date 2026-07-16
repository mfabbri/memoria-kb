from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.evidence_store_import import import_document_analysis_evidence_to_db
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


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class DocumentAnalysisEvidenceStoreImportTests(unittest.TestCase):
    def test_imports_candidate_records_without_promoting_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "mvp-run-pipeline"
            write_json(run_dir / "manifest.json", {"run_id": "mvp-run-pipeline"})
            write_json(
                run_dir / "document_analysis" / "candidate_document_person_links.json",
                {
                    "@type": "CandidateDocumentPersonLinkSet",
                    "candidate_document_person_links": [
                        {
                            "@type": "CandidateDocumentPersonLink",
                            "@id": "candidate-link:1",
                            "profile_id": "person:purocielo:bagni-alfonso",
                            "source_document_id": "source-document:doc-1",
                            "review_status": "unreviewed",
                        }
                    ],
                },
            )
            write_json(
                run_dir / "document_analysis" / "extracted_entities.json",
                {
                    "@type": "ExtractedEntitySet",
                    "extracted_entities": [
                        {
                            "@type": "ExtractedEntity",
                            "@id": "entity:1",
                            "entity_type": "place",
                            "value": "Purocielo",
                            "source_document_id": "source-document:doc-1",
                            "review_status": "unreviewed",
                        }
                    ],
                },
            )
            write_json(
                run_dir / "document_analysis" / "candidate_evidence_claims.json",
                {
                    "@type": "CandidateEvidenceClaimSet",
                    "candidate_evidence_claims": [
                        {
                            "@type": "CandidateEvidenceClaim",
                            "@id": "candidate-claim:1",
                            "profile_id": "person:purocielo:bagni-alfonso",
                            "field": "death.place",
                            "value": "Purocielo",
                            "source_document_id": "source-document:doc-1",
                            "review_status": "unreviewed",
                        }
                    ],
                    "skipped_entities": [
                        {
                            "@type": "SkippedCandidateClaim",
                            "@id": "skipped-claim:1",
                            "candidate_profile_ids": ["person:purocielo:bagni-alfonso"],
                            "source_document_id": "source-document:doc-1",
                            "reason": "segment_too_crowded",
                            "review_status": "unreviewed",
                        }
                    ],
                },
            )
            write_json(
                run_dir / "historian_review" / "review_queue.json",
                {
                    "items": [
                        {
                            "item_id": "review:item:1",
                            "profile_id": "person:purocielo:bagni-alfonso",
                            "source_document_id": "source-document:doc-1",
                            "review_status": "pending",
                        }
                        ,
                        {
                            "item_id": "review:item:workflow",
                            "subject_kind": "workflow",
                            "source_document_id": "",
                            "review_status": "unreviewed",
                        }
                    ]
                },
            )
            write_json(
                run_dir / "historian_review" / "review_decisions_summary.json",
                {
                    "decisions": [
                        {
                            "decision_id": "review-decision:1",
                            "item_id": "review:item:1",
                            "profile_id": "person:purocielo:bagni-alfonso",
                            "source_document_id": "source-document:doc-1",
                            "selected_action": "",
                            "subject_kind": "claim",
                            "review_status": "pending",
                            "decision_status": "pending",
                        },
                        {
                            "decision_id": "review-decision:historical-1",
                            "item_id": "review:item:historical-1",
                            "source_item_id": "candidate-claim:1",
                            "profile_id": "person:purocielo:bagni-alfonso",
                            "source_document_id": "source-document:doc-1",
                            "subject_kind": "claim",
                            "selected_action": "accept_for_search",
                            "decision_status": "accepted",
                            "reviewer": "storico-test",
                            "reviewed_at": "2026-06-21T12:00:00+00:00",
                            "notes": "Decisione storica sostanziale di test.",
                            "candidate": {"field": "death.place", "value": "Purocielo"},
                        },
                        {
                            "decision_id": "review-decision:workflow-1",
                            "item_id": "review:item:workflow",
                            "profile_id": "",
                            "source_document_id": "",
                            "subject_kind": "workflow",
                            "selected_action": "accept_for_search",
                            "decision_status": "accepted",
                        }
                    ]
                },
            )
            db_path = tmp_dir / "evidence.sqlite"

            result = import_document_analysis_evidence_to_db(
                run_dir=run_dir,
                db_path=db_path,
                output_json=run_dir / "evidence_store_import.json",
                output_md=run_dir / "evidence_store_import.md",
            )
            store = SQLiteEvidenceStore(db_path)
            records = store.fetch_all("evidence_records")
            evidence_claim_count = store.count("evidence_claims")
            payload_text = "\n".join(row["payload_json"] for row in records)
            subjects = {row["subject_id"] for row in records}
            records_by_kind = {}
            for row in records:
                records_by_kind.setdefault(row["record_kind"], []).append(row)

        self.assertEqual(result["record_count"], 9)
        self.assertEqual(result["inserted_record_count"], 9)
        self.assertEqual(evidence_claim_count, 0)
        self.assertEqual(result["record_kind_counts"]["candidate_evidence_claim"], 1)
        self.assertEqual(result["record_kind_counts"]["skipped_candidate_claim"], 1)
        self.assertEqual(result["record_kind_counts"]["review_decision"], 2)
        self.assertEqual(result["record_kind_counts"]["historical_review_decision"], 1)
        self.assertEqual(result["coverage"]["with_subject_count"], 6)
        self.assertEqual(result["coverage"]["with_source_document_count"], 7)
        self.assertEqual(result["coverage"]["workflow_unscoped_count"], 2)
        self.assertIn("person:purocielo:bagni-alfonso", subjects)
        self.assertIn("CandidateEvidenceClaim", payload_text)
        self.assertIn("SkippedCandidateClaim", payload_text)
        self.assertIn("HistoricalReviewDecision", payload_text)
        historical_record = records_by_kind["historical_review_decision"][0]
        historical_payload = json.loads(historical_record["payload_json"])["payload"]
        self.assertEqual(historical_record["subject_id"], "person:purocielo:bagni-alfonso")
        self.assertEqual(historical_record["source_document_id"], "source-document:doc-1")
        self.assertEqual(historical_payload["source_item_id"], "candidate-claim:1")
        self.assertEqual(historical_payload["selected_action"], "accept_for_search")
        self.assertEqual(historical_payload["reviewer"], "storico-test")
        self.assertNotIn("verified_facts", payload_text)

    def test_reimport_same_run_is_idempotent_and_payload_change_appends_record(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            run_dir = tmp_dir / "mvp-run-pipeline"
            claims_path = run_dir / "document_analysis" / "candidate_evidence_claims.json"
            write_json(run_dir / "manifest.json", {"run_id": "mvp-run-pipeline"})
            write_json(
                claims_path,
                {
                    "candidate_evidence_claims": [
                        {
                            "@id": "candidate-claim:1",
                            "profile_id": "person:purocielo:bagni-alfonso",
                            "field": "death.place",
                            "value": "Purocielo",
                            "source_document_id": "source-document:doc-1",
                            "review_status": "unreviewed",
                        }
                    ]
                },
            )
            db_path = tmp_dir / "evidence.sqlite"

            first = import_document_analysis_evidence_to_db(run_dir=run_dir, db_path=db_path)
            second = import_document_analysis_evidence_to_db(run_dir=run_dir, db_path=db_path)
            write_json(
                claims_path,
                {
                    "candidate_evidence_claims": [
                        {
                            "@id": "candidate-claim:1",
                            "profile_id": "person:purocielo:bagni-alfonso",
                            "field": "death.place",
                            "value": "Puro Cielo",
                            "source_document_id": "source-document:doc-1",
                            "review_status": "unreviewed",
                        }
                    ]
                },
            )
            third = import_document_analysis_evidence_to_db(run_dir=run_dir, db_path=db_path)
            store = SQLiteEvidenceStore(db_path)
            evidence_record_count = store.count("evidence_records")

        self.assertEqual(first["inserted_record_count"], 1)
        self.assertEqual(second["inserted_record_count"], 0)
        self.assertEqual(third["inserted_record_count"], 1)
        self.assertEqual(evidence_record_count, 2)


if __name__ == "__main__":
    unittest.main()
