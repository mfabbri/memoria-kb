from __future__ import annotations

from pathlib import Path


def resolve_knowledge_root(start: Path | None = None) -> Path:
    """Return the sibling memoria-knowledge repository when available."""
    repo_root = Path(__file__).resolve().parents[2]
    search_roots = []
    if start is not None:
        search_roots.append(start.resolve())
    search_roots.extend([Path.cwd().resolve(), repo_root])

    seen: set[Path] = set()
    for root in search_roots:
        for base in (root, *root.parents):
            for candidate in (base / "memoria-knowledge", base.parent / "memoria-knowledge"):
                if candidate in seen:
                    continue
                seen.add(candidate)
                if candidate.exists() and candidate.is_dir():
                    return candidate
    return repo_root.parent / "memoria-knowledge"


def default_places_index_path(research_dir: Path = Path("ricerche")) -> Path:
    if _is_default_research_dir(research_dir):
        knowledge_path = resolve_knowledge_root() / "places" / "places.index.jsonld"
        if knowledge_path.exists():
            return knowledge_path
    return research_dir / "places" / "places.index.jsonld"


def default_military_glossary_dir(research_dir: Path = Path("ricerche")) -> Path:
    if _is_default_research_dir(research_dir):
        knowledge_path = resolve_knowledge_root() / "glossary" / "military"
        if knowledge_path.exists():
            return knowledge_path
    return research_dir / "military_glossaries"


def _is_default_research_dir(path: Path) -> bool:
    return Path(path) == Path("ricerche")
