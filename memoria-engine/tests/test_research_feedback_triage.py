from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.research_feedback_triage import (  # noqa: E402
    build_research_feedback_actions_review_table,
    summarize_research_feedback_actions_review_table,
)


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


def write_actions_json(path: Path) -> None:
    payload = {
        "@type": "ResearchFeedbackActionSet",
        "documents": [
            {
                "@type": "ResearchFeedbackActionDocument",
                "source_id": "manual_uploads",
                "source_document_id": "doc:signals",
                "review_status": "unreviewed",
                "action_count": 2,
                "actions": [
                    {
                        "@type": "ResearchFeedbackAction",
                        "action_id": "research-feedback-action:buona",
                        "value": "Andreoli Dino",
                        "source_document_id": "doc:signals",
                        "person_id": "person:purocielo:andreoli-dino",
                        "chunk_id": "physical-document-chunk:1",
                        "weak_segment_id": "weak-document-segment:1",
                        "context": {"quote": "Contesto con Andreoli Dino e formazione."},
                        "suggested_search_hints": [
                            {"field": "person_name", "value": "Andreoli Dino"},
                            {"field": "formation", "value": "36a Brigata Garibaldi"},
                        ],
                        "suggested_sources": ["storia_memoria_bo", "partigiani_italia"],
                        "priority": "medium",
                        "risk": "medium",
                        "review_status": "unreviewed",
                    },
                    {
                        "@type": "ResearchFeedbackAction",
                        "action_id": "research-feedback-action:dubbia",
                        "value": "Laura Guazzaloca",
                        "source_document_id": "doc:signals",
                        "person_id": "person:purocielo:guazzaloca-laura",
                        "chunk_id": "physical-document-chunk:2",
                        "weak_segment_id": "weak-document-segment:2",
                        "context": {"quote": "Contesto con Laura Guazzaloca e Purocielo."},
                        "suggested_search_hints": [
                            {"field": "person_name", "value": "Laura Guazzaloca"},
                            {"field": "place", "value": "Purocielo"},
                        ],
                        "suggested_sources": ["storia_memoria_bo"],
                        "priority": "medium",
                        "risk": "low",
                        "review_status": "unreviewed",
                    },
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ResearchFeedbackTriageTests(unittest.TestCase):
    def test_builds_markdown_review_table_from_actions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json = tmp_dir / "research_feedback_actions.json"
            output_md = tmp_dir / "research_feedback_actions_review_table.md"
            write_actions_json(actions_json)

            table = build_research_feedback_actions_review_table(actions_json=actions_json, output_md=output_md)
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(table["@type"], "ResearchFeedbackActionReviewTable")
        self.assertEqual(table["action_count"], 2)
        self.assertIn("decisione | valore | action_id | documento", markdown)
        self.assertIn("research-feedback-action:buona", markdown)
        self.assertIn("Andreoli Dino", markdown)
        self.assertIn("note_storico", markdown)
        self.assertIn("decisions_do_not_create_verified_facts", json.dumps(table))

    def test_summarizes_compiled_table_as_audit_only_decisions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json = tmp_dir / "research_feedback_actions.json"
            table_md = tmp_dir / "research_feedback_actions_review_table.md"
            output_json = tmp_dir / "research_feedback_actions_review_summary.json"
            output_md = tmp_dir / "research_feedback_actions_review_summary.md"
            write_actions_json(actions_json)
            build_research_feedback_actions_review_table(actions_json=actions_json, output_md=table_md)
            text = table_md.read_text(encoding="utf-8")
            text = text.replace("|  | Andreoli Dino |", "| BUONA | Andreoli Dino |")
            text = text.replace("|  | Laura Guazzaloca |", "| DUBBIA | Laura Guazzaloca |")
            text = text.replace("|  |", "| Nota dello storico |", 1)
            table_md.write_text(text, encoding="utf-8")

            summary = summarize_research_feedback_actions_review_table(
                actions_json=actions_json,
                review_table_md=table_md,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False)

        self.assertEqual(summary["@type"], "ResearchFeedbackActionReviewSummary")
        self.assertEqual(summary["review_status"], "reviewed")
        self.assertEqual(summary["accepted_count"], 2)
        self.assertEqual(summary["pending_count"], 0)
        self.assertEqual(summary["invalid_count"], 0)
        self.assertEqual(summary["counts_by_decision"], {"BUONA": 1, "DUBBIA": 1})
        self.assertIn("person:purocielo:andreoli-dino", serialized)
        self.assertIn("ResearchFeedbackAction triage summary", markdown)
        self.assertNotIn("ProfilePatch", serialized)
        self.assertNotIn("EvidenceClaim", serialized)

    def test_reports_invalid_decision_and_unknown_action_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json = tmp_dir / "research_feedback_actions.json"
            table_md = tmp_dir / "research_feedback_actions_review_table.md"
            write_actions_json(actions_json)
            build_research_feedback_actions_review_table(actions_json=actions_json, output_md=table_md)
            lines = table_md.read_text(encoding="utf-8").splitlines()
            rows = [line for line in lines if line.startswith("| ") and "research-feedback-action:" in line]
            rows[0] = rows[0].replace("|  | Andreoli Dino |", "| FORSE | Andreoli Dino |")
            rows[1] = rows[1].replace("research-feedback-action:dubbia", "research-feedback-action:missing")
            rebuilt: list[str] = []
            row_index = 0
            for line in lines:
                if line.startswith("| ") and "research-feedback-action:" in line:
                    rebuilt.append(rows[row_index])
                    row_index += 1
                else:
                    rebuilt.append(line)
            table_md.write_text("\n".join(rebuilt) + "\n", encoding="utf-8")

            summary = summarize_research_feedback_actions_review_table(
                actions_json=actions_json,
                review_table_md=table_md,
            )

        self.assertEqual(summary["review_status"], "invalid")
        self.assertEqual(summary["accepted_count"], 0)
        self.assertEqual(summary["invalid_count"], 2)
        self.assertEqual(summary["validation_error_count"], 2)
        error_types = {error["error_type"] for error in summary["validation_errors"]}
        self.assertEqual(error_types, {"decision_not_allowed", "unknown_action_id"})


if __name__ == "__main__":
    unittest.main()
