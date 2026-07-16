from __future__ import annotations

import sys
import unittest
from pathlib import Path
import shutil
import uuid


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.validate_sources_registry import (
    format_validation_result,
    validate_sources_registry,
    validate_sources_registry_file,
)


class SourcesRegistryValidationTests(unittest.TestCase):
    def make_workspace_temp_dir(self) -> Path:
        base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
        base_dir.mkdir(exist_ok=True)
        tmp_dir = base_dir / f"registry-validation-{uuid.uuid4().hex}"
        tmp_dir.mkdir()
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))
        return tmp_dir

    def test_minimal_legacy_registry_is_valid(self) -> None:
        result = validate_sources_registry(
            {
                "sources": [
                    {
                        "id": "source_a",
                        "name": "Source A",
                        "kind": "search_page",
                    }
                ]
            }
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.source_count, 1)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])

    def test_evolved_registry_fields_are_valid(self) -> None:
        result = validate_sources_registry(
            {
                "enabled_sources": ["source_a"],
                "sources": [
                    {
                        "id": "source_a",
                        "name": "Source A",
                        "kind": "local_excel",
                        "group": "italian_local_archives",
                        "access_type": "local_file",
                        "priority": 1,
                        "legal_policy": {"allow_automated_search": True},
                        "supports": ["person_search", "evidence_extraction"],
                        "output_fields": ["birth.place"],
                        "raw_storage": {"enabled": True, "strategy": "local_table_row"},
                        "review": {"required": True},
                    }
                ],
            }
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])

    def test_missing_required_fields_are_errors(self) -> None:
        result = validate_sources_registry({"sources": [{"name": "Source A"}]})

        self.assertFalse(result.valid)
        self.assertIn("sources[0].id: campo mancante", result.errors)
        self.assertIn("sources[0].kind: campo mancante", result.errors)

    def test_priority_must_be_numeric(self) -> None:
        result = validate_sources_registry(
            {
                "sources": [
                    {
                        "id": "source_a",
                        "name": "Source A",
                        "kind": "search_page",
                        "priority": "alta",
                    }
                ]
            }
        )

        self.assertFalse(result.valid)
        self.assertIn("sources[0].priority: deve essere numerico", result.errors)

    def test_supports_and_output_fields_must_be_lists(self) -> None:
        result = validate_sources_registry(
            {
                "sources": [
                    {
                        "id": "source_a",
                        "name": "Source A",
                        "kind": "search_page",
                        "supports": "person_search",
                        "output_fields": "birth.place",
                    }
                ]
            }
        )

        self.assertFalse(result.valid)
        self.assertIn("sources[0].supports: deve essere una lista", result.errors)
        self.assertIn("sources[0].output_fields: deve essere una lista", result.errors)

    def test_policy_fields_must_be_mappings(self) -> None:
        result = validate_sources_registry(
            {
                "sources": [
                    {
                        "id": "source_a",
                        "name": "Source A",
                        "kind": "search_page",
                        "legal_policy": ["public"],
                        "raw_storage": "html_snapshot",
                        "review": True,
                    }
                ]
            }
        )

        self.assertFalse(result.valid)
        self.assertIn("sources[0].legal_policy: deve essere un mapping", result.errors)
        self.assertIn("sources[0].raw_storage: deve essere un mapping", result.errors)
        self.assertIn("sources[0].review: deve essere un mapping", result.errors)

    def test_unknown_fields_are_warnings(self) -> None:
        result = validate_sources_registry(
            {
                "sources": [
                    {
                        "id": "source_a",
                        "name": "Source A",
                        "kind": "search_page",
                        "unexpected": "value",
                    }
                ]
            }
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.warnings, ["sources[0].unexpected: campo non riconosciuto"])

    def test_duplicate_source_ids_are_errors(self) -> None:
        result = validate_sources_registry(
            {
                "sources": [
                    {"id": "source_a", "name": "Source A", "kind": "search_page"},
                    {"id": "source_a", "name": "Source B", "kind": "search_page"},
                ]
            }
        )

        self.assertFalse(result.valid)
        self.assertIn("sources[1].id: valore duplicato: source_a", result.errors)

    def test_registry_file_requires_all_declared_level_files(self) -> None:
        root = self.make_workspace_temp_dir()
        ricerche_dir = root / "ricerche"
        ricerche_dir.mkdir()
        for directory_name in ("source_profiles", "source_strategies", "source_result_logic", "source_detail_logic"):
            (ricerche_dir / directory_name).mkdir()

        registry_path = ricerche_dir / "fonti.yaml"
        registry_path.write_text(
            """
sources:
  - id: source_a
    name: Source A
    kind: search_page
""",
            encoding="utf-8",
        )
        (ricerche_dir / "source_profiles" / "source_a.yaml").write_text("source_id: source_a\n", encoding="utf-8")
        (ricerche_dir / "source_strategies" / "source_a.yaml").write_text("source_id: source_a\n", encoding="utf-8")
        (ricerche_dir / "source_result_logic" / "source_a.yaml").write_text("source_id: source_a\n", encoding="utf-8")

        result = validate_sources_registry_file(registry_path)

        self.assertFalse(result.valid)
        self.assertIn(
            "sources[0].detail_logic: file dichiarativo mancante: source_detail_logic/source_a.yaml",
            result.errors,
        )

    def test_real_registry_is_valid_from_memoria_sources(self) -> None:
        registry_path = Path(__file__).resolve().parents[2] / "memoria-sources" / "registry" / "camalanca_fonti.yaml"
        result = validate_sources_registry_file(registry_path)

        self.assertTrue(result.valid, result.errors)
        self.assertGreater(result.source_count, 0)

    def test_format_validation_result_renders_errors_and_warnings(self) -> None:
        result = validate_sources_registry(
            {
                "sources": [
                    {
                        "id": "",
                        "name": "Source A",
                        "kind": "search_page",
                        "unexpected": "value",
                    }
                ]
            }
        )

        text = format_validation_result(result)

        self.assertIn("Registry fonti non valido", text)
        self.assertIn("Fonti: 1", text)
        self.assertIn("- sources[0].id: campo mancante", text)
        self.assertIn("- sources[0].unexpected: campo non riconosciuto", text)


if __name__ == "__main__":
    unittest.main()
