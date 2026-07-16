from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .source_catalog import resolve_source_catalog_root, resolve_source_registry_path

DETAIL_LEVELS = {"claims_extractable", "detail_document_only", "reference_only", "manual_review_only"}


LEGACY_SOURCE_FIELDS = {
    "id",
    "name",
    "kind",
    "enabled",
    "query_mode",
    "url_template",
    "form",
    "auth",
    "credentials",
    "local",
    "extraction",
    "note",
    "timeout",
    "search_profile_path",
}

EVOLVED_SOURCE_FIELDS = {
    "group",
    "access_type",
    "priority",
    "legal_policy",
    "supports",
    "output_fields",
    "raw_storage",
    "review",
}

KNOWN_SOURCE_FIELDS = LEGACY_SOURCE_FIELDS | EVOLVED_SOURCE_FIELDS
REQUIRED_SOURCE_FIELDS = {"id", "name", "kind"}
MAPPING_FIELDS = {"legal_policy", "raw_storage", "review"}
LIST_FIELDS = {"supports", "output_fields"}
REQUIRED_LEVEL_DIRECTORIES = {
    "source_profiles": "source_profile",
    "source_strategies": "search_strategy",
    "source_result_logic": "result_logic",
    "source_detail_logic": "detail_logic",
}


@dataclass
class RegistryValidationResult:
    source_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def validate_sources_registry_file(
    source_config_path: Path | str,
    *,
    only_source_ids: set[str] | None = None,
) -> RegistryValidationResult:
    path = Path(source_config_path)
    try:
        raw_config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return RegistryValidationResult(errors=[f"{path}: file non trovato"])
    except yaml.YAMLError as error:
        return RegistryValidationResult(errors=[f"{path}: YAML non valido: {error}"])

    if only_source_ids:
        raw_config = dict(raw_config)
        raw_sources = raw_config.get("sources", []) or []
        raw_config["sources"] = [
            source for source in raw_sources
            if str(source.get("id", "")).strip() in only_source_ids
        ]
        raw_enabled = raw_config.get("enabled_sources")
        if raw_enabled:
            raw_config["enabled_sources"] = [
                source_id for source_id in raw_enabled
                if str(source_id).strip() in only_source_ids
            ]

    return validate_sources_registry(raw_config, levels_root=resolve_source_catalog_root(registry_path=path))


def validate_sources_registry(
    raw_config: Any,
    *,
    levels_root: Path | None = None,
) -> RegistryValidationResult:
    result = RegistryValidationResult()
    if not isinstance(raw_config, dict):
        result.errors.append("registry: deve essere un mapping YAML")
        return result

    sources = raw_config.get("sources", [])
    if not isinstance(sources, list):
        result.errors.append("sources: deve essere una lista")
        return result

    enabled_sources = raw_config.get("enabled_sources", [])
    if enabled_sources is not None and not isinstance(enabled_sources, list):
        result.errors.append("enabled_sources: deve essere una lista")

    result.source_count = len(sources)
    seen_source_ids: set[str] = set()
    for index, source_item in enumerate(sources):
        source_path = f"sources[{index}]"
        if not isinstance(source_item, dict):
            result.errors.append(f"{source_path}: deve essere un mapping")
            continue

        _validate_required_fields(source_item, source_path, result)
        _validate_source_id(source_item, source_path, seen_source_ids, result)
        _validate_optional_shapes(source_item, source_path, result)
        _warn_unknown_fields(source_item, source_path, result)
        _validate_declared_levels(source_item, source_path, result, levels_root=levels_root)
        _validate_quality_contracts(source_item, source_path, result, levels_root=levels_root)

    return result


def format_validation_result(result: RegistryValidationResult) -> str:
    lines: list[str] = []
    if result.valid:
        lines.append("Registry fonti valido")
    else:
        lines.append("Registry fonti non valido")
    lines.append(f"Fonti: {result.source_count}")
    lines.append(f"Warning: {len(result.warnings)}")

    if result.errors:
        lines.append("")
        lines.append("Errori:")
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.append("")
        lines.append("Warning:")
        lines.extend(f"- {warning}" for warning in result.warnings)

    return "\n".join(lines)


def _validate_required_fields(
    source_item: dict[str, Any],
    source_path: str,
    result: RegistryValidationResult,
) -> None:
    for field_name in sorted(REQUIRED_SOURCE_FIELDS):
        value = source_item.get(field_name)
        if value is None or str(value).strip() == "":
            result.errors.append(f"{source_path}.{field_name}: campo mancante")


def _validate_source_id(
    source_item: dict[str, Any],
    source_path: str,
    seen_source_ids: set[str],
    result: RegistryValidationResult,
) -> None:
    raw_source_id = source_item.get("id")
    source_id = str(raw_source_id).strip() if raw_source_id is not None else ""
    if not source_id:
        return
    if source_id in seen_source_ids:
        result.errors.append(f"{source_path}.id: valore duplicato: {source_id}")
        return
    seen_source_ids.add(source_id)


def _validate_optional_shapes(
    source_item: dict[str, Any],
    source_path: str,
    result: RegistryValidationResult,
) -> None:
    priority = source_item.get("priority")
    if priority is not None and not isinstance(priority, (int, float)):
        result.errors.append(f"{source_path}.priority: deve essere numerico")

    for field_name in sorted(LIST_FIELDS):
        value = source_item.get(field_name)
        if value is not None and not isinstance(value, list):
            result.errors.append(f"{source_path}.{field_name}: deve essere una lista")

    for field_name in sorted(MAPPING_FIELDS):
        value = source_item.get(field_name)
        if value is not None and not isinstance(value, dict):
            result.errors.append(f"{source_path}.{field_name}: deve essere un mapping")


def _warn_unknown_fields(
    source_item: dict[str, Any],
    source_path: str,
    result: RegistryValidationResult,
) -> None:
    for field_name in sorted(source_item):
        if field_name not in KNOWN_SOURCE_FIELDS:
            result.warnings.append(f"{source_path}.{field_name}: campo non riconosciuto")


def _validate_declared_levels(
    source_item: dict[str, Any],
    source_path: str,
    result: RegistryValidationResult,
    *,
    levels_root: Path | None,
) -> None:
    if levels_root is None:
        return

    raw_source_id = source_item.get("id")
    source_id = str(raw_source_id).strip() if raw_source_id is not None else ""
    if not source_id:
        return

    for directory_name, level_name in REQUIRED_LEVEL_DIRECTORIES.items():
        expected_path = levels_root / directory_name / f"{source_id}.yaml"
        if not expected_path.exists():
            relative_path = expected_path.relative_to(levels_root)
            result.errors.append(
                f"{source_path}.{level_name}: file dichiarativo mancante: {relative_path.as_posix()}"
            )


def _validate_quality_contracts(
    source_item: dict[str, Any],
    source_path: str,
    result: RegistryValidationResult,
    *,
    levels_root: Path | None,
) -> None:
    if levels_root is None:
        return
    raw_source_id = source_item.get("id")
    source_id = str(raw_source_id).strip() if raw_source_id is not None else ""
    if not source_id:
        return

    result_logic_path = levels_root / "source_result_logic" / f"{source_id}.yaml"
    if result_logic_path.exists():
        _validate_result_logic_quality(result_logic_path, source_path, result)

    detail_logic_path = levels_root / "source_detail_logic" / f"{source_id}.yaml"
    if detail_logic_path.exists():
        _validate_detail_logic_quality(detail_logic_path, source_path, result)


def _validate_result_logic_quality(path: Path, source_path: str, result: RegistryValidationResult) -> None:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        result.errors.append(f"{source_path}.result_logic: YAML non valido: {error}")
        return
    logic = payload.get("result_logic", payload) if isinstance(payload, dict) else {}
    if not isinstance(logic, dict):
        result.errors.append(f"{source_path}.result_logic: deve essere un mapping YAML")
        return
    signals = logic.get("signals", {}) if isinstance(logic.get("signals", {}), dict) else {}
    selector = str(signals.get("result_link_selector", "")).strip().casefold()
    filters = logic.get("candidate_filters", {}) if isinstance(logic.get("candidate_filters", {}), dict) else {}
    if selector in {"a[href]", "a"} and not filters:
        result.warnings.append(
            f"{source_path}.result_logic: result_link_selector generico senza candidate_filters"
        )


def _validate_detail_logic_quality(path: Path, source_path: str, result: RegistryValidationResult) -> None:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        result.errors.append(f"{source_path}.detail_logic: YAML non valido: {error}")
        return
    logic = payload.get("detail_logic", payload) if isinstance(payload, dict) else {}
    if not isinstance(logic, dict):
        result.errors.append(f"{source_path}.detail_logic: deve essere un mapping YAML")
        return
    detail_level = str(logic.get("detail_level", "")).strip()
    if not detail_level:
        result.warnings.append(f"{source_path}.detail_logic: detail_level mancante")
        return
    if detail_level not in DETAIL_LEVELS:
        result.errors.append(f"{source_path}.detail_logic.detail_level: valore non ammesso: {detail_level}")
    claim_mappings = logic.get("claim_mappings", []) or []
    review_notes = logic.get("review_notes", []) or []
    if detail_level == "claims_extractable" and not claim_mappings:
        result.warnings.append(f"{source_path}.detail_logic: claims_extractable senza claim_mappings")
    if detail_level in {"reference_only", "manual_review_only"} and not review_notes:
        result.warnings.append(f"{source_path}.detail_logic: review_notes consigliate per {detail_level}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida il registry YAML delle fonti.")
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml")
    args = parser.parse_args()

    sources_yaml = Path(args.sources_yaml)
    if args.sources_yaml == "ricerche/camalanca_fonti.yaml":
        sources_yaml = resolve_source_registry_path(Path.cwd())
    result = validate_sources_registry_file(sources_yaml)
    print(format_validation_result(result))
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
