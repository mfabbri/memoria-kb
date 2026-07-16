from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.profile_source_form import (
    format_profile_summary,
    main,
    profile_source_form_from_html_file,
    profile_source_form_from_url,
)
from caduti_fonti_report.source_profiles import load_source_search_profile


class ProfileSourceFormTests(unittest.TestCase):
    def test_html_file_mode_writes_loadable_yaml_profile(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        fixture_path = repo_root / "tests" / "fixtures" / "source_profiles" / "cwgc_find_war_dead.html"
        output_path = repo_root / ".tmp-tests" / "cwgc.generated.yaml"

        try:
            profile = profile_source_form_from_html_file(
                source_id="cwgc",
                engine="cwgc_find_war_dead",
                html_path=fixture_path,
                output_path=output_path,
            )
            loaded = load_source_search_profile(output_path)
        finally:
            output_path.unlink(missing_ok=True)

        fields = {field.field_id: field for field in loaded.fields}
        self.assertEqual(profile.source_id, "cwgc")
        self.assertEqual(loaded.engine, "cwgc_find_war_dead")
        self.assertEqual(loaded.discovery["method"], "html_file")
        self.assertIn("Surname", fields)
        self.assertIn("Forename", fields)
        self.assertEqual(fields["WarSelect"].field_type, "select")
        self.assertEqual(len(fields["WarSelect"].options), 3)

    def test_summary_lists_fields_and_option_counts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        fixture_path = repo_root / "tests" / "fixtures" / "source_profiles" / "cwgc_find_war_dead.html"
        output_path = repo_root / ".tmp-tests" / "cwgc.generated.yaml"

        try:
            profile = profile_source_form_from_html_file(
                source_id="cwgc",
                engine="cwgc_find_war_dead",
                html_path=fixture_path,
                output_path=output_path,
            )
        finally:
            output_path.unlink(missing_ok=True)

        summary = format_profile_summary(output_path=output_path, profile=profile)

        self.assertIn("Fonte: cwgc", summary)
        self.assertIn("Campi trovati: 3", summary)
        self.assertIn("- Surname [text]", summary)
        self.assertIn("- WarSelect [select] opzioni=3", summary)

    def test_url_mode_requires_explicit_playwright_flag(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        output_path = repo_root / ".tmp-tests" / "should-not-exist.yaml"

        with self.assertRaisesRegex(ValueError, "--use-playwright"):
            profile_source_form_from_url(
                source_id="cwgc",
                engine="cwgc_find_war_dead",
                url="https://example.test/search",
                output_path=output_path,
                use_playwright=False,
            )

        self.assertFalse(output_path.exists())

    def test_cli_html_mode_returns_zero_and_writes_output(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        fixture_path = repo_root / "tests" / "fixtures" / "source_profiles" / "cwgc_find_war_dead.html"
        output_path = repo_root / ".tmp-tests" / "cwgc.cli.generated.yaml"

        try:
            exit_code = main(
                [
                    "--source",
                    "cwgc",
                    "--engine",
                    "cwgc_find_war_dead",
                    "--html",
                    str(fixture_path),
                    "--output",
                    str(output_path),
                ]
            )
            loaded = load_source_search_profile(output_path)
        finally:
            output_path.unlink(missing_ok=True)

        self.assertEqual(exit_code, 0)
        self.assertEqual(loaded.source_id, "cwgc")
        self.assertEqual([field.field_id for field in loaded.fields], ["Surname", "Forename", "WarSelect"])

    def test_html_mode_can_save_html_snapshot(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        fixture_path = repo_root / "tests" / "fixtures" / "source_profiles" / "cwgc_find_war_dead.html"
        output_path = repo_root / ".tmp-tests" / "cwgc.snapshot.generated.yaml"
        snapshot_path = repo_root / ".tmp-tests" / "source-profiles" / "cwgc_find_war_dead.html"

        try:
            profile_source_form_from_html_file(
                source_id="cwgc",
                engine="cwgc_find_war_dead",
                html_path=fixture_path,
                output_path=output_path,
                save_html_path=snapshot_path,
            )
            snapshot = snapshot_path.read_text(encoding="utf-8")
        finally:
            output_path.unlink(missing_ok=True)
            snapshot_path.unlink(missing_ok=True)

        self.assertIn('name="Surname"', snapshot)
        self.assertIn('name="WarSelect"', snapshot)

    def test_powershell_entrypoint_runs_profile_source_form_module(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "profile_source_form.ps1"

        text = script_path.read_text(encoding="utf-8")

        self.assertIn("caduti_fonti_report.profile_source_form", text)
        self.assertIn("ValueFromRemainingArguments", text)


if __name__ == "__main__":
    unittest.main()
