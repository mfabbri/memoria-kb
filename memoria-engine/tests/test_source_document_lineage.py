from __future__ import annotations

import json
import sqlite3
import sys
import shutil
import uuid
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.source_document_lineage import build_source_document_lineage_preview


class SourceDocumentLineageTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("source-lineage-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.db = self.root / "catalog.sqlite"
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE source_documents (document_id TEXT PRIMARY KEY, title TEXT, url TEXT)")
            conn.executemany("INSERT INTO source_documents VALUES (?, ?, ?)", [("local:1", "Capture", ""), ("online:1", "Page", "https://example.test")])
        self.request = self.root / "request.json"

    def write_request(self, links):
        self.request.write_text(json.dumps({"@type": "SourceDocumentLineageRequest", "links": links}), encoding="utf-8")

    def link(self, target="online:1"):
        return {"source_document_id": "local:1", "related_source_document_id": target,
                "relation_type": "local_capture_of", "rationale": "Same explicitly reviewed page capture",
                "provenance_ref": "sidecar:sha256:abc"}

    def test_preview_is_explicit_unreviewed_and_catalog_is_unchanged(self):
        self.write_request([self.link()])
        before = self.db.read_bytes()
        report = build_source_document_lineage_preview(links_json=self.request, catalog_db=self.db, output_dir=self.root / "out")
        self.assertEqual(report["links"][0]["review_status"], "unreviewed")
        self.assertFalse(report["catalog_modified"])
        self.assertEqual(before, self.db.read_bytes())

    def test_missing_document_and_duplicate_link_fail_closed(self):
        self.write_request([self.link("missing")])
        with self.assertRaisesRegex(ValueError, "absent from catalog"):
            build_source_document_lineage_preview(links_json=self.request, catalog_db=self.db, output_dir=self.root / "out")
        self.write_request([self.link(), self.link()])
        with self.assertRaisesRegex(ValueError, "Duplicate lineage link"):
            build_source_document_lineage_preview(links_json=self.request, catalog_db=self.db, output_dir=self.root / "out")


if __name__ == "__main__":
    unittest.main()
