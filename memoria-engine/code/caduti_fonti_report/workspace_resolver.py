from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DataRootResolution:
    path: Path
    source: str


class DataRootResolutionError(RuntimeError):
    pass


def resolve_data_root(
    *,
    explicit_data_root: str = "",
    env: dict[str, str] | None = None,
    start_dir: Path | None = None,
) -> DataRootResolution:
    env = env if env is not None else os.environ
    start_dir = (start_dir or Path.cwd()).resolve()

    if explicit_data_root.strip():
        return DataRootResolution(Path(explicit_data_root).expanduser().resolve(), "--data-root")

    env_data_root = env.get("MEMORIA_DATA_ROOT", "").strip()
    if env_data_root:
        return DataRootResolution(Path(env_data_root).expanduser().resolve(), "MEMORIA_DATA_ROOT")

    manifest_path = start_dir / ".." / "memoria-workspace" / "manifest.yml"
    if manifest_path.exists():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        manifest_data_root = _manifest_data_root_path(manifest)
        if manifest_data_root:
            return DataRootResolution(Path(manifest_data_root).expanduser().resolve(), str(manifest_path.resolve()))

    raise DataRootResolutionError(
        "Data root non configurato: passa --data-root, imposta MEMORIA_DATA_ROOT, "
        "oppure crea ../memoria-workspace/manifest.yml con workspace.provider local e workspace.root."
    )


def _manifest_data_root_path(manifest: object) -> str:
    if not isinstance(manifest, dict):
        return ""

    workspace = manifest.get("workspace")
    if isinstance(workspace, dict):
        provider = str(workspace.get("provider", "")).strip().lower()
        if provider == "local":
            workspace_root = str(workspace.get("root", "")).strip()
            if workspace_root:
                return workspace_root

            providers = workspace.get("providers")
            if isinstance(providers, dict):
                local_provider = providers.get("local")
                if isinstance(local_provider, dict):
                    local_root = str(local_provider.get("root", "")).strip()
                    if local_root:
                        return local_root
        if provider:
            return _legacy_manifest_data_root_path(manifest)

    return _legacy_manifest_data_root_path(manifest)


def _legacy_manifest_data_root_path(manifest: dict[object, object]) -> str:
    data_root = manifest.get("data_root", {})
    if isinstance(data_root, dict):
        windows_path = str(data_root.get("windows_path", "")).strip()
        if windows_path:
            return windows_path
    return ""
