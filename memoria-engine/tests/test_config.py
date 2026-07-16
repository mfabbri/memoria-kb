from __future__ import annotations

import sys
import shutil
import unittest
import unittest.mock
import uuid
import os
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.config import (
    build_url_template,
    load_caduti,
    load_env_file,
    load_source_registry,
    load_sources_from_yaml,
)


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


class ConfigTests(unittest.TestCase):
    def test_build_url_template_quotes_query(self) -> None:
        builder = build_url_template("https://example.test/search?q={query}")
        self.assertEqual(builder("Mario Rossi"), "https://example.test/search?q=Mario%20Rossi")

    def test_load_caduti_reads_utf8_sig_csv(self) -> None:
        csv_text = (
            "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
            "profilo_biografico,episodio_documentato\n"
            'TEST PERSON,Test Person,Italia,1900,1944,partigiano,Fonte,"Profilo","Episodio"\n'
        )
        with workspace_temp_dir() as tmp_dir:
            csv_path = tmp_dir / "caduti.csv"
            csv_path.write_text(csv_text, encoding="utf-8-sig")
            caduti = load_caduti(csv_path)

        self.assertEqual(len(caduti), 1)
        self.assertEqual(caduti[0].nome, "Test Person")
        self.assertEqual(caduti[0].episodio_documentato, "Episodio")

    def test_load_source_registry_and_selection_use_enabled_sources(self) -> None:
        yaml_text = """
enabled_sources:
  - source_b
  - missing_source
  - source_b
sources:
  - id: source_a
    name: Source A
    kind: search_page
    query_mode: default
    url_template: https://example.test/a?q={query}
  - id: source_b
    name: Source B
    kind: credentialed
    query_mode: foreign
    url_template: https://example.test/b?q={query}
    credentials:
      email: user@example.test
    auth:
      reference_code: WO 417
    form:
      method: post
      action: https://example.test/form
      query_field: Fields[0].Value
    local:
      workbook_path: archivi/example.xls
      sheet_name: Foglio1
    timeout: 33
"""
        with workspace_temp_dir() as tmp_dir:
            yaml_path = tmp_dir / "sources.yaml"
            yaml_path.write_text(yaml_text, encoding="utf-8")
            registry = load_source_registry(yaml_path)
            selection = load_sources_from_yaml(yaml_path, registry)

        self.assertEqual(set(registry.keys()), {"source_a", "source_b"})
        self.assertEqual(registry["source_b"].timeout, 33)
        self.assertEqual(registry["source_b"].credentials["email"], "user@example.test")
        self.assertEqual(registry["source_b"].auth["reference_code"], "WO 417")
        self.assertEqual(registry["source_b"].form["query_field"], "Fields[0].Value")
        self.assertEqual(registry["source_b"].local["workbook_path"], "archivi/example.xls")
        self.assertEqual(selection.selected_source_ids, ["source_b"])
        self.assertEqual(selection.unresolved_source_ids, ["missing_source"])
        self.assertFalse(selection.used_fallback)

    def test_load_source_registry_resolves_credential_env_placeholders(self) -> None:
        yaml_text = """
sources:
  - id: source_a
    name: Source A
    kind: credentialed
    query_mode: default
    url_template: https://example.test/a?q={query}
    credentials:
      email: ${TEST_SOURCE_EMAIL}
      password: ${TEST_SOURCE_PASSWORD}
"""
        with workspace_temp_dir() as tmp_dir:
            yaml_path = tmp_dir / "sources.yaml"
            yaml_path.write_text(yaml_text, encoding="utf-8")
            with unittest.mock.patch.dict(
                "os.environ",
                {"TEST_SOURCE_EMAIL": "user@example.test"},
                clear=False,
            ):
                registry = load_source_registry(yaml_path)

        self.assertEqual(registry["source_a"].credentials["email"], "user@example.test")
        self.assertEqual(registry["source_a"].credentials["password"], "")

    def test_load_env_file_sets_missing_values_without_overriding(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            env_path = tmp_dir / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# local secrets",
                        "TEST_ENV_FILE_EMAIL=user@example.test",
                        'TEST_ENV_FILE_PASSWORD="secret-value"',
                        "TEST_ENV_FILE_EXISTING=from-file",
                    ]
                ),
                encoding="utf-8",
            )
            with unittest.mock.patch.dict(
                "os.environ",
                {"TEST_ENV_FILE_EXISTING": "from-env"},
                clear=False,
            ):
                loaded_count = load_env_file(env_path)
                email = os.environ["TEST_ENV_FILE_EMAIL"]
                password = os.environ["TEST_ENV_FILE_PASSWORD"]
                existing = os.environ["TEST_ENV_FILE_EXISTING"]

        self.assertEqual(loaded_count, 2)
        self.assertEqual(email, "user@example.test")
        self.assertEqual(password, "secret-value")
        self.assertEqual(existing, "from-env")

    def test_load_source_registry_reads_nearest_env_file(self) -> None:
        yaml_text = """
sources:
  - id: source_a
    name: Source A
    kind: credentialed
    query_mode: default
    url_template: https://example.test/a?q={query}
    credentials:
      email: ${TEST_NEAREST_ENV_EMAIL}
"""
        with workspace_temp_dir() as tmp_dir:
            env_path = tmp_dir / ".env"
            yaml_path = tmp_dir / "sources.yaml"
            env_path.write_text("TEST_NEAREST_ENV_EMAIL=nearest@example.test\n", encoding="utf-8")
            yaml_path.write_text(yaml_text, encoding="utf-8")
            with unittest.mock.patch.dict("os.environ", {}, clear=True):
                registry = load_source_registry(yaml_path)

        self.assertEqual(registry["source_a"].credentials["email"], "nearest@example.test")

    def test_load_sources_from_yaml_falls_back_to_registry_when_none_are_valid(self) -> None:
        yaml_text = """
enabled_sources:
  - missing_source
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
        with workspace_temp_dir() as tmp_dir:
            yaml_path = tmp_dir / "sources.yaml"
            yaml_path.write_text(yaml_text, encoding="utf-8")
            registry = load_source_registry(yaml_path)
            selection = load_sources_from_yaml(yaml_path, registry)

        self.assertEqual(selection.selected_source_ids, ["source_a", "source_b"])
        self.assertEqual(selection.unresolved_source_ids, ["missing_source"])
        self.assertTrue(selection.used_fallback)

    def test_load_sources_from_yaml_can_select_single_source_from_registry(self) -> None:
        yaml_text = """
enabled_sources:
  - source_a
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
        with workspace_temp_dir() as tmp_dir:
            yaml_path = tmp_dir / "sources.yaml"
            yaml_path.write_text(yaml_text, encoding="utf-8")
            registry = load_source_registry(yaml_path)
            selection = load_sources_from_yaml(yaml_path, registry, only_source_id="source_b")

        self.assertEqual(selection.selected_source_ids, ["source_b"])
        self.assertEqual(selection.unresolved_source_ids, [])
        self.assertFalse(selection.used_fallback)

    def test_load_sources_from_yaml_single_source_does_not_fallback_when_missing(self) -> None:
        yaml_text = """
enabled_sources:
  - source_a
sources:
  - id: source_a
    name: Source A
    kind: search_page
    query_mode: default
    url_template: https://example.test/a?q={query}
"""
        with workspace_temp_dir() as tmp_dir:
            yaml_path = tmp_dir / "sources.yaml"
            yaml_path.write_text(yaml_text, encoding="utf-8")
            registry = load_source_registry(yaml_path)
            selection = load_sources_from_yaml(yaml_path, registry, only_source_id="missing_source")

        self.assertEqual(selection.selected_source_ids, [])
        self.assertEqual(selection.unresolved_source_ids, ["missing_source"])
        self.assertFalse(selection.used_fallback)


if __name__ == "__main__":
    unittest.main()
