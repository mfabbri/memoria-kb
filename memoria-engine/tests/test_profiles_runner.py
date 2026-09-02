from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report import profiles_runner
from caduti_fonti_report.models import EvidenceClaim, PersonQuery, SearchHit, Source, SourceDocument, SourceResult
from caduti_fonti_report.person_profiles import profile_from_person_query, profile_to_jsonld


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
    def __init__(self, source: Source) -> None:
        self.source = source
        self.last_query: PersonQuery | None = None

    def search_person(self, query: PersonQuery) -> list[SourceResult]:
        self.last_query = query
        return [
            SourceResult(
                source_id=self.source.source_id,
                source_name=self.source.source_name,
                status="candidate_results",
                note="fixture",
                query=query.full_name,
                search_url=self.source.search_url_builder(query.full_name),
                hits=[SearchHit(title=query.full_name, url="https://example.test/detail/1", snippet="fixture")],
            )
        ]

    def fetch_detail(self, result: SourceResult) -> list[SourceDocument]:
        assert self.last_query is not None
        return [
            SourceDocument(
                document_id="controlled:doc:1",
                source_id=result.source_id,
                title=result.hits[0].title,
                url=result.hits[0].url,
                access_date="2026-05-09",
                raw_text="Scheda dettaglio online di Andreoli Dino con fonte revisionabile.",
                metadata={
                    "profile_id": self.last_query.metadata["profile_id"],
                    "profile_source_file": self.last_query.metadata["profile_source_file"],
                    "detail_assessment": "claim_candidates_extracted",
                    "detail_extracted_fields_json": json.dumps({"death_date": "11 ottobre 1944"}, ensure_ascii=False),
                },
            )
        ]

    def extract_evidence(self, document: SourceDocument) -> list[EvidenceClaim]:
        return [
            EvidenceClaim(
                claim_id="claim:controlled:1",
                subject_id=document.metadata["profile_id"],
                field="death.date",
                value="11 ottobre 1944",
                normalized_value="11 ottobre 1944",
                source_document_id=document.document_id,
                source_url=document.url,
                review_status="unreviewed",
            )
        ]

    def close(self) -> None:
        pass


class EmptyDetailConnector(FakeConnector):
    def fetch_detail(self, result: SourceResult) -> list[SourceDocument]:
        assert self.last_query is not None
        return [
            SourceDocument(
                document_id="controlled:doc:empty",
                source_id=result.source_id,
                title=result.hits[0].title,
                url=result.hits[0].url,
                access_date="2026-05-09",
                raw_text="",
                metadata={
                    "profile_id": self.last_query.metadata["profile_id"],
                    "profile_source_file": self.last_query.metadata["profile_source_file"],
                },
            )
        ]


class ValidValidation:
    valid = True
    errors: list[str] = []


class FakeManualAuthenticatedSession:
    ensured_sources: list[str] = []

    def __init__(self, source: Source, repo_root: Path):
        self.source = source
        self.repo_root = repo_root

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ensure_authenticated(self):
        self.ensured_sources.append(self.source.source_id)
        return type(
            "State",
            (),
            {
                "state": "logged-in",
                "note": "fixture",
                "checked_url": "https://partigianiditalia.cultura.gov.it/",
            },
        )()

    def close(self) -> None:
        return None


def write_profile_fixture(root: Path) -> Path:
    return write_profile_fixture_with_seed(root, seed_source="fixture.csv")


def write_legacy_profile_fixture(root: Path) -> Path:
    return write_profile_fixture_with_seed(root, seed_source="ricerche\\caduti_purocielo.csv")


def write_profile_fixture_with_seed(root: Path, *, seed_source: str) -> Path:
    profiles_dir = root / "person_profiles"
    profiles_dir.mkdir()
    profile = profile_from_person_query(
        PersonQuery(
            full_name="Andreoli Dino",
            given_name="Dino",
            family_name="Andreoli",
            death_date="11 ottobre 1944",
            place_hint="Italia",
        ),
        seed_source=seed_source,
        imported_at="2026-05-09T10:00:00+00:00",
    )
    profile_path = profiles_dir / "purocielo-andreoli-dino.jsonld"
    profile_path.write_text(json.dumps(profile_to_jsonld(profile), ensure_ascii=False, indent=2), encoding="utf-8")
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_path.write_text(
        json.dumps(
            {
                "@type": "PersonResearchProfileIndex",
                "count": 1,
                "profiles": [
                    {
                        "@id": "person:purocielo:andreoli-dino",
                        "file": "purocielo-andreoli-dino.jsonld",
                        "canonical_name": "Andreoli Dino",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return index_path


def write_sources_fixture(root: Path) -> Path:
    sources_path = root / "sources.yaml"
    sources_path.write_text(
        "\n".join(
            [
                "enabled_sources:",
                "- controlled",
                "sources:",
                "- id: controlled",
                "  name: Controlled Source",
                "  kind: search_url_only",
                "  query_mode: default",
                "  url_template: https://example.test/search?q={query}",
                "  note: Fonte controllata fixture.",
            ]
        ),
        encoding="utf-8",
    )
    return sources_path


def real_sources_path() -> Path:
    return Path(__file__).resolve().parents[1] / "ricerche" / "camalanca_fonti.yaml"


class ProfilesRunnerTests(unittest.TestCase):
    def test_repo_root_from_memoria_sources_registry_points_to_engine_repo(self) -> None:
        repo_root = profiles_runner._repo_root_from_sources_yaml(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "registry" / "camalanca_fonti.yaml"
        )

        self.assertEqual(repo_root.name, "memoria-engine")
        self.assertTrue((repo_root / "code").is_dir())

    def test_runs_from_profile_jsonld_and_preserves_profile_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            sources_path = write_sources_fixture(tmp_dir)
            output_md = tmp_dir / "report.md"
            output_json = tmp_dir / "report.json"
            output_dir = tmp_dir / "schede"

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "create_source_connector", side_effect=lambda source, **kwargs: FakeConnector(source)),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=sources_path,
                    output_md=output_md,
                    output_json=output_json,
                    output_dir=output_dir,
                    source_id="controlled",
                    profile_id="person:purocielo:andreoli-dino",
                    limit=1,
                )

            payload = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(payload["input_mode"], "person_profiles_jsonld")
        self.assertEqual(payload["profiles"][0]["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(payload["profiles"][0]["person_query"]["metadata"]["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(payload["profiles"][0]["results"][0]["documents"][0]["metadata"]["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(payload["profiles"][0]["results"][0]["claims"][0]["subject_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(payload["profiles"][0]["results"][0]["claims"][0]["review_status"], "unreviewed")

    def test_explicit_profile_id_can_run_from_legacy_seed_profile(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_legacy_profile_fixture(tmp_dir)
            sources_path = write_sources_fixture(tmp_dir)
            output_md = tmp_dir / "report.md"
            output_json = tmp_dir / "report.json"
            output_dir = tmp_dir / "schede"

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "create_source_connector", side_effect=lambda source, **kwargs: FakeConnector(source)),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=sources_path,
                    output_md=output_md,
                    output_json=output_json,
                    output_dir=output_dir,
                    source_id="controlled",
                    profile_id="person:purocielo:andreoli-dino",
                    limit=1,
                )

            payload = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(payload["profiles"][0]["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(payload["profiles"][0]["results"][0]["claims"][0]["review_status"], "unreviewed")

    def test_can_include_search_plan_without_changing_execution(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            output_md = tmp_dir / "report.md"
            output_json = tmp_dir / "report.json"
            output_dir = tmp_dir / "schede"

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "create_source_connector", side_effect=lambda source, **kwargs: FakeConnector(source)),
                patch.object(
                    profiles_runner,
                    "_planned_attempts_for_profile_source",
                    return_value=[
                        {
                            "source_id": "partigiani_italia",
                            "attempt_id": "fixture-plan",
                            "priority": 1,
                            "query_text": "Andreoli Dino",
                        }
                    ],
                ),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=real_sources_path(),
                    output_md=output_md,
                    output_json=output_json,
                    output_dir=output_dir,
                    source_id="partigiani_italia",
                    profile_id="person:purocielo:andreoli-dino",
                    limit=1,
                    include_search_plan=True,
                )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            entry = payload["profiles"][0]["results"][0]

        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(payload["include_search_plan"])
        self.assertIn("planned_attempts", entry)
        self.assertEqual(entry["planned_attempts"][0]["source_id"], "partigiani_italia")
        self.assertEqual(entry["planned_attempts"][0]["attempt_id"], "fixture-plan")
        self.assertEqual(entry["planned_execution_mode"], "standard")
        self.assertEqual(entry["planned_attempt_execution_limit"], 0)
        self.assertEqual(entry["matched_planned_attempt_id"], "fixture-plan")
        self.assertEqual(entry["matched_planned_attempt_priority"], 1)
        self.assertEqual(entry["matched_planned_attempt_status"], "matched")
        self.assertEqual(entry["claims"][0]["review_status"], "unreviewed")

    def test_can_prepare_manual_authenticated_session_before_search(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            FakeManualAuthenticatedSession.ensured_sources = []
            index_path = write_profile_fixture(tmp_dir)
            output_md = tmp_dir / "report.md"
            output_json = tmp_dir / "report.json"
            output_dir = tmp_dir / "schede"
            connector_kwargs: list[dict[str, object]] = []
            connector_sources: list[Source] = []

            def create_connector(source: Source, **kwargs):
                connector_sources.append(source)
                connector_kwargs.append(dict(kwargs))
                return FakeConnector(source)

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "ManualAuthenticatedPlaywrightSession", FakeManualAuthenticatedSession),
                patch.object(profiles_runner, "create_source_connector", side_effect=create_connector),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=real_sources_path(),
                    output_md=output_md,
                    output_json=output_json,
                    output_dir=output_dir,
                    source_id="partigiani_italia",
                    profile_id="person:purocielo:andreoli-dino",
                    limit=1,
                    ensure_authenticated_session=True,
                )

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(FakeManualAuthenticatedSession.ensured_sources, ["partigiani_italia"])
        self.assertIsNotNone(connector_kwargs[0]["authenticated_session_factory"])
        factory = connector_kwargs[0]["authenticated_session_factory"]
        prepared_session = factory(connector_sources[0], tmp_dir)
        state = prepared_session.ensure_authenticated()
        self.assertEqual(state.state, "logged-in")
        self.assertEqual(FakeManualAuthenticatedSession.ensured_sources, ["partigiani_italia"])

    def test_can_apply_authenticated_runtime_options_to_selected_sources(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            output_md = tmp_dir / "report.md"
            output_json = tmp_dir / "report.json"
            output_dir = tmp_dir / "schede"
            connector_sources: list[Source] = []

            def create_connector(source: Source, **kwargs):
                connector_sources.append(source)
                return FakeConnector(source)

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "create_source_connector", side_effect=create_connector),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=real_sources_path(),
                    output_md=output_md,
                    output_json=output_json,
                    output_dir=output_dir,
                    source_id="partigiani_italia",
                    profile_id="person:purocielo:andreoli-dino",
                    limit=1,
                    refresh_authenticated_cache=True,
                    keep_authenticated_browser_open_seconds=45,
                )

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(connector_sources[0].auth["force_refresh_authenticated_cache"], "true")
        self.assertEqual(connector_sources[0].auth["keep_open_seconds"], "45")

    def test_marks_search_plan_attempt_as_unmatched_when_query_differs(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            sources_path = write_sources_fixture(tmp_dir)
            output_md = tmp_dir / "report.md"
            output_json = tmp_dir / "report.json"
            output_dir = tmp_dir / "schede"

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "create_source_connector", side_effect=lambda source, **kwargs: FakeConnector(source)),
                patch.object(
                    profiles_runner,
                    "_planned_attempts_for_profile_source",
                    return_value=[
                        {
                            "source_id": "controlled",
                            "attempt_id": "other-plan",
                            "priority": 2,
                            "query_text": "Andreoli",
                        }
                    ],
                ),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=sources_path,
                    output_md=output_md,
                    output_json=output_json,
                    output_dir=output_dir,
                    source_id="controlled",
                    profile_id="person:purocielo:andreoli-dino",
                    limit=1,
                    include_search_plan=True,
                )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            entry = payload["profiles"][0]["results"][0]

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(entry["planned_attempts"][0]["attempt_id"], "other-plan")
        self.assertEqual(entry["matched_planned_attempt_id"], "")
        self.assertEqual(entry["matched_planned_attempt_priority"], 0)
        self.assertEqual(entry["matched_planned_attempt_status"], "unmatched")
        self.assertEqual(entry["claims"][0]["review_status"], "unreviewed")

    def test_execute_first_planned_attempt_passes_runtime_limit_and_audit_mode(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            output_md = tmp_dir / "report.md"
            output_json = tmp_dir / "report.json"
            output_dir = tmp_dir / "schede"
            connector_kwargs: list[dict[str, object]] = []

            def create_connector(source: Source, **kwargs):
                connector_kwargs.append(dict(kwargs))
                return FakeConnector(source)

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "create_source_connector", side_effect=create_connector),
                patch.object(
                    profiles_runner,
                    "_planned_attempts_for_profile_source",
                    return_value=[
                        {
                            "source_id": "partigiani_italia",
                            "attempt_id": "fixture-plan",
                            "priority": 1,
                            "query_text": "Andreoli Dino",
                        }
                    ],
                ),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=real_sources_path(),
                    output_md=output_md,
                    output_json=output_json,
                    output_dir=output_dir,
                    source_id="partigiani_italia",
                    profile_id="person:purocielo:andreoli-dino",
                    limit=1,
                    execute_first_planned_attempt=True,
                )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            entry = payload["profiles"][0]["results"][0]

        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(payload["include_search_plan"])
        self.assertEqual(payload["planned_execution_mode"], "first_planned_attempt")
        self.assertEqual(payload["planned_attempt_execution_limit"], 1)
        self.assertEqual(entry["planned_execution_mode"], "first_planned_attempt")
        self.assertEqual(entry["planned_attempt_execution_limit"], 1)
        self.assertEqual(connector_kwargs[0]["max_search_attempts"], 1)
        self.assertEqual(entry["matched_planned_attempt_status"], "matched")
        self.assertIn("Audit piano ricerca", markdown)
        self.assertIn("Modalita': `first_planned_attempt`", markdown)
        self.assertIn("Tentativo: `fixture-plan`", markdown)
        self.assertEqual(entry["claims"][0]["review_status"], "unreviewed")

    def test_execute_first_planned_attempt_requires_source_and_limit(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            sources_path = write_sources_fixture(tmp_dir)

            result = profiles_runner.run_profiles_report(
                profiles_index=index_path,
                sources_yaml=sources_path,
                output_md=tmp_dir / "report.md",
                output_json=tmp_dir / "report.json",
                output_dir=tmp_dir / "schede",
                source_id="",
                profile_id="",
                limit=1,
                execute_first_planned_attempt=True,
            )

        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(result["error"], "planned_execution_requires_source_limit")

    def test_execute_first_planned_attempt_can_run_on_limited_batch_without_profile_id(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            sources_path = write_sources_fixture(tmp_dir)
            connector_kwargs: list[dict[str, object]] = []

            def connector_factory(source, **kwargs):
                connector_kwargs.append(kwargs)
                return FakeConnector(source)

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "create_source_connector", side_effect=connector_factory),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=sources_path,
                    output_md=tmp_dir / "report.md",
                    output_json=tmp_dir / "report.json",
                    output_dir=tmp_dir / "schede",
                    source_id="controlled",
                    profile_id="",
                    limit=1,
                    execute_first_planned_attempt=True,
                )

            payload = json.loads((tmp_dir / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(payload["planned_execution_mode"], "first_planned_attempt")
        self.assertEqual(payload["planned_attempt_execution_limit"], 1)
        self.assertEqual(connector_kwargs[0]["max_search_attempts"], 1)

    def test_acquires_online_detail_documents_for_offline_processing(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            sources_path = write_sources_fixture(tmp_dir)
            acquire_root = tmp_dir / "documenti_da_processare" / "fonti_online"

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "create_source_connector", side_effect=lambda source, **kwargs: FakeConnector(source)),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=sources_path,
                    output_md=tmp_dir / "report.md",
                    output_json=tmp_dir / "report.json",
                    output_dir=tmp_dir / "schede",
                    source_id="controlled",
                    profile_id="person:purocielo:andreoli-dino",
                    limit=1,
                    acquire_documents_root=acquire_root,
                )

            payload = json.loads((tmp_dir / "report.json").read_text(encoding="utf-8"))
            entry = payload["profiles"][0]["results"][0]
            acquired = entry["acquired_documents"][0]
            text_path = Path(acquired["file"])
            sidecar_path = Path(acquired["sidecar"])
            text_content = text_path.read_text(encoding="utf-8")
            sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["acquired_documents_count"], 1)
        self.assertEqual(payload["acquired_documents_summary"]["acquired_count"], 1)
        self.assertEqual(acquired["status"], "acquired")
        self.assertEqual(text_path.parent.name, "andreoli-dino")
        self.assertEqual(text_path.parent.parent.name, "controlled")
        self.assertIn("Scheda dettaglio online", text_content)
        self.assertEqual(sidecar["metadata"]["source_id"], "controlled")
        self.assertEqual(sidecar["metadata"]["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(sidecar["metadata"]["review_status"], "unreviewed")
        self.assertTrue(sidecar["metadata"]["claim_eligible"])
        self.assertEqual(sidecar["metadata"]["document_type"], "online_detail_document")
        self.assertEqual(sidecar["metadata"]["detail_assessment"], "claim_candidates_extracted")
        self.assertEqual(sidecar["metadata"]["detail_extracted_fields_json"], '{"death_date": "11 ottobre 1944"}')

    def test_acquisition_skips_empty_detail_documents(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            sources_path = write_sources_fixture(tmp_dir)
            acquire_root = tmp_dir / "documenti_da_processare" / "fonti_online"

            with (
                patch.object(profiles_runner, "validate_sources_registry_file", return_value=ValidValidation()),
                patch.object(profiles_runner, "create_source_connector", side_effect=lambda source, **kwargs: EmptyDetailConnector(source)),
            ):
                result = profiles_runner.run_profiles_report(
                    profiles_index=index_path,
                    sources_yaml=sources_path,
                    output_md=tmp_dir / "report.md",
                    output_json=tmp_dir / "report.json",
                    output_dir=tmp_dir / "schede",
                    source_id="controlled",
                    profile_id="person:purocielo:andreoli-dino",
                    limit=1,
                    acquire_documents_root=acquire_root,
                )

            payload = json.loads((tmp_dir / "report.json").read_text(encoding="utf-8"))
            acquired = payload["profiles"][0]["results"][0]["acquired_documents"][0]

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["acquired_documents_count"], 0)
        self.assertEqual(acquired["status"], "skipped_empty_raw_text")
        self.assertFalse(list(acquire_root.rglob("*.txt")))

    def test_unknown_profile_returns_controlled_error(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_fixture(tmp_dir)
            sources_path = write_sources_fixture(tmp_dir)
            result = profiles_runner.run_profiles_report(
                profiles_index=index_path,
                sources_yaml=sources_path,
                output_md=tmp_dir / "report.md",
                output_json=tmp_dir / "report.json",
                output_dir=tmp_dir / "schede",
                source_id="controlled",
                profile_id="person:purocielo:missing",
            )

        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(result["error"], "profile_not_found")


if __name__ == "__main__":
    unittest.main()
