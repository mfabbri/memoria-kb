from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.tna import _build_tna_search_attempts
from caduti_fonti_report.models import Caduto, Source
from caduti_fonti_report.queries import default_query


class TnaSearchPlanTests(unittest.TestCase):
    def make_source(self, source_id: str = "tna_wo417", reference_code: str = "WO 417") -> Source:
        return Source(
            source_id=source_id,
            source_name="TNA test",
            kind="credentialed",
            build_query=default_query,
            search_url_builder=lambda query: f"https://example.test/?q={query}",
            credentials={"email": "user@example.test", "password": "secret"},
            auth={"reference_code": reference_code},
            note="",
            timeout=20,
        )

    def test_two_token_name_generates_original_and_reversed_attempts(self) -> None:
        caduto = Caduto(
            intestazione_pdf="PANOV SERGIO",
            nome="Panov Sergio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano sovietico della 36ª Brigata Garibaldi Bianconcini",
            fonti_richiamate="Fonte",
            profilo_biografico="Partigiano sovietico della 36ª Brigata Garibaldi.",
            episodio_documentato="Caduto durante la battaglia.",
        )

        attempts = _build_tna_search_attempts(self.make_source(), caduto)
        descriptions = [attempt["query_description"] for attempt in attempts]

        self.assertTrue(any('exact="Panov Sergio"' in item for item in descriptions))
        self.assertTrue(any('exact="Sergio Panov"' in item for item in descriptions))
        self.assertTrue(any('all_words="panov sergio"' in item for item in descriptions))
        self.assertTrue(any('all_words="sergio panov"' in item for item in descriptions))
        self.assertTrue(any('all_words="soviet union"' in item for item in descriptions))
        self.assertTrue(any('any_words="partisan, 36a, garibaldi"' in item for item in descriptions))

    def test_mononym_builds_only_mononym_attempts(self) -> None:
        caduto = Caduto(
            intestazione_pdf="GIORGIO",
            nome="Giorgio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano sovietico della 36ª Brigata",
            fonti_richiamate="Fonte",
            profilo_biografico="Partigiano sovietico della 36ª Brigata.",
            episodio_documentato="Nome italianizzato.",
        )

        attempts = _build_tna_search_attempts(self.make_source("tna_hs9", "HS 9"), caduto)
        descriptions = [attempt["query_description"] for attempt in attempts]

        self.assertTrue(any(item.startswith('mononym-context; ref="HS 9"') for item in descriptions))
        self.assertTrue(any('exact="Giorgio"' in item for item in descriptions))
        self.assertFalse(any("reversed" in item for item in descriptions))

    def test_years_are_included_when_biographical_fields_contain_them(self) -> None:
        caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="S. Lazzaro di Sav.",
            nascita="17 maggio 1920, San Lazzaro di Savena",
            morte="11 ottobre 1944, Purocielo",
            ruolo_affiliazione="partigiano della 36ª Brigata",
            fonti_richiamate="Fonte",
            profilo_biografico="Partigiano nato nel 1920 e caduto nel 1944.",
            episodio_documentato="Caduto l'11 ottobre 1944.",
        )

        attempts = _build_tna_search_attempts(self.make_source(), caduto)
        years = {(attempt["from_year"], attempt["to_year"]) for attempt in attempts}

        self.assertEqual(years, {("1944", "1944")})


if __name__ == "__main__":
    unittest.main()
