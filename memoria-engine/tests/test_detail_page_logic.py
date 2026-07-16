from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.detail_page_logic import DetailPageInterpreter, DetailPageSignals, extract_detail_page_signals, load_source_detail_logic


class DetailPageLogicTests(unittest.TestCase):
    def test_cwgc_detail_can_extract_claim_candidates(self) -> None:
        definition = load_source_detail_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_detail_logic" / "cwgc.yaml"
        )
        interpreter = DetailPageInterpreter(definition)

        signals = extract_detail_page_signals(
            source_id="cwgc",
            engine=definition.engine,
            html_text="""
            <html>
              <body>
                <h1>PANOV SERGIO</h1>
                <div>Rank: Private</div>
                <div>Service No.: 12345</div>
                <div>Date of Death: 11 October 1944</div>
                <div>Age: 24</div>
                <div>Cemetery: Forli War Cemetery</div>
              </body>
            </html>
            """,
            detail_logic=definition,
            result_url="https://www.cwgc.org/find-records/find-war-dead/casualty-details/123/panov-sergio/",
        )
        assessment = interpreter.interpret(signals)

        self.assertEqual(assessment.assessment, "claim_candidates_extracted")
        self.assertEqual(assessment.extracted_fields["person_name"], "PANOV SERGIO")
        self.assertEqual(assessment.extracted_fields["service_number"], "12345")
        self.assertEqual(assessment.extracted_fields["death_date"], "11 October 1944")

    def test_load_partigiani_italia_detail_logic(self) -> None:
        definition = load_source_detail_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_detail_logic" / "partigiani_italia.yaml"
        )

        self.assertEqual(definition.source_id, "partigiani_italia")
        self.assertEqual(definition.engine, "partigiani_italia_person_detail")
        self.assertTrue(definition.claim_mappings)
        self.assertTrue(any(mapping.field == "formation.name" for mapping in definition.claim_mappings))
        self.assertTrue(any("login" in item.casefold() for item in definition.blocked_text))

    def test_partigiani_italia_blocked_detail_is_marked_for_manual_review(self) -> None:
        definition = load_source_detail_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_detail_logic" / "partigiani_italia.yaml"
        )
        interpreter = DetailPageInterpreter(definition)

        signals = extract_detail_page_signals(
            source_id="partigiani_italia",
            engine=definition.engine,
            html_text="""
            <html><body>
              <p>La consultazione dei dati Ã¨ consentita esclusivamente agli utenti registrati. Esegui il login.</p>
            </body></html>
            """,
            detail_logic=definition,
            result_url="https://partigianiditalia.cultura.gov.it/persona/?id=123",
        )
        assessment = interpreter.interpret(signals)

        self.assertEqual(assessment.assessment, "detail_needs_manual_review")
        self.assertEqual(assessment.extracted_fields, {})

    def test_partigiani_italia_detail_text_is_cleaned_and_image_is_recorded(self) -> None:
        definition = load_source_detail_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_detail_logic" / "partigiani_italia.yaml"
        )

        signals = extract_detail_page_signals(
            source_id="partigiani_italia",
            engine=definition.engine,
            html_text="""
            <html>
              <body>
                <header>Area riservata Ciao utente Login</header>
                <main>
                  <div>Area riservata Sei collegato come utente Esci</div>
                  <nav>Home &gt;</nav>
                  <h1>Balboni, William</h1>
                  <h1>Balboni, William</h1>
                  <section>
                    <h2>Dati anagrafici</h2>
                    <p>Nome: William</p>
                    <p>Cognome: Balboni</p>
                    <p>Nato il: 1922 mag. 9</p>
                  </section>
                  <section>
                    <h2>Attivita partigiana</h2>
                    <p>Formazione: 36 Bianconcini Garibaldi, dal 1944 giu. 15 al 1944 ott. 11</p>
                    <p>Qualifica riconosciuta: Caduto</p>
                  </section>
                  <img src="/wp-content/uploads/schede/balboni-william.jpg" alt="Scheda Balboni William">
                </main>
                <footer>ISTITUTO CENTRALE PER GLI ARCHIVI Privacy Overview</footer>
              </body>
            </html>
            """,
            detail_logic=definition,
            result_url="https://partigianiditalia.cultura.gov.it/persona/?id=abc",
        )
        assessment = DetailPageInterpreter(definition).interpret(signals)

        self.assertEqual(signals.heading, "Balboni, William")
        self.assertIn("Dati anagrafici", signals.body_text)
        self.assertIn("Formazione: 36 Bianconcini Garibaldi", signals.body_text)
        self.assertNotIn("Area riservata", signals.body_text)
        self.assertNotIn("Privacy Overview", signals.body_text)
        self.assertEqual(assessment.assessment, "claim_candidates_extracted")
        self.assertEqual(assessment.extracted_fields["given_name"], "William")
        self.assertEqual(assessment.extracted_fields["family_name"], "Balboni")
        self.assertEqual(assessment.extracted_fields["formation_name"], "36 Bianconcini Garibaldi, dal 1944 giu. 15 al 1944 ott. 11")
        images = json.loads(signals.metadata["partigiani_italia_image_urls_json"])
        self.assertEqual(images[0]["url"], "https://partigianiditalia.cultura.gov.it/wp-content/uploads/schede/balboni-william.jpg")
        self.assertEqual(signals.metadata["content_cleaning"], "partigiani_italia_detail_v1")

    def test_partigiani_italia_real_table_layout_extracts_fields_and_images(self) -> None:
        definition = load_source_detail_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_detail_logic" / "partigiani_italia.yaml"
        )

        signals = extract_detail_page_signals(
            source_id="partigiani_italia",
            engine=definition.engine,
            html_text="""
            <html>
              <body>
                <section>
                  <div class="four columns">
                    <img src="https://partigianiditalia.cultura.gov.it/partigiani-rest-api/v1.4/media/ER016_1266_0001.jpg?key=abc&amp;ip=127.0.0.1">
                    <img src="https://partigianiditalia.cultura.gov.it/partigiani-rest-api/v1.4/media/ER016_1266_0002.jpg?key=abc&amp;ip=127.0.0.1">
                  </div>
                  <div class="eight columns">
                    <h3 class="slim-t-big">Balboni, William</h3>
                    <table class="slim-table-xl">
                      <tr><td colspan="2"><strong>Dati anagrafici</strong></td></tr>
                      <tr><td><strong>Nome:</strong></td><td>William</td></tr>
                      <tr><td><strong>Cognome:</strong></td><td>Balboni</td></tr>
                      <tr><td><strong>Genere:</strong></td><td>M</td></tr>
                      <tr><td><strong>Nato il:</strong></td><td>1922 mag. 9</td></tr>
                      <tr><td><strong>A:</strong></td><td>Codrea</td></tr>
                      <tr><td><strong>Comune:</strong></td><td>Ferrara</td></tr>
                      <tr><td><strong>Provincia:</strong></td><td>Ferrara</td></tr>
                      <tr><td><strong>Nazione:</strong></td><td>Italia</td></tr>
                    </table>
                    <table class="slim-table-xl">
                      <tr><td colspan="2"><strong>Attivita partigiana</strong></td></tr>
                      <tr><td><strong>Formazione:</strong></td><td>36 Bianconcini Garibaldi, dal 1944 giu. 15 al 1944 ott. 11</td></tr>
                      <tr><td><strong>Qualifica riconosciuta:</strong></td><td>Caduto</td></tr>
                    </table>
                    <table class="slim-table-xl">
                      <tr><td><strong>Commissioni:</strong></td><td>Commissione regionale Emilia Romagna</td></tr>
                      <tr><td><strong>Schedari:</strong></td><td>Emilia Romagna</td></tr>
                    </table>
                  </div>
                </section>
                <footer>Privacy Overview</footer>
              </body>
            </html>
            """,
            detail_logic=definition,
            result_url="https://partigianiditalia.cultura.gov.it/persona/?id=abc",
        )
        assessment = DetailPageInterpreter(definition).interpret(signals)
        images = json.loads(signals.metadata["partigiani_italia_image_urls_json"])

        self.assertEqual(signals.heading, "Balboni, William")
        self.assertEqual(assessment.assessment, "claim_candidates_extracted")
        self.assertEqual(assessment.extracted_fields["family_name"], "Balboni")
        self.assertEqual(assessment.extracted_fields["gender"], "M")
        self.assertEqual(assessment.extracted_fields["birth_place"], "Codrea")
        self.assertEqual(assessment.extracted_fields["recognition_status"], "Caduto")
        self.assertEqual(len(images), 2)

    def test_storia_memoria_bo_detail_can_extract_claim_candidates(self) -> None:
        definition = load_source_detail_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_detail_logic" / "storia_memoria_bo.yaml"
        )
        interpreter = DetailPageInterpreter(definition)

        signals = extract_detail_page_signals(
            source_id="storia_memoria_bo",
            engine=definition.engine,
            html_text="""
            <html>
              <body>
                <main>
                  <h1>Bassi Giancarlo</h1>
                  <p>Partigiano caduto a Imola il 18 ottobre 1944.</p>
                </main>
              </body>
            </html>
            """,
            detail_logic=definition,
            result_url="https://www.storiaememoriadibologna.it/archivio/persone/bassi-giancarlo",
        )
        assessment = interpreter.interpret(signals)

        self.assertEqual(assessment.assessment, "claim_candidates_extracted")
        self.assertEqual(assessment.extracted_fields["person_name"], "Bassi Giancarlo")
        self.assertEqual(assessment.extracted_fields["death_date"], "18 ottobre 1944")
        self.assertEqual(assessment.extracted_fields["death_place"], "Imola")

    def test_storia_memoria_bo_andreoli_detail_extracts_extended_candidate_fields(self) -> None:
        definition = load_source_detail_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_detail_logic" / "storia_memoria_bo.yaml"
        )
        interpreter = DetailPageInterpreter(definition)

        signals = extract_detail_page_signals(
            source_id="storia_memoria_bo",
            engine=definition.engine,
            html_text="""
            <html>
              <body>
                <main>
                  <h1>Dino Andreoli</h1>
                  <section>
                    <h2>Note sintetiche</h2>
                    <p>Titolo studio : Licenza elementare Causa morte : In combattimento Occupazione : Calzolaio</p>
                  </section>
                  <section>
                    <h2>Scheda</h2>
                    <p>Dino Andreoli, da Domenico e Adalgisa Torreggiani; nato il 17 maggio 1920 a San Lazzaro di Savena; ivi residente nel 1943.</p>
                    <p>PrestÃ² servizio militare in Sicilia.</p>
                    <p>MilitÃ² nella 36a brigata Bianconcini Garibaldi e operÃ² a Monte Battaglia (Casola Valsenio - RA). Cadde in combattimento a Santa Maria di Purocielo (Brisighella - RA) il 13 ottobre 1944.</p>
                    <p>Riconosciuto partigiano dal 17 giugno 1944 al 13 ottobre 1944.</p>
                    <p>E' ricordato nel Sacrario di Piazza Nettuno.</p>
                    <p>Ha fatto parte di Tutti # 36a Brigata Garibaldi Bianconcini Partigiana/o Opere Sacrario partigiani in Piazza Nettuno a Bologna</p>
                    <p>Bibliografia Gli antifascisti, i partigiani e le vittime del fascismo nel bolognese (1919- 1945) Albertazzi A., Arbizzani L., Onofri N.S.</p>
                  </section>
                </main>
              </body>
            </html>
            """,
            detail_logic=definition,
            result_url="https://www.storiaememoriadibologna.it/archivio/persone/andreoli-dino",
        )
        assessment = interpreter.interpret(signals)

        self.assertEqual(assessment.assessment, "claim_candidates_extracted")
        self.assertEqual(assessment.extracted_fields["military_service_place"], "Sicilia")
        self.assertEqual(assessment.extracted_fields["partisan_activity_place"], "Monte Battaglia (Casola Valsenio - RA)")
        self.assertEqual(assessment.extracted_fields["role_status"], "Partigiana/o")
        self.assertIn("Gli antifascisti", assessment.extracted_fields["bibliography"])

    def test_tna_wo417_detail_can_extract_claim_candidates(self) -> None:
        definition = load_source_detail_logic(
            Path(__file__).resolve().parents[2] / "memoria-sources" / "source_detail_logic" / "tna_wo417.yaml"
        )
        interpreter = DetailPageInterpreter(definition)

        signals = extract_detail_page_signals(
            source_id="tna_wo417",
            engine=definition.engine,
            html_text="""
            <html>
              <body>
                <h1>WO 417 Italian Partisan Record</h1>
                <div>Reference: WO 417/92/123</div>
                <div>Date: 1944-1945</div>
                <div>Name(s): Andreoli Dino</div>
                <div>Description: Notification regarding Andreoli Dino in Italian partisan service.</div>
                <div>Held by: The National Archives</div>
              </body>
            </html>
            """,
            detail_logic=definition,
            result_url="https://discovery.nationalarchives.gov.uk/details/r/example",
        )
        assessment = interpreter.interpret(signals)

        self.assertEqual(assessment.assessment, "claim_candidates_extracted")
        self.assertEqual(assessment.extracted_fields["archival_reference"], "WO 417/92/123")
        self.assertEqual(assessment.extracted_fields["covering_dates"], "1944-1945")
        self.assertEqual(assessment.extracted_fields["person_name"], "Andreoli Dino")
