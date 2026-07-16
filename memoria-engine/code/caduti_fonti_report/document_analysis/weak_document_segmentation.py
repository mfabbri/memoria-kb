from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .document_chunking import detect_text_quality_warnings

PERSON_NAME_PATTERN = re.compile(
    r"\b[A-Z][a-zA-ZÀ-ÖØ-öø-ÿ'’-]{2,}\s+[A-Z][a-zA-ZÀ-ÖØ-öø-ÿ'’-]{2,}\b"
)
FORMATION_PATTERN = re.compile(
    r"\b(?:brigata|divisione|distaccamento|formazione|garibaldi|giustizia\s+e\s+liberta|partigian[oaie])\b",
    re.IGNORECASE,
)
ARCHIVAL_REFERENCE_PATTERN = re.compile(
    r"\b(?:RH\s*\d+(?:/\d+)+|busta\s+\d+|fasc\.?\s*\d+|fascicolo\s+\d+|segnatura|archivio|fondo)\b",
    re.IGNORECASE,
)

SEGMENT_RULES = (
    ("archival_reference_context", ARCHIVAL_REFERENCE_PATTERN, "archival_reference_signal", 0.72),
    ("formation_context", FORMATION_PATTERN, "resistance_formation_signal", 0.68),
    ("person_mention_context", PERSON_NAME_PATTERN, "capitalized_person_like_name_signal", 0.6),
)


def weak_segment_document_chunks(
    *,
    chunk_dir: Path,
    output_dir: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
    chunk_paths: list[Path] | None = None,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    paths = sorted(chunk_paths) if chunk_paths is not None else sorted(chunk_dir.rglob("*.chunks.json"))
    for chunk_path in paths:
        payload = _load_json_object(chunk_path)
        skip_reason = _skip_reason(payload=payload)
        if skip_reason:
            skipped.append(_skip_record(payload=payload, chunk_path=chunk_path, reason=skip_reason))
            continue

        document_segments = _segments_for_document(payload=payload, chunk_path=chunk_path)
        document_entry = {
            "@type": "WeakDocumentSegmentDocument",
            "source_id": str(payload.get("source_id", "")),
            "source_document_id": str(payload.get("source_document_id", "")),
            "chunk_file": str(chunk_path),
            "segments_file": str(_segment_output_path(payload=payload, output_dir=output_dir) or ""),
            "review_status": "unreviewed",
            "segment_count": len(document_segments),
            "segments": document_segments,
        }
        documents.append(document_entry)
        if output_dir is not None:
            segment_path = output_dir / _segment_relative_path(document_entry)
            segment_path.parent.mkdir(parents=True, exist_ok=True)
            segment_path.write_text(json.dumps(document_entry, ensure_ascii=False, indent=2), encoding="utf-8")

    segment_count = sum(int(document.get("segment_count", 0) or 0) for document in documents)
    result = {
        "@type": "WeakDocumentSegmentSet",
        "chunk_dir": str(chunk_dir),
        "output_dir": str(output_dir or ""),
        "segmentation_method": "deterministic_weak_segment_rules",
        "document_count": len(documents),
        "segment_count": segment_count,
        "skipped_count": len(skipped),
        "documents": documents,
        "skipped_documents": skipped,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_weak_segments_markdown(result), encoding="utf-8")
    return result


def render_weak_segments_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# WeakDocumentSegment preview",
        "",
        f"- Metodo: `{payload.get('segmentation_method', '')}`",
        f"- Documenti processati: `{payload.get('document_count', 0)}`",
        f"- Segmenti generati: `{payload.get('segment_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Segmenti deboli",
        "",
    ]
    documents = payload.get("documents", [])
    if not isinstance(documents, list) or not documents:
        lines.append("_Nessun segmento generato._")
    else:
        for document in documents:
            if not isinstance(document, dict):
                continue
            lines.extend(
                [
                    f"### {document.get('source_document_id', '')}",
                    "",
                    f"- Fonte: `{document.get('source_id', '')}`",
                    f"- Stato revisione: `{document.get('review_status', '')}`",
                    f"- Segmenti: `{document.get('segment_count', 0)}`",
                    f"- Chunk: `{document.get('chunk_file', '')}`",
                    "",
                ]
            )
            for segment in document.get("segments", []):
                if not isinstance(segment, dict):
                    continue
                lines.append(
                    f"- `{segment.get('segment_id', '')}` | "
                    f"{segment.get('segment_type', '')} | "
                    f"chunk `{segment.get('chunk_index', '')}` | "
                    f"{segment.get('chunk_char_start', '')}-{segment.get('chunk_char_end', '')} | "
                    f"confidence `{segment.get('confidence', '')}`"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _segments_for_document(*, payload: dict[str, Any], chunk_path: Path) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    segment_index = 1
    for chunk in payload.get("chunks", []):
        if not isinstance(chunk, dict):
            continue
        text = str(chunk.get("text", ""))
        chunk_warnings = _warnings_from_chunk(chunk)
        for start, end, sentence in _sentence_windows(text):
            matched = _matched_rules(sentence)
            if not matched:
                continue
            segment_type, matched_rules, confidence = _segment_classification(matched)
            text_quality_warnings = _unique_warnings(
                [*chunk_warnings, *detect_text_quality_warnings(sentence)]
            )
            segment_id = _segment_id(
                source_document_id=str(payload.get("source_document_id", "")),
                chunk_id=str(chunk.get("chunk_id", "")),
                segment_index=segment_index,
                start=start,
                end=end,
            )
            segments.append(
                {
                    "@type": "WeakDocumentSegment",
                    "@id": segment_id,
                    "segment_id": segment_id,
                    "source_id": str(payload.get("source_id", "")),
                    "source_document_id": str(payload.get("source_document_id", "")),
                    "chunk_file": str(chunk_path),
                    "chunk_id": str(chunk.get("chunk_id", "")),
                    "chunk_index": int(chunk.get("chunk_index", 0) or 0),
                    "segment_index": segment_index,
                    "segment_type": segment_type,
                    "chunk_char_start": start,
                    "chunk_char_end": end,
                    "text": sentence,
                    "text_sha256": hashlib.sha256(sentence.encode("utf-8")).hexdigest(),
                    "matched_rules": matched_rules,
                    "confidence": confidence,
                    "segmentation_method": "deterministic_weak_segment_rules",
                    "recommended_use": "manual_review_search_hint",
                    "claim_extraction_allowed": False,
                    "text_quality_warnings": text_quality_warnings,
                    "review_status": "unreviewed",
                    "warnings": _unique_warnings(["weak_segment_not_verified_fact", *text_quality_warnings]),
                }
            )
            segment_index += 1
    return segments


def _sentence_windows(text: str) -> list[tuple[int, int, str]]:
    windows: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[^.!?\n\r;]{1,600}(?:[.!?;\n\r]+|$)", text):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        start = match.start() + len(match.group(0)) - len(match.group(0).lstrip())
        end = start + len(sentence)
        windows.append((start, end, sentence))
    return windows


def _matched_rules(text: str) -> list[tuple[str, str, float]]:
    matched: list[tuple[str, str, float]] = []
    for segment_type, pattern, rule_name, confidence in SEGMENT_RULES:
        if pattern.search(text):
            matched.append((segment_type, rule_name, confidence))
    return matched


def _segment_classification(matched: list[tuple[str, str, float]]) -> tuple[str, list[str], float]:
    ranked = sorted(matched, key=lambda item: (-item[2], item[0]))
    segment_type = ranked[0][0]
    rules = [item[1] for item in ranked]
    confidence = max(item[2] for item in ranked)
    if len(ranked) > 1:
        confidence = min(0.82, confidence + 0.06)
    return segment_type, rules, round(confidence, 2)


def _warnings_from_chunk(chunk: dict[str, Any]) -> list[str]:
    warnings = chunk.get("text_quality_warnings", [])
    if isinstance(warnings, list):
        return [str(warning) for warning in warnings if str(warning).strip()]
    return []


def _unique_warnings(warnings: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        warning = str(warning).strip()
        if not warning or warning in seen:
            continue
        seen.add(warning)
        unique.append(warning)
    return unique


def _skip_reason(*, payload: dict[str, Any]) -> str:
    if not payload:
        return "chunk_unreadable"
    if str(payload.get("@type", "")) != "PhysicalDocumentChunkDocument":
        return "unsupported_payload_type"
    chunks = payload.get("chunks", [])
    if not isinstance(chunks, list) or not chunks:
        return "empty_chunks"
    return ""


def _skip_record(*, payload: dict[str, Any], chunk_path: Path, reason: str) -> dict[str, str]:
    return {
        "source_document_id": str(payload.get("source_document_id", "")) if payload else "",
        "chunk_file": str(chunk_path),
        "reason": reason,
    }


def _segment_relative_path(document: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(document.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(document.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.weak-segments.json"


def _segment_output_path(*, payload: dict[str, Any], output_dir: Path | None) -> Path | None:
    if output_dir is None:
        return None
    return output_dir / _segment_relative_path(
        {
            "source_id": str(payload.get("source_id", "")),
            "source_document_id": str(payload.get("source_document_id", "")),
        }
    )


def _segment_id(*, source_document_id: str, chunk_id: str, segment_index: int, start: int, end: int) -> str:
    digest = hashlib.sha256(
        f"{source_document_id}|{chunk_id}|{segment_index}|{start}|{end}".encode("utf-8")
    ).hexdigest()[:16]
    return f"weak-document-segment:{digest}"


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera WeakDocumentSegment preview-only da PhysicalDocumentChunk.")
    parser.add_argument("--chunk-dir", default="data/processed/documents")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/weak_document_segments.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/weak_document_segments.md")
    args = parser.parse_args()

    payload = weak_segment_document_chunks(
        chunk_dir=Path(args.chunk_dir),
        output_dir=Path(args.output_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"WeakDocumentSegment JSON scritto in {args.output_json}")
    print(f"WeakDocumentSegment Markdown scritto in {args.output_md}")
    print(f"Documenti processati: {payload['document_count']}")
    print(f"Segmenti generati: {payload['segment_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
