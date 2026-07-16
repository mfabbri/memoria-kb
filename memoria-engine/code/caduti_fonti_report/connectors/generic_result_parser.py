from __future__ import annotations

import html
import re
import urllib.parse

from ..http_utils import page_title, strip_tags
from ..search_result_logic import CandidateLink, SearchResultSignals, SourceResultLogicDefinition


def extract_generic_result_signals(
    *,
    source_id: str,
    engine: str,
    html_text: str,
    result_url: str,
    result_logic: SourceResultLogicDefinition,
    query_is_mononym: bool = False,
) -> SearchResultSignals:
    compact = " ".join(strip_tags(html_text).split())
    heading = _extract_heading(html_text) or page_title(html_text)
    candidate_links = _candidate_links(html_text=html_text, result_url=result_url, result_logic=result_logic)
    blocked = _contains_any(compact, result_logic.signals.get("blocked_text", [])) and not candidate_links
    no_results = _contains_any(compact, result_logic.signals.get("no_results_text", []))
    total_results = len(candidate_links)
    shown_results = len(candidate_links)
    if no_results and not candidate_links:
        total_results = 0
        shown_results = 0

    return SearchResultSignals(
        source_id=source_id,
        engine=engine,
        heading=heading,
        shown_results=shown_results,
        total_results=total_results,
        candidate_links=candidate_links,
        blocked=blocked,
        metadata={
            "result_url": result_url,
            "query_is_mononym": "true" if query_is_mononym else "false",
        },
    )


def _extract_heading(html_text: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.I | re.S)
    if match:
        return strip_tags(match.group(1))
    return ""


def _candidate_links(
    *,
    html_text: str,
    result_url: str,
    result_logic: SourceResultLogicDefinition,
) -> list[CandidateLink]:
    href_fragments = _href_fragments_from_selector(str(result_logic.signals.get("result_link_selector", "")))
    css_class_tokens = _class_tokens_from_selector(str(result_logic.signals.get("result_link_selector", "")))
    title_attribute = str(result_logic.signals.get("result_link_title_attribute", "")).strip().lower()
    anchors = re.findall(r"<a\s[^>]*href=(['\"])(.*?)\1[^>]*>(.*?)</a>", html_text, flags=re.I | re.S)
    links: list[CandidateLink] = []
    seen_urls: set[str] = set()
    for _, href, raw_text in anchors:
        absolute = urllib.parse.urljoin(result_url, html.unescape(href))
        lowered = absolute.casefold()
        attrs = _anchor_attributes(raw_text="", href=href, html_text=html_text, absolute=absolute)
        if href_fragments and not any(fragment in lowered for fragment in href_fragments):
            continue
        if css_class_tokens:
            anchor_classes = {token.casefold() for token in attrs.get("class", "").split() if token.strip()}
            if not set(css_class_tokens).issubset(anchor_classes):
                continue
        if absolute in seen_urls:
            continue
        title = strip_tags(raw_text)
        if title_attribute and attrs.get(title_attribute, "").strip():
            title = strip_tags(attrs[title_attribute])
        if not _passes_candidate_filters(title=title, url=absolute, result_logic=result_logic):
            continue
        seen_urls.add(absolute)
        links.append(CandidateLink(title=title, url=absolute))
    preferred_links = [link for link in links if not _is_generic_search_link(link)]
    return preferred_links or []


def _href_fragments_from_selector(selector_text: str) -> list[str]:
    return [
        fragment.casefold()
        for fragment in re.findall(r'href\*="([^"]+)"', selector_text)
        if fragment.strip()
    ]


def _class_tokens_from_selector(selector_text: str) -> list[str]:
    return [token.casefold() for token in re.findall(r"\.([A-Za-z0-9_-]+)", selector_text) if token.strip()]


def _anchor_attributes(*, raw_text: str, href: str, html_text: str, absolute: str) -> dict[str, str]:
    escaped_href = re.escape(href)
    match = re.search(rf"<a\s(?P<attrs>[^>]*href=(['\"])({escaped_href})\2[^>]*)>", html_text, flags=re.I | re.S)
    if not match:
        return {}
    attrs_text = match.group("attrs")
    return {
        attr_match.group("name").strip().lower(): html.unescape(attr_match.group("value"))
        for attr_match in re.finditer(r'(?P<name>[\w:-]+)=(["\'])(?P<value>.*?)\2', attrs_text, flags=re.I | re.S)
    }


def _passes_candidate_filters(*, title: str, url: str, result_logic: SourceResultLogicDefinition) -> bool:
    filters = result_logic.candidate_filters
    compact_title = " ".join(title.split()).strip()
    lowered_title = compact_title.casefold()
    lowered_url = url.casefold()
    if filters.require_non_empty_title and not compact_title:
        return False
    if filters.min_title_length and len(compact_title) < filters.min_title_length:
        return False
    if filters.include_url_patterns and not any(pattern.casefold() in lowered_url for pattern in filters.include_url_patterns):
        return False
    if filters.exclude_url_patterns and any(pattern.casefold() in lowered_url for pattern in filters.exclude_url_patterns):
        return False
    if filters.include_title_patterns and not any(pattern.casefold() in lowered_title for pattern in filters.include_title_patterns):
        return False
    if filters.exclude_title_patterns and any(pattern.casefold() in lowered_title for pattern in filters.exclude_title_patterns):
        return False
    return True


def _contains_any(text: str, candidates: object) -> bool:
    if not isinstance(candidates, list):
        return False
    lowered = text.casefold()
    return any(str(candidate).strip().casefold() in lowered for candidate in candidates if str(candidate).strip())


def _is_generic_search_link(link: CandidateLink) -> bool:
    url = link.url.casefold().rstrip("/")
    title = link.title.casefold().strip()
    return url.endswith("/cerca") and title == "cerca"
