from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.source_profiles import (
    SourceSearchField,
    SourceSearchOption,
    SourceSearchProfile,
    load_source_search_profile,
    source_search_profile_from_dict,
    source_search_profile_to_dict,
    write_source_search_profile,
)


class SourceProfilesTests(unittest.TestCase):
    def test_profile_serializes_with_yaml_friendly_field_names(self) -> None:
        profile = SourceSearchProfile(
            source_id="cwgc",
            engine="cwgc_find_war_dead",
            fields=[
                SourceSearchField(
                    field_id="WarSelect",
                    label="War",
                    field_type="select",
                    default="2",
                    options=[SourceSearchOption(value="2", label="Second World War")],
                )
            ],
            strategy_notes=["Usare WarSelect=2."],
        )

        payload = source_search_profile_to_dict(profile)

        self.assertEqual(payload["fields"][0]["id"], "WarSelect")
        self.assertEqual(payload["fields"][0]["type"], "select")
        self.assertNotIn("field_id", payload["fields"][0])
        self.assertNotIn("field_type", payload["fields"][0])

    def test_profile_loads_from_yaml_payload(self) -> None:
        profile = source_search_profile_from_dict(
            {
                "source_id": "cwgc",
                "engine": "cwgc_find_war_dead",
                "fields": [
                    {
                        "id": "Surname",
                        "label": "Surname",
                        "type": "text",
                        "role": "family_name",
                    }
                ],
            }
        )

        self.assertEqual(profile.source_id, "cwgc")
        self.assertEqual(profile.fields[0].field_id, "Surname")
        self.assertEqual(profile.fields[0].field_type, "text")
        self.assertEqual(profile.fields[0].role, "family_name")

    def test_load_real_cwgc_profile(self) -> None:
        profile_path = Path(__file__).resolve().parents[2] / "memoria-sources" / "source_profiles" / "cwgc.yaml"

        profile = load_source_search_profile(profile_path)
        fields = {field.field_id: field for field in profile.fields}

        self.assertEqual(profile.source_id, "cwgc")
        self.assertEqual(profile.engine, "cwgc_find_war_dead")
        self.assertIn("Surname", fields)
        self.assertIn("Forename", fields)
        self.assertIn("WarSelect", fields)
        self.assertGreaterEqual(len(fields), 30)
        self.assertEqual(fields["WarSelect"].field_type, "checkbox")
        self.assertEqual(fields["WarSelect"].default, "1")
        self.assertEqual(fields["WarSelect"].label, "First World War")
        self.assertIn("Per il caso Purocielo/Ca' di Malanca", " ".join(profile.strategy_notes))

    def test_load_real_storia_memoria_bo_profile(self) -> None:
        profile_path = Path(__file__).resolve().parents[2] / "memoria-sources" / "source_profiles" / "storia_memoria_bo.yaml"

        profile = load_source_search_profile(profile_path)
        fields = {field.field_id: field for field in profile.fields}

        self.assertEqual(profile.source_id, "storia_memoria_bo")
        self.assertEqual(profile.engine, "storia_memoria_bo_advanced_people")
        self.assertEqual(fields["nom"].role, "given_name")
        self.assertEqual(fields["cog"].role, "family_name")
        self.assertEqual(fields["nas[min]"].metadata["value_format"], "iso_date")
        self.assertIn("Usare direttamente /ricerca-avanzata/persone", " ".join(profile.strategy_notes))
        self.assertIn("non dalla vecchia classe CSS link-assoluto", " ".join(profile.strategy_notes))

    def test_load_real_partigiani_italia_profile(self) -> None:
        profile_path = Path(__file__).resolve().parents[2] / "memoria-sources" / "source_profiles" / "partigiani_italia.yaml"

        profile = load_source_search_profile(profile_path)
        fields = {field.field_id: field for field in profile.fields}

        self.assertEqual(profile.source_id, "partigiani_italia")
        self.assertEqual(profile.engine, "partigiani_italia_public_search")
        self.assertEqual(fields["nome"].role, "given_name")
        self.assertEqual(fields["cognome"].role, "family_name")
        self.assertEqual(fields["nome_batt"].role, "alias")
        self.assertEqual(fields["lm"].default, "20")
        self.assertIn("nome_batt", " ".join(profile.strategy_notes))

    def test_load_real_tna_wo417_profile(self) -> None:
        profile_path = Path(__file__).resolve().parents[2] / "memoria-sources" / "source_profiles" / "tna_wo417.yaml"

        profile = load_source_search_profile(profile_path)
        fields = {field.field_id: field for field in profile.fields}

        self.assertEqual(profile.source_id, "tna_wo417")
        self.assertEqual(profile.engine, "tna_discovery_advanced_search")
        self.assertEqual(fields["_ep"].role, "exact_phrase")
        self.assertEqual(fields["_cr"].default, "WO 417")
        self.assertEqual(fields["repository"].default, "true")

    def test_write_and_reload_profile(self) -> None:
        tmp_path = Path(__file__).resolve().parents[1] / ".tmp-tests" / "profile-test.yaml"
        tmp_path.parent.mkdir(exist_ok=True)
        profile = SourceSearchProfile(source_id="test", engine="fixture")

        try:
            write_source_search_profile(tmp_path, profile)
            loaded = load_source_search_profile(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        self.assertEqual(loaded.source_id, "test")
        self.assertEqual(loaded.engine, "fixture")


if __name__ == "__main__":
    unittest.main()
