from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.models import Source
from caduti_fonti_report.queries import default_query
from caduti_fonti_report.source_definitions import load_source_definition


class SourceDefinitionsTests(unittest.TestCase):
    def test_load_cwgc_source_definition_from_yaml(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = Source(
            source_id="cwgc",
            source_name="CWGC",
            kind="cwgc",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.cwgc.org/find-records/find-war-dead/",
        )

        definition = load_source_definition(source, repo_root=repo_root)

        self.assertEqual(definition.source_id, "cwgc")
        self.assertEqual(definition.executor_id, "url_only_executor")
        self.assertEqual(definition.result_parser_id, "cwgc_result_parser")
        self.assertEqual(definition.detail_logic_path, "memoria-sources/source_detail_logic/cwgc.yaml")
        self.assertEqual(definition.detail_fetch_mode, "detail_page")
        self.assertEqual(definition.claim_extraction_mode, "detail_logic")
        self.assertEqual(definition.detail_logic.engine, "cwgc_casualty_detail")

    def test_load_partigiani_italia_source_definition_from_yaml(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = Source(
            source_id="partigiani_italia",
            source_name="I Partigiani d'Italia - ricerca pubblica",
            kind="search_form_get_name",
            build_query=default_query,
            search_url_builder=lambda query: "https://partigianiditalia.cultura.gov.it/cerca/",
        )

        definition = load_source_definition(source, repo_root=repo_root)

        self.assertEqual(definition.source_id, "partigiani_italia")
        self.assertEqual(definition.profile_path, "memoria-sources/source_profiles/partigiani_italia.yaml")
        self.assertEqual(definition.strategy_path, "memoria-sources/source_strategies/partigiani_italia.yaml")
        self.assertEqual(definition.result_logic_path, "memoria-sources/source_result_logic/partigiani_italia.yaml")
        self.assertEqual(definition.executor_id, "http_get_form_executor")
        self.assertEqual(definition.result_parser_id, "generic_result_page_parser")
        self.assertEqual(definition.detail_logic_path, "memoria-sources/source_detail_logic/partigiani_italia.yaml")
        self.assertEqual(definition.detail_fetch_mode, "detail_page")
        self.assertEqual(definition.claim_extraction_mode, "detail_logic")
        self.assertEqual(definition.profile.engine, "partigiani_italia_public_search")
        self.assertEqual(definition.strategy_definition.engine, "partigiani_italia_public_search")
        self.assertEqual(definition.detail_logic.engine, "partigiani_italia_person_detail")
        self.assertEqual(
            definition.result_logic.signals["result_link_selector"],
            'a[href*="/persona/"], a[href*="/partigiano/"], a[href*="/scheda/"], a[href*="/dettaglio/"], a[href*="/cerca/"]',
        )

    def test_load_storia_memoria_bo_source_definition_from_yaml(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = Source(
            source_id="storia_memoria_bo",
            source_name="Storia e Memoria di Bologna",
            kind="storia_memoria_bo",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.storiaememoriadibologna.it/ricerca-avanzata",
        )

        definition = load_source_definition(source, repo_root=repo_root)

        self.assertEqual(definition.source_id, "storia_memoria_bo")
        self.assertEqual(definition.executor_id, "storia_memoria_bo_executor")
        self.assertEqual(definition.result_parser_id, "generic_result_page_parser")
        self.assertEqual(definition.detail_logic_path, "memoria-sources/source_detail_logic/storia_memoria_bo.yaml")
        self.assertEqual(definition.detail_fetch_mode, "detail_page")
        self.assertEqual(definition.claim_extraction_mode, "detail_logic")
        self.assertEqual(definition.detail_logic.engine, "storia_memoria_bo_person_detail")
        self.assertEqual(definition.result_logic.signals["result_link_selector"], 'a[href*="/archivio/persone/"]')

    def test_load_tna_wo417_source_definition_from_yaml(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = Source(
            source_id="tna_wo417",
            source_name="TNA Discovery - WO 417",
            kind="credentialed",
            build_query=default_query,
            search_url_builder=lambda query: "https://discovery.nationalarchives.gov.uk/",
        )

        definition = load_source_definition(source, repo_root=repo_root)

        self.assertEqual(definition.source_id, "tna_wo417")
        self.assertEqual(definition.executor_id, "playwright_form_executor")
        self.assertEqual(definition.result_parser_id, "generic_result_page_parser")
        self.assertEqual(definition.detail_logic_path, "memoria-sources/source_detail_logic/tna_wo417.yaml")
        self.assertEqual(definition.detail_fetch_mode, "detail_page")
        self.assertEqual(definition.claim_extraction_mode, "detail_logic")
        self.assertEqual(definition.detail_logic.engine, "tna_discovery_record_detail")
        self.assertEqual(definition.result_logic.signals["result_link_selector"], 'a[href*="/details/r/"]')

    def test_load_fondazione_fossoli_source_definition_from_yaml(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = Source(
            source_id="fondazione_fossoli",
            source_name="Fondazione Fossoli - I Nomi di Fossoli",
            kind="search_page",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.fondazionefossoli.org/centro-studi/i-nomi-di-fossoli/",
        )

        definition = load_source_definition(source, repo_root=repo_root)

        self.assertEqual(definition.source_id, "fondazione_fossoli")
        self.assertEqual(definition.executor_id, "playwright_form_executor")
        self.assertEqual(definition.result_parser_id, "generic_result_page_parser")
        self.assertEqual(definition.detail_logic_path, "memoria-sources/source_detail_logic/fondazione_fossoli.yaml")
        self.assertEqual(definition.detail_fetch_mode, "detail_page")
        self.assertEqual(definition.claim_extraction_mode, "detail_logic")
        self.assertEqual(definition.profile.fields[0].field_id, "nome")
        self.assertEqual(definition.strategy_definition.attempts[0].template_id, "nome-cognome")
        self.assertEqual(definition.detail_logic.claim_mappings, [])


if __name__ == "__main__":
    unittest.main()
