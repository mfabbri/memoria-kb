from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


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
