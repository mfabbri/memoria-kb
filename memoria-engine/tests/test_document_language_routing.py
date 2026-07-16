from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.language_routing import (  # noqa: E402
    build_document_language_routing_plans,
    render_document_language_routing_markdown,
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


def assessment(
    *,
    source_document_id: str,
    primary_language: str,
    confidence: float = 0.82,
    secondary_languages: list[str] | None = None,
) -> dict[str, object]:
    return {
        "@type": "DocumentLanguageAssessment",
        "@id": f"document-language-assessment:document:{source_document_id.replace(':', '-')}",
        "source_id": "manual_uploads",
        "source_document_id": source_document_id,
        "text_file": f"manual_uploads/{source_document_id}.text.json",
        "scope": "document",
        "language_candidates": [{"language": primary_language, "confidence": confidence}],
        "primary_language": primary_language,
        "secondary_languages": secondary_languages or [],
        "is_multilingual": bool(secondary_languages),
        "script": "Latin",
        "confidence": confidence,
        "detection_method": "deterministic_marker_language_detection",
        "review_status": "unreviewed",
        "warnings": ["mixed_language_signals"] if secondary_languages else [],
    }


def write_assessment_set(path: Path, assessments: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "@type": "DocumentLanguageAssessmentSet",
                "assessment_count": len(assessments),
                "skipped_count": 0,
                "language_assessments": assessments,
                "skipped_documents": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class DocumentLanguageRoutingTests(unittest.TestCase):
    def test_builds_language_routing_for_supported_languages_without_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            language_json = tmp_dir / "language.json"
            output_dir = tmp_dir / "routing-sidecars"
            output_json = tmp_dir / "routing.json"
            output_md = tmp_dir / "routing.md"
            write_assessment_set(
                language_json,
                [
                    assessment(source_document_id="doc:it", primary_language="it"),
                    assessment(source_document_id="doc:de", primary_language="de"),
                    assessment(source_document_id="doc:en", primary_language="en"),
                ],
            )

            payload = build_document_language_routing_plans(
                language_dir=tmp_dir,
                language_json=language_json,
                output_dir=output_dir,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            sidecar_exists = any(output_dir.rglob("*.language-routing.json"))
            markdown = output_md.read_text(encoding="utf-8")

        by_doc = {plan["source_document_id"]: plan for plan in persisted["routing_plans"]}
        self.assertEqual(payload["@type"], "DocumentLanguageRoutingPlanSet")
        self.assertEqual(payload["routing_count"], 3)
        self.assertTrue(sidecar_exists)
        self.assertIn("DocumentLanguageRoutingPlan preview", markdown)
        self.assertEqual(by_doc["doc:it"]["recommended_ocr_languages"], ["ita"])
        self.assertIn("it_dates", by_doc["doc:it"]["recommended_rule_sets"])
        self.assertEqual(by_doc["doc:de"]["recommended_ocr_languages"], ["deu"])
        self.assertIn("de_archival_terms", by_doc["doc:de"]["recommended_rule_sets"])
        self.assertEqual(by_doc["doc:en"]["recommended_prompt_language"], "en")
        self.assertTrue(all(plan["review_status"] == "unreviewed" for plan in by_doc.values()))
        serialized = json.dumps(persisted)
        self.assertNotIn("EvidenceClaim", serialized)
        self.assertNotIn("ProfilePatch", serialized)
        self.assertNotIn("verified_facts", serialized)
        self.assertNotIn("CandidateTranslation", serialized)

    def test_multilingual_and_low_confidence_routes_require_review(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            language_json = tmp_dir / "language.json"
            write_assessment_set(
                language_json,
                [
                    assessment(
                        source_document_id="doc:mixed",
                        primary_language="it",
                        secondary_languages=["de"],
                        confidence=0.58,
                    ),
                    assessment(source_document_id="doc:uncertain", primary_language="und", confidence=0.2),
                ],
            )

            payload = build_document_language_routing_plans(language_dir=tmp_dir, language_json=language_json)

        by_doc = {plan["source_document_id"]: plan for plan in payload["routing_plans"]}
        mixed = by_doc["doc:mixed"]
        uncertain = by_doc["doc:uncertain"]
        self.assertTrue(mixed["manual_review_required"])
        self.assertEqual(mixed["recommended_ocr_languages"], ["ita", "deu"])
        self.assertIn("multilingual_routing_requires_review", mixed["warnings"])
        self.assertTrue(uncertain["manual_review_required"])
        self.assertEqual(uncertain["recommended_ocr_languages"], [])
        self.assertEqual(uncertain["recommended_prompt_language"], "manual_review_required")
        self.assertIn("language_undetermined_no_automatic_routing", uncertain["warnings"])
        self.assertIn("low_confidence_language_routing", uncertain["warnings"])

    def test_scans_language_sidecars_when_summary_json_is_not_given(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            language_dir = tmp_dir / "languages" / "manual_uploads"
            language_dir.mkdir(parents=True)
            (language_dir / "doc-de.language.json").write_text(
                json.dumps(assessment(source_document_id="doc:de", primary_language="de"), ensure_ascii=False),
                encoding="utf-8",
            )

            payload = build_document_language_routing_plans(language_dir=tmp_dir / "languages")

        self.assertEqual(payload["routing_count"], 1)
        self.assertEqual(payload["routing_plans"][0]["primary_language"], "de")

    def test_markdown_renderer_handles_empty_routing(self) -> None:
        markdown = render_document_language_routing_markdown(
            {
                "routing_method": "deterministic_language_routing_rules",
                "routing_count": 0,
                "skipped_count": 0,
                "routing_plans": [],
            }
        )

        self.assertIn("Nessun routing generato", markdown)


if __name__ == "__main__":
    unittest.main()
