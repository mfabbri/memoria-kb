from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .models import SearchHit


USER_AGENT = "Mozilla/5.0 (compatible; CaDiMalancaResearchBot/1.0)"
DEFAULT_TIMEOUT = 20
COMMON_NAV_TEXTS = {
    "home",
    "chi siamo",
    "contatti",
    "menu",
    "cerca",
    "search",
    "leggi",
    "read more",
    "login",
    "accedi",
}


def fetch_text(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="ignore")


def fetch_text_with_opener(opener: urllib.request.OpenerDirector, url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener.open(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="ignore")


def post_form_with_opener(
    opener: urllib.request.OpenerDirector,
    url: str,
    form_data: dict[str, str],
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[str, str]:
    encoded = urllib.parse.urlencode(form_data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with opener.open(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.geturl(), response.read().decode(charset, errors="ignore")


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):  # noqa: N802
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_302(self, req, fp, code, msg, headers):  # noqa: N802
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_303(self, req, fp, code, msg, headers):  # noqa: N802
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    def http_error_307(self, req, fp, code, msg, headers):  # noqa: N802
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


def strip_tags(value: str) -> str:
    value = re.sub(r"<script.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())


def page_title(html_text: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html_text, flags=re.I | re.S)
    return strip_tags(match.group(1)) if match else ""


def extract_generic_hits(html_text: str, base_url: str, query: str, limit: int = 3) -> list[SearchHit]:
    anchors = re.findall(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html_text, flags=re.I | re.S)
    parsed_base = urllib.parse.urlparse(base_url)
    query_tokens = {token.lower() for token in re.findall(r"\w+", query) if len(token) > 2}
    hits: list[tuple[int, SearchHit]] = []
    seen_urls: set[str] = set()

    for href, raw_text in anchors:
        absolute = urllib.parse.urljoin(base_url, html.unescape(href))
        parsed = urllib.parse.urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc != parsed_base.netloc:
            continue
        if absolute in seen_urls:
            continue

        text = strip_tags(raw_text)
        if len(text) < 4:
            continue
        if text.lower() in COMMON_NAV_TEXTS:
            continue

        score = 0
        lowered_text = text.lower()
        lowered_url = absolute.lower()
        for token in query_tokens:
            if token in lowered_text:
                score += 3
            if token in lowered_url:
                score += 2
        if "/tag/" in lowered_url or "/category/" in lowered_url:
            score -= 1
        if absolute.rstrip("/") == f"{parsed_base.scheme}://{parsed_base.netloc}".rstrip("/"):
            score -= 2
        if score <= 0:
            continue

        seen_urls.add(absolute)
        hits.append((score, SearchHit(title=text, url=absolute)))

    hits.sort(key=lambda item: item[0], reverse=True)
    return [hit for _, hit in hits[:limit]]


def parse_wp_json_search(url: str, timeout: int) -> list[SearchHit]:
    raw = fetch_text(url, timeout=timeout)
    data = json.loads(raw)
    hits: list[SearchHit] = []
    for item in data[:3]:
        title = item.get("title") or item.get("name") or item.get("slug") or "Risultato"
        item_url = item.get("url") or item.get("link") or ""
        subtype = item.get("subtype")
        snippet = f"REST search ({subtype})" if subtype else "REST search"
        if item_url:
            hits.append(SearchHit(title=strip_tags(str(title)), url=item_url, snippet=snippet))
    return hits


def parse_search_page(url: str, timeout: int, query: str) -> tuple[str, list[SearchHit]]:
    html_text = fetch_text(url, timeout=timeout)
    return parse_search_page_html(html_text, url, query)


def parse_search_page_html(html_text: str, base_url: str, query: str) -> tuple[str, list[SearchHit]]:
    title = page_title(html_text)
    hits = extract_generic_hits(html_text, base_url, query)
    return title, hits


def extract_hidden_inputs(html_text: str) -> dict[str, str]:
    hidden_inputs: dict[str, str] = {}
    pattern = re.compile(r'<input[^>]+type="hidden"[^>]+name="([^"]+)"[^>]+value="([^"]*)"', flags=re.I)
    for name, value in pattern.findall(html_text):
        hidden_inputs[html.unescape(name)] = html.unescape(value)
    return hidden_inputs
