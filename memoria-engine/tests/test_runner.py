from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.models import SearchHit, SourceDocument, SourceResult
from caduti_fonti_report.runner import main


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


class FakeConnector:
    def __init__(
        self,
        source,
        *,
        with_hit: bool = False,
        call_log: list[str] | None = None,
    ) -> None:
        self.source = source
        self.with_hit = with_hit
        self.call_log = call_log

    def search_person(self, query):
        if self.call_log is not None:
            self.call_log.append("search")
        hits = [SearchHit(title=f"Hit {query.full_name}", url="https://example.test/detail")] if self.with_hit else []
        return [
            SourceResult(
                source_id=self.source.source_id,
                source_name=self.source.source_name,
                status="ok",
                note=f"Risultato per {query.full_name}",
                query=query.full_name,
                search_url=self.source.search_url_builder(query.full_name),
                hits=hits,
            )
        ]

    def fetch_detail(self, result):
        if self.call_log is not None:
            self.call_log.append("fetch_detail")
        return []

    def extract_evidence(self, document):
        if self.call_log is not None:
            self.call_log.append("extract_evidence")
        return []

    def close(self):
        if self.call_log is not None:
            self.call_log.append("close")


class RunnerTests(unittest.TestCase):
    def validation_ok(self):
        return type("ValidationResult", (), {"valid": True, "errors": []})()

    def test_main_generates_markdown_json_and_single_sheets(self) -> None:
        csv_text = (
            "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
            "profilo_biografico,episodio_documentato\n"
            'TEST ONE,Test One,Italia,1900,1944,partigiano,Fonte A,"Profilo A","Episodio A"\n'
            'TEST TWO,Test Two,Austria,1901,1945,medico,Fonte B,"Profilo B","Episodio B"\n'
        )
        yaml_text = """
enabled_sources:
  - source_a
sources:
  - id: source_a
    name: Source A
    kind: search_page
    query_mode: default
    url_template: https://example.test/search?q={query}
    note: Nota sorgente
"""
        with workspace_temp_dir() as base_path:
            csv_path = base_path / "caduti.csv"
            yaml_path = base_path / "fonti.yaml"
            output_md = base_path / "out.md"
            output_json = base_path / "out.json"
            output_dir = base_path / "schede"
            csv_path.write_text(csv_text, encoding="utf-8")
            yaml_path.write_text(yaml_text, encoding="utf-8")

            argv = [
                "caduti_fonti_report.py",
                "--csv",
                str(csv_path),
                "--sources-yaml",
                str(yaml_path),
                "--output-md",
                str(output_md),
                "--output-json",
                str(output_json),
                "--output-dir",
                str(output_dir),
            ]

            with patch("caduti_fonti_report.runner.validate_sources_registry_file", return_value=self.validation_ok()):
                with patch(
                    "caduti_fonti_report.runner.create_source_connector",
                    side_effect=lambda source, **_: FakeConnector(source, with_hit=True),
                ):
                    with patch.object(sys, "argv", argv):
                        exit_code = main()

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_md.exists())
            self.assertTrue(output_json.exists())
            self.assertTrue((output_dir / "test-one.md").exists())
            self.assertTrue((output_dir / "test-two.md").exists())

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["source_selection"]["selected_source_ids"], ["source_a"])
            self.assertEqual(len(payload["caduti"]), 2)
            self.assertEqual(payload["caduti"][0]["results"][0]["result"]["status"], "ok")
            self.assertIn("Report fonti caduti di Purocielo", output_md.read_text(encoding="utf-8"))

    def test_main_can_run_one_source_from_yaml(self) -> None:
        csv_text = (
            "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
            "profilo_biografico,episodio_documentato\n"
            'TEST ONE,Test One,Italia,1900,1944,partigiano,Fonte A,"Profilo A","Episodio A"\n'
        )
        yaml_text = """
enabled_sources:
  - source_a
  - source_b
sources:
  - id: source_a
    name: Source A
    kind: search_page
    query_mode: default
    url_template: https://example.test/a?q={query}
  - id: source_b
    name: Source B
    kind: search_page
    query_mode: default
    url_template: https://example.test/b?q={query}
"""
        with workspace_temp_dir() as base_path:
            csv_path = base_path / "caduti.csv"
            yaml_path = base_path / "fonti.yaml"
            output_md = base_path / "out.md"
            output_json = base_path / "out.json"
            output_dir = base_path / "schede"
            csv_path.write_text(csv_text, encoding="utf-8")
            yaml_path.write_text(yaml_text, encoding="utf-8")

            argv = [
                "caduti_fonti_report.py",
                "--csv",
                str(csv_path),
                "--sources-yaml",
                str(yaml_path),
                "--output-md",
                str(output_md),
                "--output-json",
                str(output_json),
                "--output-dir",
                str(output_dir),
                "--source",
                "source_b",
            ]

            with patch("caduti_fonti_report.runner.validate_sources_registry_file", return_value=self.validation_ok()):
                with patch(
                    "caduti_fonti_report.runner.create_source_connector",
                    side_effect=lambda source, **_: FakeConnector(source),
                ):
                    with patch.object(sys, "argv", argv):
                        exit_code = main()

            payload = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["source_selection"]["selected_source_ids"], ["source_b"])
        self.assertEqual(payload["caduti"][0]["results"][0]["result"]["source_id"], "source_b")

    def test_main_warns_when_manual_authenticated_source_is_selected(self) -> None:
        csv_text = (
            "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
            "profilo_biografico,episodio_documentato\n"
            'TEST ONE,Test One,Italia,1900,1944,partigiano,Fonte A,"Profilo A","Episodio A"\n'
        )
        yaml_text = """
enabled_sources:
  - partigiani_italia
sources:
  - id: partigiani_italia
    name: I Partigiani d'Italia - ricerca pubblica
    kind: search_form_get_name
    query_mode: default
    url_template: https://partigianiditalia.cultura.gov.it/cerca/
    auth:
      auth_mode: manual_persistent_context
"""
        with workspace_temp_dir() as base_path:
            csv_path = base_path / "caduti.csv"
            yaml_path = base_path / "fonti.yaml"
            output_md = base_path / "out.md"
            output_json = base_path / "out.json"
            output_dir = base_path / "schede"
            csv_path.write_text(csv_text, encoding="utf-8")
            yaml_path.write_text(yaml_text, encoding="utf-8")

            argv = [
                "caduti_fonti_report.py",
                "--csv",
                str(csv_path),
                "--sources-yaml",
                str(yaml_path),
                "--output-md",
                str(output_md),
                "--output-json",
                str(output_json),
                "--output-dir",
                str(output_dir),
                "--source",
                "partigiani_italia",
            ]

            stdout = StringIO()
            with patch("caduti_fonti_report.runner.validate_sources_registry_file", return_value=self.validation_ok()):
                with patch(
                    "caduti_fonti_report.runner.create_source_connector",
                    side_effect=lambda source, **_: FakeConnector(source, with_hit=True),
                ):
                    with patch.object(sys, "argv", argv):
                        with patch("sys.stdout", stdout):
                            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertIn("puo' aprire SPID/CIE", stdout.getvalue())

    def test_main_can_filter_one_caduto_by_name(self) -> None:
        csv_text = (
            "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
            "profilo_biografico,episodio_documentato\n"
            'BASSI GIANCARLO,Bassi Giancarlo,Italia,1900,1944,partigiano,Fonte A,"Profilo A","Episodio A"\n'
            'BOSCHI DINO,Boschi Dino,Italia,1901,1945,partigiano,Fonte B,"Profilo B","Episodio B"\n'
        )
        yaml_text = """
enabled_sources:
  - source_a
sources:
  - id: source_a
    name: Source A
    kind: search_page
    query_mode: default
    url_template: https://example.test/search?q={query}
"""
        with workspace_temp_dir() as base_path:
            csv_path = base_path / "caduti.csv"
            yaml_path = base_path / "fonti.yaml"
            output_md = base_path / "out.md"
            output_json = base_path / "out.json"
            output_dir = base_path / "schede"
            csv_path.write_text(csv_text, encoding="utf-8")
            yaml_path.write_text(yaml_text, encoding="utf-8")

            argv = [
                "caduti_fonti_report.py",
                "--csv",
                str(csv_path),
                "--sources-yaml",
                str(yaml_path),
                "--output-md",
                str(output_md),
                "--output-json",
                str(output_json),
                "--output-dir",
                str(output_dir),
                "--name",
                "giancarlo bassi",
            ]

            with patch("caduti_fonti_report.runner.validate_sources_registry_file", return_value=self.validation_ok()):
                with patch(
                    "caduti_fonti_report.runner.create_source_connector",
                    side_effect=lambda source, **_: FakeConnector(source),
                ):
                    with patch.object(sys, "argv", argv):
                        exit_code = main()

            payload = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(payload["caduti"]), 1)
        self.assertEqual(payload["caduti"][0]["caduto"]["nome"], "Bassi Giancarlo")

    def test_main_uses_connector_detail_fetch_and_closes_connector(self) -> None:
        csv_text = (
            "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
            "profilo_biografico,episodio_documentato\n"
            'ANDREOLI DINO,Andreoli Dino,Italia,1900,1944,partigiano,Fonte A,"Profilo A","Episodio A"\n'
        )
        yaml_text = """
enabled_sources:
  - partigiani_italia
sources:
  - id: partigiani_italia
    name: I Partigiani d'Italia
    kind: search_form_get_name
    query_mode: default
    url_template: https://partigianiditalia.cultura.gov.it/cerca/
    auth:
      auth_mode: manual_persistent_context
"""
        with workspace_temp_dir() as base_path:
            csv_path = base_path / "caduti.csv"
            yaml_path = base_path / "fonti.yaml"
            output_md = base_path / "out.md"
            output_json = base_path / "out.json"
            output_dir = base_path / "schede"
            csv_path.write_text(csv_text, encoding="utf-8")
            yaml_path.write_text(yaml_text, encoding="utf-8")

            call_log: list[str] = []

            def create_connector(source, **_):
                class DetailConnector(FakeConnector):
                    def fetch_detail(self, result):
                        call_log.append("fetch_detail")
                        return [SourceDocument(document_id="doc-1", source_id="partigiani_italia")]

                    def extract_evidence(self, document):
                        call_log.append("extract_evidence")
                        return []

                return DetailConnector(source, call_log=call_log)

            argv = [
                "caduti_fonti_report.py",
                "--csv",
                str(csv_path),
                "--sources-yaml",
                str(yaml_path),
                "--output-md",
                str(output_md),
                "--output-json",
                str(output_json),
                "--output-dir",
                str(output_dir),
                "--source",
                "partigiani_italia",
            ]

            with patch("caduti_fonti_report.runner.validate_sources_registry_file", return_value=self.validation_ok()):
                with patch("caduti_fonti_report.runner.create_source_connector", side_effect=create_connector):
                    with patch.object(sys, "argv", argv):
                        exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(call_log, ["search", "fetch_detail", "extract_evidence", "close"])

    def test_main_returns_error_when_name_filter_has_no_match(self) -> None:
        csv_text = (
            "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
            "profilo_biografico,episodio_documentato\n"
            'BASSI GIANCARLO,Bassi Giancarlo,Italia,1900,1944,partigiano,Fonte A,"Profilo A","Episodio A"\n'
        )
        yaml_text = """
enabled_sources:
  - source_a
sources:
  - id: source_a
    name: Source A
    kind: search_page
    query_mode: default
    url_template: https://example.test/search?q={query}
"""
        with workspace_temp_dir() as base_path:
            csv_path = base_path / "caduti.csv"
            yaml_path = base_path / "fonti.yaml"
            output_md = base_path / "out.md"
            output_json = base_path / "out.json"
            output_dir = base_path / "schede"
            csv_path.write_text(csv_text, encoding="utf-8")
            yaml_path.write_text(yaml_text, encoding="utf-8")

            argv = [
                "caduti_fonti_report.py",
                "--csv",
                str(csv_path),
                "--sources-yaml",
                str(yaml_path),
                "--output-md",
                str(output_md),
                "--output-json",
                str(output_json),
                "--output-dir",
                str(output_dir),
                "--name",
                "nome inesistente",
            ]

            with patch.object(sys, "argv", argv):
                exit_code = main()

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
