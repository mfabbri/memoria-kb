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

from caduti_fonti_report.document_analysis.feedback_search_plan import (  # noqa: E402
    _repo_root_from_sources_yaml,
    build_feedback_search_plan,
    render_feedback_search_plan_markdown,
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


def write_profile_index(root_dir: Path) -> Path:
    profiles_dir = root_dir / "profiles"
    profiles_dir.mkdir()
    profile = {
        "@type": "PersonResearchProfile",
        "@id": "person:purocielo:andreoli-dino",
        "profile_id": "person:purocielo:andreoli-dino",
        "identity": {
            "canonical_name": "Andreoli Dino",
            "given_name": "Dino",
            "family_name": "Andreoli",
            "aliases": [],
            "name_forms": ["Andreoli Dino"],
        },
        "seed": {"source": "test", "source_id": "", "imported_at": "", "payload": {}},
        "birth": {},
        "death": {},
        "formations": [],
        "events": [],
        "places": [],
        "search_hints": [],
        "evidence_claim_ids": [],
        "verified_facts": {},
        "conflicts": [],
        "searched_sources": [],
        "next_research": [],
        "metadata": {"profile_source_file": str(profiles_dir / "purocielo-andreoli-dino.jsonld")},
    }
    (profiles_dir / "purocielo-andreoli-dino.jsonld").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_path.write_text(
        json.dumps(
            {
                "@type": "PersonResearchProfileIndex",
                "profiles": [
                    {
                        "@id": "person:purocielo:andreoli-dino",
                        "file": "purocielo-andreoli-dino.jsonld",
                        "canonical_name": "Andreoli Dino",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return index_path


def write_actions_json(root_dir: Path, *, person_id: str, suggested_sources: list[str] | None = None) -> Path:
    action = {
        "@type": "ResearchFeedbackAction",
        "@id": "research-feedback-action:abc",
        "action_id": "research-feedback-action:abc",
        "action_kind": "request_source_specific_search",
        "source_candidate_id": "document-mention-candidate:person-andreoli",
        "supporting_candidate_ids": ["document-mention-candidate:place-purocielo"],
        "person_id": person_id,
        "value": "Andreoli Dino",
        "source_id": "manual_uploads",
        "source_document_id": "doc:signals",
        "chunk_id": "physical-document-chunk:1",
        "weak_segment_id": "weak-document-segment:1",
        "suggested_search_hints": [
            {"field": "person_name", "value": "Andreoli Dino", "source": "person_mention_candidate"},
            {"field": "place", "value": "Purocielo", "source": "place_mention_candidate"},
        ],
        "suggested_sources": suggested_sources or ["partigiani_italia"],
        "review_status": "unreviewed",
    }
    payload = {
        "@type": "ResearchFeedbackActionSet",
        "document_count": 1,
        "action_count": 1,
        "documents": [
            {
                "@type": "ResearchFeedbackActionDocument",
                "source_id": "manual_uploads",
                "source_document_id": "doc:signals",
                "review_status": "unreviewed",
                "action_count": 1,
                "actions": [action],
            }
        ],
    }
    path = root_dir / "research_feedback_actions.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_links_json(root_dir: Path, *, links: list[dict[str, object]] | None = None) -> Path:
    payload = {
        "@type": "CandidateDocumentPersonLinkSet",
        "link_count": len(links or []),
        "skipped_count": 0,
        "candidate_document_person_links": links
        or [
            {
                "@type": "CandidateDocumentPersonLink",
                "@id": "candidate-document-person-link:andreoli",
                "profile_id": "person:purocielo:andreoli-dino",
                "profile_source_file": "profiles/purocielo-andreoli-dino.jsonld",
                "canonical_name": "Andreoli Dino",
                "matched_name": "Andreoli Dino",
                "match_kind": "canonical_name",
                "source_id": "manual_uploads",
                "source_document_id": "doc:signals",
                "score": 1.0,
                "reasons": ["exact_canonical_name_match"],
                "review_status": "unreviewed",
            }
        ],
    }
    path = root_dir / "candidate_document_person_links.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class FeedbackSearchPlanTests(unittest.TestCase):
    def test_modular_registry_path_resolves_workspace_root(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root = tmp_dir / "workspace"
            registry = root / "memoria-sources" / "registry" / "camalanca_fonti.yaml"
            registry.parent.mkdir(parents=True)
            registry.write_text("enabled_sources: []\nsources: []\n", encoding="utf-8")
            self.assertEqual(_repo_root_from_sources_yaml(registry), root.resolve())

    def test_installed_launcher_connects_actions_plan_review_outcome_and_evaluation(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
            if not launcher.is_file():
                self.skipTest("Installed memoria launcher is not available in this environment.")
            mentions_dir = tmp_dir / "mentions"
            mentions_dir.mkdir()
            mentions_file = mentions_dir / "signals.mentions.json"
            mentions_file.write_text(json.dumps({
                "@type": "DocumentMentionCandidateDocument",
                "source_id": "manual_uploads",
                "source_document_id": "doc:signals",
                "review_status": "unreviewed",
                "mentions": [
                    {"mention_id": "mention:person:andreoli", "mention_kind": "person",
                     "value": "Andreoli Dino", "normalized_value": "andreoli dino",
                     "source_id": "manual_uploads", "source_document_id": "doc:signals",
                     "chunk_id": "chunk:1", "weak_segment_id": "segment:1",
                     "context": "Andreoli Dino a Purocielo", "confidence": 0.7,
                     "candidate_profile_id": "", "review_status": "unreviewed"},
                    {"mention_id": "mention:place:purocielo", "mention_kind": "place",
                     "value": "Purocielo", "normalized_value": "purocielo",
                     "source_id": "manual_uploads", "source_document_id": "doc:signals",
                     "chunk_id": "chunk:1", "weak_segment_id": "segment:1",
                     "context": "Andreoli Dino a Purocielo", "confidence": 0.7,
                     "candidate_profile_id": "", "review_status": "unreviewed"},
                ],
            }, ensure_ascii=False), encoding="utf-8")
            actions_json = tmp_dir / "actions.json"
            profiles_index = write_profile_index(tmp_dir)
            links_json = write_links_json(tmp_dir)
            plan_json = tmp_dir / "plan.json"
            triage_md = tmp_dir / "triage.md"
            review_summary_json = tmp_dir / "review-summary.json"
            review_summary_md = tmp_dir / "review-summary.md"
            outcome_json = tmp_dir / "outcome.json"
            evaluation_json = tmp_dir / "evaluation.json"
            sources_yaml = Path(__file__).resolve().parents[1] / "ricerche" / "camalanca_fonti.yaml"
            protected_inputs = (mentions_file, profiles_index, links_json, sources_yaml)
            before = {path: path.read_bytes() for path in protected_inputs}

            generated = subprocess.run(
                [str(launcher), "feedback", "actions", "--mentions-dir", str(mentions_dir),
                 "--output-json", str(actions_json)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)
            planned = subprocess.run(
                [str(launcher), "feedback", "plan", "--actions-json", str(actions_json),
                 "--links-json", str(links_json), "--profiles-index", str(profiles_index),
                 "--sources-yaml", str(sources_yaml), "--output-json", str(plan_json)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(planned.returncode, 0, planned.stderr)
            triaged = subprocess.run(
                [str(launcher), "feedback", "triage", "build-table", "--actions-json", str(actions_json),
                 "--output-md", str(triage_md)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(triaged.returncode, 0, triaged.stderr)

            table_lines = triage_md.read_text(encoding="utf-8").splitlines()
            reviewed_lines = []
            for line in table_lines:
                if line.startswith("|") and "research-feedback-action:" in line:
                    cells = line.strip("|").split("|")
                    cells[0] = " BUONA "
                    cells[8] = " reviewer:synthetic-test "
                    cells[9] = " 2026-11-08T09:00:00+00:00 "
                    cells[10] = " 2026-11-08T09:01:00+00:00 "
                    line = "|" + "|".join(cells) + "|"
                reviewed_lines.append(line)
            triage_md.write_text("\n".join(reviewed_lines) + "\n", encoding="utf-8")
            summarized = subprocess.run(
                [str(launcher), "feedback", "triage", "summarize-table", "--actions-json", str(actions_json),
                 "--review-table-md", str(triage_md), "--output-json", str(review_summary_json),
                 "--output-md", str(review_summary_md)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(summarized.returncode, 0, summarized.stderr)

            actions = json.loads(actions_json.read_text(encoding="utf-8"))
            plan = json.loads(plan_json.read_text(encoding="utf-8"))
            triage = triage_md.read_text(encoding="utf-8")
            review_summary = json.loads(review_summary_json.read_text(encoding="utf-8"))
            action_id = actions["documents"][0]["actions"][0]["action_id"]
            plan_entry = plan["plans"][0]
            source_plan = plan_entry["source_plans"][0]
            attempt = source_plan["planned_attempts"][0]
            strategy_id = attempt.get("strategy_id") or attempt.get("attempt_id")
            outcome_result = subprocess.run(
                [str(launcher), "feedback", "outcome", "--feedback-plan-json", str(plan_json),
                 "--review-summary-json", str(review_summary_json), "--action-id", action_id,
                 "--plan-id", plan_entry["feedback_search_plan_id"], "--source-id", source_plan["source_id"],
                 "--strategy-id", strategy_id, "--outcome-status", "no_results", "--query", "synthetic test query",
                 "--run-id", "run:synthetic-test", "--executed-at", "2026-11-08T09:02:00+00:00",
                 "--output-json", str(outcome_json)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(outcome_result.returncode, 0, outcome_result.stderr)
            evaluated = subprocess.run(
                [str(launcher), "feedback", "evaluate", "--feedback-plan-json", str(plan_json),
                 "--outcome-json", str(outcome_json), "--review-summary-json", str(review_summary_json),
                 "--output-json", str(evaluation_json)], capture_output=True, text=True, check=False,
            )
            self.assertEqual(evaluated.returncode, 0, evaluated.stderr)
            outcome = json.loads(outcome_json.read_text(encoding="utf-8"))
            evaluation = json.loads(evaluation_json.read_text(encoding="utf-8"))
            after = {path: path.read_bytes() for path in protected_inputs}

        self.assertIn(action_id, triage)
        self.assertEqual(plan["plan_count"], 1)
        self.assertEqual(plan["plans"][0]["action_id"], action_id)
        self.assertEqual(plan["plans"][0]["status"], "ready_for_review")
        self.assertEqual(plan["review_status"], "unreviewed")
        self.assertFalse(plan["execution_allowed"])
        self.assertFalse(plan["online_search_started"])
        self.assertEqual(review_summary["actions_sha256"], plan["actions_sha256"])
        self.assertEqual(outcome["review_action_set_provenance"], "matched")
        self.assertTrue(outcome["approved_for_demo"])
        self.assertEqual(evaluation["metrics"]["review_latency_seconds"]["value"], 60.0)
        self.assertTrue(evaluation["audit_only"])
        self.assertFalse(evaluation["profile_write_allowed"])
        self.assertFalse(evaluation["claim_promotion_allowed"])
        self.assertEqual(before, after)

    def test_installed_launcher_builds_review_only_plan_set(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            actions_json = write_actions_json(tmp_dir, person_id="person:purocielo:andreoli-dino")
            output_json, output_md = tmp_dir / "plan.json", tmp_dir / "plan.md"
            sources_yaml = Path(__file__).resolve().parents[1] / "ricerche" / "camalanca_fonti.yaml"
            launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
            if not launcher.is_file():
                self.skipTest("Installed memoria launcher is not available in this environment.")
            before = {path: path.read_bytes() for path in (profiles_index, actions_json, sources_yaml)}
            completed = subprocess.run(
                [str(launcher), "feedback", "plan", "--actions-json", str(actions_json),
                 "--profiles-index", str(profiles_index), "--sources-yaml", str(sources_yaml),
                 "--output-json", str(output_json), "--output-md", str(output_md)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(report["@type"], "FeedbackSearchPlanSet")
            self.assertEqual(report["actions_sha256"], hashlib.sha256(actions_json.read_bytes()).hexdigest())
            self.assertEqual(report["review_status"], "unreviewed")
            self.assertFalse(report["execution_allowed"])
            self.assertFalse(report["online_search_started"])
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_builds_preview_plan_from_resolved_profile_and_registered_source(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            actions_json = write_actions_json(tmp_dir, person_id="person:purocielo:andreoli-dino")
            output_json = tmp_dir / "feedback_search_plan.json"
            output_md = tmp_dir / "feedback_search_plan.md"

            payload = build_feedback_search_plan(
                actions_json=actions_json,
                profiles_index=profiles_index,
                sources_yaml=Path(__file__).resolve().parents[1] / "ricerche" / "camalanca_fonti.yaml",
                output_json=output_json,
                output_md=output_md,
            )
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        plan = payload["plans"][0]
        source_plan = plan["source_plans"][0]
        self.assertEqual(payload["@type"], "FeedbackSearchPlanSet")
        self.assertEqual(payload["plan_count"], 1)
        self.assertEqual(payload["review_status"], "unreviewed")
        self.assertFalse(payload["execution_allowed"])
        self.assertFalse(payload["online_search_started"])
        self.assertEqual(plan["@type"], "FeedbackSearchPlan")
        self.assertEqual(plan["status"], "ready_for_review")
        self.assertTrue(plan["manual_review_required"])
        self.assertFalse(plan["profile_write_allowed"])
        self.assertEqual(plan["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(source_plan["source_id"], "partigiani_italia")
        self.assertEqual(source_plan["status"], "planned")
        self.assertGreaterEqual(source_plan["planned_attempt_count"], 1)
        self.assertIn("identity.family_name", source_plan["planned_attempts"][0]["used_profile_fields"])
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("ProfilePatch", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_resolves_missing_person_id_from_unique_candidate_document_person_link(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            actions_json = write_actions_json(tmp_dir, person_id="")
            links_json = write_links_json(tmp_dir)

            payload = build_feedback_search_plan(
                actions_json=actions_json,
                links_json=links_json,
                profiles_index=profiles_index,
                sources_yaml=Path(__file__).resolve().parents[1] / "ricerche" / "camalanca_fonti.yaml",
            )

        plan = payload["plans"][0]
        self.assertEqual(payload["skipped_count"], 0)
        self.assertEqual(plan["status"], "ready_for_review")
        self.assertEqual(plan["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(plan["profile_resolution"]["status"], "resolved")
        self.assertEqual(plan["profile_resolution"]["candidate_link_id"], "candidate-document-person-link:andreoli")
        self.assertEqual(plan["source_plans"][0]["status"], "planned")
        self.assertFalse(plan["online_search_started"])
        self.assertFalse(plan["profile_write_allowed"])
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("ProfilePatch", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_missing_person_id_requires_manual_profile_resolution(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            actions_json = write_actions_json(tmp_dir, person_id="")

            payload = build_feedback_search_plan(
                actions_json=actions_json,
                profiles_index=profiles_index,
                sources_yaml=Path(__file__).resolve().parents[1] / "ricerche" / "camalanca_fonti.yaml",
            )

        plan = payload["plans"][0]
        self.assertEqual(plan["status"], "skipped")
        self.assertEqual(plan["reason"], "manual_profile_resolution_required")
        self.assertEqual(plan["source_plans"], [])
        self.assertIn("missing_person_id_no_profile_lookup", plan["warnings"])
        self.assertEqual(payload["skipped_count"], 1)
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_ambiguous_candidate_document_person_links_keep_manual_resolution(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            actions_json = write_actions_json(tmp_dir, person_id="")
            links_json = write_links_json(
                tmp_dir,
                links=[
                    {
                        "@id": "candidate-document-person-link:one",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "matched_name": "Andreoli Dino",
                        "source_document_id": "doc:signals",
                        "review_status": "unreviewed",
                    },
                    {
                        "@id": "candidate-document-person-link:two",
                        "profile_id": "person:purocielo:guazzaloca-laura",
                        "matched_name": "Andreoli Dino",
                        "source_document_id": "doc:signals",
                        "review_status": "unreviewed",
                    },
                ],
            )

            payload = build_feedback_search_plan(
                actions_json=actions_json,
                links_json=links_json,
                profiles_index=profiles_index,
                sources_yaml=Path(__file__).resolve().parents[1] / "ricerche" / "camalanca_fonti.yaml",
            )

        plan = payload["plans"][0]
        self.assertEqual(plan["status"], "skipped")
        self.assertEqual(plan["reason"], "manual_profile_resolution_required")
        self.assertEqual(plan["profile_resolution"]["status"], "ambiguous")
        self.assertEqual(plan["source_plans"], [])

    def test_unregistered_source_is_a_reviewable_skip(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            actions_json = write_actions_json(
                tmp_dir,
                person_id="person:purocielo:andreoli-dino",
                suggested_sources=["fonte_non_censita"],
            )

            payload = build_feedback_search_plan(
                actions_json=actions_json,
                profiles_index=profiles_index,
                sources_yaml=Path(__file__).resolve().parents[1] / "ricerche" / "camalanca_fonti.yaml",
            )

        source_plan = payload["plans"][0]["source_plans"][0]
        self.assertEqual(payload["plans"][0]["status"], "skipped")
        self.assertEqual(source_plan["status"], "skipped")
        self.assertEqual(source_plan["reason"], "source_not_registered")
        self.assertEqual(source_plan["planned_attempts"], [])

    def test_markdown_renderer_lists_plan_for_review(self) -> None:
        markdown = render_feedback_search_plan_markdown(
            {
                "generation_method": "deterministic_feedback_search_plan_preview",
                "plan_count": 1,
                "skipped_count": 0,
                "review_status": "unreviewed",
                "online_search_started": False,
                "plans": [
                    {
                        "action_id": "research-feedback-action:abc",
                        "status": "ready_for_review",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "person_name": "Andreoli Dino",
                        "manual_review_required": True,
                        "reason": "planned_sources_require_review",
                        "source_plans": [
                            {
                                "source_id": "partigiani_italia",
                                "status": "planned",
                                "planned_attempt_count": 3,
                            }
                        ],
                    }
                ],
            }
        )

        self.assertIn("# FeedbackSearchPlan preview", markdown)
        self.assertIn("research-feedback-action:abc", markdown)
        self.assertIn("partigiani_italia", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
