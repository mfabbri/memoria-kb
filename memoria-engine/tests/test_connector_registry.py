from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.local_excel_connector import LocalExcelSourceConnector
from caduti_fonti_report.connectors.registry import create_source_connector, describe_source_connector
from caduti_fonti_report.connectors.uniform_source_connector import UniformSourceConnector
from caduti_fonti_report.models import Source
from caduti_fonti_report.queries import default_query


def make_source(source_id: str, kind: str) -> Source:
    return Source(
        source_id=source_id,
        source_name=source_id,
        kind=kind,
        build_query=default_query,
        search_url_builder=lambda query: f"https://example.test/?q={query}",
    )


class ConnectorRegistryTests(unittest.TestCase):
    def test_registry_returns_uniform_connector_for_cwgc(self) -> None:
        source = make_source("cwgc", "cwgc")

        connector = create_source_connector(source, repo_root=Path(__file__).resolve().parents[1])
        registration = describe_source_connector(source)

        self.assertIsInstance(connector, UniformSourceConnector)
        self.assertTrue(registration.evidence_aware)
        self.assertEqual(registration.detail_fetch, "detail_page")
        self.assertEqual(registration.claim_extraction, "detail_logic")

    def test_registry_returns_local_excel_evidence_aware_connector(self) -> None:
        source = make_source("storia_memoria_bo_excel", "local_excel")

        connector = create_source_connector(source)
        registration = describe_source_connector(source)

        self.assertIsInstance(connector, LocalExcelSourceConnector)
        self.assertTrue(registration.evidence_aware)
        self.assertEqual(registration.detail_fetch, "local_table_row")
        self.assertEqual(registration.claim_extraction, "local_table_claims")

    def test_registry_returns_uniform_connector_for_partigiani_italia(self) -> None:
        source = make_source("partigiani_italia", "search_form_get_name")

        connector = create_source_connector(source, repo_root=Path(__file__).resolve().parents[1])
        registration = describe_source_connector(source)

        self.assertIsInstance(connector, UniformSourceConnector)
        self.assertTrue(registration.evidence_aware)
        self.assertEqual(registration.detail_fetch, "detail_page")
        self.assertEqual(registration.claim_extraction, "detail_logic")

    def test_registry_returns_uniform_connector_for_storia_memoria_bo(self) -> None:
        source = make_source("storia_memoria_bo", "storia_memoria_bo")

        connector = create_source_connector(source, repo_root=Path(__file__).resolve().parents[1])
        registration = describe_source_connector(source)

        self.assertIsInstance(connector, UniformSourceConnector)
        self.assertTrue(registration.evidence_aware)
        self.assertEqual(registration.detail_fetch, "detail_page")
        self.assertEqual(registration.claim_extraction, "detail_logic")

    def test_registry_returns_uniform_connector_for_tna_wo417(self) -> None:
        source = make_source("tna_wo417", "credentialed")

        connector = create_source_connector(source, repo_root=Path(__file__).resolve().parents[1])
        registration = describe_source_connector(source)

        self.assertIsInstance(connector, UniformSourceConnector)
        self.assertTrue(registration.evidence_aware)
        self.assertEqual(registration.detail_fetch, "detail_page")
        self.assertEqual(registration.claim_extraction, "detail_logic")


if __name__ == "__main__":
    unittest.main()
