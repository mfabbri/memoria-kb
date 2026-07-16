from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .source_profiles import SourceSearchField, SourceSearchProfile, load_source_search_profile


@dataclass
class ModifiedField:
    field_id: str
    changes: list[str] = field(default_factory=list)


@dataclass
class SourceProfileDiff:
    unchanged: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[ModifiedField] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return bool(self.added or self.removed or self.modified)


def compare_source_profiles(expected: SourceSearchProfile, actual: SourceSearchProfile) -> SourceProfileDiff:
    expected_fields = _fields_by_id(expected)
    actual_fields = _fields_by_id(actual)

    diff = SourceProfileDiff()
    for field_id in sorted(expected_fields.keys() | actual_fields.keys()):
        if field_id not in expected_fields:
            diff.added.append(field_id)
            continue
        if field_id not in actual_fields:
            diff.removed.append(field_id)
            continue

        changes = _compare_fields(expected_fields[field_id], actual_fields[field_id])
        if changes:
            diff.modified.append(ModifiedField(field_id=field_id, changes=changes))
        else:
            diff.unchanged.append(field_id)

    return diff


def format_source_profile_diff(
    *,
    expected_path: Path | str,
    actual_path: Path | str,
    diff: SourceProfileDiff,
) -> str:
    lines = [
        "Confronto profili fonte",
        f"Expected: {expected_path}",
        f"Actual: {actual_path}",
        "",
        f"Campi invariati: {len(diff.unchanged)}",
        f"Campi aggiunti: {len(diff.added)}",
        f"Campi rimossi: {len(diff.removed)}",
        f"Campi modificati: {len(diff.modified)}",
    ]

    if diff.added:
        lines.extend(["", "Campi aggiunti:"])
        lines.extend(f"- {field_id}" for field_id in diff.added)

    if diff.removed:
        lines.extend(["", "Campi rimossi:"])
        lines.extend(f"- {field_id}" for field_id in diff.removed)

    if diff.modified:
        lines.extend(["", "Campi modificati:"])
        lines.extend(f"- {item.field_id}: {', '.join(item.changes)}" for item in diff.modified)

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        expected = load_source_search_profile(args.expected)
        actual = load_source_search_profile(args.actual)
    except (OSError, ValueError) as exc:
        parser.exit(status=2, message=f"Errore: {exc}\n")

    diff = compare_source_profiles(expected, actual)
    print(format_source_profile_diff(expected_path=args.expected, actual_path=args.actual, diff=diff))

    if args.fail_on_diff and diff.has_differences:
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Confronta due SourceSearchProfile YAML.")
    parser.add_argument("--expected", required=True, help="Profilo ufficiale o atteso.")
    parser.add_argument("--actual", required=True, help="Profilo generato o da verificare.")
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Ritorna exit code 1 quando vengono trovate differenze.",
    )
    return parser


def _fields_by_id(profile: SourceSearchProfile) -> dict[str, SourceSearchField]:
    return {field.field_id: field for field in profile.fields if field.field_id}


def _compare_fields(expected: SourceSearchField, actual: SourceSearchField) -> list[str]:
    changes: list[str] = []
    if expected.field_type != actual.field_type:
        changes.append("tipo cambiato")
    if expected.label != actual.label:
        changes.append("label cambiata")
    if expected.required != actual.required:
        changes.append("required cambiato")
    if expected.default != actual.default:
        changes.append("default cambiato")
    if _option_signature(expected) != _option_signature(actual):
        changes.append("opzioni cambiate")
    return changes


def _option_signature(field: SourceSearchField) -> list[tuple[str, str]]:
    return [(option.value, option.label) for option in field.options]


if __name__ == "__main__":
    raise SystemExit(main())
