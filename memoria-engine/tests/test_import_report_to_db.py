from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.import_report_to_db import import_report_to_db
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


def report_payload(*, hits: list[dict[str, str]]) -> dict[str, object]:
    return {
        "generated_at": "2026-04-26T12:00:00+00:00",
        "source_selection": {
            "source_file": "ricerche/camalanca_fonti.yaml",
            "selected_source_ids": ["partigiani_italia"],
            "unresolved_source_ids": [],
            "used_fallback": False,
        },
        "caduti": [
            {
                "caduto": {
                    "intestazione_pdf": "PANOV SERGIO",
                    "nome": "Panov Sergio",
                    "origine_sulla_lapide": "U.R.S.S.",
                    "nascita": "non reperito",
                    "morte": "non reperito",
                    "ruolo_affiliazione": "partigiano sovietico",
                    "fonti_richiamate": "MEMO",
                    "profilo_biografico": "Profilo di prova",
                    "episodio_documentato": "Episodio di prova",
                },
                "results": [
                    {
                        "source_id": "partigiani_italia",
                        "source_name": "I Partigiani d'Italia",
                        "status": "no_results" if not hits else "ok",
                        "note": "Nota di prova",
                        "query": "Panov Sergio",
                        "search_url": "https://example.test/cerca?nome=Sergio&cognome=Panov",
                        "hits": hits,
                    }
                ],
            }
        ],
    }


class ImportReportToDbTests(unittest.TestCase):
    def test_import_report_with_no_hits_writes_run_query_and_result_only(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            input_json = tmp_dir / "report.json"
            input_json.write_text(json.dumps(report_payload(hits=[])), encoding="utf-8")
            db_path = tmp_dir / "evidence.sqlite"

            result = import_report_to_db(input_json_path=input_json, db_path=db_path, run_id="run:report-test")
            store = SQLiteEvidenceStore(db_path)
            source_rows = store.fetch_all("source_results")
            counts = {
                "search_runs": store.count("search_runs"),
                "person_queries": store.count("person_queries"),
                "source_results": store.count("source_results"),
                "source_documents": store.count("source_documents"),
                "evidence_claims": store.count("evidence_claims"),
            }

        self.assertEqual(result["run_id"], "run:report-test")
        self.assertEqual(result["person_queries"], 1)
        self.assertEqual(result["source_results"], 1)
        self.assertEqual(result["source_documents"], 0)
        self.assertEqual(counts["search_runs"], 1)
        self.assertEqual(counts["person_queries"], 1)
        self.assertEqual(counts["source_results"], 1)
        self.assertEqual(counts["source_documents"], 0)
        self.assertEqual(counts["evidence_claims"], 0)
        self.assertEqual(source_rows[0]["source_id"], "partigiani_italia")
        self.assertEqual(source_rows[0]["status"], "no_results")
        self.assertEqual(source_rows[0]["query"], "Panov Sergio")

    def test_import_report_with_hits_creates_reference_documents(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            input_json = tmp_dir / "report.json"
            input_json.write_text(
                json.dumps(
                    report_payload(
                        hits=[
                            {
                                "title": "Scheda Panov Sergio",
                                "url": "https://example.test/scheda/panov-sergio",
                                "snippet": "Panov Sergio nella lista risultati",
                                "content": "",
                            }
                        ]
                    )
                ),
                encoding="utf-8",
            )
            db_path = tmp_dir / "evidence.sqlite"

            result = import_report_to_db(input_json_path=input_json, db_path=db_path, run_id="run:report-hit-test")
            store = SQLiteEvidenceStore(db_path)
            document_rows = store.fetch_all("source_documents")
            source_document_count = store.count("source_documents")
            document_payload = json.loads(document_rows[0]["payload_json"])

        self.assertEqual(result["source_documents"], 1)
        self.assertEqual(source_document_count, 1)
        self.assertEqual(document_rows[0]["source_id"], "partigiani_italia")
        self.assertEqual(document_rows[0]["url"], "https://example.test/scheda/panov-sergio")
        self.assertEqual(document_payload["metadata"]["access_mode"], "reference_only")
        self.assertEqual(document_payload["metadata"]["person_full_name"], "Panov Sergio")

    def test_reimport_same_run_replaces_previous_rows(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            input_json = tmp_dir / "report.json"
            input_json.write_text(json.dumps(report_payload(hits=[])), encoding="utf-8")
            db_path = tmp_dir / "evidence.sqlite"

            import_report_to_db(input_json_path=input_json, db_path=db_path, run_id="run:stable")
            import_report_to_db(input_json_path=input_json, db_path=db_path, run_id="run:stable")
            store = SQLiteEvidenceStore(db_path)
            run_count = store.count("search_runs")
            person_query_count = store.count("person_queries")
            source_result_count = store.count("source_results")

        self.assertEqual(run_count, 1)
        self.assertEqual(person_query_count, 1)
        self.assertEqual(source_result_count, 1)


if __name__ == "__main__":
    unittest.main()
