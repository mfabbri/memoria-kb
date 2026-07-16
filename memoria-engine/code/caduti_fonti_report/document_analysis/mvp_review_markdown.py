from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def parse_review_table(path: Path, *, table_columns: list[str]) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [unescape_cell(cell.strip()) for cell in stripped.strip("|").split("|")]
        if len(cells) != len(table_columns):
            continue
        normalized = [cell.strip().casefold() for cell in cells]
        if normalized == table_columns:
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(dict(zip(table_columns, cells)))
    rows.extend(parse_review_cards(text))
    return rows


def parse_review_cards(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current_item_id = ""
    current_allowed_decisions = ""
    in_decision_table = False
    for line in text.splitlines():
        stripped = line.strip()
        item_match = re.match(r"^##\s+\d+\.\s+.*?(mvp-review-item:[^\s`]+)", stripped)
        if item_match:
            current_item_id = item_match.group(1)
            current_allowed_decisions = ""
            in_decision_table = False
            continue
        if current_item_id and stripped.startswith("Azioni ammesse:"):
            current_allowed_decisions = stripped.split(":", 1)[1].strip().strip("`")
            continue
        if stripped == "| selected_action | reviewer | reviewed_at | note |":
            in_decision_table = True
            continue
        if not in_decision_table or not current_item_id:
            continue
        if not stripped.startswith("|") or not stripped.endswith("|"):
            in_decision_table = False
            continue
        cells = [unescape_cell(cell.strip()) for cell in stripped.strip("|").split("|")]
        if len(cells) != 4:
            in_decision_table = False
            continue
        normalized = [cell.strip().casefold() for cell in cells]
        if normalized == ["selected_action", "reviewer", "reviewed_at", "note"]:
            continue
        if all(is_markdown_separator_cell(cell) for cell in cells):
            continue
        rows.append(
            {
                "selected_action": cells[0],
                "reviewer": cells[1],
                "reviewed_at": cells[2],
                "item_id": current_item_id,
                "profilo": "",
                "tipo": "",
                "oggetto": "",
                "azioni_ammesse": current_allowed_decisions,
                "documento": "",
                "documento_label": "",
                "riferimento_documento": "",
                "domanda": "",
                "contesto": "",
                "note": cells[3],
            }
        )
        in_decision_table = False
    return rows


def is_markdown_separator_cell(cell: str) -> bool:
    stripped = cell.strip()
    return bool(stripped) and set(stripped) <= {"-", ":"}


def markdown_table_header(columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    return header + "\n" + separator


def escape_cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("\r", " ").replace("|", "&#124;").strip()


def unescape_cell(value: str) -> str:
    return value.replace("&#124;", "|").strip()


def shorten(value: Any, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def split_list(value: Any) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]
