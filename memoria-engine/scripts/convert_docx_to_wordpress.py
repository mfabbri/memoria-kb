from __future__ import annotations

import html
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = f"{{{NS['w']}}}"


def paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "tab":
            parts.append(" ")
        elif node.tag == W + "br":
            parts.append("<br>")
    return "".join(parts).strip()


def paragraph_style(paragraph: ET.Element) -> str:
    style = paragraph.find("./w:pPr/w:pStyle", NS)
    return style.get(W + "val") if style is not None else ""


def heading_block(text: str, level: int) -> str:
    escaped = html.escape(text)
    return (
        f'<!-- wp:heading {{"level":{level}}} -->\n'
        f"<h{level}>{escaped}</h{level}>\n"
        "<!-- /wp:heading -->"
    )


def paragraph_block(text: str) -> str:
    match = re.match(
        r"^(Dati|Ruolo / affiliazione|Nota biografica \(profilo ed episodio\)|Fonti / note):\s*(.*)$",
        text,
    )
    if match:
        content = f"<strong>{html.escape(match.group(1))}:</strong> {html.escape(match.group(2))}"
    else:
        content = html.escape(text)

    return f"<!-- wp:paragraph -->\n<p>{content}</p>\n<!-- /wp:paragraph -->"


def list_block(items: list[str]) -> str:
    list_items = "\n".join(f"<li>{html.escape(item)}</li>" for item in items if item)
    return f"<!-- wp:list -->\n<ul>\n{list_items}\n</ul>\n<!-- /wp:list -->"


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", html.unescape(text))
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_text = without_accents.lower().replace("ª", "a").replace("º", "o")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


def add_internal_links(blocks: list[str]) -> list[str]:
    names = []
    for block in blocks:
        match = re.search(r"<h3>(.*?)</h3>", block)
        if match:
            names.append(html.unescape(match.group(1)))

    if not names:
        return blocks

    slugs = {name: slugify(name) for name in names}
    updated = []
    for block in blocks:
        for name, slug in slugs.items():
            escaped_name = html.escape(name)
            aliases = [escaped_name]
            if name == "Moretti Renato":
                aliases.append("Memo. Moretti Renato")

            for alias in aliases:
                block = block.replace(
                    f"<li>{alias}</li>",
                    f'<li><a href="#{slug}">{alias}</a></li>',
                )

            block = block.replace(
                f'<!-- wp:heading {{"level":3}} -->\n<h3>{escaped_name}</h3>',
                f'<!-- wp:heading {{"level":3,"anchor":"{slug}"}} -->\n'
                f'<h3 id="{slug}">{escaped_name}</h3>',
            )
        updated.append(block)

    return updated


def convert(src: Path, out: Path) -> None:
    with zipfile.ZipFile(src) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    body = root.find("w:body", NS)
    if body is None:
        raise RuntimeError("Documento Word senza body leggibile.")

    blocks: list[str] = [
        '<!-- wp:group {"layout":{"type":"constrained"}} -->\n<div class="wp-block-group">'
    ]

    for child in body:
        if child.tag == W + "p":
            text = paragraph_text(child)
            if not text:
                continue

            style = paragraph_style(child)
            if style == "Titolo":
                blocks.append(heading_block(text, 1))
            elif style in {"Titolo1", "Titolo2"}:
                blocks.append(heading_block(text, 2))
            elif style in {"Titolo3", "Titolo4"}:
                blocks.append(heading_block(text, 3))
            else:
                blocks.append(paragraph_block(text))

        elif child.tag == W + "tbl":
            items = []
            for paragraph in child.findall(".//w:p", NS):
                text = paragraph_text(paragraph)
                if text:
                    items.append(text)
            blocks.append(list_block(items))

    blocks = add_internal_links(blocks)
    blocks.append("</div>\n<!-- /wp:group -->")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(blocks), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Uso: python scripts/convert_docx_to_wordpress.py input.docx output.html")

    convert(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
