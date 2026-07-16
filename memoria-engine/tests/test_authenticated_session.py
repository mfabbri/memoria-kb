from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.archival_html_cache import ArchivalHtmlCache
from caduti_fonti_report.authenticated_session import ManualAuthenticatedPlaywrightSession, source_uses_manual_authenticated_session
from caduti_fonti_report.ensure_authenticated_session import ensure_authenticated_session
from caduti_fonti_report.models import Source
from caduti_fonti_report.queries import default_query


def make_authenticated_source() -> Source:
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
            "min_delay_ms_between_actions": "100",
            "max_delay_ms_between_actions": "100",
            "min_read_delay_ms": "200",
            "max_read_delay_ms": "200",
            "archival_cache_root": "archivi",
            "audit_log_path": "logs/partigiani_italia_authenticated_session.ndjson",
        },
        timeout=5,
    )


class FakeLocator:
    def __init__(self, page, selector: str):
        self.page = page
        self.selector = selector

    def count(self) -> int:
        if self.selector == 'a[href*="logout"]':
            return 1 if self.page.logged_in else 0
        if self.selector == "body":
            return 1
        return 0

    def inner_text(self, timeout: int | None = None) -> str:
        return self.page.body_text


class FakePage:
    def __init__(self):
        self.url = "about:blank"
        self.logged_in = True
        self.body_text = "Area riservata logout"
        self.goto_calls: list[str] = []
        self.wait_calls: list[int] = []
        self.html_by_url = {
            "https://partigianiditalia.cultura.gov.it/": "<html><body>Area riservata logout</body></html>",
            "https://partigianiditalia.cultura.gov.it/persona/?id=123": "<html><body><h1>Andreoli Dino</h1></body></html>",
        }

    def goto(self, url: str, wait_until: str | None = None, timeout: int | None = None) -> None:
        self.url = url
        self.goto_calls.append(url)
        if "login" in url and not self.logged_in:
            self.body_text = "login spid cie"
        elif self.logged_in:
            self.body_text = "Area riservata logout"

    def wait_for_load_state(self, state: str, timeout: int | None = None) -> None:
        return None

    def wait_for_timeout(self, milliseconds: int) -> None:
        self.wait_calls.append(milliseconds)
        self.logged_in = True
        self.body_text = "Area riservata logout"

    def locator(self, selector: str):
        return FakeLocator(self, selector)

    def content(self) -> str:
        return self.html_by_url.get(self.url, "<html><body>Area riservata logout</body></html>")


class FakePersistentContext:
    def __init__(self, page: FakePage):
        self.pages = [page]
        self.page = page
        self.closed = False

    def new_page(self):
        return self.page

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, page: FakePage):
        self.page = page

    def launch_persistent_context(self, user_data_dir: str, **kwargs):
        return FakePersistentContext(self.page)


class FakePlaywright:
    def __init__(self, page: FakePage):
        self.chromium = FakeChromium(page)


class FakePlaywrightFactory:
    def __init__(self, page: FakePage):
        self.page = page

    def __call__(self):
        return self

    def __enter__(self):
        return FakePlaywright(self.page)

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeEnsuredSession:
    def __init__(self, source: Source, repo_root: Path | None = None):
        self.source = source
        self.repo_root = repo_root or Path.cwd()
        self.policy = type("Policy", (), {"profile_dir": str(self.repo_root / "secure/browser-profiles/test"), "audit_log_path": str(self.repo_root / "logs/test.ndjson")})()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ensure_authenticated(self):
        return type("State", (), {"state": "logged-in", "checked_url": "https://partigianiditalia.cultura.gov.it/", "note": "fake"})()


class AuthenticatedSessionTests(unittest.TestCase):
    def test_source_can_be_marked_as_manual_authenticated_session(self) -> None:
        self.assertTrue(source_uses_manual_authenticated_session(make_authenticated_source()))

    def test_manual_authenticated_session_can_detect_logged_in_state_and_fetch_html(self) -> None:
        tmp_dir = Path(__file__).resolve().parents[1] / ".tmp-tests" / "authenticated-session"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        for path in tmp_dir.glob("**/*"):
            if path.is_file():
                path.unlink()
        if (tmp_dir / "logs").exists():
            for path in (tmp_dir / "logs").glob("*"):
                if path.is_file():
                    path.unlink()
        if (tmp_dir / "secure").exists():
            for path in (tmp_dir / "secure").glob("**/*"):
                if path.is_file():
                    path.unlink()
        page = FakePage()
        session = ManualAuthenticatedPlaywrightSession(
            make_authenticated_source(),
            repo_root=tmp_dir,
            playwright_factory=FakePlaywrightFactory(page),
        )

        with session:
            state = session.ensure_authenticated()
            html_text = session.fetch_html("https://partigianiditalia.cultura.gov.it/persona/?id=123")

        self.assertEqual(state.state, "logged-in")
        self.assertIn("Andreoli Dino", html_text)
        self.assertIn(200, page.wait_calls)
        self.assertTrue((tmp_dir / "logs" / "partigiani_italia_authenticated_session.ndjson").exists())
        cached_files = list((tmp_dir / "archivi" / "partigianiditalia.cultura.gov.it").glob("**/content.html"))
        self.assertTrue(cached_files)

    def test_manual_login_polling_does_not_reload_auth_check_page(self) -> None:
        tmp_dir = Path(__file__).resolve().parents[1] / ".tmp-tests" / "authenticated-session-polling"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        page = FakePage()
        page.logged_in = False
        page.body_text = "login spid cie"
        session = ManualAuthenticatedPlaywrightSession(
            make_authenticated_source(),
            repo_root=tmp_dir,
            playwright_factory=FakePlaywrightFactory(page),
        )

        with session:
            state = session.ensure_authenticated()

        self.assertEqual(state.state, "logged-in")
        self.assertGreaterEqual(len(page.goto_calls), 2)
        self.assertEqual(page.goto_calls[0], "https://partigianiditalia.cultura.gov.it/")
        self.assertEqual(page.goto_calls[1], "https://partigianiditalia.cultura.gov.it/login/")
        self.assertNotIn("https://partigianiditalia.cultura.gov.it/", page.goto_calls[2:])

    def test_login_page_with_reserved_area_text_is_not_treated_as_logged_in(self) -> None:
        tmp_dir = Path(__file__).resolve().parents[1] / ".tmp-tests" / "authenticated-session-ambiguous"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        page = FakePage()
        page.logged_in = False
        page.body_text = "Area riservata login SPID CIE"
        session = ManualAuthenticatedPlaywrightSession(
            make_authenticated_source(),
            repo_root=tmp_dir,
            playwright_factory=FakePlaywrightFactory(page),
        )

        with session:
            state = session.detect_login_state(navigate=False)

        self.assertEqual(state.state, "anonymous")
        self.assertEqual(state.note, "logged_out_text")

    def test_authenticated_session_uses_archival_cache_before_refetching(self) -> None:
        tmp_dir = Path(__file__).resolve().parents[1] / ".tmp-tests" / "authenticated-session-cache"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        source = make_authenticated_source()
        source.auth["archival_cache_root"] = "archivi"
        session = ManualAuthenticatedPlaywrightSession(
            source,
            repo_root=tmp_dir,
            playwright_factory=FakePlaywrightFactory(FakePage()),
        )

        cache = ArchivalHtmlCache(tmp_dir / "archivi")
        cache.write(
            url="https://partigianiditalia.cultura.gov.it/persona/?id=123",
            html_text="<html><body><h1>Cached Andreoli Dino</h1></body></html>",
        )

        with session:
            html_text = session.fetch_html("https://partigianiditalia.cultura.gov.it/persona/?id=123")

        self.assertIn("Cached Andreoli Dino", html_text)

    def test_cli_helper_can_ensure_authenticated_session(self) -> None:
        tmp_dir = Path(__file__).resolve().parents[1] / ".tmp-tests" / "authenticated-session-cli"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        sources_yaml = tmp_dir / "fonti.yaml"
        sources_yaml.write_text(
            """
enabled_sources:
  - partigiani_italia
sources:
  - id: partigiani_italia
    name: I Partigiani d'Italia - ricerca pubblica
    kind: search_form_get_name
    query_mode: default
    url_template: "https://partigianiditalia.cultura.gov.it/cerca/"
    auth:
      auth_mode: "manual_persistent_context"
      profile_root: "secure/browser-profiles"
      profile_id: "partigiani_italia_acs"
      login_entry_url: "https://partigianiditalia.cultura.gov.it/login/"
      auth_check_url: "https://partigianiditalia.cultura.gov.it/"
      logged_in_text: "logout"
      logged_out_text: "login||spid||cie"
      logged_in_selector: 'a[href*="logout"]'
      login_wait_seconds: "5"
      min_delay_ms_between_actions: "100"
      max_delay_ms_between_actions: "100"
      min_read_delay_ms: "200"
      max_read_delay_ms: "200"
      audit_log_path: "logs/partigiani_italia_authenticated_session.ndjson"
""".strip(),
            encoding="utf-8",
        )

        with patch("caduti_fonti_report.ensure_authenticated_session.ManualAuthenticatedPlaywrightSession", FakeEnsuredSession):
            result = ensure_authenticated_session(
                source_id="partigiani_italia",
                sources_yaml=sources_yaml,
                repo_root=tmp_dir,
            )

        self.assertEqual(result["state"], "logged-in")
        self.assertIn("secure/browser-profiles/test", result["profile_dir"].replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
