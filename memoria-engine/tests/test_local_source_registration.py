from __future__ import annotations

import hashlib
import json
import sys
import shutil
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.local_source_registration import register_local_source_document
from caduti_fonti_report.memoria_cli import main
from caduti_fonti_report.sqlite_store import SQLiteEvidenceStore


class LocalSourceRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("local-registration-" + __import__("uuid").uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.file = self.root / "sample.docx"
        self.file.write_bytes(b"synthetic file bytes")
        self.db = self.root / "evidence.sqlite"
        SQLiteEvidenceStore(self.db).init_schema()
        self.registry = self.root / "sources.yml"
        self.registry.write_text("enabled_sources:\n  - offline\n", encoding="utf-8")
        self.kw = dict(database_path=self.db, file_path=self.file, source_id="offline", title="Synthetic",
            access_date="2026-11-15", archival_reference="fixture", sources_registry=self.registry,
            timestamp="2026-11-15T00:00:00Z")

    def test_preview_apply_idempotence_and_provenance(self):
        original = self.file.read_bytes()
        preview = register_local_source_document(**self.kw)
        self.assertEqual(preview["status"], "would_register")
        with closing(SQLiteEvidenceStore(self.db).connect()) as c:
            self.assertEqual(c.execute("select count(*) from source_documents").fetchone()[0], 0)
        self.assertEqual(register_local_source_document(**self.kw, apply=True)["status"], "registered")
        self.assertEqual(register_local_source_document(**self.kw, apply=True)["status"], "already_registered")
        doc = preview["source_document"]
        self.assertEqual(doc["content_hash"], hashlib.sha256(original).hexdigest())
        self.assertEqual(doc["metadata"]["review_status"], "unreviewed")
        self.assertEqual(self.file.read_bytes(), original)
        with closing(SQLiteEvidenceStore(self.db).connect()) as c:
            self.assertEqual(c.execute("select count(*) from search_runs").fetchone()[0], 1)
            self.assertEqual(c.execute("select count(*) from evidence_claims").fetchone()[0], 0)

    def test_divergent_retry_and_unenabled_source_fail_closed(self):
        register_local_source_document(**self.kw, apply=True)
        with self.assertRaisesRegex(ValueError, "differs"):
            register_local_source_document(**{**self.kw, "title": "Changed"}, apply=True)
        with self.assertRaisesRegex(ValueError, "not enabled"):
            register_local_source_document(**{**self.kw, "source_id": "other"})

    def test_cli_preview_and_apply(self):
        command = ["documents", "register-local-source", "--database", str(self.db), "--file", str(self.file),
            "--source-id", "offline", "--title", "Synthetic", "--access-date", "2026-11-15",
            "--sources-registry", str(self.registry)]
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(main(command), 0)
        self.assertIn("would_register", out.getvalue())
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(main([*command, "--apply"]), 0)
        self.assertIn("registered", out.getvalue())


if __name__ == "__main__":
    unittest.main()
