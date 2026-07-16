from __future__ import annotations

from dataclasses import asdict
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.models import Caduto, SearchHit, SourceDocument, SourceResult, SourceSelection
from caduti_fonti_report.renderers import render_markdown, render_single_caduto_markdown, slugify


class RendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.caduto = Caduto(
            intestazione_pdf="PÀNOV “SERGIO”",
            nome="Panov Sergio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="Fonte 1",
            profilo_biografico="Profilo breve",
            episodio_documentato="Episodio breve",
        )
        self.source_selection = SourceSelection(
            source_file="ricerche/camalanca_fonti.yaml",
            selected_sources=[],
            selected_source_ids=["tna_wo417"],
            unresolved_source_ids=["missing_source"],
            used_fallback=True,
        )
        self.result = SourceResult(
            source_id="tna_wo417",
            source_name="TNA Discovery - WO 417",
            status="ok",
            note="Nota di test",
            query='exact="Panov Sergio"',
            search_url="https://example.test/results",
            hits=[SearchHit(title="Hit One", url="https://example.test/hit", snippet="Snippet", content="Contenuto scheda")],
        )
        self.detail_entry = {
            "result": asdict(self.result),
            "documents": [
                asdict(
                    SourceDocument(
                        document_id="doc-1",
                        source_id="tna_wo417",
                        title="WO 417 record",
                        url="https://example.test/hit",
                        raw_text="Nome: Panov Sergio Data: 1944 Luogo: Brisighella",
                        metadata={"detail_assessment": "detail_document_fetched"},
                    )
                )
            ],
            "claims": [],
        }
        self.detail_entry_with_plan = {
            **self.detail_entry,
            "planned_execution_mode": "first_planned_attempt",
            "planned_attempt_execution_limit": 1,
            "planned_attempts": [
                {
                    "source_id": "tna_wo417",
                    "attempt_id": "exact-identity",
                    "priority": 1,
                    "query_text": 'exact="Panov Sergio"',
                    "metadata": {
                        "field_resolution.kind": "source_place_mapping",
                        "field_resolution.id": "atlante-place-purocielo-ca-marcone",
                        "field_resolution.matched_terms": "Purocielo; Ca Marcone",
                        "field_resolution.output_fields": "comune=4030; provincia=39; regione=8",
                        "field_resolution.labels": "comune=Brisighella; provincia=Ravenna; regione=Emilia-Romagna",
                        "field_resolution.review_status": "unreviewed",
                    },
                }
            ],
            "matched_planned_attempt_id": "exact-identity",
            "matched_planned_attempt_priority": 1,
            "matched_planned_attempt_status": "matched",
        }

    def test_slugify_normalizes_problematic_sequences(self) -> None:
        self.assertEqual(slugify(self.caduto.intestazione_pdf), "panov-sergio")

    def test_render_markdown_includes_selection_notes_hits_and_detail_documents(self) -> None:
        markdown = render_markdown(
            [self.caduto],
            {self.caduto.intestazione_pdf: [self.result]},
            self.source_selection,
            {self.caduto.intestazione_pdf: [self.detail_entry]},
        )

        self.assertIn("File fonti usato come source of truth", markdown)
        self.assertIn("ID fonte presenti nel YAML ma non trovati nel registry", markdown)
        self.assertIn("nessuna fonte valida selezionata nel YAML", markdown)
        self.assertIn("### TNA Discovery - WO 417", markdown)
        self.assertIn("[Hit One](https://example.test/hit)", markdown)
        self.assertIn("Estratto risultati: Snippet", markdown)
        self.assertIn("Contenuto scheda: Contenuto scheda", markdown)
        self.assertIn("Documenti di dettaglio", markdown)
        self.assertIn("Estratto scheda: Nome: Panov Sergio Data: 1944 Luogo: Brisighella", markdown)

    def test_render_single_caduto_markdown_contains_csv_result_and_detail_data(self) -> None:
        markdown = render_single_caduto_markdown(self.caduto, [self.result], [self.detail_entry])

        self.assertIn("# PÀNOV “SERGIO”", markdown)
        self.assertIn("Fonti richiamate nel CSV: Fonte 1", markdown)
        self.assertIn("Stato: `ok`", markdown)
        self.assertIn("Nota di test", markdown)
        self.assertIn("Contenuto scheda: Contenuto scheda", markdown)
        self.assertIn("Documenti di dettaglio", markdown)
        self.assertIn("Valutazione dettaglio: `detail_document_fetched`", markdown)

    def test_render_markdown_includes_search_plan_audit(self) -> None:
        markdown = render_markdown(
            [self.caduto],
            {self.caduto.intestazione_pdf: [self.result]},
            self.source_selection,
            {self.caduto.intestazione_pdf: [self.detail_entry_with_plan]},
        )

        self.assertIn("Audit piano ricerca", markdown)
        self.assertIn("Modalita': `first_planned_attempt`", markdown)
        self.assertIn("Limite tentativi eseguiti: `1`", markdown)
        self.assertIn("Stato match tentativo: `matched`", markdown)
        self.assertIn("Tentativo: `exact-identity`", markdown)
        self.assertIn('Query pianificata: `exact="Panov Sergio"`', markdown)
        self.assertIn("Risoluzione campi fonte: `atlante-place-purocielo-ca-marcone`", markdown)
        self.assertIn("Stato revisione mapping: `unreviewed`", markdown)

    def test_render_single_caduto_markdown_includes_unmatched_search_plan_audit(self) -> None:
        unmatched_entry = {
            **self.detail_entry_with_plan,
            "matched_planned_attempt_id": "",
            "matched_planned_attempt_priority": 0,
            "matched_planned_attempt_status": "unmatched",
        }

        markdown = render_single_caduto_markdown(self.caduto, [self.result], [unmatched_entry])

        self.assertIn("Audit piano ricerca", markdown)
        self.assertIn("Stato match tentativo: `unmatched`", markdown)
        self.assertIn("Tentativo: non riconciliato con il risultato prodotto", markdown)
        self.assertIn("Primo tentativo pianificato: `exact-identity`", markdown)


if __name__ == "__main__":
    unittest.main()
