from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.candidate_new_profile_materialization import (
    CandidateNewProfileMaterializationPlan,
    build_candidate_new_profile_materialization_plan,
    validate_candidate_new_profile_materialization_plan,
)


def candidate(name: str) -> dict[str, str]:
    slug = name.casefold().replace(" ", "-")
    return {
        "@id": f"candidate-new-profile:{slug}",
        "detected_name": name,
        "source_profile_id": "person:purocielo:guazzaloca-laura",
        "source_run_id": "run:t34b-fixture",
        "source_document_id": "doc:t34b-fixture",
        "source_url": "https://example.test/t34b",
        "context_quote": f"Fixture offline per {name}.",
        "confidence": "0.9",
    }


def accepted_decision(name: str) -> dict[str, str]:
    return {
        "decision": "accepted",
        "json_pointer": f"/review_decisions/{name.casefold().replace(' ', '-')}",
        "reviewer": "reviewer-fixture",
        "reviewed_at": "2026-09-11T10:00:00+02:00",
    }


DECISION_SET = {"@id": "decision-set:block5f", "hash": "sha256:decision-fixture"}


class CandidateNewProfileMaterializationTests(unittest.TestCase):
    def test_four_t34b_cases_are_preview_only_and_auditable(self) -> None:
        cases = (
            ("Marciatori Adriano", "create_new", ""),
            ("Tacconi Rosa", "create_new", ""),
            ("Bergonzoni Lino", "create_new", ""),
            ("Saba Mario", "link_existing", "person:purocielo:saba-mario"),
        )
        plans = []
        for name, resolution, existing_profile_id in cases:
            plans.append(
                build_candidate_new_profile_materialization_plan(
                    candidate=candidate(name),
                    decision=accepted_decision(name),
                    candidate_artifact_hash="sha256:candidate-fixture",
                    decision_set=DECISION_SET,
                    resolution=resolution,
                    existing_profile_id=existing_profile_id,
                )
            )

        by_name = {plan["candidate"]["detected_name"]: plan for plan in plans}
        self.assertTrue(all(isinstance(plan, CandidateNewProfileMaterializationPlan) for plan in plans))
        self.assertTrue(all(plan["preview_only"] for plan in plans))
        self.assertTrue(all(not plan["canonical_profiles_modified"] for plan in plans))
        self.assertEqual(by_name["Saba Mario"]["resolution"], "link_existing")
        self.assertIsNone(by_name["Saba Mario"]["profile_seed"])
        self.assertEqual(by_name["Saba Mario"]["target"]["existing_profile_id"], "person:purocielo:saba-mario")
        self.assertEqual(by_name["Tacconi Rosa"]["target"]["profile_id"], "person:purocielo:tacconi-rosa")
        self.assertEqual(by_name["Tacconi Rosa"]["target"]["profile_path"], "ricerche/person_profiles/purocielo-tacconi-rosa.jsonld")
        self.assertEqual(
            set(by_name["Tacconi Rosa"]["profile_seed"]),
            {"@id", "@type", "identity", "seed_provenance"},
        )
        self.assertEqual(by_name["Tacconi Rosa"]["audit"]["status"], "planned_preview_only")
        self.assertEqual(by_name["Tacconi Rosa"]["audit"]["review_status"], "accepted")
        self.assertEqual(by_name["Tacconi Rosa"]["rollback"]["rollback_action"], "no_canonical_write_to_revert")
        self.assertEqual(by_name["Tacconi Rosa"]["manifest"]["plan_hash"], by_name["Tacconi Rosa"]["plan_hash"])

    def test_plan_is_immutable_and_hash_validated(self) -> None:
        plan = build_candidate_new_profile_materialization_plan(
            candidate=candidate("Tacconi Rosa"),
            decision=accepted_decision("Tacconi Rosa"),
            candidate_artifact_hash="sha256:candidate-fixture",
            decision_set=DECISION_SET,
            resolution="create_new",
        )
        with self.assertRaises(TypeError):
            plan["preview_only"] = False  # type: ignore[index]
        with self.assertRaises(TypeError):
            plan["profile_seed"]["identity"]["canonical_name"] = "Alterata"  # type: ignore[index]
        validate_candidate_new_profile_materialization_plan(plan)
        tampered = plan.to_dict()
        tampered["provenance"]["source_document_id"] = "doc:altered"
        with self.assertRaisesRegex(ValueError, "plan_hash divergente"):
            validate_candidate_new_profile_materialization_plan(tampered)

    def test_rejects_non_accepted_and_incomplete_provenance(self) -> None:
        rejected = accepted_decision("Marciatori Adriano")
        rejected["decision"] = "rejected"
        with self.assertRaisesRegex(ValueError, "Solo una decisione accepted"):
            build_candidate_new_profile_materialization_plan(
                candidate=candidate("Marciatori Adriano"),
                decision=rejected,
                candidate_artifact_hash="sha256:candidate-fixture",
                decision_set=DECISION_SET,
                resolution="create_new",
            )
        missing_run = candidate("Bergonzoni Lino")
        missing_run["source_run_id"] = ""
        with self.assertRaisesRegex(ValueError, "source_run_id obbligatorio"):
            build_candidate_new_profile_materialization_plan(
                candidate=missing_run,
                decision=accepted_decision("Bergonzoni Lino"),
                candidate_artifact_hash="sha256:candidate-fixture",
                decision_set=DECISION_SET,
                resolution="create_new",
            )

    def test_blocked_collision_is_a_preview_plan_without_seed(self) -> None:
        plan = build_candidate_new_profile_materialization_plan(
            candidate=candidate("Collisione Nome"),
            decision=accepted_decision("Collisione Nome"),
            candidate_artifact_hash="sha256:candidate-fixture",
            decision_set=DECISION_SET,
            resolution="blocked_collision",
        )

        self.assertEqual(plan["resolution"], "blocked_collision")
        self.assertIsNone(plan["profile_seed"])
        self.assertEqual(plan["manifest"]["canonical_write_count"], 0)


if __name__ == "__main__":
    unittest.main()
