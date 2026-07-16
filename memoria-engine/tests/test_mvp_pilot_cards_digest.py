from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_pilot_cards_digest import (  # noqa: E402
    build_mvp_pilot_cards_digest,
    render_mvp_pilot_cards_digest_markdown,
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


def write_summary_fixture(root: Path) -> Path:
    summary = {
        "@type": "MvpPilotSummary",
        "profiles": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
            },
            {
                "profile_id": "person:purocielo:guazzaloca-laura",
                "canonical_name": "Guazzaloca Laura",
            },
        ],
        "documents": [
            {
                "source_document_id": "doc-andreoli",
                "title": "Scheda Andreoli Dino",
                "review_status": "unreviewed",
            }
        ],
        "candidate_document_person_links": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "doc-andreoli",
                "review_status": "unreviewed",
            }
        ],
        "candidate_evidence_claims": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "doc-andreoli",
                "field": "birth_date",
                "value": "1920-05-17",
                "review_status": "unreviewed",
            }
        ],
        "reviewable_document_signals": [
            {
                "profile_id": "person:purocielo:guazzaloca-laura",
                "signals": [
                    {
                        "signal_type": "research_feedback_action",
                        "source_document_id": "doc-guazzaloca",
                        "context": "Guazzaloca Laura citata in un documento da segmentare.",
                        "review_status": "unreviewed",
                    }
                ],
            }
        ],
        "profile_readiness": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "document_count": 1,
                "readiness_status": "ready_for_review",
                "next_action": "Revisionare documenti, link e claim candidati.",
                "review_status": "unreviewed",
            },
            {
                "profile_id": "person:purocielo:guazzaloca-laura",
                "document_count": 0,
                "readiness_status": "needs_signal_review",
                "next_action": "Revisionare piste documentali.",
                "review_status": "unreviewed",
            },
        ],
    }
    path = root / "mvp_pilot_summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class MvpPilotCardsDigestTests(unittest.TestCase):
    def test_builds_digest_for_candidate_cards_without_promoting_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            summary_json = write_summary_fixture(tmp_dir)
            vault_dir = tmp_dir / "vault"
            cards_dir = vault_dir / "40_Publication_Candidates"
            cards_dir.mkdir(parents=True)
            (cards_dir / "andreoli-dino.md").write_text("# Andreoli Dino\n", encoding="utf-8")
            output_json = tmp_dir / "mvp_pilot_cards_digest.json"
            output_md = tmp_dir / "mvp_pilot_cards_digest.md"

            digest = build_mvp_pilot_cards_digest(
                summary_json=summary_json,
                vault_dir=vault_dir,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False) + markdown

        self.assertEqual(digest["@type"], "MvpPilotCardsDigest")
        self.assertEqual(persisted["profile_count"], 2)
        self.assertEqual(persisted["ready_for_review_count"], 1)
        self.assertEqual(persisted["candidate_card_count"], 1)
        self.assertTrue(persisted["cards"][0]["candidate_card_exists"])
        self.assertEqual(persisted["cards"][0]["top_claims"][0]["field"], "birth_date")
        self.assertEqual(persisted["cards"][1]["top_signals"][0]["signal_type"], "research_feedback_action")
        self.assertIn("Digest schede pilota MVP", markdown)
        self.assertIn("Andreoli Dino", markdown)
        self.assertIn("Guazzaloca Laura", markdown)
        self.assertIn("1 schede candidate non sono presenti nel vault", markdown)
        self.assertIn("not_publishable_without_curator_review", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_markdown_handles_empty_digest(self) -> None:
        markdown = render_mvp_pilot_cards_digest_markdown({"cards": []})

        self.assertIn("Nessuna scheda pilota", markdown)
        self.assertIn("Non legge note editoriali Obsidian", markdown)


if __name__ == "__main__":
    unittest.main()
