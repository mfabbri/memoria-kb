from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.interface import SourceConnector
from caduti_fonti_report.connectors.legacy_adapter import LegacyConnectorAdapter, caduto_from_person_query
from caduti_fonti_report.connectors.search_strategy import SearchAttempt, SingleQuerySearchStrategy
from caduti_fonti_report.models import Caduto, PersonQuery, Source, SourceResult


def make_source() -> Source:
    return Source(
        source_id="source_a",
        source_name="Source A",
        kind="search_page",
        build_query=lambda caduto: caduto.nome,
        search_url_builder=lambda query: f"https://example.test/?q={query}",
    )


class SourceConnectorInterfaceTests(unittest.TestCase):
    def test_source_connector_protocol_declares_expected_methods(self) -> None:
        self.assertIn("search_person", SourceConnector.__dict__)
        self.assertIn("fetch_detail", SourceConnector.__dict__)
        self.assertIn("extract_evidence", SourceConnector.__dict__)

    def test_single_query_strategy_generates_one_attempt_without_executing_search(self) -> None:
        source = make_source()
        strategy = SingleQuerySearchStrategy()

        attempts = strategy.build_attempts(source=source, query=PersonQuery(full_name="ROSSI MARIO"))

        self.assertEqual(
            attempts,
            [
                SearchAttempt(
                    attempt_id="canonical-name",
                    label="Nome canonico",
                    query_text="ROSSI MARIO",
                    fields={"full_name": "ROSSI MARIO"},
                    metadata={"source_id": "source_a"},
                )
            ],
        )

    def test_legacy_adapter_uses_injected_run_source_and_returns_no_documents_or_claims(self) -> None:
        source = make_source()
        calls: list[Caduto] = []

        def fake_run_source(source_arg: Source, caduto: Caduto) -> SourceResult:
            calls.append(caduto)
            return SourceResult(
                source_id=source_arg.source_id,
                source_name=source_arg.source_name,
                status="ok",
                note="legacy",
                query=caduto.nome,
                search_url="https://example.test/",
            )

        adapter = LegacyConnectorAdapter(source, run_source_func=fake_run_source)
        results = adapter.search_person(PersonQuery(full_name="ROSSI MARIO"))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "ok")
        self.assertEqual(calls[0].nome, "ROSSI MARIO")
        self.assertEqual(adapter.fetch_detail(results[0]), [])
        self.assertEqual(adapter.extract_evidence(document=object()), [])

    def test_caduto_from_person_query_preserves_metadata_when_available(self) -> None:
        person_query = PersonQuery(
            full_name="ROSSI MARIO",
            place_hint="Italia",
            metadata={
                "intestazione_pdf": "ROSSI MARIO PDF",
                "nome": "ROSSI MARIO",
                "nascita": "1900",
                "morte": "1944",
            },
        )

        caduto = caduto_from_person_query(person_query)

        self.assertEqual(caduto.intestazione_pdf, "ROSSI MARIO PDF")
        self.assertEqual(caduto.nome, "ROSSI MARIO")
        self.assertEqual(caduto.origine_sulla_lapide, "Italia")
        self.assertEqual(caduto.nascita, "1900")
        self.assertEqual(caduto.morte, "1944")


if __name__ == "__main__":
    unittest.main()
