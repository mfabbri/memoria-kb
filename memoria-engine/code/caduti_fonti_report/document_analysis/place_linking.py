from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from caduti_fonti_report.knowledge_catalog import default_places_index_path


@dataclass(frozen=True)
class PlaceLabelCandidate:
    place_id: str
    place_source_file: str
    preferred_label: str
    matched_label: str
    match_kind: str
    normalized_label: str
    review_status: str


def build_candidate_document_place_links(
    *,
    mentions_dir: Path,
    places_index: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    place_labels = _place_label_candidates(places_index)
    labels_by_normalized: dict[str, list[PlaceLabelCandidate]] = {}
    for candidate in place_labels:
        labels_by_normalized.setdefault(candidate.normalized_label, []).append(candidate)

    links: list[dict[str, Any]] = []
    skipped_mentions: list[dict[str, str]] = []
    skipped_documents: list[dict[str, str]] = []
    seen_link_keys: set[tuple[str, str, str]] = set()

    for mentions_path in sorted(mentions_dir.rglob("*.mentions.json")):
        payload = _load_json_object(mentions_path)
        if str(payload.get("@type", "")) != "DocumentMentionCandidateDocument":
            skipped_documents.append({"mentions_file": str(mentions_path), "reason": "unsupported_payload_type"})
            continue
        for mention in payload.get("mentions", []):
            if not isinstance(mention, dict) or str(mention.get("mention_kind", "")) != "place":
                continue
            if _is_navigation_or_boilerplate_context(mention):
                skipped_mentions.append(
                    _skipped_mention(
                        mention=mention,
                        mentions_path=mentions_path,
                        reason="navigation_or_boilerplate_context",
                    )
                )
                continue
            normalized_value = _normalize_label(str(mention.get("value", "")))
            matches = _unique_place_matches(labels_by_normalized.get(normalized_value, []))
            if len(matches) != 1:
                skipped_mentions.append(
                    _skipped_mention(
                        mention=mention,
                        mentions_path=mentions_path,
                        reason="place_not_found" if not matches else "ambiguous_place_label",
                    )
                )
                continue
            link_key = _candidate_link_key(mention=mention, candidate=matches[0])
            if link_key in seen_link_keys:
                skipped_mentions.append(
                    _skipped_mention(
                        mention=mention,
                        mentions_path=mentions_path,
                        reason="duplicate_place_link_in_segment",
                    )
                )
                continue
            seen_link_keys.add(link_key)
            links.append(_candidate_link(mention=mention, mentions_path=mentions_path, candidate=matches[0]))

    links = _deduplicate_links(links)
    result = {
        "@type": "CandidateDocumentPlaceLinkSet",
        "mentions_dir": str(mentions_dir),
        "places_index": str(places_index),
        "link_count": len(links),
        "skipped_mention_count": len(skipped_mentions),
        "skipped_document_count": len(skipped_documents),
        "candidate_document_place_links": links,
        "skipped_mentions": skipped_mentions,
        "skipped_documents": skipped_documents,
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_candidate_document_place_links_markdown(result), encoding="utf-8")

    return result


def render_candidate_document_place_links_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CandidateDocumentPlaceLink preview",
        "",
        f"- Indice luoghi: `{payload.get('places_index', '')}`",
        f"- Link candidati: `{payload.get('link_count', 0)}`",
        f"- Menzioni saltate: `{payload.get('skipped_mention_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_document_count', 0)}`",
        "",
        "## Link candidati",
        "",
    ]
    links = payload.get("candidate_document_place_links", [])
    if not isinstance(links, list) or not links:
        lines.append("_Nessun link candidato._")
    else:
        for link in links:
            lines.extend(
                [
                    f"### {link.get('matched_label', '')}",
                    "",
                    f"- Luogo: `{link.get('place_id', '')}`",
                    f"- Documento: `{link.get('source_document_id', '')}`",
                    f"- Fonte: `{link.get('source_id', '')}`",
                    f"- Menzione: `{link.get('mention_id', '')}`",
                    f"- Stato revisione: `{link.get('review_status', '')}`",
                    f"- Score: `{link.get('score', '')}`",
                    f"- Motivi: {', '.join(str(reason) for reason in link.get('reasons', []))}",
                    f"- Contesto: {link.get('context', '')}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _place_label_candidates(index_path: Path) -> list[PlaceLabelCandidate]:
    index_payload = _load_json_object(index_path)
    index_dir = index_path.parent
    candidates: list[PlaceLabelCandidate] = []
    for entry in _list_dicts(index_payload.get("places")):
        place_file = str(entry.get("file", "")).strip()
        place_path = index_dir / place_file if place_file else Path("")
        place_payload = _load_json_object(place_path)
        place_id = str(place_payload.get("place_id") or place_payload.get("@id") or entry.get("@id") or "")
        preferred_label = str(place_payload.get("preferred_label") or entry.get("preferred_label") or "").strip()
        review_status = str(place_payload.get("review_status") or entry.get("review_status") or "unreviewed")
        if not place_id or not preferred_label:
            continue
        labels = [(preferred_label, "preferred_label")]
        labels.extend((label, "alternate_label") for label in _list_strings(place_payload.get("alternate_labels")))
        for label, kind in labels:
            normalized = _normalize_label(label)
            if not normalized:
                continue
            candidates.append(
                PlaceLabelCandidate(
                    place_id=place_id,
                    place_source_file=str(place_path),
                    preferred_label=preferred_label,
                    matched_label=label.strip(),
                    match_kind=kind,
                    normalized_label=normalized,
                    review_status=review_status,
                )
            )
    return _deduplicate_candidates(candidates)


def _candidate_link(*, mention: dict[str, Any], mentions_path: Path, candidate: PlaceLabelCandidate) -> dict[str, Any]:
    mention_id = str(mention.get("mention_id") or mention.get("@id") or "")
    source_document_id = str(mention.get("source_document_id", ""))
    return {
        "@type": "CandidateDocumentPlaceLink",
        "@id": _candidate_link_id(candidate.place_id, source_document_id, mention_id),
        "place_id": candidate.place_id,
        "place_source_file": candidate.place_source_file,
        "preferred_label": candidate.preferred_label,
        "matched_label": str(mention.get("value", "")),
        "matched_catalog_label": candidate.matched_label,
        "match_kind": candidate.match_kind,
        "mention_id": mention_id,
        "source_id": str(mention.get("source_id", "")),
        "source_document_id": source_document_id,
        "mentions_file": str(mentions_path),
        "chunk_id": str(mention.get("chunk_id", "")),
        "weak_segment_id": str(mention.get("weak_segment_id", "")),
        "context": str(mention.get("context", "")),
        "score": _candidate_score(candidate.match_kind),
        "reasons": [f"normalized_{candidate.match_kind}_match"],
        "warnings": ["place_link_not_verified_fact", "place_link_not_person_presence"],
        "catalog_review_status": candidate.review_status,
        "review_status": "unreviewed",
    }


def _skipped_mention(*, mention: dict[str, Any], mentions_path: Path, reason: str) -> dict[str, str]:
    return {
        "mention_id": str(mention.get("mention_id") or mention.get("@id") or ""),
        "value": str(mention.get("value", "")),
        "source_document_id": str(mention.get("source_document_id", "")),
        "mentions_file": str(mentions_path),
        "reason": reason,
    }


def _candidate_link_key(*, mention: dict[str, Any], candidate: PlaceLabelCandidate) -> tuple[str, str, str]:
    source_document_id = str(mention.get("source_document_id", ""))
    weak_segment_id = str(mention.get("weak_segment_id", ""))
    if not weak_segment_id:
        weak_segment_id = _context_fingerprint(str(mention.get("context", "")))
    return (source_document_id, candidate.place_id, weak_segment_id)


def _is_navigation_or_boilerplate_context(mention: dict[str, Any]) -> bool:
    context = _normalize_label(str(mention.get("context", "")))
    if not context:
        return False
    strong_markers = [
        "salta al contenuto",
        "menu home",
        "centro di documentazione",
        "documentazione dalla resistenza",
    ]
    return any(marker in context for marker in strong_markers)


def _deduplicate_candidates(candidates: list[PlaceLabelCandidate]) -> list[PlaceLabelCandidate]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[PlaceLabelCandidate] = []
    for candidate in candidates:
        key = (candidate.place_id, candidate.normalized_label, candidate.match_kind)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _unique_place_matches(candidates: list[PlaceLabelCandidate]) -> list[PlaceLabelCandidate]:
    by_place: dict[str, PlaceLabelCandidate] = {}
    for candidate in candidates:
        existing = by_place.get(candidate.place_id)
        if existing is None or _candidate_score(candidate.match_kind) > _candidate_score(existing.match_kind):
            by_place[candidate.place_id] = candidate
    return list(by_place.values())


def _deduplicate_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for link in links:
        link_id = str(link.get("@id", ""))
        if link_id in seen:
            continue
        seen.add(link_id)
        deduped.append(link)
    return deduped


def _candidate_link_id(place_id: str, source_document_id: str, mention_id: str) -> str:
    digest = hashlib.sha256(f"{place_id}|{source_document_id}|{mention_id}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-document-place-link:{digest}"


def _context_fingerprint(context: str) -> str:
    normalized = _normalize_label(context)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"context:{digest}"


def _candidate_score(match_kind: str) -> float:
    return 1.0 if match_kind == "preferred_label" else 0.9


def _normalize_label(value: str) -> str:
    value = value.casefold().replace("-", " ")
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        if not path or not path.exists() or not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera CandidateDocumentPlaceLink offline da menzioni documentali.")
    parser.add_argument("--mentions-dir", default="data/processed/documents")
    parser.add_argument("--places-index", default=str(default_places_index_path()))
    parser.add_argument("--output-json", default="risultati/document_analysis/candidate_document_place_links.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/candidate_document_place_links.md")
    args = parser.parse_args()

    payload = build_candidate_document_place_links(
        mentions_dir=Path(args.mentions_dir),
        places_index=Path(args.places_index),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"CandidateDocumentPlaceLink JSON scritto in {args.output_json}")
    print(f"CandidateDocumentPlaceLink Markdown scritto in {args.output_md}")
    print(f"Link candidati: {payload['link_count']}")
    print(f"Menzioni saltate: {payload['skipped_mention_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
