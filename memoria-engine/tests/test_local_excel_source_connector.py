from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.local_excel_connector import (
    LocalExcelSearchExecutor,
    LocalExcelSearchStrategy,
    LocalExcelSourceConnector,
)
from caduti_fonti_report.connectors.search_strategy import SearchAttempt
from caduti_fonti_report.models import PersonQuery, Source


def make_excel_source() -> Source:
    return Source(
        source_id="storia_memoria_bo_excel",
        source_name="Storia e Memoria Excel",
        kind="local_excel",
        build_query=lambda caduto: caduto.nome,
        search_url_builder=lambda query: f"file:///archive/{query}",
        local={
            "name_order": "surname_first",
            "surname_column": "Cognome",
            "given_name_column": "Nome",
            "alias_columns": "Nome battaglia",
            "snippet_columns": "Nome battaglia,Nato comune,Brigata di appartenenza",
        },
        extraction={
            "method": "local_table_claims",
            "claim_mappings": [
                {"column": "Nome battaglia", "field": "alias", "confidence": 0.8},
                {"column": "Nato comune", "field": "birth.place", "confidence": 0.75},
                {"column": "Brigata di appartenenza", "field": "formation.name", "confidence": 0.7},
            ],
        },
        note="Fonte locale.",
    )


def workbook_rows() -> list[tuple[Path, str, list[dict[str, str]]]]:
    return [
        (
            Path("archivi/test.xls"),
            "Foglio1",
            [
                {
                    "__row_number__": "2",
                    "Cognome": "ROSSI",
                    "Nome": "MARIO",
                    "Nome battaglia": "Falco",
                    "Nato comune": "Faenza",
                    "Brigata di appartenenza": "36 Brigata",
                },
                {
                    "__row_number__": "3",
                    "Cognome": "BIANCHI",
                    "Nome": "LUIGI",
                    "Nome battaglia": "",
                    "Nato comune": "Imola",
                    "Brigata di appartenenza": "",
                },
            ],
        )
    ]


class LocalExcelSourceConnectorTests(unittest.TestCase):
    def test_strategy_generates_canonical_and_alias_attempts(self) -> None:
        source = make_excel_source()
        strategy = LocalExcelSearchStrategy()

        attempts = strategy.build_attempts(
            source=source,
            query=PersonQuery(full_name="ROSSI MARIO", aliases=["Falco", "ROSSI MARIO"]),
        )

        self.assertEqual([attempt.query_text for attempt in attempts], ["ROSSI MARIO", "Falco"])
        self.assertEqual(attempts[0].attempt_id, "canonical-name")
        self.assertEqual(attempts[1].attempt_id, "alias-1")

    def test_executor_consumes_attempt_without_generating_strategy(self) -> None:
        source = make_excel_source()
        executor = LocalExcelSearchExecutor()
        attempt = SearchAttempt(
            attempt_id="expert-attempt",
            label="Tentativo esperto",
            query_text="ROSSI MARIO",
            fields={"full_name": "ROSSI MARIO"},
        )

        with patch(
            "caduti_fonti_report.connectors.local_excel_connector.load_excel_rows",
            return_value=workbook_rows(),
        ):
            results = executor.execute(source=source, attempt=attempt)

        self.assertEqual(len(results), 1)
        self.assertIs(results[0].attempt, attempt)
        self.assertEqual(results[0].title, "ROSSI MARIO")
        self.assertIn("Riga Excel: 2", results[0].snippet)

    def test_connector_search_fetch_extract_pipeline_for_local_excel(self) -> None:
        source = make_excel_source()
        connector = LocalExcelSourceConnector(
            source,
            run_id="test-run",
            now_factory=lambda: datetime(2026, 4, 30, 12, 0, tzinfo=UTC),
        )

        with patch(
            "caduti_fonti_report.connectors.local_excel_connector.load_excel_rows",
            return_value=workbook_rows(),
        ):
            results = connector.search_person(PersonQuery(full_name="ROSSI MARIO"))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "ok")
        self.assertEqual(len(results[0].hits), 1)

        documents = connector.fetch_detail(results[0])
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].source_id, "storia_memoria_bo_excel")
        self.assertEqual(documents[0].metadata["access_mode"], "local_table_row")
        self.assertIn("riga 2", documents[0].title)

        claims = connector.extract_evidence(documents[0])
        self.assertEqual([claim.field for claim in claims], ["alias", "birth.place", "formation.name"])
        self.assertEqual([claim.value for claim in claims], ["Falco", "Faenza", "36 Brigata"])
        self.assertTrue(all(claim.source_document_id == documents[0].document_id for claim in claims))
        self.assertTrue(all(claim.review_status == "unreviewed" for claim in claims))

    def test_connector_returns_no_results_without_fetch_or_extract(self) -> None:
        source = make_excel_source()
        connector = LocalExcelSourceConnector(source)

        with patch(
            "caduti_fonti_report.connectors.local_excel_connector.load_excel_rows",
            return_value=workbook_rows(),
        ):
            results = connector.search_person(PersonQuery(full_name="VERDI ANNA"))

        self.assertEqual(results[0].status, "no_results")
        self.assertEqual(results[0].hits, [])
        self.assertEqual(connector.fetch_detail(results[0]), [])


if __name__ == "__main__":
    unittest.main()
