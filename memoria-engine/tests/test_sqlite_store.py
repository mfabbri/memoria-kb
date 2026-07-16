from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import closing
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.import_person_queries_to_db import import_person_queries_export
from caduti_fonti_report.models import EvidenceClaim, HistoricalEvent, PersonQuery, Place, SearchRun, SourceDocument, SourceResult
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


class SQLiteStoreTests(unittest.TestCase):
    def test_init_schema_creates_expected_tables(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = SQLiteEvidenceStore(tmp_dir / "evidence.sqlite")
            store.init_schema()

            with closing(store.connect()) as connection:
                table_rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()

        table_names = {row["name"] for row in table_rows}
        self.assertIn("search_runs", table_names)
        self.assertIn("person_queries", table_names)
        self.assertIn("source_results", table_names)
        self.assertIn("source_documents", table_names)
        self.assertIn("evidence_claims", table_names)
        self.assertIn("events", table_names)
        self.assertIn("places", table_names)
        self.assertIn("evidence_import_batches", table_names)
        self.assertIn("evidence_records", table_names)

    def test_insert_core_records(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = SQLiteEvidenceStore(tmp_dir / "evidence.sqlite")
            store.init_schema()
            run = SearchRun(
                run_id="run:test",
                timestamp="2026-04-26T12:00:00+00:00",
                input_file="ricerche/caduti_purocielo.csv",
                source_ids=["partigiani_italia"],
                parameters={"limit": "1"},
            )
            person_query = PersonQuery(full_name="Panov Sergio", given_name="Sergio", family_name="Panov")
            source_result = SourceResult(
                source_id="partigiani_italia",
                source_name="Partigiani d'Italia",
                status="no_results",
                note="Nessun risultato",
                query="Panov Sergio",
                search_url="https://example.test/search?q=Panov+Sergio",
            )
            document = SourceDocument(
                document_id="doc-1",
                source_id="partigiani_italia",
                title="Risultato online",
                url="https://example.test/doc",
                access_date="2026-04-26T12:00:00+00:00",
                local_path="data/raw/partigiani/doc/content.txt",
                content_hash="abc123",
            )
            claim = EvidenceClaim(
                claim_id="claim-1",
                subject_id="Panov Sergio",
                field="status",
                value="no_results",
                source_document_id="doc-1",
                review_status="unreviewed",
            )
            event = HistoricalEvent(
                event_id="event:battaglia-purocielo",
                event_type="battle",
                label="Battaglia di Purocielo",
                review_status="draft",
                place_labels=["Purocielo"],
                place_ids=["place:purocielo"],
                provenance="fixture:test",
            )
            place = Place(
                place_id="place:purocielo",
                preferred_label="Purocielo",
                place_type="locality",
                alternate_labels=["Puro Cielo"],
                review_status="draft",
                provenance="fixture:test",
            )

            store.insert_search_run(run)
            store.insert_person_query(run.run_id, person_query)
            store.insert_source_result(run.run_id, source_result)
            store.insert_source_document(run.run_id, document)
            store.insert_evidence_claim(run.run_id, claim)
            store.insert_event(event)
            store.insert_place(place)

            person_rows = store.fetch_all("person_queries")
            document_rows = store.fetch_all("source_documents")
            event_rows = store.fetch_events()
            place_rows = store.fetch_places()
            counts = {
                "search_runs": store.count("search_runs"),
                "person_queries": store.count("person_queries"),
                "source_results": store.count("source_results"),
                "source_documents": store.count("source_documents"),
                "evidence_claims": store.count("evidence_claims"),
                "events": store.count("events"),
                "places": store.count("places"),
                "evidence_import_batches": store.count("evidence_import_batches"),
                "evidence_records": store.count("evidence_records"),
            }

        self.assertEqual(counts["search_runs"], 1)
        self.assertEqual(counts["person_queries"], 1)
        self.assertEqual(counts["source_results"], 1)
        self.assertEqual(counts["source_documents"], 1)
        self.assertEqual(counts["evidence_claims"], 1)
        self.assertEqual(counts["events"], 1)
        self.assertEqual(counts["places"], 1)
        self.assertEqual(counts["evidence_import_batches"], 0)
        self.assertEqual(counts["evidence_records"], 0)
        self.assertEqual(person_rows[0]["full_name"], "Panov Sergio")
        self.assertEqual(document_rows[0]["document_id"], "doc-1")
        self.assertEqual(event_rows[0]["event_id"], "event:battaglia-purocielo")
        self.assertEqual(event_rows[0]["review_status"], "draft")
        self.assertIn("place:purocielo", event_rows[0]["payload_json"])
        self.assertEqual(place_rows[0]["place_id"], "place:purocielo")
        self.assertEqual(place_rows[0]["review_status"], "draft")
        self.assertIn("fixture:test", event_rows[0]["payload_json"])
        self.assertIn("fixture:test", place_rows[0]["payload_json"])

    def test_import_person_queries_export_writes_run_and_queries(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            input_json = tmp_dir / "person_queries.json"
            input_json.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-26T12:00:00+00:00",
                        "input_file": "ricerche/caduti_purocielo.csv",
                        "count": 2,
                        "person_queries": [
                            {"full_name": "Panov Sergio", "given_name": "Sergio", "family_name": "Panov"},
                            {"full_name": "Andreoli Dino", "given_name": "Dino", "family_name": "Andreoli"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            db_path = tmp_dir / "evidence.sqlite"

            result = import_person_queries_export(
                input_json_path=input_json,
                db_path=db_path,
                run_id="run:import-test",
            )
            store = SQLiteEvidenceStore(db_path)
            run_count = store.count("search_runs")
            person_query_count = store.count("person_queries")

        self.assertEqual(result["run_id"], "run:import-test")
        self.assertEqual(result["person_queries"], 2)
        self.assertEqual(run_count, 1)
        self.assertEqual(person_query_count, 2)

    def test_rejects_unknown_table_names_in_helpers(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = SQLiteEvidenceStore(tmp_dir / "evidence.sqlite")
            store.init_schema()

            with self.assertRaises(ValueError):
                store.count("not_a_table")

    def test_insert_evidence_import_records_is_append_only_and_idempotent(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = SQLiteEvidenceStore(tmp_dir / "evidence.sqlite")
            store.init_schema()
            batch = {
                "import_batch_id": "evidence-import:test",
                "source_run_id": "run:test",
                "imported_at": "2026-06-13T10:00:00+00:00",
                "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/run-test",
                "record_count": 1,
                "payload_hash": "hash-batch",
            }
            record = {
                "record_id": "evidence-record:test",
                "import_batch_id": "evidence-import:test",
                "source_run_id": "run:test",
                "record_kind": "candidate_evidence_claim",
                "subject_id": "person:purocielo:test",
                "source_document_id": "source-document:test",
                "review_status": "unreviewed",
                "payload_hash": "hash-record",
                "payload": {"@type": "CandidateEvidenceClaim"},
            }

            store.insert_evidence_import_batch(batch)
            first_insert = store.insert_evidence_record(record)
            second_insert = store.insert_evidence_record(record)
            batch_count = store.count("evidence_import_batches")
            record_count = store.count("evidence_records")

        self.assertTrue(first_insert)
        self.assertFalse(second_insert)
        self.assertEqual(batch_count, 1)
        self.assertEqual(record_count, 1)


if __name__ == "__main__":
    unittest.main()
