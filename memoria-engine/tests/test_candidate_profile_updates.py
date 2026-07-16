from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.candidate_profile_updates import build_candidate_profile_updates, build_profile_patch
from caduti_fonti_report.models import PersonQuery
from caduti_fonti_report.person_profiles import profile_from_person_query, profile_to_jsonld


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


class CandidateProfileUpdatesTests(unittest.TestCase):
    def test_builds_reviewable_updates_without_merging_profile(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path = tmp_dir / "purocielo-guazzaloca-laura.jsonld"
            report_path = tmp_dir / "report.json"
            profile = profile_from_person_query(
                PersonQuery(
                    full_name="Guazzaloca Laura",
                    given_name="Laura",
                    family_name="Guazzaloca",
                    birth_date="28 gennaio 1920, Bologna",
                    death_date="novembre 1944, campo di Fossoli",
                    formation="maestra elementare, infermiera partigiana",
                ),
                seed_source="fixture.csv",
            )
            profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False), encoding="utf-8")
            report_path.write_text(
                json.dumps(
                    {
                        "profiles": [
                            {
                                "profile_id": "person:purocielo:guazzaloca-laura",
                                "results": [
                                    {
                                        "claims": [
                                            {
                                                "claim_id": "claim:1",
                                                "field": "person.full_name",
                                                "value": "Laura Guazzaloca",
                                                "source_document_id": "doc:1",
                                                "source_url": "https://example.test/1",
                                                "quote": "Laura Guazzaloca",
                                                "confidence": 0.95,
                                            },
                                            {
                                                "claim_id": "claim:2",
                                                "field": "birth.date",
                                                "value": "28 gennaio 1920",
                                                "source_document_id": "doc:1",
                                                "source_url": "https://example.test/1",
                                                "quote": "28 gennaio 1920",
                                                "confidence": 0.9,
                                            },
                                            {
                                                "claim_id": "claim:3",
                                                "field": "death.date",
                                                "value": "23 novembre 1944",
                                                "source_document_id": "doc:1",
                                                "source_url": "https://example.test/1",
                                                "quote": "23 novembre 1944",
                                                "confidence": 0.9,
                                            },
                                            {
                                                "claim_id": "claim:4",
                                                "field": "death.cause",
                                                "value": "Esecuzione",
                                                "source_document_id": "doc:1",
                                                "source_url": "https://example.test/1",
                                                "quote": "Esecuzione",
                                                "confidence": 0.75,
                                            },
                                            {
                                                "claim_id": "claim:4",
                                                "field": "death.cause",
                                                "value": "Esecuzione",
                                                "source_document_id": "doc:1",
                                                "source_url": "https://example.test/1",
                                                "quote": "Esecuzione",
                                                "confidence": 0.75,
                                            },
                                        ]
                                    }
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_candidate_profile_updates(report_json=report_path, profile_jsonld=profile_path)

        updates_by_field = {update["field"]: update for update in payload["candidate_updates"]}
        self.assertEqual(payload["merge_policy"], "preview_only_no_profile_write")
        self.assertEqual(updates_by_field["person.full_name"]["proposed_action"], "alternate_name_order")
        self.assertEqual(updates_by_field["person.full_name"]["review_bucket"], "da_accettare_facilmente")
        self.assertEqual(updates_by_field["birth.date"]["proposed_action"], "refinement")
        self.assertEqual(updates_by_field["death.date"]["proposed_action"], "refinement")
        self.assertEqual(updates_by_field["death.cause"]["proposed_action"], "new_fact")
        self.assertEqual(updates_by_field["death.cause"]["review_status"], "pending")
        self.assertEqual(updates_by_field["death.cause"]["source_claim_ids"], ["claim:4"])

    def test_extracts_candidate_new_profiles_from_related_people_section(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path = tmp_dir / "purocielo-guazzaloca-laura.jsonld"
            report_path = tmp_dir / "report.json"
            profile = profile_from_person_query(
                PersonQuery(full_name="Guazzaloca Laura", given_name="Laura", family_name="Guazzaloca"),
                seed_source="fixture.csv",
            )
            profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False), encoding="utf-8")
            report_path.write_text(
                json.dumps(
                    {
                        "profiles": [
                            {
                                "profile_id": "person:purocielo:guazzaloca-laura",
                                "canonical_name": "Guazzaloca Laura",
                                "results": [
                                    {
                                        "documents": [
                                            {
                                                "document_id": "doc:1",
                                                "url": "https://example.test/1",
                                                "raw_text": "Persone Giordano Romeo Moretti Renato Bologna, 20 ottobre 1944 Terzi Ferruccio Bibliografia",
                                            }
                                        ],
                                        "claims": [],
                                    }
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_candidate_profile_updates(report_json=report_path, profile_jsonld=profile_path)

        detected_names = {candidate["detected_name"] for candidate in payload["candidate_new_profiles"]}
        self.assertIn("Giordano Romeo", detected_names)
        self.assertIn("Moretti Renato", detected_names)
        self.assertIn("Terzi Ferruccio", detected_names)
        self.assertTrue(all(candidate["review_status"] == "pending" for candidate in payload["candidate_new_profiles"]))

    def test_existing_profile_index_moves_related_people_to_links(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path = tmp_dir / "purocielo-guazzaloca-laura.jsonld"
            report_path = tmp_dir / "report.json"
            index_path = tmp_dir / "purocielo.index.jsonld"
            profile = profile_from_person_query(
                PersonQuery(full_name="Guazzaloca Laura", given_name="Laura", family_name="Guazzaloca"),
                seed_source="fixture.csv",
            )
            profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False), encoding="utf-8")
            report_path.write_text(
                json.dumps(
                    {
                        "profiles": [
                            {
                                "profile_id": "person:purocielo:guazzaloca-laura",
                                "canonical_name": "Guazzaloca Laura",
                                "results": [
                                    {
                                        "documents": [
                                            {
                                                "document_id": "doc:1",
                                                "url": "https://example.test/1",
                                                "raw_text": "Persone Giordano Romeo Moretti Renato Bologna, 20 ottobre 1944 Terzi Ferruccio Bibliografia",
                                            }
                                        ],
                                        "claims": [],
                                    }
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            index_path.write_text(
                json.dumps(
                    {
                        "profiles": [
                            {
                                "@id": "person:purocielo:guazzaloca-laura",
                                "file": "purocielo-guazzaloca-laura.jsonld",
                                "canonical_name": "Guazzaloca Laura",
                            },
                            {
                                "@id": "person:purocielo:memo-moretti-renato",
                                "file": "purocielo-memo-moretti-renato.jsonld",
                                "canonical_name": "Memo. Moretti Renato",
                            },
                            {
                                "@id": "person:purocielo:terzi-ferruccio",
                                "file": "purocielo-terzi-ferruccio.jsonld",
                                "canonical_name": "Terzi Ferruccio",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_candidate_profile_updates(
                report_json=report_path,
                profile_jsonld=profile_path,
                profiles_index=index_path,
            )

        new_names = {candidate["detected_name"] for candidate in payload["candidate_new_profiles"]}
        linked_by_name = {link["detected_name"]: link for link in payload["candidate_existing_profile_links"]}
        self.assertEqual(new_names, {"Giordano Romeo"})
        self.assertEqual(linked_by_name["Moretti Renato"]["existing_profile_id"], "person:purocielo:memo-moretti-renato")
        self.assertEqual(linked_by_name["Terzi Ferruccio"]["existing_profile_id"], "person:purocielo:terzi-ferruccio")
        self.assertTrue(all(link["review_status"] == "pending" for link in linked_by_name.values()))
        self.assertTrue(all(link["source_document_id"] == "doc:1" for link in linked_by_name.values()))

    def test_builds_profile_updates_from_document_candidate_claims_without_merging(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path = tmp_dir / "purocielo-guazzaloca-laura.jsonld"
            claims_path = tmp_dir / "candidate_evidence_claims.json"
            profile = profile_from_person_query(
                PersonQuery(
                    full_name="Guazzaloca Laura",
                    given_name="Laura",
                    family_name="Guazzaloca",
                    death_date="novembre 1944",
                ),
                seed_source="fixture.csv",
            )
            profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False), encoding="utf-8")
            claims_path.write_text(
                json.dumps(
                    {
                        "@type": "CandidateEvidenceClaimSet",
                        "candidate_evidence_claims": [
                            {
                                "@type": "CandidateEvidenceClaim",
                                "@id": "candidate-evidence-claim:death-date",
                                "profile_id": "person:purocielo:guazzaloca-laura",
                                "profile_source_file": str(profile_path),
                                "field": "death.date",
                                "value": "23 novembre 1944",
                                "source_document_id": "manual_uploads:doc-1",
                                "url": "https://example.test/documento",
                                "evidence_span": "Caduta il 23 novembre 1944",
                                "confidence": 0.82,
                                "review_status": "unreviewed",
                            },
                            {
                                "@type": "CandidateEvidenceClaim",
                                "@id": "candidate-evidence-claim:reviewed",
                                "profile_id": "person:purocielo:guazzaloca-laura",
                                "field": "birth.date",
                                "value": "28 gennaio 1920",
                                "source_document_id": "manual_uploads:doc-1",
                                "confidence": 0.8,
                                "review_status": "reviewed",
                            },
                            {
                                "@type": "CandidateEvidenceClaim",
                                "@id": "candidate-evidence-claim:other-profile",
                                "profile_id": "person:purocielo:andreoli-dino",
                                "field": "death.date",
                                "value": "11 ottobre 1944",
                                "source_document_id": "manual_uploads:doc-2",
                                "confidence": 0.8,
                                "review_status": "unreviewed",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = build_candidate_profile_updates(
                candidate_claims_json=claims_path,
                profile_jsonld=profile_path,
            )

        self.assertEqual(payload["input_report"], "")
        self.assertEqual(payload["input_candidate_claims"], str(claims_path))
        self.assertEqual(payload["merge_policy"], "preview_only_no_profile_write")
        self.assertEqual(len(payload["candidate_updates"]), 1)
        update = payload["candidate_updates"][0]
        self.assertEqual(update["field"], "death.date")
        self.assertEqual(update["candidate_value"], "23 novembre 1944")
        self.assertEqual(update["review_status"], "pending")
        self.assertEqual(update["source_claim_ids"], ["candidate-evidence-claim:death-date"])
        self.assertEqual(update["source_document_ids"], ["manual_uploads:doc-1"])
        self.assertEqual(update["source_urls"], ["https://example.test/documento"])
        self.assertEqual(update["quotes"], ["Caduta il 23 novembre 1944"])
        self.assertEqual(update["confidence"], 0.82)

    def test_requires_report_or_document_candidate_claims_input(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path = tmp_dir / "purocielo-guazzaloca-laura.jsonld"
            profile = profile_from_person_query(
                PersonQuery(full_name="Guazzaloca Laura", given_name="Laura", family_name="Guazzaloca"),
                seed_source="fixture.csv",
            )
            profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(ValueError):
                build_candidate_profile_updates(profile_jsonld=profile_path)

    def test_accepted_review_decisions_generate_profile_patch_preview(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            updates_path = tmp_dir / "candidate_updates.jsonld"
            decisions_path = tmp_dir / "decisions.json"
            updates_path.write_text(
                json.dumps(
                    {
                        "profile_id": "person:purocielo:guazzaloca-laura",
                        "profile_source_file": "profile.jsonld",
                        "candidate_updates": [
                            {
                                "@id": "candidate-profile-update:accepted",
                                "field": "death.date",
                                "candidate_value": "23 novembre 1944",
                                "source_claim_ids": ["claim:1"],
                                "source_document_ids": ["doc:1"],
                            },
                            {
                                "@id": "candidate-profile-update:rejected",
                                "field": "death.cause",
                                "candidate_value": "Esecuzione",
                                "source_claim_ids": ["claim:2"],
                                "source_document_ids": ["doc:1"],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            decisions_path.write_text(
                json.dumps(
                    {
                        "review_decisions": [
                            {
                                "@type": "ReviewDecision",
                                "candidate_update_id": "candidate-profile-update:accepted",
                                "decision": "accepted",
                                "reviewer": "test",
                                "note": "Data precisa accettata.",
                            },
                            {
                                "@type": "ReviewDecision",
                                "candidate_update_id": "candidate-profile-update:rejected",
                                "decision": "rejected",
                                "reviewer": "test",
                                "note": "Da verificare altrove.",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            patch = build_profile_patch(candidate_updates_jsonld=updates_path, decisions_json=decisions_path)

        self.assertEqual(patch["@type"], "ProfilePatch")
        self.assertEqual(len(patch["operations"]), 1)
        self.assertEqual(patch["operations"][0]["path"], "/death/date")
        self.assertEqual(patch["operations"][0]["value"], "23 novembre 1944")
        self.assertEqual(patch["apply_policy"], "requires_explicit_apply_profile_patch_command")


if __name__ == "__main__":
    unittest.main()
