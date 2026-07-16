from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.workspace_resolver import resolve_data_root  # noqa: E402


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


def make_project_workspace(tmp_dir: Path) -> tuple[Path, Path]:
    project_root = tmp_dir / "project"
    engine_root = project_root / "memoria-engine"
    workspace_root = project_root / "memoria-workspace"
    engine_root.mkdir(parents=True)
    workspace_root.mkdir()
    return engine_root, workspace_root


if __name__ == "__main__":
    unittest.main()
