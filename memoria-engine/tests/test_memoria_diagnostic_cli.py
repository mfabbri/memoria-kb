from __future__ import annotations

import os
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

from caduti_fonti_report.memoria_cli import REQUIRED_DATA_ROOT_DIRS, main  # noqa: E402
from caduti_fonti_report.workspace_storage import LocalWorkspaceStorage, PCloudStorageError  # noqa: E402


ROOT_DIR = Path(__file__).resolve().parents[1]


@contextmanager
def temp_workspace():
    base_dir = ROOT_DIR / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"memoria-cli-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def make_data_root(base_dir: Path, *, missing: tuple[str, ...] = ()) -> Path:
    data_root = base_dir / "external-data-root"
    data_root.mkdir(parents=True)
    for name in REQUIRED_DATA_ROOT_DIRS:
        if name not in missing:
            (data_root / name).mkdir()
    return data_root


def write_profiles_index(data_root: Path, *, missing_profile: bool = False) -> Path:
    profiles_dir = data_root / "ricerche" / "person_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / "purocielo-andreoli-dino.jsonld"
    if not missing_profile:
        profile_path.write_text(
            """
{
  "@type": "PersonResearchProfile",
  "@id": "person:purocielo:andreoli-dino",
  "metadata": {
    "profile_status": "preview",
    "review_status": "needs_review",
    "publication_status": "not_publishable_without_editorial_review"
  }
}
""".strip(),
            encoding="utf-8",
        )
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_path.write_text(
        """
{
  "@type": "PersonResearchProfileIndex",
  "profiles": [
    {
      "@id": "person:purocielo:andreoli-dino",
      "file": "purocielo-andreoli-dino.jsonld",
      "canonical_name": "Andreoli Dino"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    return index_path


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_review_workspace(data_root: Path) -> tuple[Path, Path]:
    weak_run = data_root / "risultati" / "runs" / "run-debole-pipeline"
    strong_run = data_root / "risultati" / "runs" / "run-forte-pipeline"
    write_json(weak_run / "historian_review" / "review_queue.json", {"items": [{"item_id": "review:item:weak"}]})
    write_json(
        strong_run / "historian_review" / "review_queue.json",
        {
            "items": [
                {
                    "item_id": "review:item:1",
                    "profile_id": "person:purocielo:test",
                    "source_document_id": "source-document:test",
                    "subject_kind": "claim",
                    "question": "Questo documento conferma il claim?",
                },
                {
                    "item_id": "review:item:2",
                    "profile_id": "person:purocielo:test",
                    "source_document_id": "source-document:test-2",
                    "subject_kind": "document",
                    "question": "Questo documento riguarda la persona?",
                },
            ]
        },
    )
    write_json(
        strong_run / "historian_review" / "review_decisions_summary.json",
        {
            "decisions": [
                {
                    "item_id": "review:item:1",
                    "profile_id": "person:purocielo:test",
                    "source_document_id": "source-document:test",
                    "subject_kind": "claim",
                    "selected_action": "confirm",
                    "decision_status": "accepted",
                }
            ]
        },
    )
    write_json(
        strong_run / "historian_review" / "review_session.json",
        {
            "profiles": [
                {
                    "profile_id": "person:purocielo:test",
                    "canonical_name": "Persona Test",
                    "review_item_count": 2,
                    "pending_decision_count": 2,
                }
            ]
        },
    )
    write_json(strong_run / "mvp_consolidated_review_ledger.json", {"profiles": [{"profile_id": "person:purocielo:test"}]})
    return weak_run, strong_run


def write_active_review_session(data_root: Path, strong_run: Path) -> Path:
    session_path = data_root / "database" / "memoria_review_session.active.json"
    write_json(
        session_path,
        {
            "@type": "MemoriaReviewSession",
            "selected_run_id": "run-forte-pipeline",
            "preview_only": True,
            "worklist_item_count": 2,
            "review_session_json": str(strong_run / "historian_review" / "review_session.json"),
            "review_queue_json": str(strong_run / "historian_review" / "review_queue.json"),
            "last_decision_item_number": 2,
            "last_decision_item_id": "review:item:2",
            "last_selected_action": "uncertain",
            "worklist": [
                {
                    "display_number": 1,
                    "profile_label": "Persona Test",
                    "item_id": "review:item:1",
                    "subject_kind": "claim",
                    "decision_status": "pending",
                    "selected_action": "pending",
                    "source_document_id": "source-document:test",
                    "raw_file": "documenti_da_processare/purocielo/test.pdf",
                    "metadata_file": "documenti_processati/purocielo/test.metadata.json",
                    "question": "Questo documento conferma il claim?",
                },
                {
                    "display_number": 2,
                    "profile_label": "Persona Test",
                    "item_id": "review:item:2",
                    "subject_kind": "document",
                    "decision_status": "accepted",
                    "selected_action": "uncertain",
                    "source_document_id": "source-document:test-2",
                    "question": "Questo documento riguarda la persona?",
                },
            ],
        },
    )
    return session_path


def write_consolidate_workspace(data_root: Path) -> tuple[Path, Path]:
    weak_run = data_root / "risultati" / "runs" / "run-senza-ledger-pipeline"
    strong_run = data_root / "risultati" / "runs" / "run-con-ledger-pipeline"
    write_json(
        weak_run / "historian_review" / "review_queue.json",
        {"items": [{"item_id": "review:item:weak"}]},
    )
    write_json(
        strong_run / "mvp_consolidated_review_ledger.json",
        {
            "profiles": [
                {"profile_id": "person:purocielo:test"},
                {"profile_id": "person:purocielo:altro"},
            ]
        },
    )
    write_json(
        strong_run / "historian_review" / "review_decisions_summary.json",
        {
            "decisions": [
                {
                    "item_id": "review:item:1",
                    "profile_id": "person:purocielo:test",
                    "source_document_id": "source-document:test",
                    "subject_kind": "claim",
                    "selected_action": "confirm",
                    "decision_status": "accepted",
                }
            ]
        },
    )
    write_json(
        strong_run / "historian_review" / "review_session.json",
        {"profiles": [{"profile_id": "person:purocielo:test"}]},
    )
    return weak_run, strong_run


def write_active_consolidate_session(data_root: Path, strong_run: Path) -> Path:
    session_path = data_root / "database" / "memoria_consolidate_session.active.json"
    write_json(
        session_path,
        {
            "@type": "MemoriaConsolidateSession",
            "selected_run_id": "run-con-ledger-pipeline",
            "selected_run_dir": str(strong_run),
            "selected_ledger_json": str(strong_run / "mvp_consolidated_review_ledger.json"),
            "preview_only": True,
            "discovery_score": 82,
            "discovery_reason": "ledger_json_available",
        },
    )
    return session_path


def write_sources_online_workspace(data_root: Path) -> None:
    registry_path = data_root / "ricerche" / "camalanca_fonti.yaml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        """
enabled_sources:
  - bundesarchiv_invenio
  - deutsche_dienststelle
sources:
  bundesarchiv_invenio:
    label: Bundesarchiv Invenio
  deutsche_dienststelle:
    label: Deutsche Dienststelle
  altro_archivio:
    label: Altro archivio
""".strip(),
        encoding="utf-8",
    )
    profiles_dir = data_root / "ricerche" / "person_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        profiles_dir / "purocielo.index.jsonld",
        {
            "@type": "PersonResearchProfileIndex",
            "profiles": [
                {"@id": "person:purocielo:test", "file": "test.jsonld"},
                {"@id": "person:purocielo:altro", "file": "altro.jsonld"},
            ],
        },
    )


def write_active_sources_online_session(data_root: Path) -> Path:
    session_path = data_root / "database" / "memoria_sources_online_session.active.json"
    write_json(
        session_path,
        {
            "@type": "MemoriaSourcesOnlineSession",
            "workspace_root": str(data_root),
            "preview_only": True,
            "subject": {"kind": "place", "id": "place:purocielo", "label": "Purocielo"},
            "candidate_query": {"seed": "Purocielo", "status": "candidate_unreviewed"},
            "proposed_intake_path": str(data_root / "documenti_da_processare" / "sources_online" / "place" / "purocielo"),
            "candidate_sources": [
                {"source_id": "bundesarchiv_invenio", "status": "candidate"},
                {"source_id": "deutsche_dienststelle", "status": "candidate"},
            ],
        },
    )
    return session_path


def write_sources_offline_workspace(data_root: Path) -> None:
    (data_root / "documenti_da_processare" / "mvp_purocielo").mkdir(parents=True)
    (data_root / "documenti_da_processare" / "note_sciolte.txt").write_text("fixture", encoding="utf-8")
    (data_root / "documenti_processati" / "mvp_purocielo").mkdir(parents=True)
    (data_root / "documenti_processati" / "manifest.json").write_text("{}", encoding="utf-8")


def write_mvp_demo_descriptor(data_root: Path) -> Path:
    run_dir = data_root / "risultati" / "runs" / "golden-run-pipeline"
    reconciliation = run_dir / "mvp_reconciliation_table.md"
    verified_facts = run_dir / "historian_review" / "verified_facts.preview.json"
    reconciliation.parent.mkdir(parents=True, exist_ok=True)
    verified_facts.parent.mkdir(parents=True, exist_ok=True)
    reconciliation.write_text("# Reconciliation\n", encoding="utf-8")
    write_json(verified_facts, {"facts": []})
    descriptor_path = data_root / "database" / "memoria_mvp_demo.active.json"
    write_json(
        descriptor_path,
        {
            "contract_version": "memoria_mvp_demo.v1",
            "status": "ready_for_internal_demo",
            "preview_only": True,
            "publication_status": "not_publishable_without_human_review",
            "run_id": "golden-run-pipeline",
            "run_dir": str(run_dir),
            "primary_profile_ids": ["person:purocielo:andreoli-dino"],
            "contrast_profile_ids": ["person:purocielo:balboni-william"],
            "source_document_ids": [
                "legacy_csv:a4ac96061a2381b5",
                "local_docx:4c2ad1d2ab937913",
                "partigiani_italia:b45553cd6b1673d8",
            ],
            "source_families": ["legacy_csv", "local_docx", "partigiani_italia"],
            "artifacts": {
                "reconciliation_table": str(reconciliation),
                "verified_facts_preview": str(verified_facts),
                "profile_patch_preview": str(run_dir / "historian_review" / "profile_patch.preview.json"),
            },
            "safety": {
                "no_canonical_profile_patch_applied": True,
                "no_publication_output": True,
                "publication_ready": False,
                "real_data_not_copied_to_git": True,
            },
        },
    )
    return descriptor_path


def write_mvp_demo_build_workspace(data_root: Path) -> Path:
    run_dir = data_root / "risultati" / "runs" / "golden-run-pipeline"
    write_json(
        run_dir / "mvp_consolidated_review_ledger.json",
        {
            "@type": "MvpConsolidatedReviewLedger",
            "profiles": [
                {
                    "profile_id": "person:purocielo:andreoli-dino",
                    "canonical_name": "Andreoli Dino",
                    "documents": [
                        {"source_document_id": "legacy_csv:a4ac96061a2381b5", "source_id": "legacy_csv"},
                        {"source_document_id": "local_docx:4c2ad1d2ab937913", "source_id": "local_docx"},
                    ],
                    "candidate_evidence_claims": [
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "source_document_id": "legacy_csv:a4ac96061a2381b5",
                            "source_id": "legacy_csv",
                            "field": "death.place",
                            "value": "Purocielo",
                            "normalized_value": "purocielo",
                            "extraction_method": "legacy_csv_row",
                            "review_status": "accepted",
                        },
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "source_document_id": "local_docx:4c2ad1d2ab937913",
                            "source_id": "local_docx",
                            "field": "death.place",
                            "value": "Purocielo",
                            "normalized_value": "purocielo",
                            "extraction_method": "docx_segment",
                            "review_status": "accepted",
                        },
                    ],
                }
            ],
        },
    )
    review_dir = run_dir / "historian_review"
    write_json(review_dir / "review_queue.json", {"items": [{"item_id": "demo-review-1"}]})
    write_json(
        review_dir / "review_decisions_summary.json",
        {"decisions": [{"item_id": "demo-review-1", "selected_action": "confirm", "decision_status": "accepted"}]},
    )
    write_json(review_dir / "verified_facts.preview.json", {"fact_count": 1})
    write_json(review_dir / "profile_patch.preview.json", {"patch_count": 1, "operation_count": 1})
    return run_dir


def make_project_workspace(tmp_dir: Path) -> tuple[Path, Path]:
    project_root = tmp_dir / "project"
    engine_root = project_root / "memoria-engine"
    workspace_root = project_root / "memoria-workspace"
    engine_root.mkdir(parents=True)
    workspace_root.mkdir()
    return engine_root, workspace_root


def run_cli(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    old_cwd = Path.cwd()
    try:
        if cwd is not None:
            os.chdir(cwd)
        with patch.dict(os.environ, env or {}, clear=True), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            code = main(list(args))
    finally:
        os.chdir(old_cwd)
    return code, stdout.getvalue(), stderr.getvalue()


class MemoriaDiagnosticCliTests(unittest.TestCase):
    def test_workspace_status_reports_pcloud_selected_from_env_without_printing_token(self) -> None:
        with temp_workspace() as tmp_dir:
            engine_root, workspace_root = make_project_workspace(tmp_dir)
            (workspace_root / "manifest.yml").write_text(
                """
workspace_id: test
repository_role: descriptor_only
workspace:
  provider: local
  root: P:/local/fallback
  providers:
    pcloud:
      app_name: MemoriaStorage
      root: /MeMoRiA
      folderid: 123
      api_host: eapi.pcloud.com
      client_id_ref: MEMORIA_PCLOUD_CLIENT_ID
      client_secret_ref: MEMORIA_PCLOUD_CLIENT_SECRET
      access_token_ref: MEMORIA_PCLOUD_ACCESS_TOKEN
      mode: read_only
""".strip(),
                encoding="utf-8",
            )

            code, stdout, stderr = run_cli(
                "workspace",
                "status",
                cwd=engine_root,
                env={
                    "MEMORIA_WORKSPACE_PROVIDER": "pcloud",
                    "MEMORIA_PCLOUD_CLIENT_ID": "client-id",
                    "MEMORIA_PCLOUD_CLIENT_SECRET": "client-secret",
                    "MEMORIA_PCLOUD_ACCESS_TOKEN": "secret-token",
                    "MEMORIA_PCLOUD_API_HOST": "eapi.pcloud.com",
                    "MEMORIA_PCLOUD_ROOT": "/MeMoRiA",
                    "MEMORIA_PCLOUD_FOLDER_ID": "123",
                },
            )

            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("provider: pcloud", stdout)
            self.assertIn("pcloud_app_name: MemoriaStorage", stdout)
            self.assertIn("pcloud_api_host: eapi.pcloud.com", stdout)
            self.assertIn("pcloud_root: /MeMoRiA", stdout)
            self.assertIn("pcloud_folderid: 123", stdout)
            self.assertIn("pcloud_client_id_configured: true", stdout)
            self.assertIn("pcloud_client_secret_configured: true", stdout)
            self.assertIn("pcloud_access_token_configured: true", stdout)
            self.assertNotIn("secret-token", stdout)
            self.assertNotIn("client-secret", stdout)

    def test_workspace_pcloud_auth_url_uses_client_id_without_printing_secret(self) -> None:
        with temp_workspace() as tmp_dir:
            engine_root, workspace_root = make_project_workspace(tmp_dir)
            (workspace_root / "manifest.yml").write_text(
                """
workspace_id: test
repository_role: descriptor_only
workspace:
  provider: pcloud
  providers:
    pcloud:
      client_id_ref: MEMORIA_PCLOUD_CLIENT_ID
      client_secret_ref: MEMORIA_PCLOUD_CLIENT_SECRET
""".strip(),
                encoding="utf-8",
            )

            code, stdout, stderr = run_cli(
                "workspace",
                "pcloud-auth-url",
                "--redirect-uri",
                "http://localhost/callback",
                cwd=engine_root,
                env={
                    "MEMORIA_PCLOUD_CLIENT_ID": "client-id",
                    "MEMORIA_PCLOUD_CLIENT_SECRET": "client-secret",
                },
            )

            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("https://my.pcloud.com/oauth2/authorize?", stdout)
            self.assertIn("client_id=client-id", stdout)
            self.assertIn("response_type=code", stdout)
            self.assertNotIn("client-secret", stdout)

    def test_workspace_status_list_reports_pcloud_errors_without_traceback(self) -> None:
        with temp_workspace() as tmp_dir:
            engine_root, workspace_root = make_project_workspace(tmp_dir)
            (workspace_root / "manifest.yml").write_text(
                """
workspace_id: test
repository_role: descriptor_only
workspace:
  provider: pcloud
  providers:
    pcloud:
      access_token_ref: MEMORIA_PCLOUD_ACCESS_TOKEN
""".strip(),
                encoding="utf-8",
            )

            with patch(
                "caduti_fonti_report.memoria_cli.build_workspace_storage",
                side_effect=PCloudStorageError("pCloud listfolder failed with result 2000."),
            ):
                code, stdout, stderr = run_cli(
                    "workspace",
                    "status",
                    "--list",
                    ".",
                    cwd=engine_root,
                    env={"MEMORIA_PCLOUD_ACCESS_TOKEN": "secret-token"},
                )

            self.assertEqual(code, 2)
            self.assertIn("provider: pcloud", stdout)
            self.assertIn("ERROR pCloud listfolder failed with result 2000.", stderr)
            self.assertNotIn("Traceback", stderr)

    def test_workspace_pcloud_exchange_code_saves_token_without_printing_it(self) -> None:
        with temp_workspace() as tmp_dir:
            engine_root, workspace_root = make_project_workspace(tmp_dir)
            (workspace_root / "manifest.yml").write_text(
                """
workspace_id: test
repository_role: descriptor_only
workspace:
  provider: pcloud
  providers:
    pcloud:
      api_host: eapi.pcloud.com
      client_id_ref: MEMORIA_PCLOUD_CLIENT_ID
      client_secret_ref: MEMORIA_PCLOUD_CLIENT_SECRET
      access_token_ref: MEMORIA_PCLOUD_ACCESS_TOKEN
""".strip(),
                encoding="utf-8",
            )
            env_path = engine_root / ".env"
            env_path.write_text(
                """
MEMORIA_WORKSPACE_PROVIDER=pcloud
MEMORIA_PCLOUD_CLIENT_ID=client-id
MEMORIA_PCLOUD_CLIENT_SECRET=client-secret
""".strip()
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "caduti_fonti_report.memoria_cli.exchange_pcloud_oauth_code",
                return_value=type("Token", (), {"access_token": "oauth-token", "token_type": "bearer", "uid": "123", "api_host": "eapi.pcloud.com"})(),
            ):
                code, stdout, stderr = run_cli(
                    "workspace",
                    "pcloud-exchange-code",
                    "--code",
                    "auth-code",
                    "--save-env",
                    cwd=engine_root,
                    env={
                        "MEMORIA_WORKSPACE_PROVIDER": "pcloud",
                        "MEMORIA_PCLOUD_CLIENT_ID": "client-id",
                        "MEMORIA_PCLOUD_CLIENT_SECRET": "client-secret",
                    },
                )

            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Access token pCloud salvato in:", stdout)
            self.assertNotIn("oauth-token", stdout)
            self.assertNotIn("client-secret", stdout)
            env_text = env_path.read_text(encoding="utf-8")
            self.assertIn("MEMORIA_PCLOUD_ACCESS_TOKEN=oauth-token", env_text)
            self.assertIn("MEMORIA_PCLOUD_API_HOST=eapi.pcloud.com", env_text)

    def test_inventory_reports_missing_required_folder_without_recursing(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir, missing=("secure",))

            code, stdout, stderr = run_cli("inventory", "--data-root", str(data_root))

            self.assertEqual(code, 1)
            self.assertIn("OK risultati", stdout)
            self.assertIn("MISSING secure", stdout)
            self.assertEqual(stderr, "")

    def test_inventory_without_options_keeps_required_folder_check(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)

            code, stdout, stderr = run_cli("inventory", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Data root:", stdout)
            self.assertIn("OK risultati", stdout)
            self.assertIn("OK documenti_processati", stdout)
            self.assertNotIn("top_level_files", stdout)
            self.assertEqual(stderr, "")

    def test_inventory_section_risultati_reports_top_level_summary(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            risultati = data_root / "risultati"
            (risultati / "run-a").mkdir()
            (risultati / "run-b").mkdir()
            (risultati / "summary.txt").write_text("not read by inventory", encoding="utf-8")

            code, stdout, stderr = run_cli("inventory", "--data-root", str(data_root), "--section", "risultati")

            self.assertEqual(code, 0)
            self.assertIn("Section: risultati", stdout)
            self.assertIn("exists: true", stdout)
            self.assertIn("top_level_files: 1", stdout)
            self.assertIn("top_level_dirs: 2", stdout)
            self.assertIn("- run-a/", stdout)
            self.assertIn("- summary.txt", stdout)
            self.assertEqual(stderr, "")

    def test_inventory_section_all_reports_supported_sections(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            (data_root / "risultati" / "run-a").mkdir()
            (data_root / "documenti_processati" / "processed.txt").write_text("x", encoding="utf-8")
            (data_root / "documenti_da_processare" / "batch").mkdir()

            code, stdout, stderr = run_cli("inventory", "--data-root", str(data_root), "--section", "all")

            self.assertEqual(code, 0)
            self.assertIn("Section: risultati", stdout)
            self.assertIn("Section: documenti_processati", stdout)
            self.assertIn("Section: documenti_da_processare", stdout)
            self.assertIn("- processed.txt", stdout)
            self.assertEqual(stderr, "")

    def test_inventory_markdown_output_is_readable(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            (data_root / "risultati" / "run-a").mkdir()

            code, stdout, stderr = run_cli(
                "inventory",
                "--data-root",
                str(data_root),
                "--section",
                "risultati",
                "--output",
                "markdown",
            )

            self.assertEqual(code, 0)
            self.assertIn("# Memoria inventory", stdout)
            self.assertIn("## risultati", stdout)
            self.assertIn("- Top-level directories: 1", stdout)
            self.assertIn("- `run-a/`", stdout)
            self.assertEqual(stderr, "")

    def test_inventory_markdown_output_without_section_keeps_required_folder_check(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)

            code, stdout, stderr = run_cli("inventory", "--data-root", str(data_root), "--output", "markdown")

            self.assertEqual(code, 0)
            self.assertIn("# Memoria inventory", stdout)
            self.assertIn("## Required folders", stdout)
            self.assertIn("- [x] `risultati`", stdout)
            self.assertIn("- [x] `documenti_processati`", stdout)
            self.assertEqual(stderr, "")

    def test_inventory_section_missing_returns_error_code(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir, missing=("risultati",))

            code, stdout, stderr = run_cli("inventory", "--data-root", str(data_root), "--section", "risultati")

            self.assertEqual(code, 1)
            self.assertIn("Section: risultati", stdout)
            self.assertIn("exists: false", stdout)
            self.assertIn("top_level_files: 0", stdout)
            self.assertEqual(stderr, "")

    def test_inventory_section_does_not_use_recursive_deep_scan(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            nested = data_root / "risultati" / "top" / "nested"
            nested.mkdir(parents=True)
            (nested / "deep.txt").write_text("deep content", encoding="utf-8")

            with patch.object(Path, "rglob", side_effect=AssertionError("recursive scan is forbidden")):
                code, stdout, stderr = run_cli("inventory", "--data-root", str(data_root), "--section", "risultati")

            self.assertEqual(code, 0)
            self.assertIn("- top/", stdout)
            self.assertNotIn("nested", stdout)
            self.assertNotIn("deep.txt", stdout)
            self.assertEqual(stderr, "")

    def test_doctor_checks_sibling_repositories(self) -> None:
        with temp_workspace() as tmp_dir:
            project_root = tmp_dir / "project"
            engine_root = project_root / "memoria-engine"
            engine_root.mkdir(parents=True)
            for repo_name in (
                "memoria-bootstrap",
                "memoria-knowledge",
                "memoria-rules",
                "memoria-sources",
                "memoria-workspace",
            ):
                (project_root / repo_name).mkdir()
            data_root = make_data_root(tmp_dir)

            code, stdout, stderr = run_cli("doctor", "--data-root", str(data_root), cwd=engine_root)

            self.assertEqual(code, 0)
            self.assertIn("OK data-root", stdout)
            self.assertIn("OK memoria-bootstrap", stdout)
            self.assertIn("OK memoria-engine", stdout)
            self.assertEqual(stderr, "")

    def test_doctor_uses_local_workspace_storage(self) -> None:
        with temp_workspace() as tmp_dir:
            project_root = tmp_dir / "project"
            engine_root = project_root / "memoria-engine"
            engine_root.mkdir(parents=True)
            for repo_name in (
                "memoria-bootstrap",
                "memoria-knowledge",
                "memoria-rules",
                "memoria-sources",
                "memoria-workspace",
            ):
                (project_root / repo_name).mkdir()
            data_root = make_data_root(tmp_dir)

            with patch(
                "caduti_fonti_report.memoria_cli.LocalWorkspaceStorage",
                wraps=LocalWorkspaceStorage,
            ) as storage_cls:
                code, stdout, stderr = run_cli("doctor", "--data-root", str(data_root), cwd=engine_root)

            self.assertEqual(code, 0)
            self.assertIn("OK data-root", stdout)
            self.assertGreaterEqual(storage_cls.call_count, 2)
            self.assertEqual(stderr, "")

    def test_profiles_status_resolves_index_from_data_root(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            index_path = write_profiles_index(data_root)

            code, stdout, stderr = run_cli("profiles", "status", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn(f"Profiles index: {index_path}", stdout)
            self.assertIn("exists: true", stdout)
            self.assertIn("index_profiles: 1", stdout)
            self.assertIn("loaded_profiles: 1", stdout)
            self.assertIn("- preview: 1", stdout)
            self.assertIn("- needs_review: 1", stdout)
            self.assertIn("- not_publishable_without_editorial_review: 1", stdout)
            self.assertEqual(stderr, "")

    def test_profiles_status_does_not_fallback_to_engine_ricerche(self) -> None:
        with temp_workspace() as tmp_dir:
            project_root = tmp_dir / "project"
            engine_root = project_root / "memoria-engine"
            engine_profiles = engine_root / "ricerche" / "person_profiles"
            engine_profiles.mkdir(parents=True)
            write_profiles_index(engine_root)
            data_root = make_data_root(tmp_dir / "external")

            code, stdout, stderr = run_cli("profiles", "status", "--data-root", str(data_root), cwd=engine_root)

            self.assertEqual(code, 1)
            self.assertIn(str(data_root / "ricerche" / "person_profiles" / "purocielo.index.jsonld"), stdout)
            self.assertNotIn(str(engine_profiles), stdout)
            self.assertIn("Indice profili non trovato", stderr)

    def test_profiles_status_reports_missing_profile_files(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_profiles_index(data_root, missing_profile=True)

            code, stdout, stderr = run_cli("profiles", "status", "--data-root", str(data_root))

            self.assertEqual(code, 1)
            self.assertIn("index_profiles: 1", stdout)
            self.assertIn("loaded_profiles: 0", stdout)
            self.assertIn("missing_profile_files: 1", stdout)
            self.assertIn("- purocielo-andreoli-dino.jsonld", stdout)
            self.assertEqual(stderr, "")

    def test_profiles_status_markdown_output_is_readable(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_profiles_index(data_root)

            code, stdout, stderr = run_cli(
                "profiles",
                "status",
                "--data-root",
                str(data_root),
                "--output",
                "markdown",
            )

            self.assertEqual(code, 0)
            self.assertIn("# Memoria profiles status", stdout)
            self.assertIn("## Profile status", stdout)
            self.assertIn("- `preview`: 1", stdout)
            self.assertIn("## Review status", stdout)
            self.assertEqual(stderr, "")

    def test_review_discover_reports_candidate_runs_without_creating_session(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_review_workspace(data_root)
            session_path = data_root / "database" / "memoria_review_session.active.json"

            code, stdout, stderr = run_cli("review", "discover", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria review discovery", stdout)
            self.assertIn("Modalita: preview-only/read-only", stdout)
            self.assertIn("[1] run-forte-pipeline", stdout)
            self.assertIn("Decisioni storiche sostanziali: 1", stdout)
            self.assertIn("run-debole-pipeline", stdout)
            self.assertIn("memoria review status", stdout)
            self.assertFalse(session_path.exists())
            self.assertEqual(stderr, "")

    def test_review_status_falls_back_to_discovery_when_session_is_missing(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_review_workspace(data_root)

            code, stdout, stderr = run_cli("review", "status", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria review discovery", stdout)
            self.assertIn("[1] run-forte-pipeline", stdout)
            self.assertEqual(stderr, "")

    def test_review_status_and_work_read_existing_active_session(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            _, strong_run = write_review_workspace(data_root)
            write_active_review_session(data_root, strong_run)

            status_code, status_stdout, status_stderr = run_cli("review", "status", "--data-root", str(data_root))
            work_code, work_stdout, work_stderr = run_cli("review", "work", "--data-root", str(data_root))

            self.assertEqual(status_code, 0)
            self.assertIn("Me.Mo.Ria review status", status_stdout)
            self.assertIn("Run attiva: run-forte-pipeline", status_stdout)
            self.assertIn("Decisioni sessione: 1/2", status_stdout)
            self.assertIn("Pendenti: 1", status_stdout)
            self.assertIn("Ultima decisione: [2] review:item:2 -> uncertain", status_stdout)
            self.assertEqual(status_stderr, "")
            self.assertEqual(work_code, 0)
            self.assertIn("Me.Mo.Ria review work", work_stdout)
            self.assertIn("[1] Persona Test | claim | pending", work_stdout)
            self.assertIn("review:item:1", work_stdout)
            self.assertIn("File sorgente: documenti_da_processare/purocielo/test.pdf", work_stdout)
            self.assertIn("Metadata: documenti_processati/purocielo/test.metadata.json", work_stdout)
            self.assertIn("Questo documento conferma il claim?", work_stdout)
            self.assertIn("comando Python read-only", work_stdout)
            self.assertEqual(work_stderr, "")

    def test_review_decisions_falls_back_to_recommended_run_without_creating_session(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_review_workspace(data_root)
            session_path = data_root / "database" / "memoria_review_session.active.json"

            code, stdout, stderr = run_cli("review", "decisions", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria review decisions", stdout)
            self.assertIn("Origine: run consigliata", stdout)
            self.assertIn("Run: run-forte-pipeline", stdout)
            self.assertIn("Presente: true", stdout)
            self.assertIn("Decisioni totali: 1", stdout)
            self.assertIn("Decisioni storiche sostanziali: 1", stdout)
            self.assertIn("selected_action:", stdout)
            self.assertIn("- confirm: 1", stdout)
            self.assertIn("decision_status:", stdout)
            self.assertIn("- accepted: 1", stdout)
            self.assertFalse(session_path.exists())
            self.assertEqual(stderr, "")

    def test_review_decisions_reads_existing_active_session_summary(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            _, strong_run = write_review_workspace(data_root)
            write_active_review_session(data_root, strong_run)

            code, stdout, stderr = run_cli("review", "decisions", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria review decisions", stdout)
            self.assertIn("Origine: sessione attiva", stdout)
            self.assertIn("Run: run-forte-pipeline", stdout)
            self.assertIn(str(strong_run / "historian_review" / "review_decisions_summary.json"), stdout)
            self.assertIn("Decisioni totali: 1", stdout)
            self.assertIn("subject_kind:", stdout)
            self.assertIn("- claim: 1", stdout)
            self.assertIn("non registra decisioni", stdout)
            self.assertEqual(stderr, "")

    def test_mvp_status_composes_read_only_demo_walkthrough(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_sources_online_workspace(data_root)
            write_profiles_index(data_root)
            _, review_run = write_review_workspace(data_root)
            write_active_review_session(data_root, review_run)
            _, consolidate_run = write_consolidate_workspace(data_root)
            write_active_consolidate_session(data_root, consolidate_run)
            write_sources_offline_workspace(data_root)
            write_mvp_demo_descriptor(data_root)

            code, stdout, stderr = run_cli("mvp", "status", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria MVP demo status", stdout)
            self.assertIn("Modalita: preview-only/read-only", stdout)
            self.assertIn("Golden run:", stdout)
            self.assertIn("Descriptor presente: true", stdout)
            self.assertIn("Status: ready_for_internal_demo", stdout)
            self.assertIn("Run canonica: golden-run-pipeline", stdout)
            self.assertIn("Artefatti presenti: 2", stdout)
            self.assertIn("Preview-only: true", stdout)
            self.assertIn("Publication ready: false", stdout)
            self.assertIn("Publication status: not_publishable_without_human_review", stdout)
            self.assertIn("Profili caricati: 1/1", stdout)
            self.assertIn("Review:", stdout)
            self.assertIn("Decisioni: 1", stdout)
            self.assertIn("Decisioni storiche sostanziali: 1", stdout)
            self.assertIn("Consolidamento:", stdout)
            self.assertIn("Profili ledger attivo: 2", stdout)
            self.assertIn("Registry online presente: true", stdout)
            self.assertIn("Fonti online abilitate:", stdout)
            self.assertIn("Offline intake: 1 cartelle, 1 file", stdout)
            self.assertIn("memoria mvp demo", stdout)
            self.assertIn("memoria mvp demo-build", stdout)
            self.assertIn("memoria review decisions", stdout)
            self.assertIn("memoria sources offline status", stdout)
            self.assertIn("non genera report, non crea run", stdout)
            self.assertEqual(stderr, "")

    def test_mvp_demo_reports_missing_descriptor_without_creating_it(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            descriptor_path = data_root / "database" / "memoria_mvp_demo.active.json"

            code, stdout, stderr = run_cli("mvp", "demo", "--data-root", str(data_root))

            self.assertEqual(code, 1)
            self.assertIn("Me.Mo.Ria MVP demo descriptor", stdout)
            self.assertIn("Presente: false", stdout)
            self.assertIn("JSON valido: false", stdout)
            self.assertIn(str(descriptor_path), stdout)
            self.assertIn("non crea il descrittore", stdout)
            self.assertFalse(descriptor_path.exists())
            self.assertEqual(stderr, "")

    def test_mvp_demo_reads_descriptor_and_artifact_presence_read_only(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            descriptor_path = write_mvp_demo_descriptor(data_root)

            code, stdout, stderr = run_cli("mvp", "demo", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria MVP demo descriptor", stdout)
            self.assertIn(str(descriptor_path), stdout)
            self.assertIn("Contract version: memoria_mvp_demo.v1", stdout)
            self.assertIn("Status: ready_for_internal_demo", stdout)
            self.assertIn("Preview-only: true", stdout)
            self.assertIn("Run: golden-run-pipeline", stdout)
            self.assertIn("Run dir presente: true", stdout)
            self.assertIn("Profili principali: 1", stdout)
            self.assertIn("- person:purocielo:andreoli-dino", stdout)
            self.assertIn("Documenti sorgente: 3", stdout)
            self.assertIn("- partigiani_italia:b45553cd6b1673d8", stdout)
            self.assertIn("Famiglie fonte: legacy_csv, local_docx, partigiani_italia", stdout)
            self.assertIn("reconciliation_table:", stdout)
            self.assertIn("presente=true", stdout)
            self.assertIn("profile_patch_preview:", stdout)
            self.assertIn("presente=false", stdout)
            self.assertIn("no_canonical_profile_patch_applied: true", stdout)
            self.assertIn("non crea run, non rigenera artefatti", stdout)
            self.assertEqual(stderr, "")

    def test_mvp_demo_build_dry_run_and_explicit_outputs(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            run_dir = write_mvp_demo_build_workspace(data_root)
            descriptor_path = data_root / "database" / "memoria_mvp_demo.active.json"
            reconciliation_path = run_dir / "mvp_demo_reconciliation_table.md"

            code, stdout, stderr = run_cli(
                "mvp",
                "demo-build",
                "--data-root",
                str(data_root),
                "--run-id",
                "golden-run-pipeline",
            )

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria MVP demo descriptor build", stdout)
            self.assertIn("Descriptor output: skipped", stdout)
            self.assertIn("Reconciliation output: skipped", stdout)
            self.assertIn("Readiness: ready_for_internal_demo", stdout)
            self.assertIn("Readiness errors: 0", stdout)
            self.assertIn("Readiness warnings: 1", stdout)
            self.assertIn("- WARNING selected_documents_without_reconciliation_rows", stdout)
            self.assertIn("Azioni successive:", stdout)
            self.assertIn(
                "Collegare ai profili demo selezionati i documenti T29 assenti dal perimetro: "
                "partigiani_italia:b45553cd6b1673d8, partigiani_italia:b6b3c9e526723a27.",
                stdout,
            )
            self.assertIn("Famiglie selezionate: legacy_csv, local_docx, partigiani_italia", stdout)
            self.assertIn("Famiglie coperte: legacy_csv, local_docx", stdout)
            self.assertIn("Famiglie mancanti: partigiani_italia", stdout)
            self.assertIn("Documenti coperti: 2/4", stdout)
            self.assertIn("Diagnostica famiglie:", stdout)
            self.assertIn(
                "- FAMILY_STATUS legacy_csv | coverage=covered | blocked_by=covered | selected_documents=1 | "
                "covered_documents=1 | missing_documents=0",
                stdout,
            )
            self.assertIn(
                "- FAMILY_STATUS partigiani_italia | coverage=missing_reconciliation | "
                "blocked_by=candidate_claims_missing | "
                "selected_documents=2 | covered_documents=0 | missing_documents=2",
                stdout,
            )
            self.assertIn("Diagnostica documenti:", stdout)
            self.assertIn(
                "- DOCUMENT_STATUS legacy_csv:a4ac96061a2381b5 | family=legacy_csv | "
                "reconciliation=covered | profile_scope=present_in_selected_profiles | "
                "claims=claims_in_selected_profiles | blocked_by=covered",
                stdout,
            )
            self.assertIn(
                "- DOCUMENT_STATUS partigiani_italia:b45553cd6b1673d8 | family=partigiani_italia | "
                "reconciliation=missing_reconciliation_row | profile_scope=absent_from_selected_profiles | "
                "claims=no_candidate_claims | blocked_by=candidate_claims_missing",
                stdout,
            )
            self.assertIn("Piano riallineamento preview:", stdout)
            self.assertIn(
                "- ALIGNMENT_STEP 1 | action=produce_candidate_claims | "
                "document=partigiani_italia:b45553cd6b1673d8 | family=partigiani_italia | "
                "reason=candidate_claims_missing",
                stdout,
            )
            self.assertIn(
                "- ALIGNMENT_STEP 2 | action=produce_candidate_claims | "
                "document=partigiani_italia:b6b3c9e526723a27 | family=partigiani_italia | "
                "reason=candidate_claims_missing",
                stdout,
            )
            self.assertIn("- COVERED_DOCUMENT legacy_csv:a4ac96061a2381b5", stdout)
            self.assertIn("- COVERED_DOCUMENT local_docx:4c2ad1d2ab937913", stdout)
            self.assertIn("- MISSING_DOCUMENT partigiani_italia:b45553cd6b1673d8", stdout)
            self.assertIn("- MISSING_DOCUMENT partigiani_italia:b6b3c9e526723a27", stdout)
            self.assertIn("- MISSING_DOCUMENT_ABSENT_FROM_SELECTED_PROFILES partigiani_italia:b45553cd6b1673d8", stdout)
            self.assertIn("- MISSING_DOCUMENT_WITHOUT_CANDIDATE_CLAIMS partigiani_italia:b6b3c9e526723a27", stdout)
            self.assertIn("Righe riconciliazione: 2", stdout)
            self.assertIn("- corroborated: 2", stdout)
            self.assertIn("Decisioni sostanziali: 1", stdout)
            self.assertIn("Verified facts preview: 1", stdout)
            self.assertIn("ProfilePatch preview: 1", stdout)
            self.assertIn("scrive solo sugli output espliciti", stdout)
            self.assertFalse(descriptor_path.exists())
            self.assertFalse(reconciliation_path.exists())
            self.assertEqual(stderr, "")

            code, stdout, stderr = run_cli(
                "mvp",
                "demo-build",
                "--data-root",
                str(data_root),
                "--run-id",
                "golden-run-pipeline",
                "--output-descriptor",
                str(descriptor_path),
                "--output-reconciliation",
                str(reconciliation_path),
            )

            self.assertEqual(code, 0)
            self.assertIn(str(descriptor_path), stdout)
            self.assertIn(str(reconciliation_path), stdout)
            self.assertTrue(descriptor_path.exists())
            self.assertTrue(reconciliation_path.exists())
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            self.assertEqual(descriptor["contract_version"], "memoria_mvp_demo.v1")
            self.assertTrue(descriptor["preview_only"])
            self.assertEqual(descriptor["readiness"]["status"], "ready_for_internal_demo")
            self.assertEqual(descriptor["readiness"]["warning_count"], 1)
            self.assertEqual(descriptor["readiness"]["missing_source_families"], ["partigiani_italia"])
            self.assertEqual(descriptor["readiness"]["covered_document_count"], 2)
            self.assertFalse(descriptor["safety"]["applies_profile_patch"])
            self.assertIn("death.place", reconciliation_path.read_text(encoding="utf-8"))
            self.assertEqual(stderr, "")

    def test_mvp_demo_build_blocked_readiness_does_not_write_outputs(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            run_dir = write_mvp_demo_build_workspace(data_root)
            descriptor_path = data_root / "database" / "memoria_mvp_demo.active.json"
            reconciliation_path = run_dir / "mvp_demo_reconciliation_table.md"

            code, stdout, stderr = run_cli(
                "mvp",
                "demo-build",
                "--data-root",
                str(data_root),
                "--run-id",
                "golden-run-pipeline",
                "--source-document-id",
                "legacy_csv:a4ac96061a2381b5",
                "--output-descriptor",
                str(descriptor_path),
                "--output-reconciliation",
                str(reconciliation_path),
            )

            self.assertEqual(code, 1)
            self.assertIn("Readiness: blocked_for_internal_demo", stdout)
            self.assertIn("- ERROR multi_source_reconciliation_requires_at_least_two_source_families", stdout)
            self.assertIn("Aggiungere alla riconciliazione della run canonica claim da una seconda famiglia fonte T29.", stdout)
            self.assertIn(
                "- FAMILY_STATUS legacy_csv | coverage=covered | blocked_by=covered | selected_documents=1 | "
                "covered_documents=1 | missing_documents=0",
                stdout,
            )
            self.assertIn(
                "- DOCUMENT_STATUS legacy_csv:a4ac96061a2381b5 | family=legacy_csv | "
                "reconciliation=covered | profile_scope=present_in_selected_profiles | "
                "claims=claims_in_selected_profiles | blocked_by=covered",
                stdout,
            )
            self.assertIn("- COVERED_DOCUMENT legacy_csv:a4ac96061a2381b5", stdout)
            self.assertIn("Piano riallineamento preview:", stdout)
            self.assertIn("- none", stdout)
            self.assertIn(f"Descriptor output: {descriptor_path} (blocked, not written)", stdout)
            self.assertIn(f"Reconciliation output: {reconciliation_path} (blocked, not written)", stdout)
            self.assertIn("nessun output e' stato scritto", stdout)
            self.assertFalse(descriptor_path.exists())
            self.assertFalse(reconciliation_path.exists())
            self.assertEqual(stderr, "")

    def test_consolidate_discover_reports_candidate_runs_without_creating_session(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_consolidate_workspace(data_root)
            session_path = data_root / "database" / "memoria_consolidate_session.active.json"

            code, stdout, stderr = run_cli("consolidate", "discover", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria consolidate discovery", stdout)
            self.assertIn("Modalita: preview-only/read-only", stdout)
            self.assertIn("[1] run-con-ledger-pipeline", stdout)
            self.assertIn("Ledger disponibile: True", stdout)
            self.assertIn("Profili ledger: 2", stdout)
            self.assertIn("run-senza-ledger-pipeline", stdout)
            self.assertIn("memoria consolidate status", stdout)
            self.assertFalse(session_path.exists())
            self.assertEqual(stderr, "")

    def test_consolidate_status_falls_back_to_discovery_when_session_is_missing(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_consolidate_workspace(data_root)

            code, stdout, stderr = run_cli("consolidate", "status", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria consolidate discovery", stdout)
            self.assertIn("[1] run-con-ledger-pipeline", stdout)
            self.assertEqual(stderr, "")

    def test_consolidate_status_reads_existing_active_session(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            _, strong_run = write_consolidate_workspace(data_root)
            write_active_consolidate_session(data_root, strong_run)
            write_mvp_demo_descriptor(data_root)

            code, stdout, stderr = run_cli("consolidate", "status", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria consolidate status", stdout)
            self.assertIn("Run attiva: run-con-ledger-pipeline", stdout)
            self.assertIn("Score: 82", stdout)
            self.assertIn("Motivo: ledger_json_available", stdout)
            self.assertIn("mvp_consolidated_review_ledger.json", stdout)
            self.assertIn("Demo golden run:", stdout)
            self.assertIn("Run canonica: golden-run-pipeline", stdout)
            self.assertIn("Status: ready_for_internal_demo", stdout)
            self.assertIn("la sessione consolidate attiva non coincide con la golden run demo", stdout)
            self.assertIn("consolidate run --preview", stdout)
            self.assertIn("comando Python read-only", stdout)
            self.assertEqual(stderr, "")

    def test_sources_online_discover_reports_registry_without_network_or_session(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_sources_online_workspace(data_root)
            session_path = data_root / "database" / "memoria_sources_online_session.active.json"

            with patch(
                "caduti_fonti_report.memoria_cli._sources_registry_path",
                return_value=data_root / "ricerche" / "camalanca_fonti.yaml",
            ):
                code, stdout, stderr = run_cli("sources", "online", "discover", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria sources online discovery", stdout)
            self.assertIn("Modalita: preview-only/read-only", stdout)
            self.assertIn("Registry fonti:", stdout)
            self.assertIn("Fonti abilitate: 2", stdout)
            self.assertIn("Definizioni fonte: 3", stdout)
            self.assertIn("Profili candidati: 2", stdout)
            self.assertIn("- bundesarchiv_invenio", stdout)
            self.assertIn("- deutsche_dienststelle", stdout)
            self.assertIn("non avvia rete", stdout)
            self.assertFalse(session_path.exists())
            self.assertEqual(stderr, "")

    def test_sources_online_status_reads_existing_active_session(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_sources_online_workspace(data_root)
            write_active_sources_online_session(data_root)

            with patch(
                "caduti_fonti_report.memoria_cli._sources_registry_path",
                return_value=data_root / "ricerche" / "camalanca_fonti.yaml",
            ):
                code, stdout, stderr = run_cli("sources", "online", "status", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria sources online status", stdout)
            self.assertIn("Stato: presente", stdout)
            self.assertIn("Soggetto: place place:purocielo", stdout)
            self.assertIn("Etichetta: Purocielo", stdout)
            self.assertIn("Query seed candidata: Purocielo", stdout)
            self.assertIn("- bundesarchiv_invenio | candidate", stdout)
            self.assertIn("comando Python read-only", stdout)
            self.assertEqual(stderr, "")

    def test_sources_offline_discover_reports_shallow_intake_without_creating_runs(self) -> None:
        with temp_workspace() as tmp_dir:
            data_root = make_data_root(tmp_dir)
            write_sources_offline_workspace(data_root)
            runs_root = data_root / "risultati" / "runs"

            code, stdout, stderr = run_cli("sources", "offline", "discover", "--data-root", str(data_root))

            self.assertEqual(code, 0)
            self.assertIn("Me.Mo.Ria sources offline discovery", stdout)
            self.assertIn("Documenti da processare:", stdout)
            self.assertIn("Cartelle candidate: 1", stdout)
            self.assertIn("File candidati: 1", stdout)
            self.assertIn("- mvp_purocielo", stdout)
            self.assertIn("- note_sciolte.txt", stdout)
            self.assertIn("non crea run", stdout)
            self.assertFalse(runs_root.exists())
            self.assertEqual(stderr, "")

    def test_data_root_command_fails_when_resolved_path_does_not_exist(self) -> None:
        with temp_workspace() as tmp_dir:
            missing = tmp_dir / "missing-data-root"

            code, stdout, stderr = run_cli("data-root", "--data-root", str(missing))

            self.assertEqual(code, 1)
            self.assertIn(str(missing.resolve()), stdout)
            self.assertIn("Data root non trovato", stderr)

    def test_data_root_command_reports_clear_error_when_data_root_is_not_resolvable(self) -> None:
        with temp_workspace() as tmp_dir:
            isolated_engine_root = tmp_dir / "isolated" / "memoria-engine"
            isolated_engine_root.mkdir(parents=True)

            code, stdout, stderr = run_cli("data-root", cwd=isolated_engine_root)

            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("Data root non configurato", stderr)
            self.assertIn("--data-root", stderr)
            self.assertIn("MEMORIA_DATA_ROOT", stderr)


if __name__ == "__main__":
    unittest.main()
