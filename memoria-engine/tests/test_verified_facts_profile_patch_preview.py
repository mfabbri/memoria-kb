from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.verified_facts_profile_patch_preview import (  # noqa: E402
    build_verified_facts_profile_patch_preview,
    render_verified_facts_profile_patch_preview_markdown,
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


def write_preview(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "@type": "VerifiedFactsPreview",
                "review_status": "preview-only",
                "preview_only": True,
                "facts": [
                    {
                        "@type": "VerifiedFactPreview",
                        "fact_id": "verified-fact-preview:andreoli:death-date",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "field": "death.date",
                        "value": "11 ottobre 1944",
                        "source_document_id": "source-document:doc-1",
                        "source_run_id": "mvp-run-pipeline",
                        "source_decision_record_id": "evidence-record:decision-1",
                        "source_item_id": "candidate-evidence-claim:1",
                        "item_id": "mvp-review-item:1",
                        "reviewer": "storico-test",
                        "reviewed_at": "2026-06-21",
                        "provenance": [
                            "historical_review_decision_record_id=evidence-record:decision-1",
                            "source_document_id=source-document:doc-1",
                        ],
                    },
                    {
                        "@type": "VerifiedFactPreview",
                        "fact_id": "verified-fact-preview:andreoli:formation",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "field": "formation.name",
                        "value": "36a Brigata Garibaldi",
                        "source_document_id": "source-document:doc-2",
                        "source_run_id": "mvp-run-pipeline",
                        "source_decision_record_id": "evidence-record:decision-2",
                        "reviewer": "storico-test",
                        "reviewed_at": "2026-06-21",
                        "provenance": ["payload_hash=hash-2"],
                    },
                    {
                        "@type": "VerifiedFactPreview",
                        "fact_id": "verified-fact-preview:balboni:death-cause",
                        "profile_id": "person:purocielo:balboni-william",
                        "field": "death.cause",
                        "value": "Caduto in combattimento",
                        "source_document_id": "source-document:doc-3",
                        "source_run_id": "mvp-run-pipeline",
                        "source_decision_record_id": "evidence-record:decision-3",
                        "reviewer": "storico-test",
                        "reviewed_at": "2026-06-21",
                        "provenance": ["payload_hash=hash-3"],
                    },
                    {
                        "@type": "VerifiedFactPreview",
                        "fact_id": "verified-fact-preview:incomplete",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "field": "death.place",
                        "value": "",
                        "source_document_id": "source-document:doc-4",
                        "source_decision_record_id": "evidence-record:decision-4",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class VerifiedFactsProfilePatchPreviewTests(unittest.TestCase):
    def test_builds_profile_patch_preview_batch_without_applying_profiles(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            preview_json = tmp_dir / "verified_facts.preview.json"
            output_json = tmp_dir / "profile_patch.preview.json"
            output_md = tmp_dir / "profile_patch.preview.md"
            write_preview(preview_json)

            payload = build_verified_facts_profile_patch_preview(
                verified_facts_preview_json=preview_json,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["@type"], "ProfilePatchPreviewBatch")
        self.assertTrue(payload["preview_only"])
        self.assertEqual(payload["apply_policy"], "requires_explicit_apply_profile_patch_command")
        self.assertEqual(payload["patch_count"], 2)
        self.assertEqual(payload["operation_count"], 3)
        self.assertEqual(payload["skipped_fact_count"], 1)
        self.assertEqual(persisted["operation_count"], 3)
        patches_by_profile = {patch["profile_id"]: patch for patch in payload["profile_patches"]}
        andreoli_ops = patches_by_profile["person:purocielo:andreoli-dino"]["operations"]
        self.assertEqual(andreoli_ops[0]["path"], "/death/date")
        self.assertEqual(andreoli_ops[0]["op"], "set")
        self.assertEqual(andreoli_ops[0]["source_decision_record_id"], "evidence-record:decision-1")
        self.assertEqual(andreoli_ops[1]["path"], "/formations/-")
        self.assertEqual(andreoli_ops[1]["op"], "add")
        balboni_ops = patches_by_profile["person:purocielo:balboni-william"]["operations"]
        self.assertEqual(balboni_ops[0]["path"], "/verified_facts/death.cause")
        self.assertEqual(balboni_ops[0]["op"], "add")
        self.assertIn("campo_mancante:value", serialized)
        self.assertIn("preview-only", markdown)
        self.assertIn("Non applica ProfilePatch", markdown)
        self.assertNotIn('"profile_source_file": "P:', serialized)

    def test_filters_patch_preview_by_profile_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            preview_json = tmp_dir / "verified_facts.preview.json"
            write_preview(preview_json)

            payload = build_verified_facts_profile_patch_preview(
                verified_facts_preview_json=preview_json,
                profile_id=["person:purocielo:balboni-william"],
            )

        self.assertEqual(payload["profile_ids"], ["person:purocielo:balboni-william"])
        self.assertEqual(payload["patch_count"], 1)
        self.assertEqual(payload["operation_count"], 1)
        self.assertEqual(payload["profile_patches"][0]["profile_id"], "person:purocielo:balboni-william")

    def test_skipped_verified_facts_preview_produces_empty_batch(self) -> None:
        payload = {
            "type": "verified_facts_preview",
            "status": "skipped",
            "reason": "skip_evidence_import",
        }

        markdown = render_verified_facts_profile_patch_preview_markdown(
            {
                "@type": "ProfilePatchPreviewBatch",
                "review_status": "preview-only",
                "publication_status": "not_publishable_without_editorial_review",
                "preview_only": True,
                "apply_policy": "requires_explicit_apply_profile_patch_command",
                "patch_count": 0,
                "operation_count": 0,
                "skipped_fact_count": 0,
                "source_verified_facts_preview": "verified_facts.preview.json",
                "profile_patches": [],
                "skipped_facts": [],
            }
        )
        with workspace_temp_dir() as tmp_dir:
            preview_json = tmp_dir / "verified_facts.preview.json"
            preview_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            built = build_verified_facts_profile_patch_preview(verified_facts_preview_json=preview_json)

        self.assertEqual(built["patch_count"], 0)
        self.assertEqual(built["operation_count"], 0)
        self.assertIn("Nessuna patch preview generata", markdown)


if __name__ == "__main__":
    unittest.main()
