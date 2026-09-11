from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.t34b_materialization_preflight import build_t34b_materialization_preflight


CASES = (
    ("Marciatori Adriano", "candidate-new-profile:28791183d6d3b40e", "person:candidate:marciatori-adriano"),
    ("Saba Mario", "candidate-new-profile:5b7127b0979a5f9d", "person:candidate:saba-mario"),
    ("Tacconi Rosa", "candidate-new-profile:17c558caca87c244", "person:candidate:tacconi-rosa"),
    ("Bergonzoni Lino", "candidate-new-profile:681c0e078581bd54", "person:candidate:bergonzoni-lino"),
)


def fixtures() -> tuple[dict[str, object], dict[str, object]]:
    items = []
    decisions = []
    for index, (name, candidate_id, suggested_id) in enumerate(CASES):
        items.append({"item_type": "CandidateNewProfile", "candidate_update_id": candidate_id, "candidate_value": name, "profile_id": "person:purocielo:source", "source_document_ids": [f"doc:{index}"], "source_urls": [f"https://example.test/{index}"], "context_quote": f"Contesto offline {name}", "run_id": "run:t34", "suggested_profile_id": suggested_id})
        decisions.append({"candidate_new_profile_id": candidate_id, "candidate_name": name, "suggested_profile_id": suggested_id, "decision": "accepted", "reviewer": "user-explicit", "reviewed_at": "2026-09-11T17:08:14Z"})
    return {"items": items}, {"decisions": decisions}


class T34bMaterializationPreflightTests(unittest.TestCase):
    def test_builds_the_four_required_preview_plans(self) -> None:
        queue, decisions = fixtures()
        output = build_t34b_materialization_preflight(queue_payload=queue, decision_set_block5f=decisions)
        plans = {plan["candidate"]["detected_name"]: plan for plan in output["plans"]}
        self.assertEqual(set(plans), {case[0] for case in CASES})
        self.assertTrue(output["preview_only"])
        self.assertFalse(output["canonical_profiles_modified"])
        self.assertEqual(plans["Marciatori Adriano"]["resolution"], "create_new")
        self.assertEqual(plans["Tacconi Rosa"]["resolution"], "create_new")
        self.assertEqual(plans["Bergonzoni Lino"]["resolution"], "create_new")
        self.assertEqual(plans["Saba Mario"]["target"]["existing_profile_id"], "person:purocielo:saba-mario")
        self.assertEqual(plans["Saba Mario"]["provenance"]["decision_json_pointer"], "/decisions/1")
        self.assertEqual(output["manifest"]["plan_count"], 4)
        self.assertEqual(output["manifest"]["plan_hashes"], [plan["plan_hash"] for plan in output["plans"]])
        self.assertEqual(
            output["manifest"]["plan_hashes"],
            build_t34b_materialization_preflight(queue_payload=queue, decision_set_block5f=decisions)["manifest"]["plan_hashes"],
        )

    def test_rejects_missing_decision_candidate_and_empty_source_arrays(self) -> None:
        queue, decisions = fixtures()
        missing = deepcopy(decisions)
        missing["decisions"] = missing["decisions"][:-1]
        with self.assertRaisesRegex(ValueError, "quattro accepted"):
            build_t34b_materialization_preflight(queue_payload=queue, decision_set_block5f=missing)
        absent_queue = deepcopy(queue)
        absent_queue["items"] = absent_queue["items"][1:]
        with self.assertRaisesRegex(ValueError, "Candidate ID non trovato"):
            build_t34b_materialization_preflight(queue_payload=absent_queue, decision_set_block5f=decisions)
        no_documents = deepcopy(queue)
        no_documents["items"][0]["source_document_ids"] = []
        with self.assertRaisesRegex(ValueError, "source_document_ids non puo' essere vuoto"):
            build_t34b_materialization_preflight(queue_payload=no_documents, decision_set_block5f=decisions)
        no_urls = deepcopy(queue)
        no_urls["items"][0]["source_urls"] = []
        with self.assertRaisesRegex(ValueError, "source_urls non puo' essere vuoto"):
            build_t34b_materialization_preflight(queue_payload=no_urls, decision_set_block5f=decisions)

    def test_rejects_incoherent_resolution(self) -> None:
        queue, decisions = fixtures()
        decisions["decisions"][1]["suggested_profile_id"] = "person:candidate:other"
        with self.assertRaisesRegex(ValueError, "Resolution incoerente"):
            build_t34b_materialization_preflight(queue_payload=queue, decision_set_block5f=decisions)


if __name__ == "__main__":
    unittest.main()
