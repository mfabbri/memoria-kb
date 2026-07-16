from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import to_json_safe


@dataclass
class SourceSearchOption:
    value: str
    label: str = ""


@dataclass
class SourceSearchField:
    field_id: str
    label: str = ""
    field_type: str = "unknown"
    role: str = ""
    required: bool = False
    default: str = ""
    options: list[SourceSearchOption] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class SourceSearchProfile:
    source_id: str
    engine: str
    discovery: dict[str, str] = field(default_factory=dict)
    fields: list[SourceSearchField] = field(default_factory=list)
    strategy_notes: list[str] = field(default_factory=list)


def source_search_profile_to_dict(profile: SourceSearchProfile) -> dict[str, Any]:
    payload = to_json_safe(profile)
    for field_item in payload.get("fields", []):
        if "field_id" in field_item:
            field_item["id"] = field_item.pop("field_id")
        if "field_type" in field_item:
            field_item["type"] = field_item.pop("field_type")
    return payload


def source_search_profile_from_dict(payload: dict[str, Any]) -> SourceSearchProfile:
    fields: list[SourceSearchField] = []
    for item in payload.get("fields", []) or []:
        if not isinstance(item, dict):
            continue
        fields.append(
            SourceSearchField(
                field_id=str(item.get("id") or item.get("field_id") or ""),
                label=str(item.get("label", "")),
                field_type=str(item.get("type") or item.get("field_type") or "unknown"),
                role=str(item.get("role", "")),
                required=bool(item.get("required", False)),
                default=str(item.get("default", "")),
                options=[
                    SourceSearchOption(
                        value=str(option.get("value", "")),
                        label=str(option.get("label", "")),
                    )
                    for option in item.get("options", []) or []
                    if isinstance(option, dict)
                ],
                metadata={str(key): str(value) for key, value in (item.get("metadata", {}) or {}).items()},
            )
        )

    return SourceSearchProfile(
        source_id=str(payload.get("source_id", "")),
        engine=str(payload.get("engine", "")),
        discovery={str(key): str(value) for key, value in (payload.get("discovery", {}) or {}).items()},
        fields=fields,
        strategy_notes=[str(item) for item in payload.get("strategy_notes", []) or []],
    )


def load_source_search_profile(path: Path | str) -> SourceSearchProfile:
    raw_payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if "search_profile" in raw_payload and isinstance(raw_payload["search_profile"], dict):
        raw_payload = raw_payload["search_profile"]
    if not isinstance(raw_payload, dict):
        raise ValueError("Profilo fonte non valido: atteso mapping YAML.")
    return source_search_profile_from_dict(raw_payload)


def write_source_search_profile(path: Path | str, profile: SourceSearchProfile) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"search_profile": source_search_profile_to_dict(profile)}
    target.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
