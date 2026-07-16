from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from caduti_fonti_report.knowledge_catalog import default_military_glossary_dir


@dataclass(frozen=True)
class MilitaryGlossaryEntry:
    entry_id: str
    term: str
    language: str
    category: str
    translation_it: str
    aliases: tuple[str, ...]
    abbreviations: tuple[str, ...]
    source_reference: str
    review_status: str


def extract_military_glossary_mentions(
    *,
    text_dir: Path,
    glossary_dir: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
    text_paths: list[Path] | None = None,
) -> dict[str, Any]:
    entries = load_military_glossary_entries(glossary_dir)
    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    paths = sorted(text_paths) if text_paths is not None else sorted(text_dir.rglob("*.text.json"))

    for text_path in paths:
        payload = _load_json_object(text_path)
        skip_reason = _skip_reason(payload)
        if skip_reason:
            skipped.append(_skip_record(payload=payload, text_path=text_path, reason=skip_reason))
            continue

        mentions = _mentions_for_text(payload=payload, text_path=text_path, entries=entries)
        if not mentions:
            continue
        documents.append(
            {
                "@type": "CandidateMilitaryGlossaryMentionDocument",
                "source_id": str(payload.get("source_id", "")),
                "source_document_id": str(payload.get("source_document_id", "")),
                "document_class": str(payload.get("document_class", "")),
                "raw_file": str(payload.get("raw_file", "")),
                "metadata_file": str(payload.get("metadata_file", "")),
                "text_file": str(text_path),
                "media_type": str(payload.get("media_type", "")),
                "extraction_status": str(payload.get("extraction_status", "")),
                "text_status": str(payload.get("text_status", "")),
                "review_status": str(payload.get("review_status", "")) or "unreviewed",
                "mention_count": len(mentions),
                "mentions": mentions,
            }
        )

    mention_count = sum(int(document.get("mention_count", 0) or 0) for document in documents)
    result = {
        "@type": "CandidateMilitaryGlossaryMentionSet",
        "text_dir": str(text_dir),
        "glossary_dir": str(glossary_dir),
        "extraction_method": "deterministic_military_glossary_lookup",
        "review_status": "unreviewed",
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
        output_md.write_text(render_military_glossary_mentions_markdown(result), encoding="utf-8")
    return result


def load_military_glossary_entries(glossary_dir: Path) -> list[MilitaryGlossaryEntry]:
    entries: list[MilitaryGlossaryEntry] = []
    for path in sorted(glossary_dir.rglob("*.jsonld")):
        payload = _load_json_object(path)
        if str(payload.get("@type", "")) != "MilitaryGlossary":
            continue
        raw_entries = payload.get("entries", [])
        if not isinstance(raw_entries, list):
            continue
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict):
                continue
            entry = _entry_from_payload(raw_entry)
            if entry is not None:
                entries.append(entry)
    return _deduplicate_entries(entries)


def render_military_glossary_mentions_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CandidateMilitaryGlossaryMention preview",
        "",
        f"- Metodo: `{payload.get('extraction_method', '')}`",
        f"- Glossario: `{payload.get('glossary_dir', '')}`",
        f"- Documenti con menzioni: `{payload.get('document_count', 0)}`",
        f"- Menzioni candidate: `{payload.get('mention_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        f"- Stato revisione: `{payload.get('review_status', '')}`",
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
                    f"- Classe documento: `{document.get('document_class', '')}`",
                    f"- Stato testo: `{document.get('text_status', '')}`",
                    f"- Estrazione: `{document.get('extraction_status', '')}`",
                    f"- Stato revisione: `{document.get('review_status', '')}`",
                    f"- File testo: `{document.get('text_file', '')}`",
                    "",
                ]
            )
            for mention in document.get("mentions", []):
                if not isinstance(mention, dict):
                    continue
                lines.append(
                    f"- `{mention.get('mention_id', '')}` | "
                    f"{mention.get('category', '')} | "
                    f"`{mention.get('matched_text', '')}` -> "
                    f"`{mention.get('term', '')}` | confidence `{mention.get('confidence', '')}`"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _entry_from_payload(payload: dict[str, Any]) -> MilitaryGlossaryEntry | None:
    entry_id = str(payload.get("@id") or payload.get("entry_id") or "").strip()
    term = str(payload.get("term", "")).strip()
    language = str(payload.get("language", "")).strip()
    category = str(payload.get("category", "")).strip()
    if not entry_id or not term or not language or not category:
        return None
    return MilitaryGlossaryEntry(
        entry_id=entry_id,
        term=term,
        language=language,
        category=category,
        translation_it=str(payload.get("translation_it", "")).strip(),
        aliases=tuple(_strings(payload.get("aliases", []))),
        abbreviations=tuple(_strings(payload.get("abbreviations", []))),
        source_reference=str(payload.get("source_reference", "")).strip(),
        review_status=str(payload.get("review_status", "")).strip() or "unreviewed",
    )


def _mentions_for_text(*, payload: dict[str, Any], text_path: Path, entries: list[MilitaryGlossaryEntry]) -> list[dict[str, Any]]:
    text = str(payload.get("text", ""))
    mentions: list[dict[str, Any]] = []
    for entry in entries:
        for matched_field, value in _match_values(entry):
            for match in _term_pattern(value).finditer(text):
                mentions.append(
                    _mention_candidate(
                        payload=payload,
                        text_path=text_path,
                        text=text,
                        entry=entry,
                        matched_field=matched_field,
                        matched_text=match.group(0),
                        start=match.start(),
                        end=match.end(),
                    )
                )
    return _deduplicate_mentions(mentions)


def _mention_candidate(
    *,
    payload: dict[str, Any],
    text_path: Path,
    text: str,
    entry: MilitaryGlossaryEntry,
    matched_field: str,
    matched_text: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    source_document_id = str(payload.get("source_document_id", ""))
    mention_id = _mention_id(
        source_document_id=source_document_id,
        entry_id=entry.entry_id,
        matched_text=matched_text,
        start=start,
        end=end,
    )
    return {
        "@type": "CandidateMilitaryGlossaryMention",
        "@id": mention_id,
        "mention_id": mention_id,
        "entry_id": entry.entry_id,
        "term": entry.term,
        "matched_text": " ".join(matched_text.split()),
        "matched_field": matched_field,
        "language": entry.language,
        "category": entry.category,
        "translation_it": entry.translation_it,
        "source_reference": entry.source_reference,
        "source_id": str(payload.get("source_id", "")),
        "source_document_id": source_document_id,
        "document_class": str(payload.get("document_class", "")),
        "raw_file": str(payload.get("raw_file", "")),
        "metadata_file": str(payload.get("metadata_file", "")),
        "text_file": str(text_path),
        "extraction_status": str(payload.get("extraction_status", "")),
        "text_status": str(payload.get("text_status", "")),
        "text_char_start": start,
        "text_char_end": end,
        "context": _context(text, start, end),
        "confidence": 0.72 if matched_field == "term" else 0.66,
        "warnings": [
            "military_glossary_match_not_verified_fact",
            "candidate_not_military_unit_identity_resolution",
        ],
        "claim_extraction_allowed": False,
        "territorial_presence_claim_allowed": False,
        "review_status": "unreviewed",
    }


def _match_values(entry: MilitaryGlossaryEntry) -> Iterable[tuple[str, str]]:
    yield "term", entry.term
    for alias in entry.aliases:
        yield "alias", alias
    for abbreviation in entry.abbreviations:
        yield "abbreviation", abbreviation


def _term_pattern(value: str) -> re.Pattern[str]:
    escaped = re.escape(value.strip())
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![\w]){escaped}(?![\w])", re.IGNORECASE)


def _skip_reason(payload: dict[str, Any]) -> str:
    if not payload:
        return "text_unreadable"
    if str(payload.get("@type", "")) != "ProcessedDocumentText":
        return "unsupported_payload_type"
    if str(payload.get("text_status", "")) != "extracted":
        return "text_not_extracted"
    if not str(payload.get("text", "")).strip():
        return "empty_text"
    return ""


def _skip_record(*, payload: dict[str, Any], text_path: Path, reason: str) -> dict[str, str]:
    return {
        "source_id": str(payload.get("source_id", "")) if payload else "",
        "source_document_id": str(payload.get("source_document_id", "")) if payload else "",
        "document_class": str(payload.get("document_class", "")) if payload else "",
        "text_file": str(text_path),
        "reason": reason,
    }


def _deduplicate_mentions(mentions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for mention in mentions:
        key = "|".join(
            [
                str(mention.get("source_document_id", "")),
                str(mention.get("entry_id", "")),
                str(mention.get("text_char_start", "")),
                str(mention.get("text_char_end", "")),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(mention)
    return deduped


def _deduplicate_entries(entries: list[MilitaryGlossaryEntry]) -> list[MilitaryGlossaryEntry]:
    seen: set[str] = set()
    deduped: list[MilitaryGlossaryEntry] = []
    for entry in entries:
        if entry.entry_id in seen:
            continue
        seen.add(entry.entry_id)
        deduped.append(entry)
    return deduped


def _mention_id(*, source_document_id: str, entry_id: str, matched_text: str, start: int, end: int) -> str:
    digest = hashlib.sha256(f"{source_document_id}|{entry_id}|{matched_text}|{start}|{end}".encode("utf-8")).hexdigest()[:16]
    return f"military-glossary-mention:{digest}"


def _context(text: str, start: int, end: int, *, radius: int = 80) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Estrae CandidateMilitaryGlossaryMention preview-only da testi processati.")
    parser.add_argument("--text-dir", default="data/processed/documents")
    parser.add_argument("--glossary-dir", default=str(default_military_glossary_dir()))
    parser.add_argument("--output-json", default="risultati/document_analysis/military_glossary_mentions.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/military_glossary_mentions.md")
    args = parser.parse_args()

    payload = extract_military_glossary_mentions(
        text_dir=Path(args.text_dir),
        glossary_dir=Path(args.glossary_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"CandidateMilitaryGlossaryMention JSON scritto in {args.output_json}")
    print(f"CandidateMilitaryGlossaryMention Markdown scritto in {args.output_md}")
    print(f"Documenti con menzioni: {payload['document_count']}")
    print(f"Menzioni candidate: {payload['mention_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
