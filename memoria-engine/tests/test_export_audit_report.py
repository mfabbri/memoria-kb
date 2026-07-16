from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.export_audit_report import build_audit_report, write_audit_report
from caduti_fonti_report.models import PersonQuery, SearchRun, SourceDocument, SourceResult
from caduti_fonti_report.sqlite_store import SQLiteEvidenceStore


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


def populated_store(db_path: Path) -> SQLiteEvidenceStore:
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    run = SearchRun(
        run_id="meta:prova-cwgc",
        timestamp="2026-04-26T16:55:03+00:00",
        input_file="risultati/prova_meta_cwgc.json",
        source_ids=["cwgc"],
    )
    store.insert_search_run(run)
    store.insert_person_query(run.run_id, PersonQuery(full_name="Panov Sergio", given_name="Sergio", family_name="Panov"))
    store.insert_source_result(
        run.run_id,
        SourceResult(
            source_id="cwgc",
            source_name="CWGC",
            status="search_url_ready",
            note="URL pronti",
            query="Panov Sergio",
            search_url="https://example.test/cwgc",
        ),
    )
    store.insert_source_document(
        run.run_id,
        SourceDocument(
            document_id="cwgc-doc-1",
            source_id="cwgc",
            title="CWGC ricerca 1",
            url="https://example.test/cwgc/1",
            access_date="2026-04-26T16:55:03+00:00",
            media_type="text/uri-list",
            metadata={"access_mode": "reference_only"},
        ),
    )
    store.insert_source_document(
        run.run_id,
        SourceDocument(
            document_id="cwgc-doc-2",
            source_id="cwgc",
            title="CWGC ricerca 2",
            url="https://example.test/cwgc/2",
            access_date="2026-04-26T16:55:03+00:00",
            media_type="text/uri-list",
            metadata={"access_mode": "reference_only"},
        ),
    )
    return store


class ExportAuditReportTests(unittest.TestCase):
    def test_build_audit_report_renders_run_people_results_documents_and_manual_checks(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            populated_store(tmp_dir / "evidence.sqlite")
            markdown = build_audit_report(db_path=tmp_dir / "evidence.sqlite", run_id="meta:prova-cwgc")

        self.assertIn("# Audit run meta:prova-cwgc", markdown)
        self.assertIn("- Persone cercate: 1", markdown)
        self.assertIn("- Fonti interrogate: 1", markdown)
        self.assertIn("- Documenti registrati: 2", markdown)
        self.assertIn("- Evidenze estratte: 0", markdown)
        self.assertIn("- Panov Sergio", markdown)
        self.assertIn("### cwgc", markdown)
        self.assertIn("- Stato: `search_url_ready`", markdown)
        self.assertIn("cwgc-doc-1", markdown)
        self.assertIn("https://example.test/cwgc/1", markdown)
        self.assertIn("Nessuna EvidenceClaim estratta per questa run.", markdown)
        self.assertIn("verificare manualmente", markdown)

    def test_write_audit_report_creates_markdown_file(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            populated_store(tmp_dir / "evidence.sqlite")
            output_md = tmp_dir / "audit.md"
            markdown = write_audit_report(
                db_path=tmp_dir / "evidence.sqlite",
                run_id="meta:prova-cwgc",
                output_md_path=output_md,
            )
            file_text = output_md.read_text(encoding="utf-8")

        self.assertEqual(file_text, markdown)
        self.assertIn("# Audit run meta:prova-cwgc", file_text)

    def test_missing_run_raises_controlled_error_without_writing_file(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            SQLiteEvidenceStore(tmp_dir / "evidence.sqlite").init_schema()
            output_md = tmp_dir / "audit.md"

            with self.assertRaises(ValueError):
                write_audit_report(
                    db_path=tmp_dir / "evidence.sqlite",
                    run_id="missing-run",
                    output_md_path=output_md,
                )

            exists = output_md.exists()

        self.assertFalse(exists)


if __name__ == "__main__":
    unittest.main()
