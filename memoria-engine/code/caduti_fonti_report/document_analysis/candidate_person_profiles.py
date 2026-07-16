from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROW_PATTERN = re.compile(r"(?:^|\s)Riga\s+(\d+)\.\s+(.*?)(?=\s+Riga\s+\d+\.|$)")
NAME_FIELDS = ("nome", "nominativo", "full_name", "nome completo", "intestazione_pdf", "intestazione")
BIRTH_FIELDS = ("nascita", "data nascita", "data_di_nascita", "birth_date")
DEATH_FIELDS = ("morte", "data morte", "data_di_morte", "death_date")
FORMATION_FIELDS = ("ruolo_affiliazione", "formazione", "brigata", "reparto", "ruolo")
PLACE_FIELDS = ("origine_sulla_lapide", "luogo", "luogo nascita", "luogo morte", "place")


def build_candidate_person_profiles_from_documents(
    *,
    text_dir: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
    text_paths: list[Path] | None = None,
    target_names: list[str] | None = None,
) -> dict[str, Any]:
    paths = sorted(text_paths) if text_paths is not None else sorted(text_dir.rglob("*.text.json"))
    targets = _target_name_lookup(target_names or [])
    candidates: list[dict[str, Any]] = []
    skipped = []
    document_count = 0
    tabular_document_count = 0
    seen: set[tuple[str, int, str]] = set()

    for text_path in paths:
        payload = _load_json_object(text_path)
        if not payload:
            continue
        document_count += 1
        if str(payload.get("document_class", "")) != "tabular_document":
            skipped.append(_skip_item(payload, text_path=text_path, reason="not_tabular_document"))
            candidates.extend(
                _candidate_profiles_from_mentions(
                    payload,
                    text_path=text_path,
                    targets=targets,
                    seen=seen,
                )
            )
            continue
        if str(payload.get("text_status", "")) != "extracted":
            skipped.append(_skip_item(payload, text_path=text_path, reason="text_not_extracted"))
            candidates.extend(
                _candidate_profiles_from_mentions(
                    payload,
                    text_path=text_path,
                    targets=targets,
                    seen=seen,
                )
            )
            continue
        tabular_document_count += 1
        rows = _rows_from_processed_text(str(payload.get("text", "")))
        if not rows:
            skipped.append(_skip_item(payload, text_path=text_path, reason="no_parseable_rows"))
            candidates.extend(
                _candidate_profiles_from_mentions(
                    payload,
                    text_path=text_path,
                    targets=targets,
                    seen=seen,
                )
            )
            continue
        for row_number, fields in rows:
            canonical_name = _first_value(fields, NAME_FIELDS)
            if not canonical_name:
                skipped.append(
                    _skip_item(
                        payload,
                        text_path=text_path,
                        reason="missing_person_name",
                        row_number=row_number,
                    )
                )
                continue
            key = (str(payload.get("source_document_id", "")), row_number, canonical_name.casefold())
            if key in seen:
                skipped.append(
                    _skip_item(
                        payload,
                        text_path=text_path,
                        reason="duplicate_candidate_row",
                        row_number=row_number,
                    )
                )
                continue
            seen.add(key)
            candidates.append(_candidate_profile(payload, text_path=text_path, row_number=row_number, fields=fields, canonical_name=canonical_name))

    result = {
        "@type": "CandidatePersonProfileSet",
        "text_dir": str(text_dir),
        "document_count": document_count,
        "tabular_document_count": tabular_document_count,
        "candidate_profile_count": len(candidates),
        "skipped_count": len(skipped),
        "target_names": list(targets.values()),
        "review_status": "unreviewed",
        "promotion_status": "not_promoted",
        "candidate_person_profiles": candidates,
        "skipped_rows": skipped,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_candidate_person_profiles_markdown(result), encoding="utf-8")
    return result


def render_candidate_person_profiles_markdown(payload: dict[str, Any]) -> str:
    candidates = _list_items(payload.get("candidate_person_profiles"))
    lines = [
        "# CandidatePersonProfile preview",
        "",
        f"- Documenti letti: `{payload.get('document_count', 0)}`",
        f"- Documenti tabellari: `{payload.get('tabular_document_count', 0)}`",
        f"- Profili candidati: `{payload.get('candidate_profile_count', 0)}`",
        f"- Righe saltate: `{payload.get('skipped_count', 0)}`",
        f"- Stato revisione: `{payload.get('review_status', '')}`",
        f"- Stato promozione: `{payload.get('promotion_status', '')}`",
        "",
        "## Profili candidati",
        "",
    ]
    if not candidates:
        lines.append("_Nessun profilo candidato._")
    else:
        lines.extend(
            [
                "| Nome | Profilo suggerito | Documento | Riga | Nascita | Morte | Stato |",
                "| --- | --- | --- | ---: | --- | --- | --- |",
            ]
        )
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(candidate.get("canonical_name", "")),
                        f"`{_md_cell(candidate.get('suggested_profile_id', ''))}`",
                        f"`{_md_cell(candidate.get('source_document_id', ''))}`",
                        _md_cell(candidate.get("row_number", "")),
                        _md_cell(candidate.get("birth", {}).get("raw", "") if isinstance(candidate.get("birth"), dict) else ""),
                        _md_cell(candidate.get("death", {}).get("raw", "") if isinstance(candidate.get("death"), dict) else ""),
                        f"`{_md_cell(candidate.get('review_status', ''))}`",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Questo report non modifica i profili JSON-LD reali.",
            "- Nessun candidato viene promosso automaticamente a PersonResearchProfile canonico.",
            "- Ogni riga resta `unreviewed` finche' non viene validata da revisione umana.",
            "",
        ]
    )
    return "\n".join(lines)


def _candidate_profile(
    payload: dict[str, Any],
    *,
    text_path: Path,
    row_number: int,
    fields: dict[str, str],
    canonical_name: str,
) -> dict[str, Any]:
    source_document_id = str(payload.get("source_document_id", ""))
    candidate_id = "candidate-person-profile:" + _digest(source_document_id, str(row_number), canonical_name)
    suggested_profile_id = "person:purocielo:" + _slug(canonical_name)
    return {
        "@type": "CandidatePersonProfile",
        "@id": candidate_id,
        "candidate_profile_id": candidate_id,
        "suggested_profile_id": suggested_profile_id,
        "canonical_name": canonical_name,
        "identity": {
            "canonical_name": canonical_name,
            "name_forms": _name_forms(canonical_name, fields),
        },
        "birth": {"raw": _first_value(fields, BIRTH_FIELDS)},
        "death": {"raw": _first_value(fields, DEATH_FIELDS)},
        "formations": _non_empty_values(fields, FORMATION_FIELDS),
        "places": _non_empty_values(fields, PLACE_FIELDS),
        "row_number": row_number,
        "row_fields": fields,
        "source_id": str(payload.get("source_id", "")),
        "source_document_id": source_document_id,
        "text_path": str(text_path),
        "raw_file": str(payload.get("raw_file", "")),
        "provenance": {
            "document_text_path": str(text_path),
            "source_document_id": source_document_id,
            "row_number": row_number,
            "extraction_method": "processed_tabular_document_text",
        },
        "review_status": "unreviewed",
        "promotion_status": "not_promoted",
    }


def _candidate_profiles_from_mentions(
    payload: dict[str, Any],
    *,
    text_path: Path,
    targets: dict[str, str],
    seen: set[tuple[str, int, str]],
) -> list[dict[str, Any]]:
    if not targets:
        return []
    mentions_path = _mentions_path_for_text_path(text_path)
    mentions_payload = _load_json_object(mentions_path)
    if not mentions_payload:
        return []
    candidates = []
    for mention in _list_items(mentions_payload.get("mentions")):
        if not isinstance(mention, dict):
            continue
        if str(mention.get("mention_kind", "")) != "person":
            continue
        if str(mention.get("review_status", "")) not in {"", "unreviewed"}:
            continue
        canonical_name = _target_name_for_mention(mention, targets=targets)
        if not canonical_name:
            continue
        source_document_id = str(mention.get("source_document_id") or payload.get("source_document_id", ""))
        key = (source_document_id, 0, canonical_name.casefold())
        if key in seen:
            continue
        seen.add(key)
        candidates.append(_candidate_profile_from_mention(payload, text_path=text_path, mentions_path=mentions_path, mention=mention, canonical_name=canonical_name))
    return candidates


def _candidate_profile_from_mention(
    payload: dict[str, Any],
    *,
    text_path: Path,
    mentions_path: Path,
    mention: dict[str, Any],
    canonical_name: str,
) -> dict[str, Any]:
    source_document_id = str(mention.get("source_document_id") or payload.get("source_document_id", ""))
    mention_id = str(mention.get("mention_id") or mention.get("@id") or "")
    context = str(mention.get("context", ""))
    candidate_id = "candidate-person-profile:" + _digest(source_document_id, mention_id, canonical_name)
    suggested_profile_id = "person:purocielo:" + _slug(canonical_name)
    return {
        "@type": "CandidatePersonProfile",
        "@id": candidate_id,
        "candidate_profile_id": candidate_id,
        "suggested_profile_id": suggested_profile_id,
        "canonical_name": canonical_name,
        "identity": {
            "canonical_name": canonical_name,
            "name_forms": _dedupe([canonical_name, str(mention.get("value", ""))]),
        },
        "birth": {"raw": ""},
        "death": {"raw": ""},
        "formations": [],
        "places": [],
        "row_number": 0,
        "row_fields": {
            "mention_value": str(mention.get("value", "")),
            "mention_context": context,
            "weak_segment_id": str(mention.get("weak_segment_id", "")),
            "chunk_id": str(mention.get("chunk_id", "")),
        },
        "source_id": str(mention.get("source_id") or payload.get("source_id", "")),
        "source_document_id": source_document_id,
        "text_path": str(text_path),
        "raw_file": str(payload.get("raw_file", "")),
        "provenance": {
            "document_text_path": str(text_path),
            "mentions_path": str(mentions_path),
            "source_document_id": source_document_id,
            "mention_id": mention_id,
            "weak_segment_id": str(mention.get("weak_segment_id", "")),
            "chunk_id": str(mention.get("chunk_id", "")),
            "extraction_method": "processed_person_mention_target_match",
        },
        "review_status": "unreviewed",
        "promotion_status": "not_promoted",
    }


def _rows_from_processed_text(text: str) -> list[tuple[int, dict[str, str]]]:
    rows = []
    for match in ROW_PATTERN.finditer(text):
        row_number = int(match.group(1))
        fields = _fields_from_row(match.group(2))
        rows.append((row_number, fields))
    return rows


def _fields_from_row(row_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in row_text.split(";"):
        label, sep, value = part.partition(":")
        if not sep:
            continue
        normalized_label = _normalize_label(label)
        if normalized_label and value.strip():
            fields[normalized_label] = value.strip()
    return fields


def _first_value(fields: dict[str, str], labels: tuple[str, ...]) -> str:
    for label in labels:
        value = fields.get(_normalize_label(label), "").strip()
        if value:
            return value
    return ""


def _non_empty_values(fields: dict[str, str], labels: tuple[str, ...]) -> list[str]:
    values = []
    for label in labels:
        value = fields.get(_normalize_label(label), "").strip()
        if value and value not in values:
            values.append(value)
    return values


def _name_forms(canonical_name: str, fields: dict[str, str]) -> list[str]:
    forms = [canonical_name]
    for label in NAME_FIELDS:
        value = fields.get(_normalize_label(label), "").strip()
        if value and value not in forms:
            forms.append(value)
    return forms


def _skip_item(payload: dict[str, Any], *, text_path: Path, reason: str, row_number: int = 0) -> dict[str, Any]:
    return {
        "reason": reason,
        "source_id": str(payload.get("source_id", "")),
        "source_document_id": str(payload.get("source_document_id", "")),
        "text_path": str(text_path),
        "row_number": row_number,
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _list_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _target_name_lookup(values: list[str]) -> dict[str, str]:
    lookup = {}
    for raw in values:
        name = str(raw).strip()
        if not name:
            continue
        lookup[_name_key(name)] = name
    return lookup


def _target_name_for_mention(mention: dict[str, Any], *, targets: dict[str, str]) -> str:
    values = [
        str(mention.get("value", "")),
        str(mention.get("normalized_value", "")),
    ]
    for value in values:
        key = _name_key(value)
        if key in targets:
            return targets[key]
        reversed_key = _reversed_name_key(value)
        if reversed_key in targets:
            return targets[reversed_key]
    return ""


def _name_key(value: str) -> str:
    return " ".join(_slug(value).split("-"))


def _reversed_name_key(value: str) -> str:
    tokens = _name_key(value).split()
    if len(tokens) != 2:
        return ""
    return " ".join(reversed(tokens))


def _mentions_path_for_text_path(text_path: Path) -> Path:
    name = text_path.name
    if name.endswith(".text.json"):
        return text_path.with_name(name[: -len(".text.json")] + ".mentions.json")
    return text_path.with_suffix(".mentions.json")


def _normalize_label(value: str) -> str:
    return " ".join(str(value).strip().casefold().replace("-", "_").split())


def _dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _slug(value: str) -> str:
    normalized = str(value).strip().casefold()
    parts = []
    current = []
    for char in normalized:
        if char.isalnum():
            current.append(char)
        elif current:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    return "-".join(parts) or "unknown"


def _digest(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera CandidatePersonProfile preview-only da documenti tabellari processati.")
    parser.add_argument("--text-dir", default="data/processed/documents")
    parser.add_argument("--text-path", action="append", default=[], help="File .text.json specifico da includere; ripetibile.")
    parser.add_argument("--output-json", default="risultati/document_analysis/candidate_person_profiles_from_documents.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/candidate_person_profiles_from_documents.md")
    parser.add_argument("--target-name", action="append", default=[], help="Nome target da cercare nelle mention gia' processate.")
    args = parser.parse_args()

    payload = build_candidate_person_profiles_from_documents(
        text_dir=Path(args.text_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
        text_paths=[Path(path) for path in args.text_path] if args.text_path else None,
        target_names=args.target_name,
    )
    print(f"CandidatePersonProfile JSON scritto in {args.output_json}")
    print(f"CandidatePersonProfile Markdown scritto in {args.output_md}")
    print(f"Profili candidati: {payload['candidate_profile_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
