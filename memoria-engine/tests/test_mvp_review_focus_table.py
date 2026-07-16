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
from caduti_fonti_report.document_analysis.mvp_review_focus_table import (  # noqa: E402
    build_mvp_review_focus_decisions_cards,
    build_mvp_review_focus_decisions_table,
    build_mvp_review_queue_decisions_cards,
    convert_mvp_review_focus_decisions_table,
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


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_review_session_fixture(root: Path) -> tuple[Path, Path]:
    processed_dir = root / "processed_documents"
    write_json(
        processed_dir / "doc-andreoli.metadata.json",
        {
            "@type": "ProcessedDocumentMetadata",
            "source_document_id": "doc-andreoli",
            "title": "Scheda Andreoli.docx",
            "source_url": "https://example.test/andreoli",
            "raw_file": "profili_pilota\\Scheda Andreoli.docx",
        },
    )
    write_json(
        processed_dir / "doc-andreoli.text.json",
        {
            "@type": "ProcessedDocumentText",
            "source_document_id": "doc-andreoli",
            "text": "Andreoli Dino testo processato.",
        },
    )
    write_json(
        processed_dir / "doc-andreoli-image-1.text.json",
        {
            "@type": "ProcessedDocumentText",
            "source_document_id": "doc-andreoli-image-1",
            "text": "Retro immagine Andreoli.",
        },
    )
    summary_json = write_json(
        root / "document_analysis" / "mvp_pilot_summary.json",
        {
            "@type": "MvpPilotSummary",
            "documents": [
                {
                    "source_document_id": "doc-andreoli",
                    "quality_path": str(root / "processed_documents" / "doc-andreoli.quality.json"),
                    "document_class": "word_document",
                }
            ],
            "candidate_document_person_links": [
                {
                    "source_document_id": "doc-andreoli",
                    "title": "Scheda Andreoli.docx",
                    "raw_file": "profili_pilota\\Scheda Andreoli.docx",
                    "metadata_file": str(root / "processed_documents" / "doc-andreoli.metadata.json"),
                }
            ],
        },
    )
    queue_json = write_json(
        root / "historian_review" / "review_queue.json",
        {
            "@type": "HistorianReviewQueue",
            "source_summary_json": str(summary_json),
            "items": [
                {
                    "item_id": "mvp-review-item:0001",
                    "item_type": "candidate_claim_review",
                    "subject_kind": "date",
                    "profile_id": "person:purocielo:andreoli-dino",
                    "canonical_name": "Andreoli Dino",
                    "source_document_id": "doc-andreoli",
                    "source_item_id": "candidate-evidence-claim:birth",
                    "question": "La data candidata e' supportata dal documento?",
                    "context": "Estratto candidato per Andreoli Dino.",
                    "allowed_decisions": ["approve_claim", "reject_claim", "mark_uncertain"],
                    "candidate": {"field": "birth.date", "value": "1920"},
                },
                {
                    "item_id": "mvp-review-item:0002",
                    "item_type": "person_document_link_review",
                    "subject_kind": "person",
                    "profile_id": "person:purocielo:andreoli-dino",
                    "canonical_name": "Andreoli Dino",
                    "source_document_id": "doc-andreoli",
                    "source_item_id": "candidate-link:andreoli",
                    "question": "Il documento riguarda Andreoli Dino?",
                    "context": "Nome presente nella scheda Andreoli.",
                    "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                },
                {
                    "item_id": "mvp-review-item:0003",
                    "item_type": "person_document_link_review",
                    "subject_kind": "person",
                    "profile_id": "person:purocielo:balboni-william",
                    "canonical_name": "Balboni William",
                    "source_document_id": "doc-andreoli",
                    "source_item_id": "candidate-link:balboni",
                    "question": "Il documento riguarda Balboni William?",
                    "context": "Nome presente nella scheda Balboni.",
                    "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                },
            ],
        },
    )
    review_session_json = write_json(
        root / "historian_review" / "review_session.json",
        {
            "@type": "MvpReviewSessionPack",
            "source_summary_json": str(summary_json),
            "source_review_queue_json": str(queue_json),
            "review_focus_decisions_template": {
                "@type": "MvpReviewFocusDecisionsTemplate",
                "template_scope": "review_focus",
                "item_count": 2,
                "decisions": [
                    {
                        "@type": "ReviewDecision",
                        "item_id": "mvp-review-item:0001",
                        "item_type": "candidate_claim_review",
                        "subject_kind": "date",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "source_document_id": "doc-andreoli",
                        "question": "La data candidata e' supportata dal documento?",
                        "allowed_decisions": ["approve_claim", "reject_claim", "mark_uncertain"],
                        "selected_action": "",
                        "reviewer": "",
                        "reviewed_at": "",
                        "notes": "",
                    },
                    {
                        "@type": "ReviewDecision",
                        "item_id": "mvp-review-item:0002",
                        "item_type": "person_document_link_review",
                        "subject_kind": "person",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "source_document_id": "doc-andreoli",
                        "question": "Il documento riguarda Andreoli Dino?",
                        "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                        "selected_action": "",
                        "reviewer": "",
                        "reviewed_at": "",
                        "notes": "",
                    },
                    {
                        "@type": "ReviewDecision",
                        "item_id": "mvp-review-item:0003",
                        "item_type": "person_document_link_review",
                        "subject_kind": "person",
                        "profile_id": "person:purocielo:balboni-william",
                        "source_document_id": "doc-andreoli",
                        "question": "Il documento riguarda Balboni William?",
                        "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                        "selected_action": "",
                        "reviewer": "",
                        "reviewed_at": "",
                        "notes": "",
                    },
                ],
            },
        },
    )
    return review_session_json, queue_json


class MvpReviewFocusTableTests(unittest.TestCase):
    def test_builds_markdown_table_from_review_focus(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, _queue_json = write_review_session_fixture(tmp_dir)
            output_md = tmp_dir / "historian_review" / "review_focus_decisions_table.md"

            table = build_mvp_review_focus_decisions_table(
                review_session_json=review_session_json,
                output_md=output_md,
            )
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(table, ensure_ascii=False) + markdown

        self.assertEqual(table["@type"], "MvpReviewFocusDecisionsTable")
        self.assertEqual(table["decision_count"], 3)
        self.assertIn("selected_action", markdown)
        self.assertIn("azioni_ammesse", markdown)
        self.assertIn("mvp-review-item:0001", markdown)
        self.assertIn("approve_claim, reject_claim, mark_uncertain", markdown)
        self.assertIn("Scheda Andreoli.docx (word_document)", markdown)
        self.assertIn("profili_pilota\\Scheda Andreoli.docx", markdown)
        self.assertIn("Estratto candidato per Andreoli Dino.", markdown)
        self.assertIn("validare sempre", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_builds_readable_cards_from_review_focus(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, _queue_json = write_review_session_fixture(tmp_dir)
            output_md = tmp_dir / "historian_review" / "review_focus_decisions_cards.md"

            cards = build_mvp_review_focus_decisions_cards(
                review_session_json=review_session_json,
                output_md=output_md,
            )
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(cards, ensure_ascii=False) + markdown

        self.assertEqual(cards["@type"], "MvpReviewFocusDecisionCards")
        self.assertEqual(cards["decision_count"], 3)
        self.assertIn("## 1. Andreoli Dino - mvp-review-item:0001", markdown)
        self.assertIn("Documento: Scheda Andreoli.docx (word_document)", markdown)
        self.assertIn("Riferimento documento: `profili_pilota\\Scheda Andreoli.docx`", markdown)
        self.assertIn("### Come aprire il documento", markdown)
        self.assertIn("URL fonte: `https://example.test/andreoli`", markdown)
        self.assertIn("Raw locale: `profili_pilota\\Scheda Andreoli.docx`", markdown)
        self.assertIn("Testo processato: `", markdown)
        self.assertIn("doc-andreoli.text.json", markdown)
        self.assertIn("Domanda: La data candidata e' supportata dal documento?", markdown)
        self.assertIn("> Estratto candidato per Andreoli Dino.", markdown)
        self.assertIn("| selected_action | reviewer | reviewed_at | note |", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_builds_readable_cards_from_review_queue_item_ids(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            _review_session_json, queue_json = write_review_session_fixture(tmp_dir)
            output_md = tmp_dir / "historian_review" / "review_claim_cards.md"

            cards = build_mvp_review_queue_decisions_cards(
                review_queue_json=queue_json,
                output_md=output_md,
                item_ids=["mvp-review-item:0001"],
            )
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(cards, ensure_ascii=False) + markdown

        self.assertEqual(cards["@type"], "MvpReviewQueueDecisionCards")
        self.assertEqual(cards["decision_count"], 1)
        self.assertEqual(cards["cards"][0]["item_id"], "mvp-review-item:0001")
        self.assertIn("mvp-review-item:0001", markdown)
        self.assertIn("### Come aprire il documento", markdown)
        self.assertIn("URL fonte: `https://example.test/andreoli`", markdown)
        self.assertIn("Metadati: `", markdown)
        self.assertIn("doc-andreoli.metadata.json", markdown)
        self.assertIn("doc-andreoli-image-1.text.json", markdown)
        self.assertIn("- field: `birth.date`", markdown)
        self.assertIn("- value: `1920`", markdown)
        self.assertIn("| selected_action | reviewer | reviewed_at | note |", markdown)
        self.assertNotIn("mvp-review-item:0002", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_converts_compiled_markdown_to_decisions_json_and_canonical_summary(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, queue_json = write_review_session_fixture(tmp_dir)
            table_md = tmp_dir / "historian_review" / "review_focus_decisions_table.md"
            decisions_json = tmp_dir / "historian_review" / "review_decisions.compilato.json"
            table_summary_json = tmp_dir / "historian_review" / "review_focus_decisions_table_summary.json"
            table_summary_md = tmp_dir / "historian_review" / "review_focus_decisions_table_summary.md"
            build_mvp_review_focus_decisions_table(review_session_json=review_session_json, output_md=table_md)
            table_text = table_md.read_text(encoding="utf-8")
            table_text = table_text.replace(
                "|  |  |  | mvp-review-item:0001 |",
                "| approve_claim | storico | 2026-06-14T12:00:00+02:00 | mvp-review-item:0001 |",
            )
            table_text = table_text.replace(
                "|  |  |  | mvp-review-item:0002 |",
                "|  |  |  | mvp-review-item:0002 |",
            )
            table_md.write_text(table_text, encoding="utf-8")

            table_summary = convert_mvp_review_focus_decisions_table(
                review_table_md=table_md,
                output_decisions_json=decisions_json,
                output_summary_json=table_summary_json,
                output_summary_md=table_summary_md,
            )
            decisions = json.loads(decisions_json.read_text(encoding="utf-8"))
            canonical_summary = build_mvp_review_decisions_summary(
                review_queue_json=queue_json,
                decisions_json=decisions_json,
            )
            serialized = json.dumps(decisions, ensure_ascii=False) + json.dumps(table_summary, ensure_ascii=False)

        self.assertEqual(table_summary["review_status"], "partial_review")
        self.assertEqual(table_summary["provided_count"], 1)
        self.assertEqual(table_summary["pending_count"], 2)
        self.assertEqual(table_summary["invalid_count"], 0)
        self.assertEqual(decisions["@type"], "MvpReviewDecisions")
        self.assertEqual(decisions["decisions"][0]["selected_action"], "approve_claim")
        self.assertEqual(decisions["decisions"][0]["reviewer"], "storico")
        self.assertEqual(canonical_summary["review_status"], "partial_review")
        self.assertEqual(canonical_summary["accepted_count"], 1)
        self.assertEqual(canonical_summary["pending_count"], 2)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_converts_compiled_cards_to_decisions_json_and_canonical_summary(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, queue_json = write_review_session_fixture(tmp_dir)
            cards_md = tmp_dir / "historian_review" / "review_focus_decisions_cards.md"
            decisions_json = tmp_dir / "historian_review" / "review_decisions.compilato.json"
            build_mvp_review_focus_decisions_cards(review_session_json=review_session_json, output_md=cards_md)
            cards_text = cards_md.read_text(encoding="utf-8")
            cards_text = cards_text.replace(
                "|  |  |  |  |",
                "| approve_claim | storico | 2026-06-14T12:00:00+02:00 | Confermato da scheda. |",
                1,
            )
            cards_text = cards_text.replace(
                "|  |  |  |  |",
                "| uncertain | storico | 2026-06-14T12:05:00+02:00 | Serve controllo omonimia. |",
                1,
            )
            cards_md.write_text(cards_text, encoding="utf-8")

            table_summary = convert_mvp_review_focus_decisions_table(
                review_table_md=cards_md,
                output_decisions_json=decisions_json,
            )
            decisions = json.loads(decisions_json.read_text(encoding="utf-8"))
            canonical_summary = build_mvp_review_decisions_summary(
                review_queue_json=queue_json,
                decisions_json=decisions_json,
            )
            serialized = json.dumps(decisions, ensure_ascii=False) + json.dumps(table_summary, ensure_ascii=False)

        self.assertEqual(table_summary["review_status"], "partial_review")
        self.assertEqual(table_summary["row_count"], 3)
        self.assertEqual(table_summary["provided_count"], 2)
        self.assertEqual(table_summary["invalid_count"], 0)
        self.assertEqual(decisions["decisions"][0]["item_id"], "mvp-review-item:0001")
        self.assertEqual(decisions["decisions"][0]["selected_action"], "approve_claim")
        self.assertEqual(decisions["decisions"][1]["item_id"], "mvp-review-item:0002")
        self.assertEqual(decisions["decisions"][1]["selected_action"], "uncertain")
        self.assertEqual(canonical_summary["accepted_count"], 2)
        self.assertEqual(canonical_summary["pending_count"], 1)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_builds_cards_filtered_by_profile_ids(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, _queue_json = write_review_session_fixture(tmp_dir)
            output_md = tmp_dir / "historian_review" / "review_focus_decisions_cards.md"

            cards = build_mvp_review_focus_decisions_cards(
                review_session_json=review_session_json,
                output_md=output_md,
                profile_ids=["person:purocielo:balboni-william"],
            )
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(cards, ensure_ascii=False) + markdown

        self.assertEqual(cards["decision_count"], 1)
        self.assertEqual(cards["cards"][0]["profile_id"], "person:purocielo:balboni-william")
        self.assertIn("Balboni William", markdown)
        self.assertNotIn("Andreoli Dino", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_card_conversion_ignores_repeated_headers_and_spaced_separators(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, _queue_json = write_review_session_fixture(tmp_dir)
            cards_md = tmp_dir / "historian_review" / "review_focus_decisions_cards.md"
            decisions_json = tmp_dir / "historian_review" / "review_decisions.compilato.json"
            build_mvp_review_focus_decisions_cards(review_session_json=review_session_json, output_md=cards_md, limit=1)
            cards_text = cards_md.read_text(encoding="utf-8")
            cards_text = cards_text.replace(
                "|  |  |  |  |",
                "| selected_action | reviewer | reviewed_at | note |\n"
                "|---|---|---|---|\n"
                "| approve_claim | storico | 2026-06-14T12:00:00+02:00 | Confermato da scheda. |",
                1,
            )
            cards_md.write_text(cards_text, encoding="utf-8")

            table_summary = convert_mvp_review_focus_decisions_table(
                review_table_md=cards_md,
                output_decisions_json=decisions_json,
            )
            decisions = json.loads(decisions_json.read_text(encoding="utf-8"))

        self.assertEqual(table_summary["review_status"], "compiled")
        self.assertEqual(table_summary["row_count"], 1)
        self.assertEqual(table_summary["invalid_count"], 0)
        self.assertEqual(decisions["decisions"][0]["item_id"], "mvp-review-item:0001")
        self.assertEqual(decisions["decisions"][0]["selected_action"], "approve_claim")

    def test_table_conversion_reports_duplicates_without_writing_duplicate_decisions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, _queue_json = write_review_session_fixture(tmp_dir)
            table_md = tmp_dir / "historian_review" / "review_focus_decisions_table.md"
            decisions_json = tmp_dir / "historian_review" / "review_decisions.compilato.json"
            build_mvp_review_focus_decisions_table(review_session_json=review_session_json, output_md=table_md)
            lines = table_md.read_text(encoding="utf-8").splitlines()
            duplicate_row = next(line for line in lines if "mvp-review-item:0001" in line)
            table_md.write_text("\n".join(lines + [duplicate_row]) + "\n", encoding="utf-8")

            summary = convert_mvp_review_focus_decisions_table(
                review_table_md=table_md,
                output_decisions_json=decisions_json,
            )
            decisions = json.loads(decisions_json.read_text(encoding="utf-8"))

        self.assertEqual(summary["review_status"], "invalid")
        self.assertEqual(summary["invalid_count"], 1)
        self.assertEqual(summary["validation_errors"][0]["error_type"], "duplicate_item_id")
        self.assertEqual(len(decisions["decisions"]), 3)

    def test_table_conversion_reports_action_not_listed_in_table(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, _queue_json = write_review_session_fixture(tmp_dir)
            table_md = tmp_dir / "historian_review" / "review_focus_decisions_table.md"
            build_mvp_review_focus_decisions_table(review_session_json=review_session_json, output_md=table_md)
            table_text = table_md.read_text(encoding="utf-8").replace(
                "|  |  |  | mvp-review-item:0001 |",
                "| publish_now |  |  | mvp-review-item:0001 |",
            )
            table_md.write_text(table_text, encoding="utf-8")

            summary = convert_mvp_review_focus_decisions_table(review_table_md=table_md)

        self.assertEqual(summary["review_status"], "invalid")
        self.assertEqual(summary["invalid_count"], 1)
        self.assertEqual(summary["validation_errors"][0]["error_type"], "action_not_listed_in_table")

    def test_builds_table_from_legacy_priority_items_when_focus_template_is_missing(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, queue_json = write_review_session_fixture(tmp_dir)
            session = json.loads(review_session_json.read_text(encoding="utf-8"))
            session.pop("review_focus_decisions_template")
            session["source_review_queue_json"] = str(queue_json)
            session["profiles"] = [
                {
                    "profile_id": "person:purocielo:andreoli-dino",
                    "priority_review_items": [
                        {"item_id": "mvp-review-item:0001"},
                        {"item_id": "mvp-review-item:0002"},
                    ],
                }
            ]
            review_session_json.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
            output_md = tmp_dir / "historian_review" / "review_focus_decisions_table.md"

            table = build_mvp_review_focus_decisions_table(
                review_session_json=review_session_json,
                output_md=output_md,
            )
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(table["decision_count"], 2)
        self.assertEqual(table["rows"][0]["item_id"], "mvp-review-item:0001")
        self.assertIn("approve_claim, reject_claim, mark_uncertain", markdown)
        self.assertIn("La data candidata", markdown)

    def test_builds_cards_from_review_queue_when_focus_and_profiles_are_empty(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            review_session_json, _queue_json = write_review_session_fixture(tmp_dir)
            session = json.loads(review_session_json.read_text(encoding="utf-8"))
            session["review_focus_decisions_template"] = {
                "@type": "ReviewDecisionTemplate",
                "template_scope": "review_focus",
                "item_count": 0,
                "decisions": [],
            }
            session["profiles"] = []
            review_session_json.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
            output_md = tmp_dir / "historian_review" / "review_focus_decisions_cards.md"

            cards = build_mvp_review_focus_decisions_cards(
                review_session_json=review_session_json,
                output_md=output_md,
                limit=1,
            )
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(cards, ensure_ascii=False) + markdown

        self.assertEqual(cards["decision_count"], 1)
        self.assertEqual(cards["cards"][0]["item_id"], "mvp-review-item:0001")
        self.assertIn("mvp-review-item:0001", markdown)
        self.assertIn("La data candidata e' supportata dal documento?", markdown)
        self.assertIn("| selected_action | reviewer | reviewed_at | note |", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)


if __name__ == "__main__":
    unittest.main()
