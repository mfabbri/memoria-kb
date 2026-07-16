from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_MAX_CHARS = 4500
DEFAULT_OVERLAP_CHARS = 300
DEFAULT_BOUNDARY_SEARCH_CHARS = 500
SKIPPED_DOCUMENT_CLASSES = {"result_page", "reference_page"}
MOJIBAKE_MARKERS = ("\ufffd", "\u00c3", "\u00c2", "\u00e2\u20ac")
PARAGRAPH_BOUNDARIES = ("\n\n", "\r\n\r\n")
SENTENCE_BOUNDARIES = (". ", "! ", "? ", ".\n", "!\n", "?\n", "; ")


def chunk_document_texts(
    *,
    text_dir: Path,
    output_dir: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    text_paths: list[Path] | None = None,
) -> dict[str, Any]:
    max_chars = _bounded_positive_int(max_chars, DEFAULT_MAX_CHARS)
    overlap_chars = max(0, min(_bounded_positive_int(overlap_chars, DEFAULT_OVERLAP_CHARS), max_chars - 1))
    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    paths = sorted(text_paths) if text_paths is not None else sorted(text_dir.rglob("*.text.json"))
    for text_path in paths:
        payload = _load_json_object(text_path)
        skip_reason = _skip_reason(payload=payload)
        if skip_reason:
            skipped.append(_skip_record(payload=payload, text_path=text_path, reason=skip_reason))
            continue

        document_chunks = _chunks_for_document(
            payload=payload,
            text_path=text_path,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        )
        chunk_path = _chunk_output_path(payload=payload, output_dir=output_dir)
        document_entry = {
            "@type": "PhysicalDocumentChunkDocument",
            "source_id": str(payload.get("source_id", "")),
            "source_document_id": str(payload.get("source_document_id", "")),
            "document_class": str(payload.get("document_class", "")),
            "review_status": str(payload.get("review_status", "")) or "unreviewed",
            "text_file": str(text_path),
            "chunk_file": str(chunk_path or ""),
            "text_sha256": str(payload.get("text_sha256", "")),
            "chunk_count": len(document_chunks),
            "chunks": document_chunks,
        }
        documents.append(document_entry)
        if output_dir is not None:
            chunk_path = output_dir / _chunk_relative_path(document_entry)
            chunk_path.parent.mkdir(parents=True, exist_ok=True)
            chunk_path.write_text(json.dumps(document_entry, ensure_ascii=False, indent=2), encoding="utf-8")

    chunk_count = sum(int(document.get("chunk_count", 0) or 0) for document in documents)
    payload = {
        "@type": "PhysicalDocumentChunkSet",
        "text_dir": str(text_dir),
        "output_dir": str(output_dir or ""),
        "chunking_method": "fixed_window_chunking",
        "max_chars": max_chars,
        "overlap_chars": overlap_chars,
        "document_count": len(documents),
        "chunk_count": chunk_count,
        "skipped_count": len(skipped),
        "documents": documents,
        "skipped_documents": skipped,
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_document_chunks_markdown(payload), encoding="utf-8")

    return payload


def render_document_chunks_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# PhysicalDocumentChunk preview",
        "",
        f"- Metodo: `{payload.get('chunking_method', '')}`",
        f"- Dimensione massima chunk: `{payload.get('max_chars', '')}`",
        f"- Overlap caratteri: `{payload.get('overlap_chars', '')}`",
        f"- Documenti processati: `{payload.get('document_count', 0)}`",
        f"- Chunk generati: `{payload.get('chunk_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Documenti chunked",
        "",
    ]
    documents = payload.get("documents", [])
    if not isinstance(documents, list) or not documents:
        lines.append("_Nessun chunk generato._")
    else:
        for document in documents:
            if not isinstance(document, dict):
                continue
            lines.extend(
                [
                    f"### {document.get('source_document_id', '')}",
                    "",
                    f"- Fonte: `{document.get('source_id', '')}`",
                    f"- Classe documento: `{document.get('document_class', '')}`",
                    f"- Stato revisione: `{document.get('review_status', '')}`",
                    f"- Chunk: `{document.get('chunk_count', 0)}`",
                    f"- Testo: `{document.get('text_file', '')}`",
                    "",
                ]
            )
            for chunk in document.get("chunks", []):
                if not isinstance(chunk, dict):
                    continue
                lines.append(
                    f"- `{chunk.get('chunk_id', '')}` | "
                    f"{chunk.get('char_start', '')}-{chunk.get('char_end', '')} | "
                    f"overlap prev=`{chunk.get('overlap_previous', '')}` next=`{chunk.get('overlap_next', '')}`"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _chunks_for_document(
    *,
    payload: dict[str, Any],
    text_path: Path,
    max_chars: int,
    overlap_chars: int,
) -> list[dict[str, Any]]:
    text = str(payload.get("text", ""))
    source_document_id = str(payload.get("source_document_id", ""))
    chunks: list[dict[str, Any]] = []
    start = 0
    index = 1
    while start < len(text):
        fixed_end = min(len(text), start + max_chars)
        boundary = _choose_chunk_boundary(text=text, start=start, fixed_end=fixed_end)
        end = boundary["end"]
        chunk_text = text[start:end]
        chunk_id = _chunk_id(source_document_id=source_document_id, index=index, start=start, end=end)
        text_quality_warnings = detect_text_quality_warnings(chunk_text)
        chunks.append(
            {
                "@type": "PhysicalDocumentChunk",
                "@id": chunk_id,
                "chunk_id": chunk_id,
                "source_id": str(payload.get("source_id", "")),
                "source_document_id": source_document_id,
                "text_file": str(text_path),
                "source_text_sha256": str(payload.get("text_sha256", "")),
                "chunk_index": index,
                "char_start": start,
                "char_end": end,
                "token_estimate": _token_estimate(chunk_text),
                "overlap_previous": start > 0,
                "overlap_next": end < len(text),
                "text": chunk_text,
                "chunk_text_sha256": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                "extraction_method": "fixed_window_chunking",
                "boundary_strategy": boundary["strategy"],
                "boundary_adjusted": boundary["adjusted"],
                "boundary_reason": boundary["reason"],
                "text_quality_warnings": text_quality_warnings,
                "review_status": "unreviewed",
            }
        )
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
        index += 1
    return chunks


def _skip_reason(*, payload: dict[str, Any]) -> str:
    if not payload:
        return "text_unreadable"
    if str(payload.get("@type", "")) != "ProcessedDocumentText":
        return "unsupported_payload_type"
    if str(payload.get("document_class", "")) in SKIPPED_DOCUMENT_CLASSES:
        return f"skipped_{payload.get('document_class', '')}"
    if str(payload.get("text_status", "")) != "extracted":
        return "text_not_extracted"
    if not str(payload.get("text", "")).strip():
        return "empty_text"
    return ""


def _skip_record(*, payload: dict[str, Any], text_path: Path, reason: str) -> dict[str, str]:
    return {
        "source_document_id": str(payload.get("source_document_id", "")) if payload else "",
        "text_file": str(text_path),
        "reason": reason,
    }


def _chunk_relative_path(document: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(document.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(document.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.chunks.json"


def _chunk_output_path(*, payload: dict[str, Any], output_dir: Path | None) -> Path | None:
    if output_dir is None:
        return None
    return output_dir / _chunk_relative_path(
        {
            "source_id": str(payload.get("source_id", "")),
            "source_document_id": str(payload.get("source_document_id", "")),
        }
    )


def _chunk_id(*, source_document_id: str, index: int, start: int, end: int) -> str:
    digest = hashlib.sha256(f"{source_document_id}|{index}|{start}|{end}".encode("utf-8")).hexdigest()[:16]
    return f"physical-document-chunk:{digest}"


def _token_estimate(text: str) -> int:
    return len([token for token in text.split() if token])


def detect_text_quality_warnings(text: str) -> list[str]:
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        return ["encoding_suspect_mojibake"]
    return []


def _choose_chunk_boundary(*, text: str, start: int, fixed_end: int) -> dict[str, Any]:
    if fixed_end >= len(text):
        return {
            "end": fixed_end,
            "strategy": "document_end",
            "adjusted": False,
            "reason": "reached_document_end",
        }

    window_start = max(start + 1, fixed_end - DEFAULT_BOUNDARY_SEARCH_CHARS)
    minimum_end = start + max(1, int((fixed_end - start) * 0.6))
    paragraph_end = _last_boundary_end(text=text, window_start=window_start, fixed_end=fixed_end, markers=PARAGRAPH_BOUNDARIES)
    if paragraph_end and paragraph_end >= minimum_end:
        return {
            "end": paragraph_end,
            "strategy": "paragraph_near_limit",
            "adjusted": paragraph_end != fixed_end,
            "reason": "paragraph_boundary_before_max_chars",
        }

    sentence_end = _last_boundary_end(text=text, window_start=window_start, fixed_end=fixed_end, markers=SENTENCE_BOUNDARIES)
    if sentence_end and sentence_end >= minimum_end:
        return {
            "end": sentence_end,
            "strategy": "sentence_near_limit",
            "adjusted": sentence_end != fixed_end,
            "reason": "sentence_boundary_before_max_chars",
        }

    whitespace_end = _last_whitespace_boundary(text=text, window_start=window_start, fixed_end=fixed_end)
    if whitespace_end and whitespace_end >= minimum_end:
        return {
            "end": whitespace_end,
            "strategy": "whitespace_near_limit",
            "adjusted": whitespace_end != fixed_end,
            "reason": "word_boundary_before_max_chars",
        }

    return {
        "end": fixed_end,
        "strategy": "fixed_window_fallback",
        "adjusted": False,
        "reason": "no_reliable_boundary_near_limit",
    }


def _last_boundary_end(*, text: str, window_start: int, fixed_end: int, markers: tuple[str, ...]) -> int | None:
    best_end: int | None = None
    window = text[window_start:fixed_end]
    for marker in markers:
        position = window.rfind(marker)
        if position < 0:
            continue
        candidate_end = window_start + position + len(marker)
        if best_end is None or candidate_end > best_end:
            best_end = candidate_end
    return best_end


def _last_whitespace_boundary(*, text: str, window_start: int, fixed_end: int) -> int | None:
    for index in range(fixed_end - 1, window_start - 1, -1):
        if text[index].isspace():
            return index + 1
    return None


def _bounded_positive_int(value: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera PhysicalDocumentChunk preview-only da testi processati.")
    parser.add_argument("--text-dir", default="data/processed/documents")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/document_chunks.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/document_chunks.md")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--overlap-chars", type=int, default=DEFAULT_OVERLAP_CHARS)
    args = parser.parse_args()

    payload = chunk_document_texts(
        text_dir=Path(args.text_dir),
        output_dir=Path(args.output_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
        max_chars=args.max_chars,
        overlap_chars=args.overlap_chars,
    )
    print(f"PhysicalDocumentChunk JSON scritto in {args.output_json}")
    print(f"PhysicalDocumentChunk Markdown scritto in {args.output_md}")
    print(f"Documenti processati: {payload['document_count']}")
    print(f"Chunk generati: {payload['chunk_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
