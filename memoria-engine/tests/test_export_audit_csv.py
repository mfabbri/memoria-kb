from __future__ import annotations

import csv
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.export_audit_csv import export_audit_csv
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class ExportAuditCsvTests(unittest.TestCase):
    def test_export_audit_csv_writes_all_files_with_expected_rows(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            populated_store(tmp_dir / "evidence.sqlite")
            output_dir = tmp_dir / "csv"

            result = export_audit_csv(
                db_path=tmp_dir / "evidence.sqlite",
                run_id="meta:prova-cwgc",
                output_dir=output_dir,
            )
            search_runs = read_csv(output_dir / "search_runs.csv")
            person_queries = read_csv(output_dir / "person_queries.csv")
            source_results = read_csv(output_dir / "source_results.csv")
            source_documents = read_csv(output_dir / "source_documents.csv")
            evidence_claims = read_csv(output_dir / "evidence_claims.csv")
            manual_review = read_csv(output_dir / "manual_review.csv")

        self.assertEqual(result["files"]["search_runs.csv"], 1)
        self.assertEqual(len(search_runs), 1)
        self.assertEqual(search_runs[0]["run_id"], "meta:prova-cwgc")
        self.assertEqual(len(person_queries), 1)
        self.assertEqual(person_queries[0]["full_name"], "Panov Sergio")
        self.assertEqual(len(source_results), 1)
        self.assertEqual(source_results[0]["status"], "search_url_ready")
        self.assertEqual(len(source_documents), 2)
        self.assertEqual(source_documents[0]["url"], "https://example.test/cwgc/1")
        self.assertEqual(evidence_claims, [])
        self.assertEqual(len(manual_review), 1)
        self.assertEqual(manual_review[0]["source_id"], "cwgc")
        self.assertIn("verifica manuale", manual_review[0]["reason"])

    def test_export_audit_csv_creates_empty_claims_file_with_header(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            populated_store(tmp_dir / "evidence.sqlite")
            output_dir = tmp_dir / "csv"

            export_audit_csv(
                db_path=tmp_dir / "evidence.sqlite",
                run_id="meta:prova-cwgc",
                output_dir=output_dir,
            )
            header = (output_dir / "evidence_claims.csv").read_text(encoding="utf-8").splitlines()[0]

        self.assertEqual(header, "claim_id,run_id,subject_id,field,value,source_document_id,review_status")

    def test_missing_run_raises_controlled_error_without_creating_output_dir(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            SQLiteEvidenceStore(tmp_dir / "evidence.sqlite").init_schema()
            output_dir = tmp_dir / "csv"

            with self.assertRaises(ValueError):
                export_audit_csv(
                    db_path=tmp_dir / "evidence.sqlite",
                    run_id="missing-run",
                    output_dir=output_dir,
                )

            exists = output_dir.exists()

        self.assertFalse(exists)


if __name__ == "__main__":
    unittest.main()
