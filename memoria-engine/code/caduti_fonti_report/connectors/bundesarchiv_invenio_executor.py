from __future__ import annotations

from datetime import datetime
from pathlib import Path
import html
import json
import os
import re
import time
import urllib.parse
from typing import Any

from ..authenticated_session import ManualAuthenticatedPlaywrightSession, AuthenticatedSessionState
from ..http_utils import strip_tags
from ..models import Source
from .bundesarchiv_invenio_parsing import (
    InvenioCandidate,
    candidate_stabilization_key as _candidate_stabilization_key,
    deduplicate_invenio_candidates as _deduplicate_invenio_candidates,
    extract_panel_hit_candidates as _parse_panel_hit_candidates,
    extract_tree_node_candidates as _parse_tree_node_candidates,
    parse_attrs as _parse_attrs,
)
from .search_executor import SearchExecutionResult
from .search_strategy import SearchAttempt


# Field ids used by memoria-sources/source_strategies/bundesarchiv_invenio.yaml.
# The html_name values come from memoria-sources/source_profiles/bundesarchiv_invenio.yaml.
FIELD_HTML_NAMES: dict[str, str] = {
    "simple_search_terms": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchEinfach:searchStrings",
    "simple_digital_only": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchEinfach:nurDigitalisaten_input",
    "simple_signature": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchEinfach:searchSignStrings",
    "simple_signature_type": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchEinfach:signTypeSelectedGroup",
    "simple_time_from": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchEinfach:timeRangeFrom",
    "simple_time_to": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchEinfach:timeRangeTo",
    "advanced_search_terms": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:searchStrings",
    "advanced_concat_mode": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:concatSelectedGroup",
    "advanced_left_truncation": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:leftTrunk_input",
    "advanced_right_truncation": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:rightTrunk_input",
    "advanced_digital_only": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:nurDigitalisaten_input",
    "advanced_thesaurus": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:mitThesaurus_input",
    "advanced_record_scope": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:rechercheList",
    "advanced_time_from": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:timeRangeFrom",
    "advanced_time_to": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:timeRangeTo",
    "advanced_file_number": "masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:aktenzeichen",
}

TEXT_FIELD_IDS = {
    "simple_search_terms",
    "simple_signature",
    "simple_time_from",
    "simple_time_to",
    "advanced_search_terms",
    "advanced_time_from",
    "advanced_time_to",
    "advanced_file_number",
}

CHECKBOX_FIELD_IDS = {
    "simple_digital_only",
    "advanced_left_truncation",
    "advanced_right_truncation",
    "advanced_digital_only",
    "advanced_thesaurus",
}

RADIO_FIELD_IDS = {
    "simple_signature_type",
    "advanced_concat_mode",
    "advanced_record_scope",
}

SERVICE_URL_MARKERS = (
    "login", "logout", "hilfe", "help", "kontakt", "impressum", "datenschutz", "javax.faces", "primefaces",
)
SERVICE_TITLE_MARKERS = (
    "login", "logout", "hilfe", "kontakt", "impressum", "datenschutz", "abmelden", "anmelden",
)


class BundesarchivInvenioPlaywrightExecutor:
    """Playwright executor for the authenticated Bundesarchiv invenio UI.

    The normal uniform connector can parse static result pages, but invenio is a
    JSF/AJAX application. This executor uses the persistent authenticated browser
    profile configured in camalanca_fonti.yaml, opens the search UI, fills either
    the simple or advanced fields from the strategy attempt, submits the form,
    waits for the dynamic result tab, and converts detected result rows into a
    synthetic HTML page that the existing generic result parser can consume.

    The executor also writes debug artefacts when BUNDESARCHIV_INVENIO_DEBUG is
    true, because selector stabilization must be based on the real authenticated
    page seen by Playwright.
    """

    def __init__(self, *, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or Path.cwd()
        self._session: ManualAuthenticatedPlaywrightSession | None = None
        self._authenticated_state: AuthenticatedSessionState | None = None
        self._debug_enabled = _env_bool("BUNDESARCHIV_INVENIO_DEBUG", default=True)
        self._slow_mo_ms = _env_int("BUNDESARCHIV_INVENIO_SLOWMO_MS", default=0)

    def execute(self, *, source: Source, attempt: SearchAttempt) -> list[SearchExecutionResult]:
        started_at = time.perf_counter()
        debug_dir = self._debug_dir(attempt) if self._debug_enabled else None
        try:
            session = self._ensure_session(source)
            state = self._ensure_authenticated(session)
            page = session.page
            main_url = source.auth.get("main_url", "").strip() or source.search_url_builder("")
            page.goto(main_url, wait_until="domcontentloaded", timeout=source.timeout * 1000)
            _wait_networkidle_best_effort(page, timeout_ms=source.timeout * 1000)
            _install_network_recorder(page, debug_dir)
            self._save_artifacts(debug_dir, "01-main", page)
            _save_dom_diagnostics(debug_dir, "01-main-diagnostics", page)

            if not _looks_authenticated(page):
                self._save_artifacts(debug_dir, "02-auth-state-unexpected", page)
                html_text = page.content()
                return [
                    SearchExecutionResult(
                        attempt=attempt,
                        title=attempt.label,
                        url=str(page.url),
                        status="auth_required",
                        payload={
                            "html": html_text,
                            "error": "Sessione non autenticata o contesto Benutzung non disponibile nella pagina vista da Playwright.",
                            "auth_state": state.state,
                            "auth_note": state.note,
                            "debug_dir": str(debug_dir or ""),
                        },
                    )
                ]

            self._open_search_tab(page, attempt, debug_dir=debug_dir)
            self._save_artifacts(debug_dir, "02-search-tab", page)
            self._fill_attempt_fields(page, attempt)
            self._save_artifacts(debug_dir, "03-filled", page)
            self._submit_search(page, source, debug_dir=debug_dir)
            self._save_artifacts(debug_dir, "04-after-submit", page)
            self._expand_full_tree_views(page, debug_dir=debug_dir)
            _manual_capture_wait_if_enabled(page, debug_dir=debug_dir)

            candidates = self._extract_candidates(page)
            synthetic_html = _synthetic_results_html(candidates, page_url=str(page.url), actual_html=page.content())
            detail_html_by_url = {candidate.url: candidate.detail_html or page.content() for candidate in candidates}
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            return [
                SearchExecutionResult(
                    attempt=attempt,
                    title=attempt.label,
                    url=str(page.url),
                    status="ok",
                    payload={
                        "html": synthetic_html,
                        "detail_html_by_url": detail_html_by_url,
                        "debug_dir": str(debug_dir or ""),
                        "auth_state": state.state,
                        "auth_note": state.note,
                        "elapsed_ms": str(elapsed_ms),
                        "candidate_count": str(len(candidates)),
                    },
                )
            ]
        except Exception as exc:  # noqa: BLE001 - source run must continue and report diagnostics
            error_html = ""
            current_url = source.search_url_builder("")
            try:
                if self._session is not None:
                    page = self._session.page
                    current_url = str(page.url)
                    self._save_artifacts(debug_dir, "99-error", page)
                    error_html = page.content()

                    # If the UI flow failed after the AJAX search had already
                    # returned Tektonik/Klassifikation data, do not discard the
                    # useful candidates. This is common with PrimeFaces pages:
                    # the visible tab can remain unstable while the XML
                    # partial-response contains materialized tree nodes.
                    recovered_candidates = _extract_candidates_from_recorded_ajax(page=page, base_url=current_url)
                    if not recovered_candidates:
                        recovered_candidates = _extract_candidates_from_frames(page=page, base_url=current_url)
                    if recovered_candidates:
                        synthetic_html = _synthetic_results_html(
                            recovered_candidates,
                            page_url=current_url,
                            actual_html=error_html,
                        )
                        detail_html_by_url = {
                            candidate.url: candidate.detail_html or error_html
                            for candidate in recovered_candidates
                        }
                        return [
                            SearchExecutionResult(
                                attempt=attempt,
                                title=attempt.label,
                                url=current_url,
                                status="ok",
                                payload={
                                    "html": synthetic_html,
                                    "detail_html_by_url": detail_html_by_url,
                                    "debug_dir": str(debug_dir or ""),
                                    "error_recovered_from": f"{type(exc).__name__}: {exc}",
                                    "candidate_count": str(len(recovered_candidates)),
                                },
                            )
                        ]
            except Exception:  # noqa: BLE001
                error_html = ""
            return [
                SearchExecutionResult(
                    attempt=attempt,
                    title=attempt.label,
                    url=current_url,
                    status="error",
                    payload={
                        "html": error_html,
                        "error": f"{type(exc).__name__}: {exc}",
                        "debug_dir": str(debug_dir or ""),
                    },
                )
            ]

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            finally:
                self._session = None
                self._authenticated_state = None

    def _ensure_session(self, source: Source) -> ManualAuthenticatedPlaywrightSession:
        if self._session is None:
            self._session = ManualAuthenticatedPlaywrightSession(source, repo_root=self.repo_root)
            self._session.__enter__()
        return self._session

    def _ensure_authenticated(self, session: ManualAuthenticatedPlaywrightSession) -> AuthenticatedSessionState:
        if self._authenticated_state is None or self._authenticated_state.state != "logged-in":
            self._authenticated_state = session.ensure_authenticated()
        return self._authenticated_state

    def _open_search_tab(self, page: Any, attempt: SearchAttempt, *, debug_dir: Path | None) -> None:
        # Invenio is a PrimeFaces/JSF tab view. In the authenticated page seen in
        # May 2026 the tab header is present, but the tab body is lazy-loaded by
        # a JSF/PrimeFaces AJAX request. Do not wait for minutes: try the known
        # strategies quickly, persist diagnostics, then optionally allow a short
        # headed/manual fallback so selectors can be stabilized from real DOM.
        if _search_fields_present(page):
            return

        _click_primefaces_tab(page, tab_label="Suche", tab_index=1, tab_client_id="masterLayoutForm:tabPanel:searchTab")
        _wait_for_search_fields(page, timeout_ms=1500)

        if not _search_fields_present(page):
            _activate_primefaces_tab_with_exact_ajax(
                page,
                tab_index=1,
                tab_client_id="masterLayoutForm:tabPanel:searchTab",
                debug_dir=debug_dir,
            )
            _wait_for_search_fields(page, timeout_ms=3000)

        if not _search_fields_present(page):
            _activate_jsf_ajax_tab_request(
                page,
                tab_index=1,
                tab_client_id="masterLayoutForm:tabPanel:searchTab",
                debug_dir=debug_dir,
            )
            _wait_for_search_fields(page, timeout_ms=3000)

        if not _search_fields_present(page):
            _activate_primefaces_tab_with_ajax(
                page,
                tab_index=1,
                tab_client_id="masterLayoutForm:tabPanel:searchTab",
            )
            _wait_for_search_fields(page, timeout_ms=2500)

        if not _search_fields_present(page):
            _activate_primefaces_tab_with_jquery(
                page,
                tab_index=1,
                tab_client_id="masterLayoutForm:tabPanel:searchTab",
            )
            _wait_for_search_fields(page, timeout_ms=1500)

        if not _search_fields_present(page):
            self._save_artifacts(debug_dir, "02-search-tab-not-loaded", page)
            _save_dom_diagnostics(debug_dir, "02-search-tab-diagnostics", page)
            if _env_bool("BUNDESARCHIV_INVENIO_MANUAL_TAB_FALLBACK", default=False):
                # In headed mode the user can click the Suche tab manually once.
                # This keeps the run usable while we stabilize the exact JSF AJAX
                # call for this PrimeFaces deployment. The wait is bounded and
                # checked every second.
                for _ in range(_env_int("BUNDESARCHIV_INVENIO_MANUAL_TAB_WAIT_SECONDS", default=5)):
                    if _search_fields_present(page):
                        break
                    try:
                        page.wait_for_timeout(1000)
                    except Exception:  # noqa: BLE001
                        break
                self._save_artifacts(debug_dir, "02b-after-manual-tab-wait", page)
                _save_dom_diagnostics(debug_dir, "02b-after-manual-tab-wait-diagnostics", page)

        target_labels = ["Erweiterte Suche"] if _attempt_uses_advanced_search(attempt) else ["Einfache Suche"]
        for label in target_labels:
            _click_first_text(page, [label], exact=False)
        _wait_networkidle_best_effort(page, timeout_ms=5000)
        _slow(self._slow_mo_ms, page)

        if not _search_fields_present(page):
            raise RuntimeError(
                "Scheda Suche non caricata: la sessione Ã¨ autenticata ma il corpo "
                "del tab di ricerca non viene caricato dall'automazione. Verificare "
                "02-search-tab-not-loaded.* e i file diagnostics JSON. In headed mode "
                "si puÃ² cliccare manualmente 'Suche' durante il breve fallback per "
                "acquisire il DOM reale della maschera."
            )

    def _fill_attempt_fields(self, page: Any, attempt: SearchAttempt) -> None:
        filled_count = 0
        missing_fields: list[str] = []
        for field_id, value in attempt.fields.items():
            if not value:
                continue
            html_name = FIELD_HTML_NAMES.get(field_id)
            if not html_name:
                continue
            filled = False
            if field_id in TEXT_FIELD_IDS:
                filled = _fill_text_field(page, html_name, value)
            elif field_id in CHECKBOX_FIELD_IDS:
                filled = _set_checkbox(page, html_name, _as_bool(value))
            elif field_id in RADIO_FIELD_IDS:
                filled = _set_radio(page, html_name, value)
            if filled:
                filled_count += 1
            else:
                missing_fields.append(field_id)

        if filled_count == 0 and attempt.fields:
            raise RuntimeError(
                "Nessun campo Invenio compilato. Campi mancanti: "
                + ", ".join(missing_fields or sorted(attempt.fields))
            )

    def _submit_search(self, page: Any, source: Source, *, debug_dir: Path | None = None) -> None:
        selectors = [
            'button:has-text("Suchen")',
            'button:has-text("Suche starten")',
            'input[type="submit"][value*="Suchen"]',
            'input[type="button"][value*="Suchen"]',
            'a:has-text("Suchen")',
        ]
        clicked = False
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.count() > 0 and locator.is_visible(timeout=1000):
                    locator.click(timeout=3000)
                    clicked = True
                    break
            except Exception:  # noqa: BLE001
                continue
        if not clicked:
            # Fallback: press Enter in the active form field.
            try:
                page.keyboard.press("Enter")
                clicked = True
            except Exception:  # noqa: BLE001
                pass
        if not clicked:
            raise RuntimeError("Pulsante Suchen non trovato nella UI Invenio.")

        _wait_after_search_submit(page, source=source, debug_dir=debug_dir)
        _slow(self._slow_mo_ms, page)

    def _extract_candidates(self, page: Any) -> list[InvenioCandidate]:
        html_text = page.content()
        page_url = str(page.url)

        # 1) Prefer the JSF/AJAX partial responses. In Invenio the authenticated
        # search often returns the meaningful Tektonik/Klassifikation tree nodes
        # in <partial-response> XML, while the visible DOM remains a generic shell
        # containing hidden login/help dialogs. Parsing AJAX first avoids false
        # blocked_or_dynamic classifications from irrelevant hidden page text.
        ajax_hits = _extract_candidates_from_recorded_ajax(page=page, base_url=page_url)
        if ajax_hits:
            return ajax_hits[:50]

        # 2) Then inspect every Playwright frame. The interactive Invenio UI is
        # rendered as a two-pane PrimeFaces layout and, depending on browser
        # state, the useful Tektonik/Klassifikation tree can live in a nested
        # frame/panel that is not visible from page.content().
        frame_hits = _extract_candidates_from_frames(page=page, base_url=page_url)
        if frame_hits:
            return frame_hits[:50]

        # 3) Then use direct/row candidates that are materialized in the main DOM.
        # This remains useful when a later Invenio step exposes a real result
        # table or direct archival links.
        candidates = _extract_direct_link_candidates(html_text=html_text, base_url=page_url)
        if candidates:
            return candidates[:50]

        rows = _extract_row_candidates(page=page, base_url=page_url)
        if rows:
            return rows[:50]

        # 3) Fallback to side-panel markers currently visible in the DOM.
        panel_hits = _extract_panel_hit_candidates(html_text=html_text, base_url=page_url)
        return panel_hits[:50]

    def _expand_full_tree_views(self, page: Any, *, debug_dir: Path | None) -> None:
        _expand_full_tree_views(page, debug_dir=debug_dir)

    def _debug_dir(self, attempt: SearchAttempt) -> Path:
        safe_attempt = re.sub(r"[^A-Za-z0-9_.-]+", "_", attempt.attempt_id or "attempt")[:80]
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        return self.repo_root / "data" / "debug" / "bundesarchiv_invenio" / f"{stamp}_{safe_attempt}"

    def _save_artifacts(self, debug_dir: Path | None, stem: str, page: Any) -> None:
        if debug_dir is None:
            return
        try:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{stem}.url.txt").write_text(str(page.url), encoding="utf-8")
            (debug_dir / f"{stem}.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(debug_dir / f"{stem}.png"), full_page=True)
            _save_frame_artifacts(debug_dir, stem, page)
        except Exception:  # noqa: BLE001 - debug artefacts must not break the run
            return






def _safe_frame_value(frame: Any, attr_name: str) -> str:
    try:
        value = getattr(frame, attr_name, "")
        if callable(value):
            value = value()
        return str(value or "")
    except Exception:  # noqa: BLE001
        return ""


def _frame_body_text(frame: Any, *, timeout_ms: int = 1000) -> str:
    try:
        return frame.locator("body").inner_text(timeout=timeout_ms)
    except Exception:  # noqa: BLE001
        try:
            return strip_tags(frame.content())
        except Exception:  # noqa: BLE001
            return ""


def _save_frame_artifacts(debug_dir: Path | None, stem: str, page: Any) -> None:
    """Persist all Playwright frame HTML/text for Invenio two-pane debugging.

    Manual navigation shows a left Tektonik pane and a right content/search pane.
    On JSF/PrimeFaces pages those panes can be represented as nested frames or
    dynamic layout fragments. page.content() alone is not enough to understand
    where results were rendered, so every page snapshot also stores a frame dump.
    """
    if debug_dir is None:
        return
    try:
        frames = list(getattr(page, "frames", []) or [])
    except Exception:  # noqa: BLE001
        frames = []
    if not frames:
        return

    frames_dir = debug_dir / f"{stem}-frames"
    metadata: list[dict[str, Any]] = []
    try:
        frames_dir.mkdir(parents=True, exist_ok=True)
    except Exception:  # noqa: BLE001
        return

    for index, frame in enumerate(frames):
        frame_id = f"frame-{index:02d}"
        frame_name = _safe_frame_value(frame, "name")
        frame_url = _safe_frame_value(frame, "url")
        try:
            frame_html = frame.content()
        except Exception as exc:  # noqa: BLE001
            frame_html = f"<!-- frame.content() failed: {type(exc).__name__}: {exc} -->"
        frame_text = _frame_body_text(frame)
        metadata.append({
            "index": index,
            "name": frame_name,
            "url": frame_url,
            "html_file": f"{stem}-frames/{frame_id}.html",
            "text_file": f"{stem}-frames/{frame_id}.txt",
            "text_start": frame_text[:2000],
            "contains_tektonik": "Tektonik" in frame_text or "tektonik" in frame_html,
            "contains_klassifikation": "Klassifikation" in frame_text or "klassifikation" in frame_html,
            "contains_suchergebnis": "Suchergebnis" in frame_text or "searchResult" in frame_html,
            "contains_ui_tree": "ui-tree" in frame_html or "ui-treenode" in frame_html,
        })
        try:
            (frames_dir / f"{frame_id}.html").write_text(frame_html, encoding="utf-8")
            (frames_dir / f"{frame_id}.txt").write_text(frame_text, encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        try:
            # Frame screenshots are best-effort; some frames have no body or are
            # cross-origin/zero-sized. Failures must not affect the source run.
            frame.locator("body").screenshot(path=str(frames_dir / f"{frame_id}.png"), timeout=1500)
        except Exception:  # noqa: BLE001
            pass

    try:
        (debug_dir / f"{stem}-frames.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001
        pass


def _extract_candidates_from_frames(*, page: Any, base_url: str) -> list[InvenioCandidate]:
    """Extract candidate references from all Playwright frames, not only main DOM."""
    try:
        frames = list(getattr(page, "frames", []) or [])
    except Exception:  # noqa: BLE001
        frames = []
    candidates: list[InvenioCandidate] = []

    for index, frame in enumerate(frames):
        frame_url = _safe_frame_value(frame, "url") or base_url
        try:
            frame_html = frame.content()
        except Exception:  # noqa: BLE001
            continue
        frame_base_url = frame_url if frame_url and frame_url != "about:blank" else base_url

        frame_candidates: list[InvenioCandidate] = []
        frame_candidates.extend(_extract_tree_node_candidates(
            html_text=frame_html,
            base_url=frame_base_url,
            response_index=index,
        ))
        frame_candidates.extend(_extract_panel_hit_candidates(
            html_text=frame_html,
            base_url=frame_base_url,
            response_index=index,
        ))
        frame_candidates.extend(_extract_direct_link_candidates(
            html_text=frame_html,
            base_url=frame_base_url,
        ))
        try:
            frame_candidates.extend(_extract_row_candidates(page=frame, base_url=frame_base_url))
        except Exception:  # noqa: BLE001
            pass

        for candidate in frame_candidates:
            snippet_prefix = f"Frame Invenio {index}"
            snippet = candidate.snippet or ""
            if snippet_prefix not in snippet:
                snippet = f"{snippet_prefix}. {snippet}".strip()
            candidates.append(InvenioCandidate(
                title=candidate.title,
                url=candidate.url,
                snippet=snippet,
                detail_html=candidate.detail_html or frame_html,
            ))

    return _deduplicate_invenio_candidates(candidates)


def _manual_capture_wait_if_enabled(page: Any, *, debug_dir: Path | None) -> None:
    """Keep the authenticated Invenio page open for manual navigation capture.

    This is a diagnostic-only mode used to learn the exact JSF/PrimeFaces events
    emitted when a human expands the Tektonik/Klassifikation result panels. The
    network recorder is already attached to the page, so every click performed
    during this wait is written to ``network-events.jsonl`` and every relevant
    JSF partial-response is saved as ``05-search-response-XX.xml``.

    Enable with:

        BUNDESARCHIV_INVENIO_MANUAL_CAPTURE=true
        BUNDESARCHIV_INVENIO_MANUAL_CAPTURE_SECONDS=120

    The function is intentionally best-effort: it must never break the report.
    """
    if not _env_bool("BUNDESARCHIV_INVENIO_MANUAL_CAPTURE", default=False):
        return

    seconds = max(1, _env_int("BUNDESARCHIV_INVENIO_MANUAL_CAPTURE_SECONDS", default=120))
    poll_seconds = max(1, _env_int("BUNDESARCHIV_INVENIO_MANUAL_CAPTURE_SNAPSHOT_SECONDS", default=10))
    started = time.perf_counter()
    deadline = started + seconds

    instructions = (
        "Manual capture mode enabled for Bundesarchiv Invenio.\n"
        "During this window, use the opened browser manually:\n"
        "1. wait for the submitted search to settle;\n"
        "2. expand the first Tektonik branch that shows Treffer;\n"
        "3. expand the first Klassifikation branch with Treffer, if present;\n"
        "4. click the first concrete archival record/document if it appears;\n"
        "5. do not close the browser; let the script resume after the timeout.\n"
    )
    if debug_dir is not None:
        try:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / "MANUAL_CAPTURE_INSTRUCTIONS.txt").write_text(instructions, encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    try:
        # Make the capture state visible in the browser window without relying
        # on console logs. The banner is injected only into the local DOM.
        page.evaluate(
            """([seconds]) => {
              const existing = document.getElementById('invenio-manual-capture-banner');
              if (existing) existing.remove();
              const banner = document.createElement('div');
              banner.id = 'invenio-manual-capture-banner';
              banner.textContent = 'Manual capture attiva: espandi Tektonik/Klassifikation e clicca un record. Timeout ' + seconds + 's.';
              banner.style.cssText = 'position:fixed;z-index:2147483647;left:12px;right:12px;bottom:12px;padding:12px 16px;background:#fff3cd;border:2px solid #d39e00;color:#2b2b2b;font:14px Arial,sans-serif;box-shadow:0 2px 10px rgba(0,0,0,.25);';
              document.body.appendChild(banner);
            }""",
            [seconds],
        )
    except Exception:  # noqa: BLE001
        pass

    _save_page_artifacts(debug_dir, "06-manual-capture-start", page)
    _save_dom_diagnostics(debug_dir, "06-manual-capture-start-diagnostics", page)

    next_snapshot = started + poll_seconds
    snapshot_index = 1
    while time.perf_counter() < deadline:
        remaining_ms = int(max(0.1, min(1000, (deadline - time.perf_counter()) * 1000)))
        try:
            page.wait_for_timeout(remaining_ms)
        except Exception:  # noqa: BLE001
            break
        now = time.perf_counter()
        if now >= next_snapshot:
            stem = f"06-manual-capture-snapshot-{snapshot_index:02d}"
            _save_page_artifacts(debug_dir, stem, page)
            _save_dom_diagnostics(debug_dir, f"{stem}-diagnostics", page)
            snapshot_index += 1
            next_snapshot = now + poll_seconds

    try:
        page.evaluate("""() => { const b = document.getElementById('invenio-manual-capture-banner'); if (b) b.remove(); }""")
    except Exception:  # noqa: BLE001
        pass

    _save_page_artifacts(debug_dir, "06-manual-capture-end", page)
    _save_dom_diagnostics(debug_dir, "06-manual-capture-end-diagnostics", page)



def _wait_after_search_submit(page: Any, *, source: Source, debug_dir: Path | None) -> None:
    """Wait for Invenio's post-submit state and open the result tab.

    Invenio's ``Suchen`` button performs a PrimeFaces/JSF AJAX post and may then
    trigger one or more document reloads. A plain ``networkidle`` can capture the
    application back on the navigation/search tab while the result tab is still
    lazy-loaded or disabled in the DOM. This helper keeps the wait bounded, saves
    intermediate artefacts, and explicitly activates ``Suchergebnis`` after the
    submit has settled.
    """
    timeout_ms = _env_int("BUNDESARCHIV_INVENIO_RESULT_WAIT_MS", default=15000)
    deadline = time.perf_counter() + (timeout_ms / 1000)

    # Let AJAX/document reloads finish without allowing a single search to block
    # a whole report for minutes.
    _wait_networkidle_best_effort(page, timeout_ms=min(timeout_ms, max(3000, source.timeout * 1000)))
    while time.perf_counter() < deadline:
        if _result_markers_present(page):
            break
        if not _search_loading_visible(page):
            # Give PrimeFaces one extra rendering cycle after the loader becomes hidden.
            try:
                page.wait_for_timeout(600)
            except Exception:  # noqa: BLE001
                pass
            break
        try:
            page.wait_for_timeout(500)
        except Exception:  # noqa: BLE001
            break

    _save_page_artifacts(debug_dir, "04a-after-submit-settled", page)
    _save_dom_diagnostics(debug_dir, "04a-after-submit-settled-diagnostics", page)

    # The outer result tab is lazy and usually disabled until after a successful
    # search. Try to activate it explicitly; if it remains unavailable, we still
    # keep the settled HTML for diagnostics/no-result interpretation.
    if not _result_content_present(page):
        _activate_top_level_tab_with_exact_ajax(
            page,
            tab_index=2,
            tab_client_id="masterLayoutForm:tabPanel:searchResultTab",
            debug_dir=debug_dir,
            stem="04b-result-tab",
        )
        _wait_for_result_content(page, timeout_ms=6000)

    _save_page_artifacts(debug_dir, "04b-result-tab", page)
    _save_dom_diagnostics(debug_dir, "04b-result-tab-diagnostics", page)


def _activate_top_level_tab_with_exact_ajax(
    page: Any,
    *,
    tab_index: int,
    tab_client_id: str,
    debug_dir: Path | None = None,
    stem: str = "tabchange",
) -> bool:
    """Trigger a top-level PrimeFaces tabChange for the Invenio outer tabPanel."""
    script = """
    async ([tabIndex, tabClientId]) => {
      const hasResultContent = () => {
        const text = (document.body && document.body.innerText || '');
        return !!document.querySelector('[id*=\"searchResultTab\"] tbody tr, [id*=\"searchResultTab\"] .ui-datatable, [id*=\"searchResultTab\"] table')
          || /Suchergebnis|Treffer|Keine Treffer|Keine Suchergebnisse/i.test(text);
      };
      const setActiveHeader = () => {
        const tabPanel = document.getElementById('masterLayoutForm:tabPanel');
        const links = Array.from((tabPanel || document).querySelectorAll('a[href]')).filter(a => {
          const href = a.getAttribute('href') || '';
          return href.includes('masterLayoutForm:tabPanel:') || (tabPanel && tabPanel.contains(a));
        });
        links.forEach((a, idx) => {
          const li = a.closest('li');
          if (!li) return;
          const active = (a.getAttribute('href') === '#' + tabClientId) || idx === tabIndex;
          li.classList.toggle('ui-tabs-selected', active);
          li.classList.toggle('ui-state-active', active);
          li.classList.toggle('ui-state-disabled', false);
          li.setAttribute('aria-selected', active ? 'true' : 'false');
          li.setAttribute('aria-expanded', active ? 'true' : 'false');
          if (active) li.removeAttribute('tabindex');
        });
        location.hash = tabClientId;
      };
      setActiveHeader();
      const params = [
        {name: 'javax.faces.behavior.event', value: 'tabChange'},
        {name: 'javax.faces.partial.event', value: 'tabChange'},
        {name: 'masterLayoutForm:tabPanel_newTab', value: tabClientId},
        {name: 'masterLayoutForm:tabPanel_tabindex', value: String(tabIndex)},
        {name: 'masterLayoutForm:tabPanel_activeIndex', value: String(tabIndex)},
        {name: 'masterLayoutForm:tabPanel_contentLoad', value: 'true'}
      ];
      if (!window.PrimeFaces || !PrimeFaces.ab) return {invoked: false, reason: 'PrimeFaces.ab missing', hasResultContent: hasResultContent()};
      return await new Promise(resolve => {
        let settled = false;
        const done = (reason) => {
          if (settled) return;
          settled = true;
          setTimeout(() => resolve({invoked: true, reason, hasResultContent: hasResultContent(), bodyStart: (document.body && document.body.innerText || '').slice(0, 800)}), 450);
        };
        setTimeout(() => done('timeout'), 6000);
        try {
          PrimeFaces.ab({
            s: 'masterLayoutForm:j_idt285',
            f: 'masterLayoutForm',
            p: 'masterLayoutForm',
            u: 'masterLayoutForm:tabPanel',
            e: 'tabChange',
            pa: params,
            onco: function() { done('onco'); },
            oncomplete: function() { done('oncomplete'); },
            onerror: function() { done('onerror'); }
          });
        } catch (e) {
          resolve({invoked: false, reason: String(e), hasResultContent: hasResultContent()});
        }
      });
    }
    """
    try:
        result = page.evaluate(script, [tab_index, tab_client_id])
        if debug_dir is not None:
            import json
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{stem}-tabchange-result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        _wait_networkidle_best_effort(page, timeout_ms=5000)
        try:
            page.wait_for_timeout(600)
        except Exception:  # noqa: BLE001
            pass
        return _result_content_present(page)
    except Exception as exc:  # noqa: BLE001
        if debug_dir is not None:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{stem}-tabchange-error.txt").write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        return False


def _wait_for_result_content(page: Any, *, timeout_ms: int) -> bool:
    deadline = time.perf_counter() + (timeout_ms / 1000)
    while time.perf_counter() < deadline:
        if _result_content_present(page):
            return True
        try:
            page.wait_for_timeout(300)
        except Exception:  # noqa: BLE001
            break
    return _result_content_present(page)


def _result_markers_present(page: Any) -> bool:
    text = _safe_body_text(page)
    return _contains_any(
        text,
        (
            "Suchergebnis",
            "Treffer",
            "Treffer in der Tektonik",
            "Treffer in der Klassifikation",
            "Keine Treffer",
            "Keine Suchergebnisse",
        ),
    ) or _result_content_present(page)


def _result_content_present(page: Any) -> bool:
    selectors = [
        'div[id*="searchResultTab"] tbody tr',
        'div[id*="searchResultTab"] .ui-datatable',
        'div[id*="searchResultTab"] table',
        'tbody.ui-datatable-data > tr',
        '.ui-datatable tbody > tr',
    ]
    for selector in selectors:
        try:
            if page.locator(selector).count() > 0:
                return True
        except Exception:  # noqa: BLE001
            continue
    return _contains_any(
        _safe_body_text(page),
        (
            "Suchergebnis",
            "Treffer in der Tektonik",
            "Treffer in der Klassifikation",
            "Keine Treffer",
            "Keine Suchergebnisse",
            "0 Treffer",
        ),
    )


def _search_loading_visible(page: Any) -> bool:
    script = """() => {
      const candidates = Array.from(document.querySelectorAll('[id*=\"searchLoading\"], .ui-dialog, .ui-widget-overlay'));
      return candidates.some(el => {
        const id = el.id || '';
        const text = (el.innerText || '').trim();
        const style = window.getComputedStyle(el);
        const visible = style && style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || '1') !== 0;
        const hasBox = !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
        return visible && hasBox && (id.includes('searchLoading') || text === 'Abbrechen');
      });
    }"""
    try:
        return bool(page.evaluate(script))
    except Exception:  # noqa: BLE001
        return False


def _save_page_artifacts(debug_dir: Path | None, stem: str, page: Any) -> None:
    if debug_dir is None:
        return
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / f"{stem}.url.txt").write_text(str(page.url), encoding="utf-8")
        (debug_dir / f"{stem}.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(debug_dir / f"{stem}.png"), full_page=True)
    except Exception:  # noqa: BLE001
        return

def _install_network_recorder(page: Any, debug_dir: Path | None) -> None:
    try:
        # Keep in-memory copies of relevant JSF partial responses. The DOM may
        # not retain those updates, while the response body is the most reliable
        # evidence of whether Invenio found Treffer in Tektonik/Klassifikation.
        if not hasattr(page, "_invenio_partial_responses"):
            page._invenio_partial_responses = []
        # Also remember the debug directory so extraction can fall back to the
        # persisted 05-search-response-*.xml files. This is important because
        # Playwright response handlers can be timing-sensitive on JSF pages.
        if debug_dir is not None:
            page._invenio_debug_dir = str(debug_dir)
    except Exception:
        pass

    if debug_dir is None:
        return
    try:
        import json

        debug_dir.mkdir(parents=True, exist_ok=True)
        path = debug_dir / "network-events.jsonl"
        response_counter = {"value": 0}

        def write_event(event: dict[str, Any]) -> None:
            try:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            except Exception:
                pass

        def on_request(request: Any) -> None:
            try:
                if request.resource_type not in {"xhr", "fetch", "document"} and request.method.upper() != "POST":
                    return
                post_data = request.post_data or ""
                write_event({
                    "type": "request",
                    "method": request.method,
                    "url": request.url,
                    "resource_type": request.resource_type,
                    "is_search_submit": "searchDoSearch" in post_data,
                    "post_data_start": post_data[:12000],
                })
            except Exception:
                pass

        def on_response(response: Any) -> None:
            try:
                request = response.request
                if request.resource_type not in {"xhr", "fetch", "document"} and request.method.upper() != "POST":
                    return
                body_start = ""
                content_type = (response.headers or {}).get("content-type", "")
                post_data = request.post_data or ""
                is_search_submit = "searchDoSearch" in post_data
                if "xml" in content_type or "text" in content_type or "html" in content_type:
                    try:
                        body_start = response.text()[:250000]
                    except Exception:
                        body_start = ""

                is_candidate_partial = (
                    "<partial-response" in body_start
                    and (
                        is_search_submit
                        or "Treffer" in body_start
                        or "ui-tree" in body_start
                        or "ui-treenode" in body_start
                        or "masterLayoutForm:j_idt159" in body_start
                        or "masterLayoutForm:j_idt224" in body_start
                        or "tabSearchResultDetailPanel" in body_start
                    )
                )
                if is_candidate_partial:
                    try:
                        page._invenio_partial_responses.append(body_start)
                    except Exception:
                        pass
                    response_counter["value"] += 1
                    try:
                        (debug_dir / f"05-search-response-{response_counter['value']:02d}.xml").write_text(
                            body_start,
                            encoding="utf-8",
                        )
                    except Exception:
                        pass

                write_event({
                    "type": "response",
                    "method": request.method,
                    "url": response.url,
                    "status": response.status,
                    "content_type": content_type,
                    "is_search_submit": is_search_submit,
                    "is_candidate_partial": is_candidate_partial,
                    "body_start": body_start[:60000],
                })
            except Exception:
                pass

        page.on("request", on_request)
        page.on("response", on_response)
    except Exception:
        return

def _search_fields_present(page: Any) -> bool:
    selectors = [
        'input[name="masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchEinfach:searchStrings"]',
        'input[id="masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchEinfach:searchStrings"]',
        'input[name="masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:searchStrings"]',
        'input[id="masterLayoutForm:tabPanel:tabSearch:searchTabPanel:tabSearchAllgemein:searchStrings"]',
        'input[id*="tabSearchEinfach"][id*="searchStrings"]',
        'input[id*="tabSearchAllgemein"][id*="searchStrings"]',
    ]
    for selector in selectors:
        try:
            if page.locator(selector).count() > 0:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _expand_full_tree_views(page: Any, *, debug_dir: Path | None) -> None:
    """Best-effort expansion of Invenio Tektonik/Klassifikation side trees.

    The search itself is already useful when it yields tree-node candidates.
    Step 28 needs a deeper artefact: the full tree response after activating
    "vollstaendig anzeigen" controls. The exact JSF ids are unstable, so this
    helper uses visible text normalized in the browser and persists whatever
    new partial responses are captured by the network recorder.
    """
    for tree_kind in ("tektonik", "klassifikation"):
        stem = f"06-full-{tree_kind}"
        start_index = _invenio_partial_response_count(page)
        result = _click_full_tree_control(page, tree_kind=tree_kind)
        _write_debug_json(debug_dir, f"{stem}-click-result.json", result)
        if not result.get("clicked"):
            continue
        _wait_networkidle_best_effort(page, timeout_ms=6000)
        try:
            page.wait_for_timeout(900)
        except Exception:  # noqa: BLE001
            pass
        _save_page_artifacts(debug_dir, f"{stem}-after", page)
        _save_dom_diagnostics(debug_dir, f"{stem}-after-diagnostics", page)
        _persist_new_invenio_partial_responses(
            page,
            debug_dir=debug_dir,
            stem=f"{stem}-response",
            start_index=start_index,
        )


def _click_full_tree_control(page: Any, *, tree_kind: str) -> dict[str, Any]:
    script = """
    ([treeKind]) => {
      const normalize = (value) => (value || '')
        .normalize('NFD')
        .replace(/[\\u0300-\\u036f]/g, '')
        .replace(/\\s+/g, ' ')
        .trim()
        .toLowerCase();
      const wanted = `${treeKind} vollstandig anzeigen`;
      const genericWanted = 'vollstandig anzeigen';
      const elements = Array.from(document.querySelectorAll('button, a, span, div[role="button"], input[type="button"], input[type="submit"]'));
      for (const element of elements) {
        const text = normalize(element.innerText || element.textContent || element.value || element.title || element.getAttribute('aria-label') || '');
        if (!text) continue;
        const nearTree = text.includes(treeKind) || normalize((element.closest('[id*="' + treeKind + '"], [id*="klassif"], [id*="tektonik"]') || {}).id || '').includes(treeKind);
        if (text.includes(wanted) || (text.includes(genericWanted) && nearTree)) {
          element.click();
          return {clicked: true, tree_kind: treeKind, text, id: element.id || '', tag: element.tagName || ''};
        }
      }
      return {clicked: false, tree_kind: treeKind, reason: 'full tree control not found'};
    }
    """
    try:
        result = page.evaluate(script, [tree_kind])
        return result if isinstance(result, dict) else {"clicked": False, "tree_kind": tree_kind, "result": str(result)}
    except Exception as exc:  # noqa: BLE001
        return {"clicked": False, "tree_kind": tree_kind, "error": f"{type(exc).__name__}: {exc}"}


def _invenio_partial_response_count(page: Any) -> int:
    try:
        return len(list(getattr(page, "_invenio_partial_responses", []) or []))
    except Exception:
        return 0


def _persist_new_invenio_partial_responses(page: Any, *, debug_dir: Path | None, stem: str, start_index: int) -> None:
    if debug_dir is None:
        return
    try:
        responses = list(getattr(page, "_invenio_partial_responses", []) or [])
    except Exception:
        responses = []
    new_responses = [body for body in responses[start_index:] if isinstance(body, str) and body.strip()]
    if not new_responses:
        return
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        for index, body in enumerate(new_responses, start=1):
            (debug_dir / f"{stem}-{index:02d}.xml").write_text(body, encoding="utf-8")
    except Exception:
        pass


def _write_debug_json(debug_dir: Path | None, filename: str, payload: Any) -> None:
    if debug_dir is None:
        return
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _wait_for_search_fields(page: Any, *, timeout_ms: int) -> bool:
    deadline = time.perf_counter() + (timeout_ms / 1000)
    while time.perf_counter() < deadline:
        if _search_fields_present(page):
            return True
        try:
            page.wait_for_timeout(250)
        except Exception:  # noqa: BLE001
            break
    return _search_fields_present(page)


def _click_primefaces_tab(page: Any, *, tab_label: str, tab_index: int, tab_client_id: str) -> bool:
    selectors = [
        f'li[role="tab"]:has-text("{tab_label}")',
        f'a[href="#{tab_client_id}"]',
        f'a:has-text("{tab_label}")',
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.click(timeout=5000, force=True)
                _wait_networkidle_best_effort(page, timeout_ms=5000)
                page.wait_for_timeout(1000)
                if _search_fields_present(page):
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False



def _activate_primefaces_tab_with_exact_ajax(
    page: Any,
    *,
    tab_index: int,
    tab_client_id: str,
    debug_dir: Path | None = None,
) -> bool:
    """Trigger the lazy PrimeFaces tab body with the explicit JSF tabChange payload.

    The authenticated Invenio page exposes only the tab headers. The script in
    the page defines ``onTabChangeProcess`` as a PrimeFaces.ajax wrapper whose
    source is ``masterLayoutForm:j_idt285``. A plain click only changes the URL
    hash; this function sends the tabChange parameters expected by JSF/PrimeFaces.
    """
    script = """
    async ([tabIndex, tabClientId]) => {
      const hasFields = () => !!document.querySelector(
        'input[id*=\"tabSearchEinfach\"][id*=\"searchStrings\"], input[name*=\"tabSearchEinfach\"][name*=\"searchStrings\"], input[id*=\"tabSearchAllgemein\"][id*=\"searchStrings\"], input[name*=\"tabSearchAllgemein\"][name*=\"searchStrings\"]'
      );
      const params = [
        {name: 'javax.faces.behavior.event', value: 'tabChange'},
        {name: 'javax.faces.partial.event', value: 'tabChange'},
        {name: 'masterLayoutForm:tabPanel_newTab', value: tabClientId},
        {name: 'masterLayoutForm:tabPanel_tabindex', value: String(tabIndex)},
        {name: 'masterLayoutForm:tabPanel_activeIndex', value: String(tabIndex)},
        {name: 'masterLayoutForm:tabPanel_contentLoad', value: 'true'}
      ];
      const setActiveHeader = () => {
        const tabPanel = document.getElementById('masterLayoutForm:tabPanel');
        const links = Array.from((tabPanel || document).querySelectorAll('a[href]')).filter(a => {
          const href = a.getAttribute('href') || '';
          return href.includes('masterLayoutForm:tabPanel:') || (tabPanel && tabPanel.contains(a));
        });
        links.forEach((a, idx) => {
          const li = a.closest('li');
          if (!li) return;
          const active = (a.getAttribute('href') === '#' + tabClientId) || idx === tabIndex;
          li.classList.toggle('ui-tabs-selected', active);
          li.classList.toggle('ui-state-active', active);
          li.setAttribute('aria-selected', active ? 'true' : 'false');
          li.setAttribute('aria-expanded', active ? 'true' : 'false');
        });
        location.hash = tabClientId;
      };
      setActiveHeader();
      if (!window.PrimeFaces || !PrimeFaces.ab) return {invoked: false, reason: 'PrimeFaces.ab missing', hasFields: hasFields()};
      return await new Promise(resolve => {
        let settled = false;
        const done = (reason) => {
          if (settled) return;
          settled = true;
          setTimeout(() => resolve({invoked: true, reason, hasFields: hasFields(), bodyStart: (document.body && document.body.innerText || '').slice(0, 500)}), 350);
        };
        setTimeout(() => done('timeout'), 8000);
        try {
          PrimeFaces.ab({
            s: 'masterLayoutForm:j_idt285',
            f: 'masterLayoutForm',
            p: 'masterLayoutForm',
            u: 'masterLayoutForm:tabPanel',
            e: 'tabChange',
            pa: params,
            onco: function() { done('onco'); },
            oncomplete: function() { done('oncomplete'); },
            onerror: function() { done('onerror'); }
          });
        } catch (e) {
          resolve({invoked: false, reason: String(e), hasFields: hasFields()});
        }
      });
    }
    """
    try:
        result = page.evaluate(script, [tab_index, tab_client_id])
        if debug_dir is not None:
            import json
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / "02a-exact-primefaces-tabchange-result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        _wait_networkidle_best_effort(page, timeout_ms=5000)
        page.wait_for_timeout(750)
        _save_dom_diagnostics(debug_dir, "02a-after-exact-primefaces-tabchange-diagnostics", page)
        return _search_fields_present(page)
    except Exception as exc:  # noqa: BLE001
        if debug_dir is not None:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / "02a-exact-primefaces-tabchange-error.txt").write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        return False


def _activate_jsf_ajax_tab_request(
    page: Any,
    *,
    tab_index: int,
    tab_client_id: str,
    debug_dir: Path | None = None,
) -> bool:
    """Fallback using the native jsf.ajax.request API with tabChange options."""
    script = """
    async ([tabIndex, tabClientId]) => {
      const hasFields = () => !!document.querySelector(
        'input[id*=\"tabSearchEinfach\"][id*=\"searchStrings\"], input[name*=\"tabSearchEinfach\"][name*=\"searchStrings\"], input[id*=\"tabSearchAllgemein\"][id*=\"searchStrings\"], input[name*=\"tabSearchAllgemein\"][name*=\"searchStrings\"]'
      );
      const source = document.getElementById('masterLayoutForm:j_idt285') || document.querySelector('script[id$=\":j_idt285\"]');
      if (!window.jsf || !jsf.ajax || !source) return {invoked: false, reason: 'jsf.ajax/source missing', hasFields: hasFields()};
      return await new Promise(resolve => {
        let settled = false;
        const finish = (reason, data) => {
          if (settled) return;
          settled = true;
          setTimeout(() => resolve({invoked: true, reason, status: data && data.status, hasFields: hasFields()}), 350);
        };
        setTimeout(() => finish('timeout'), 8000);
        try {
          jsf.ajax.request(source, null, {
            execute: 'masterLayoutForm',
            render: 'masterLayoutForm:tabPanel',
            onevent: function(data) { if (data && data.status === 'success') finish('success', data); },
            onerror: function(data) { finish('error', data); },
            'javax.faces.behavior.event': 'tabChange',
            'javax.faces.partial.event': 'tabChange',
            'masterLayoutForm:tabPanel_newTab': tabClientId,
            'masterLayoutForm:tabPanel_tabindex': String(tabIndex),
            'masterLayoutForm:tabPanel_activeIndex': String(tabIndex),
            'masterLayoutForm:tabPanel_contentLoad': 'true'
          });
        } catch (e) {
          resolve({invoked: false, reason: String(e), hasFields: hasFields()});
        }
      });
    }
    """
    try:
        result = page.evaluate(script, [tab_index, tab_client_id])
        if debug_dir is not None:
            import json
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / "02c-jsf-ajax-tabchange-result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        _wait_networkidle_best_effort(page, timeout_ms=5000)
        page.wait_for_timeout(750)
        _save_dom_diagnostics(debug_dir, "02c-after-jsf-ajax-tabchange-diagnostics", page)
        return _search_fields_present(page)
    except Exception as exc:  # noqa: BLE001
        if debug_dir is not None:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / "02c-jsf-ajax-tabchange-error.txt").write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        return False

def _activate_primefaces_tab_with_ajax(page: Any, *, tab_index: int, tab_client_id: str) -> bool:
    # PrimeFaces 6 tab change normally triggers a JSF AJAX request. The exact
    # handler differs across deployments, so send the common PrimeFaces params
    # and then wait for the partial update to inject the tab body.
    script = """
    ([tabIndex, tabClientId]) => {
      const form = document.getElementById('masterLayoutForm');
      if (!form || !window.PrimeFaces || !PrimeFaces.ab) return false;
      const params = [
        {name: 'masterLayoutForm:tabPanel_activeIndex', value: String(tabIndex)},
        {name: 'masterLayoutForm:tabPanel_tabindex', value: String(tabIndex)},
        {name: 'masterLayoutForm:tabPanel_newTab', value: tabClientId},
        {name: 'masterLayoutForm:tabPanel_contentLoad', value: 'true'}
      ];
      try {
        if (typeof window.onTabChangeProcess === 'function') {
          window.onTabChangeProcess(params);
          return true;
        }
      } catch (e) {}
      try {
        PrimeFaces.ab({
          s: 'masterLayoutForm:j_idt285',
          f: 'masterLayoutForm',
          p: 'masterLayoutForm',
          u: 'masterLayoutForm:tabPanel',
          pa: params
        });
        return true;
      } catch (e) {
        return false;
      }
    }
    """
    try:
        invoked = bool(page.evaluate(script, [tab_index, tab_client_id]))
        _wait_networkidle_best_effort(page, timeout_ms=8000)
        page.wait_for_timeout(1500)
        return invoked and _search_fields_present(page)
    except Exception:  # noqa: BLE001
        return False


def _activate_primefaces_tab_with_jquery(page: Any, *, tab_index: int, tab_client_id: str) -> bool:
    script = """
    ([tabIndex, tabClientId]) => {
      const panel = document.getElementById('masterLayoutForm:tabPanel');
      const link = document.querySelector('a[href="#' + tabClientId + '"]');
      if (link) {
        ['mousedown', 'mouseup', 'click'].forEach(type =>
          link.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}))
        );
      }
      try {
        if (window.jQuery && panel && jQuery(panel).tabs) {
          jQuery(panel).tabs('option', 'active', Number(tabIndex));
          jQuery(panel).tabs('load', Number(tabIndex));
          return true;
        }
      } catch (e) {}
      return !!link;
    }
    """
    try:
        invoked = bool(page.evaluate(script, [tab_index, tab_client_id]))
        _wait_networkidle_best_effort(page, timeout_ms=8000)
        page.wait_for_timeout(1500)
        return invoked and _search_fields_present(page)
    except Exception:  # noqa: BLE001
        return False


def _save_dom_diagnostics(debug_dir: Path | None, stem: str, page: Any) -> None:
    if debug_dir is None:
        return
    try:
        import json

        data = page.evaluate(
            """() => {
              const attrs = el => {
                const out = {};
                if (!el || !el.attributes) return out;
                for (const a of el.attributes) out[a.name] = a.value;
                return out;
              };
              return {
                url: location.href,
                title: document.title,
                bodyTextStart: (document.body && document.body.innerText || '').slice(0, 3000),
                forms: Array.from(document.forms).map(f => ({id: f.id, name: f.name, action: f.action, method: f.method})),
                inputs: Array.from(document.querySelectorAll('input, textarea, select')).map(e => ({
                  tag: e.tagName, id: e.id, name: e.name, type: e.type, value: (e.value || '').slice(0, 120), visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
                })),
                anchors: Array.from(document.querySelectorAll('a')).map(a => ({
                  text: (a.innerText || '').trim().slice(0, 160), href: a.getAttribute('href'), attrs: attrs(a)
                })),
                scriptsWithPrimeFaces: Array.from(document.scripts).map(s => s.textContent || '').filter(t => t.includes('PrimeFaces') || t.includes('onTabChangeProcess')).map(t => t.slice(0, 2000)),
                tabPanelOuterHTML: (document.getElementById('masterLayoutForm:tabPanel') || {}).outerHTML || ''
              };
            }"""
        )
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / f"{stem}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001 - diagnostics must not break the run
        return

def _attempt_uses_advanced_search(attempt: SearchAttempt) -> bool:
    return any(field_id.startswith("advanced_") for field_id in attempt.fields)


def _looks_authenticated(page: Any) -> bool:
    text = _safe_body_text(page)
    lowered = text.casefold()
    logged_out = any(marker.casefold() in lowered for marker in ("Benutzerkennung", "Passwort", "Zur Registrierung"))
    logged_in = any(marker.casefold() in lowered for marker in ("Abmelden", "Benutzung", "Erweiterte Suche", "Suchergebnis"))
    return logged_in and not logged_out


def _click_first_text(page: Any, labels: list[str], *, exact: bool) -> bool:
    for label in labels:
        try:
            locator = page.get_by_text(label, exact=exact).first
            if locator.count() > 0 and locator.is_visible(timeout=1000):
                locator.click(timeout=3000)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _fill_text_field(page: Any, html_name: str, value: str) -> bool:
    selectors = [
        f'input[name="{_css_attr_escape(html_name)}"]',
        f'textarea[name="{_css_attr_escape(html_name)}"]',
        f'input[id="{_css_attr_escape(html_name)}"]',
        f'textarea[id="{_css_attr_escape(html_name)}"]',
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.fill(value, timeout=3000)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _set_checkbox(page: Any, html_name: str, checked: bool) -> bool:
    selectors = [
        f'input[name="{_css_attr_escape(html_name)}"]',
        f'input[id="{_css_attr_escape(html_name)}"]',
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0:
                if checked:
                    locator.check(timeout=3000, force=True)
                else:
                    locator.uncheck(timeout=3000, force=True)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _set_radio(page: Any, html_name: str, value: str) -> bool:
    candidates = [
        f'input[name="{_css_attr_escape(html_name)}"][value="{_css_attr_escape(value)}"]',
        f'input[id="{_css_attr_escape(html_name)}:{_css_attr_escape(value)}"]',
        f'input[id*="{_css_attr_escape(html_name)}"][value="{_css_attr_escape(value)}"]',
    ]
    for selector in candidates:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.check(timeout=3000, force=True)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _extract_direct_link_candidates(*, html_text: str, base_url: str) -> list[InvenioCandidate]:
    anchors = re.findall(r"<a\s(?P<attrs>[^>]*href=(['\"])(?P<href>.*?)\2[^>]*)>(?P<body>.*?)</a>", html_text, flags=re.I | re.S)
    candidates: list[InvenioCandidate] = []
    seen: set[str] = set()
    for attrs, _, href, body in anchors:
        raw_title = strip_tags(body).strip()
        attrs_map = _parse_attrs(attrs)
        title = raw_title or attrs_map.get("title", "") or attrs_map.get("aria-label", "")
        absolute = urllib.parse.urljoin(base_url, html.unescape(href))
        lowered_url = absolute.casefold()
        lowered_title = title.casefold()
        is_direct = "/invenio/direktlink/" in lowered_url or "direktlink" in lowered_url or "direktlink" in lowered_title
        if not is_direct:
            continue
        if not _is_candidate_url_title(absolute, title):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        candidates.append(InvenioCandidate(title=title or absolute, url=absolute, snippet="Direktlink Bundesarchiv Invenio", detail_html=html_text))
    return candidates


def _extract_row_candidates(*, page: Any, base_url: str) -> list[InvenioCandidate]:
    row_selectors = [
        'div[id*="searchResultTab"] tbody.ui-datatable-data > tr',
        'tbody.ui-datatable-data > tr',
        '.ui-datatable tbody > tr',
        'table tbody > tr',
    ]
    candidates: list[InvenioCandidate] = []
    seen_titles: set[str] = set()
    for selector in row_selectors:
        try:
            rows = page.locator(selector)
            count = min(rows.count(), 50)
        except Exception:  # noqa: BLE001
            continue
        for index in range(count):
            try:
                row = rows.nth(index)
                text = " ".join(row.inner_text(timeout=1000).split())
                if not _is_candidate_row_text(text):
                    continue
                row_html = row.evaluate("element => element.outerHTML")
                url = _first_candidate_href_from_html(row_html, base_url) or f"{base_url}#invenio-row-{index + 1}"
                title = _title_from_row_text(text)
                title_key = title.casefold()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)
                candidates.append(InvenioCandidate(title=title, url=url, snippet=text[:500], detail_html=row_html))
            except Exception:  # noqa: BLE001
                continue
        if candidates:
            break
    return candidates


def _first_candidate_href_from_html(row_html: str, base_url: str) -> str:
    anchors = re.findall(r"<a\s[^>]*href=(['\"])(.*?)\1[^>]*>(.*?)</a>", row_html, flags=re.I | re.S)
    for _, href, body in anchors:
        absolute = urllib.parse.urljoin(base_url, html.unescape(href))
        title = strip_tags(body).strip()
        if _is_candidate_url_title(absolute, title):
            return absolute
    return ""


def _is_candidate_url_title(url: str, title: str) -> bool:
    lowered_url = url.casefold()
    lowered_title = title.casefold().strip()
    if not url or lowered_url.startswith("javascript:") or lowered_url.endswith("#"):
        return False
    if any(marker in lowered_url for marker in SERVICE_URL_MARKERS):
        return False
    if any(marker in lowered_title for marker in SERVICE_TITLE_MARKERS):
        return False
    return True


def _is_candidate_row_text(text: str) -> bool:
    if len(text) < 12:
        return False
    lowered = text.casefold()
    if any(marker in lowered for marker in ("keine treffer", "keine suchergebnisse", "anmelden", "passwort")):
        return False
    # Prefer rows that look archival: signatures, dates, titles, Bestand/Klassifikation, etc.
    return bool(
        re.search(r"\b(BArch|R\s*\d+|NS\s*\d+|RW\s*\d+|[A-ZÃ„Ã–Ãœ]{1,4}\s*\d+[\-/])", text)
        or re.search(r"\b(18|19|20)\d{2}\b", text)
        or any(marker in lowered for marker in ("signatur", "bestand", "klassifikation", "laufzeit", "titel"))
    )


def _title_from_row_text(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= 180:
        return cleaned
    return cleaned[:177].rstrip() + "..."





def _extract_candidates_from_recorded_ajax(*, page: Any, base_url: str) -> list[InvenioCandidate]:
    """Extract stabilized Invenio candidates from JSF partial-response bodies.

    The authenticated Invenio search often returns useful Tektonik/
    Klassifikation state in JSF partial-response XML while the final DOM remains
    unstable. Stabilize those intermediate references so the normal report can
    show ``candidate_results`` instead of ``blocked_or_dynamic``. Tree nodes are
    preferred over generic ``Treffer`` side panels; both are deduplicated by
    semantic key rather than by volatile response file/suffix.
    """
    responses: list[tuple[str, str]] = []
    try:
        for index, body in enumerate(list(getattr(page, "_invenio_partial_responses", []) or []), start=1):
            if body:
                responses.append((f"memory-{index:02d}", body))
    except Exception:
        pass

    debug_dir_value = ""
    try:
        debug_dir_value = str(getattr(page, "_invenio_debug_dir", "") or "")
    except Exception:
        debug_dir_value = ""
    if debug_dir_value:
        try:
            debug_dir = Path(debug_dir_value)
            for file in sorted(debug_dir.glob("05-search-response-*.xml")):
                body = file.read_text(encoding="utf-8", errors="ignore")
                if body:
                    responses.append((file.name, body))
        except Exception:
            pass

    all_tree_candidates: list[InvenioCandidate] = []
    all_panel_candidates: list[InvenioCandidate] = []
    summary: list[dict[str, Any]] = []

    for index, (response_name, response_body) in enumerate(responses, start=1):
        tree_candidates = _extract_tree_node_candidates(
            html_text=response_body,
            base_url=base_url,
            response_index=index,
        )
        panel_candidates = _extract_panel_hit_candidates(
            html_text=response_body,
            base_url=base_url,
            response_index=index,
        )
        all_tree_candidates.extend(tree_candidates)
        all_panel_candidates.extend(panel_candidates)
        summary.append(
            {
                "response": response_name,
                "has_partial_response": "<partial-response" in response_body,
                "has_ui_tree": "ui-tree" in response_body or "ui-treenode" in response_body,
                "has_treffer": "Treffer" in response_body,
                "tree_candidates": len(tree_candidates),
                "panel_candidates": len(panel_candidates),
            }
        )

    # Prefer concrete tree nodes. Generic panels such as "Treffer in der
    # Tektonik" are useful only if no tree node was materialized.
    selected = all_tree_candidates if all_tree_candidates else all_panel_candidates
    stabilized = _deduplicate_invenio_candidates(selected)
    _write_invenio_candidate_debug(debug_dir_value, summary=summary, candidates=stabilized)
    return stabilized


def _write_invenio_candidate_debug(debug_dir_value: str, *, summary: list[dict[str, Any]], candidates: list[InvenioCandidate]) -> None:
    if not debug_dir_value:
        return
    try:
        import json
        debug_dir = Path(debug_dir_value)
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / "05-candidate-extraction-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (debug_dir / "05-stabilized-candidates.json").write_text(
            json.dumps(
                [
                    {
                        "title": candidate.title,
                        "url": candidate.url,
                        "snippet": candidate.snippet,
                        "stabilization_key": _candidate_stabilization_key(candidate),
                    }
                    for candidate in candidates
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

def _extract_tree_node_candidates(*, html_text: str, base_url: str, response_index: int | None = None) -> list[InvenioCandidate]:
    """Extract materialized Tektonik/Klassifikation tree nodes from JSF updates.

    Once Invenio has accepted the search it may not render a conventional result
    table. Instead, subsequent partial responses update PrimeFaces trees such as
    ``masterLayoutForm:tektonik:tree`` and ``masterLayoutForm:klassif:tree``.
    Those nodes are the next actionable navigation targets. Expose them as
    candidate references so the report can show concrete archival branches
    instead of only the generic "Treffer in der Tektonik" message.
    """
    return _parse_tree_node_candidates(html_text=html_text, base_url=base_url, response_index=response_index)

def _extract_panel_hit_candidates(*, html_text: str, base_url: str, response_index: int | None = None) -> list[InvenioCandidate]:
    """Extract coarse candidate references from Invenio result side panels.

    After a successful search Invenio often updates only the Tektonik and
    Klassifikation panels, or an explanatory ``Suchergebnis`` panel saying that
    the hits were found in the Tektonik. In that state there is no standard
    result table yet, but the partial-response is still a valid candidate signal
    that the authenticated search was executed and produced hits.
    """
    return _parse_panel_hit_candidates(html_text=html_text, base_url=base_url, response_index=response_index)

def _synthetic_results_html(*, candidates: list[InvenioCandidate], page_url: str, actual_html: str) -> str:
    if not candidates:
        # Do not return the full authenticated Invenio page here: it contains
        # hidden login/password dialogs that make the generic result logic think
        # the page is blocked. The dedicated executor has already completed the
        # authenticated submit; if it extracted no candidates, expose a minimal
        # no-results page to the normal parser.
        return (
            "<html><head><title>Bundesarchiv Invenio no results</title></head>"
            f"<body data-source-page=\"{html.escape(page_url, quote=True)}\">"
            "<div class=\"no-results\">Keine Treffer</div>"
            "</body></html>"
        )
    rows = []
    for candidate in candidates:
        rows.append(
            "<tr><td>"
            f'<a data-invenio-candidate="true" href="{html.escape(candidate.url, quote=True)}">{html.escape(candidate.title)}</a>'
            f"<div class=\"snippet\">{html.escape(candidate.snippet)}</div>"
            "</td></tr>"
        )
    return (
        "<html><head><title>Bundesarchiv Invenio synthetic results</title></head>"
        f"<body data-source-page=\"{html.escape(page_url, quote=True)}\">"
        "<div id=\"searchResultTab\"><table><tbody class=\"ui-datatable-data\">"
        + "".join(rows)
        + "</tbody></table></div></body></html>"
    )


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(marker.casefold() in lowered for marker in markers)


def _safe_body_text(page: Any) -> str:
    try:
        return " ".join(page.locator("body").inner_text(timeout=5000).split())
    except Exception:  # noqa: BLE001
        return ""


def _wait_networkidle_best_effort(page: Any, *, timeout_ms: int) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:  # noqa: BLE001
        return


def _slow(milliseconds: int, page: Any) -> None:
    if milliseconds > 0:
        try:
            page.wait_for_timeout(milliseconds)
        except Exception:  # noqa: BLE001
            pass


def _css_attr_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _as_bool(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "si", "sÃ¬", "ja", "on"}


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return _as_bool(raw)


def _env_int(name: str, *, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed >= 0 else default

