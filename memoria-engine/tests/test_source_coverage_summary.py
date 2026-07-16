from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.source_coverage_summary import build_source_coverage_summary  # noqa: E402


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


def write_profiles_report(path: Path) -> Path:
    payload = {
        "generated_at": "2026-06-01T10:00:00+00:00",
        "input_mode": "person_profiles_jsonld",
        "profiles": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "results": [
                    {
                        "result": {
                            "source_id": "partigiani_italia",
                            "source_name": "I Partigiani d'Italia",
                            "status": "candidate_results",
                            "query": "Andreoli Dino",
                            "search_url": "https://example.test/cerca",
                            "hits": [
                                {"title": "Andreoli, Dino", "url": "https://example.test/persona/1"},
                                {"title": "Andreoli, Dino", "url": "https://example.test/persona/2"},
                            ],
                        },
                        "documents": [
                            {
                                "document_id": "partigiani:doc:1",
                                "source_id": "partigiani_italia",
                                "title": "Andreoli, Dino",
                                "url": "https://example.test/persona/1",
                                "metadata": {
                                    "access_mode": "detail_page",
                                    "detail_assessment": "detail_document_fetched",
                                },
                            }
                        ],
                        "claims": [
                            {
                                "claim_id": "claim:1",
                                "source_document_id": "partigiani:doc:1",
                                "review_status": "unreviewed",
                            }
                        ],
                        "matched_planned_attempt_status": "matched",
                        "matched_planned_attempt_id": "cognome-nome-contains",
                    }
                ],
            },
            {
                "profile_id": "person:purocielo:guazzaloca-laura",
                "canonical_name": "Guazzaloca Laura",
                "results": [
                    {
                        "result": {
                            "source_id": "partigiani_italia",
                            "source_name": "I Partigiani d'Italia",
                            "status": "no_results",
                            "query": "Guazzaloca Laura",
                            "search_url": "https://example.test/cerca",
                            "hits": [],
                        },
                        "documents": [
                            {
                                "document_id": "partigiani:search:1",
                                "source_id": "partigiani_italia",
                                "url": "https://example.test/cerca",
                                "metadata": {"source_result_status": "no_results"},
                            }
                        ],
                        "claims": [],
                    }
                ],
            },
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class SourceCoverageSummaryTests(unittest.TestCase):
    def test_builds_source_and_profile_coverage_summary(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            report_path = write_profiles_report(tmp_dir / "profiles_report.json")
            output_json = tmp_dir / "source_coverage_summary.json"
            output_md = tmp_dir / "source_coverage_summary.md"

            summary = build_source_coverage_summary(
                input_json=[report_path],
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(persisted, ensure_ascii=False)

        self.assertEqual(summary["@type"], "SourceCoverageSummary")
        self.assertEqual(persisted["profile_count"], 2)
        self.assertEqual(persisted["source_count"], 1)
        self.assertEqual(persisted["entry_count"], 2)
        self.assertEqual(persisted["sources"][0]["candidate_profile_count"], 1)
        self.assertEqual(persisted["sources"][0]["detail_profile_count"], 1)
        self.assertEqual(persisted["sources"][0]["no_results_profile_count"], 1)
        self.assertEqual(persisted["profiles"][0]["recommended_action"], "review_detail_documents")
        self.assertEqual(persisted["profiles"][1]["recommended_action"], "try_other_sources_or_queries")
        self.assertIn("Source coverage summary", markdown)
        self.assertIn("Andreoli Dino", markdown)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("ProfilePatch", serialized)

    def test_merges_multiple_reports_without_live_source_access(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            report_a = write_profiles_report(tmp_dir / "profiles_report_a.json")
            report_b = write_profiles_report(tmp_dir / "profiles_report_b.json")

            summary = build_source_coverage_summary(input_json=[report_a, report_b])

        self.assertEqual(summary["report_count"], 2)
        self.assertEqual(summary["entry_count"], 4)
        self.assertEqual(summary["sources"][0]["hit_count"], 4)
        self.assertEqual(summary["sources"][0]["claim_count"], 2)

    def test_empty_or_invalid_report_is_handled_as_empty_summary(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            report_path = tmp_dir / "invalid.json"
            report_path.write_text("[]", encoding="utf-8")

            summary = build_source_coverage_summary(input_json=[report_path])

        self.assertEqual(summary["report_count"], 1)
        self.assertEqual(summary["entry_count"], 0)
        self.assertEqual(summary["sources"], [])
        self.assertEqual(summary["profiles"], [])


if __name__ == "__main__":
    unittest.main()
