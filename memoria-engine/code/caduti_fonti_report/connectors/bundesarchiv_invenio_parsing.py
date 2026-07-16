from __future__ import annotations

from dataclasses import dataclass
import html
import re
import urllib.parse

from ..http_utils import strip_tags


@dataclass(frozen=True)
class InvenioCandidate:
    title: str
    url: str
    snippet: str = ""
    detail_html: str = ""


def extract_jsf_update_blocks(partial_response_text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    pattern = re.compile(
        r'<update\s+id=(?P<quote>["\'])(?P<id>.*?)(?P=quote)\s*>\s*<!\[CDATA\[(?P<body>.*?)\]\]>\s*</update>',
        flags=re.I | re.S,
    )
    for match in pattern.finditer(partial_response_text):
        blocks.append((html.unescape(match.group("id")), match.group("body")))
    if not blocks and partial_response_text.strip():
        blocks.append(("document", partial_response_text))
    return blocks


def extract_tree_node_candidates(*, html_text: str, base_url: str, response_index: int | None = None) -> list[InvenioCandidate]:
    """Extract materialized Tektonik/Klassifikation tree nodes from JSF updates."""
    candidates: list[InvenioCandidate] = []
    seen: set[str] = set()

    for update_id, update_html in extract_jsf_update_blocks(html_text):
        lowered_update = f"{update_id} {update_html[:1000]}".casefold()
        if "ui-treenode" not in update_html and "ui-tree" not in update_html:
            continue
        if "tektonik" in lowered_update:
            tree_kind = "Tektonik"
            fragment_prefix = "tektonik"
        elif "klassif" in lowered_update or "klassifikation" in lowered_update:
            tree_kind = "Klassifikation"
            fragment_prefix = "klassifikation"
        else:
            tree_kind = "Invenio tree"
            fragment_prefix = "tree"

        for node_index, node in enumerate(iter_primefaces_tree_nodes(update_html), start=1):
            title = node.get("title", "").strip()
            rowkey = node.get("rowkey", "").strip()
            node_id = node.get("id", "").strip()
            node_type = node.get("node_type", "").strip()
            node_html = node.get("html", "")
            if not title or len(title) < 3:
                continue
            # The artificial root is less useful than its children; keep it only
            # when it is the sole candidate.
            if title.casefold() in {"bestÃ¤nde", "bestaende"} and rowkey in {"0", ""}:
                continue
            key = f"{tree_kind}|{rowkey}|{title}".casefold()
            if key in seen:
                continue
            seen.add(key)
            candidate_kind = invenio_node_candidate_kind(title=title, node_type=node_type, node_html=node_html)
            candidate_tree_kind = "Record" if candidate_kind == "record" else tree_kind
            candidate_fragment_prefix = "record" if candidate_kind == "record" else fragment_prefix
            safe_rowkey = urllib.parse.quote(rowkey or str(node_index), safe="")
            url = f"{base_url}#invenio-{candidate_fragment_prefix}-{safe_rowkey}"
            snippet = " | ".join(
                part
                for part in (
                    f"{candidate_tree_kind} node",
                    "record_candidate" if candidate_kind == "record" else "intermediate_candidate",
                    f"rowkey={rowkey}" if rowkey else "",
                    f"node_type={node_type}" if node_type else "",
                    f"id={node_id}" if node_id else "",
                )
                if part
            )
            candidates.append(
                InvenioCandidate(
                    title=f"Bundesarchiv Invenio {candidate_tree_kind}: {title}",
                    url=url,
                    snippet=snippet,
                    detail_html=node_html or update_html,
                )
            )
            if len(candidates) >= 25:
                return candidates

    return candidates


def extract_panel_hit_candidates(*, html_text: str, base_url: str, response_index: int | None = None) -> list[InvenioCandidate]:
    """Extract coarse candidate references from Invenio result side panels."""
    candidates: list[InvenioCandidate] = []
    seen: set[str] = set()

    for update_id, update_html in extract_jsf_update_blocks(html_text):
        text = strip_tags(update_html)
        normalized = " ".join(text.split())
        if not normalized:
            continue
        lowered = normalized.casefold()

        markers: list[tuple[str, str, str]] = []
        if "treffer in der tektonik" in lowered:
            markers.append(
                (
                    "Bundesarchiv Invenio: Treffer in der Tektonik",
                    "tektonik-treffer",
                    "Treffer in der Tektonik",
                )
            )
        if "treffer in der klassifikation" in lowered:
            markers.append(
                (
                    "Bundesarchiv Invenio: Treffer in der Klassifikation",
                    "klassifikation-treffer",
                    "Treffer in der Klassifikation",
                )
            )
        if "die treffer zu ihrer suche wurden ermittelt" in lowered or "sie finden sie in der tektonik" in lowered:
            markers.append(
                (
                    "Bundesarchiv Invenio: Suchtreffer in der Tektonik",
                    "suchtreffer-tektonik",
                    "Die Treffer zu Ihrer Suche wurden ermittelt",
                )
            )

        # When the update id is one of the known side panels but the heading was
        # rewritten to just ``Tektonik``/``Klassifikation``, still keep it as a
        # weaker candidate if the update looks like a post-search panel.
        if not markers and update_id in {"masterLayoutForm:j_idt159", "masterLayoutForm:j_idt224"}:
            if "tektonik" in lowered and "bestÃ¤nde" in lowered:
                markers.append(
                    (
                        "Bundesarchiv Invenio: Tektonik panel after search",
                        "tektonik-panel",
                        "Tektonik",
                    )
                )
            elif "klassifikation" in lowered:
                markers.append(
                    (
                        "Bundesarchiv Invenio: Klassifikation panel after search",
                        "klassifikation-panel",
                        "Klassifikation",
                    )
                )

        for title, fragment, marker in markers:
            url = f"{base_url}#{fragment}"
            key = f"{title}|{url}".casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                InvenioCandidate(
                    title=title,
                    url=url,
                    snippet=panel_snippet(normalized, marker),
                    detail_html=update_html,
                )
            )

    return candidates


def deduplicate_invenio_candidates(candidates: list[InvenioCandidate]) -> list[InvenioCandidate]:
    """Deduplicate candidate references by stable semantic key."""
    by_key: dict[str, InvenioCandidate] = {}
    for candidate in candidates:
        key = candidate_stabilization_key(candidate)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = candidate
            continue
        # Keep the version with the longer snippet/detail when two candidates
        # describe the same Tektonik/Klassifikation node.
        if len(candidate.snippet) + len(candidate.detail_html) > len(existing.snippet) + len(existing.detail_html):
            by_key[key] = candidate
    return list(by_key.values())[:50]


def candidate_stabilization_key(candidate: InvenioCandidate) -> str:
    title = re.sub(r"\s+", " ", candidate.title).strip().casefold()
    url = re.sub(r"-r\d+(?=$|[&#])", "", candidate.url)
    # If the URL contains a rowkey-derived fragment, use it as the stable key.
    fragment = urllib.parse.urlsplit(url).fragment.casefold()
    fragment = re.sub(r"-r\d+$", "", fragment)
    if fragment:
        return f"{title}|{fragment}"
    return f"{title}|{url.casefold()}"


def invenio_node_candidate_kind(*, title: str, node_type: str, node_html: str) -> str:
    """Classify a tree node as intermediate or record-like."""
    haystack = f"{title} {node_type} {strip_tags(node_html[:2000])}".casefold()
    if "tabsearchresultdetailpanel" in haystack or "direktlink" in haystack:
        return "record"
    if any(marker in haystack for marker in ("verzeichnungseinheit", "archivalieneinheit", "archivale", "signatur")):
        return "record"
    if re.search(r"\b(BArch\s+)?[A-Z][A-Z0-9]{0,4}\s+\d+[A-Z0-9_/ .-]*\b", title):
        return "record"
    return "intermediate"


def iter_primefaces_tree_nodes(update_html: str) -> list[dict[str, str]]:
    """Return PrimeFaces tree nodes from an Invenio JSF update fragment."""
    nodes: list[dict[str, str]] = []
    matches = list(re.finditer(r"<li\b(?P<attrs>[^>]*)>", update_html, flags=re.I | re.S))
    for idx, match in enumerate(matches):
        attrs = parse_attrs(match.group("attrs"))
        class_text = attrs.get("class", "")
        node_id = attrs.get("id", "")
        rowkey = attrs.get("data-rowkey", "")
        node_type = attrs.get("data-nodetype", "")
        if "ui-treenode" not in class_text and not rowkey and ":tree:" not in node_id:
            continue
        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else min(len(update_html), match.end() + 4000)
        segment = update_html[match.start():next_start]
        title = tree_node_title(segment)
        if not title:
            # Fall back to the first short text around the node opening. Avoid
            # swallowing the whole subtree of a parent node.
            plain = " ".join(strip_tags(segment[:1200]).split())
            title = plain[:180]
        title = html.unescape(title).strip()
        if not title:
            continue
        nodes.append(
            {
                "id": node_id,
                "rowkey": rowkey,
                "node_type": node_type,
                "title": title,
                "html": segment,
            }
        )
    return nodes


def tree_node_title(node_body: str) -> str:
    # Prefer the explicit title attribute used by Invenio labels.
    title_match = re.search(r'<span\b[^>]*\btitle=(?P<quote>["\'])(?P<title>.*?)(?P=quote)[^>]*>', node_body, flags=re.I | re.S)
    if title_match:
        return title_match.group("title")
    # Then the visible label span.
    label_match = re.search(
        r'<span\b[^>]*class=(?P<quote>["\'])[^"\']*ui-treenode-label[^"\']*(?P=quote)[^>]*>(?P<label>.*?)</span>',
        node_body,
        flags=re.I | re.S,
    )
    if label_match:
        return strip_tags(label_match.group("label"))
    # Finally, any first nested span text inside the node segment.
    first_span = re.search(r'<span\b[^>]*>(?P<label>[^<]{3,220})</span>', node_body, flags=re.I | re.S)
    if first_span:
        return first_span.group("label")
    return ""


def panel_snippet(text: str, marker: str) -> str:
    idx = text.find(marker)
    if idx < 0:
        return text[:500]
    start = max(0, idx - 180)
    end = min(len(text), idx + 500)
    return text[start:end]


def parse_attrs(attrs_text: str) -> dict[str, str]:
    return {
        match.group("name").strip().lower(): html.unescape(match.group("value"))
        for match in re.finditer(r'(?P<name>[\w:-]+)=(["\'])(?P<value>.*?)\2', attrs_text, flags=re.I | re.S)
    }
