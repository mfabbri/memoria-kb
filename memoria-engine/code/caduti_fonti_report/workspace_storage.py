from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol
import json
import urllib.parse
import urllib.request


@dataclass(frozen=True)
class WorkspaceEntry:
    name: str
    path: str
    is_dir: bool
    is_file: bool
    size: int | None = None


@dataclass(frozen=True)
class WorkspaceStat:
    path: str
    exists: bool
    is_dir: bool
    is_file: bool
    size: int | None = None
    modified_time: float | None = None


class WorkspaceStorage(Protocol):
    def exists(self, path: str | Path) -> bool:
        ...

    def list_dir(self, path: str | Path) -> tuple[WorkspaceEntry, ...]:
        ...

    def read_bytes(self, path: str | Path) -> bytes:
        ...

    def write_bytes(self, path: str | Path, data: bytes) -> None:
        ...

    def mkdir(self, path: str | Path) -> None:
        ...

    def stat(self, path: str | Path) -> WorkspaceStat:
        ...


class PCloudStorageError(RuntimeError):
    pass


class LocalWorkspaceStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def exists(self, path: str | Path) -> bool:
        return self._resolve(path).exists()

    def list_dir(self, path: str | Path) -> tuple[WorkspaceEntry, ...]:
        directory = self._resolve(path)
        if not directory.is_dir():
            return ()
        entries = []
        for entry in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            stat = entry.stat()
            entries.append(
                WorkspaceEntry(
                    name=entry.name,
                    path=self._logical_path(entry),
                    is_dir=entry.is_dir(),
                    is_file=entry.is_file(),
                    size=stat.st_size if entry.is_file() else None,
                )
            )
        return tuple(entries)

    def read_bytes(self, path: str | Path) -> bytes:
        return self._resolve(path).read_bytes()

    def write_bytes(self, path: str | Path, data: bytes) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def mkdir(self, path: str | Path) -> None:
        self._resolve(path).mkdir(parents=True, exist_ok=True)

    def stat(self, path: str | Path) -> WorkspaceStat:
        target = self._resolve(path)
        if not target.exists():
            return WorkspaceStat(
                path=self._logical_path(target),
                exists=False,
                is_dir=False,
                is_file=False,
            )
        stat = target.stat()
        return WorkspaceStat(
            path=self._logical_path(target),
            exists=True,
            is_dir=target.is_dir(),
            is_file=target.is_file(),
            size=stat.st_size if target.is_file() else None,
            modified_time=stat.st_mtime,
        )

    def _resolve(self, path: str | Path) -> Path:
        logical_path = Path(path)
        if logical_path.is_absolute():
            target = logical_path.expanduser().resolve()
        else:
            target = (self.root / logical_path).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError(f"Workspace path escapes root: {path}")
        return target

    def _logical_path(self, path: Path) -> str:
        try:
            relative = path.resolve().relative_to(self.root)
        except ValueError:
            return str(path)
        return "." if str(relative) == "." else relative.as_posix()


HttpJsonGet = Callable[[str, dict[str, str], int], dict[str, Any]]
HttpBytesGet = Callable[[str, int], bytes]


class PCloudWorkspaceStorage:
    def __init__(
        self,
        *,
        access_token: str,
        root: str = "/",
        root_folder_id: str = "",
        api_host: str = "api.pcloud.com",
        timeout: int = 20,
        http_json_get: HttpJsonGet | None = None,
        http_bytes_get: HttpBytesGet | None = None,
    ) -> None:
        token = access_token.strip()
        if not token:
            raise ValueError("PCloudWorkspaceStorage requires an access token.")
        self.access_token = token
        self.root = _normalize_pcloud_root(root)
        self.root_folder_id = root_folder_id.strip()
        self.api_host = api_host.strip() or "api.pcloud.com"
        self.timeout = timeout
        self._http_json_get = http_json_get or _default_http_json_get
        self._http_bytes_get = http_bytes_get or _default_http_bytes_get

    def exists(self, path: str | Path) -> bool:
        return self.stat(path).exists

    def list_dir(self, path: str | Path) -> tuple[WorkspaceEntry, ...]:
        params = self._path_params("listfolder", path)
        try:
            payload = self._api_json("listfolder", params)
        except PCloudStorageError as exc:
            if "2005" in str(exc):
                return ()
            raise
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            raise PCloudStorageError("pCloud listfolder response missing metadata.")
        contents = metadata.get("contents", [])
        if not isinstance(contents, list):
            return ()
        entries = []
        for item in contents:
            if not isinstance(item, dict):
                continue
            entries.append(
                WorkspaceEntry(
                    name=str(item.get("name", "")),
                    path=self._logical_path_from_remote(str(item.get("path", ""))),
                    is_dir=bool(item.get("isfolder")),
                    is_file=not bool(item.get("isfolder")),
                    size=_optional_int(item.get("size")) if not bool(item.get("isfolder")) else None,
                )
            )
        return tuple(sorted(entries, key=lambda entry: entry.name.lower()))

    def read_bytes(self, path: str | Path) -> bytes:
        payload = self._api_json("getfilelink", {"path": self._remote_path(path), "forcedownload": "1"})
        hosts = payload.get("hosts", [])
        download_path = str(payload.get("path", "")).strip()
        if not isinstance(hosts, list) or not hosts or not download_path:
            raise PCloudStorageError("pCloud getfilelink response missing hosts/path.")
        host = str(hosts[0]).strip()
        return self._http_bytes_get(f"https://{host}{download_path}", self.timeout)

    def write_bytes(self, path: str | Path, data: bytes) -> None:
        raise NotImplementedError("PCloudWorkspaceStorage is read-only in T26.")

    def mkdir(self, path: str | Path) -> None:
        raise NotImplementedError("PCloudWorkspaceStorage is read-only in T26.")

    def stat(self, path: str | Path) -> WorkspaceStat:
        try:
            payload = self._api_json("stat", self._path_params("stat", path))
        except PCloudStorageError as exc:
            if "2005" in str(exc) or "2009" in str(exc):
                return WorkspaceStat(path=self._logical_path(path), exists=False, is_dir=False, is_file=False)
            raise
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            raise PCloudStorageError("pCloud stat response missing metadata.")
        is_dir = bool(metadata.get("isfolder"))
        return WorkspaceStat(
            path=self._logical_path_from_remote(str(metadata.get("path", self._remote_path(path)))),
            exists=True,
            is_dir=is_dir,
            is_file=not is_dir,
            size=_optional_int(metadata.get("size")) if not is_dir else None,
            modified_time=None,
        )

    def _api_json(self, method: str, params: dict[str, str]) -> dict[str, Any]:
        request_params = {"access_token": self.access_token, **params}
        payload = self._http_json_get(f"https://{self.api_host}/{method}", request_params, self.timeout)
        result = payload.get("result", 0)
        if result != 0:
            raise PCloudStorageError(f"pCloud {method} failed with result {result}.")
        return payload

    def _path_params(self, method: str, path: str | Path) -> dict[str, str]:
        logical = self._logical_path(path)
        if method == "listfolder" and logical == "." and self.root_folder_id:
            return {"folderid": self.root_folder_id}
        return {"path": self._remote_path(logical)}

    def _remote_path(self, path: str | Path) -> str:
        logical = self._logical_path(path)
        if logical == ".":
            return self.root
        return f"{self.root.rstrip('/')}/{logical}"

    def _logical_path(self, path: str | Path) -> str:
        raw = str(path).replace("\\", "/").strip()
        if raw in ("", "."):
            return "."
        if raw.startswith("/"):
            raw = raw.lstrip("/")
        parts = [part for part in raw.split("/") if part not in ("", ".")]
        if any(part == ".." for part in parts):
            raise ValueError(f"Workspace path escapes root: {path}")
        return "/".join(parts) if parts else "."

    def _logical_path_from_remote(self, remote_path: str) -> str:
        remote = remote_path.strip() or self.root
        root = self.root.rstrip("/")
        if root and root != "/" and remote.startswith(root + "/"):
            return remote[len(root) + 1 :]
        if remote == self.root:
            return "."
        return remote.lstrip("/") or "."


def _normalize_pcloud_root(root: str) -> str:
    value = root.strip() or "/"
    if not value.startswith("/"):
        value = "/" + value
    return value.rstrip("/") or "/"


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _default_http_json_get(url: str, params: dict[str, str], timeout: int) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "memoria-pcloud-storage/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _default_http_bytes_get(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "memoria-pcloud-storage/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()
