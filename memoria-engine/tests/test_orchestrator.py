from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.models import SearchHit, SourceDocument, SourceResult
from caduti_fonti_report.orchestrator import run_meta_search
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


def write_inputs(base_path: Path) -> tuple[Path, Path]:
    csv_text = (
        "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
        "profilo_biografico,episodio_documentato\n"
        'PANOV SERGIO,Panov Sergio,U.R.S.S.,non reperito,non reperito,partigiano,Fonte A,"Profilo","Episodio"\n'
    )
    yaml_text = """
enabled_sources:
  - partigiani_italia
sources:
  - id: partigiani_italia
    name: I Partigiani d'Italia
    kind: search_form_get_name
    form:
      action: https://example.test/cerca/
"""
    csv_path = base_path / "caduti.csv"
    yaml_path = base_path / "fonti.yaml"
    csv_path.write_text(csv_text, encoding="utf-8")
    yaml_path.write_text(yaml_text, encoding="utf-8")
    return csv_path, yaml_path


class OrchestratorTests(unittest.TestCase):
    def test_run_meta_search_writes_report_and_imports_database(self) -> None:
        with workspace_temp_dir() as base_path:
            csv_path, yaml_path = write_inputs(base_path)
            output_md = base_path / "out.md"
            output_json = base_path / "out.json"
            output_dir = base_path / "schede"
            db_path = base_path / "evidence.sqlite"

            class FakeConnector:
                def __init__(self, source):
                    self.source = source

                def search_person(self, query):
                    return [
                        SourceResult(
                            source_id=self.source.source_id,
                            source_name=self.source.source_name,
                            status="ok",
                            note="Risultato di prova",
                            query=query.full_name,
                            search_url="https://example.test/cerca/?nome=Sergio&cognome=Panov",
                            hits=[SearchHit(title="Scheda Panov Sergio", url="https://example.test/scheda/panov")],
                        )
                    ]

                def fetch_detail(self, result):
                    return [
                        SourceDocument(
                            document_id="doc:test:panov",
                            source_id=result.source_id,
                            title=result.hits[0].title,
                            url=result.hits[0].url,
                            access_date="2026-05-09",
                            media_type="text/html",
                            metadata={"access_mode": "reference_only"},
                        )
                    ]

                def extract_evidence(self, document):
                    return []

                def close(self):
                    return None

            def fake_create_source_connector(source, **_kwargs):
                return FakeConnector(source)

            validation_ok = type("Validation", (), {"valid": True, "errors": []})()
            with (
                patch("caduti_fonti_report.runner.create_source_connector", side_effect=fake_create_source_connector),
                patch("caduti_fonti_report.runner.validate_sources_registry_file", return_value=validation_ok),
            ):
                result = run_meta_search(
                    csv_path=csv_path,
                    sources_yaml=yaml_path,
                    output_md=output_md,
                    output_json=output_json,
                    output_dir=output_dir,
                    db_path=db_path,
                    run_id="meta:test",
                )

            store = SQLiteEvidenceStore(db_path)
            counts = {
                "search_runs": store.count("search_runs"),
                "person_queries": store.count("person_queries"),
                "source_results": store.count("source_results"),
                "source_documents": store.count("source_documents"),
                "evidence_claims": store.count("evidence_claims"),
            }
            output_md_exists = output_md.exists()
            output_json_exists = output_json.exists()

        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(output_md_exists)
        self.assertTrue(output_json_exists)
        self.assertEqual(counts["search_runs"], 1)
        self.assertEqual(counts["person_queries"], 1)
        self.assertEqual(counts["source_results"], 1)
        self.assertEqual(counts["source_documents"], 0)
        self.assertEqual(counts["evidence_claims"], 0)

    def test_run_meta_search_does_not_import_when_name_filter_fails(self) -> None:
        with workspace_temp_dir() as base_path:
            csv_path, yaml_path = write_inputs(base_path)
            db_path = base_path / "evidence.sqlite"

            result = run_meta_search(
                csv_path=csv_path,
                sources_yaml=yaml_path,
                output_md=base_path / "out.md",
                output_json=base_path / "out.json",
                output_dir=base_path / "schede",
                db_path=db_path,
                name_filter="nome inesistente",
                run_id="meta:not-imported",
            )

        self.assertEqual(result["exit_code"], 2)
        self.assertIsNone(result["db_import"])
        self.assertFalse(db_path.exists())

    def test_run_meta_search_does_not_import_when_source_is_missing(self) -> None:
        with workspace_temp_dir() as base_path:
            csv_path, yaml_path = write_inputs(base_path)
            db_path = base_path / "evidence.sqlite"

            result = run_meta_search(
                csv_path=csv_path,
                sources_yaml=yaml_path,
                output_md=base_path / "out.md",
                output_json=base_path / "out.json",
                output_dir=base_path / "schede",
                db_path=db_path,
                source_id="fonte_assente",
                run_id="meta:not-imported",
            )

        self.assertEqual(result["exit_code"], 2)
        self.assertIsNone(result["db_import"])
        self.assertFalse(db_path.exists())


if __name__ == "__main__":
    unittest.main()
