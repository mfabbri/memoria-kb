from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import json
import urllib.parse
import urllib.request

import yaml

from caduti_fonti_report.config import load_nearest_env_file
from caduti_fonti_report.workspace_storage import LocalWorkspaceStorage, PCloudWorkspaceStorage, WorkspaceStorage


@dataclass(frozen=True)
class DataRootResolution:
    path: Path
    source: str


@dataclass(frozen=True)
class PCloudWorkspaceConfig:
    app_name: str
    root: str
    folder_id: str
    api_host: str
    client_id_ref: str
    client_secret_ref: str
    access_token_ref: str
    client_id_configured: bool
    client_secret_configured: bool
    token_configured: bool
    mode: str


@dataclass(frozen=True)
class WorkspaceResolution:
    provider: str
    source: str
    local_root: Path | None = None
    pcloud: PCloudWorkspaceConfig | None = None


@dataclass(frozen=True)
class PCloudOAuthToken:
    access_token: str
    token_type: str
    uid: str
    api_host: str


class DataRootResolutionError(RuntimeError):
    pass


class WorkspaceResolutionError(RuntimeError):
    pass


def resolve_data_root(
    *,
    explicit_data_root: str = "",
    env: dict[str, str] | None = None,
    start_dir: Path | None = None,
) -> DataRootResolution:
    start_dir = (start_dir or Path.cwd()).resolve()
    if env is None:
        load_nearest_env_file(start_dir)
        env = os.environ

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


def resolve_workspace(
    *,
    explicit_data_root: str = "",
    env: dict[str, str] | None = None,
    start_dir: Path | None = None,
) -> WorkspaceResolution:
    start_dir = (start_dir or Path.cwd()).resolve()
    if env is None:
        load_nearest_env_file(start_dir)
        env = os.environ
    manifest_path = start_dir / ".." / "memoria-workspace" / "manifest.yml"
    manifest = _load_manifest(manifest_path)
    workspace = manifest.get("workspace", {}) if isinstance(manifest.get("workspace"), dict) else {}
    provider = (
        env.get("MEMORIA_WORKSPACE_PROVIDER", "").strip().lower()
        or str(workspace.get("provider", "")).strip().lower()
        or "local"
    )
    if provider == "local":
        data_root = resolve_data_root(explicit_data_root=explicit_data_root, env=env, start_dir=start_dir)
        return WorkspaceResolution(provider="local", source=data_root.source, local_root=data_root.path)
    if provider == "pcloud":
        pcloud_config = _pcloud_config(manifest, env)
        return WorkspaceResolution(provider="pcloud", source=_workspace_source(manifest_path), pcloud=pcloud_config)
    raise WorkspaceResolutionError(f"Workspace provider non supportato: {provider}")


def build_workspace_storage(resolution: WorkspaceResolution, env: dict[str, str] | None = None) -> WorkspaceStorage:
    env = env if env is not None else os.environ
    if resolution.provider == "local" and resolution.local_root is not None:
        return LocalWorkspaceStorage(resolution.local_root)
    if resolution.provider == "pcloud" and resolution.pcloud is not None:
        access_token = env.get(resolution.pcloud.access_token_ref, "").strip()
        if not access_token:
            raise WorkspaceResolutionError(
                f"Access token pCloud non configurato: completa OAuth e imposta {resolution.pcloud.access_token_ref} nel .env locale."
            )
        return PCloudWorkspaceStorage(
            access_token=access_token,
            root=resolution.pcloud.root,
            root_folder_id=resolution.pcloud.folder_id,
            api_host=resolution.pcloud.api_host,
        )
    raise WorkspaceResolutionError(f"Workspace provider non costruibile: {resolution.provider}")


def build_pcloud_authorize_url(
    config: PCloudWorkspaceConfig,
    env: dict[str, str] | None = None,
    *,
    redirect_uri: str = "",
    state: str = "",
    response_type: str = "code",
    force_reapprove: bool = False,
) -> str:
    env = env if env is not None else os.environ
    client_id = env.get(config.client_id_ref, "").strip()
    if not client_id:
        raise WorkspaceResolutionError(
            f"Client ID pCloud non configurato: imposta {config.client_id_ref} nel .env locale."
        )
    params = {"client_id": client_id, "response_type": response_type}
    if redirect_uri.strip():
        params["redirect_uri"] = redirect_uri.strip()
    if state.strip():
        params["state"] = state.strip()
    if force_reapprove:
        params["force_reapprove"] = "1"
    return f"https://my.pcloud.com/oauth2/authorize?{urllib.parse.urlencode(params)}"


HttpJsonGet = Callable[[str, dict[str, str], int], dict[str, Any]]


def exchange_pcloud_oauth_code(
    config: PCloudWorkspaceConfig,
    *,
    code: str,
    env: dict[str, str] | None = None,
    api_host: str = "",
    timeout: int = 20,
    http_json_get: HttpJsonGet | None = None,
) -> PCloudOAuthToken:
    env = env if env is not None else os.environ
    client_id = env.get(config.client_id_ref, "").strip()
    client_secret = env.get(config.client_secret_ref, "").strip()
    auth_code = code.strip()
    if not client_id:
        raise WorkspaceResolutionError(
            f"Client ID pCloud non configurato: imposta {config.client_id_ref} nel .env locale."
        )
    if not client_secret:
        raise WorkspaceResolutionError(
            f"Client secret pCloud non configurato: imposta {config.client_secret_ref} nel .env locale."
        )
    if not auth_code:
        raise WorkspaceResolutionError("Authorization code pCloud mancante.")
    host = api_host.strip() or config.api_host
    getter = http_json_get or _default_http_json_get
    payload = getter(
        f"https://{host}/oauth2_token",
        {"client_id": client_id, "client_secret": client_secret, "code": auth_code},
        timeout,
    )
    result = payload.get("result", 0)
    if result != 0:
        raise WorkspaceResolutionError(f"pCloud oauth2_token failed with result {result}.")
    access_token = str(payload.get("access_token", "")).strip()
    if not access_token:
        raise WorkspaceResolutionError("pCloud oauth2_token response missing access_token.")
    return PCloudOAuthToken(
        access_token=access_token,
        token_type=str(payload.get("token_type", "")).strip() or "bearer",
        uid=str(payload.get("uid", "")).strip(),
        api_host=host,
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


def _load_manifest(manifest_path: Path) -> dict[object, object]:
    if not manifest_path.exists():
        return {}
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _workspace_source(manifest_path: Path) -> str:
    return str(manifest_path.resolve()) if manifest_path.exists() else "MEMORIA_WORKSPACE_PROVIDER"


def _pcloud_config(manifest: dict[object, object], env: dict[str, str]) -> PCloudWorkspaceConfig:
    workspace = manifest.get("workspace", {}) if isinstance(manifest.get("workspace"), dict) else {}
    providers = workspace.get("providers", {}) if isinstance(workspace.get("providers"), dict) else {}
    manifest_pcloud = providers.get("pcloud", {}) if isinstance(providers.get("pcloud"), dict) else {}
    if not manifest_pcloud and str(workspace.get("provider", "")).strip().lower() == "pcloud":
        manifest_pcloud = workspace
    access_token_ref = (
        env.get("MEMORIA_PCLOUD_ACCESS_TOKEN_REF", "").strip()
        or str(manifest_pcloud.get("access_token_ref", "")).strip()
        or str(manifest_pcloud.get("credentials_ref", "")).strip()
        or "MEMORIA_PCLOUD_ACCESS_TOKEN"
    )
    client_id_ref = (
        env.get("MEMORIA_PCLOUD_CLIENT_ID_REF", "").strip()
        or str(manifest_pcloud.get("client_id_ref", "")).strip()
        or "MEMORIA_PCLOUD_CLIENT_ID"
    )
    client_secret_ref = (
        env.get("MEMORIA_PCLOUD_CLIENT_SECRET_REF", "").strip()
        or str(manifest_pcloud.get("client_secret_ref", "")).strip()
        or "MEMORIA_PCLOUD_CLIENT_SECRET"
    )
    return PCloudWorkspaceConfig(
        app_name=env.get("MEMORIA_PCLOUD_APP_NAME", "").strip()
        or str(manifest_pcloud.get("app_name", "")).strip()
        or "MemoriaStorage",
        root=env.get("MEMORIA_PCLOUD_ROOT", "").strip() or str(manifest_pcloud.get("root", "")).strip() or "/",
        folder_id=env.get("MEMORIA_PCLOUD_FOLDER_ID", "").strip() or str(manifest_pcloud.get("folderid", "")).strip(),
        api_host=env.get("MEMORIA_PCLOUD_API_HOST", "").strip()
        or str(manifest_pcloud.get("api_host", "")).strip()
        or "api.pcloud.com",
        client_id_ref=client_id_ref,
        client_secret_ref=client_secret_ref,
        access_token_ref=access_token_ref,
        client_id_configured=bool(env.get(client_id_ref, "").strip()),
        client_secret_configured=bool(env.get(client_secret_ref, "").strip()),
        token_configured=bool(env.get(access_token_ref, "").strip()),
        mode=env.get("MEMORIA_PCLOUD_MODE", "").strip() or str(manifest_pcloud.get("mode", "")).strip() or "read_only",
    )


def _legacy_manifest_data_root_path(manifest: dict[object, object]) -> str:
    data_root = manifest.get("data_root", {})
    if isinstance(data_root, dict):
        windows_path = str(data_root.get("windows_path", "")).strip()
        if windows_path:
            return windows_path
    return ""


def _default_http_json_get(url: str, params: dict[str, str], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "memoria-pcloud-oauth/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))
