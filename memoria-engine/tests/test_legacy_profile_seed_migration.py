from __future__ import annotations

import json
import shutil
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from caduti_fonti_report import legacy_profile_seed_migration
from caduti_fonti_report.legacy_profile_seed_migration import migrate_legacy_profile_seeds


class LegacyProfileSeedMigrationTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        root = Path(__file__).parent / ".tmp-tests" / f"seed-migration-{uuid4().hex}"
        root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    @contextmanager
    def _temporary_workspace(self):
        root = Path(__file__).parent / ".tmp-tests" / f"seed-migration-{uuid4().hex}"
        root.mkdir(parents=True)
        try:
            yield str(root)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def _fixture(self, root: Path) -> tuple[Path, Path, dict[str, Path]]:
        profile_dir = root / "person_profiles"
        profile_dir.mkdir()
        paths: dict[str, Path] = {}
        entries = []
        for slug, source in (("one", r"ricerche\caduti_purocielo.csv"), ("two", "catalogue")):
            profile_id = f"person:test:{slug}"
            filename = f"{slug}.jsonld"
            path = profile_dir / filename
            payload = {
                "@type": "PersonResearchProfile",
                "@id": profile_id,
                "identity": {"canonical_name": slug},
                "seed": {"source": source, "source_id": slug, "imported_at": "2026-01-01", "payload": {"name": slug}},
                "verified_facts": [],
                "metadata": {"review_status": "unreviewed", "profile_status": "seed_profile"},
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            paths[profile_id] = path
            entries.append({"@id": profile_id, "file": filename})
        index_path = profile_dir / "index.jsonld"
        index_path.write_text(json.dumps({"profiles": entries}, indent=2) + "\n", encoding="utf-8")
        return profile_dir, index_path, paths

    def test_preview_is_read_only_and_emits_audit(self) -> None:
        with self._temporary_workspace() as tmp:
            root = Path(tmp)
            _, index, paths = self._fixture(root)
            before = paths["person:test:one"].read_bytes()
            audit = migrate_legacy_profile_seeds(
                profiles_index=index,
                output_dir=root / "run",
                expected_legacy_count=1,
            )
            self.assertEqual(audit["status"], "preview")
            self.assertEqual(audit["legacy_profile_count"], 1)
            self.assertEqual(paths["person:test:one"].read_bytes(), before)
            self.assertTrue((root / "run" / "profile-seed-migration.preview.json").is_file())
            self.assertFalse((root / "run" / "backups").exists())

    def test_apply_detaches_seed_source_and_payload_with_verified_backup(self) -> None:
        with self._temporary_workspace() as tmp:
            root = Path(tmp)
            _, index, paths = self._fixture(root)
            output = root / "run"
            original = paths["person:test:one"].read_bytes()
            audit = migrate_legacy_profile_seeds(
                profiles_index=index,
                output_dir=output,
                expected_legacy_count=1,
                apply=True,
            )
            changed = json.loads(paths["person:test:one"].read_text(encoding="utf-8"))
            unchanged = json.loads(paths["person:test:two"].read_text(encoding="utf-8"))
            self.assertEqual(audit["status"], "applied")
            self.assertEqual(audit["migrated_count"], 1)
            self.assertEqual(changed["seed"]["source"], "profile_seed_migration")
            self.assertEqual(changed["seed"]["payload"], {})
            self.assertTrue(changed["metadata"]["profile_seed_migration_id"].startswith("profile-seed-migration:"))
            self.assertEqual(changed["metadata"]["review_status"], "unreviewed")
            self.assertEqual(changed["metadata"]["profile_status"], "seed_profile")
            self.assertEqual(changed["verified_facts"], [])
            self.assertEqual(unchanged["seed"]["source"], "catalogue")
            backup_path = Path(audit["profiles"][0]["backup_path"])
            self.assertEqual(backup_path.read_bytes(), original)
            backup = json.loads(backup_path.read_text(encoding="utf-8"))
            self.assertEqual(backup["seed"]["source"], r"ricerche\caduti_purocielo.csv")
            rerun = migrate_legacy_profile_seeds(
                profiles_index=index,
                output_dir=output,
                expected_legacy_count=1,
            )
            self.assertEqual(rerun["status"], "already_applied")
            changed["identity"]["canonical_name"] = "changed after migration"
            paths["person:test:one"].write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "modificato dopo l'audit"):
                migrate_legacy_profile_seeds(
                    profiles_index=index,
                    output_dir=output,
                    expected_legacy_count=1,
                )

    def test_wrong_expected_count_fails_before_any_write(self) -> None:
        with self._temporary_workspace() as tmp:
            root = Path(tmp)
            _, index, paths = self._fixture(root)
            before = paths["person:test:one"].read_bytes()
            with self.assertRaisesRegex(ValueError, "Conteggio seed legacy"):
                migrate_legacy_profile_seeds(
                    profiles_index=index,
                    output_dir=root / "run",
                    expected_legacy_count=2,
                    apply=True,
                )
            self.assertEqual(paths["person:test:one"].read_bytes(), before)
            self.assertFalse((root / "run" / "backups").exists())

    def test_failed_multi_profile_apply_rolls_back_only_written_profiles(self) -> None:
        root = self._temp_root()
        _, index, paths = self._fixture(root)
        second_path = paths["person:test:two"]
        second_payload = json.loads(second_path.read_text(encoding="utf-8"))
        second_payload["seed"]["source"] = r"ricerche\caduti_purocielo.csv"
        second_path.write_text(json.dumps(second_payload, indent=2) + "\n", encoding="utf-8")
        original_one = paths["person:test:one"].read_bytes()
        original_two = second_path.read_bytes()
        real_atomic_write = legacy_profile_seed_migration._atomic_write
        calls = 0

        def fail_second_write(path: Path, content: bytes) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("fixture write failure")
            real_atomic_write(path, content)

        with patch("caduti_fonti_report.legacy_profile_seed_migration._atomic_write", side_effect=fail_second_write):
            with self.assertRaisesRegex(OSError, "fixture write failure"):
                migrate_legacy_profile_seeds(
                    profiles_index=index,
                    output_dir=root / "run",
                    expected_legacy_count=2,
                    apply=True,
                )
        self.assertEqual(paths["person:test:one"].read_bytes(), original_one)
        self.assertEqual(second_path.read_bytes(), original_two)
        audit = json.loads((root / "run" / "profile-seed-migration.audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["status"], "rolled_back_after_error")


if __name__ == "__main__":
    unittest.main()
