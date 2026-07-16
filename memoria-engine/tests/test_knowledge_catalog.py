from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.knowledge_catalog import (  # noqa: E402
    default_military_glossary_dir,
    default_places_index_path,
    resolve_knowledge_root,
)


class KnowledgeCatalogTests(unittest.TestCase):
    def test_resolves_sibling_knowledge_repository(self) -> None:
        root = resolve_knowledge_root()

        self.assertEqual(root.name, "memoria-knowledge")
        self.assertTrue((root / "places" / "places.index.jsonld").exists())
        self.assertTrue((root / "glossary" / "military").exists())

    def test_defaults_prefer_knowledge_for_default_research_dir(self) -> None:
        root = resolve_knowledge_root()

        self.assertEqual(default_places_index_path(), root / "places" / "places.index.jsonld")
        self.assertEqual(default_military_glossary_dir(), root / "glossary" / "military")

    def test_explicit_research_dir_keeps_legacy_shape(self) -> None:
        research_dir = Path("remote") / "ricerche"

        self.assertEqual(default_places_index_path(research_dir), research_dir / "places" / "places.index.jsonld")
        self.assertEqual(default_military_glossary_dir(research_dir), research_dir / "military_glossaries")


if __name__ == "__main__":
    unittest.main()
