from __future__ import annotations

import html
import json
import re
import urllib.parse

from ..search_result_logic import CandidateLink, SearchResultSignals, SourceResultLogicDefinition


CWGC_BASE_URL = "https://www.cwgc.org"


def extract_cwgc_result_signals(
    *,
    html_text: str,
    result_url: str,
    result_logic: SourceResultLogicDefinition | None = None,
    query_is_mononym: bool = False,
) -> SearchResultSignals:
    compact = _compact(html_text)
    heading = _first_match(compact, r"<h1>\s*([^<]+?)\s*</h1>")
    shown_results, total_results = _result_counts(compact, result_logic=result_logic)
    active_result_tab = _active_result_tab(html_text, compact=compact, result_logic=result_logic)
    available_tabs = _available_result_tabs(html_text, result_url=result_url, result_logic=result_logic)
    if heading.casefold() == "no search results" and total_results <= 0:
        shown_results = 0
        total_results = 0

    candidate_links = _candidate_links(compact)
    if total_results <= 0 and candidate_links:
        total_results = len(candidate_links)
        shown_results = len(candidate_links)

    return SearchResultSignals(
        source_id="cwgc",
        engine="cwgc_find_war_dead",
        heading=heading,
        shown_results=shown_results,
        total_results=total_results,
        candidate_links=candidate_links,
        metadata={
            "result_url": result_url,
            "query_is_mononym": "true" if query_is_mononym else "false",
            "active_result_tab": active_result_tab,
            "available_result_tabs_json": json.dumps(available_tabs, ensure_ascii=False),
        },
    )


def _result_counts(text: str, *, result_logic: SourceResultLogicDefinition | None) -> tuple[int, int]:
    pattern = _signal_text(result_logic, "result_count_pattern") or r"SHOW\s+(\d+)\s+OF\s+(\d+)\s+WAR DEAD"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return 0, 0
    return int(match.group(1)), int(match.group(2))


def _candidate_links(text: str) -> list[CandidateLink]:
    links: list[CandidateLink] = []
    seen: set[str] = set()
    for match in re.finditer(r'<a\b[^>]*href="([^"]*casualty-details/[^"]*)"[^>]*>(.*?)</a>', text, flags=re.IGNORECASE):
        url = _absolute_url(html.unescape(match.group(1)))
        if url in seen:
            continue
        seen.add(url)
        anchor_text = _clean_html(match.group(2))
        nearby_title = _nearby_title(text, match.start())
        title = nearby_title if anchor_text.casefold() in {"more details", "details"} else anchor_text
        title = title or nearby_title or "CWGC casualty detail"
        links.append(CandidateLink(title=title, url=url))
    return links


def _nearby_title(text: str, position: int) -> str:
    window = text[max(0, position - 1000) : position]
    candidates = re.findall(r"<(?:h2|h3|h4|strong|b)[^>]*>([^<]{2,120})</(?:h2|h3|h4|strong|b)>", window, flags=re.IGNORECASE)
    if not candidates:
        return ""
    return html.unescape(candidates[-1]).strip()


def _absolute_url(value: str) -> str:
    return urllib.parse.urljoin(CWGC_BASE_URL, value)


def _first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return html.unescape(match.group(1)).strip() if match else ""


def _clean_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", value)).strip()


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value)


def _active_result_tab(
    html_text: str,
    *,
    compact: str,
    result_logic: SourceResultLogicDefinition | None,
) -> str:
    for tab_definition in _tab_definitions(result_logic):
        active_pattern = str(tab_definition.get("active_pattern", "")).strip()
        if active_pattern and re.search(active_pattern, html_text, flags=re.IGNORECASE | re.S):
            return str(tab_definition.get("id", "")).strip()
        label_text = str(tab_definition.get("label_text", "")).strip()
        if label_text and _contains_active_marker(compact, label_text):
            return str(tab_definition.get("id", "")).strip()
    return ""


def _available_result_tabs(
    html_text: str,
    *,
    result_url: str,
    result_logic: SourceResultLogicDefinition | None,
) -> list[dict[str, str]]:
    tabs: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for tab_definition in _tab_definitions(result_logic):
        tab_id = str(tab_definition.get("id", "")).strip()
        if not tab_id or tab_id in seen_ids:
            continue
        href_pattern = str(tab_definition.get("href_pattern", "")).strip()
        href = ""
        if href_pattern:
            match = re.search(href_pattern, html_text, flags=re.IGNORECASE | re.S)
            if match:
                href = urllib.parse.urljoin(result_url, html.unescape(match.group(1)))
        tabs.append(
            {
                "id": tab_id,
                "label": str(tab_definition.get("label_text", "")).strip(),
                "url": href,
            }
        )
        seen_ids.add(tab_id)
    return tabs


def _tab_definitions(result_logic: SourceResultLogicDefinition | None) -> list[dict[str, str]]:
    if result_logic is None:
        return []
    raw_value = result_logic.signals.get("result_tabs", [])
    if not isinstance(raw_value, list):
        return []
    return [item for item in raw_value if isinstance(item, dict)]


def _signal_text(result_logic: SourceResultLogicDefinition | None, key: str) -> str:
    if result_logic is None:
        return ""
    return str(result_logic.signals.get(key, "")).strip()


def _contains_active_marker(compact: str, label_text: str) -> bool:
    normalized_label = re.escape(label_text.strip())
    pattern = rf"{normalized_label}\s*(?:ACTIVE|SELECTED)"
    return bool(re.search(pattern, compact, flags=re.IGNORECASE))
