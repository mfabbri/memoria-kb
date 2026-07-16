from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.profile_html_forms import profile_search_form_html


class ProfileHtmlFormsTests(unittest.TestCase):
    def test_profile_cwgc_fixture_extracts_expected_fields(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parents[1]
            / "tests"
            / "fixtures"
            / "source_profiles"
            / "cwgc_find_war_dead.html"
        )
        html = fixture_path.read_text(encoding="utf-8")

        profile = profile_search_form_html(
            html=html,
            source_id="cwgc",
            engine="cwgc_find_war_dead",
            discovery={"method": "fixture"},
        )
        fields = {field.field_id: field for field in profile.fields}

        self.assertEqual(profile.source_id, "cwgc")
        self.assertEqual(profile.discovery["method"], "fixture")
        self.assertEqual(fields["Surname"].label, "Surname")
        self.assertEqual(fields["Surname"].field_type, "text")
        self.assertEqual(fields["Forename"].label, "Forename")
        self.assertEqual(fields["WarSelect"].field_type, "select")
        self.assertEqual(fields["WarSelect"].default, "2")
        self.assertEqual(
            [(option.value, option.label) for option in fields["WarSelect"].options],
            [
                ("", "All wars"),
                ("1", "First World War"),
                ("2", "Second World War"),
            ],
        )

    def test_duplicate_field_names_are_ignored_after_first_seen(self) -> None:
        html = """
        <label for="Surname">Surname</label>
        <input id="Surname" name="Surname" type="text">
        <input id="SurnameDuplicate" name="Surname" type="hidden" value="ignored">
        """

        profile = profile_search_form_html(html=html, source_id="x", engine="fixture")

        self.assertEqual([field.field_id for field in profile.fields], ["Surname"])
        self.assertEqual(profile.fields[0].field_type, "text")


if __name__ == "__main__":
    unittest.main()
