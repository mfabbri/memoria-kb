from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.workspace_resolver import (  # noqa: E402
    build_pcloud_authorize_url,
    build_workspace_storage,
    exchange_pcloud_oauth_code,
    resolve_data_root,
    resolve_workspace,
)


ROOT_DIR = Path(__file__).resolve().parents[1]


@contextmanager
def temp_workspace():
    base_dir = ROOT_DIR / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"workspace-resolver-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def make_data_root(base_dir: Path) -> Path:
    data_root = base_dir / "external-data-root"
    data_root.mkdir(parents=True)
    return data_root


class WorkspaceResolverTests(unittest.TestCase):
    def test_data_root_prefers_explicit_argument(self) -> None:
        with temp_workspace() as tmp_dir:
            explicit = make_data_root(tmp_dir / "explicit")
            env_root = make_data_root(tmp_dir / "env")

            resolution = resolve_data_root(
                explicit_data_root=str(explicit),
                env={"MEMORIA_DATA_ROOT": str(env_root)},
                start_dir=tmp_dir,
            )

            self.assertEqual(resolution.path, explicit.resolve())
            self.assertEqual(resolution.source, "--data-root")

    def test_data_root_uses_environment_when_argument_is_missing(self) -> None:
        with temp_workspace() as tmp_dir:
            env_root = make_data_root(tmp_dir)

            resolution = resolve_data_root(env={"MEMORIA_DATA_ROOT": str(env_root)}, start_dir=tmp_dir)

            self.assertEqual(resolution.path, env_root.resolve())
            self.assertEqual(resolution.source, "MEMORIA_DATA_ROOT")

    def test_data_root_uses_legacy_workspace_manifest_when_env_is_missing(self) -> None:
        with temp_workspace() as tmp_dir:
            engine_root, workspace_root = make_project_workspace(tmp_dir)
            data_root = make_data_root(tmp_dir)
            (workspace_root / "manifest.yml").write_text(
                f"""
workspace_id: test
repository_role: descriptor_only
data_root:
  type: external_path
  windows_path: '{data_root}'
""".strip(),
                encoding="utf-8",
            )

            resolution = resolve_data_root(env={}, start_dir=engine_root)

            self.assertEqual(resolution.path, data_root.resolve())
            self.assertIn("manifest.yml", resolution.source)

    def test_data_root_uses_provider_aware_local_workspace_manifest(self) -> None:
        with temp_workspace() as tmp_dir:
            engine_root, workspace_root = make_project_workspace(tmp_dir)
            data_root = make_data_root(tmp_dir)
            (workspace_root / "manifest.yml").write_text(
                f"""
workspace_id: test
repository_role: descriptor_only
workspace:
  provider: local
  root: '{data_root}'
  env_var: MEMORIA_DATA_ROOT
  providers:
    pcloud:
      status: blocked_api_support
      root: /MeMoRiA
      credentials_ref: MEMORIA_PCLOUD_ACCESS_TOKEN
""".strip(),
                encoding="utf-8",
            )

            resolution = resolve_data_root(env={}, start_dir=engine_root)

            self.assertEqual(resolution.path, data_root.resolve())
            self.assertIn("manifest.yml", resolution.source)

    def test_data_root_uses_legacy_manifest_path_when_provider_is_not_local(self) -> None:
        with temp_workspace() as tmp_dir:
            engine_root, workspace_root = make_project_workspace(tmp_dir)
            data_root = make_data_root(tmp_dir)
            (workspace_root / "manifest.yml").write_text(
                f"""
workspace_id: test
repository_role: descriptor_only
workspace:
  provider: pcloud
  root: /MeMoRiA
  credentials_ref: MEMORIA_PCLOUD_ACCESS_TOKEN
  mode: read_only
data_root:
  type: external_path
  windows_path: '{data_root}'
""".strip(),
                encoding="utf-8",
            )

            resolution = resolve_data_root(env={}, start_dir=engine_root)

            self.assertEqual(resolution.path, data_root.resolve())
            self.assertIn("manifest.yml", resolution.source)

    def test_workspace_resolves_local_provider_from_manifest(self) -> None:
        with temp_workspace() as tmp_dir:
            engine_root, workspace_root = make_project_workspace(tmp_dir)
            data_root = make_data_root(tmp_dir)
            (workspace_root / "manifest.yml").write_text(
                f"""
workspace_id: test
repository_role: descriptor_only
workspace:
  provider: local
  root: '{data_root}'
  env_var: MEMORIA_DATA_ROOT
""".strip(),
                encoding="utf-8",
            )

            resolution = resolve_workspace(env={}, start_dir=engine_root)

            self.assertEqual(resolution.provider, "local")
            self.assertEqual(resolution.local_root, data_root.resolve())
            self.assertIsNone(resolution.pcloud)

    def test_workspace_provider_can_be_overridden_to_pcloud_from_env(self) -> None:
        with temp_workspace() as tmp_dir:
            engine_root, workspace_root = make_project_workspace(tmp_dir)
            data_root = make_data_root(tmp_dir)
            (workspace_root / "manifest.yml").write_text(
                f"""
workspace_id: test
repository_role: descriptor_only
workspace:
  provider: local
  root: '{data_root}'
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

            resolution = resolve_workspace(
                env={
                    "MEMORIA_WORKSPACE_PROVIDER": "pcloud",
                    "MEMORIA_PCLOUD_CLIENT_ID": "client-id",
                    "MEMORIA_PCLOUD_CLIENT_SECRET": "client-secret",
                    "MEMORIA_PCLOUD_ACCESS_TOKEN": "secret-token",
                },
                start_dir=engine_root,
            )

            self.assertEqual(resolution.provider, "pcloud")
            self.assertIsNotNone(resolution.pcloud)
            assert resolution.pcloud is not None
            self.assertEqual(resolution.pcloud.root, "/MeMoRiA")
            self.assertEqual(resolution.pcloud.folder_id, "123")
            self.assertEqual(resolution.pcloud.api_host, "eapi.pcloud.com")
            self.assertEqual(resolution.pcloud.app_name, "MemoriaStorage")
            self.assertEqual(resolution.pcloud.client_id_ref, "MEMORIA_PCLOUD_CLIENT_ID")
            self.assertEqual(resolution.pcloud.client_secret_ref, "MEMORIA_PCLOUD_CLIENT_SECRET")
            self.assertEqual(resolution.pcloud.access_token_ref, "MEMORIA_PCLOUD_ACCESS_TOKEN")
            self.assertTrue(resolution.pcloud.client_id_configured)
            self.assertTrue(resolution.pcloud.client_secret_configured)
            self.assertTrue(resolution.pcloud.token_configured)

    def test_workspace_pcloud_values_can_be_overridden_from_env(self) -> None:
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
      root: /ManifestRoot
      folderid: 111
      api_host: api.pcloud.com
      client_id_ref: MEMORIA_PCLOUD_CLIENT_ID
      client_secret_ref: MEMORIA_PCLOUD_CLIENT_SECRET
      access_token_ref: MEMORIA_PCLOUD_ACCESS_TOKEN
      mode: read_only
""".strip(),
                encoding="utf-8",
            )

            resolution = resolve_workspace(
                env={
                    "MEMORIA_PCLOUD_ROOT": "/EnvRoot",
                    "MEMORIA_PCLOUD_FOLDER_ID": "222",
                    "MEMORIA_PCLOUD_API_HOST": "eapi.pcloud.com",
                    "MEMORIA_PCLOUD_CLIENT_ID_REF": "CUSTOM_PCLOUD_CLIENT_ID",
                    "MEMORIA_PCLOUD_CLIENT_SECRET_REF": "CUSTOM_PCLOUD_CLIENT_SECRET",
                    "MEMORIA_PCLOUD_ACCESS_TOKEN_REF": "CUSTOM_PCLOUD_TOKEN",
                    "CUSTOM_PCLOUD_CLIENT_ID": "client-id",
                    "CUSTOM_PCLOUD_CLIENT_SECRET": "client-secret",
                    "CUSTOM_PCLOUD_TOKEN": "secret-token",
                },
                start_dir=engine_root,
            )

            self.assertEqual(resolution.provider, "pcloud")
            self.assertIsNotNone(resolution.pcloud)
            assert resolution.pcloud is not None
            self.assertEqual(resolution.pcloud.root, "/EnvRoot")
            self.assertEqual(resolution.pcloud.folder_id, "222")
            self.assertEqual(resolution.pcloud.api_host, "eapi.pcloud.com")
            self.assertEqual(resolution.pcloud.client_id_ref, "CUSTOM_PCLOUD_CLIENT_ID")
            self.assertEqual(resolution.pcloud.client_secret_ref, "CUSTOM_PCLOUD_CLIENT_SECRET")
            self.assertEqual(resolution.pcloud.access_token_ref, "CUSTOM_PCLOUD_TOKEN")
            self.assertTrue(resolution.pcloud.client_id_configured)
            self.assertTrue(resolution.pcloud.client_secret_configured)
            self.assertTrue(resolution.pcloud.token_configured)

    def test_workspace_provider_can_be_loaded_from_nearest_env_file(self) -> None:
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
      root: /MeMoRiA
      api_host: eapi.pcloud.com
      client_id_ref: MEMORIA_PCLOUD_CLIENT_ID
      client_secret_ref: MEMORIA_PCLOUD_CLIENT_SECRET
      access_token_ref: MEMORIA_PCLOUD_ACCESS_TOKEN
""".strip(),
                encoding="utf-8",
            )
            (engine_root / ".env").write_text(
                """
MEMORIA_WORKSPACE_PROVIDER=pcloud
MEMORIA_PCLOUD_CLIENT_ID=client-id
MEMORIA_PCLOUD_CLIENT_SECRET=client-secret
MEMORIA_PCLOUD_ACCESS_TOKEN=secret-token
MEMORIA_PCLOUD_FOLDER_ID=456
""".strip(),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                resolution = resolve_workspace(start_dir=engine_root)

            self.assertEqual(resolution.provider, "pcloud")
            self.assertIsNotNone(resolution.pcloud)
            assert resolution.pcloud is not None
            self.assertEqual(resolution.pcloud.folder_id, "456")
            self.assertTrue(resolution.pcloud.client_id_configured)
            self.assertTrue(resolution.pcloud.client_secret_configured)
            self.assertTrue(resolution.pcloud.token_configured)

    def test_build_workspace_storage_uses_pcloud_token_from_configured_env_ref(self) -> None:
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
      root: /MeMoRiA
      access_token_ref: CUSTOM_PCLOUD_TOKEN
""".strip(),
                encoding="utf-8",
            )
            resolution = resolve_workspace(env={"CUSTOM_PCLOUD_TOKEN": "secret-token"}, start_dir=engine_root)

            storage = build_workspace_storage(resolution, env={"CUSTOM_PCLOUD_TOKEN": "secret-token"})

            with self.assertRaises(ValueError):
                storage.exists("../blocked")

    def test_pcloud_authorize_url_uses_client_id_without_client_secret(self) -> None:
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
            resolution = resolve_workspace(
                env={
                    "MEMORIA_PCLOUD_CLIENT_ID": "client-id",
                    "MEMORIA_PCLOUD_CLIENT_SECRET": "client-secret",
                },
                start_dir=engine_root,
            )
            assert resolution.pcloud is not None

            url = build_pcloud_authorize_url(
                resolution.pcloud,
                env={"MEMORIA_PCLOUD_CLIENT_ID": "client-id", "MEMORIA_PCLOUD_CLIENT_SECRET": "client-secret"},
                redirect_uri="http://localhost/callback",
                state="memoria",
            )

            self.assertIn("https://my.pcloud.com/oauth2/authorize?", url)
            self.assertIn("client_id=client-id", url)
            self.assertIn("response_type=code", url)
            self.assertIn("redirect_uri=http%3A%2F%2Flocalhost%2Fcallback", url)
            self.assertNotIn("client-secret", url)

    def test_exchange_pcloud_oauth_code_uses_client_secret_and_returns_token(self) -> None:
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
""".strip(),
                encoding="utf-8",
            )
            resolution = resolve_workspace(
                env={
                    "MEMORIA_PCLOUD_CLIENT_ID": "client-id",
                    "MEMORIA_PCLOUD_CLIENT_SECRET": "client-secret",
                },
                start_dir=engine_root,
            )
            assert resolution.pcloud is not None
            calls: list[tuple[str, dict[str, str], int]] = []

            def http_json_get(url: str, params: dict[str, str], timeout: int) -> dict[str, object]:
                calls.append((url, params, timeout))
                return {"result": 0, "access_token": "oauth-token", "token_type": "bearer", "uid": 123}

            token = exchange_pcloud_oauth_code(
                resolution.pcloud,
                code="auth-code",
                env={
                    "MEMORIA_PCLOUD_CLIENT_ID": "client-id",
                    "MEMORIA_PCLOUD_CLIENT_SECRET": "client-secret",
                },
                timeout=7,
                http_json_get=http_json_get,
            )

            self.assertEqual(calls, [("https://eapi.pcloud.com/oauth2_token", {
                "client_id": "client-id",
                "client_secret": "client-secret",
                "code": "auth-code",
            }, 7)])
            self.assertEqual(token.access_token, "oauth-token")
            self.assertEqual(token.token_type, "bearer")
            self.assertEqual(token.uid, "123")


def make_project_workspace(tmp_dir: Path) -> tuple[Path, Path]:
    project_root = tmp_dir / "project"
    engine_root = project_root / "memoria-engine"
    workspace_root = project_root / "memoria-workspace"
    engine_root.mkdir(parents=True)
    workspace_root.mkdir()
    return engine_root, workspace_root


if __name__ == "__main__":
    unittest.main()
