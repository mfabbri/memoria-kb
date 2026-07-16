from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_historical_review_targets import (  # noqa: E402
    build_mvp_historical_review_targets,
)
from caduti_fonti_report.document_analysis.mvp_historical_review_targets_markdown import (  # noqa: E402
    render_mvp_historical_review_targets_markdown,
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


def write_review_queue(root: Path) -> Path:
    queue = {
        "@type": "HistorianReviewQueue",
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "items": [
            {
                "item_id": "mvp-review-item:0001",
                "item_type": "mvp_warning_review",
                "subject_kind": "workflow",
                "decision_type": "workflow_triage",
                "question": "Warning tecnico da non presentare come target storico.",
                "allowed_decisions": ["uncertain"],
                "priority": "medium",
                "profile_id": "",
                "source_document_id": "",
                "source_item_id": "warning:1",
                "review_status": "unreviewed",
            },
            {
                "item_id": "mvp-review-item:0002",
                "item_type": "person_document_link_review",
                "subject_kind": "person",
                "decision_type": "candidate_link",
                "question": "Questo documento riguarda davvero Andreoli Dino?",
                "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                "priority": "high",
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "source_document_id": "doc-andreoli-1",
                "source_item_id": "candidate-document-person-link:andreoli",
                "context": "Il testo cita Andreoli Dino.",
                "review_status": "unreviewed",
            },
            {
                "item_id": "mvp-review-item:0003",
                "item_type": "candidate_claim_review",
                "subject_kind": "claim",
                "decision_type": "candidate_claim",
                "question": "Un secondo claim Andreoli non deve saturare la lista corta.",
                "allowed_decisions": ["confirm", "uncertain"],
                "priority": "high",
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "source_document_id": "doc-andreoli-2",
                "source_item_id": "candidate-evidence-claim:andreoli-second",
                "context": "Secondo item Andreoli.",
                "review_status": "unreviewed",
            },
            {
                "item_id": "mvp-review-item:0004",
                "item_type": "candidate_claim_review",
                "subject_kind": "claim",
                "decision_type": "candidate_claim",
                "question": "Il claim candidato e' supportato dal documento?",
                "allowed_decisions": ["confirm", "reject_false_positive", "request_more_sources"],
                "priority": "high",
                "profile_id": "person:purocielo:balboni-william",
                "canonical_name": "Balboni William",
                "source_document_id": "doc-balboni-1",
                "source_item_id": "candidate-evidence-claim:balboni",
                "context": "Scheda con campo candidato.",
                "review_status": "unreviewed",
            },
            {
                "item_id": "mvp-review-item:0005",
                "item_type": "document_signal_review",
                "subject_kind": "document_signal",
                "decision_type": "document_signal",
                "question": "Questa pista documentale aiuta a produrre un futuro claim?",
                "allowed_decisions": ["confirm", "uncertain", "needs_human_transcription"],
                "priority": "medium",
                "profile_id": "person:purocielo:bendini-ateo",
                "canonical_name": "Bendini Ateo",
                "source_document_id": "doc-bendini-1",
                "source_item_id": "document-signal:bendini",
                "context": "Pista claim-zero da controllare.",
                "review_status": "unreviewed",
            },
        ],
    }
    path = root / "review_queue.json"
    path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_review_session(root: Path) -> Path:
    session = {
        "@type": "MvpReviewSessionPack",
        "profiles": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "model_card_review_status": "in_historical_review",
            }
        ],
    }
    path = root / "review_session.json"
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class MvpHistoricalReviewTargetsTests(unittest.TestCase):
    def test_markdown_renderer_keeps_front_matter_empty_state_and_provenance(self) -> None:
        markdown = render_mvp_historical_review_targets_markdown(
            {
                "review_status": 'needs "historian"',
                "publication_status": "not_publishable_without_human_review",
                "source_mode": "review_queue",
                "source_run_ids": ["run-a"],
                "targets": [
                    {
                        "target_id": "historical-review-target:0001",
                        "profile_id": "person:test",
                        "canonical_name": "Persona Test",
                        "source_document_id": "doc:test",
                        "item_type": "candidate_claim_review",
                        "subject_kind": "claim",
                        "review_status": "pending",
                        "current_selected_action": "",
                        "current_decision_status": "",
                        "allowed_decisions": ["confirm", "uncertain"],
                        "historian_question": "Verificare il claim?",
                        "context": "Contesto sintetico.",
                        "provenance": ["review_queue_item=item-1"],
                        "safety_note": "Non modifica profili JSON-LD.",
                    }
                ],
            }
        )
        empty_markdown = render_mvp_historical_review_targets_markdown({"targets": []})

        self.assertIn('review_status: "needs \\"historian\\""', markdown)
        self.assertIn("- Run store: `run-a`", markdown)
        self.assertIn("- Azioni ammesse: confirm, uncertain", markdown)
        self.assertIn("> Contesto sintetico.", markdown)
        self.assertIn("- review_queue_item=item-1", markdown)
        self.assertIn("_Nessun target storico revisionabile generato._", empty_markdown)

    def test_builds_short_historical_targets_without_workflow_warnings(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            queue_json = write_review_queue(tmp_dir)
            session_json = write_review_session(tmp_dir)
            output_json = tmp_dir / "historian_review" / "historical_review_targets.json"
            output_md = tmp_dir / "historian_review" / "historical_review_targets.md"

            payload = build_mvp_historical_review_targets(
                review_queue_json=queue_json,
                review_session_json=session_json,
                output_json=output_json,
                output_md=output_md,
                limit=3,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False)

        self.assertEqual(payload["@type"], "MvpHistoricalReviewTargets")
        self.assertEqual(persisted["target_count"], 3)
        self.assertEqual(persisted["review_status"], "pending_historian_review")
        self.assertTrue(persisted["preview_only"])
        self.assertNotIn("mvp_warning_review", serialized)
        self.assertNotIn("workflow_triage", serialized)
        self.assertNotIn('"verified_facts":', serialized)
        self.assertNotIn('"ProfilePatch":', serialized)
        self.assertTrue(all(target["review_status"] == "pending" for target in persisted["targets"]))
        self.assertEqual(
            [target["profile_id"] for target in persisted["targets"]],
            [
                "person:purocielo:andreoli-dino",
                "person:purocielo:balboni-william",
                "person:purocielo:bendini-ateo",
            ],
        )
        self.assertIn("Target storici revisionabili MVP", markdown)
        self.assertIn("Questo documento riguarda davvero Andreoli Dino?", markdown)
        self.assertIn("source_document_id=doc-andreoli-1", markdown)
        self.assertIn("model_card_review_status=in_historical_review", markdown)
        self.assertIn("non modifica profili JSON-LD", markdown)

    def test_builds_historical_targets_from_evidence_store_records(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            store.insert_evidence_import_batch(
                {
                    "import_batch_id": "evidence-import:store-targets",
                    "source_run_id": "store-targets-run",
                    "imported_at": "2026-06-21T10:00:00+00:00",
                    "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/store-targets-run",
                    "record_count": 3,
                    "payload_hash": "batch-hash",
                }
            )
            for record in [
                {
                    "record_id": "evidence-record:target-item-1",
                    "record_kind": "review_queue_item",
                    "subject_id": "person:purocielo:andreoli-dino",
                    "source_document_id": "doc-andreoli-1",
                    "review_status": "pending",
                    "payload_hash": "hash-target-1",
                    "payload": {
                        "@type": "MvpReviewQueueItem",
                        "item_id": "mvp-review-item:0001",
                        "item_type": "person_document_link_review",
                        "subject_kind": "person",
                        "decision_type": "candidate_link",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "canonical_name": "Andreoli Dino",
                        "source_item_id": "candidate-document-person-link:andreoli",
                        "question": "Questo documento riguarda davvero Andreoli Dino?",
                        "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                        "priority": "high",
                    },
                },
                {
                    "record_id": "evidence-record:workflow",
                    "record_kind": "review_queue_item",
                    "subject_id": "",
                    "source_document_id": "",
                    "review_status": "pending",
                    "payload_hash": "hash-workflow",
                    "payload": {
                        "@type": "MvpReviewQueueItem",
                        "item_id": "mvp-review-item:workflow",
                        "item_type": "mvp_warning_review",
                        "subject_kind": "workflow",
                        "question": "Warning da escludere.",
                        "allowed_decisions": ["uncertain"],
                    },
                },
                {
                    "record_id": "evidence-record:historical-decision-1",
                    "record_kind": "historical_review_decision",
                    "subject_id": "person:purocielo:andreoli-dino",
                    "source_document_id": "doc-andreoli-1",
                    "review_status": "pending",
                    "payload_hash": "hash-decision",
                    "payload": {
                        "@type": "HistoricalReviewDecision",
                        "decision_id": "historical-review-decision:1",
                        "item_id": "mvp-review-item:0001",
                        "source_item_id": "candidate-document-person-link:andreoli",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "source_document_id": "doc-andreoli-1",
                        "selected_action": "confirm",
                        "decision_status": "accepted",
                        "reviewer": "storico-test",
                        "reviewed_at": "2026-06-21",
                    },
                },
            ]:
                record["import_batch_id"] = "evidence-import:store-targets"
                record["source_run_id"] = "store-targets-run"
                store.insert_evidence_record(record)
            before_records = store.count("evidence_records")
            output_json = tmp_dir / "historian_review" / "historical_review_targets.store.json"
            output_md = tmp_dir / "historian_review" / "historical_review_targets.store.md"

            payload = build_mvp_historical_review_targets(
                evidence_db=db_path,
                evidence_source_run_id=["store-targets-run"],
                output_json=output_json,
                output_md=output_md,
            )
            after_records = store.count("evidence_records")
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False)

        self.assertEqual(before_records, after_records)
        self.assertEqual(payload["source_mode"], "evidence_store")
        self.assertEqual(persisted["target_count"], 1)
        target = persisted["targets"][0]
        self.assertEqual(target["source_record_id"], "evidence-record:target-item-1")
        self.assertEqual(target["source_run_id"], "store-targets-run")
        self.assertEqual(target["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(target["source_document_id"], "doc-andreoli-1")
        self.assertEqual(target["historian_question"], "Questo documento riguarda davvero Andreoli Dino?")
        self.assertEqual(target["allowed_decisions"], ["confirm", "reject_false_positive", "uncertain"])
        self.assertEqual(target["current_selected_action"], "confirm")
        self.assertEqual(target["current_decision_status"], "accepted")
        self.assertEqual(target["current_decision_record_id"], "evidence-record:historical-decision-1")
        self.assertIn("record_id=evidence-record:target-item-1", target["provenance"])
        self.assertIn("historical_review_decision_record_id=evidence-record:historical-decision-1", target["provenance"])
        self.assertNotIn("mvp-review-item:workflow", serialized)
        self.assertNotIn("Warning da escludere", serialized)
        self.assertNotIn('"verified_facts":', serialized)
        self.assertIn("Modalita' sorgente: `evidence_store`", markdown)
        self.assertIn("Decisione corrente: `confirm` / `accepted`", markdown)

    def test_store_targets_match_decision_by_source_item_id_fallback(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            db_path = tmp_dir / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            store.init_schema()
            store.insert_evidence_import_batch(
                {
                    "import_batch_id": "evidence-import:store-targets-source-item",
                    "source_run_id": "store-targets-source-item-run",
                    "imported_at": "2026-06-28T10:00:00+00:00",
                    "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/store-targets-source-item-run",
                    "record_count": 2,
                    "payload_hash": "batch-hash",
                }
            )
            for record in [
                {
                    "record_id": "evidence-record:target-item-source-fallback",
                    "record_kind": "review_queue_item",
                    "subject_id": "person:purocielo:balboni-william",
                    "source_document_id": "doc-balboni-1",
                    "review_status": "pending",
                    "payload_hash": "hash-target-source-fallback",
                    "payload": {
                        "@type": "MvpReviewQueueItem",
                        "item_id": "mvp-review-item:source-fallback",
                        "item_type": "candidate_claim_review",
                        "subject_kind": "claim",
                        "decision_type": "candidate_claim",
                        "profile_id": "person:purocielo:balboni-william",
                        "canonical_name": "Balboni William",
                        "source_document_id": "doc-balboni-1",
                        "source_item_id": "candidate-evidence-claim:balboni-source",
                        "question": "Il claim candidato e' supportato dal documento?",
                        "allowed_decisions": ["confirm", "uncertain"],
                        "priority": "high",
                    },
                },
                {
                    "record_id": "evidence-record:historical-decision-source-fallback",
                    "record_kind": "historical_review_decision",
                    "subject_id": "person:purocielo:balboni-william",
                    "source_document_id": "doc-balboni-1",
                    "review_status": "pending",
                    "payload_hash": "hash-decision-source-fallback",
                    "payload": {
                        "@type": "HistoricalReviewDecision",
                        "decision_id": "historical-review-decision:source-fallback",
                        "source_item_id": "candidate-evidence-claim:balboni-source",
                        "profile_id": "person:purocielo:balboni-william",
                        "source_document_id": "doc-balboni-1",
                        "selected_action": "confirm",
                        "decision_status": "accepted",
                        "reviewer": "storico-test",
                        "reviewed_at": "2026-06-28",
                    },
                },
            ]:
                record["import_batch_id"] = "evidence-import:store-targets-source-item"
                record["source_run_id"] = "store-targets-source-item-run"
                store.insert_evidence_record(record)
            before_records = store.count("evidence_records")

            payload = build_mvp_historical_review_targets(
                evidence_db=db_path,
                evidence_source_run_id=["store-targets-source-item-run"],
            )

            after_records = store.count("evidence_records")
            serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(before_records, after_records)
        self.assertEqual(payload["target_count"], 1)
        target = payload["targets"][0]
        self.assertEqual(target["profile_id"], "person:purocielo:balboni-william")
        self.assertEqual(target["current_selected_action"], "confirm")
        self.assertEqual(target["current_decision_status"], "accepted")
        self.assertEqual(target["current_decision_record_id"], "evidence-record:historical-decision-source-fallback")
        self.assertEqual(target["current_reviewer"], "storico-test")
        self.assertEqual(target["review_status"], "decided")
        self.assertIn("historical_review_decision_record_id=evidence-record:historical-decision-source-fallback", target["provenance"])
        self.assertNotIn('"verified_facts":', serialized)
        self.assertNotIn('"ProfilePatch":', serialized)

    def test_missing_review_queue_fails_without_outputs(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            with self.assertRaises(FileNotFoundError):
                build_mvp_historical_review_targets(
                    review_queue_json=tmp_dir / "missing.json",
                    output_json=tmp_dir / "out.json",
                    output_md=tmp_dir / "out.md",
                )

        self.assertFalse((tmp_dir / "out.json").exists())
        self.assertFalse((tmp_dir / "out.md").exists())


if __name__ == "__main__":
    unittest.main()
