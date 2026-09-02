from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.base import run_source
from caduti_fonti_report.connectors.cwgc import _build_cwgc_search_url
from caduti_fonti_report.connectors.obd_memorial import (
    _build_obd_memorial_search_attempts,
    transliterate_latin_to_russian,
)
from caduti_fonti_report.connectors.pamyat_naroda import _build_pamyat_search_url
from caduti_fonti_report.connectors.storia_memoria_bo import (
    _build_storia_memoria_search_attempts,
    _first_visible_locator,
)
from caduti_fonti_report.models import Caduto, SearchHit, Source
from caduti_fonti_report.queries import default_query


class FakeStoriaMemoriaLocator:
    def __init__(self, page, selector: str):
        self.page = page
        self.selector = selector

    def count(self) -> int:
        if self.selector == "#views-exposed-form-persone-block-2":
            return 1
        if self.selector == 'a[href*="/ricerca-avanzata/persone"]':
            return 0
        return 1

    @property
    def first(self):
        return self

    def locator(self, selector: str):
        return FakeStoriaMemoriaLocator(self.page, f"{self.selector} >> {selector}")

    def click(self) -> None:
        if self.selector.endswith("#edit-submit-persone"):
            self.page.submit()

    def fill(self, value: str) -> None:
        self.page.fields[self.selector] = value


class VisibleLocator:
    def __init__(self, visible: list[bool]):
        self.items = [VisibleLocatorItem(value) for value in visible]

    def count(self) -> int:
        return len(self.items)

    def nth(self, index: int):
        return self.items[index]

    @property
    def first(self):
        return self.items[0]


class VisibleLocatorItem:
    def __init__(self, visible: bool):
        self.visible = visible

    def is_visible(self) -> bool:
        return self.visible


class FakeStoriaMemoriaPage:
    def __init__(self, responses: list[dict[str, str]], detail_pages: dict[str, str] | None = None):
        self.responses = responses
        self.detail_pages = detail_pages or {}
        self.fields: dict[str, str] = {}
        self.url = "about:blank"
        self.submit_index = 0
        self.current_html = "<html></html>"

    def goto(self, url: str, wait_until: str | None = None, timeout: int | None = None) -> None:
        self.url = url
        if url in self.detail_pages:
            self.current_html = self.detail_pages[url]

    def wait_for_load_state(self, state: str, timeout: int | None = None) -> None:
        return None

    def locator(self, selector: str) -> FakeStoriaMemoriaLocator:
        return FakeStoriaMemoriaLocator(self, selector)

    def content(self) -> str:
        return self.current_html

    def submit(self) -> None:
        response = self.responses[self.submit_index]
        self.submit_index += 1
        self.url = response["url"]
        self.current_html = response["html"]


class FakeStoriaMemoriaContext:
    def __init__(self, page: FakeStoriaMemoriaPage):
        self.page = page

    def new_page(self) -> FakeStoriaMemoriaPage:
        return self.page

    def close(self) -> None:
        return None


class FakeStoriaMemoriaBrowser:
    def __init__(self, page: FakeStoriaMemoriaPage):
        self.page = page

    def new_context(self, **kwargs):
        return FakeStoriaMemoriaContext(self.page)

    def close(self) -> None:
        return None


class FakeStoriaMemoriaPlaywright:
    def __init__(self, page: FakeStoriaMemoriaPage):
        self.chromium = self
        self.page = page

    def launch(self, **kwargs):
        return FakeStoriaMemoriaBrowser(self.page)


class FakeStoriaMemoriaPlaywrightFactory:
    def __init__(self, responses: list[dict[str, str]], detail_pages: dict[str, str] | None = None):
        self.page = FakeStoriaMemoriaPage(responses, detail_pages=detail_pages)

    def __call__(self):
        return self

    def __enter__(self):
        return FakeStoriaMemoriaPlaywright(self.page)

    def __exit__(self, exc_type, exc, tb):
        return False


class ConnectorTests(unittest.TestCase):
    def test_storia_memoria_bo_uses_first_visible_form_match(self) -> None:
        locator = VisibleLocator([False, True])

        selected = _first_visible_locator(locator)

        self.assertIs(selected, locator.nth(1))

    def test_credentialed_source_without_credentials_returns_needs_credentials(self) -> None:
        caduto = Caduto(
            intestazione_pdf="TEST PERSON",
            nome="Mario Rossi",
            origine_sulla_lapide="Italia",
            nascita="1900",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="tna_wo417",
            source_name="TNA Discovery - WO 417",
            kind="credentialed",
            build_query=default_query,
            search_url_builder=lambda query: "https://discovery.nationalarchives.gov.uk/",
            credentials={"email": "", "password": ""},
            auth={"reference_code": "WO 417"},
            note="Richiede account Discovery del National Archives.",
        )

        result = run_source(source, caduto)

        self.assertEqual(result.status, "needs_credentials")
        self.assertIn("email", result.note)
        self.assertIn("password", result.note)

    def test_search_url_only_source_returns_ready_without_credentials(self) -> None:
        caduto = Caduto(
            intestazione_pdf="TEST PERSON",
            nome="Mario Rossi",
            origine_sulla_lapide="Italia",
            nascita="1900",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="icrc_pow",
            source_name="ICRC Archives - ricerca POW/captured personnel",
            kind="search_url_only",
            build_query=default_query,
            search_url_builder=lambda query: "https://archives.icrc.org/search/advanced",
            note="Accesso anonimo alla ricerca avanzata ICRC.",
        )

        result = run_source(source, caduto)

        self.assertEqual(result.status, "search_url_ready")
        self.assertEqual(result.query, "Mario Rossi")
        self.assertEqual(result.search_url, "https://archives.icrc.org/search/advanced")

    def test_search_form_post_source_returns_hits_after_submit(self) -> None:
        caduto = Caduto(
            intestazione_pdf="TEST PERSON",
            nome="Mario Rossi",
            origine_sulla_lapide="Italia",
            nascita="1900",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="icrc_pow",
            source_name="ICRC Archives - ricerca POW/captured personnel",
            kind="search_form_post",
            build_query=default_query,
            search_url_builder=lambda query: "https://archives.icrc.org/search/advanced",
            form={
                "method": "post",
                "action": "https://archives.icrc.org/search/advanced",
                "query_field": "Fields[0].Value",
                "query_label": "Word(s) from the title / content",
                "SourceName": "archive",
                "Fields[0].FieldName": "Field_TitleArchive",
            },
            note="Accesso anonimo alla ricerca avanzata ICRC.",
        )

        html = """
<html>
  <head><title>Search results</title></head>
  <body>
    <a href="/Details/archive/110000001">Mario Rossi prisoner card</a>
  </body>
</html>
"""
        with patch(
            "caduti_fonti_report.connectors.http_sources.post_form_with_opener",
            return_value=("https://archives.icrc.org/search/results", html),
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.query, "Mario Rossi")
        self.assertEqual(result.search_url, "https://archives.icrc.org/search/results")
        self.assertEqual(len(result.hits), 1)
        self.assertIn("Search results", result.note)

    def test_search_form_post_source_returns_error_when_submit_fails(self) -> None:
        caduto = Caduto(
            intestazione_pdf="TEST PERSON",
            nome="Mario Rossi",
            origine_sulla_lapide="Italia",
            nascita="1900",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="icrc_pow",
            source_name="ICRC Archives - ricerca POW/captured personnel",
            kind="search_form_post",
            build_query=default_query,
            search_url_builder=lambda query: "https://archives.icrc.org/search/advanced",
            form={
                "method": "post",
                "action": "https://archives.icrc.org/search/advanced",
                "query_field": "Fields[0].Value",
                "query_label": "Word(s) from the title / content",
                "SourceName": "archive",
                "Fields[0].FieldName": "Field_TitleArchive",
            },
            note="Accesso anonimo alla ricerca avanzata ICRC.",
        )

        with patch(
            "caduti_fonti_report.connectors.http_sources.post_form_with_opener",
            side_effect=ValueError("form unavailable"),
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "error")
        self.assertIn("form POST", result.note)
        self.assertIn("Fields[0].Value", result.note)

    def test_search_form_aspnet_source_fetches_hidden_fields_and_returns_hits(self) -> None:
        caduto = Caduto(
            intestazione_pdf="TEST PERSON",
            nome="Mario Rossi",
            origine_sulla_lapide="Italia",
            nascita="1900",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="oesta_kriegsarchiv",
            source_name="OeStA Kriegsarchiv",
            kind="search_form_aspnet",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.archivinformationssystem.at/volltextsuche.aspx",
            form={
                "method": "post",
                "action": "https://www.archivinformationssystem.at/volltextsuche.aspx",
                "query_field": "ctl00$cphMainArea$txtMitAllenWoertern",
                "query_label": "With all words",
                "ctl00$cphMainArea$cmdSuchen": "Search",
                "dynamic_hidden_fields": "__VIEWSTATE,__EVENTVALIDATION",
            },
            note="Ricerca full-text anonima nel catalogo OeStA via form ASP.NET.",
        )
        initial_html = """
<html><body>
<input type="hidden" name="__VIEWSTATE" value="viewstate-token" />
<input type="hidden" name="__EVENTVALIDATION" value="eventvalidation-token" />
</body></html>
"""
        result_html = """
<html>
  <head><title>Result list</title></head>
  <body>
    <a href="/detail.aspx?ID=300169">Mario Rossi Standestabellen</a>
  </body>
</html>
"""

        with patch(
            "caduti_fonti_report.connectors.http_sources.fetch_text_with_opener",
            return_value=initial_html,
        ), patch(
            "caduti_fonti_report.connectors.http_sources.post_form_with_opener",
            return_value=("https://www.archivinformationssystem.at/resultatliste.aspx", result_html),
        ) as mocked_post:
            result = run_source(source, caduto)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.search_url, "https://www.archivinformationssystem.at/resultatliste.aspx")
        self.assertEqual(len(result.hits), 1)
        posted_data = mocked_post.call_args.args[2]
        self.assertEqual(posted_data["__VIEWSTATE"], "viewstate-token")
        self.assertEqual(posted_data["__EVENTVALIDATION"], "eventvalidation-token")
        self.assertEqual(posted_data["ctl00$cphMainArea$txtMitAllenWoertern"], "Mario Rossi")

    def test_search_form_aspnet_source_returns_error_when_initial_fetch_fails(self) -> None:
        caduto = Caduto(
            intestazione_pdf="TEST PERSON",
            nome="Mario Rossi",
            origine_sulla_lapide="Italia",
            nascita="1900",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="oesta_kriegsarchiv",
            source_name="OeStA Kriegsarchiv",
            kind="search_form_aspnet",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.archivinformationssystem.at/volltextsuche.aspx",
            form={
                "method": "post",
                "action": "https://www.archivinformationssystem.at/volltextsuche.aspx",
                "query_field": "ctl00$cphMainArea$txtMitAllenWoertern",
                "query_label": "With all words",
            },
            note="Ricerca full-text anonima nel catalogo OeStA via form ASP.NET.",
        )

        with patch(
            "caduti_fonti_report.connectors.http_sources.fetch_text_with_opener",
            side_effect=ValueError("page unavailable"),
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "error")
        self.assertIn("ASP.NET", result.note)

    def test_search_form_get_name_source_builds_public_search_url(self) -> None:
        caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="U.R.S.S.",
            nascita="1920",
            morte="1944",
            ruolo_affiliazione="partigiano sovietico",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="partigiani_italia",
            source_name="I Partigiani d'Italia - ricerca pubblica",
            kind="search_form_get_name",
            build_query=default_query,
            search_url_builder=lambda query: "https://partigianiditalia.cultura.gov.it/cerca/",
            form={
                "name_order": "surname_first",
                "name_field": "nome",
                "surname_field": "cognome",
                "nome_op": "contains",
                "cognome_op": "contains",
                "cmd": "CERCA",
                "solr": "1",
                "lm": "20",
            },
            note="Ricerca pubblica via form GET su /cerca/.",
        )

        with patch(
            "caduti_fonti_report.connectors.http_sources.parse_search_page",
            return_value=(
                "Cerca",
                [SearchHit(title="Andreoli Dino", url="https://partigianiditalia.cultura.gov.it/persona/?id=123")],
            ),
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "ok")
        self.assertIn("nome=Dino", result.search_url)
        self.assertIn("cognome=Andreoli", result.search_url)
        self.assertIn("nome_op=contains", result.search_url)
        self.assertEqual(len(result.hits), 1)

    def test_obd_memorial_transliterates_latin_name_tokens_to_cyrillic(self) -> None:
        self.assertEqual(transliterate_latin_to_russian("Panov"), "Панов")
        self.assertEqual(transliterate_latin_to_russian("Sadavich"), "Садавич")

    def test_obd_memorial_source_builds_cyrillic_search_attempts(self) -> None:
        caduto = Caduto(
            intestazione_pdf="PANOV SERGIO",
            nome="Panov Sergio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano sovietico della 36a Brigata",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="obd_memorial",
            source_name="OBD-Memorial",
            kind="obd_memorial",
            build_query=default_query,
            search_url_builder=lambda query: "https://obd-memorial.ru/html/search.htm",
            form={"search_base_url": "https://obd-memorial.ru/html/search.htm"},
            note="Genera tentativi con cognome e nome in cirillico.",
        )

        attempts = _build_obd_memorial_search_attempts(source, caduto)
        with patch(
            "caduti_fonti_report.connectors.obd_memorial.fetch_text",
            return_value="<html><body><a href=\"/html/info.htm?id=1\">record</a></body></html>",
        ):
            result = run_source(source, caduto)

        self.assertEqual(attempts[0]["surname"], "Панов")
        self.assertEqual(attempts[0]["given_name"], "Сергей")
        self.assertEqual(result.status, "search_url_ready")
        self.assertIn("f=%D0%9F%D0%B0%D0%BD%D0%BE%D0%B2", result.search_url)
        self.assertIn("n=%D0%A1%D0%B5%D1%80%D0%B3%D0%B5%D0%B9", result.search_url)
        self.assertGreaterEqual(len(result.hits), 3)
        self.assertIn('f="Панов"', result.query)

    def test_obd_memorial_source_handles_italianized_mononym(self) -> None:
        caduto = Caduto(
            intestazione_pdf="GIORGIO",
            nome="Giorgio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano sovietico della 36a Brigata",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="obd_memorial",
            source_name="OBD-Memorial",
            kind="obd_memorial",
            build_query=default_query,
            search_url_builder=lambda query: "https://obd-memorial.ru/html/search.htm",
            form={"search_base_url": "https://obd-memorial.ru/html/search.htm"},
            note="Genera tentativi con cognome e nome in cirillico.",
        )

        with patch(
            "caduti_fonti_report.connectors.obd_memorial.fetch_text",
            return_value="<html><body><a href=\"/html/info.htm?id=1\">record</a></body></html>",
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "search_url_ready")
        self.assertIn("Георгий", result.query)
        self.assertTrue(any("n=%D0%93%D0%B5%D0%BE%D1%80%D0%B3%D0%B8%D0%B9" in hit.url for hit in result.hits))

    def test_obd_memorial_source_hides_standard_no_results_pages(self) -> None:
        caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="U.R.S.S.",
            nascita="1920",
            morte="1944",
            ruolo_affiliazione="partigiano sovietico",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="obd_memorial",
            source_name="OBD-Memorial",
            kind="obd_memorial",
            build_query=default_query,
            search_url_builder=lambda query: "https://obd-memorial.ru/html/search.htm",
            form={"search_base_url": "https://obd-memorial.ru/html/search.htm"},
            note="Genera tentativi con cognome e nome in cirillico.",
        )
        no_results_html = (
            "<html><body>"
            "\u041a \u0441\u043e\u0436\u0430\u043b\u0435\u043d\u0438\u044e, "
            "\u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e "
            "\u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432 "
            "\u043f\u043e \u0412\u0430\u0448\u0435\u043c\u0443 "
            "\u0437\u0430\u043f\u0440\u043e\u0441\u0443."
            "</body></html>"
        )

        with patch(
            "caduti_fonti_report.connectors.obd_memorial.fetch_text",
            return_value=no_results_html,
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "no_results")
        self.assertEqual(result.search_url, "")
        self.assertEqual(result.hits, [])
        self.assertIn("non vengono mostrate come hit", result.note)

    def test_obd_memorial_source_skips_non_soviet_caduti_without_fetching(self) -> None:
        caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="Italia",
            nascita="1920",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="obd_memorial",
            source_name="OBD-Memorial",
            kind="obd_memorial",
            build_query=default_query,
            search_url_builder=lambda query: "https://obd-memorial.ru/html/search.htm",
            form={"search_base_url": "https://obd-memorial.ru/html/search.htm"},
            note="Genera tentativi con cognome e nome in cirillico.",
        )

        with patch("caduti_fonti_report.connectors.obd_memorial.fetch_text") as mocked_fetch:
            result = run_source(source, caduto)

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.search_url, "")
        mocked_fetch.assert_not_called()

    def test_obd_memorial_source_limits_checked_attempts(self) -> None:
        caduto = Caduto(
            intestazione_pdf="PANOV SERGIO",
            nome="Panov Sergio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano sovietico della 36a Brigata",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="obd_memorial",
            source_name="OBD-Memorial",
            kind="obd_memorial",
            build_query=default_query,
            search_url_builder=lambda query: "https://obd-memorial.ru/html/search.htm",
            form={"search_base_url": "https://obd-memorial.ru/html/search.htm", "max_attempts": "2"},
            note="Genera tentativi con cognome e nome in cirillico.",
        )

        with patch(
            "caduti_fonti_report.connectors.obd_memorial.fetch_text",
            return_value="<html><body><a href=\"/html/info.htm?id=1\">record</a></body></html>",
        ) as mocked_fetch:
            result = run_source(source, caduto)

        self.assertEqual(result.status, "search_url_ready")
        self.assertEqual(mocked_fetch.call_count, 2)
        self.assertEqual(len(result.hits), 2)

    def test_pamyat_naroda_builds_advanced_search_url(self) -> None:
        url = _build_pamyat_search_url(
            "https://pamyat-naroda.ru/heroes/",
            surname="Панов",
            given_name="Сергей",
            year="1920",
        )

        self.assertIn("adv_search=y", url)
        self.assertIn("last_name=%D0%9F%D0%B0%D0%BD%D0%BE%D0%B2", url)
        self.assertIn("first_name=%D0%A1%D0%B5%D1%80%D0%B3%D0%B5%D0%B9", url)
        self.assertIn("date_birth=1920", url)
        self.assertIn("group=all", url)

    def test_pamyat_naroda_source_returns_cyrillic_search_links_for_soviet_caduto(self) -> None:
        caduto = Caduto(
            intestazione_pdf="PANOV SERGIO",
            nome="Panov Sergio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano sovietico della 36a Brigata",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="pamyat_naroda",
            source_name="Pamyat Naroda",
            kind="pamyat_naroda",
            build_query=default_query,
            search_url_builder=lambda query: "https://pamyat-naroda.ru/heroes/",
            form={"search_base_url": "https://pamyat-naroda.ru/heroes/", "max_attempts": "2"},
            note="Genera URL di ricerca avanzata.",
        )

        result = run_source(source, caduto)

        self.assertEqual(result.status, "search_url_ready")
        self.assertEqual(len(result.hits), 2)
        self.assertIn("last_name=%D0%9F%D0%B0%D0%BD%D0%BE%D0%B2", result.search_url)
        self.assertIn("first_name=%D0%A1%D0%B5%D1%80%D0%B3%D0%B5%D0%B9", result.search_url)
        self.assertIn('f="Панов"', result.query)

    def test_pamyat_naroda_source_skips_non_soviet_caduti(self) -> None:
        caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="Italia",
            nascita="1920",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="pamyat_naroda",
            source_name="Pamyat Naroda",
            kind="pamyat_naroda",
            build_query=default_query,
            search_url_builder=lambda query: "https://pamyat-naroda.ru/heroes/",
            form={"search_base_url": "https://pamyat-naroda.ru/heroes/"},
            note="Genera URL di ricerca avanzata.",
        )

        result = run_source(source, caduto)

        self.assertEqual(result.status, "skipped")
        self.assertEqual(result.search_url, "")
        self.assertEqual(result.hits, [])

    def test_cwgc_builds_find_war_dead_search_url(self) -> None:
        url = _build_cwgc_search_url(
            "https://www.cwgc.org/find-records/find-war-dead/search-results/",
            surname="Panov",
            forename="Sergio",
            war_select="2",
        )

        self.assertIn("/find-records/find-war-dead/search-results/", url)
        self.assertIn("Surname=Panov", url)
        self.assertIn("Forename=Sergio", url)
        self.assertIn("WarSelect=2", url)
        self.assertIn("CountryCommemoratedIn=null", url)

    def test_cwgc_source_returns_find_war_dead_links(self) -> None:
        caduto = Caduto(
            intestazione_pdf="PANOV SERGIO",
            nome="Panov Sergio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano sovietico",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="cwgc",
            source_name="CWGC",
            kind="cwgc",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.cwgc.org/find-records/find-war-dead/",
            form={
                "results_base_url": "https://www.cwgc.org/find-records/find-war-dead/search-results/",
                "name_order": "surname_first",
                "war_select": "2",
                "max_attempts": "2",
            },
            note="Ricerca pubblica Find War Dead.",
        )

        result = run_source(source, caduto)

        self.assertEqual(result.status, "search_url_ready")
        self.assertEqual(len(result.hits), 2)
        self.assertIn("Surname=Panov", result.search_url)
        self.assertIn("Forename=Sergio", result.search_url)
        self.assertIn('Surname="Panov"', result.query)

    def test_cwgc_source_handles_mononym(self) -> None:
        caduto = Caduto(
            intestazione_pdf="GIORGIO",
            nome="Giorgio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano sovietico",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="cwgc",
            source_name="CWGC",
            kind="cwgc",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.cwgc.org/find-records/find-war-dead/",
            form={
                "results_base_url": "https://www.cwgc.org/find-records/find-war-dead/search-results/",
                "name_order": "surname_first",
                "war_select": "2",
            },
            note="Ricerca pubblica Find War Dead.",
        )

        result = run_source(source, caduto)

        self.assertEqual(result.status, "search_url_ready")
        self.assertEqual(len(result.hits), 2)
        self.assertIn("Surname=Giorgio", result.hits[0].url)
        self.assertIn("Forename=Giorgio", result.hits[1].url)

    def test_storia_memoria_bo_source_builds_name_birth_and_death_attempts(self) -> None:
        caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="Italia",
            nascita="17 maggio 1920, San Lazzaro di Savena",
            morte="11 ottobre 1944, battaglia di Purocielo/Ca Marcone",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="storia_memoria_bo",
            source_name="Storia e Memoria di Bologna",
            kind="storia_memoria_bo",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.storiaememoriadibologna.it/ricerca-avanzata",
            form={"name_order": "surname_first"},
            note="Ricerca avanzata Persone via Playwright.",
        )
        attempts = _build_storia_memoria_search_attempts(source, caduto)

        self.assertEqual(len(attempts), 3)
        self.assertEqual(attempts[0]["nom"], "Dino")
        self.assertEqual(attempts[0]["cog"], "Andreoli")
        self.assertEqual(attempts[1]["nas_min"], "1920-05-17")
        self.assertEqual(attempts[1]["nas_max"], "1920-05-17")
        self.assertEqual(attempts[2]["mor_min"], "1944-10-11")
        self.assertEqual(attempts[2]["mor_max"], "1944-10-11")

    def test_storia_memoria_bo_source_returns_hit_from_people_results(self) -> None:
        caduto = Caduto(
            intestazione_pdf="BASSI GIANCARLO",
            nome="Bassi Giancarlo",
            origine_sulla_lapide="Italia",
            nascita="1921",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="storia_memoria_bo",
            source_name="Storia e Memoria di Bologna",
            kind="storia_memoria_bo",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.storiaememoriadibologna.it/ricerca-avanzata",
            form={"name_order": "surname_first"},
            auth={
                "advanced_search_url": "https://www.storiaememoriadibologna.it/ricerca-avanzata",
                "form_selector": "#views-exposed-form-persone-block-2",
                "submit_selector": "#edit-submit-persone",
            },
            note="Ricerca avanzata Persone via Playwright.",
        )
        html = """
<html>
  <body>
    <div class="mini-card position-relative">
      <div class="testo"><h3 class="h6"><span>Bassi Giancarlo</span></h3>Imola, 18 ottobre 1944</div>
      <a href="/archivio/persone/bassi-giancarlo" class="link-assoluto" title="Bassi Giancarlo"></a>
    </div>
  </body>
</html>
"""
        detail_html = """
<html>
  <body>
    <main>
      <h1>Bassi Giancarlo</h1>
      <p>Partigiano caduto a Imola il 18 ottobre 1944.</p>
      <p>La scheda ricostruisce in sintesi la vicenda biografica e il contesto della morte.</p>
    </main>
  </body>
</html>
"""
        factory = FakeStoriaMemoriaPlaywrightFactory(
            [
                {
                    "url": "https://www.storiaememoriadibologna.it/ricerca-avanzata/persone?nom=giancarlo&cog=bassi",
                    "html": html,
                }
            ],
            detail_pages={
                "https://www.storiaememoriadibologna.it/archivio/persone/bassi-giancarlo": detail_html,
            },
        )

        with patch(
            "caduti_fonti_report.connectors.storia_memoria_bo._get_playwright_factory",
            return_value=factory,
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.hits[0].title, "Bassi Giancarlo")
        self.assertIn("/archivio/persone/bassi-giancarlo", result.hits[0].url)
        self.assertIn("Imola", result.hits[0].snippet)
        self.assertIn("Partigiano caduto a Imola", result.hits[0].content)

    def test_storia_memoria_bo_source_falls_back_to_birth_date_when_name_only_is_empty(self) -> None:
        caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="Italia",
            nascita="17 maggio 1920, San Lazzaro di Savena",
            morte="11 ottobre 1944, battaglia di Purocielo/Ca Marcone",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="storia_memoria_bo",
            source_name="Storia e Memoria di Bologna",
            kind="storia_memoria_bo",
            build_query=default_query,
            search_url_builder=lambda query: "https://www.storiaememoriadibologna.it/ricerca-avanzata",
            form={"name_order": "surname_first"},
            auth={
                "advanced_search_url": "https://www.storiaememoriadibologna.it/ricerca-avanzata",
                "form_selector": "#views-exposed-form-persone-block-2",
                "submit_selector": "#edit-submit-persone",
            },
            note="Ricerca avanzata Persone via Playwright.",
        )
        empty_html = """
<html>
  <body>
    <p>Nessun risultato trovato.</p>
  </body>
</html>
"""
        hit_html = """
<html>
  <body>
    <div class="mini-card position-relative">
      <div class="testo"><h3 class="h6"><span>Andreoli Dino</span></h3>Brisighella, Ca di Costino in localita Santa Maria in Purocielo (RA), 13 Ottobre 1944</div>
      <a href="/archivio/persone/andreoli-dino" class="link-assoluto" title="Andreoli Dino"></a>
    </div>
</body>
</html>
"""
        factory = FakeStoriaMemoriaPlaywrightFactory(
            [
                {
                    "url": "https://www.storiaememoriadibologna.it/ricerca-avanzata/persone?nom=dino&cog=andreoli",
                    "html": empty_html,
                },
                {
                    "url": "https://www.storiaememoriadibologna.it/ricerca-avanzata/persone?nom=dino&cog=andreoli&nas%5Bmin%5D=1920-05-17&nas%5Bmax%5D=1920-05-17",
                    "html": hit_html,
                },
            ]
        )

        with patch(
            "caduti_fonti_report.connectors.storia_memoria_bo._get_playwright_factory",
            return_value=factory,
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.hits), 1)
        self.assertIn('nascita="1920-05-17"', result.note)
        self.assertIn("nas%5Bmin%5D=1920-05-17", result.search_url)

    def test_local_excel_source_returns_matching_row(self) -> None:
        caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="Italia",
            nascita="1920",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="storia_memoria_bo_excel",
            source_name="Storia e Memoria Bologna/Emilia-Romagna (Excel locali)",
            kind="local_excel",
            build_query=default_query,
            search_url_builder=lambda query: "file:///D:/xampp/htdocs/ca-di-malanca/archivi/storia.sba.unibo.it/",
            local={
                "workbook_dir": "archivi/storia.sba.unibo.it",
                "workbook_glob": "*.xls",
                "sheet_name": "Foglio1",
                "name_order": "surname_first",
                "surname_column": "Cognome",
                "given_name_column": "Nome",
                "alias_columns": "Nome battaglia",
                "snippet_columns": "Brigata di appartenenza,Varie",
            },
            note="Ricerca locale nel file Excel esportato.",
        )

        with patch(
            "caduti_fonti_report.connectors.local_excel.load_excel_rows",
            return_value=[
                (
                    Path("archivi/storia.sba.unibo.it/Bologna.xls"),
                    "Foglio1",
                    [
                        {
                            "__row_number__": "42",
                            "Cognome": "Andreoli",
                            "Nome": "Dino",
                            "Nome battaglia": "",
                            "Brigata di appartenenza": "36a Brigata Garibaldi",
                            "Varie": "Caduto",
                        }
                    ],
                )
            ],
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.hits), 1)
        self.assertIn("Bologna.xls", result.hits[0].snippet)
        self.assertIn("Riga Excel: 42", result.hits[0].snippet)
        self.assertIn("36a Brigata Garibaldi", result.hits[0].snippet)

    def test_local_excel_source_returns_error_when_workbook_is_missing(self) -> None:
        caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="Italia",
            nascita="1920",
            morte="1944",
            ruolo_affiliazione="partigiano",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )
        source = Source(
            source_id="storia_memoria_bo_excel",
            source_name="Storia e Memoria Bologna/Emilia-Romagna (Excel locali)",
            kind="local_excel",
            build_query=default_query,
            search_url_builder=lambda query: "file:///D:/xampp/htdocs/ca-di-malanca/archivi/storia.sba.unibo.it/",
            local={"workbook_dir": "archivi/storia.sba.unibo.it", "workbook_glob": "*.xls"},
            note="Ricerca locale nel file Excel esportato.",
        )

        with patch(
            "caduti_fonti_report.connectors.local_excel.load_excel_rows",
            side_effect=FileNotFoundError("Workbook non trovato"),
        ):
            result = run_source(source, caduto)

        self.assertEqual(result.status, "error")
        self.assertIn("Excel locale", result.note)


if __name__ == "__main__":
    unittest.main()
