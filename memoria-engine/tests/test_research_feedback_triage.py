from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.research_feedback_triage import (  # noqa: E402
    build_research_feedback_actions_review_table,
    render_research_feedback_actions_review_table,
    run_research_feedback_triage_wizard,
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
    def test_review_wizard_records_explicit_decisions_and_per_action_timing(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json = tmp_dir / "actions.json"
            table_md, summary_json, summary_md = (tmp_dir / name for name in ("decisions.md", "summary.json", "summary.md"))
            write_actions_json(actions_json)
            answers = iter(["reviewer:test", "b", "nota 1", "i", "nota 2", "s"])
            timestamps = iter([
                "2026-11-08T10:00:00+00:00", "2026-11-08T10:02:00+00:00",
                "2026-11-08T10:03:00+00:00", "2026-11-08T10:04:00+00:00",
            ])
            summary = run_research_feedback_triage_wizard(
                actions_json=actions_json, output_review_table_md=table_md,
                output_json=summary_json, output_md=summary_md,
                input_fn=lambda _: next(answers), output_fn=lambda _: None, now_fn=lambda: next(timestamps),
            )
            self.assertIsNotNone(summary)
            assert summary is not None
            first, second = summary["decisions"]
            self.assertEqual((first["decision"], first["reviewer"], first["review_timing_status"],
                              first["review_duration_seconds"]), ("BUONA", "reviewer:test", "measured", 120.0))
            self.assertEqual((second["decision"], second["review_timing_status"],
                              second["review_duration_seconds"]), ("INUTILE", "measured", 60.0))
            self.assertTrue(table_md.is_file())
            self.assertEqual(json.loads(summary_json.read_text(encoding="utf-8"))["accepted_count"], 2)

    def test_review_wizard_cancel_writes_no_artifacts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json = tmp_dir / "actions.json"
            table_md, summary_json, summary_md = (tmp_dir / name for name in ("decisions.md", "summary.json", "summary.md"))
            write_actions_json(actions_json)
            answers = iter(["reviewer:test", "q"])
            summary = run_research_feedback_triage_wizard(
                actions_json=actions_json, output_review_table_md=table_md,
                output_json=summary_json, output_md=summary_md,
                input_fn=lambda _: next(answers), output_fn=lambda _: None,
                now_fn=lambda: "2026-11-08T10:00:00+00:00",
            )
            self.assertIsNone(summary)
            self.assertFalse(table_md.exists())
            self.assertFalse(summary_json.exists())
            self.assertFalse(summary_md.exists())

    def test_installed_launcher_builds_and_summarizes_timed_triage(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json = tmp_dir / "actions.json"
            table_md = tmp_dir / "review-table.md"
            summary_json, summary_md = tmp_dir / "summary.json", tmp_dir / "summary.md"
            write_actions_json(actions_json)
            launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
            if not launcher.is_file():
                self.skipTest("Installed memoria launcher is not available in this environment.")
            before = actions_json.read_bytes()
            built = subprocess.run(
                [str(launcher), "feedback", "triage", "build-table", "--actions-json", str(actions_json),
                 "--output-md", str(table_md)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            rows = table_md.read_text(encoding="utf-8").splitlines()
            updated = []
            for line in rows:
                if line.startswith("|") and "research-feedback-action:buona" in line:
                    cells = line.strip("|").split("|")
                    cells[0] = " BUONA "
                    cells[8] = " reviewer:test "
                    cells[9] = " 2026-11-08T10:00:00+00:00 "
                    cells[10] = " 2026-11-08T10:02:00+00:00 "
                    line = "|" + "|".join(cells) + "|"
                updated.append(line)
            table_md.write_text("\n".join(updated) + "\n", encoding="utf-8")
            summarized = subprocess.run(
                [str(launcher), "feedback", "triage", "summarize-table", "--actions-json", str(actions_json),
                 "--review-table-md", str(table_md), "--output-json", str(summary_json),
                 "--output-md", str(summary_md)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(summarized.returncode, 0, summarized.stderr)
            summary = json.loads(summary_json.read_text(encoding="utf-8"))
            self.assertEqual(summary["@type"], "ResearchFeedbackActionReviewSummary")
            self.assertEqual(summary["review_status"], "partial_review")
            self.assertEqual(summary["accepted_count"], 1)
            self.assertEqual(summary["review_timing_counts"], {"measured": 1, "unavailable": 1})
            self.assertEqual(actions_json.read_bytes(), before)

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
        self.assertIn("reviewer | review_started_at | reviewed_at", markdown)
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
            expected_actions_sha256 = hashlib.sha256(actions_json.read_bytes()).hexdigest()

        self.assertEqual(summary["@type"], "ResearchFeedbackActionReviewSummary")
        self.assertEqual(summary["review_status"], "reviewed")
        self.assertEqual(summary["accepted_count"], 2)
        self.assertEqual(summary["pending_count"], 0)
        self.assertEqual(summary["invalid_count"], 0)
        self.assertEqual(summary["counts_by_decision"], {"BUONA": 1, "DUBBIA": 1})
        self.assertEqual(summary["actions_sha256"], expected_actions_sha256)
        self.assertIn("person:purocielo:andreoli-dino", serialized)
        self.assertIn("ResearchFeedbackAction triage summary", markdown)
        self.assertNotIn("ProfilePatch", serialized)
        self.assertNotIn("EvidenceClaim", serialized)

    def test_summary_rejects_review_table_if_action_set_changed(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json = tmp_dir / "actions.json"
            table_md = tmp_dir / "review.md"
            write_actions_json(actions_json)
            build_research_feedback_actions_review_table(actions_json=actions_json, output_md=table_md)
            table = table_md.read_text(encoding="utf-8")
            table = table.replace("|  | Andreoli Dino |", "| BUONA | Andreoli Dino |")
            table_md.write_text(table, encoding="utf-8")
            actions_json.write_text(actions_json.read_text(encoding="utf-8").replace("Purocielo", "Bologna"), encoding="utf-8")

            summary = summarize_research_feedback_actions_review_table(
                actions_json=actions_json, review_table_md=table_md
            )

        self.assertEqual(summary["source_actions_binding_status"], "mismatch")
        self.assertEqual(summary["review_status"], "invalid")
        self.assertEqual(summary["accepted_count"], 0)
        self.assertIn("review_table_action_set_hash_mismatch", summary["warnings"])

    def test_summary_rejects_legacy_review_table_without_action_hash(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json = tmp_dir / "actions.json"
            table_md = tmp_dir / "review.md"
            write_actions_json(actions_json)
            build_research_feedback_actions_review_table(actions_json=actions_json, output_md=table_md)
            table = table_md.read_text(encoding="utf-8")
            table = table.replace("- Action set SHA-256: `" + hashlib.sha256(actions_json.read_bytes()).hexdigest() + "`\n", "")
            table = table.replace("|  | Andreoli Dino |", "| BUONA | Andreoli Dino |")
            table_md.write_text(table, encoding="utf-8")

            summary = summarize_research_feedback_actions_review_table(
                actions_json=actions_json, review_table_md=table_md
            )

        self.assertEqual(summary["source_actions_binding_status"], "missing")
        self.assertEqual(summary["review_status"], "invalid")
        self.assertEqual(summary["accepted_count"], 0)
        self.assertIn("review_table_action_set_hash_missing", summary["warnings"])

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

    def test_explicit_review_metadata_round_trips_with_timezone_aware_duration(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json, table_md = tmp_dir / "actions.json", tmp_dir / "review.md"
            write_actions_json(actions_json)
            table = build_research_feedback_actions_review_table(actions_json=actions_json)
            table["rows"][0].update({
                "decisione": "BUONA", "reviewer": "fixture-reviewer",
                "review_started_at": "2026-11-07T10:00:00+01:00",
                "reviewed_at": "2026-11-07T09:01:30Z",
            })
            table_md.write_text(render_research_feedback_actions_review_table(table), encoding="utf-8")
            before = table_md.read_bytes()

            summary = summarize_research_feedback_actions_review_table(actions_json=actions_json, review_table_md=table_md)

            self.assertEqual(table_md.read_bytes(), before)
        decision = summary["decisions"][0]
        self.assertEqual(decision["reviewer"], "fixture-reviewer")
        self.assertEqual(decision["review_started_at"], "2026-11-07T10:00:00+01:00")
        self.assertEqual(decision["reviewed_at"], "2026-11-07T09:01:30Z")
        self.assertEqual(decision["review_duration_seconds"], 90.0)
        self.assertEqual(decision["review_timing_status"], "measured")
        self.assertEqual(decision["decision_status"], "accepted")
        self.assertEqual(decision["source_document_id"], "doc:signals")
        self.assertEqual(summary["review_timing_counts"], {"measured": 1, "unavailable": 1})
        self.assertEqual(summary["review_timing_validation_errors"], [])

    def test_legacy_eight_column_table_is_not_approved_without_hash(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json, table_md = tmp_dir / "actions.json", tmp_dir / "review.md"
            write_actions_json(actions_json)
            table_md.write_text(
                "| decisione | valore | action_id | documento | fonti_suggerite | indizi | contesto | note_storico |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| BUONA | Andreoli Dino | research-feedback-action:buona | doc:signals | storia_memoria_bo | | | Legacy review |\n",
                encoding="utf-8",
            )
            summary = summarize_research_feedback_actions_review_table(actions_json=actions_json, review_table_md=table_md)
        decision = summary["decisions"][0]
        self.assertEqual(summary["accepted_count"], 0)
        self.assertEqual(summary["review_status"], "invalid")
        self.assertEqual(summary["source_actions_binding_status"], "missing")
        self.assertEqual(decision["decision_status"], "invalid")
        self.assertEqual(decision["reviewer"], "")
        self.assertEqual(decision["review_started_at"], "")
        self.assertEqual(decision["reviewed_at"], "")
        self.assertEqual(decision["review_timing_status"], "unavailable")
        self.assertIsNone(decision["review_duration_seconds"])
        self.assertEqual(summary["review_timing_validation_error_count"], 0)

    def test_invalid_or_reversed_timestamps_are_reported_without_changing_decisions(self) -> None:
        for start, end, error in (
            ("not-a-timestamp", "2026-11-07T09:01:00Z", "invalid_review_started_at"),
            ("2026-11-07T09:00:00", "2026-11-07T09:01:00Z", "invalid_review_started_at"),
            ("2026-11-07T09:00:00Z", "2026-11-07T09:01:00", "invalid_reviewed_at"),
            ("2026-11-07T09:02:00Z", "2026-11-07T09:01:00Z", "reviewed_at_before_review_started_at"),
        ):
            with self.subTest(start=start, end=end), workspace_temp_dir() as tmp_dir:
                actions_json, table_md = tmp_dir / "actions.json", tmp_dir / "review.md"
                write_actions_json(actions_json)
                table = build_research_feedback_actions_review_table(actions_json=actions_json)
                table["rows"][0].update({"decisione": "BUONA", "review_started_at": start, "reviewed_at": end})
                table_md.write_text(render_research_feedback_actions_review_table(table), encoding="utf-8")
                summary = summarize_research_feedback_actions_review_table(actions_json=actions_json, review_table_md=table_md)
            decision = summary["decisions"][0]
            self.assertEqual(decision["decision_status"], "accepted")
            self.assertEqual(decision["review_started_at"], start)
            self.assertEqual(decision["reviewed_at"], end)
            self.assertEqual(decision["review_timing_status"], "invalid")
            self.assertIsNone(decision["review_duration_seconds"])
            self.assertEqual(summary["validation_error_count"], 0)
            self.assertEqual(summary["review_timing_validation_error_count"], 1)
            self.assertEqual(summary["review_timing_validation_errors"][0]["error_type"], error)

    def test_single_valid_timestamp_does_not_infer_missing_endpoint(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            actions_json, table_md = tmp_dir / "actions.json", tmp_dir / "review.md"
            write_actions_json(actions_json)
            table = build_research_feedback_actions_review_table(actions_json=actions_json)
            table["rows"][0].update({"decisione": "DUBBIA", "review_started_at": "2026-11-07T09:00:00Z"})
            table_md.write_text(render_research_feedback_actions_review_table(table), encoding="utf-8")
            summary = summarize_research_feedback_actions_review_table(actions_json=actions_json, review_table_md=table_md)
        decision = summary["decisions"][0]
        self.assertEqual(decision["reviewed_at"], "")
        self.assertEqual(decision["review_timing_status"], "unavailable")
        self.assertIsNone(decision["review_duration_seconds"])
        self.assertEqual(summary["review_timing_validation_errors"], [])


if __name__ == "__main__":
    unittest.main()
