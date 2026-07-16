from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


def extract_document_text(
    *,
    metadata_dir: Path,
    output_dir: Path,
    raw_root_dir: Path,
    metadata_paths: list[Path] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    processed = []
    paths = sorted(metadata_paths) if metadata_paths is not None else sorted(metadata_dir.rglob("*.metadata.json"))
    for metadata_path in paths:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            continue
        document_text = _processed_text(metadata, metadata_path=metadata_path, raw_root_dir=raw_root_dir)
        text_path = output_dir / _text_relative_path(document_text)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(json.dumps(document_text, ensure_ascii=False, indent=2), encoding="utf-8")
        processed.append(
            {
                "source_document_id": document_text["source_document_id"],
                "text_path": str(text_path),
                "document_class": document_text["document_class"],
                "claim_eligible": document_text["claim_eligible"],
                "text_status": document_text["text_status"],
                "extraction_status": document_text["extraction_status"],
            }
        )

    extracted_count = sum(1 for item in processed if item["text_status"] == "extracted")
    extraction_status_counts = Counter(str(item.get("extraction_status", "")) for item in processed)
    document_class_counts = Counter(str(item.get("document_class", "")) for item in processed)
    return {
        "@type": "ProcessedDocumentTextSet",
        "metadata_dir": str(metadata_dir),
        "raw_root_dir": str(raw_root_dir),
        "output_dir": str(output_dir),
        "document_count": len(processed),
        "extracted_count": extracted_count,
        "skipped_count": len(processed) - extracted_count,
        "extraction_status_counts": dict(sorted(extraction_status_counts.items())),
        "document_class_counts": dict(sorted(document_class_counts.items())),
        "documents": processed,
    }


def _processed_text(metadata: dict[str, Any], *, metadata_path: Path, raw_root_dir: Path) -> dict[str, Any]:
    media_type = str(metadata.get("media_type", ""))
    raw_file = str(metadata.get("raw_file", ""))
    text = ""
    extraction_status = "skipped_unsupported_media_type"
    text_status = "not_extracted"

    if media_type.startswith("image/"):
        extraction_status = "manual_ocr_required"
    elif not raw_file.strip():
        extraction_status = "raw_file_missing"
    else:
        raw_path = _resolve_raw_path(raw_file, raw_root_dir=raw_root_dir)
        if not raw_path.exists() or not raw_path.is_file():
            extraction_status = "raw_file_not_found"
        elif _is_docx(media_type, raw_path):
            try:
                text = _normalize_text(_docx_to_text(raw_path))
                extraction_status = "text_extracted"
                text_status = "extracted"
            except (KeyError, ElementTree.ParseError, zipfile.BadZipFile):
                extraction_status = "docx_read_error"
        elif _is_csv(media_type, raw_path):
            try:
                text = _normalize_text(_csv_to_text(raw_path))
                extraction_status = "text_extracted"
                text_status = "extracted"
            except (OSError, UnicodeDecodeError, csv.Error):
                extraction_status = "csv_read_error"
        elif _is_extractable_text_document(media_type=media_type, raw_path=raw_path):
            raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
            text = _normalize_text(_html_to_text(raw_text) if _is_html(media_type, raw_path) else raw_text)
            extraction_status = "text_extracted"
            text_status = "extracted"

    return {
        "@type": "ProcessedDocumentText",
        "source_id": str(metadata.get("source_id", "")),
        "source_document_id": str(metadata.get("source_document_id", "")),
        "document_class": str(metadata.get("document_class", "")),
        "claim_eligible": bool(metadata.get("claim_eligible", False)),
        "review_status": str(metadata.get("review_status", "")) or "unreviewed",
        "raw_file": raw_file,
        "metadata_file": str(metadata_path),
        "media_type": media_type,
        "extraction_status": extraction_status,
        "text_status": text_status,
        "text": text,
        "text_length": len(text),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
    }


def _resolve_raw_path(raw_file: str, *, raw_root_dir: Path) -> Path:
    raw_path = Path(raw_file)
    if raw_path.is_absolute():
        return raw_path
    return raw_root_dir / raw_path


def _is_extractable_text_document(*, media_type: str, raw_path: Path) -> bool:
    return media_type in {"text/plain", "text/html", "application/xhtml+xml"} or raw_path.suffix.casefold() in {
        ".txt",
        ".html",
        ".htm",
    }


def _is_html(media_type: str, raw_path: Path) -> bool:
    return media_type in {"text/html", "application/xhtml+xml"} or raw_path.suffix.casefold() in {".html", ".htm"}


def _is_docx(media_type: str, raw_path: Path) -> bool:
    return (
        media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or raw_path.suffix.casefold() == ".docx"
    )


def _is_csv(media_type: str, raw_path: Path) -> bool:
    return media_type == "text/csv" or raw_path.suffix.casefold() == ".csv"


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _csv_to_text(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(handle, dialect))
    if not rows:
        return ""
    header = [cell.strip() for cell in rows[0]]
    lines: list[str] = []
    for index, row in enumerate(rows[1:] if header else rows, start=1):
        cells = [cell.strip() for cell in row]
        if not any(cells):
            continue
        if header and any(header):
            pairs = []
            for column_index, value in enumerate(cells):
                label = header[column_index] if column_index < len(header) and header[column_index] else f"colonna_{column_index + 1}"
                if value:
                    pairs.append(f"{label}: {value}")
            if pairs:
                lines.append(f"Riga {index}. " + "; ".join(pairs))
        else:
            lines.append(f"Riga {index}. " + "; ".join(value for value in cells if value))
    return "\n".join(lines)


def _docx_to_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:body//w:p", namespace):
        parts: list[str] = []
        for node in paragraph.iter():
            tag = _local_name(node.tag)
            if tag == "t" and node.text:
                parts.append(node.text)
            elif tag == "tab":
                parts.append(" ")
            elif tag in {"br", "cr"}:
                parts.append("\n")
        paragraph_text = "".join(parts).strip()
        if paragraph_text:
            paragraphs.append(paragraph_text)
    return "\n".join(paragraphs)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _html_to_text(raw_html: str) -> str:
    parser = _ReadableHtmlParser()
    parser.feed(raw_html)
    parser.close()
    return parser.text()


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        return " ".join(self._parts)


def _text_relative_path(document_text: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(document_text.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(document_text.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.text.json"


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Estrae testo offline da metadati documentali HTML/testo/DOCX.")
    parser.add_argument("--metadata-dir", default="data/processed/documents")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--raw-root-dir", default="data/raw")
    parser.add_argument("--summary-json", default="risultati/document_analysis/document_text_extraction.json")
    args = parser.parse_args()

    summary = extract_document_text(
        metadata_dir=Path(args.metadata_dir),
        output_dir=Path(args.output_dir),
        raw_root_dir=Path(args.raw_root_dir),
    )
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Testi processati scritti in {args.output_dir}")
    print(f"Summary JSON scritto in {summary_path}")
    print(f"Documenti processati: {summary['document_count']}")
    print(f"Documenti estratti: {summary['extracted_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
