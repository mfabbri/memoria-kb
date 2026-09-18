from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_ocr_pages_markdown(*, root_dir: Path, output_dir: Path, apply: bool = False) -> dict[str, Any]:
    """Render existing OCR layout rows as reviewable, page-scoped Markdown.

    The OCR strings are always enclosed in a literal text fence: this export
    records OCR output and deliberately does not interpret its Markdown shape.
    """
    root = Path(root_dir)
    destination = Path(output_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Root testi OCR non trovata: {root}")

    documents: list[dict[str, Any]] = []
    planned_outputs: set[Path] = set()
    for text_path in sorted(root.rglob("*.text.json")):
        documents.extend(_export_document(text_path=text_path, output_dir=destination, apply=apply, planned_outputs=planned_outputs))
    return {
        "@type": "OcrPageMarkdownExportReport",
        "root_dir": str(root),
        "output_dir": str(destination),
        "apply": apply,
        "documents": documents,
    }


def _export_document(*, text_path: Path, output_dir: Path, apply: bool, planned_outputs: set[Path]) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [{"status": "skipped_invalid_json", "text_path": str(text_path), "reason": f"{type(exc).__name__}: {exc}"}]
    if not isinstance(payload, dict) or payload.get("@type") != "ProcessedDocumentText":
        return [{"status": "skipped_invalid_document", "text_path": str(text_path), "reason": "ProcessedDocumentText non valido"}]
    if "ocr_quality_gate_status" in payload and payload.get("ocr_quality_gate_status") != "accepted":
        return [{"status": "skipped_insufficient_quality", "text_path": str(text_path), "reason": "OCR rifiutato dal quality gate"}]
    if "ocr_quality_gate_status" not in payload and payload.get("ocr_quality_status") != "usable_for_preview":
        return [{"status": "skipped_insufficient_quality", "text_path": str(text_path), "reason": "payload OCR legacy senza quality gate utilizzabile"}]
    source_document_id = str(payload.get("source_document_id", "")).strip()
    lines = payload.get("ocr_layout_lines")
    if not source_document_id or not isinstance(lines, list):
        return [{"status": "skipped_invalid_document", "text_path": str(text_path), "reason": "source_document_id o ocr_layout_lines non validi"}]

    pages: dict[str, list[dict[str, Any]]] = {}
    skipped_empty_lines = 0
    for line in lines:
        if isinstance(line, dict) and str(line.get("page_id", "")).strip() and _has_alphanumeric_text(line.get("text", "")):
            pages.setdefault(str(line["page_id"]), []).append(line)
        elif isinstance(line, dict):
            skipped_empty_lines += 1
    if not pages:
        return [{"status": "skipped_empty_layout", "text_path": str(text_path), "source_document_id": source_document_id, "reason": "ocr_layout_lines assente, vuoto o senza testo alfanumerico"}]

    results: list[dict[str, Any]] = []
    for page_id, page_lines in sorted(pages.items()):
        target = output_dir / _safe_path_part(source_document_id) / f"{_safe_path_part(page_id)}.md"
        item = {
            "text_path": str(text_path), "source_document_id": source_document_id,
            "page_id": page_id, "output_path": str(target), "line_count": len(page_lines), "skipped_empty_lines": skipped_empty_lines,
        }
        normalized_target = target.resolve()
        try:
            normalized_target.relative_to(output_dir.resolve())
        except ValueError:
            results.append({**item, "status": "skipped_unsafe_output", "reason": "percorso output non contenuto nella directory richiesta"})
            continue
        if normalized_target in planned_outputs:
            results.append({**item, "status": "skipped_duplicate_output", "reason": "output Markdown duplicato nella stessa esportazione"})
            continue
        planned_outputs.add(normalized_target)
        if target.exists():
            results.append({**item, "status": "skipped_existing_output", "reason": "output Markdown gia' presente"})
            continue
        if not apply:
            results.append({**item, "status": "would_write"})
            continue
        try:
            _write_exclusive(
                target,
                render_ocr_page_markdown(document=payload, page_id=page_id, lines=page_lines),
            )
        except FileExistsError:
            results.append({**item, "status": "skipped_existing_output", "reason": "output Markdown creato durante l'esportazione"})
            continue
        results.append({**item, "status": "written"})
    return results


def render_ocr_page_markdown(*, document: dict[str, Any], page_id: str, lines: list[dict[str, Any]]) -> str:
    """Return a literal OCR transcription page with traceable layout metadata."""
    rendered = [
        "# OCR page export", "", "Questo file riporta OCR non revisionato; non inferisce struttura semantica.", "",
        f"- Source document ID: `{_code(document.get('source_document_id', ''))}`",
        f"- Source file: `{_code(document.get('raw_file', ''))}`",
        f"- OCR engine: `{_code(document.get('ocr_engine', ''))}`",
        f"- OCR language: `{_code(document.get('ocr_language', ''))}`",
        f"- Page ID: `{_code(page_id)}`",
        f"- Review status: `{_code(document.get('review_status', 'unreviewed'))}`", "",
    ]
    for line in sorted(lines, key=lambda value: (_sort_order(value.get("read_order")), str(value.get("ocr_line_id", "")))):
        rendered.extend([
            f"## OCR line `{_code(line.get('ocr_line_id', ''))}`", "",
            f"- Region ID: `{_code(line.get('region_id', ''))}`",
            f"- Bounding box: `left={_integer(line.get('left'))}; top={_integer(line.get('top'))}; width={_integer(line.get('width'))}; height={_integer(line.get('height'))}`",
            f"- Confidence: `{_number(line.get('confidence'))}`",
            f"- Review status: `{_code(line.get('review_status', 'unreviewed'))}`",
            f"- Read order: `{_integer(line.get('read_order'))}` ({_code(line.get('read_order_status', ''))}; base: `{_code(line.get('read_order_basis', ''))}`)",
            "- OCR text (untrusted):", "", _literal_fence(str(line.get("text", ""))), "",
        ])
    return "\n".join(rendered).rstrip() + "\n"


def _literal_fence(text: str) -> str:
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}text\n{text}\n{fence}"


def _code(value: object) -> str:
    return " ".join(str(value).replace("`", "'").splitlines())


def _safe_path_part(value: str) -> str:
    candidate = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-")
    return candidate if candidate not in {"", ".", ".."} else "unknown"


def _integer(value: object) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "unknown"


def _number(value: object) -> str:
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return "unknown"


def _sort_order(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _has_alphanumeric_text(value: object) -> bool:
    return any(character.isalnum() for character in str(value))


def _write_exclusive(path: Path, text: str) -> None:
    """Create an export once; never replace a file created by another process."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)
