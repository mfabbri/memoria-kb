from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_review_queue import build_mvp_review_queue  # noqa: E402
from caduti_fonti_report.document_analysis.mvp_review_queue_markdown import render_mvp_review_queue_markdown  # noqa: E402


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


def write_mvp_summary(root: Path) -> Path:
    summary = {
        "@type": "MvpPilotSummary",
        "profiles": [
            {"profile_id": "person:purocielo:andreoli-dino", "canonical_name": "Andreoli Dino"},
            {"profile_id": "person:purocielo:guazzaloca-laura", "canonical_name": "Guazzaloca Laura"},
        ],
        "profile_readiness": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "document_count": 1,
                "candidate_document_person_link_count": 1,
                "candidate_evidence_claim_count": 4,
                "readiness_status": "ready_for_review",
                "next_action": "Revisionare documenti, link e claim candidati.",
                "review_status": "unreviewed",
            },
            {
                "profile_id": "person:purocielo:guazzaloca-laura",
                "canonical_name": "Guazzaloca Laura",
                "document_count": 0,
                "candidate_document_person_link_count": 0,
                "candidate_evidence_claim_count": 0,
                "reviewable_document_signal_count": 1,
                "readiness_status": "needs_signal_review",
                "next_action": "Revisionare piste documentali e valutare segmentazione per produrre claim candidati.",
                "review_status": "unreviewed",
            },
        ],
        "candidate_document_person_links": [
            {
                "@id": "candidate-document-person-link:andreoli-doc-1",
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "doc-andreoli-1",
                "raw_file": "documenti_da_processare/andreoli/doc-andreoli-1.pdf",
                "metadata_file": "documenti_processati/andreoli/doc-andreoli-1.metadata.json",
                "score": 1.0,
                "context": "Andreoli Dino nacque a Bologna.",
                "review_status": "unreviewed",
            }
        ],
        "candidate_evidence_claims": [
            {
                "@id": "candidate-evidence-claim:andreoli-birth",
                "profile_id": "person:purocielo:andreoli-dino",
                "field": "birth.date",
                "value": "17 maggio 1920",
                "source_document_id": "doc-andreoli-1",
                "evidence_span": "Nato il 17 maggio 1920.",
                "review_status": "unreviewed",
            },
            {
                "@id": "candidate-evidence-claim:andreoli-death-place",
                "profile_id": "person:purocielo:andreoli-dino",
                "field": "death.place",
                "value": "Purocielo",
                "source_document_id": "doc-andreoli-1",
                "evidence_span": "Caduto nell'area di Purocielo.",
                "review_status": "unreviewed",
            },
            {
                "@id": "candidate-evidence-claim:andreoli-formation",
                "profile_id": "person:purocielo:andreoli-dino",
                "field": "formation.name",
                "value": "36a Brigata Garibaldi",
                "source_document_id": "doc-andreoli-1",
                "evidence_span": "Militava nella 36a Brigata Garibaldi.",
                "review_status": "unreviewed",
            },
            {
                "@id": "candidate-evidence-claim:andreoli-status",
                "profile_id": "person:purocielo:andreoli-dino",
                "field": "person.status",
                "value": "caduto",
                "source_document_id": "doc-andreoli-1",
                "evidence_span": "Scheda sintetica dei caduti.",
                "review_status": "unreviewed",
            }
        ],
        "reviewable_document_signals": [
            {
                "@type": "MvpProfileReviewableDocumentSignals",
                "profile_id": "person:purocielo:guazzaloca-laura",
                "canonical_name": "Guazzaloca Laura",
                "signal_count": 2,
                "signals": [
                    {
                        "@type": "ReviewableDocumentSignal",
                        "signal_type": "research_feedback_action",
                        "source_document_id": "legacy_csv:guazzaloca-1",
                        "source_item_id": "research-feedback-action:guazzaloca",
                        "value": "Guazzaloca Laura",
                        "context": "Guazzaloca Laura, Nascita: 28 gennaio 1920, Bologna.",
                        "reasons": ["research_feedback_action_unreviewed"],
                        "review_status": "unreviewed",
                    },
                    {
                        "@type": "ReviewableDocumentSignal",
                        "signal_type": "skipped_claim_candidate",
                        "source_document_id": "doc-guazzaloca-1",
                        "source_item_id": "skipped-candidate-claim:guazzaloca-birth",
                        "value": "28 gennaio 1920",
                        "entity_type": "date",
                        "context": "Guazzaloca Laura, nata il 28 gennaio 1920.",
                        "recommended_next_action": "better_segmentation_or_link_review",
                        "reasons": [
                            "ambiguous_or_missing_document_person_link",
                            "skipped_claim_candidate_unreviewed",
                        ],
                        "review_status": "unreviewed",
                        "publication_status": "not_publishable_without_human_review",
                    },
                    {
                        "@type": "ReviewableDocumentSignal",
                        "signal_type": "skipped_structured_document_claim_candidate",
                        "source_document_id": "doc-guazzaloca-1",
                        "source_item_id": "skipped-structured-document-claim:guazzaloca",
                        "value": "missing_source_detail_claim_mappings",
                        "context": "Scheda strutturata Guazzaloca | Motivo skip: missing_source_detail_claim_mappings",
                        "recommended_next_action": "manual_review",
                        "reasons": [
                            "missing_source_detail_claim_mappings",
                            "skipped_structured_document_claim_candidate_unreviewed",
                        ],
                        "review_status": "unreviewed",
                        "publication_status": "not_publishable_without_human_review",
                    }
                ],
                "review_status": "unreviewed",
            }
        ],
        "warnings": ["Nessun claim candidato per alcuni profili pilota."],
    }
    path = root / "mvp_pilot_summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class MvpReviewQueueTests(unittest.TestCase):
    def test_builds_review_queue_and_decision_template_from_mvp_summary(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            summary_path = write_mvp_summary(tmp_dir)
            output_json = tmp_dir / "historian_review" / "review_queue.json"
            output_md = tmp_dir / "historian_review" / "review_queue.md"
            template_json = tmp_dir / "historian_review" / "review_decisions.template.json"

            queue = build_mvp_review_queue(
                summary_json=summary_path,
                output_json=output_json,
                output_md=output_md,
                decisions_template_json=template_json,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            template = json.loads(template_json.read_text(encoding="utf-8"))
            serialized = json.dumps(persisted, ensure_ascii=False)

        self.assertEqual(queue["@type"], "HistorianReviewQueue")
        self.assertEqual(persisted["review_status"], "unreviewed")
        self.assertGreaterEqual(persisted["item_count"], 4)
        item_types = {item["item_type"] for item in persisted["items"]}
        self.assertIn("profile_readiness_review", item_types)
        self.assertIn("person_document_link_review", item_types)
        self.assertIn("candidate_claim_review", item_types)
        self.assertIn("date_entity_review", item_types)
        self.assertIn("place_entity_review", item_types)
        self.assertIn("event_context_review", item_types)
        self.assertIn("mvp_warning_review", item_types)
        subject_kinds = {item["subject_kind"] for item in persisted["items"]}
        self.assertIn("person", subject_kinds)
        self.assertIn("date", subject_kinds)
        self.assertIn("place", subject_kinds)
        self.assertIn("event_context", subject_kinds)
        self.assertIn("claim", subject_kinds)
        self.assertIn("workflow", subject_kinds)
        self.assertIn("subject_kind", json.dumps(template, ensure_ascii=False))
        self.assertIn("needs_human_transcription", json.dumps(template, ensure_ascii=False))
        self.assertIn("Review queue MVP", markdown)
        self.assertIn("Conteggi per oggetto", markdown)
        self.assertIn("Questo documento riguarda davvero la persona indicata?", markdown)
        self.assertIn("File sorgente: `documenti_da_processare/andreoli/doc-andreoli-1.pdf`", markdown)
        self.assertIn("Metadata: `documenti_processati/andreoli/doc-andreoli-1.metadata.json`", markdown)
        self.assertIn("File sorgente: `ricerche/caduti_purocielo.csv`", markdown)
        self.assertIn("seed legacy CSV, non documento storico verificato", markdown)
        self.assertIn("La data candidata", markdown)
        self.assertIn("Questo elemento saltato puo' diventare un claim", markdown)
        self.assertIn("Questa scheda strutturata va mappata", markdown)
        self.assertIn("Il luogo candidato", markdown)
        self.assertIn("Il contesto evento candidato", markdown)
        skipped_items = [
            item
            for item in persisted["items"]
            if item["source_item_id"] == "skipped-candidate-claim:guazzaloca-birth"
        ]
        self.assertEqual(len(skipped_items), 1)
        self.assertEqual(skipped_items[0]["subject_kind"], "date")
        self.assertEqual(skipped_items[0]["candidate"], {"field": "document_signal", "value": "28 gennaio 1920"})
        self.assertIn("signal_type=skipped_claim_candidate", skipped_items[0]["reasons"])
        structured_items = [
            item
            for item in persisted["items"]
            if item["source_item_id"] == "skipped-structured-document-claim:guazzaloca"
        ]
        self.assertEqual(len(structured_items), 1)
        self.assertEqual(structured_items[0]["subject_kind"], "claim")
        self.assertEqual(structured_items[0]["candidate"], {"field": "document_signal", "value": "missing_source_detail_claim_mappings"})
        self.assertIn("signal_type=skipped_structured_document_claim_candidate", structured_items[0]["reasons"])
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)
        self.assertTrue(all(item["review_status"] == "unreviewed" for item in persisted["items"]))

    def test_missing_summary_fails_without_writing_outputs(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            output_json = tmp_dir / "historian_review" / "review_queue.json"

            with self.assertRaises(FileNotFoundError):
                build_mvp_review_queue(
                    summary_json=tmp_dir / "missing.json",
                    output_json=output_json,
                    output_md=tmp_dir / "historian_review" / "review_queue.md",
                    decisions_template_json=tmp_dir / "historian_review" / "review_decisions.template.json",
                )

            self.assertFalse(output_json.exists())

    def test_markdown_renderer_keeps_empty_state_and_document_details(self) -> None:
        markdown = render_mvp_review_queue_markdown(
            {
                "source_summary_json": "runs/demo/mvp_pilot_summary.json",
                "review_status": "unreviewed",
                "publication_status": "not_publishable_without_human_review",
                "item_count": 1,
                "items": [
                    {
                        "item_id": "mvp-review-item:0001",
                        "item_type": "person_document_link_review",
                        "subject_kind": "person",
                        "priority": "high",
                        "risk": "medium",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "canonical_name": "Andreoli Dino",
                        "source_document_id": "doc-andreoli-1",
                        "question": "Questo documento riguarda davvero la persona indicata?",
                        "allowed_decisions": ["confirm", "reject_false_positive"],
                        "review_status": "unreviewed",
                        "raw_file": "documenti_da_processare/andreoli/doc-andreoli-1.pdf",
                        "metadata_file": "documenti_processati/andreoli/doc-andreoli-1.metadata.json",
                        "document_reference_note": "nota documento demo",
                        "context": "Andreoli Dino nacque a Bologna.",
                        "reasons": ["candidate_link_unreviewed"],
                    }
                ],
            }
        )
        empty_markdown = render_mvp_review_queue_markdown({"items": []})

        self.assertIn("Source summary: `runs/demo/mvp_pilot_summary.json`", markdown)
        self.assertIn("- `person`: 1", markdown)
        self.assertIn("File sorgente: `documenti_da_processare/andreoli/doc-andreoli-1.pdf`", markdown)
        self.assertIn("Metadata: `documenti_processati/andreoli/doc-andreoli-1.metadata.json`", markdown)
        self.assertIn("- Nota documento: nota documento demo", markdown)
        self.assertIn("> Andreoli Dino nacque a Bologna.", markdown)
        self.assertIn("- candidate_link_unreviewed", markdown)
        self.assertIn("`confirm` conferma solo l'item in revisione", markdown)
        self.assertIn("_Nessun oggetto di revisione generato._", empty_markdown)
        self.assertIn("_Nessun item di revisione generato._", empty_markdown)


if __name__ == "__main__":
    unittest.main()
