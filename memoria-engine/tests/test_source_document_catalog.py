from __future__ import annotations

import sqlite3
import sys
import shutil
import unittest
from contextlib import closing
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.source_document_catalog import resolve_source_documents


class SourceDocumentCatalogTests(unittest.TestCase):
    def test_resolves_ids_and_reports_stable_catalog_fingerprint(self) -> None:
        path = self._catalog_path()
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE source_documents (document_id TEXT PRIMARY KEY, payload_json TEXT)")
            connection.executemany("INSERT INTO source_documents VALUES (?, '{}')", [("doc:1",), ("doc:2",)])
            connection.commit()
        before = path.read_bytes()
        first = resolve_source_documents(path, {"doc:2", "doc:1"})
        second = resolve_source_documents(path, {"doc:1", "doc:2"})
        self.assertEqual(first, second)
        self.assertEqual(first["resolved_document_ids"], ["doc:1", "doc:2"])
        self.assertEqual(path.read_bytes(), before)

    def test_fails_closed_for_missing_ids_and_incompatible_catalog(self) -> None:
        path = self._catalog_path()
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE source_documents (document_id TEXT PRIMARY KEY)")
            connection.commit()
        with self.assertRaisesRegex(ValueError, "absent from catalog"):
            resolve_source_documents(path, {"doc:missing"})
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("DROP TABLE source_documents")
            connection.execute("CREATE TABLE unrelated (id TEXT)")
            connection.commit()
        with self.assertRaisesRegex(ValueError, "lacks source_documents"):
            resolve_source_documents(path, set())

    def test_does_not_create_missing_catalog(self) -> None:
        directory = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("catalog-test-" + uuid.uuid4().hex)
        directory.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        path = directory / "missing.sqlite"
        with self.assertRaisesRegex(ValueError, "existing SQLite"):
            resolve_source_documents(path, set())
        self.assertFalse(path.exists())

    def _catalog_path(self) -> Path:
        directory = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("catalog-test-" + uuid.uuid4().hex)
        directory.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        return directory / "catalog.sqlite"


if __name__ == "__main__":
    unittest.main()
