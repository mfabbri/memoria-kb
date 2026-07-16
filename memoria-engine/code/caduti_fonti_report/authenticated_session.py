from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import random
import re
import time

from .archival_html_cache import ArchivalHtmlCache
from .models import Source


def _get_playwright_factory():
    from playwright.sync_api import sync_playwright

    return sync_playwright


@dataclass(frozen=True)
class AuthenticatedSessionPolicy:
    mode: str
    requires_human_login: bool
    allow_cookie_export: bool
    allow_token_export: bool
    max_wait_seconds: int
    min_delay_ms_between_actions: int
    max_delay_ms_between_actions: int
    min_read_delay_ms: int
    max_read_delay_ms: int
    keep_open_seconds: int
    profile_dir: str
    audit_log_path: str


@dataclass(frozen=True)
class AuthenticatedSessionState:
    state: str
    note: str = ""
    checked_url: str = ""


@dataclass(frozen=True)
class LoginSignalConfig:
    auth_check_url: str
    login_entry_url: str
    logged_in_text: tuple[str, ...] = ()
    logged_out_text: tuple[str, ...] = ()
    logged_in_selector: str = ""
    logged_out_selector: str = ""
    max_wait_seconds: int = 300


class ManualAuthenticatedPlaywrightSession:
    def __init__(
        self,
        source: Source,
        *,
        repo_root: Path | None = None,
        playwright_factory: Callable[[], object] | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.source = source
        self.repo_root = repo_root or Path.cwd()
        self.playwright_factory = playwright_factory or _get_playwright_factory
        self.now_factory = now_factory or (lambda: datetime.now(UTC))
        self.policy = _policy_from_source(source=source, repo_root=self.repo_root)
        self.login_config = _login_config_from_source(source)
        self.archival_cache = _archival_cache_from_source(source=source, repo_root=self.repo_root)
        self.force_refresh_cache = _as_bool(source.auth.get("force_refresh_authenticated_cache", "false"))
        self._playwright_context_manager = None
        self._context = None
        self._page = None
        self._last_navigation_monotonic = 0.0

    def __enter__(self) -> ManualAuthenticatedPlaywrightSession:
        self._open()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def ensure_authenticated(self) -> AuthenticatedSessionState:
        self._require_open_page()
        state = self.detect_login_state()
        if state.state == "logged-in":
            self._last_navigation_monotonic = time.monotonic()
            self._write_audit("session_reused", {"checked_url": state.checked_url, "note": state.note})
            return state

        self._write_audit("login_required", {"checked_url": state.checked_url, "note": state.note})
        self._page.goto(self.login_config.login_entry_url, wait_until="domcontentloaded", timeout=self.source.timeout * 1000)
        self._write_audit("manual_login_gate_started", {"login_entry_url": self.login_config.login_entry_url})
        print(
            "Login manuale richiesto: completa SPID/CIE nel browser aperto. "
            f"Attendo fino a {self.login_config.max_wait_seconds}s per {self.source.source_id}."
        )

        started_at = time.monotonic()
        deadline = started_at + self.login_config.max_wait_seconds
        next_progress_at = started_at + 30
        while time.monotonic() < deadline:
            self._page.wait_for_timeout(3000)
            state = self.detect_login_state(navigate=False)
            if state.state == "logged-in":
                self._last_navigation_monotonic = time.monotonic()
                self._write_audit("manual_login_detected", {"checked_url": state.checked_url, "note": state.note})
                return state
            now = time.monotonic()
            if now >= next_progress_at:
                remaining_seconds = max(0, int(deadline - now))
                print(f"Login manuale ancora in attesa per {self.source.source_id}: {remaining_seconds}s rimanenti.")
                next_progress_at = now + 30

        self._write_audit("manual_login_timeout", {"login_entry_url": self.login_config.login_entry_url})
        raise RuntimeError(
            f"Login manuale non completato entro {self.login_config.max_wait_seconds}s per la fonte {self.source.source_id}."
        )

    def detect_login_state(self, *, navigate: bool = True) -> AuthenticatedSessionState:
        self._require_open_page()
        if navigate:
            self._page.goto(self.login_config.auth_check_url, wait_until="domcontentloaded", timeout=self.source.timeout * 1000)
            self._page.wait_for_load_state("networkidle", timeout=self.source.timeout * 1000)

        page_text = self._safe_body_text()
        current_url = str(self._page.url)
        if self.login_config.logged_in_selector and self._page.locator(self.login_config.logged_in_selector).count() > 0:
            return AuthenticatedSessionState(state="logged-in", note="logged_in_selector", checked_url=current_url)
        if self.login_config.logged_out_selector and self._page.locator(self.login_config.logged_out_selector).count() > 0:
            return AuthenticatedSessionState(state="anonymous", note="logged_out_selector", checked_url=current_url)
        if _contains_any(page_text, self.login_config.logged_out_text):
            return AuthenticatedSessionState(state="anonymous", note="logged_out_text", checked_url=current_url)
        if _contains_any(page_text, self.login_config.logged_in_text):
            return AuthenticatedSessionState(state="logged-in", note="logged_in_text", checked_url=current_url)
        return AuthenticatedSessionState(state="unknown", note="no_login_signal", checked_url=current_url)

    def fetch_html(self, url: str, *, allow_cache: bool = True) -> str:
        if allow_cache and self.archival_cache is not None and not self.force_refresh_cache:
            cached_html = self.archival_cache.read(url)
            if cached_html is not None:
                self._write_audit("detail_cache_hit", {"url": url, "html_length": str(len(cached_html))})
                return cached_html

        self._require_open_page()
        self._wait_between_human_actions()
        self._page.goto(url, wait_until="domcontentloaded", timeout=self.source.timeout * 1000)
        self._page.wait_for_load_state("networkidle", timeout=self.source.timeout * 1000)
        self._wait_for_human_reading()
        html_text = self._page.content()
        self._last_navigation_monotonic = time.monotonic()
        if self.archival_cache is not None:
            self.archival_cache.write(
                url=url,
                html_text=html_text,
                metadata={
                    "source_id": self.source.source_id,
                    "access_mode": "authenticated_detail_cache",
                    "force_refresh": str(self.force_refresh_cache).lower(),
                },
            )
        self._write_audit("detail_fetch", {"url": url, "html_length": str(len(html_text))})
        return html_text

    def has_cached_html(self, url: str) -> bool:
        return self.archival_cache is not None and not self.force_refresh_cache and self.archival_cache.has(url)


    @property
    def page(self):
        """Return the active Playwright page for dedicated authenticated executors."""
        return self._require_open_page()

    def close(self) -> None:
        """Close the Playwright session defensively.

        Some sources use a persistent browser context. During manual or
        authenticated browsing Playwright can already have closed the page,
        context, or browser before the report runner reaches the final cleanup
        block. Cleanup must therefore be idempotent: a close failure must not
        turn an otherwise completed source run into a report failure.
        """
        close_errors: list[str] = []

        if self._page is not None:
            try:
                if self.policy.keep_open_seconds > 0 and hasattr(self._page, "is_closed") and not self._page.is_closed():
                    self._write_audit("keep_open_before_close", {"seconds": str(self.policy.keep_open_seconds)})
                    self._page.wait_for_timeout(self.policy.keep_open_seconds * 1000)
                if hasattr(self._page, "is_closed") and not self._page.is_closed():
                    self._page.close()
            except Exception as exc:  # noqa: BLE001 - best-effort cleanup
                close_errors.append(f"page.close: {type(exc).__name__}: {exc}")
            finally:
                self._page = None

        if self._context is not None:
            try:
                self._context.close()
            except Exception as exc:  # noqa: BLE001 - context may already be closed
                close_errors.append(f"context.close: {type(exc).__name__}: {exc}")
            finally:
                self._context = None

        if self._playwright_context_manager is not None:
            try:
                self._playwright_context_manager.__exit__(None, None, None)
            except Exception as exc:  # noqa: BLE001 - best-effort cleanup
                close_errors.append(f"playwright.__exit__: {type(exc).__name__}: {exc}")
            finally:
                self._playwright_context_manager = None

        if close_errors:
            self._write_audit("close_ignored_errors", {"errors": " | ".join(close_errors)})

    def _open(self) -> None:
        profile_dir = Path(self.policy.profile_dir)
        profile_dir.mkdir(parents=True, exist_ok=True)
        playwright_context_manager = self.playwright_factory()
        if not hasattr(playwright_context_manager, "__enter__") and callable(playwright_context_manager):
            playwright_context_manager = playwright_context_manager()
        self._playwright_context_manager = playwright_context_manager
        playwright = self._playwright_context_manager.__enter__()
        browser_channel = self.source.auth.get("browser_channel", "").strip() or None
        browser_user_agent = self.source.auth.get(
            "browser_user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        ).strip()
        headless = _as_bool(self.source.auth.get("headless", "false"))
        self._context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=headless,
            channel=browser_channel,
            user_agent=browser_user_agent,
            locale="it-IT",
            viewport={"width": 1440, "height": 1200},
            accept_downloads=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._write_audit("persistent_context_opened", {"profile_dir": str(profile_dir), "headless": str(headless).lower()})

    def _require_open_page(self):
        if self._page is None:
            raise RuntimeError("Sessione Playwright persistente non aperta.")
        return self._page

    def _safe_body_text(self) -> str:
        try:
            return " ".join(self._page.locator("body").inner_text(timeout=5000).split())
        except Exception:  # noqa: BLE001
            return ""

    def _wait_between_human_actions(self) -> None:
        if self._last_navigation_monotonic <= 0:
            return
        elapsed_ms = int((time.monotonic() - self._last_navigation_monotonic) * 1000)
        target_ms = _bounded_delay_ms(
            self.policy.min_delay_ms_between_actions,
            self.policy.max_delay_ms_between_actions,
        )
        remaining_ms = max(0, target_ms - elapsed_ms)
        if remaining_ms > 0:
            self._page.wait_for_timeout(remaining_ms)
            self._write_audit("human_delay_between_actions", {"delay_ms": str(remaining_ms)})

    def _wait_for_human_reading(self) -> None:
        delay_ms = _bounded_delay_ms(self.policy.min_read_delay_ms, self.policy.max_read_delay_ms)
        if delay_ms > 0:
            self._page.wait_for_timeout(delay_ms)
            self._write_audit("human_read_delay", {"delay_ms": str(delay_ms)})

    def _write_audit(self, action: str, payload: dict[str, str]) -> None:
        audit_path = Path(self.policy.audit_log_path)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": self.now_factory().isoformat(),
            "source_id": self.source.source_id,
            "action": action,
            **payload,
        }
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def source_uses_manual_authenticated_session(source: Source) -> bool:
    return source.auth.get("auth_mode", "").strip().casefold() == "manual_persistent_context"


def _policy_from_source(*, source: Source, repo_root: Path) -> AuthenticatedSessionPolicy:
    profile_root = source.auth.get("profile_root", "secure/browser-profiles").strip() or "secure/browser-profiles"
    profile_id = source.auth.get("profile_id", source.source_id).strip() or source.source_id
    audit_log = source.auth.get("audit_log_path", f"logs/{source.source_id}_authenticated_session.ndjson").strip()
    return AuthenticatedSessionPolicy(
        mode=source.auth.get("auth_mode", "").strip(),
        requires_human_login=True,
        allow_cookie_export=False,
        allow_token_export=False,
        max_wait_seconds=_as_positive_int(source.auth.get("login_wait_seconds", "300"), 300),
        min_delay_ms_between_actions=_as_positive_int(source.auth.get("min_delay_ms_between_actions", "4000"), 4000),
        max_delay_ms_between_actions=_as_positive_int(source.auth.get("max_delay_ms_between_actions", "8000"), 8000),
        min_read_delay_ms=_as_positive_int(source.auth.get("min_read_delay_ms", "5000"), 5000),
        max_read_delay_ms=_as_positive_int(source.auth.get("max_read_delay_ms", "9000"), 9000),
        keep_open_seconds=_as_non_negative_int(source.auth.get("keep_open_seconds", "0"), 0),
        profile_dir=str((repo_root / profile_root / profile_id).resolve()),
        audit_log_path=str((repo_root / audit_log).resolve()),
    )


def _login_config_from_source(source: Source) -> LoginSignalConfig:
    auth_check_url = source.auth.get("auth_check_url", "").strip() or source.search_url_builder("")
    login_entry_url = source.auth.get("login_entry_url", "").strip() or auth_check_url
    return LoginSignalConfig(
        auth_check_url=auth_check_url,
        login_entry_url=login_entry_url,
        logged_in_text=_parse_multi_value(source.auth.get("logged_in_text", "")),
        logged_out_text=_parse_multi_value(source.auth.get("logged_out_text", "")),
        logged_in_selector=source.auth.get("logged_in_selector", "").strip(),
        logged_out_selector=source.auth.get("logged_out_selector", "").strip(),
        max_wait_seconds=_as_positive_int(source.auth.get("login_wait_seconds", "300"), 300),
    )


def _archival_cache_from_source(*, source: Source, repo_root: Path) -> ArchivalHtmlCache | None:
    cache_root = source.auth.get("archival_cache_root", "").strip()
    if not cache_root:
        return None
    return ArchivalHtmlCache(repo_root / cache_root)


def _contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(candidate.casefold() in lowered for candidate in candidates if candidate)


def _parse_multi_value(value: str) -> tuple[str, ...]:
    tokens = [item.strip() for item in re.split(r"\s*\|\|\s*|\s*,\s*", value or "") if item.strip()]
    return tuple(tokens)


def _as_positive_int(value: str, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _as_non_negative_int(value: str, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return default
    return parsed if parsed >= 0 else default


def _as_bool(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "si", "sì"}


def _bounded_delay_ms(minimum: int, maximum: int) -> int:
    low = minimum if minimum > 0 else 0
    high = maximum if maximum >= low else low
    return random.randint(low, high) if high > low else low
