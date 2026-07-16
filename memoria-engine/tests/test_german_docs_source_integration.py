from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.german_docs_in_russia_executor import GermanDocsInRussiaSearchExecutor  # noqa: E402
from caduti_fonti_report.connectors.uniform_source_connector import UniformSourceConnector  # noqa: E402
from caduti_fonti_report.models import PersonQuery, Source  # noqa: E402
from caduti_fonti_report.queries import default_query  # noqa: E402
from caduti_fonti_report.source_definitions import load_source_definition  # noqa: E402


def make_german_docs_source() -> Source:
    return Source(
        source_id="german_docs_in_russia_wwii",
        source_name="German Docs in Russia - documenti tedeschi della Seconda guerra mondiale",
        kind="archival_document_repository",
        build_query=default_query,
        search_url_builder=lambda query: "https://wwii.germandocsinrussia.org/ru",
        form={
            "browse_root_url": "https://wwii.germandocsinrussia.org/ru/nodes/28468-top",
            "fund_500_url": "https://wwii.germandocsinrussia.org/ru/nodes/1-fond-500",
        },
        note="Fonte archivistica gerarchica fond/opis/delo/pagina.",
        timeout=5,
    )


class GermanDocsSourceIntegrationTests(unittest.TestCase):
    def test_source_definition_loads_and_uses_dedicated_executor(self) -> None:
        definition = load_source_definition(make_german_docs_source(), repo_root=Path(__file__).resolve().parents[1])

        self.assertEqual(definition.source_id, "german_docs_in_russia_wwii")
        self.assertEqual(definition.executor_id, "german_docs_in_russia_executor")
        self.assertEqual(definition.result_parser_id, "generic_result_page_parser")
        self.assertEqual(definition.detail_fetch_mode, "detail_page")
        self.assertEqual(definition.claim_extraction_mode, "detail_logic")
        self.assertEqual(definition.profile_path, "memoria-sources/source_profiles/german_docs_in_russia_wwii.yaml")
        self.assertEqual(definition.strategy_path, "memoria-sources/source_strategies/german_docs_in_russia_wwii.yaml")
        self.assertEqual(definition.result_logic_path, "memoria-sources/source_result_logic/german_docs_in_russia_wwii.yaml")
        self.assertEqual(definition.detail_logic_path, "memoria-sources/source_detail_logic/german_docs_in_russia_wwii.yaml")
        self.assertIsNotNone(definition.profile)
        self.assertIsNotNone(definition.strategy_definition)
        self.assertIsNotNone(definition.result_logic)
        self.assertIsNotNone(definition.detail_logic)

    def test_uniform_connector_treats_hierarchy_nodes_as_candidate_results_then_detail_documents(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = make_german_docs_source()
        definition = load_source_definition(source, repo_root=repo_root)
        fetched_urls: list[str] = []

        def fetcher(url: str, timeout: int) -> str:
            fetched_urls.append(url)
            return """
            <html><body>
              <h1>Fond 500</h1>
              <a href="/ru/nodes/9329-opis-12475-tankovye-korpusa">Opis 12475 - Tankovye korpusa</a>
              <a href="/ru/nodes/21261-delo-30-documentation">Delo 30 - XIV Panzerkorps</a>
            </body></html>
            """

        def detail_html(url: str) -> str:
            return """
            <html><body>
              <h1>Delo 30 - XIV Panzerkorps</h1>
              <p>Fond 500 Opis 12475 Delo 30 16.08.1944</p>
            </body></html>
            """

        connector = UniformSourceConnector(
            source,
            source_definition=definition,
            executor=GermanDocsInRussiaSearchExecutor(fetcher=fetcher),
            detail_html_provider=detail_html,
            run_id="german-docs-source-test",
            now_factory=lambda: datetime(2026, 5, 31, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
            max_search_attempts=1,
        )

        results = connector.search_person(PersonQuery(full_name="Purocielo"))

        self.assertEqual(fetched_urls, ["https://wwii.germandocsinrussia.org/ru/nodes/1-fond-500"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "archival_hierarchy_candidates")
        self.assertEqual([hit.title for hit in results[0].hits], ["Opis 12475 - Tankovye korpusa", "Delo 30 - XIV Panzerkorps"])

        documents = connector.fetch_detail(results[0])

        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].source_id, "german_docs_in_russia_wwii")
        self.assertEqual(documents[0].metadata["access_mode"], "detail_page")
        self.assertEqual(documents[0].metadata["detail_assessment"], "archival_metadata_candidates_extracted")
        claims = connector.extract_evidence(documents[0])
        self.assertTrue(any(claim.field == "archive.fund" and claim.value == "500" for claim in claims))
        self.assertTrue(all(claim.review_status == "unreviewed" for claim in claims))


if __name__ == "__main__":
    unittest.main()
