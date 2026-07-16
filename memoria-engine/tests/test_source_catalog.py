from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.source_catalog import resolve_source_catalog_root, resolve_source_registry_path


class SourceCatalogTests(unittest.TestCase):
    def test_engine_resolves_sibling_memoria_sources_as_primary_catalog(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        catalog_root = resolve_source_catalog_root(repo_root)

        self.assertEqual(catalog_root, repo_root.parent / "memoria-sources")

    def test_engine_resolves_sibling_memoria_sources_registry(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        registry_path = resolve_source_registry_path(repo_root)

        self.assertEqual(registry_path, repo_root.parent / "memoria-sources" / "registry" / "camalanca_fonti.yaml")


if __name__ == "__main__":
    unittest.main()
