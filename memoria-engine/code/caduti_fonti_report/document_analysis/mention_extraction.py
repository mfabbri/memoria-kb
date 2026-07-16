from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Pattern

PERSON_NAME_PATTERN = re.compile(
    r"\b[A-Z][a-zA-ZÀ-ÖØ-öø-ÿ'’-]{2,}\s+[A-Z][a-zA-ZÀ-ÖØ-öø-ÿ'’-]{2,}\b"
)
FORMATION_PATTERN = re.compile(
    r"\b(?:\d{1,3}\s*(?:a|ma|ª)?\s+)?"
    r"(?:brigata|brg\.?|divisione|distaccamento|formazione)"
    r"(?:\s+[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’-]+){0,4}\b"
    r"|\bGaribaldi\b|\bGiustizia\s+e\s+Liberta\b",
    re.IGNORECASE,
)
ARCHIVAL_REFERENCE_PATTERN = re.compile(
    r"\b(?:BArch,\s*)?RH\s*\d+(?:[-/]\d+){1,4}\b"
    r"|\b(?:busta|fasc\.?|fascicolo)\s+\d+\b"
    r"|\b(?:segnatura|archivio|fondo)\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}\s+"
    r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
    r"\s+\d{4}"
    r"|(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
    r"\s+\d{4}"
    r")\b",
    re.IGNORECASE,
)
PLACE_PATTERN = re.compile(
    r"(?<![\w])(?:"
    r"Ca['â€™]\s+di\s+Malanca"
    r"|Purocielo"
    r"|Monte\s+Battaglia"
    r"|Bologna"
    r"|Imola"
    r"|Faenza"
    r"|Brisighella"
    r"|Modigliana"
    r"|Marradi"
    r"|Casola\s+Valsenio"
    r"|Ravenna"
    r"|Forli"
    r")(?![\w])",
    re.IGNORECASE,
)
PERSON_FALSE_POSITIVE_TOKENS = {
    "atti",
    "centro",
    "documenti",
    "home",
    "info",
    "informazioni",
    "malanca",
    "menu",
    "mostra",
    "pag",
    "pagina",
    "quando",
    "salta",
    "statuto",
    "video",
    "visita",
}


@dataclass(frozen=True)
class MentionRule:
    mention_type: str
    mention_kind: str
    pattern: Pattern[str]
    reason: str
    confidence: float


MENTION_RULES = (
    MentionRule(
        mention_type="DateMentionCandidate",
        mention_kind="date",
        pattern=DATE_PATTERN,
        reason="explicit_date_pattern",
        confidence=0.74,
    ),
    MentionRule(
        mention_type="PlaceMentionCandidate",
        mention_kind="place",
        pattern=PLACE_PATTERN,
        reason="curated_place_name_pattern",
        confidence=0.66,
    ),
    MentionRule(
        mention_type="ArchivalReferenceMentionCandidate",
        mention_kind="archival_reference",
        pattern=ARCHIVAL_REFERENCE_PATTERN,
        reason="archival_reference_pattern",
        confidence=0.78,
    ),
    MentionRule(
        mention_type="FormationMentionCandidate",
        mention_kind="formation",
        pattern=FORMATION_PATTERN,
        reason="formation_pattern",
        confidence=0.7,
    ),
    MentionRule(
        mention_type="PersonMentionCandidate",
        mention_kind="person",
        pattern=PERSON_NAME_PATTERN,
        reason="capitalized_person_like_name_pattern",
        confidence=0.62,
    ),
)


def extract_document_mentions(
    *,
    segments_dir: Path,
    output_dir: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
    segment_paths: list[Path] | None = None,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    paths = sorted(segment_paths) if segment_paths is not None else sorted(segments_dir.rglob("*.weak-segments.json"))
    for segments_path in paths:
        payload = _load_json_object(segments_path)
        skip_reason = _skip_reason(payload=payload)
        if skip_reason:
            skipped.append(_skip_record(payload=payload, segments_path=segments_path, reason=skip_reason))
            continue

        mentions = _mentions_for_document(payload=payload, segments_path=segments_path)
        document_entry = {
            "@type": "DocumentMentionCandidateDocument",
            "source_id": str(payload.get("source_id", "")),
            "source_document_id": str(payload.get("source_document_id", "")),
            "segments_file": str(segments_path),
            "mentions_file": str(_mentions_output_path(payload=payload, output_dir=output_dir) or ""),
            "review_status": "unreviewed",
            "mention_count": len(mentions),
            "mentions": mentions,
        }
        documents.append(document_entry)
        if output_dir is not None:
            mention_path = output_dir / _mentions_relative_path(document_entry)
            mention_path.parent.mkdir(parents=True, exist_ok=True)
            mention_path.write_text(json.dumps(document_entry, ensure_ascii=False, indent=2), encoding="utf-8")

    mention_count = sum(int(document.get("mention_count", 0) or 0) for document in documents)
    result = {
        "@type": "DocumentMentionCandidateSet",
        "segments_dir": str(segments_dir),
        "output_dir": str(output_dir or ""),
        "extraction_method": "deterministic_mention_candidate_rules",
        "document_count": len(documents),
        "mention_count": mention_count,
        "skipped_count": len(skipped),
        "documents": documents,
        "skipped_documents": skipped,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_document_mentions_markdown(result), encoding="utf-8")
    return result


def render_document_mentions_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DocumentMentionCandidate preview",
        "",
        f"- Metodo: `{payload.get('extraction_method', '')}`",
        f"- Documenti processati: `{payload.get('document_count', 0)}`",
        f"- Menzioni candidate: `{payload.get('mention_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Menzioni candidate",
        "",
    ]
    documents = payload.get("documents", [])
    if not isinstance(documents, list) or not documents:
        lines.append("_Nessuna menzione candidata estratta._")
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
                    f"- Menzioni: `{document.get('mention_count', 0)}`",
                    f"- Segmenti: `{document.get('segments_file', '')}`",
                    "",
                ]
            )
            for mention in document.get("mentions", []):
                if not isinstance(mention, dict):
                    continue
                lines.append(
                    f"- `{mention.get('mention_id', '')}` | "
                    f"{mention.get('mention_kind', '')} | "
                    f"`{mention.get('value', '')}` | "
                    f"confidence `{mention.get('confidence', '')}`"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _mentions_for_document(*, payload: dict[str, Any], segments_path: Path) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for segment in payload.get("segments", []):
        if not isinstance(segment, dict):
            continue
        segment_text = str(segment.get("text", ""))
        for rule in MENTION_RULES:
            if not _rule_allowed_for_segment(rule=rule, segment=segment):
                continue
            for match in rule.pattern.finditer(segment_text):
                value = _clean_value(rule.mention_kind, match.group(0))
                if not value:
                    continue
                mentions.append(
                    _mention_candidate(
                        payload=payload,
                        segment=segment,
                        segments_path=segments_path,
                        rule=rule,
                        value=value,
                        start=match.start(),
                        end=match.end(),
                    )
                )
    return _deduplicate_mentions(mentions)


def _mention_candidate(
    *,
    payload: dict[str, Any],
    segment: dict[str, Any],
    segments_path: Path,
    rule: MentionRule,
    value: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    source_document_id = str(payload.get("source_document_id") or segment.get("source_document_id") or "")
    source_id = str(payload.get("source_id") or segment.get("source_id") or "")
    normalized_value = _normalize_value(rule.mention_kind, value)
    weak_segment_id = str(segment.get("segment_id") or segment.get("@id") or "")
    mention_id = _mention_id(
        mention_kind=rule.mention_kind,
        source_document_id=source_document_id,
        weak_segment_id=weak_segment_id,
        normalized_value=normalized_value,
        start=start,
        end=end,
    )
    text = str(segment.get("text", ""))
    return {
        "@type": rule.mention_type,
        "@id": mention_id,
        "mention_id": mention_id,
        "mention_kind": rule.mention_kind,
        "value": value,
        "normalized_value": normalized_value,
        "source_id": source_id,
        "source_document_id": source_document_id,
        "segments_file": str(segments_path),
        "chunk_id": str(segment.get("chunk_id", "")),
        "chunk_index": int(segment.get("chunk_index", 0) or 0),
        "weak_segment_id": weak_segment_id,
        "segment_type": str(segment.get("segment_type", "")),
        "segment_char_start": start,
        "segment_char_end": end,
        "context": _context(text, start, end),
        "confidence": rule.confidence,
        "reasons": [rule.reason],
        "warnings": ["mention_candidate_not_identity_resolution", "mention_candidate_not_verified_fact"],
        "candidate_profile_id": "",
        "candidate_place_id": "",
        "candidate_date_id": "",
        "candidate_event_id": "",
        "claim_extraction_allowed": False,
        "extraction_method": "deterministic_mention_candidate_rules",
        "review_status": "unreviewed",
    }


def _rule_allowed_for_segment(*, rule: MentionRule, segment: dict[str, Any]) -> bool:
    segment_type = str(segment.get("segment_type", ""))
    if rule.mention_kind == "person":
        return segment_type == "person_mention_context"
    if rule.mention_kind == "formation":
        return segment_type in {"formation_context", "person_mention_context"}
    if rule.mention_kind == "archival_reference":
        return segment_type in {"archival_reference_context", "person_mention_context"}
    if rule.mention_kind in {"date", "place"}:
        return segment_type in {"archival_reference_context", "formation_context", "person_mention_context"}
    return False


def _skip_reason(*, payload: dict[str, Any]) -> str:
    if not payload:
        return "segments_unreadable"
    if str(payload.get("@type", "")) != "WeakDocumentSegmentDocument":
        return "unsupported_payload_type"
    segments = payload.get("segments", [])
    if not isinstance(segments, list):
        return "segments_not_list"
    return ""


def _skip_record(*, payload: dict[str, Any], segments_path: Path, reason: str) -> dict[str, str]:
    return {
        "source_document_id": str(payload.get("source_document_id", "")) if payload else "",
        "segments_file": str(segments_path),
        "reason": reason,
    }


def _deduplicate_mentions(mentions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for mention in mentions:
        key = "|".join(
            [
                str(mention.get("mention_kind", "")),
                str(mention.get("source_document_id", "")),
                str(mention.get("weak_segment_id", "")),
                str(mention.get("normalized_value", "")),
                str(mention.get("segment_char_start", "")),
                str(mention.get("segment_char_end", "")),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(mention)
    return deduped


def _mentions_relative_path(document: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(document.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(document.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.mentions.json"


def _mentions_output_path(*, payload: dict[str, Any], output_dir: Path | None) -> Path | None:
    if output_dir is None:
        return None
    return output_dir / _mentions_relative_path(
        {
            "source_id": str(payload.get("source_id", "")),
            "source_document_id": str(payload.get("source_document_id", "")),
        }
    )


def _mention_id(
    *,
    mention_kind: str,
    source_document_id: str,
    weak_segment_id: str,
    normalized_value: str,
    start: int,
    end: int,
) -> str:
    digest = hashlib.sha256(
        f"{mention_kind}|{source_document_id}|{weak_segment_id}|{normalized_value}|{start}|{end}".encode("utf-8")
    ).hexdigest()[:16]
    return f"document-mention-candidate:{digest}"


def _context(text: str, start: int, end: int, *, radius: int = 80) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


def _clean_value(mention_kind: str, value: str) -> str:
    cleaned = " ".join(value.split()).strip(" .,;:")
    if mention_kind == "person" and _is_false_positive_person_value(cleaned):
        return ""
    if mention_kind == "formation":
        cleaned = re.sub(r"\b([Bb])rg\.\b", r"\1rigata", cleaned)
    if mention_kind == "date":
        cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _is_false_positive_person_value(value: str) -> bool:
    tokens = [token.strip(".,;:()[]{}").casefold() for token in value.split()]
    if not tokens:
        return True
    return any(token in PERSON_FALSE_POSITIVE_TOKENS for token in tokens)


def _normalize_value(mention_kind: str, value: str) -> str:
    normalized = " ".join(value.casefold().split()).strip()
    if mention_kind == "formation":
        normalized = normalized.replace("brg.", "brigata")
        normalized = re.sub(r"\b(\d{1,3})\s*(?:a|ma|ª)\s+brigata\b", r"\1 brigata", normalized)
    return " ".join(normalized.split())


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Estrae DocumentMentionCandidate preview-only da WeakDocumentSegment.")
    parser.add_argument("--segments-dir", default="data/processed/documents")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/document_mentions.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/document_mentions.md")
    args = parser.parse_args()

    payload = extract_document_mentions(
        segments_dir=Path(args.segments_dir),
        output_dir=Path(args.output_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"DocumentMentionCandidate JSON scritto in {args.output_json}")
    print(f"DocumentMentionCandidate Markdown scritto in {args.output_md}")
    print(f"Documenti processati: {payload['document_count']}")
    print(f"Menzioni candidate: {payload['mention_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
