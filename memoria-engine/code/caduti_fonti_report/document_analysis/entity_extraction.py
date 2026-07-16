from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Pattern

SKIPPED_DOCUMENT_CLASSES = {"result_page", "reference_page"}

MONTHS_IT = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


@dataclass(frozen=True)
class EntityPattern:
    entity_type: str
    pattern: Pattern[str]
    reason: str
    score: float


ENTITY_PATTERNS = [
    EntityPattern(
        entity_type="date",
        pattern=re.compile(rf"\b\d{{1,2}}\s+(?:{'|'.join(MONTHS_IT)})\s+\d{{4}}\b", re.IGNORECASE),
        reason="italian_textual_date_pattern",
        score=0.9,
    ),
    EntityPattern(
        entity_type="date",
        pattern=re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4})\b"),
        reason="numeric_date_pattern",
        score=0.75,
    ),
    EntityPattern(
        entity_type="formation",
        pattern=re.compile(
            r"\b\d{1,3}\s*(?:\u00aa|\u00c2\u00aa|a|ma)?\s+[Bb]r(?:igata|g\.)"
            r"(?:\s+[A-Z\u00c0-\u00dd][\w\u00c0-\u00ff'-]+){1,3}\b"
        ),
        reason="brigata_pattern",
        score=0.8,
    ),
    EntityPattern(
        entity_type="archival_reference",
        pattern=re.compile(r"\b[A-Z]{1,4}\s+\d+(?:/\d+){1,4}\b"),
        reason="archival_reference_code_pattern",
        score=0.85,
    ),
    EntityPattern(
        entity_type="archival_reference",
        pattern=re.compile(r"\b(?:BArch,\s*)?RH\s+\d{1,3}[-/]\d{1,3}(?:[-/]\d{1,4})?\b", re.IGNORECASE),
        reason="bundesarchiv_rh_reference_pattern",
        score=0.82,
    ),
]


def extract_document_entities(
    *,
    text_dir: Path,
    metadata_dir: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for text_path in sorted(text_dir.rglob("*.text.json")):
        text_payload = _load_json_object(text_path)
        if not text_payload:
            continue
        text_payload["_text_file"] = str(text_path)
        metadata = _load_metadata_for_text(text_payload=text_payload, metadata_dir=metadata_dir)
        document_class = str(text_payload.get("document_class") or metadata.get("document_class") or "")
        source_document_id = str(text_payload.get("source_document_id") or metadata.get("source_document_id") or "")

        skip_reason = _skip_reason(text_payload=text_payload, metadata=metadata, document_class=document_class)
        if skip_reason:
            skipped.append({"source_document_id": source_document_id, "text_file": str(text_path), "reason": skip_reason})
            continue

        text = str(text_payload.get("text", ""))
        for entity_pattern in ENTITY_PATTERNS:
            for match in entity_pattern.pattern.finditer(text):
                if _should_skip_match(entity_type=entity_pattern.entity_type, text=text, start=match.start(), end=match.end()):
                    continue
                entities.append(
                    _extracted_entity(
                        entity_pattern=entity_pattern,
                        metadata=metadata,
                        text_payload=text_payload,
                        value=match.group(0),
                        start=match.start(),
                        end=match.end(),
                    )
                )

    entities.extend(_entities_from_segment_mentions(text_dir=text_dir, metadata_dir=metadata_dir))
    entities = _deduplicate_entities(entities)
    payload = {
        "@type": "ExtractedEntitySet",
        "text_dir": str(text_dir),
        "metadata_dir": str(metadata_dir),
        "entity_count": len(entities),
        "skipped_count": len(skipped),
        "extracted_entities": entities,
        "skipped_documents": skipped,
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_extracted_entities_markdown(payload), encoding="utf-8")

    return payload


def render_extracted_entities_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# ExtractedEntity preview",
        "",
        f"- Entita estratte: `{payload.get('entity_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Entita",
        "",
    ]
    entities = payload.get("extracted_entities", [])
    if not isinstance(entities, list) or not entities:
        lines.append("_Nessuna entita estratta._")
    else:
        for entity in entities:
            lines.extend(
                [
                    f"### {entity.get('entity_type', '')}: {entity.get('value', '')}",
                    "",
                    f"- Documento: `{entity.get('source_document_id', '')}`",
                    f"- Fonte: `{entity.get('source_id', '')}`",
                    f"- Titolo: {entity.get('title', '')}",
                    f"- Stato revisione: `{entity.get('review_status', '')}`",
                    f"- Score: `{entity.get('score', '')}`",
                    f"- Motivi: {', '.join(str(reason) for reason in entity.get('reasons', []))}",
                    f"- Contesto: {entity.get('context', '')}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _load_metadata_for_text(*, text_payload: dict[str, Any], metadata_dir: Path) -> dict[str, Any]:
    metadata_file = str(text_payload.get("metadata_file", "")).strip()
    if metadata_file:
        metadata_path = Path(metadata_file)
        if metadata_path.exists():
            metadata = _load_json_object(metadata_path)
            if metadata:
                return metadata

    source_id = _safe_path_part(str(text_payload.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(text_payload.get("source_document_id", "")) or "unknown")
    metadata_path = metadata_dir / source_id / f"{document_id}.metadata.json"
    return _load_json_object(metadata_path)


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _skip_reason(*, text_payload: dict[str, Any], metadata: dict[str, Any], document_class: str) -> str:
    if document_class in SKIPPED_DOCUMENT_CLASSES:
        return f"skipped_{document_class}"
    if str(text_payload.get("text_status", "")) != "extracted":
        return "text_not_extracted"
    if not str(text_payload.get("text", "")).strip():
        return "empty_text"
    if not metadata:
        return "metadata_missing"
    if not bool(metadata.get("claim_eligible", False)) and not str(text_payload.get("transcription_method", "")).strip():
        return "claim_not_eligible_metadata"
    return ""


def _extracted_entity(
    *,
    entity_pattern: EntityPattern,
    metadata: dict[str, Any],
    text_payload: dict[str, Any],
    value: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    source_document_id = str(text_payload.get("source_document_id") or metadata.get("source_document_id") or "")
    source_id = str(text_payload.get("source_id") or metadata.get("source_id") or "")
    entity_value = _clean_entity_value(entity_pattern.entity_type, value)
    normalized_value = _normalize_entity_value(entity_pattern.entity_type, entity_value)
    context = _context(str(text_payload.get("text", "")), start, end)
    normalized_value = _normalize_entity_value_from_context(
        entity_type=entity_pattern.entity_type,
        normalized_value=normalized_value,
        context=context,
    )
    return {
        "@type": "ExtractedEntity",
        "@id": _entity_id(entity_pattern.entity_type, source_document_id, normalized_value),
        "entity_type": entity_pattern.entity_type,
        "value": entity_value,
        "normalized_value": normalized_value,
        "source_id": source_id,
        "source_document_id": source_document_id,
        "title": str(metadata.get("title", "")),
        "url": str(metadata.get("url", "")),
        "archival_reference": str(metadata.get("archival_reference", "")),
        "raw_file": str(metadata.get("raw_file", "")),
        "metadata_file": str(text_payload.get("metadata_file", "")),
        "text_file": str(text_payload.get("_text_file", "")),
        "context": context,
        "score": entity_pattern.score,
        "reasons": [entity_pattern.reason],
        "review_status": "unreviewed",
    }


def _entities_from_segment_mentions(*, text_dir: Path, metadata_dir: Path) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for mentions_path in sorted(text_dir.rglob("*.mentions.json")):
        payload = _load_json_object(mentions_path)
        if not payload:
            continue
        for mention in _list_items(payload.get("mentions")):
            entity_type = _entity_type_for_mention(mention)
            if not entity_type:
                continue
            if str(mention.get("review_status", "")) not in {"", "unreviewed"}:
                continue
            metadata = _metadata_for_mention(mention=mention, metadata_dir=metadata_dir)
            entities.append(_extracted_entity_from_mention(mention=mention, metadata=metadata, mentions_path=mentions_path, entity_type=entity_type))
    return entities


def _entity_type_for_mention(mention: dict[str, Any]) -> str:
    mention_kind = str(mention.get("mention_kind", ""))
    if mention_kind in {"date", "formation", "archival_reference"}:
        return mention_kind
    return ""


def _metadata_for_mention(*, mention: dict[str, Any], metadata_dir: Path) -> dict[str, Any]:
    source_id = _safe_path_part(str(mention.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(mention.get("source_document_id", "")) or "unknown")
    metadata_path = metadata_dir / source_id / f"{document_id}.metadata.json"
    metadata = _load_json_object(metadata_path)
    if metadata:
        metadata["_metadata_file"] = str(metadata_path)
    return metadata


def _extracted_entity_from_mention(
    *,
    mention: dict[str, Any],
    metadata: dict[str, Any],
    mentions_path: Path,
    entity_type: str,
) -> dict[str, Any]:
    value = _clean_entity_value(entity_type, str(mention.get("value", "")))
    normalized_value = str(mention.get("normalized_value", "")).strip() or _normalize_entity_value(entity_type, value)
    source_document_id = str(mention.get("source_document_id") or metadata.get("source_document_id") or "")
    weak_segment_id = str(mention.get("weak_segment_id", ""))
    chunk_id = str(mention.get("chunk_id", ""))
    return {
        "@type": "ExtractedEntity",
        "@id": _entity_id(entity_type, f"{source_document_id}|{weak_segment_id}|{chunk_id}", normalized_value),
        "entity_type": entity_type,
        "value": value,
        "normalized_value": normalized_value,
        "source_id": str(mention.get("source_id") or metadata.get("source_id") or ""),
        "source_document_id": source_document_id,
        "title": str(metadata.get("title", "")),
        "url": str(metadata.get("url", "")),
        "archival_reference": str(metadata.get("archival_reference", "")),
        "raw_file": str(metadata.get("raw_file", "")),
        "metadata_file": str(metadata.get("_metadata_file", "")),
        "mentions_file": str(mentions_path),
        "mention_id": str(mention.get("@id") or mention.get("mention_id") or ""),
        "chunk_id": chunk_id,
        "weak_segment_id": weak_segment_id,
        "context": str(mention.get("context", "")),
        "score": float(mention.get("confidence", 0.0) or 0.0),
        "reasons": [*_list_strings(mention.get("reasons")), "segment_mention_entity"],
        "review_status": "unreviewed",
    }


def _deduplicate_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for entity in entities:
        entity_id = str(entity.get("@id", ""))
        if entity_id in seen:
            continue
        seen.add(entity_id)
        deduped.append(entity)
    return deduped


def _entity_id(entity_type: str, source_document_id: str, normalized_value: str) -> str:
    digest = hashlib.sha256(f"{entity_type}|{source_document_id}|{normalized_value}".encode("utf-8")).hexdigest()[:16]
    return f"extracted-entity:{digest}"


def _context(text: str, start: int, end: int, *, radius: int = 90) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


def _should_skip_match(*, entity_type: str, text: str, start: int, end: int) -> bool:
    if entity_type != "formation":
        return False
    context = _context(text, start, end, radius=120).casefold()
    navigation_markers = [
        "guzzo il sentiero di corbari storia la lotta di liberazione",
        "come arrivare aspetti naturali atti e documenti",
    ]
    return any(marker in context for marker in navigation_markers)


def _normalize_value(value: str) -> str:
    return " ".join(value.casefold().split())


def _clean_entity_value(entity_type: str, value: str) -> str:
    cleaned = " ".join(value.split()).strip(" .,;:")
    if entity_type != "formation":
        return cleaned
    return re.sub(r"\b([Bb])rg\.\b", r"\1rigata", cleaned)


def _normalize_entity_value(entity_type: str, value: str) -> str:
    normalized = _normalize_value(value)
    if entity_type != "formation":
        return normalized
    normalized = normalized.replace("brg.", "brigata")
    normalized = re.sub(r"\b(\d{1,3})\s*(?:a|ma|\u00aa|\u00c2\u00aa)\s+brigata\b", r"\1 brigata", normalized)
    if (
        normalized.startswith("36 brigata")
        and "garibaldi" in normalized.split()
        and "bianconcini" in normalized.split()
    ):
        normalized = "36 brigata garibaldi bianconcini"
    return " ".join(normalized.split())


def _normalize_entity_value_from_context(*, entity_type: str, normalized_value: str, context: str) -> str:
    if entity_type != "formation":
        return normalized_value
    if normalized_value == "36 brigata garibaldi" and "bianconcini" in context.casefold():
        return "36 brigata garibaldi bianconcini"
    return normalized_value


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Estrae ExtractedEntity offline da testi processati.")
    parser.add_argument("--text-dir", default="data/processed/documents")
    parser.add_argument("--metadata-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/extracted_entities.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/extracted_entities.md")
    args = parser.parse_args()

    payload = extract_document_entities(
        text_dir=Path(args.text_dir),
        metadata_dir=Path(args.metadata_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"ExtractedEntity JSON scritto in {args.output_json}")
    print(f"ExtractedEntity Markdown scritto in {args.output_md}")
    print(f"Entita estratte: {payload['entity_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
