from __future__ import annotations

from pathlib import Path


SOURCE_LEVEL_DIRECTORIES = (
    "source_profiles",
    "source_strategies",
    "source_result_logic",
    "source_detail_logic",
)


def resolve_source_catalog_root(repo_root: Path | str | None = None, *, registry_path: Path | str | None = None) -> Path:
    candidates: list[Path] = []
    if registry_path is not None:
        registry = Path(registry_path).resolve()
        candidates.append(registry.parent)
        if registry.parent.name == "registry":
            candidates.append(registry.parent.parent)

    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    candidates.extend(
        [
            root.parent / "memoria-sources",
            root / "memoria-sources",
            root / "ricerche",
            root,
        ]
    )

    for candidate in candidates:
        if _has_source_levels(candidate):
            return candidate
    return candidates[0]


def resolve_source_registry_path(repo_root: Path | str | None = None, *, registry_name: str = "camalanca_fonti.yaml") -> Path:
    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    candidates = [
        root.parent / "memoria-sources" / "registry" / registry_name,
        root / "memoria-sources" / "registry" / registry_name,
        root / "ricerche" / registry_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def source_level_path(catalog_root: Path | str, directory_name: str, source_id: str) -> Path:
    return Path(catalog_root) / directory_name / f"{source_id}.yaml"


def source_catalog_relative_path(repo_root: Path | str, target: Path | str) -> str:
    repo = Path(repo_root).resolve()
    path = Path(target).resolve()
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        try:
            return path.relative_to(repo.parent).as_posix()
        except ValueError:
            return str(path)


def _has_source_levels(path: Path) -> bool:
    return all((path / directory).exists() for directory in SOURCE_LEVEL_DIRECTORIES)
