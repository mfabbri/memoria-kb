from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_model_cards import build_mvp_model_cards  # noqa: E402


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class MvpModelCardsTests(unittest.TestCase):
    def test_builds_model_cards_and_excerpts_without_promoting_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            digest_json = write_json(
                tmp_dir / "mvp_pilot_cards_digest.json",
                {
                    "@type": "MvpPilotCardsDigest",
                    "cards": [
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "canonical_name": "Andreoli Dino",
                            "readiness_status": "ready_for_review",
                            "next_action": "Revisionare documenti, link e claim candidati.",
                            "candidate_card_path": "vault/40_Publication_Candidates/andreoli-dino.md",
                            "document_count": 1,
                            "candidate_document_person_link_count": 2,
                            "candidate_evidence_claim_count": 1,
                            "reviewable_document_signal_count": 1,
                            "top_documents": [
                                {
                                    "source_document_id": "doc-1",
                                    "title": "Scheda Andreoli",
                                }
                            ],
                            "top_claims": [
                                {
                                    "field": "person.full_name",
                                    "value": "Andreoli Dino",
                                    "source_document_id": "doc-1",
                                    "review_status": "unreviewed",
                                }
                            ],
                            "top_signals": [
                                {
                                    "signal_type": "candidate_document_person_link",
                                    "source_document_id": "doc-1",
                                    "summary": "Nome compatibile nel documento.",
                                    "review_status": "unreviewed",
                                }
                            ],
                        }
                    ],
                },
            )
            summary_json = write_json(
                tmp_dir / "mvp_pilot_summary.json",
                {
                    "@type": "MvpPilotSummary",
                    "profiles": [
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "canonical_name": "Andreoli Dino",
                            "seed": {"full_name": "Andreoli Dino"},
                        }
                    ],
                },
            )
            review_session_json = write_json(
                tmp_dir / "review_session.json",
                {
                    "@type": "MvpReviewSessionPack",
                    "profiles": [
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "model_card_review_status": "in_historical_review",
                            "review_session_status": "not_started",
                            "accepted_decision_count": 2,
                            "approved_decision_count": 1,
                            "rejected_decision_count": 1,
                            "uncertain_decision_count": 1,
                            "pending_decision_count": 3,
                            "invalid_decision_count": 0,
                            "decision_counts_by_action": {
                                "approve_claim": 1,
                                "reject_false_positive": 1,
                                "request_more_sources": 1,
                            },
                            "decision_counts_by_status": {"accepted": 2, "pending": 3},
                            "publication_constraint": "Non pubblicabile: restano decisioni storiche pending.",
                            "next_action": "Compilare le decisioni pending.",
                        }
                    ],
                },
            )
            verified_facts_preview_json = write_json(
                tmp_dir / "verified_facts.preview.json",
                {
                    "@type": "VerifiedFactsPreview",
                    "preview_only": True,
                    "facts": [
                        {
                            "@type": "VerifiedFactPreview",
                            "profile_id": "person:purocielo:andreoli-dino",
                            "field": "death.place",
                            "value": "Purocielo",
                            "source_document_id": "doc-1",
                            "source_decision_record_id": "evidence-record:decision-confirm",
                            "reviewer": "storico-test",
                            "reviewed_at": "2026-06-21",
                            "review_status": "preview-only",
                            "publication_status": "not_publishable_without_editorial_review",
                        },
                        {
                            "@type": "VerifiedFactPreview",
                            "profile_id": "person:purocielo:balboni-william",
                            "field": "death.place",
                            "value": "Altro profilo",
                            "source_document_id": "doc-2",
                            "source_decision_record_id": "evidence-record:decision-other",
                        },
                    ],
                },
            )
            output_dir = tmp_dir / "schede_modello"
            excerpts_dir = tmp_dir / "funding_excerpts"

            manifest = build_mvp_model_cards(
                digest_json=digest_json,
                summary_json=summary_json,
                review_session_json=review_session_json,
                output_dir=output_dir,
                funding_excerpts_dir=excerpts_dir,
                verified_facts_preview_json=verified_facts_preview_json,
                limit=3,
            )
            model_card = output_dir / "andreoli-dino.md"
            excerpt = excerpts_dir / "andreoli-dino.md"
            manifest_json = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            model_card_exists = model_card.exists()
            excerpt_exists = excerpt.exists()
            serialized = (
                model_card.read_text(encoding="utf-8")
                + excerpt.read_text(encoding="utf-8")
                + json.dumps(manifest_json, ensure_ascii=False)
            )

        self.assertEqual(manifest["@type"], "MvpModelCardsBuild")
        self.assertEqual(manifest["model_card_count"], 1)
        self.assertTrue(model_card_exists)
        self.assertTrue(excerpt_exists)
        self.assertIn("Bozza di revisione - non pubblicabile senza validazione storica", serialized)
        self.assertIn("Dati seed non pubblicabili senza fonte", serialized)
        self.assertIn("Fatti preview", serialized)
        self.assertIn("`death.place`: Purocielo", serialized)
        self.assertIn("evidence-record:decision-confirm", serialized)
        self.assertIn("storico-test", serialized)
        self.assertIn("Fatti preview: `1`", serialized)
        self.assertNotIn("Altro profilo", serialized)
        self.assertIn("Evidenze candidate", serialized)
        self.assertIn("Piste documentali senza claim", serialized)
        self.assertIn("Decisioni storiche", serialized)
        self.assertIn("Decisioni accettate: `2`", serialized)
        self.assertIn("Decisioni approvate: `1`", serialized)
        self.assertIn("Decisioni respinte: `1`", serialized)
        self.assertIn("Decisioni incerte o conflittuali: `1`", serialized)
        self.assertIn("Decisioni storiche: accettate `2`, respinte `1`, incerte `1`, pending `3`", serialized)
        self.assertEqual(manifest_json["cards"][0]["accepted_decision_count"], 2)
        self.assertEqual(manifest_json["cards"][0]["rejected_decision_count"], 1)
        self.assertEqual(manifest_json["cards"][0]["verified_fact_preview_count"], 1)
        self.assertIn("review `unreviewed`", serialized)
        self.assertIn("not_publishable_without_human_review", serialized)
        self.assertIn("Non pubblicabile: restano decisioni storiche pending.", serialized)
        self.assertNotIn('"verified_facts"', serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_limit_controls_generated_cards(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            digest_json = write_json(
                tmp_dir / "mvp_pilot_cards_digest.json",
                {
                    "cards": [
                        {"profile_id": "person:purocielo:one", "canonical_name": "One"},
                        {"profile_id": "person:purocielo:two", "canonical_name": "Two"},
                    ]
                },
            )
            summary_json = write_json(tmp_dir / "mvp_pilot_summary.json", {"profiles": []})
            review_session_json = write_json(tmp_dir / "review_session.json", {"profiles": []})

            manifest = build_mvp_model_cards(
                digest_json=digest_json,
                summary_json=summary_json,
                review_session_json=review_session_json,
                output_dir=tmp_dir / "schede_modello",
                limit=1,
            )

        self.assertEqual(manifest["model_card_count"], 1)
        self.assertEqual(manifest["cards"][0]["canonical_name"], "One")

    def test_skipped_verified_facts_preview_is_accepted_without_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            digest_json = write_json(
                tmp_dir / "mvp_pilot_cards_digest.json",
                {"cards": [{"profile_id": "person:purocielo:one", "canonical_name": "One"}]},
            )
            summary_json = write_json(tmp_dir / "mvp_pilot_summary.json", {"profiles": []})
            review_session_json = write_json(tmp_dir / "review_session.json", {"profiles": []})
            verified_facts_preview_json = write_json(
                tmp_dir / "verified_facts.preview.json",
                {"status": "skipped", "facts": [{"profile_id": "person:purocielo:one"}]},
            )

            manifest = build_mvp_model_cards(
                digest_json=digest_json,
                summary_json=summary_json,
                review_session_json=review_session_json,
                output_dir=tmp_dir / "schede_modello",
                verified_facts_preview_json=verified_facts_preview_json,
                limit=1,
            )
            model_card = (tmp_dir / "schede_modello" / "one.md").read_text(encoding="utf-8")

        self.assertEqual(manifest["cards"][0]["verified_fact_preview_count"], 0)
        self.assertIn("Nessun fatto preview per questo profilo.", model_card)


if __name__ == "__main__":
    unittest.main()
