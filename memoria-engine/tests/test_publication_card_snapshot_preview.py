from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.publication_card_snapshot_preview import (  # noqa: E402
    build_publication_card_snapshot_preview,
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


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_model_cards_fixture(tmp_dir: Path) -> tuple[Path, Path]:
    model_dir = tmp_dir / "schede_modello"
    model_dir.mkdir()
    card_path = model_dir / "andreoli-dino.md"
    card_text = "\n".join(
        [
            "---",
            "type: mvp_model_card",
            "profile_id: \"person:purocielo:andreoli-dino\"",
            "---",
            "",
            "# Andreoli Dino",
            "",
            "Bozza di revisione - non pubblicabile senza validazione storica.",
            "",
        ]
    )
    card_path.write_text(card_text, encoding="utf-8")
    manifest = {
        "@type": "MvpModelCardsBuild",
        "cards": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "model_card_path": str(card_path),
                "model_card_review_status": "in_historical_review",
            },
            {
                "profile_id": "person:purocielo:balboni-william",
                "canonical_name": "Balboni William",
                "model_card_path": str(model_dir / "missing.md"),
                "model_card_review_status": "candidate_model_card",
            },
        ],
    }
    manifest_path = write_json(model_dir / "manifest.json", manifest)
    return manifest_path, card_path


def write_dataset_export_preview(path: Path) -> Path:
    return write_json(
        path,
        {
            "@type": "DatasetExportPreview",
            "review_status": "preview-only",
            "publication_status": "not_publishable_without_editorial_review",
            "preview_only": True,
            "persons": [
                {
                    "profile_id": "person:purocielo:andreoli-dino",
                    "source_document_ids": ["source-document:doc-1"],
                    "provenance": [
                        {
                            "record_id": "evidence-record:claim-1",
                            "source_run_id": "mvp-run-pipeline",
                            "source_document_id": "source-document:doc-1",
                            "payload_hash": "record-hash-1",
                        }
                    ],
                }
            ],
            "source_documents": [
                {
                    "source_document_id": "source-document:doc-1",
                    "profile_ids": ["person:purocielo:andreoli-dino"],
                    "provenance": [
                        {
                            "record_id": "evidence-record:claim-1",
                            "source_run_id": "mvp-run-pipeline",
                            "source_document_id": "source-document:doc-1",
                            "payload_hash": "record-hash-1",
                        }
                    ],
                }
            ],
            "review_decisions": [
                {
                    "record_id": "evidence-record:historical-decision-1",
                    "source_run_id": "mvp-run-pipeline",
                    "profile_id": "person:purocielo:andreoli-dino",
                    "source_document_id": "source-document:doc-1",
                    "selected_action": "confirm",
                    "decision_status": "approved",
                    "payload_hash": "record-hash-2",
                }
            ],
            "verified_facts_preview": {
                "facts": [
                    {
                        "@type": "VerifiedFactPreview",
                        "fact_id": "verified-fact-preview:andreoli:death-place",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "field": "death.place",
                        "value": "Purocielo",
                        "source_document_id": "source-document:doc-1",
                        "source_run_id": "mvp-run-pipeline",
                        "source_decision_record_id": "evidence-record:historical-decision-1",
                    }
                ]
            },
            "profile_patch_preview": {
                "profile_patches": [
                    {
                        "@type": "ProfilePatch",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "operations": [
                            {
                                "op": "set",
                                "path": "/death/place",
                                "value": "Purocielo",
                                "source_decision_record_id": "evidence-record:historical-decision-1",
                            }
                        ],
                    }
                ]
            },
        },
    )


class PublicationCardSnapshotPreviewTests(unittest.TestCase):
    def test_builds_snapshot_preview_with_dataset_provenance(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            manifest_path, card_path = write_model_cards_fixture(tmp_dir)
            dataset_path = write_dataset_export_preview(tmp_dir / "dataset_export.preview.json")
            source_text_before = card_path.read_text(encoding="utf-8")

            manifest = build_publication_card_snapshot_preview(
                model_cards_manifest_json=manifest_path,
                dataset_export_preview_json=dataset_path,
                output_dir=tmp_dir / "publication_card_snapshots_preview",
            )
            source_text_after = card_path.read_text(encoding="utf-8")
            output_dir = Path(manifest["output_dir"])
            snapshot_json = output_dir / "andreoli-dino.snapshot.json"
            snapshot_md = output_dir / "andreoli-dino.snapshot.md"
            readme_exists = (output_dir / "README.md").is_file()
            manifest_exists = (output_dir / "manifest.json").is_file()
            snapshot = json.loads(snapshot_json.read_text(encoding="utf-8"))
            markdown = snapshot_md.read_text(encoding="utf-8")

        self.assertEqual(source_text_before, source_text_after)
        self.assertEqual(manifest["@type"], "PublicationCardSnapshotPreviewIndex")
        self.assertEqual(manifest["snapshot_count"], 1)
        self.assertEqual(manifest["skipped_card_count"], 1)
        self.assertEqual(manifest["skipped_cards"][0]["reason"], "model_card_missing")
        self.assertTrue(readme_exists)
        self.assertTrue(manifest_exists)
        self.assertEqual(snapshot["@type"], "PublicationCardSnapshotPreview")
        self.assertTrue(snapshot["preview_only"])
        self.assertEqual(snapshot["publication_status"], "not_publishable_without_editorial_review")
        self.assertEqual(snapshot["dataset_profile"]["dataset_profile_status"], "available")
        self.assertEqual(snapshot["dataset_profile"]["source_document_ids"], ["source-document:doc-1"])
        self.assertEqual(snapshot["dataset_profile"]["review_decisions"][0]["record_id"], "evidence-record:historical-decision-1")
        self.assertEqual(snapshot["dataset_profile"]["review_decisions"][0]["payload_hash"], "record-hash-2")
        self.assertEqual(snapshot["dataset_profile"]["verified_facts_preview"][0]["source_run_id"], "mvp-run-pipeline")
        self.assertIn("source_model_card_sha256", snapshot)
        self.assertIn("source_dataset_export_sha256", snapshot)
        self.assertIn("Snapshot tecnico preview-only", markdown)
        self.assertIn("Non e' una scheda pubblicabile", markdown)
        self.assertIn("evidence-record:historical-decision-1", markdown)
        self.assertIn("Bozza di revisione", markdown)

    def test_profile_filter_limits_snapshots_and_skips(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            manifest_path, _card_path = write_model_cards_fixture(tmp_dir)
            dataset_path = write_dataset_export_preview(tmp_dir / "dataset_export.preview.json")

            manifest = build_publication_card_snapshot_preview(
                model_cards_manifest_json=manifest_path,
                dataset_export_preview_json=dataset_path,
                output_dir=tmp_dir / "snapshots",
                profile_id=["person:purocielo:andreoli-dino"],
            )

        self.assertEqual(manifest["snapshot_count"], 1)
        self.assertEqual(manifest["skipped_card_count"], 0)
        self.assertEqual(manifest["snapshots"][0]["profile_id"], "person:purocielo:andreoli-dino")

    def test_missing_dataset_profile_is_explicit(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            manifest_path, _card_path = write_model_cards_fixture(tmp_dir)
            dataset_path = write_json(
                tmp_dir / "dataset_export.preview.json",
                {"@type": "DatasetExportPreview", "persons": [], "source_documents": [], "review_decisions": []},
            )

            manifest = build_publication_card_snapshot_preview(
                model_cards_manifest_json=manifest_path,
                dataset_export_preview_json=dataset_path,
                output_dir=tmp_dir / "snapshots",
                profile_id=["person:purocielo:andreoli-dino"],
            )
            snapshot = json.loads(Path(manifest["snapshots"][0]["snapshot_json_path"]).read_text(encoding="utf-8"))

        self.assertEqual(snapshot["dataset_profile"]["dataset_profile_status"], "missing")
        self.assertEqual(snapshot["dataset_profile"]["review_decisions"], [])


if __name__ == "__main__":
    unittest.main()
