from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from contextlib import closing
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.online_source_registration import register_online_source_document
from caduti_fonti_report.memoria_cli import main
from caduti_fonti_report.sqlite_store import SQLiteEvidenceStore


class OnlineSourceRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("online-registration-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.database = self.root / "evidence.sqlite"
        SQLiteEvidenceStore(self.database).init_schema()
        self.registry = self.root / "sources.yml"
        self.registry.write_text("enabled_sources:\n  - memorie_locali\n", encoding="utf-8")
        self.args = {"database_path": self.database, "source_id": "memorie_locali",
            "document_id": "doc:online:1", "title": "Purocielo source page",
            "url": "https://example.org/purocielo", "access_date": "2026-11-07",
            "sources_registry": self.registry, "timestamp": "2026-11-07T21:00:00Z"}

    def test_preview_is_read_only_and_registry_bound(self) -> None:
        report = register_online_source_document(**self.args)
        self.assertEqual(report["status"], "would_register")
        self.assertFalse(report["apply"])
        self.assertFalse(report["source_document"]["local_path"])
        with closing(SQLiteEvidenceStore(self.database).connect()) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0], 0)

    def test_apply_is_additive_and_identical_retry_is_idempotent(self) -> None:
        report = register_online_source_document(**self.args, apply=True)
        self.assertEqual(report["status"], "registered")
        retry = register_online_source_document(**self.args, apply=True)
        self.assertEqual(retry["status"], "already_registered")
        with closing(SQLiteEvidenceStore(self.database).connect()) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0], 1)

    def test_existing_id_with_different_metadata_is_never_overwritten(self) -> None:
        register_online_source_document(**self.args, apply=True)
        changed = {**self.args, "title": "Different title"}
        with self.assertRaisesRegex(ValueError, "refusing overwrite"):
            register_online_source_document(**changed, apply=True)
        with closing(SQLiteEvidenceStore(self.database).connect()) as connection:
            self.assertEqual(connection.execute("SELECT title FROM source_documents WHERE document_id='doc:online:1'").fetchone()[0],
                             "Purocielo source page")

    def test_title_correction_requires_exact_compare_and_swap_value(self) -> None:
        register_online_source_document(**self.args, apply=True)
        changed = {**self.args, "title": "Correct title"}
        with self.assertRaisesRegex(ValueError, "expected-existing-title"):
            register_online_source_document(**changed, apply=True)
        preview = register_online_source_document(
            **changed, expected_existing_title="Purocielo source page")
        self.assertEqual(preview["status"], "would_correct_title")
        result = register_online_source_document(
            **changed, expected_existing_title="Purocielo source page", apply=True)
        self.assertEqual(result["status"], "title_corrected")
        with closing(SQLiteEvidenceStore(self.database).connect()) as connection:
            self.assertEqual(connection.execute(
                "SELECT title FROM source_documents WHERE document_id='doc:online:1'").fetchone()[0],
                "Correct title")
            payload = connection.execute(
                "SELECT payload_json FROM source_documents WHERE document_id='doc:online:1'").fetchone()[0]
            self.assertEqual(__import__("json").loads(payload)["title"], "Correct title")

    def test_unenabled_source_and_non_https_url_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "not enabled"):
            register_online_source_document(**{**self.args, "source_id": "unknown"})
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            register_online_source_document(**{**self.args, "url": "http://example.org/purocielo"})

    def test_root_cli_preview_apply_and_repeat_use_no_json_input(self) -> None:
        command = ["documents", "register-online-source", "--database", str(self.database),
                   "--source-id", "memorie_locali", "--document-id", "doc:online:1",
                   "--title", "Purocielo source page", "--url", "https://example.org/purocielo",
                   "--access-date", "2026-11-07", "--sources-registry", str(self.registry)]
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main(command), 0)
        self.assertIn("would_register", output.getvalue())
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main([*command, "--apply"]), 0)
        self.assertIn("registered", output.getvalue())
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main([*command, "--apply"]), 0)
        self.assertIn("already_registered", output.getvalue())


if __name__ == "__main__":
    unittest.main()
