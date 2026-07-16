from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_review_decisions import (  # noqa: E402
    build_mvp_review_decisions_summary,
)
from caduti_fonti_report.document_analysis.mvp_review_decisions_markdown import (  # noqa: E402
    render_mvp_review_decisions_markdown,
)
from caduti_fonti_report.document_analysis.mvp_review_queue import build_mvp_review_queue  # noqa: E402
from tests.test_mvp_review_queue import write_mvp_summary  # noqa: E402


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


def build_queue_fixture(root: Path) -> tuple[Path, Path]:
    summary_path = write_mvp_summary(root)
    output_json = root / "historian_review" / "review_queue.json"
    template_json = root / "historian_review" / "review_decisions.template.json"
    build_mvp_review_queue(
        summary_json=summary_path,
        output_json=output_json,
        output_md=root / "historian_review" / "review_queue.md",
        decisions_template_json=template_json,
    )
    return output_json, template_json


class MvpReviewDecisionsTests(unittest.TestCase):
    def test_markdown_renderer_keeps_coverage_candidate_and_empty_states(self) -> None:
        markdown = render_mvp_review_decisions_markdown(
            {
                "source_review_queue_json": "review_queue.json",
                "source_decisions_json": "decisions.json",
                "review_status": "partial_review",
                "publication_status": "not_publishable_without_human_review",
                "decision_file_coverage": {
                    "queue_item_count": 2,
                    "provided_decision_count": 1,
                    "provided_known_item_count": 1,
                    "selected_action_count": 1,
                },
                "review_session": {"profiles": []},
                "counts_by_action": {"request_more_sources": 1},
                "counts_by_subject_kind": {"claim": 1},
                "validation_errors": [],
                "decisions": [
                    {
                        "item_id": "mvp-review-item:0001",
                        "item_type": "candidate_claim_review",
                        "subject_kind": "claim",
                        "profile_id": "person:test",
                        "source_document_id": "doc:test",
                        "source_item_id": "candidate-evidence-claim:test",
                        "question": "Verificare il claim?",
                        "selected_action": "request_more_sources",
                        "allowed_decisions": ["confirm", "request_more_sources"],
                        "decision_status": "accepted",
                        "candidate": {"field": "birth.date", "value": "17 maggio 1920"},
                        "context": "La data candidata compare nel documento.",
                    }
                ],
            }
        )
        empty_markdown = render_mvp_review_decisions_markdown({})

        self.assertIn("Decisioni review queue MVP", markdown)
        self.assertIn("Azioni selezionate: `1`", markdown)
        self.assertIn("Campo candidato", markdown)
        self.assertIn("birth.date", markdown)
        self.assertIn("> La data candidata compare nel documento.", markdown)
        self.assertIn("Questo report non crea fatti verificati.", markdown)
        self.assertIn("_Copertura non disponibile._", empty_markdown)
        self.assertIn("_Nessuna decisione riepilogata._", empty_markdown)

    def test_summarizes_valid_and_pending_decisions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            queue_json, decisions_json = build_queue_fixture(tmp_dir)
            queue = json.loads(queue_json.read_text(encoding="utf-8"))
            decisions = json.loads(decisions_json.read_text(encoding="utf-8"))
            andreoli_item = next(
                item
                for item in queue["items"]
                if item.get("source_item_id") == "candidate-evidence-claim:andreoli-birth"
            )
            andreoli_decision = next(
                item for item in decisions["decisions"] if item.get("item_id") == andreoli_item["item_id"]
            )
            andreoli_decision["selected_action"] = "request_more_sources"
            andreoli_decision["reviewer"] = "storico"
            andreoli_decision["notes"] = "Serve una seconda fonte."
            decisions_json.write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")
            output_json = tmp_dir / "historian_review" / "review_decisions_summary.json"
            output_md = tmp_dir / "historian_review" / "review_decisions_summary.md"

            summary = build_mvp_review_decisions_summary(
                review_queue_json=queue_json,
                decisions_json=decisions_json,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False)

        self.assertEqual(summary["@type"], "MvpReviewDecisionsSummary")
        self.assertEqual(persisted["review_status"], "partial_review")
        self.assertEqual(persisted["accepted_count"], 1)
        self.assertGreaterEqual(persisted["pending_count"], 1)
        self.assertEqual(persisted["validation_error_count"], 0)
        self.assertEqual(persisted["decision_file_coverage"]["coverage_status"], "partial")
        self.assertEqual(persisted["decision_file_coverage"]["provided_decision_count"], len(decisions["decisions"]))
        self.assertEqual(persisted["decision_file_coverage"]["selected_action_count"], 1)
        self.assertEqual(persisted["decision_file_coverage"]["blank_action_count"], len(decisions["decisions"]) - 1)
        self.assertEqual(persisted["decision_file_coverage"]["queue_items_without_provided_decision_count"], 0)
        self.assertIn("request_more_sources", persisted["counts_by_action"])
        self.assertEqual(persisted["review_session"]["profile_count"], 2)
        self.assertEqual(persisted["review_session"]["session_status"], "in_review")
        self.assertIn("date", persisted["counts_by_subject_kind"])
        self.assertIn("place", persisted["counts_by_subject_kind"])
        self.assertIn("event_context", persisted["counts_by_subject_kind"])
        self.assertTrue(all("subject_kind" in item for item in persisted["decisions"]))
        reviewed_item = next(item for item in persisted["decisions"] if item["item_id"] == andreoli_item["item_id"])
        self.assertEqual(reviewed_item["source_item_id"], "candidate-evidence-claim:andreoli-birth")
        self.assertEqual(reviewed_item["candidate"], {"field": "birth.date", "value": "17 maggio 1920"})
        self.assertEqual(reviewed_item["question"], andreoli_item["question"])
        self.assertEqual(reviewed_item["allowed_decisions"], andreoli_item["allowed_decisions"])
        self.assertEqual(reviewed_item["context"], "Nato il 17 maggio 1920.")
        profiles_by_id = {item["profile_id"]: item for item in persisted["review_session"]["profiles"]}
        self.assertEqual(profiles_by_id["person:purocielo:andreoli-dino"]["session_status"], "in_review")
        self.assertIn("date", profiles_by_id["person:purocielo:andreoli-dino"]["counts_by_subject_kind"])
        self.assertEqual(profiles_by_id["person:purocielo:guazzaloca-laura"]["session_status"], "not_started")
        self.assertIn("Decisioni review queue MVP", markdown)
        self.assertIn("Copertura file decisioni", markdown)
        self.assertIn("Azioni selezionate", markdown)
        self.assertIn("Sessione storici", markdown)
        self.assertIn("Conteggi per oggetto", markdown)
        self.assertIn("Campo candidato", markdown)
        self.assertIn("birth.date", markdown)
        self.assertIn("17 maggio 1920", markdown)
        self.assertIn("La data candidata", markdown)
        self.assertIn("candidate-evidence-claim:andreoli-birth", markdown)
        self.assertIn("person:purocielo:andreoli-dino", markdown)
        self.assertIn("Serve una seconda fonte.", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_reports_partial_review_when_compiled_file_omits_queue_items(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            queue_json, decisions_json = build_queue_fixture(tmp_dir)
            queue = json.loads(queue_json.read_text(encoding="utf-8"))
            decisions = json.loads(decisions_json.read_text(encoding="utf-8"))
            selected_item = queue["items"][0]
            decisions["decisions"] = [
                {
                    "@type": "ReviewDecision",
                    "item_id": selected_item["item_id"],
                    "selected_action": selected_item["allowed_decisions"][0],
                    "reviewer": "storico",
                    "notes": "Prima decisione compilata.",
                }
            ]
            decisions_json.write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")

            summary = build_mvp_review_decisions_summary(
                review_queue_json=queue_json,
                decisions_json=decisions_json,
            )

        coverage = summary["decision_file_coverage"]
        self.assertEqual(summary["review_status"], "partial_review")
        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["pending_count"], len(queue["items"]) - 1)
        self.assertEqual(coverage["coverage_status"], "partial")
        self.assertEqual(coverage["provided_decision_count"], 1)
        self.assertEqual(coverage["provided_known_item_count"], 1)
        self.assertEqual(coverage["provided_unknown_item_count"], 0)
        self.assertEqual(coverage["selected_action_count"], 1)
        self.assertEqual(coverage["blank_action_count"], 0)
        self.assertEqual(coverage["queue_items_without_provided_decision_count"], len(queue["items"]) - 1)
        self.assertFalse(any("verified_facts" in item for item in summary["decisions"]))

    def test_reports_invalid_action_without_dropping_other_decisions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            queue_json, decisions_json = build_queue_fixture(tmp_dir)
            queue = json.loads(queue_json.read_text(encoding="utf-8"))
            decisions = json.loads(decisions_json.read_text(encoding="utf-8"))
            decisions["decisions"][0]["selected_action"] = queue["items"][0]["allowed_decisions"][0]
            decisions["decisions"][1]["selected_action"] = "publish_now"
            decisions_json.write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")

            summary = build_mvp_review_decisions_summary(
                review_queue_json=queue_json,
                decisions_json=decisions_json,
            )

        self.assertEqual(summary["review_status"], "invalid")
        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["invalid_count"], 1)
        self.assertEqual(summary["validation_error_count"], 1)
        self.assertEqual(summary["validation_errors"][0]["error_type"], "action_not_allowed")
        invalid_item = summary["decisions"][1]
        self.assertIn("question", invalid_item)
        self.assertIn("allowed_decisions", invalid_item)
        self.assertIn("source_item_id", invalid_item)

    def test_reports_unknown_item_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            queue_json, decisions_json = build_queue_fixture(tmp_dir)
            decisions = json.loads(decisions_json.read_text(encoding="utf-8"))
            decisions["decisions"].append(
                {
                    "@type": "ReviewDecision",
                    "item_id": "mvp-review-item:9999",
                    "selected_action": "confirm",
                    "reviewer": "storico",
                    "notes": "Item non presente.",
                }
            )
            decisions_json.write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding="utf-8")

            summary = build_mvp_review_decisions_summary(
                review_queue_json=queue_json,
                decisions_json=decisions_json,
            )

        self.assertEqual(summary["review_status"], "invalid")
        self.assertEqual(summary["validation_error_count"], 1)
        self.assertEqual(summary["validation_errors"][0]["error_type"], "unknown_item_id")
        self.assertEqual(summary["decision_file_coverage"]["provided_unknown_item_count"], 1)
        self.assertEqual(summary["decision_file_coverage"]["provided_decision_count"], len(decisions["decisions"]))

    def test_missing_inputs_fail_without_writing_outputs(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            output_json = tmp_dir / "historian_review" / "review_decisions_summary.json"

            with self.assertRaises(FileNotFoundError):
                build_mvp_review_decisions_summary(
                    review_queue_json=tmp_dir / "missing-review-queue.json",
                    decisions_json=tmp_dir / "missing-decisions.json",
                    output_json=output_json,
                    output_md=tmp_dir / "historian_review" / "review_decisions_summary.md",
                )

            self.assertFalse(output_json.exists())


if __name__ == "__main__":
    unittest.main()
