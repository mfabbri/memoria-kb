from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def build_glossary_preview(
    *,
    structure_path: Path,
    glossary_path: Path,
    output_path: Path,
    apply: bool,
) -> dict[str, Any]:
    """Build a preview-only glossary annotation set for one structured document."""
    structure = _load_json(structure_path)
    glossary = _load_json(glossary_path)
    if structure.get("@type") != "DocumentStructure":
        raise ValueError(f"Payload struttura non supportato: {structure.get('@type', '')}")
    if glossary.get("@type") != "MilitaryGlossary":
        raise ValueError(f"Payload glossario non supportato: {glossary.get('@type', '')}")

    digest = hashlib.sha256(glossary_path.read_bytes()).hexdigest()
    version = str(glossary.get("version") or f"sha256:{digest}")
    entries = _entries(glossary)
    mentions = _mentions(structure=structure, entries=entries)
    page_id = str(structure.get("page_id") or structure.get("source_document_id") or structure_path.stem)
    payload: dict[str, Any] = {
        "@type": "CandidateMilitaryGlossaryMentionSet",
        "@id": f"candidate-glossary-mentions:{page_id}:{digest[:16]}",
        "source_structure": str(structure_path),
        "source_document_id": str(structure.get("source_document_id", "")),
        "source_page_id": page_id,
        "source_image_hash": _source_image_hash(structure),
        "source_evidence": structure.get("source_evidence", {}),
        "glossary_resource": str(glossary.get("@id", "")),
        "glossary_version": version,
        "glossary_digest": f"sha256:{digest}",
        "extraction_method": "deterministic_versioned_glossary_lookup",
        "preview_only": True,
        "review_status": "unreviewed",
        "claim_extraction_allowed": False,
        "territorial_presence_claim_allowed": False,
        "mention_count": len(mentions),
        "mentions": mentions,
    }

    status = "preview"
    if apply:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if output_path.exists():
            if output_path.read_text(encoding="utf-8") == encoded:
                status = "skipped_existing"
            else:
                raise ValueError(f"Output gia' esistente e diverso: {output_path}")
        else:
            output_path.write_text(encoded, encoding="utf-8")
            status = "written"
    payload["operation_status"] = status
    payload["output_path"] = str(output_path)
    return payload


def build_glossary_diff(
    *,
    previous_path: Path,
    current_path: Path,
    output_path: Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Compare two candidate mention sets without mutating either preview."""
    previous = _load_json(previous_path)
    current = _load_json(current_path)
    for label, payload in (("precedente", previous), ("corrente", current)):
        if payload.get("@type") != "CandidateMilitaryGlossaryMentionSet":
            raise ValueError(f"Preview {label} non supportato: {payload.get('@type', '')}")

    previous_mentions = _mention_map(previous)
    current_mentions = _mention_map(current)
    changes: list[dict[str, Any]] = []
    for mention_id in sorted(set(previous_mentions) | set(current_mentions)):
        old = previous_mentions.get(mention_id)
        new = current_mentions.get(mention_id)
        if old is None:
            changes.append({"change": "added", "mention": new})
            continue
        if new is None:
            changes.append({"change": "removed", "mention": old})
            continue
        old_translation = str(old.get("translation_it", ""))
        new_translation = str(new.get("translation_it", ""))
        if old_translation == new_translation:
            changes.append({"change": "unchanged", "mention": new})
            continue
        reviewed = str(old.get("review_status", "unreviewed")) != "unreviewed"
        changes.append({
            "change": "protected_reviewed" if reviewed else "changed",
            "mention": new,
            "previous_mention": old,
            "proposed_translation_it": new_translation,
            "effective_translation_it": old_translation if reviewed else new_translation,
            "human_revision_protected": reviewed,
        })

    previous_digest = _file_digest(previous_path)
    current_digest = _file_digest(current_path)
    payload: dict[str, Any] = {
        "@type": "CandidateMilitaryGlossaryMentionDiff",
        "@id": f"candidate-glossary-diff:{previous_digest[:16]}:{current_digest[:16]}",
        "previous_preview": str(previous_path),
        "current_preview": str(current_path),
        "previous_glossary_version": str(previous.get("glossary_version", "")),
        "current_glossary_version": str(current.get("glossary_version", "")),
        "previous_preview_digest": f"sha256:{previous_digest}",
        "current_preview_digest": f"sha256:{current_digest}",
        "preview_only": True,
        "human_revisions_protected": True,
        "counts": {name: sum(1 for item in changes if item["change"] == name)
                   for name in ("added", "removed", "changed", "protected_reviewed", "unchanged")},
        "changes": changes,
        "operation_status": "preview",
    }
    if output_path is not None:
        if apply:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            if output_path.exists():
                if output_path.read_text(encoding="utf-8") == encoded:
                    payload["operation_status"] = "skipped_existing"
                else:
                    raise ValueError(f"Output gia' esistente e diverso: {output_path}")
            else:
                output_path.write_text(encoded, encoding="utf-8")
                payload["operation_status"] = "written"
        payload["output_path"] = str(output_path)
    return payload


def _mention_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    mentions = payload.get("mentions", [])
    if not isinstance(mentions, list):
        raise ValueError("Campo mentions non valido")
    for mention in mentions:
        if isinstance(mention, dict) and mention.get("@id"):
            result[str(mention["@id"])] = mention
    return result


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object atteso: {path}")
    return value


def _entries(glossary: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for raw in glossary.get("entries", []):
        if not isinstance(raw, dict) or not raw.get("@id") or not raw.get("term"):
            continue
        values = [("term", str(raw["term"]))]
        for field in ("aliases", "abbreviations"):
            for value in raw.get(field, []):
                if str(value).strip():
                    values.append(("alias" if field == "aliases" else "abbreviation", str(value)))
        result.append({"raw": raw, "values": values})
    return result


def _mentions(*, structure: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for block in _blocks(structure):
        text = str(block.get("text") or block.get("value") or "")
        if not text.strip():
            continue
        candidates = []
        for entry in entries:
            for matched_field, value in entry["values"]:
                candidates.append((len(value), matched_field, value, entry["raw"]))
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
        occupied: list[tuple[int, int]] = []
        for _, matched_field, value, raw in candidates:
            for match in _pattern(value).finditer(text):
                span = (match.start(), match.end())
                if any(span[0] < end and start < span[1] for start, end in occupied):
                    continue
                occupied.append(span)
                source_regions = block.get("source_region_ids", block.get("region_ids", []))
                if not isinstance(source_regions, list):
                    source_regions = [str(source_regions)] if source_regions else []
                entry_id = str(raw["@id"])
                mention_key = "|".join((str(structure.get("source_document_id", "")), str(block.get("id", "")), entry_id, match.group(0)))
                mention_id = "candidate-glossary-mention:" + hashlib.sha256(mention_key.encode("utf-8")).hexdigest()[:24]
                mentions.append({
                    "@type": "CandidateMilitaryGlossaryMention",
                    "@id": mention_id,
                    "mention_id": mention_id,
                    "entry_id": entry_id,
                    "term": str(raw.get("term", "")),
                    "matched_text": match.group(0),
                    "matched_field": matched_field,
                    "translation_it": str(raw.get("translation_it", "")),
                    "source_reference": raw.get("source_reference", ""),
                    "source_references": raw.get("source_references", []),
                    "source_document_id": str(structure.get("source_document_id", "")),
                    "source_page_id": str(structure.get("page_id", "")),
                    "source_region_ids": source_regions,
                    "context": text,
                    "review_status": "unreviewed",
                    "claim_extraction_allowed": False,
                    "territorial_presence_claim_allowed": False,
                    "warnings": ["glossary_match_not_verified_fact"],
                })
    return mentions


def _blocks(structure: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    pages = structure.get("pages", [])
    if not isinstance(pages, list):
        pages = [structure]
    for page in pages:
        if not isinstance(page, dict):
            continue
        blocks = page.get("blocks", page.get("regions", []))
        if isinstance(blocks, list):
            result.extend(item for item in blocks if isinstance(item, dict))
        elif page.get("text") or page.get("value"):
            result.append(page)
    return result


def _source_image_hash(structure: dict[str, Any]) -> str:
    evidence = structure.get("source_evidence", {})
    if not isinstance(evidence, dict):
        return ""
    return str(evidence.get("source_image_hash", ""))


def _pattern(value: str) -> re.Pattern[str]:
    escaped = re.escape(value.strip()).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![\w]){escaped}(?![\w])", re.IGNORECASE)
