from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.extract_table_claims import extract_table_claims_to_db
from caduti_fonti_report.models import PersonQuery, SearchRun
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


def write_sources_yaml(path: Path, *, extraction: str) -> None:
    path.write_text(
        f"""sources:
  - id: local_test
    name: Fonte tabellare test
    kind: local_excel
    query_mode: default
    url_template: "file:///tmp"
    local:
      name_order: "surname_first"
      surname_column: "Cognome"
      given_name_column: "Nome"
      snippet_columns: "Nome battaglia,Nato comune,Vuoto"
{extraction}
""",
        encoding="utf-8",
    )


def seed_run(db_path: Path) -> SQLiteEvidenceStore:
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    store.insert_search_run(
        SearchRun(
            run_id="run:test",
            timestamp="2026-04-26T12:00:00+00:00",
            input_file="fixture.csv",
            source_ids=["local_test"],
            parameters={},
            metadata={},
        )
    )
    store.insert_person_query(
        "run:test",
        PersonQuery(full_name="Rossi Mario", given_name="Mario", family_name="Rossi"),
    )
    return store


class ExtractTableClaimsTests(unittest.TestCase):
    def test_mapping_creates_source_document_and_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            sources_yaml = tmp_dir / "sources.yaml"
            write_sources_yaml(
                sources_yaml,
                extraction="""    extraction:
      method: local_table_claims
      claim_mappings:
        - column: "Nome battaglia"
          field: "alias"
          confidence: 0.8
        - column: "Nato comune"
          field: "birth.place"
          confidence: 0.7
        - column: "Vuoto"
          field: "note.empty"
          confidence: 0.5
""",
            )
            db_path = tmp_dir / "evidence.sqlite"
            store = seed_run(db_path)
            rows = [
                {
                    "__row_number__": "2",
                    "Cognome": "Rossi",
                    "Nome": "Mario",
                    "Nome battaglia": "Falco",
                    "Nato comune": "Faenza",
                    "Vuoto": "",
                }
            ]

            with patch("caduti_fonti_report.extract_table_claims.load_excel_rows") as load_excel_rows:
                load_excel_rows.return_value = [(tmp_dir / "fonte.xls", "Foglio1", rows)]
                summary = extract_table_claims_to_db(
                    db_path=db_path,
                    run_id="run:test",
                    source_id="local_test",
                    sources_yaml_path=sources_yaml,
                )
            document_rows = store.fetch_all("source_documents")
            claim_rows = store.fetch_all("evidence_claims")
            claim_payloads = [json.loads(row["payload_json"]) for row in claim_rows]

        self.assertEqual(summary.matched_people, 1)
        self.assertEqual(summary.documents, 1)
        self.assertEqual(summary.claims, 2)
        self.assertEqual(len(document_rows), 1)
        self.assertEqual(len(claim_rows), 2)
        self.assertEqual({claim["field"] for claim in claim_payloads}, {"alias", "birth.place"})
        self.assertEqual({claim["review_status"] for claim in claim_payloads}, {"unreviewed"})
        self.assertEqual({claim["extraction_method"] for claim in claim_payloads}, {"local_table_claims"})

    def test_source_without_mapping_creates_no_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            sources_yaml = tmp_dir / "sources.yaml"
            write_sources_yaml(sources_yaml, extraction="")
            db_path = tmp_dir / "evidence.sqlite"
            store = seed_run(db_path)

            summary = extract_table_claims_to_db(
                db_path=db_path,
                run_id="run:test",
                source_id="local_test",
                sources_yaml_path=sources_yaml,
            )
            claim_count = store.count("evidence_claims")
            document_count = store.count("source_documents")

        self.assertEqual(summary.claims, 0)
        self.assertEqual(claim_count, 0)
        self.assertEqual(document_count, 0)

    def test_rerun_is_idempotent_for_identical_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            sources_yaml = tmp_dir / "sources.yaml"
            write_sources_yaml(
                sources_yaml,
                extraction="""    extraction:
      method: local_table_claims
      claim_mappings:
        - column: "Nato comune"
          field: "birth.place"
          confidence: 0.7
""",
            )
            db_path = tmp_dir / "evidence.sqlite"
            store = seed_run(db_path)
            rows = [{"__row_number__": "2", "Cognome": "Rossi", "Nome": "Mario", "Nato comune": "Faenza"}]

            with patch("caduti_fonti_report.extract_table_claims.load_excel_rows") as load_excel_rows:
                load_excel_rows.return_value = [(tmp_dir / "fonte.xls", "Foglio1", rows)]
                extract_table_claims_to_db(
                    db_path=db_path,
                    run_id="run:test",
                    source_id="local_test",
                    sources_yaml_path=sources_yaml,
                )
                extract_table_claims_to_db(
                    db_path=db_path,
                    run_id="run:test",
                    source_id="local_test",
                    sources_yaml_path=sources_yaml,
                )
            claim_count = store.count("evidence_claims")
            document_count = store.count("source_documents")

        self.assertEqual(claim_count, 1)
        self.assertEqual(document_count, 1)


if __name__ == "__main__":
    unittest.main()
