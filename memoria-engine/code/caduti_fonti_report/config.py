from __future__ import annotations

import csv
import os
import re
import urllib.parse
from pathlib import Path

import yaml

from .models import Caduto, Source, SourceSelection
from .queries import QUERY_BUILDERS


ENV_PLACEHOLDER_RE = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def load_env_file(env_path: Path) -> int:
    if not env_path.exists():
        return 0

    loaded_count = 0
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]

        if not os.environ.get(key):
            os.environ[key] = value
            loaded_count += 1

    return loaded_count


def load_nearest_env_file(start_path: Path) -> int:
    current = start_path.resolve()
    if current.is_file():
        current = current.parent

    for directory in [current, *current.parents]:
        env_path = directory / ".env"
        if env_path.exists():
            return load_env_file(env_path)

    return 0


def resolve_env_placeholder(value: object) -> str:
    text = str(value)
    match = ENV_PLACEHOLDER_RE.match(text.strip())
    if not match:
        return text
    return os.environ.get(match.group(1), "")


def build_url_template(url_template: str):
    def builder(query: str) -> str:
        return url_template.format(query=urllib.parse.quote(query))

    return builder


def load_caduti(csv_path: Path) -> list[Caduto]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [Caduto(**row) for row in reader]


def load_source_registry(source_config_path: Path) -> dict[str, Source]:
    load_nearest_env_file(source_config_path)
    raw_config = yaml.safe_load(source_config_path.read_text(encoding="utf-8")) or {}
    source_items = raw_config.get("sources", [])
    registry: dict[str, Source] = {}

    for item in source_items:
        source_id = item["id"]
        query_mode = item.get("query_mode", "default")
        query_builder = QUERY_BUILDERS.get(query_mode)
        if query_builder is None:
            raise ValueError(f"query_mode non supportato per {source_id}: {query_mode}")

        registry[source_id] = Source(
            source_id=source_id,
            source_name=item["name"],
            kind=item["kind"],
            build_query=query_builder,
            search_url_builder=build_url_template(item.get("url_template", "")),
            credentials={
                str(key): resolve_env_placeholder(value)
                for key, value in (item.get("credentials", {}) or {}).items()
            },
            auth={str(key): str(value) for key, value in (item.get("auth", {}) or {}).items()},
            form={str(key): str(value) for key, value in (item.get("form", {}) or {}).items()},
            local={str(key): str(value) for key, value in (item.get("local", {}) or {}).items()},
            extraction=item.get("extraction", {}) or {},
            note=item.get("note", ""),
            timeout=int(item.get("timeout", 20)),
        )

    return registry


def load_sources_from_yaml(
    source_config_path: Path,
    source_registry: dict[str, Source],
    only_source_id: str = "",
) -> SourceSelection:
    raw_config = yaml.safe_load(source_config_path.read_text(encoding="utf-8")) or {}
    declared_source_ids = raw_config.get("enabled_sources") or [item["id"] for item in raw_config.get("sources", [])]

    selected_source_ids: list[str] = []
    unresolved_source_ids: list[str] = []

    if only_source_id:
        if only_source_id in source_registry:
            selected_source_ids.append(only_source_id)
        else:
            unresolved_source_ids.append(only_source_id)
        return SourceSelection(
            source_file=str(source_config_path),
            selected_sources=[source_registry[source_id] for source_id in selected_source_ids],
            selected_source_ids=selected_source_ids,
            unresolved_source_ids=unresolved_source_ids,
            used_fallback=False,
        )

    for source_id in declared_source_ids:
        if source_id not in source_registry:
            unresolved_source_ids.append(source_id)
            continue
        if source_id not in selected_source_ids:
            selected_source_ids.append(source_id)

    used_fallback = False
    if not selected_source_ids:
        selected_source_ids = list(source_registry.keys())
        used_fallback = True

    return SourceSelection(
        source_file=str(source_config_path),
        selected_sources=[source_registry[source_id] for source_id in selected_source_ids],
        selected_source_ids=selected_source_ids,
        unresolved_source_ids=unresolved_source_ids,
        used_fallback=used_fallback,
    )
