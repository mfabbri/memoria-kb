from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.models import PersonQuery
from caduti_fonti_report.person_profiles import profile_from_person_query, profile_to_jsonld
from caduti_fonti_report.promote_profile_patch_preview import promote_profile_patch_preview


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


def write_profile_workspace(root: Path) -> Path:
    profiles_dir = root / "ricerche" / "person_profiles"
    profiles_dir.mkdir(parents=True)
    profile = profile_from_person_query(
        PersonQuery(
            full_name="Andreoli Dino",
            given_name="Dino",
            family_name="Andreoli",
            death_date="",
        ),
        seed_source="fixture",
        imported_at="2026-06-27T00:00:00+00:00",
    )
    profile_path = profiles_dir / "purocielo-andreoli-dino.jsonld"
    profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False, indent=2), encoding="utf-8")
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
    return profile_path


def write_patch_preview(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "@type": "ProfilePatchPreviewBatch",
                "preview_only": True,
                "profile_patches": [
                    {
                        "@type": "ProfilePatch",
                        "profile_id": "person:purocielo:andreoli-dino",
                        "review_status": "preview-only",
                        "apply_policy": "requires_explicit_apply_profile_patch_command",
                        "operations": [
                            {
                                "op": "set",
                                "path": "/death/date",
                                "value": "11 ottobre 1944",
                                "source_item_id": "claim:death-date",
                                "source_document_id": "doc:1",
                            },
                            {
                                "op": "add",
                                "path": "/verified_facts/death.cause",
                                "value": "Caduto",
                                "source_item_id": "claim:death-cause",
                                "source_document_id": "doc:2",
                            },
                        ],
                    },
                    {
                        "@type": "ProfilePatch",
                        "profile_id": "person:purocielo:balboni-william",
                        "operations": [],
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class PromoteProfilePatchPreviewTests(unittest.TestCase):
    def test_dry_run_selects_patch_resolves_profile_and_writes_audit_without_modifying_profile(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            workspace = tmp_dir / "workspace"
            profile_path = write_profile_workspace(workspace)
            original_payload = json.loads(profile_path.read_text(encoding="utf-8"))
            preview_path = tmp_dir / "profile_patch.preview.json"
            output_dir = tmp_dir / "promotion"
            write_patch_preview(preview_path)

            promotion = promote_profile_patch_preview(
                workspace_root=workspace,
                profile_patch_preview_json=preview_path,
                profile_id="person:purocielo:andreoli-dino",
                output_dir=output_dir,
            )
            current_payload = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertTrue(Path(promotion["selected_patch_json"]).exists())
            self.assertTrue(Path(promotion["audit_json"]).exists())
            self.assertTrue(Path(promotion["audit_md"]).exists())
            self.assertTrue(Path(promotion["summary_md"]).exists())

        self.assertEqual(promotion["status"], "dry-run")
        self.assertTrue(promotion["dry_run"])
        self.assertEqual(promotion["operation_count"], 2)
        self.assertEqual(promotion["applied_operations"], 2)
        self.assertEqual(current_payload, original_payload)

    def test_apply_requires_explicit_flag_and_writes_backup_and_profile(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            workspace = tmp_dir / "workspace"
            profile_path = write_profile_workspace(workspace)
            preview_path = tmp_dir / "profile_patch.preview.json"
            output_dir = tmp_dir / "promotion"
            write_patch_preview(preview_path)

            promotion = promote_profile_patch_preview(
                workspace_root=workspace,
                profile_patch_preview_json=preview_path,
                profile_id="person:purocielo:andreoli-dino",
                output_dir=output_dir,
                apply=True,
            )
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(len(list((output_dir / "backups").glob("*.backup.jsonld"))), 1)

        self.assertEqual(promotion["status"], "applied")
        self.assertFalse(promotion["dry_run"])
        self.assertEqual(payload["death"]["date"], "11 ottobre 1944")
        self.assertEqual(payload["verified_facts"]["death.cause"]["value"], "Caduto")

    def test_sandbox_writes_derived_profile_without_modifying_canonical_profile(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            workspace = tmp_dir / "workspace"
            profile_path = write_profile_workspace(workspace)
            original_payload = json.loads(profile_path.read_text(encoding="utf-8"))
            preview_path = tmp_dir / "profile_patch.preview.json"
            output_dir = tmp_dir / "promotion"
            write_patch_preview(preview_path)

            promotion = promote_profile_patch_preview(
                workspace_root=workspace,
                profile_patch_preview_json=preview_path,
                profile_id="person:purocielo:andreoli-dino",
                output_dir=output_dir,
                sandbox=True,
            )
            current_payload = json.loads(profile_path.read_text(encoding="utf-8"))
            sandbox_profile_path = Path(promotion["output_jsonld"])
            sandbox_payload = json.loads(sandbox_profile_path.read_text(encoding="utf-8"))

        self.assertEqual(promotion["status"], "sandbox")
        self.assertFalse(promotion["dry_run"])
        self.assertTrue(promotion["sandbox"])
        self.assertFalse(promotion["writes_canonical_profile"])
        self.assertEqual(current_payload, original_payload)
        self.assertEqual(sandbox_payload["death"]["date"], "11 ottobre 1944")
        self.assertEqual(sandbox_payload["verified_facts"]["death.cause"]["value"], "Caduto")

    def test_unknown_profile_patch_fails_readably(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            workspace = tmp_dir / "workspace"
            write_profile_workspace(workspace)
            preview_path = tmp_dir / "profile_patch.preview.json"
            write_patch_preview(preview_path)

            with self.assertRaisesRegex(ValueError, "Profilo non trovato"):
                promote_profile_patch_preview(
                    workspace_root=workspace,
                    profile_patch_preview_json=preview_path,
                    profile_id="person:purocielo:missing",
                    output_dir=tmp_dir / "promotion",
                )


if __name__ == "__main__":
    unittest.main()
