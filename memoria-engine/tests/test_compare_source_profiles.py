from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.compare_source_profiles import (
    compare_source_profiles,
    format_source_profile_diff,
    main,
)
from caduti_fonti_report.source_profiles import (
    SourceSearchField,
    SourceSearchOption,
    SourceSearchProfile,
    write_source_search_profile,
)


class CompareSourceProfilesTests(unittest.TestCase):
    def test_identical_profiles_have_no_differences(self) -> None:
        expected = _profile()
        actual = _profile()

        diff = compare_source_profiles(expected, actual)

        self.assertFalse(diff.has_differences)
        self.assertEqual(diff.unchanged, ["Surname", "WarSelect"])

    def test_detects_added_and_removed_fields(self) -> None:
        expected = _profile(fields=["Surname", "WarSelect"])
        actual = _profile(fields=["Forename", "Surname"])

        diff = compare_source_profiles(expected, actual)

        self.assertEqual(diff.added, ["Forename"])
        self.assertEqual(diff.removed, ["WarSelect"])
        self.assertTrue(diff.has_differences)

    def test_detects_type_default_required_label_and_option_changes(self) -> None:
        expected = _profile()
        actual = _profile()
        actual.fields[0].label = "Family name"
        actual.fields[0].field_type = "search"
        actual.fields[0].required = True
        actual.fields[1].default = "1"
        actual.fields[1].options.append(SourceSearchOption(value="3", label="Post-war"))

        diff = compare_source_profiles(expected, actual)

        changes = {item.field_id: item.changes for item in diff.modified}
        self.assertEqual(
            changes["Surname"],
            ["tipo cambiato", "label cambiata", "required cambiato"],
        )
        self.assertEqual(changes["WarSelect"], ["default cambiato", "opzioni cambiate"])

    def test_format_renders_summary_and_details(self) -> None:
        diff = compare_source_profiles(_profile(fields=["Surname"]), _profile(fields=["Surname", "WarSelect"]))

        text = format_source_profile_diff(expected_path="expected.yaml", actual_path="actual.yaml", diff=diff)

        self.assertIn("Confronto profili fonte", text)
        self.assertIn("Campi invariati: 1", text)
        self.assertIn("Campi aggiunti: 1", text)
        self.assertIn("- WarSelect", text)

    def test_cli_fail_on_diff_returns_one(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        expected_path = repo_root / ".tmp-tests" / "profile-expected.yaml"
        actual_path = repo_root / ".tmp-tests" / "profile-actual.yaml"
        expected_path.parent.mkdir(exist_ok=True)

        try:
            write_source_search_profile(expected_path, _profile(fields=["Surname"]))
            write_source_search_profile(actual_path, _profile(fields=["Surname", "WarSelect"]))

            exit_code = main(
                [
                    "--expected",
                    str(expected_path),
                    "--actual",
                    str(actual_path),
                    "--fail-on-diff",
                ]
            )
        finally:
            expected_path.unlink(missing_ok=True)
            actual_path.unlink(missing_ok=True)

        self.assertEqual(exit_code, 1)

    def test_powershell_entrypoint_runs_compare_module(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "compare_source_profile.ps1"

        text = script_path.read_text(encoding="utf-8")

        self.assertIn("caduti_fonti_report.compare_source_profiles", text)
        self.assertIn("ValueFromRemainingArguments", text)


def _profile(fields: list[str] | None = None) -> SourceSearchProfile:
    selected = fields or ["Surname", "WarSelect"]
    all_fields = {
        "Surname": SourceSearchField(field_id="Surname", label="Surname", field_type="text"),
        "Forename": SourceSearchField(field_id="Forename", label="Forename", field_type="text"),
        "WarSelect": SourceSearchField(
            field_id="WarSelect",
            label="War",
            field_type="select",
            default="2",
            options=[
                SourceSearchOption(value="", label="All wars"),
                SourceSearchOption(value="1", label="First World War"),
                SourceSearchOption(value="2", label="Second World War"),
            ],
        ),
    }
    return SourceSearchProfile(source_id="cwgc", engine="cwgc_find_war_dead", fields=[all_fields[item] for item in selected])


if __name__ == "__main__":
    unittest.main()
