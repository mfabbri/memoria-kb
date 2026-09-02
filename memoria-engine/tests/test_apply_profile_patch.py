from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.apply_profile_patch import apply_profile_patch
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


def write_profile_fixture(path: Path, *, death_date: str = "novembre 1944") -> None:
    profile = profile_from_person_query(
        PersonQuery(
            full_name="Guazzaloca Laura",
            given_name="Laura",
            family_name="Guazzaloca",
            death_date=death_date,
            formation="infermiera partigiana",
        ),
        seed_source="fixture.csv",
        imported_at="2026-05-09T10:00:00+00:00",
    )
    path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False, indent=2), encoding="utf-8")


def write_patch(path: Path, operations: list[dict[str, object]], *, profile_id: str = "person:purocielo:guazzaloca-laura") -> None:
    path.write_text(
        json.dumps(
            {
                "@type": "ProfilePatch",
                "profile_id": profile_id,
                "apply_policy": "requires_explicit_apply_profile_patch_command",
                "operations": operations,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def apply_fixture(tmp_dir: Path, *, operations: list[dict[str, object]], dry_run: bool = False):
    profile_path = tmp_dir / "profile.jsonld"
    patch_path = tmp_dir / "patch.json"
    output_path = tmp_dir / "profile.jsonld"
    audit_json = tmp_dir / "audit.json"
    audit_md = tmp_dir / "audit.md"
    backup_dir = tmp_dir / "backups"
    write_profile_fixture(profile_path)
    original_payload = json.loads(profile_path.read_text(encoding="utf-8"))
    write_patch(patch_path, operations)
    audit = apply_profile_patch(
        profile_jsonld=profile_path,
        patch_json=patch_path,
        output_jsonld=output_path,
        audit_json=audit_json,
        audit_md=audit_md,
        backup_dir=backup_dir,
        dry_run=dry_run,
    )
    return profile_path, original_payload, audit, audit_json, audit_md, backup_dir


class ApplyProfilePatchTests(unittest.TestCase):
    def test_applies_accepted_patch_and_preserves_claim_document_review_and_provenance(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path, _original, audit, audit_json, audit_md, backup_dir = apply_fixture(
                tmp_dir,
                operations=[
                    {
                        "op": "add",
                        "path": "/verified_facts/death.cause",
                        "value": "Esecuzione",
                        "candidate_update_id": "candidate-profile-update:accepted",
                        "source_claim_ids": ["claim:1"],
                        "source_document_ids": ["doc:1"],
                    }
                ],
            )
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertTrue(audit_json.exists())
            self.assertTrue(audit_md.exists())
            self.assertEqual(len(list(backup_dir.glob("*.backup.jsonld"))), 1)

        fact = payload["verified_facts"]["death.cause"]
        self.assertEqual(fact["value"], "Esecuzione")
        self.assertEqual(fact["source_claim_ids"], ["claim:1"])
        self.assertEqual(fact["source_document_ids"], ["doc:1"])
        self.assertEqual(fact["review_status"], "reviewed")
        self.assertEqual(fact["provenance"], "ProfilePatch:candidate-profile-update:accepted")
        self.assertEqual(payload["evidence_claim_ids"], ["claim:1"])
        self.assertTrue(audit["changed"])

    def test_rejected_operation_is_not_applied(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path, _original, audit, _audit_json, _audit_md, backup_dir = apply_fixture(
                tmp_dir,
                operations=[
                    {
                        "op": "add",
                        "path": "/verified_facts/death.cause",
                        "value": "Esecuzione",
                        "decision": "rejected",
                        "source_claim_ids": ["claim:1"],
                        "source_document_ids": ["doc:1"],
                    }
                ],
            )
            payload = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertNotIn("death.cause", payload["verified_facts"])
        self.assertFalse(audit["changed"])
        self.assertEqual(len(audit["skipped_operations"]), 1)
        self.assertEqual(list(backup_dir.glob("*.backup.jsonld")), [])

    def test_dry_run_writes_audit_but_does_not_modify_profile_or_create_backup(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path, original_payload, audit, audit_json, audit_md, backup_dir = apply_fixture(
                tmp_dir,
                operations=[
                    {
                        "op": "add",
                        "path": "/verified_facts/occupation",
                        "value": "Maestra",
                        "source_claim_ids": ["claim:2"],
                        "source_document_ids": ["doc:2"],
                    }
                ],
                dry_run=True,
            )
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertTrue(audit_json.exists())
            self.assertTrue(audit_md.exists())
            self.assertEqual(list(backup_dir.glob("*.backup.jsonld")), [])

        self.assertEqual(payload, original_payload)
        self.assertTrue(audit["changed"])
        self.assertTrue(audit["dry_run"])

    def test_conflicting_structural_patch_records_conflict_without_overwriting(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path, _original, audit, _audit_json, _audit_md, _backup_dir = apply_fixture(
                tmp_dir,
                operations=[
                    {
                        "op": "set",
                        "path": "/death/date",
                        "value": "23 novembre 1944",
                        "candidate_update_id": "candidate-profile-update:date",
                        "source_claim_ids": ["claim:3"],
                        "source_document_ids": ["doc:3"],
                    }
                ],
            )
            payload = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["death"]["date"], "novembre 1944")
        self.assertEqual(len(payload["conflicts"]), 1)
        self.assertEqual(payload["conflicts"][0]["review_status"], "needs_review")
        self.assertEqual(payload["conflicts"][0]["source_document_ids"], ["doc:3"])
        self.assertEqual(len(audit["conflict_operations"]), 1)

    def test_explicit_replace_structural_patch_overwrites_after_review(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path, _original, audit, _audit_json, _audit_md, _backup_dir = apply_fixture(
                tmp_dir,
                operations=[
                    {
                        "op": "replace",
                        "path": "/death/date",
                        "value": "13 ottobre 1944",
                        "candidate_update_id": "candidate-profile-update:date",
                        "source_claim_ids": ["claim:date"],
                        "source_document_ids": ["doc:date"],
                    }
                ],
            )
            payload = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["death"]["date"], "13 ottobre 1944")
        self.assertEqual(audit["applied_operations"][0]["reason"], "structural_value_replaced_after_explicit_review")
        self.assertEqual(audit["conflict_operations"], [])

    def test_unreviewed_claim_cannot_be_promoted_without_source_document(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path, _original, audit, _audit_json, _audit_md, _backup_dir = apply_fixture(
                tmp_dir,
                operations=[
                    {
                        "op": "add",
                        "path": "/verified_facts/death.cause",
                        "value": "Esecuzione",
                        "source_claim_ids": ["claim:unreviewed"],
                        "source_document_ids": [],
                    }
                ],
            )
            payload = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertNotIn("death.cause", payload["verified_facts"])
        self.assertEqual(audit["skipped_operations"][0]["reason"], "verified_fact_requires_claims_and_documents")

    def test_appends_allowed_review_lists_and_search_hint_with_provenance(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path, _original, audit, _audit_json, _audit_md, _backup_dir = apply_fixture(
                tmp_dir,
                operations=[
                    {"op": "add", "path": "/evidence_claim_ids/-", "value": "claim:4"},
                    {"op": "add", "path": "/searched_sources/-", "value": "storia_memoria_bo"},
                    {"op": "add", "path": "/next_research/-", "value": "Verificare documento originale"},
                    {
                        "op": "add",
                        "path": "/search_hints/-",
                        "value": {
                            "hint_id": "hint:reviewed:name",
                            "source_id": "review",
                            "field": "identity.alias",
                            "value": "Laura Guazzaloca",
                            "provenance": "ProfilePatch:candidate-profile-update:name",
                        },
                    },
                ],
            )
            payload = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertIn("claim:4", payload["evidence_claim_ids"])
        self.assertIn("storia_memoria_bo", payload["searched_sources"])
        self.assertIn("Verificare documento originale", payload["next_research"])
        self.assertEqual(payload["search_hints"][-1]["review_status"], "unreviewed")
        self.assertEqual(len(audit["applied_operations"]), 4)

    def test_appends_reviewed_formation(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path, _original, audit, _audit_json, _audit_md, backup_dir = apply_fixture(
                tmp_dir,
                operations=[
                    {
                        "op": "add",
                        "path": "/formations/-",
                        "value": "36ª Brigata Bianconcini Garibaldi",
                        "candidate_update_id": "candidate-profile-update:formation",
                        "source_claim_ids": ["claim:formation"],
                        "source_document_ids": ["doc:formation"],
                    }
                ],
            )
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(len(list(backup_dir.glob("*.backup.jsonld"))), 1)

        self.assertIn("36ª Brigata Bianconcini Garibaldi", payload["formations"])
        self.assertEqual(len(audit["applied_operations"]), 1)

    def test_missing_profile_fails_readably(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            patch_path = tmp_dir / "patch.json"
            write_patch(patch_path, [])

            with self.assertRaisesRegex(FileNotFoundError, "Profilo non trovato"):
                apply_profile_patch(
                    profile_jsonld=tmp_dir / "missing.jsonld",
                    patch_json=patch_path,
                    output_jsonld=tmp_dir / "out.jsonld",
                    audit_json=tmp_dir / "audit.json",
                    audit_md=tmp_dir / "audit.md",
                )

    def test_invalid_patch_fails_readably(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profile_path = tmp_dir / "profile.jsonld"
            patch_path = tmp_dir / "patch.json"
            write_profile_fixture(profile_path)
            patch_path.write_text(json.dumps({"@type": "NotProfilePatch"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Patch non valida"):
                apply_profile_patch(
                    profile_jsonld=profile_path,
                    patch_json=patch_path,
                    output_jsonld=profile_path,
                    audit_json=tmp_dir / "audit.json",
                    audit_md=tmp_dir / "audit.md",
                )


if __name__ == "__main__":
    unittest.main()
