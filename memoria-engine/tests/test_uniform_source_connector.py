from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
import shutil
import uuid


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.connectors.http_get_form_executor import HttpGetFormSearchExecutor
from caduti_fonti_report.connectors.playwright_form_executor import PlaywrightFormSearchExecutor
from caduti_fonti_report.connectors.search_executor import SearchExecutionResult
from caduti_fonti_report.connectors.uniform_source_connector import UniformSourceConnector
from caduti_fonti_report.models import PersonQuery, SearchHit, Source, SourceResult
from caduti_fonti_report.queries import default_query
from caduti_fonti_report.source_definitions import load_source_definition


def make_source() -> Source:
    return Source(
        source_id="partigiani_italia",
        source_name="I Partigiani d'Italia - ricerca pubblica",
        kind="search_form_get_name",
        build_query=default_query,
        search_url_builder=lambda query: "https://partigianiditalia.cultura.gov.it/cerca/",
        form={"name_order": "surname_first"},
        note="Ricerca pubblica via form GET su `/cerca/`; le schede persona complete richiedono autenticazione.",
        timeout=8,
    )


def make_authenticated_partigiani_source() -> Source:
    return Source(
        source_id="partigiani_italia",
        source_name="I Partigiani d'Italia - ricerca pubblica",
        kind="search_form_get_name",
        build_query=default_query,
        search_url_builder=lambda query: "https://partigianiditalia.cultura.gov.it/cerca/",
        auth={
            "auth_mode": "manual_persistent_context",
            "profile_root": "secure/browser-profiles",
            "profile_id": "partigiani_italia_acs",
            "login_entry_url": "https://partigianiditalia.cultura.gov.it/login/",
            "auth_check_url": "https://partigianiditalia.cultura.gov.it/",
            "logged_in_text": "logout||esci||area riservata",
            "logged_out_text": "login||spid||cie",
            "logged_in_selector": 'a[href*="logout"]',
            "login_wait_seconds": "5",
            "headless": "false",
            "archival_cache_root": "archivi",
            "audit_log_path": "logs/partigiani_italia_authenticated_session.ndjson",
        },
        form={"name_order": "surname_first"},
        note="Ricerca pubblica via form GET su `/cerca/`; le schede persona complete richiedono autenticazione.",
        timeout=8,
    )


def result_list_html() -> str:
    return """
    <html>
      <head><title>Risultati ricerca</title></head>
      <body>
        <h1>Risultati ricerca</h1>
        <div class="results">
          <a href="/persona/?id=123">ANDREOLI DINO</a>
          <a href="/persona/?id=456">ANDREOLI DINO DETTO LUPO</a>
        </div>
      </body>
    </html>
    """


def result_list_html_with_login_link() -> str:
    return """
    <html>
      <head><title>Cerca</title></head>
      <body>
        <nav><a href="/login/">Login</a></nav>
        <h1>Cerca</h1>
        <div class="risultati-ricerca">
          <h3>Risultati trovati (2)</h3>
          <ul>
            <li>1 <a href="https://partigianiditalia.cultura.gov.it/persona/?id=5bf69e7e153c89309043fad9">Andreoli, Dino (S. Lazzaro di Savena, Bologna, 1920 mag. 17)</a></li>
            <li>2 <a href="https://partigianiditalia.cultura.gov.it/persona/?id=5bf6b32f153c89309045f1bf">Andreoli, Dino, commissione: Lombardia</a></li>
          </ul>
        </div>
      </body>
    </html>
    """


def no_results_html() -> str:
    return """
    <html>
      <head><title>Cerca</title></head>
      <body>
        <h1>Cerca</h1>
        <p>Nessun risultato</p>
      </body>
    </html>
    """


def blocked_search_html() -> str:
    return """
    <html>
      <body>
        <h1>Cerca</h1>
        <p>Accesso riservato. Esegui il login.</p>
      </body>
    </html>
    """


def partigiani_detail_login_html() -> str:
    return """
    <html>
      <body>
        <p>
          La consultazione dei dati è consentita esclusivamente agli utenti registrati che dispongono delle credenziali di accesso.
          Esegui il <a href="/login/">login</a>
        </p>
      </body>
    </html>
    """


def make_cwgc_source() -> Source:
    return Source(
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
        timeout=8,
    )


def cwgc_candidate_results_html(total: int = 2) -> str:
    return f"""
    <html><body>
      <h1>Your Search Results</h1>
      <h2>SHOW 2 OF {total} WAR DEAD</h2>
      <table>
        <tr>
          <td><strong>PETER PANOS</strong></td>
          <td><a href="/find-records/find-war-dead/casualty-details/123/peter-panos/">More details</a></td>
        </tr>
        <tr>
          <td><strong>PANO THABENG</strong></td>
          <td><a href="/find-records/find-war-dead/casualty-details/456/pano-thabeng/">More details</a></td>
        </tr>
      </table>
    </body></html>
    """


def make_storia_memoria_source() -> Source:
    return Source(
        source_id="storia_memoria_bo",
        source_name="Storia e Memoria di Bologna",
        kind="storia_memoria_bo",
        build_query=default_query,
        search_url_builder=lambda query: "https://www.storiaememoriadibologna.it/ricerca-avanzata",
        form={"name_order": "surname_first"},
        auth={
            "advanced_search_url": "https://www.storiaememoriadibologna.it/ricerca-avanzata",
            "form_selector": "#views-exposed-form-persone-block-2",
            "people_tab_selector": 'a[href*="/ricerca-avanzata/persone"]',
            "submit_selector": "#edit-submit-persone",
        },
        note="Ricerca avanzata Persone via Playwright.",
        timeout=8,
    )


def make_tna_source() -> Source:
    return Source(
        source_id="tna_wo417",
        source_name="TNA Discovery - WO 417",
        kind="credentialed",
        build_query=default_query,
        search_url_builder=lambda query: "https://discovery.nationalarchives.gov.uk/",
        credentials={"email": "user@example.test", "password": "secret"},
        auth={
            "advanced_search_url": "https://discovery.nationalarchives.gov.uk/advanced-search",
            "form_selector": "body",
            "submit_selector": "#search-submit",
        },
        note="Ricerca autenticata Discovery.",
        timeout=8,
    )


def make_fondazione_fossoli_source() -> Source:
    return Source(
        source_id="fondazione_fossoli",
        source_name="Fondazione Fossoli - I Nomi di Fossoli",
        kind="search_page",
        build_query=default_query,
        search_url_builder=lambda query: "https://www.fondazionefossoli.org/centro-studi/i-nomi-di-fossoli/",
        auth={
            "advanced_search_url": "https://www.fondazionefossoli.org/centro-studi/i-nomi-di-fossoli/",
            "form_selector": "body",
            "submit_selector": 'button:has-text("Cerca")',
            "field_selector_nome": 'input[placeholder="es: Mario"]',
            "field_selector_cognome": 'input[placeholder="es: Rossi"]',
            "field_selector_giorno_nascita": 'input[placeholder="gg"]',
            "field_selector_mese_nascita": 'input[placeholder="mm"]',
            "field_selector_anno_nascita": 'input[placeholder="aaaa"]',
        },
        note="Banca dati pubblica I Nomi di Fossoli.",
        timeout=8,
    )


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
        if self.selector.endswith("#edit-submit-persone") or "Cerca" in self.selector:
            self.page.submit()

    def fill(self, value: str) -> None:
        self.page.fields[self.selector] = value


class FakeStoriaMemoriaPage:
    def __init__(self, responses: list[dict[str, str]]):
        self.responses = responses
        self.fields: dict[str, str] = {}
        self.url = "about:blank"
        self.submit_index = 0
        self.current_html = "<html></html>"

    def goto(self, url: str, wait_until: str | None = None, timeout: int | None = None) -> None:
        self.url = url

    def wait_for_load_state(self, state: str, timeout: int | None = None) -> None:
        return None

    def locator(self, selector: str):
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

    def new_page(self):
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
    def __init__(self, responses: list[dict[str, str]]):
        self.page = FakeStoriaMemoriaPage(responses)

    def __call__(self):
        return self

    def __enter__(self):
        return FakeStoriaMemoriaPlaywright(self.page)

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeAuthenticatedSession:
    def __init__(self, source: Source, repo_root: Path):
        self.source = source
        self.repo_root = repo_root
        self.ensure_count = 0
        self.fetch_count = 0
        self.allow_cache_values: list[bool] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ensure_authenticated(self):
        self.ensure_count += 1
        return None

    def fetch_html(self, url: str, *, allow_cache: bool = True) -> str:
        self.allow_cache_values.append(allow_cache)
        self.fetch_count += 1
        return """
        <html>
          <body>
            <main>
              <h1>Andreoli Dino</h1>
              <div>Luogo di nascita: San Lazzaro di Savena</div>
              <img src="/wp-content/uploads/schede/andreoli-dino.jpg" alt="Scheda Andreoli Dino">
            </main>
          </body>
        </html>
        """

    def has_cached_html(self, url: str) -> bool:
        return False

    def close(self) -> None:
        return None


class UniformSourceConnectorTests(unittest.TestCase):
    def workspace_temp_dir(self) -> Path:
        base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
        base_dir.mkdir(exist_ok=True)
        tmp_dir = base_dir / f"uniform-cache-{uuid.uuid4().hex}"
        tmp_dir.mkdir()
        self.addCleanup(lambda: shutil.rmtree(tmp_dir, ignore_errors=True))
        return tmp_dir

    def test_connector_interprets_partigiani_italia_candidate_results_reference_only(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        definition = load_source_definition(make_source(), repo_root=repo_root)
        connector = UniformSourceConnector(
            make_source(),
            source_definition=definition,
            executor=HttpGetFormSearchExecutor(fetcher=lambda url, timeout: result_list_html()),
            detail_html_provider=lambda url: partigiani_detail_login_html(),
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        results = connector.search_person(
            PersonQuery(
                full_name="ANDREOLI DINO",
                family_name="ANDREOLI",
                given_name="DINO",
                birth_date="17 maggio 1920, San Lazzaro di Savena",
            )
        )

        self.assertEqual([result.status for result in results], ["candidate_results", "candidate_results", "candidate_results"])
        self.assertTrue(all("cognome=ANDREOLI" in result.search_url for result in results))
        self.assertEqual([hit.title for hit in results[0].hits], ["ANDREOLI DINO", "ANDREOLI DINO DETTO LUPO"])

        documents = connector.fetch_detail(results[0])
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].access_date, "2026-05-01")
        self.assertEqual(documents[0].metadata["access_mode"], "detail_page")
        self.assertEqual(documents[0].metadata["document_type"], "detail_document")
        self.assertEqual(documents[0].metadata["detail_assessment"], "detail_needs_manual_review")
        self.assertEqual(connector.extract_evidence(documents[0]), [])

    def test_connector_can_limit_runtime_search_attempts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        definition = load_source_definition(make_source(), repo_root=repo_root)
        connector = UniformSourceConnector(
            make_source(),
            source_definition=definition,
            executor=HttpGetFormSearchExecutor(fetcher=lambda url, timeout: result_list_html()),
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
            max_search_attempts=1,
        )

        results = connector.search_person(
            PersonQuery(
                full_name="ANDREOLI DINO",
                family_name="ANDREOLI",
                given_name="DINO",
                birth_date="17 maggio 1920, San Lazzaro di Savena",
            )
        )

        self.assertEqual(len(results), 1)
        self.assertIn("cognome-nome-contains", results[0].query)
        self.assertNotIn("cognome-nome-nascita", results[0].query)

    def test_partigiani_italia_results_are_not_blocked_only_because_page_contains_login_link(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        definition = load_source_definition(make_source(), repo_root=repo_root)
        connector = UniformSourceConnector(
            make_source(),
            source_definition=definition,
            executor=HttpGetFormSearchExecutor(fetcher=lambda url, timeout: result_list_html_with_login_link()),
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))[0]

        self.assertEqual(result.status, "candidate_results")
        self.assertEqual(len(result.hits), 2)
        self.assertIn("/persona/?id=", result.hits[0].url)

    def test_partigiani_italia_can_fetch_detail_via_manual_authenticated_session(self) -> None:
        repo_root = self.workspace_temp_dir()
        source = make_authenticated_partigiani_source()
        definition = load_source_definition(source, repo_root=Path(__file__).resolve().parents[1])
        session_holder: dict[str, FakeAuthenticatedSession] = {}

        def authenticated_session_factory(source: Source, repo_root_path: Path):
            session = FakeAuthenticatedSession(source, repo_root_path)
            session_holder["session"] = session
            return session

        connector = UniformSourceConnector(
            source,
            source_definition=definition,
            executor=HttpGetFormSearchExecutor(fetcher=lambda url, timeout: result_list_html()),
            authenticated_session_factory=authenticated_session_factory,
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))[0]
        documents = connector.fetch_detail(result)

        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].metadata["access_mode"], "detail_page")
        self.assertEqual(documents[0].metadata["detail_assessment"], "claim_candidates_extracted")
        self.assertIn("partigiani_italia_image_urls_json", documents[0].metadata)
        self.assertEqual(documents[0].metadata["content_cleaning"], "partigiani_italia_detail_v1")
        self.assertEqual(session_holder["session"].ensure_count, 1)
        self.assertEqual(session_holder["session"].fetch_count, 2)

    def test_partigiani_italia_can_retry_blocked_search_via_manual_authenticated_session(self) -> None:
        repo_root = self.workspace_temp_dir()
        source = make_authenticated_partigiani_source()
        definition = load_source_definition(source, repo_root=Path(__file__).resolve().parents[1])
        session_holder: dict[str, FakeAuthenticatedSession] = {}

        class SearchRetrySession(FakeAuthenticatedSession):
            def fetch_html(self, url: str, *, allow_cache: bool = True) -> str:
                self.fetch_count += 1
                return result_list_html()

        def authenticated_session_factory(source: Source, repo_root_path: Path):
            session = SearchRetrySession(source, repo_root_path)
            session_holder["session"] = session
            return session

        connector = UniformSourceConnector(
            source,
            source_definition=definition,
            executor=HttpGetFormSearchExecutor(fetcher=lambda url, timeout: blocked_search_html()),
            authenticated_session_factory=authenticated_session_factory,
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))[0]

        self.assertEqual(result.status, "candidate_results")
        self.assertEqual(len(result.hits), 2)
        self.assertEqual(session_holder["session"].ensure_count, 1)
        self.assertGreaterEqual(session_holder["session"].fetch_count, 1)

    def test_partigiani_italia_blocked_search_retry_ensures_login_even_with_cached_html(self) -> None:
        repo_root = self.workspace_temp_dir()
        source = make_authenticated_partigiani_source()
        definition = load_source_definition(source, repo_root=Path(__file__).resolve().parents[1])
        session_holder: dict[str, FakeAuthenticatedSession] = {}

        class CachedSearchRetrySession(FakeAuthenticatedSession):
            def has_cached_html(self, url: str) -> bool:
                return True

            def fetch_html(self, url: str, *, allow_cache: bool = True) -> str:
                self.allow_cache_values.append(allow_cache)
                self.fetch_count += 1
                return result_list_html()

        def authenticated_session_factory(source: Source, repo_root_path: Path):
            session = CachedSearchRetrySession(source, repo_root_path)
            session_holder["session"] = session
            return session

        connector = UniformSourceConnector(
            source,
            source_definition=definition,
            executor=HttpGetFormSearchExecutor(fetcher=lambda url, timeout: blocked_search_html()),
            authenticated_session_factory=authenticated_session_factory,
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))[0]

        self.assertEqual(result.status, "candidate_results")
        self.assertEqual(session_holder["session"].ensure_count, 1)
        self.assertGreaterEqual(session_holder["session"].fetch_count, 1)
        self.assertTrue(all(value is False for value in session_holder["session"].allow_cache_values))

    def test_partigiani_italia_uses_cache_before_ensuring_authenticated_for_detail(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        definition = load_source_definition(make_authenticated_partigiani_source(), repo_root=repo_root)
        session_factory_calls: list[str] = []

        connector = UniformSourceConnector(
            make_authenticated_partigiani_source(),
            source_definition=definition,
            executor=HttpGetFormSearchExecutor(fetcher=lambda url, timeout: result_list_html()),
            authenticated_session_factory=lambda source, repo_root_path: session_factory_calls.append("opened") or FakeAuthenticatedSession(source, repo_root_path),
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))[0]
        documents = connector.fetch_detail(result)

        self.assertEqual(len(documents), 2)
        self.assertEqual(session_factory_calls, [])

    def test_partigiani_italia_force_refresh_ignores_detail_cache(self) -> None:
        repo_root = self.workspace_temp_dir()
        cache_dir = repo_root / "archivi" / "partigianiditalia.cultura.gov.it" / "persona-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        html_path = cache_dir / "content.html"
        html_path.write_text(
            """
            <html>
              <head><title>Andreoli, Dino cached</title></head>
              <body><h1>Andreoli, Dino cached</h1></body>
            </html>
            """,
            encoding="utf-8",
        )
        (cache_dir / "document.yaml").write_text(
            f"""
url: https://partigianiditalia.cultura.gov.it/persona/?id=5bf69e7e153c89309043fad9
html_path: {html_path}
metadata:
  source_id: partigiani_italia
  access_mode: authenticated_detail_cache
""".strip(),
            encoding="utf-8",
        )
        source = make_authenticated_partigiani_source()
        source.auth["force_refresh_authenticated_cache"] = "true"
        definition = load_source_definition(source, repo_root=Path(__file__).resolve().parents[1])
        session_holder: dict[str, FakeAuthenticatedSession] = {}

        def authenticated_session_factory(source: Source, repo_root_path: Path):
            session = FakeAuthenticatedSession(source, repo_root_path)
            session_holder["session"] = session
            return session

        connector = UniformSourceConnector(
            source,
            source_definition=definition,
            executor=HttpGetFormSearchExecutor(fetcher=lambda url, timeout: result_list_html()),
            authenticated_session_factory=authenticated_session_factory,
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))[0]
        documents = connector.fetch_detail(result)

        self.assertEqual(len(documents), 2)
        self.assertEqual(session_holder["session"].ensure_count, 1)
        self.assertEqual(session_holder["session"].fetch_count, 2)
        self.assertNotIn("cached", documents[0].raw_text)

    def test_partigiani_italia_can_use_local_archival_cache_before_online_search(self) -> None:
        repo_root = self.workspace_temp_dir()
        cache_dir = repo_root / "archivi" / "partigianiditalia.cultura.gov.it" / "persona-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        html_path = cache_dir / "content.html"
        html_path.write_text(
            """
            <html>
              <head><title>Andreoli, Dino</title></head>
              <body><h1>Andreoli, Dino</h1></body>
            </html>
            """,
            encoding="utf-8",
        )
        (cache_dir / "document.yaml").write_text(
            f"""
url: https://partigianiditalia.cultura.gov.it/persona/?id=5bf69e7e153c89309043fad9
html_path: {html_path}
metadata:
  source_id: partigiani_italia
  access_mode: authenticated_detail_cache
""".strip(),
            encoding="utf-8",
        )

        source = make_authenticated_partigiani_source()
        definition = load_source_definition(source, repo_root=Path(__file__).resolve().parents[1])

        class FailingExecutor:
            def execute(self, *, source, attempt):
                raise AssertionError("La ricerca online non dovrebbe partire quando la cache locale contiene gia' la scheda.")

        connector = UniformSourceConnector(
            source,
            source_definition=definition,
            executor=FailingExecutor(),
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="Andreoli Dino", family_name="Andreoli", given_name="Dino"))[0]

        self.assertEqual(result.status, "candidate_results")
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.hits[0].url, "https://partigianiditalia.cultura.gov.it/persona/?id=5bf69e7e153c89309043fad9")

    def test_connector_keeps_no_result_page_as_reference_only_document(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        definition = load_source_definition(make_source(), repo_root=repo_root)
        connector = UniformSourceConnector(
            make_source(),
            source_definition=definition,
            executor=HttpGetFormSearchExecutor(fetcher=lambda url, timeout: no_results_html()),
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="GIORGIO", given_name="GIORGIO"))[0]
        documents = connector.fetch_detail(result)

        self.assertEqual(result.status, "no_results")
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].metadata["document_type"], "search_result_reference")
        self.assertEqual(documents[0].metadata["source_result_status"], "no_results")

    def test_connector_can_use_uniform_path_for_cwgc(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        definition = load_source_definition(make_cwgc_source(), repo_root=repo_root)
        connector = UniformSourceConnector(
            make_cwgc_source(),
            source_definition=definition,
            html_provider=lambda execution_result: cwgc_candidate_results_html(total=2),
            detail_html_provider=lambda url: """
            <html>
              <body>
                <h1>PETER PANOS</h1>
                <div>Rank: Private</div>
                <div>Service No.: 12345</div>
                <div>Date of Death: 11 October 1944</div>
                <div>Cemetery: Forli War Cemetery</div>
              </body>
            </html>
            """,
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        results = connector.search_person(PersonQuery(full_name="PANOV SERGIO", family_name="PANOV", given_name="SERGIO"))

        self.assertEqual([result.status for result in results], ["candidate_results", "candidate_results"])
        self.assertEqual([hit.title for hit in results[0].hits], ["PETER PANOS", "PANO THABENG"])
        documents = connector.fetch_detail(results[0])
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].metadata["document_type"], "detail_document")
        self.assertEqual(documents[0].metadata["detail_assessment"], "claim_candidates_extracted")
        claims = connector.extract_evidence(documents[0])
        self.assertEqual([claim.field for claim in claims], ["person.full_name", "military.rank", "military.service_number", "death.date", "burial.memorial"])

    def test_connector_can_use_uniform_path_for_storia_memoria_bo(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        definition = load_source_definition(make_storia_memoria_source(), repo_root=repo_root)
        executor = PlaywrightFormSearchExecutor(
            playwright_factory=FakeStoriaMemoriaPlaywrightFactory(
                [
                    {
                        "url": "https://www.storiaememoriadibologna.it/ricerca-avanzata/persone?nom=dino&cog=andreoli",
                        "html": """
                        <html>
                          <body>
                            <div class="mini-card position-relative">
                              <div class="testo"><h3 class="h6"><span>Andreoli Dino</span></h3>Brisighella, 13 Ottobre 1944</div>
                              <a href="/archivio/persone/andreoli-dino" class="link-assoluto" title="Andreoli Dino"></a>
                            </div>
                          </body>
                        </html>
                        """,
                    }
                ]
            )
        )
        connector = UniformSourceConnector(
            make_storia_memoria_source(),
            source_definition=definition,
            executor=executor,
            detail_html_provider=lambda url: """
            <html>
              <body>
                <main>
                  <h1>Andreoli Dino</h1>
                  <p>Partigiano caduto a Brisighella il 13 Ottobre 1944.</p>
                </main>
              </body>
            </html>
            """,
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))[0]

        self.assertEqual(result.status, "candidate_results")
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.hits[0].title, "Andreoli Dino")
        self.assertIn("/archivio/persone/andreoli-dino", result.hits[0].url)

        documents = connector.fetch_detail(result)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].metadata["detail_assessment"], "claim_candidates_extracted")
        claims = connector.extract_evidence(documents[0])
        self.assertEqual([claim.field for claim in claims], ["person.full_name", "death.date", "death.place"])
        self.assertTrue(all(claim.review_status == "unreviewed" for claim in claims))

    def test_storia_memoria_bo_unverified_permalink_detail_stays_manual_review_without_live_fetch(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        definition = load_source_definition(make_storia_memoria_source(), repo_root=repo_root)
        person_url = "https://www.storiaememoriadibologna.it/archivio/persone/andreoli-dino"

        class UnverifiedPermalinkExecutor:
            def execute(self, *, source, attempt):
                return [
                    SearchExecutionResult(
                        attempt=attempt,
                        title=attempt.label,
                        url="https://www.storiaememoriadibologna.it/ricerca-avanzata/persone",
                        status="ok",
                        payload={
                            "html": (
                                "<html><body><main>"
                                f'<a href="{person_url}" title="Andreoli Dino">Andreoli Dino</a>'
                                "<p>Permalink persona costruito deterministicamente dal nome/cognome.</p>"
                                "</main></body></html>"
                            ),
                            "storia_memoria_bo_resolution": "direct_person_permalink_unverified",
                            "storia_memoria_bo_permalink": person_url,
                        },
                    )
                ]

        connector = UniformSourceConnector(
            make_storia_memoria_source(),
            source_definition=definition,
            executor=UnverifiedPermalinkExecutor(),
            detail_html_provider=lambda url: (_ for _ in ()).throw(AssertionError("Il detail live non deve essere chiamato.")),
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = connector.search_person(PersonQuery(full_name="ANDREOLI DINO", family_name="ANDREOLI", given_name="DINO"))[0]
        documents = connector.fetch_detail(result)

        self.assertEqual(result.status, "candidate_results")
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].url, person_url)
        self.assertEqual(documents[0].metadata["detail_assessment"], "detail_needs_manual_review")
        self.assertEqual(connector.extract_evidence(documents[0]), [])

    def test_connector_can_extract_detail_claims_for_tna_wo417(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        definition = load_source_definition(make_tna_source(), repo_root=repo_root)
        connector = UniformSourceConnector(
            make_tna_source(),
            source_definition=definition,
            executor=PlaywrightFormSearchExecutor(playwright_factory=FakeStoriaMemoriaPlaywrightFactory([])),
            detail_html_provider=lambda url: """
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
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
        )

        result = SourceResult(
            source_id="tna_wo417",
            source_name="TNA Discovery - WO 417",
            status="candidate_results",
            note="detail candidate",
            query='exact-original-wo417; _ep="ANDREOLI DINO"',
            search_url="https://discovery.nationalarchives.gov.uk/results/r/example",
            hits=[SearchHit(title="WO 417 record", url="https://discovery.nationalarchives.gov.uk/details/r/example")],
        )

        documents = connector.fetch_detail(result)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].metadata["document_type"], "detail_document")
        self.assertEqual(documents[0].metadata["detail_assessment"], "claim_candidates_extracted")
        claims = connector.extract_evidence(documents[0])
        self.assertEqual(
            [claim.field for claim in claims],
            ["archive.title", "archive.reference", "archive.covering_dates", "person.full_name", "archive.description"],
        )

    def test_fondazione_fossoli_uses_structured_playwright_form_without_navigation_claims(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source = make_fondazione_fossoli_source()
        definition = load_source_definition(source, repo_root=repo_root)
        executor = PlaywrightFormSearchExecutor(
            playwright_factory=FakeStoriaMemoriaPlaywrightFactory(
                [
                    {
                        "url": "https://www.fondazionefossoli.org/centro-studi/i-nomi-di-fossoli/?search=1",
                        "html": """
                        <html>
                          <body>
                            <main>
                              <a href="https://www.fondazionefossoli.org/scheda/guazzaloca-laura">Guazzaloca Laura</a>
                              <a href="https://www.fondazionefossoli.org/i-luoghi/campo-di-fossoli/">Il Campo</a>
                            </main>
                          </body>
                        </html>
                        """,
                    }
                ]
            )
        )
        connector = UniformSourceConnector(
            source,
            source_definition=definition,
            executor=executor,
            detail_html_provider=lambda url: """
            <html>
              <body>
                <main>
                  <h1>Guazzaloca Laura</h1>
                  <p>Record candidato da revisionare manualmente.</p>
                </main>
              </body>
            </html>
            """,
            run_id="uniform-test",
            now_factory=lambda: datetime(2026, 5, 1, 10, 0, tzinfo=UTC),
            repo_root=repo_root,
            max_search_attempts=1,
        )

        results = connector.search_person(
            PersonQuery(
                full_name="Guazzaloca Laura",
                family_name="Guazzaloca",
                given_name="Laura",
                birth_date="28 gennaio 1920, Bologna",
            )
        )

        self.assertEqual(results[0].status, "candidate_results")
        self.assertEqual([hit.title for hit in results[0].hits], ["Guazzaloca Laura"])
        self.assertEqual(
            executor.playwright_factory.page.fields,
            {
                'body >> input[placeholder="es: Mario"]': "Laura",
                'body >> input[placeholder="es: Rossi"]': "Guazzaloca",
            },
        )
        documents = connector.fetch_detail(results[0])
        self.assertEqual(documents[0].metadata["detail_assessment"], "detail_document_fetched")
        self.assertEqual(connector.extract_evidence(documents[0]), [])


if __name__ == "__main__":
    unittest.main()
