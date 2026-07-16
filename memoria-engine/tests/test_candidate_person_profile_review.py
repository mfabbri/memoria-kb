from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.candidate_person_profile_review import (  # noqa: E402
    build_candidate_person_profile_review,
)
from caduti_fonti_report.profile_repository import ProfileRepository  # noqa: E402


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


class CandidatePersonProfileReviewTests(unittest.TestCase):
    def test_builds_review_template_without_promoting_profiles(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            candidates_json = tmp_dir / "candidate_person_profiles_from_documents.json"
            output_dir = tmp_dir / "review"
            candidates_json.write_text(json.dumps(_candidate_payload(), ensure_ascii=False, indent=2), encoding="utf-8")

            summary = build_candidate_person_profile_review(candidates_json=candidates_json, output_dir=output_dir, limit=1)
            template = json.loads((output_dir / "candidate_person_profile_review.template.json").read_text(encoding="utf-8"))
            table = (output_dir / "candidate_person_profile_review_table.md").read_text(encoding="utf-8")
            historian_sheet = (output_dir / "candidate_person_profile_review_storico.md").read_text(encoding="utf-8")
            preview_index_exists = (output_dir / "preview_person_profiles" / "purocielo.index.jsonld").exists()

        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(summary["preview_profile_count"], 0)
        self.assertEqual(template["@type"], "CandidatePersonProfileReviewDecisionSet")
        self.assertEqual(len(template["decisions"]), 1)
        self.assertEqual(template["decisions"][0]["decision"], "needs_review")
        self.assertIn("Andreoli Dino", table)
        self.assertIn("Scheda di revisione storica", historian_sheet)
        self.assertIn("Si, preparare una scheda provvisoria", historian_sheet)
        self.assertIn("Nota:", historian_sheet)
        self.assertNotIn("Compilare il JSON", historian_sheet)
        self.assertTrue(preview_index_exists)

    def test_accepted_decision_generates_preview_profile_index(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            candidates_json = tmp_dir / "candidate_person_profiles_from_documents.json"
            decisions_json = tmp_dir / "review_decisions.json"
            output_dir = tmp_dir / "review"
            candidates_json.write_text(json.dumps(_candidate_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
            decisions_json.write_text(
                json.dumps(
                    {
                        "@type": "CandidatePersonProfileReviewDecisionSet",
                        "decisions": [
                            {
                                "candidate_profile_id": "candidate-person-profile:andreoli",
                                "decision": "accepted",
                                "corrected_canonical_name": "",
                                "reviewer": "storico",
                                "note": "profilo pilota",
                            },
                            {
                                "candidate_profile_id": "candidate-person-profile:guazzaloca",
                                "decision": "rejected",
                                "reviewer": "storico",
                                "note": "fuori subset",
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = build_candidate_person_profile_review(
                candidates_json=candidates_json,
                output_dir=output_dir,
                decisions_json=decisions_json,
            )
            preview_dir = output_dir / "preview_person_profiles"
            repository = ProfileRepository(preview_dir / "purocielo.index.jsonld")
            profiles = repository.load_profiles()
            profile_payload = json.loads((preview_dir / "purocielo-andreoli-dino.jsonld").read_text(encoding="utf-8"))

        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertEqual(summary["preview_profile_count"], 1)
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].profile_id, "person:purocielo:andreoli-dino")
        self.assertEqual(profiles[0].identity.canonical_name, "Andreoli Dino")
        self.assertEqual(profiles[0].seed.source, "document_candidate_profile_review")
        self.assertEqual(profiles[0].metadata["profile_status"], "preview")
        self.assertEqual(profile_payload["@type"], "PersonResearchProfile")
        self.assertEqual(profile_payload["verified_facts"], {})

    def test_decisions_json_is_read_without_being_overwritten(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            candidates_json = tmp_dir / "candidate_person_profiles_from_documents.json"
            output_dir = tmp_dir / "review"
            decisions_json = output_dir / "candidate_person_profile_review.compilato.json"
            candidates_json.write_text(json.dumps(_candidate_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
            output_dir.mkdir()
            decision_payload = {
                "@type": "CandidatePersonProfileReviewDecisionSet",
                "decisions": [
                    {
                        "candidate_profile_id": "candidate-person-profile:andreoli",
                        "decision": "accepted",
                        "reviewer": "storico",
                        "note": "tenere questa nota",
                    }
                ],
            }
            decisions_json.write_text(json.dumps(decision_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            original_decisions_text = decisions_json.read_text(encoding="utf-8")

            summary = build_candidate_person_profile_review(
                candidates_json=candidates_json,
                output_dir=output_dir,
                decisions_json=decisions_json,
            )
            decisions_text_after_run = decisions_json.read_text(encoding="utf-8")

        self.assertEqual(summary["decision_count"], 1)
        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["preview_profile_count"], 1)
        self.assertEqual(decisions_text_after_run, original_decisions_text)

    def test_refuses_template_as_compiled_decisions_file(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            candidates_json = tmp_dir / "candidate_person_profiles_from_documents.json"
            output_dir = tmp_dir / "review"
            template_json = output_dir / "candidate_person_profile_review.template.json"
            candidates_json.write_text(json.dumps(_candidate_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
            output_dir.mkdir()
            template_json.write_text(json.dumps({"decisions": []}, indent=2), encoding="utf-8")

            with self.assertRaises(ValueError):
                build_candidate_person_profile_review(
                    candidates_json=candidates_json,
                    output_dir=output_dir,
                    decisions_json=template_json,
                )

    def test_inline_accepted_candidate_ids_generate_preview_profiles(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            candidates_json = tmp_dir / "candidate_person_profiles_from_documents.json"
            output_dir = tmp_dir / "review"
            candidates_json.write_text(json.dumps(_candidate_payload(), ensure_ascii=False, indent=2), encoding="utf-8")

            summary = build_candidate_person_profile_review(
                candidates_json=candidates_json,
                output_dir=output_dir,
                accepted_candidate_profile_ids=[
                    "candidate-person-profile:andreoli",
                    "candidate-person-profile:missing",
                    "candidate-person-profile:andreoli",
                ],
            )
            repository = ProfileRepository(output_dir / "preview_person_profiles" / "purocielo.index.jsonld")
            profiles = repository.load_profiles()

        self.assertEqual(summary["decisions_source"], "accepted_candidate_profile_ids")
        self.assertEqual(summary["accepted_candidate_profile_ids"], ["candidate-person-profile:andreoli", "candidate-person-profile:missing"])
        self.assertEqual(summary["unknown_accepted_candidate_profile_ids"], ["candidate-person-profile:missing"])
        self.assertEqual(summary["accepted_count"], 1)
        self.assertEqual(summary["preview_profile_count"], 1)
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].profile_id, "person:purocielo:andreoli-dino")

    def test_decisions_json_takes_precedence_over_inline_accepted_ids(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            candidates_json = tmp_dir / "candidate_person_profiles_from_documents.json"
            decisions_json = tmp_dir / "review_decisions.json"
            output_dir = tmp_dir / "review"
            candidates_json.write_text(json.dumps(_candidate_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
            decisions_json.write_text(
                json.dumps(
                    {
                        "decisions": [
                            {
                                "candidate_profile_id": "candidate-person-profile:andreoli",
                                "decision": "rejected",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = build_candidate_person_profile_review(
                candidates_json=candidates_json,
                output_dir=output_dir,
                decisions_json=decisions_json,
                accepted_candidate_profile_ids=["candidate-person-profile:andreoli"],
            )

        self.assertEqual(summary["decisions_source"], "decisions_json")
        self.assertEqual(summary["ignored_accepted_candidate_profile_ids"], ["candidate-person-profile:andreoli"])
        self.assertEqual(summary["accepted_count"], 0)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertEqual(summary["preview_profile_count"], 0)


def _candidate_payload() -> dict[str, object]:
    return {
        "@type": "CandidatePersonProfileSet",
        "candidate_person_profiles": [
            {
                "@type": "CandidatePersonProfile",
                "@id": "candidate-person-profile:andreoli",
                "candidate_profile_id": "candidate-person-profile:andreoli",
                "suggested_profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "identity": {"canonical_name": "Andreoli Dino", "name_forms": ["Andreoli Dino"]},
                "birth": {"raw": "17 maggio 1920"},
                "death": {"raw": "11 ottobre 1944"},
                "formations": ["36a Brigata Garibaldi"],
                "places": ["Bologna"],
                "row_number": 1,
                "row_fields": {"nome": "Andreoli Dino", "nascita": "17 maggio 1920"},
                "source_document_id": "legacy_documents:caduti_purocielo",
                "text_path": "processed/legacy/caduti_purocielo.text.json",
                "raw_file": "legacy_documents/caduti_purocielo.csv",
                "provenance": {
                    "document_text_path": "processed/legacy/caduti_purocielo.text.json",
                    "source_document_id": "legacy_documents:caduti_purocielo",
                    "row_number": 1,
                },
            },
            {
                "@type": "CandidatePersonProfile",
                "@id": "candidate-person-profile:guazzaloca",
                "candidate_profile_id": "candidate-person-profile:guazzaloca",
                "suggested_profile_id": "person:purocielo:guazzaloca-laura",
                "canonical_name": "Guazzaloca Laura",
                "identity": {"canonical_name": "Guazzaloca Laura", "name_forms": ["Guazzaloca Laura"]},
                "birth": {"raw": "28 gennaio 1920"},
                "death": {"raw": ""},
                "formations": ["infermiera"],
                "places": ["Faenza"],
                "row_number": 2,
                "row_fields": {"nome": "Guazzaloca Laura"},
                "source_document_id": "legacy_documents:caduti_purocielo",
                "text_path": "processed/legacy/caduti_purocielo.text.json",
                "raw_file": "legacy_documents/caduti_purocielo.csv",
                "provenance": {
                    "document_text_path": "processed/legacy/caduti_purocielo.text.json",
                    "source_document_id": "legacy_documents:caduti_purocielo",
                    "row_number": 2,
                },
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
