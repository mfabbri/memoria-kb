from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report import profiles_runner
from caduti_fonti_report.connectors.uniform_source_connector import UniformSourceConnector
from caduti_fonti_report.models import PersonQuery, Source
from caduti_fonti_report.person_profiles import profile_from_person_query, profile_to_jsonld
from caduti_fonti_report.queries import default_query
from caduti_fonti_report.source_definitions import load_source_definition

ENGINE = Path(__file__).resolve().parents[1]
CATALOG = ENGINE.parent / "memoria-sources"


@contextmanager
def workspace_temp_dir():
    base = ENGINE / ".tmp-tests"
    base.mkdir(exist_ok=True)
    directory = base / f"test-{uuid.uuid4().hex}"
    directory.mkdir()
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def write_profile_fixture(root):
    profile = profile_from_person_query(
        PersonQuery(full_name="Andreoli Dino", given_name="Dino", family_name="Andreoli"),
        seed_source="fixture.csv", imported_at="2026-05-09T10:00:00+00:00",
    )
    profile_path = root / "profile.jsonld"
    profile_path.write_text(json.dumps(profile_to_jsonld(profile)), encoding="utf-8")
    index = root / "index.jsonld"
    index.write_text(json.dumps({
        "@type": "PersonResearchProfileIndex", "count": 1,
        "profiles": [{"@id": profile.profile_id, "file": profile_path.name, "canonical_name": "Andreoli Dino"}],
    }), encoding="utf-8")
    return index


def make_source():
    return Source(
        source_id="partigiani_italia", source_name="Offline Partigiani fixture",
        kind="search_form_get_name", build_query=default_query,
        search_url_builder=lambda query: "https://example.invalid/search",
        form={"name_order": "surname_first"},
    )


def make_storia_memoria_source():
    return Source(
        source_id="storia_memoria_bo", source_name="Offline Storia fixture",
        kind="storia_memoria_bo", build_query=default_query,
        search_url_builder=lambda query: "https://example.invalid/search",
        form={"name_order": "surname_first"},
    )


class RecordingExecutor:
    def __init__(self):
        self.ids = []

    def execute(self, *, source, attempt):
        self.ids.append(attempt.attempt_id)
        return []


class AttemptSelectionTests(unittest.TestCase):
    def setUp(self):
        self.query = PersonQuery(full_name="Andreoli Dino", family_name="Andreoli", given_name="Dino", birth_date="1920-05-17")

    def test_only_requested_templates_execute_in_declared_order(self):
        for source, ids in (
            (make_source(), ["cognome-nome-contains", "cognome-nome-nascita"]),
            (make_storia_memoria_source(), ["nome-cognome", "testo-libero-nome-completo"]),
        ):
            for selection in ([ids[1]], list(reversed(ids))):
                with self.subTest(source=source.source_id, selection=selection):
                    executor = RecordingExecutor()
                    connector = UniformSourceConnector(source, repo_root=ENGINE, executor=executor, selected_attempt_ids=selection)
                    with patch.object(connector, "_cached_detail_hits_for_query", side_effect=AssertionError("explicit selection must execute selected attempts")):
                        connector.search_person(self.query)
                    self.assertEqual(executor.ids, [value for value in ids if value in selection])
                    connector.close()

    def test_invalid_selection_never_executes_or_reads_cache(self):
        for ids, query in (
            (["unknown"], self.query),
            (["nome-cognome"], self.query),
            (["cognome-nome-contains"] * 2, self.query),
            (["cognome-nome-nascita"], replace(self.query, birth_date="")),
        ):
            with self.subTest(ids=ids):
                executor = RecordingExecutor()
                connector = UniformSourceConnector(make_source(), repo_root=ENGINE, executor=executor, selected_attempt_ids=ids)
                with patch.object(connector, "_cached_detail_hits_for_query", side_effect=AssertionError("no cache before validation")):
                    with self.assertRaises(ValueError):
                        connector.search_person(query)
                self.assertEqual(executor.ids, [])
                connector.close()

    def test_mismatched_definition_is_rejected(self):
        source = make_source()
        definition = load_source_definition(source, repo_root=ENGINE)
        definition = replace(definition, strategy_definition=replace(definition.strategy_definition, source_id="another-source"))
        with self.assertRaisesRegex(ValueError, "non corrispondente"):
            UniformSourceConnector.selected_attempts(source, definition, self.query, ["cognome-nome-contains"])

    def test_launcher_runs_offline_declared_reference_connector_and_audits_selection(self):
        launcher = ENGINE / ".venv" / "Scripts" / "memoria.exe"
        self.assertTrue(launcher.is_file(), "installed memoria launcher is required")
        with workspace_temp_dir() as root:
            index = write_profile_fixture(root)
            # Independent catalog and reference-only source prevent any live source access.
            for level in ("source_profiles", "source_strategies", "source_result_logic", "source_detail_logic"):
                (root / level).mkdir()
                fixture = CATALOG / level / "storia_memoria_bo.yaml"
                if fixture.exists():
                    shutil.copyfile(fixture, root / level / "fixture.yaml")
                    path = root / level / "fixture.yaml"
                    path.write_text(path.read_text(encoding="utf-8").replace("storia_memoria_bo", "fixture"), encoding="utf-8")
            registry = root / "sources.yaml"
            registry.write_text("enabled_sources: [fixture]\nsources:\n- id: fixture\n  name: Offline fixture\n  kind: search_url_only\n  query_mode: default\n  url_template: https://example.invalid/?q={query}\n", encoding="utf-8")
            args = [str(launcher), "sources", "online", "run", "--profiles-index", str(index), "--sources-yaml", str(registry), "--source", "fixture", "--limit", "1", "--attempt-id", "testo-libero-nome-completo", "--output-json", str(root / "report.json"), "--output-md", str(root / "report.md"), "--output-dir", str(root / "cards")]
            result = subprocess.run(args, cwd=ENGINE, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((root / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["selected_attempt_ids"], ["testo-libero-nome-completo"])
            self.assertEqual(report["planned_execution_mode"], "selected_attempts")
            self.assertEqual(len(report["profiles"][0]["results"]), 1)
            invalid = subprocess.run(args + ["--attempt-id", "nome-sconosciuto", "--ensure-authenticated-session"], cwd=ENGINE, capture_output=True, text=True, timeout=30)
            self.assertEqual(invalid.returncode, 2, invalid.stdout + invalid.stderr)
            self.assertIn("attempt-id sconosciuto", invalid.stdout)

    def test_runner_preflights_profile_conditions_before_authentication(self):
        with workspace_temp_dir() as root:
            index = write_profile_fixture(root)  # No birth date: chosen strategy cannot apply.
            with (
                patch.object(profiles_runner, "_ensure_manual_authenticated_sessions") as authenticate,
                patch.object(profiles_runner, "create_source_connector") as create,
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index, sources_yaml=CATALOG / "registry" / "camalanca_fonti.yaml",
                    output_json=root / "report.json", output_md=root / "report.md", output_dir=root / "cards",
                    source_id="partigiani_italia", limit=1, selected_attempt_ids=["cognome-nome-nascita"],
                    ensure_authenticated_session=True,
                )
            self.assertEqual(result["exit_code"], 2)
            self.assertEqual(result["error"], "invalid_attempt_selection")
            authenticate.assert_not_called()
            create.assert_not_called()

    def test_runner_rejects_unbounded_or_conflicting_selection_before_loading_profiles(self):
        with workspace_temp_dir() as root:
            for extra in ({"limit": 0, "source_id": "partigiani_italia"}, {"limit": 1}, {"limit": 1, "source_id": "partigiani_italia", "execute_first_planned_attempt": True}):
                with patch.object(profiles_runner, "ProfileRepository", side_effect=AssertionError("validation must precede profiles")):
                    result = profiles_runner.run_profiles_report(profiles_index=root / "missing", sources_yaml=root / "missing", output_json=root / "report.json", output_md=root / "report.md", output_dir=root / "cards", selected_attempt_ids=["cognome-nome-contains"], **extra)
                self.assertEqual(result["exit_code"], 2)


if __name__ == "__main__":
    unittest.main()
