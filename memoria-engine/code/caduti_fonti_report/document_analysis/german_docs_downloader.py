from __future__ import annotations

import argparse
import html
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from .german_docs_manifest import render_german_docs_manifest_markdown as _render_markdown
from .manual_registration import register_manual_document

SOURCE_ID = "german_docs_in_russia_wwii"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


def download_german_docs_pages(
    *,
    node_url: str,
    output_dir: Path,
    archival_reference: str,
    title_prefix: str = "",
    start_page: int = 1,
    max_pages: int = 3,
    zoom: int = 7,
    delay_seconds: float = 1.0,
    overwrite: bool = False,
    headless: bool = True,
    playwright_factory: Callable[[], object] | None = None,
) -> dict[str, Any]:
    if max_pages < 1:
        raise ValueError("max_pages deve essere almeno 1.")
    if start_page < 1:
        raise ValueError("start_page deve essere almeno 1.")
    if not archival_reference.strip():
        raise ValueError("archival_reference obbligatorio.")

    if playwright_factory is None:
        from playwright.sync_api import sync_playwright

        playwright_factory = sync_playwright

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    access_date = datetime.now(UTC).date().isoformat()
    manifest: dict[str, Any] = {
        "@type": "GermanDocsInRussiaDownloadManifest",
        "source_id": SOURCE_ID,
        "node_url": node_url,
        "output_dir": str(output_dir),
        "archival_reference": archival_reference,
        "start_page": start_page,
        "max_pages": max_pages,
        "zoom": zoom,
        "access_date": access_date,
        "documents": [],
    }

    with playwright_factory() as playwright:
        browser = playwright.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            locale="it-IT",
            viewport={"width": 1440, "height": 1200},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.goto(node_url, wait_until="domcontentloaded", timeout=60000)
        _accept_user_agreement(page)
        page.wait_for_load_state("networkidle", timeout=60000)

        content = page.content()
        title = _page_title(page, content)
        archival_context = _collect_archival_context(context=context, node_url=node_url, node_title=title, node_content=content)
        page_ids = _extract_page_ids(content)
        selected_ids = page_ids[start_page - 1 : start_page - 1 + max_pages]
        manifest["node_title"] = title
        manifest["archival_context"] = archival_context
        manifest["page_count_detected"] = len(page_ids)
        manifest["page_ids_selected"] = selected_ids

        safe_prefix = _safe_filename(title_prefix or archival_reference)
        for offset, page_id in enumerate(selected_ids, start=start_page):
            image_url = urljoin(node_url, f"/pages/{page_id}/zooms/{zoom}")
            filename = f"{safe_prefix}_page_{offset:04d}_{page_id}_zoom{zoom}.jpg"
            target = output_dir / filename
            sidecar = target.with_name(f"{target.name}.document.yaml")
            item: dict[str, Any] = {
                "page_number": offset,
                "page_id": page_id,
                "image_url": image_url,
                "file": str(target),
                "sidecar": str(sidecar),
            }
            if target.exists() and sidecar.exists() and not overwrite:
                item["status"] = "skipped_existing"
                manifest["documents"].append(item)
                continue

            try:
                response = context.request.get(image_url, timeout=60000)
            except Exception as exc:
                item["status"] = "error"
                item["error"] = f"download failed: {exc}"
                manifest["documents"].append(item)
                continue

            item["http_status"] = response.status
            if not response.ok:
                item["status"] = "error"
                item["error"] = f"download failed: HTTP {response.status}"
                manifest["documents"].append(item)
                continue

            target.write_bytes(response.body())
            registration = register_manual_document(
                file_path=target,
                source_id=SOURCE_ID,
                title=f"{title_prefix or title} - page {offset:04d}",
                url=image_url,
                archival_reference=f"{archival_reference}, page {offset}, page_id {page_id}",
                access_date=access_date,
                review_status="unreviewed",
                sidecar_path=sidecar,
                extra_metadata={"german_docs_archival_context": archival_context},
                overwrite=overwrite,
            )
            item["status"] = "downloaded"
            item["document_id"] = registration["document"]["document_id"]
            manifest["documents"].append(item)
            if delay_seconds > 0:
                time.sleep(delay_seconds)

        context.close()
        browser.close()

    manifest["summary"] = _summary(manifest["documents"])
    return manifest


def download_german_docs_opis_delos(
    *,
    opis_url: str,
    output_dir: Path,
    archival_reference: str,
    title_prefix: str = "",
    max_delos: int = 25,
    max_pages_per_delo: int = 0,
    max_total_pages: int = 100,
    zoom: int = 7,
    delay_seconds: float = 1.0,
    overwrite: bool = False,
    headless: bool = True,
    playwright_factory: Callable[[], object] | None = None,
) -> dict[str, Any]:
    if max_delos < 0:
        raise ValueError("max_delos deve essere almeno 0; usa 0 per tutti i Delo rilevati.")
    if max_pages_per_delo < 0:
        raise ValueError("max_pages_per_delo deve essere almeno 0; usa 0 per tutte le pagine del Delo.")
    if max_total_pages < 1:
        raise ValueError("max_total_pages deve essere almeno 1.")
    if not archival_reference.strip():
        raise ValueError("archival_reference obbligatorio.")

    if playwright_factory is None:
        from playwright.sync_api import sync_playwright

        playwright_factory = sync_playwright

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    access_date = datetime.now(UTC).date().isoformat()
    manifest: dict[str, Any] = {
        "@type": "GermanDocsInRussiaOpisDownloadManifest",
        "source_id": SOURCE_ID,
        "opis_url": opis_url,
        "output_dir": str(output_dir),
        "archival_reference": archival_reference,
        "max_delos": max_delos,
        "max_pages_per_delo": max_pages_per_delo,
        "max_total_pages": max_total_pages,
        "zoom": zoom,
        "access_date": access_date,
        "delo_nodes": [],
        "documents": [],
    }

    with playwright_factory() as playwright:
        browser = playwright.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            locale="it-IT",
            viewport={"width": 1440, "height": 1200},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.goto(opis_url, wait_until="domcontentloaded", timeout=60000)
        _accept_user_agreement(page)
        page.wait_for_load_state("networkidle", timeout=60000)
        opis_content = page.content()
        opis_title = _page_title(page, opis_content)
        delo_nodes = _extract_delo_node_links(base_url=opis_url, content=opis_content)
        selected_delo_nodes = delo_nodes if max_delos == 0 else delo_nodes[:max_delos]
        manifest["opis_title"] = opis_title
        manifest["delo_count_detected"] = len(delo_nodes)
        manifest["delo_count_selected"] = len(selected_delo_nodes)

        downloaded_or_seen = 0
        for delo_index, delo_node in enumerate(selected_delo_nodes, start=1):
            if downloaded_or_seen >= max_total_pages:
                break
            delo_url = str(delo_node["url"])
            page.goto(delo_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
            content = page.content()
            title = _page_title(page, content)
            archival_context = _collect_archival_context(
                context=context,
                node_url=delo_url,
                node_title=title,
                node_content=content,
            )
            page_ids = _extract_page_ids(content)
            remaining_total = max_total_pages - downloaded_or_seen
            per_delo_limit = len(page_ids) if max_pages_per_delo == 0 else max_pages_per_delo
            selected_ids = page_ids[: min(per_delo_limit, remaining_total)]
            delo_output_dir = _hierarchical_output_dir(
                output_dir=output_dir,
                archival_context=archival_context,
                fallback_parts=[archival_reference, title],
            )
            delo_output_dir.mkdir(parents=True, exist_ok=True)
            delo_manifest: dict[str, Any] = {
                "index": delo_index,
                "url": delo_url,
                "title": title,
                "label": delo_node.get("label", ""),
                "output_dir": str(delo_output_dir),
                "archival_context": archival_context,
                "page_count_detected": len(page_ids),
                "page_ids_selected": selected_ids,
                "documents": [],
            }
            safe_prefix = _safe_filename(title_prefix or _archive_context_label(archival_context) or title)
            for offset, page_id in enumerate(selected_ids, start=1):
                image_url = urljoin(delo_url, f"/pages/{page_id}/zooms/{zoom}")
                filename = f"{safe_prefix}_page_{offset:04d}_{page_id}_zoom{zoom}.jpg"
                target = delo_output_dir / filename
                sidecar = target.with_name(f"{target.name}.document.yaml")
                item: dict[str, Any] = {
                    "delo_url": delo_url,
                    "delo_title": title,
                    "page_number": offset,
                    "page_id": page_id,
                    "image_url": image_url,
                    "file": str(target),
                    "sidecar": str(sidecar),
                }
                if target.exists() and sidecar.exists() and not overwrite:
                    item["status"] = "skipped_existing"
                    delo_manifest["documents"].append(item)
                    manifest["documents"].append(item)
                    downloaded_or_seen += 1
                    continue

                try:
                    response = context.request.get(image_url, timeout=60000)
                except Exception as exc:
                    item["status"] = "error"
                    item["error"] = f"download failed: {exc}"
                    delo_manifest["documents"].append(item)
                    manifest["documents"].append(item)
                    downloaded_or_seen += 1
                    continue

                item["http_status"] = response.status
                if not response.ok:
                    item["status"] = "error"
                    item["error"] = f"download failed: HTTP {response.status}"
                    delo_manifest["documents"].append(item)
                    manifest["documents"].append(item)
                    downloaded_or_seen += 1
                    continue

                target.write_bytes(response.body())
                registration = register_manual_document(
                    file_path=target,
                    source_id=SOURCE_ID,
                    title=f"{title} - page {offset:04d}",
                    url=image_url,
                    archival_reference=f"{_archive_context_label(archival_context) or archival_reference}, page {offset}, page_id {page_id}",
                    access_date=access_date,
                    review_status="unreviewed",
                    sidecar_path=sidecar,
                    extra_metadata={"german_docs_archival_context": archival_context},
                    overwrite=overwrite,
                )
                item["status"] = "downloaded"
                item["document_id"] = registration["document"]["document_id"]
                delo_manifest["documents"].append(item)
                manifest["documents"].append(item)
                downloaded_or_seen += 1
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
            manifest["delo_nodes"].append(delo_manifest)

        context.close()
        browser.close()

    manifest["summary"] = _summary(manifest["documents"])
    return manifest


def write_manifest(*, manifest: dict[str, Any], output_json: Path, output_md: Path | None = None) -> None:
    output_json = Path(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md = Path(output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_render_markdown(manifest), encoding="utf-8")


def _accept_user_agreement(page) -> None:
    button = page.locator(".user_agreements__button--yes")
    try:
        if button.count() > 0 and button.first.is_visible(timeout=1000):
            button.first.click()
            page.wait_for_timeout(500)
    except Exception:
        return


def _page_title(page, content: str) -> str:
    try:
        heading = page.locator("h1").first.text_content(timeout=2000)
        if heading and heading.strip():
            return _repair_mojibake(" ".join(heading.split()))
    except Exception:
        pass
    match = re.search(r"<title[^>]*>(.*?)</title>", content, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return _repair_mojibake(" ".join(html.unescape(re.sub(r"<[^>]+>", " ", match.group(1))).split()))
    return "German Docs in Russia document"


def _collect_archival_context(*, context, node_url: str, node_title: str, node_content: str) -> dict[str, Any]:
    nodes = _extract_breadcrumb_nodes(base_url=node_url, content=node_content)
    if not nodes or nodes[-1]["url"] != node_url:
        nodes.append({"label": node_title, "url": node_url})

    hierarchy: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for node in nodes:
        url = str(node.get("url", "")).strip()
        label = str(node.get("label", "")).strip()
        if not url or url in seen_urls or _is_top_node(label, url):
            continue
        seen_urls.add(url)
        if url == node_url:
            content = node_content
        else:
            content = _fetch_node_html(context=context, url=url)
        title = _title_from_content(content) or label
        hierarchy.append(
            {
                "level": _classify_archival_level(label or title),
                "label": _repair_mojibake(label or title),
                "url": url,
                "title": _repair_mojibake(title),
                "metadata": _extract_metadata_table(content),
            }
        )
    return {
        "source": "german_docs_in_russia_node_metadata",
        "review_status": "unreviewed",
        "hierarchy": hierarchy,
    }


def _fetch_node_html(*, context, url: str) -> str:
    try:
        response = context.request.get(url, timeout=60000)
    except Exception:
        return ""
    if not getattr(response, "ok", False):
        return ""
    body = response.body()
    for encoding in ("utf-8", "cp1252", "latin1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def _extract_breadcrumb_nodes(*, base_url: str, content: str) -> list[dict[str, str]]:
    match = re.search(r'<div class="crumbs">(.*?)</div>\s*<h1', content, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    parser = _BreadcrumbParser(base_url=base_url)
    parser.feed(match.group(1))
    return parser.nodes


def _is_top_node(label: str, url: str) -> bool:
    value = f"{label} {url}".lower()
    return "top" in value and "/nodes/28468" in value


def _classify_archival_level(label: str) -> str:
    lowered = _repair_mojibake(label).lower()
    if "fond" in lowered or "фонд" in lowered:
        return "fond"
    if "opis" in lowered or "опись" in lowered:
        return "opis"
    if "delo" in lowered or "дело" in lowered:
        return "delo"
    return "node"


def _extract_delo_node_links(*, base_url: str, content: str) -> list[dict[str, str]]:
    parser = _NodeLinkParser(base_url=base_url)
    parser.feed(content)
    selected: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for node in parser.nodes:
        url = node["url"]
        label = node["label"]
        if url in seen_urls:
            continue
        if _classify_archival_level(f"{label} {url}") != "delo":
            continue
        seen_urls.add(url)
        selected.append({"label": label, "url": url})
    return selected


def _hierarchical_output_dir(
    *,
    output_dir: Path,
    archival_context: dict[str, Any],
    fallback_parts: list[str],
) -> Path:
    hierarchy = archival_context.get("hierarchy", []) if isinstance(archival_context, dict) else []
    parts: list[str] = []
    if isinstance(hierarchy, list):
        for item in hierarchy:
            if not isinstance(item, dict):
                continue
            level = str(item.get("level", ""))
            if level not in {"fond", "opis", "delo"}:
                continue
            label = str(item.get("label") or item.get("title") or level)
            parts.append(_safe_filename(label))
    if not parts:
        parts = [_safe_filename(part) for part in fallback_parts if part.strip()]
    target = output_dir
    for part in parts:
        target = target / part
    return target


def _archive_context_label(archival_context: dict[str, Any]) -> str:
    hierarchy = archival_context.get("hierarchy", []) if isinstance(archival_context, dict) else []
    if not isinstance(hierarchy, list):
        return ""
    labels = [
        str(item.get("label") or item.get("title") or "").strip()
        for item in hierarchy
        if isinstance(item, dict) and item.get("level") in {"fond", "opis", "delo"}
    ]
    return ", ".join(label for label in labels if label)


def _title_from_content(content: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", content, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return _clean_html_text(match.group(1))
    match = re.search(r"<title[^>]*>(.*?)</title>", content, flags=re.IGNORECASE | re.DOTALL)
    if match:
        title = _clean_html_text(match.group(1))
        if "|" in title:
            title = title.rsplit("|", 1)[-1].strip()
        return title
    return ""


def _extract_metadata_table(content: str) -> dict[str, str]:
    parser = _MetadataTableParser()
    parser.feed(content)
    return {_repair_mojibake(key): _repair_mojibake(value) for key, value in parser.metadata.items() if key and value}


def _clean_html_text(value: str) -> str:
    return _repair_mojibake(" ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split()))


def _repair_mojibake(value: str) -> str:
    markers = ("Ð", "Ñ", "Â", "â€", "â€“", "â€™")
    original_score = sum(value.count(marker) for marker in markers)
    if original_score == 0:
        return value

    best = value
    best_score = original_score
    for encoding in ("cp1252", "latin1"):
        try:
            candidate = value.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        score = sum(candidate.count(marker) for marker in markers)
        if score < best_score:
            best = candidate
            best_score = score
    return best


class _BreadcrumbParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.nodes: list[dict[str, str]] = []
        self._current_href = ""
        self._current_text: list[str] = []
        self._span_depth = 0
        self._span_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag == "a" and attrs_dict.get("href", ""):
            self._current_href = attrs_dict["href"]
            self._current_text = []
        elif tag == "span" and not self._current_href:
            self._span_depth += 1
            self._span_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)
        elif self._span_depth:
            self._span_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href:
            label = _clean_html_text(" ".join(self._current_text))
            if label:
                self.nodes.append({"label": label, "url": urljoin(self.base_url, self._current_href)})
            self._current_href = ""
            self._current_text = []
        elif tag == "span" and self._span_depth:
            self._span_depth -= 1
            if self._span_depth == 0:
                label = _clean_html_text(" ".join(self._span_text))
                if label and label not in {"", "|"}:
                    self.nodes.append({"label": label, "url": self.base_url})
                self._span_text = []


class _NodeLinkParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.nodes: list[dict[str, str]] = []
        self._current_href = ""
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        href = attrs_dict.get("href", "")
        if tag == "a" and "/nodes/" in href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._current_href:
            return
        label = _clean_html_text(" ".join(self._current_text))
        if label:
            self.nodes.append({"label": label, "url": urljoin(self.base_url, self._current_href)})
        self._current_href = ""
        self._current_text = []


class _MetadataTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, str] = {}
        self._in_record = False
        self._div_depth = 0
        self._field = ""
        self._label_parts: list[str] = []
        self._value_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        class_value = attrs_dict.get("class", "")
        if tag == "div" and "table__strike" in class_value:
            self._in_record = True
            self._div_depth = 1
            self._field = ""
            self._label_parts = []
            self._value_parts = []
            return
        if not self._in_record:
            return
        if tag == "div":
            self._div_depth += 1
            if "table__column" in class_value and "first" in class_value:
                self._field = "label"
            elif "table__column" in class_value:
                self._field = "value"

    def handle_data(self, data: str) -> None:
        if not self._in_record:
            return
        if self._field == "label":
            self._label_parts.append(data)
        elif self._field == "value":
            self._value_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._in_record or tag != "div":
            return
        self._div_depth -= 1
        if self._div_depth <= 0:
            label = _clean_html_text(" ".join(self._label_parts))
            value = _clean_html_text(" ".join(self._value_parts))
            if label and value:
                self.metadata[label] = value
            self._in_record = False
            self._field = ""


def _extract_page_ids(content: str) -> list[int]:
    ids = [int(value) for value in re.findall(r'"id"\s*:\s*(\d+)', content)]
    seen: set[int] = set()
    unique: list[int] = []
    for page_id in ids:
        if page_id not in seen:
            unique.append(page_id)
            seen.add(page_id)
    return unique


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned[:120] or "german_docs"


def _summary(documents: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {"total": len(documents)}
    for item in documents:
        status = str(item.get("status", "unknown"))
        summary[status] = summary.get(status, 0) + 1
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Scarica pagine da German Docs in Russia con Playwright e sidecar.")
    parser.add_argument("--node-url", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--archival-reference", required=True)
    parser.add_argument("--title-prefix", default="")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--download-opis-delos", action="store_true")
    parser.add_argument("--max-delos", type=int, default=25)
    parser.add_argument("--max-pages-per-delo", type=int, default=0)
    parser.add_argument("--max-total-pages", type=int, default=100)
    parser.add_argument("--zoom", type=int, default=7)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    if args.download_opis_delos:
        manifest = download_german_docs_opis_delos(
            opis_url=args.node_url,
            output_dir=Path(args.output_dir),
            archival_reference=args.archival_reference,
            title_prefix=args.title_prefix,
            max_delos=args.max_delos,
            max_pages_per_delo=args.max_pages_per_delo,
            max_total_pages=args.max_total_pages,
            zoom=args.zoom,
            delay_seconds=args.delay_seconds,
            overwrite=args.overwrite,
            headless=not args.headed,
        )
    else:
        manifest = download_german_docs_pages(
            node_url=args.node_url,
            output_dir=Path(args.output_dir),
            archival_reference=args.archival_reference,
            title_prefix=args.title_prefix,
            start_page=args.start_page,
            max_pages=args.max_pages,
            zoom=args.zoom,
            delay_seconds=args.delay_seconds,
            overwrite=args.overwrite,
            headless=not args.headed,
        )
    write_manifest(
        manifest=manifest,
        output_json=Path(args.output_json),
        output_md=Path(args.output_md) if args.output_md.strip() else None,
    )
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
