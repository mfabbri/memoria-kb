from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import PersonResearchProfile
from ..profile_repository import ProfileRepository

SKIPPED_DOCUMENT_CLASSES = {"result_page", "reference_page"}


@dataclass(frozen=True)
class ProfileNameCandidate:
    profile_id: str
    profile_source_file: str
    canonical_name: str
    matched_name: str
    match_kind: str
    normalized_name: str
    confidence: float = 1.0
    provenance: str = ""


def build_candidate_document_person_links(
    *,
    text_dir: Path,
    metadata_dir: Path,
    profiles_index: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    profile_names = _profile_name_candidates(profiles_index)
    links: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    links.extend(_links_from_segment_mentions(text_dir=text_dir, metadata_dir=metadata_dir, profile_names=profile_names))

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
        for candidate in profile_names:
            match = _match_name_in_text(text, candidate.matched_name)
            if not match:
                continue
            links.append(_candidate_link(candidate=candidate, metadata=metadata, text_payload=text_payload, match=match))

    links = _deduplicate_links(links)
    payload = {
        "@type": "CandidateDocumentPersonLinkSet",
        "text_dir": str(text_dir),
        "metadata_dir": str(metadata_dir),
        "profiles_index": str(profiles_index),
        "link_count": len(links),
        "skipped_count": len(skipped),
        "candidate_document_person_links": links,
        "skipped_documents": skipped,
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_candidate_document_person_links_markdown(payload), encoding="utf-8")

    return payload


def render_candidate_document_person_links_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CandidateDocumentPersonLink preview",
        "",
        f"- Profili indice: `{payload.get('profiles_index', '')}`",
        f"- Link candidati: `{payload.get('link_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Link candidati",
        "",
    ]
    links = payload.get("candidate_document_person_links", [])
    if not isinstance(links, list) or not links:
        lines.append("_Nessun link candidato._")
    else:
        for link in links:
            lines.extend(
                [
                    f"### {link.get('matched_name', '')}",
                    "",
                    f"- Profilo: `{link.get('profile_id', '')}`",
                    f"- Documento: `{link.get('source_document_id', '')}`",
                    f"- Fonte: `{link.get('source_id', '')}`",
                    f"- Titolo: {link.get('title', '')}",
                    f"- Stato revisione: `{link.get('review_status', '')}`",
                    f"- Score: `{link.get('score', '')}`",
                    f"- Motivi: {', '.join(str(reason) for reason in link.get('reasons', []))}",
                    f"- Contesto: {link.get('context', '')}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _profile_name_candidates(index_path: Path) -> list[ProfileNameCandidate]:
    repository = ProfileRepository(index_path)
    candidates: list[ProfileNameCandidate] = []
    for entry in repository.list_entries():
        profile = repository.load_entry(entry)
        for name, kind in _profile_names(profile):
            normalized = _normalize_name(name)
            if _is_conservative_name(normalized):
                candidates.append(
                    ProfileNameCandidate(
                        profile_id=profile.profile_id,
                        profile_source_file=str(profile.metadata.get("profile_source_file", "")),
                        canonical_name=profile.identity.canonical_name,
                        matched_name=name.strip(),
                        match_kind=kind,
                        normalized_name=normalized,
                    )
                )
    return _dedupe_profile_candidates(candidates)


def _profile_names(profile: PersonResearchProfile) -> list[tuple[str, str]]:
    names: list[tuple[str, str]] = [(profile.identity.canonical_name, "canonical_name")]
    names.extend((name, "alias") for name in profile.identity.aliases)
    names.extend((name, "name_form") for name in profile.identity.name_forms)
    names.extend(_identity_search_hint_names(profile))
    return names


def _identity_search_hint_names(profile: PersonResearchProfile) -> list[tuple[str, str]]:
    names: list[tuple[str, str]] = []
    allowed_fields = {"identity.full_name", "identity.name_form", "identity.alias"}
    for hint in profile.search_hints:
        if hint.field not in allowed_fields or hint.review_status not in {"", "unreviewed", "pending", "reviewed"}:
            continue
        value = hint.value.strip()
        if not value:
            continue
        suffix = hint.field.rsplit(".", 1)[-1].replace("full_name", "name_form")
        names.append((value, f"search_hint_{suffix}"))
    return names


def _is_conservative_name(normalized_name: str) -> bool:
    tokens = [token for token in normalized_name.split() if token]
    return len(tokens) >= 2 and all(len(token) >= 2 for token in tokens)


def _dedupe_profile_candidates(candidates: list[ProfileNameCandidate]) -> list[ProfileNameCandidate]:
    seen: set[tuple[str, str]] = set()
    deduped: list[ProfileNameCandidate] = []
    for candidate in candidates:
        key = (candidate.profile_id, candidate.normalized_name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


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
    try:
        if not path.exists() or not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
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


def _match_name_in_text(text: str, name: str) -> dict[str, Any]:
    pattern = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)
    match = pattern.search(text)
    match_type = "exact"
    if not match:
        normalized_pattern = _normalized_name_pattern(name)
        if normalized_pattern is None:
            return {}
        match = normalized_pattern.search(text)
        match_type = "normalized"
    if not match:
        return {}
    return {
        "start": match.start(),
        "end": match.end(),
        "context": _context(text, match.start(), match.end()),
        "match_type": match_type,
    }


def _candidate_link(
    *,
    candidate: ProfileNameCandidate,
    metadata: dict[str, Any],
    text_payload: dict[str, Any],
    match: dict[str, Any],
) -> dict[str, Any]:
    source_document_id = str(text_payload.get("source_document_id") or metadata.get("source_document_id") or "")
    source_id = str(text_payload.get("source_id") or metadata.get("source_id") or "")
    return {
        "@type": "CandidateDocumentPersonLink",
        "@id": _candidate_link_id(candidate.profile_id, source_document_id, candidate.normalized_name),
        "profile_id": candidate.profile_id,
        "profile_source_file": candidate.profile_source_file,
        "canonical_name": candidate.canonical_name,
        "matched_name": candidate.matched_name,
        "match_kind": candidate.match_kind,
        "source_id": source_id,
        "source_document_id": source_document_id,
        "title": str(metadata.get("title", "")),
        "url": str(metadata.get("url", "")),
        "archival_reference": str(metadata.get("archival_reference", "")),
        "raw_file": str(metadata.get("raw_file", "")),
        "metadata_file": str(text_payload.get("metadata_file", "")),
        "text_file": str(text_payload.get("_text_file", "")),
        "context": str(match.get("context", "")),
        "score": _candidate_score(candidate=candidate, match=match),
        "reasons": [_candidate_reason(candidate=candidate, match=match)],
        "review_status": "unreviewed",
    }


def _links_from_segment_mentions(
    *,
    text_dir: Path,
    metadata_dir: Path,
    profile_names: list[ProfileNameCandidate],
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for mentions_path in sorted(text_dir.rglob("*.mentions.json")):
        mentions_payload = _load_json_object(mentions_path)
        if not mentions_payload:
            continue
        for mention in _list_items(mentions_payload.get("mentions")):
            if str(mention.get("mention_kind", "")) != "person":
                continue
            if str(mention.get("review_status", "")) not in {"", "unreviewed"}:
                continue
            mention_name = _normalize_name(str(mention.get("value", "")))
            if not mention_name:
                continue
            for candidate in profile_names:
                if mention_name != candidate.normalized_name:
                    continue
                metadata = _metadata_for_mention(mention=mention, metadata_dir=metadata_dir)
                links.append(_candidate_link_from_mention(candidate=candidate, mention=mention, metadata=metadata, mentions_path=mentions_path))
    return links


def _metadata_for_mention(*, mention: dict[str, Any], metadata_dir: Path) -> dict[str, Any]:
    source_id = _safe_path_part(str(mention.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(mention.get("source_document_id", "")) or "unknown")
    metadata_path = metadata_dir / source_id / f"{document_id}.metadata.json"
    metadata = _load_json_object(metadata_path)
    if metadata:
        metadata["_metadata_file"] = str(metadata_path)
    return metadata


def _candidate_link_from_mention(
    *,
    candidate: ProfileNameCandidate,
    mention: dict[str, Any],
    metadata: dict[str, Any],
    mentions_path: Path,
) -> dict[str, Any]:
    source_document_id = str(mention.get("source_document_id") or metadata.get("source_document_id") or "")
    source_id = str(mention.get("source_id") or metadata.get("source_id") or "")
    weak_segment_id = str(mention.get("weak_segment_id", ""))
    chunk_id = str(mention.get("chunk_id", ""))
    score = min(float(mention.get("confidence", 0.0) or 0.0), candidate.confidence, 0.88)
    return {
        "@type": "CandidateDocumentPersonLink",
        "@id": _candidate_link_id(candidate.profile_id, source_document_id, f"{candidate.normalized_name}|{weak_segment_id}|{chunk_id}"),
        "profile_id": candidate.profile_id,
        "profile_source_file": candidate.profile_source_file,
        "canonical_name": candidate.canonical_name,
        "matched_name": candidate.matched_name,
        "match_kind": candidate.match_kind,
        "source_id": source_id,
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
        "score": round(score, 2),
        "reasons": [*_list_strings(mention.get("reasons")), "segment_name_match"],
        "review_status": "unreviewed",
    }


def _deduplicate_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    seen_document_matches: set[tuple[str, str]] = set()
    seen_profile_documents: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for link in links:
        link_id = str(link.get("@id", ""))
        if link_id in seen:
            continue
        profile_document_key = (str(link.get("profile_id", "")), str(link.get("source_document_id", "")))
        if not str(link.get("weak_segment_id", "")).strip() and not str(link.get("chunk_id", "")).strip():
            if profile_document_key in seen_profile_documents:
                continue
        document_match_key = (str(link.get("profile_id", "")), _document_fingerprint(link))
        if document_match_key in seen_document_matches:
            continue
        seen.add(link_id)
        seen_document_matches.add(document_match_key)
        seen_profile_documents.add(profile_document_key)
        deduped.append(link)
    return deduped


def _candidate_link_id(profile_id: str, source_document_id: str, normalized_name: str) -> str:
    digest = hashlib.sha256(f"{profile_id}|{source_document_id}|{normalized_name}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-document-person-link:{digest}"


def _document_fingerprint(link: dict[str, Any]) -> str:
    weak_segment_id = str(link.get("weak_segment_id", "")).strip()
    chunk_id = str(link.get("chunk_id", "")).strip()
    if weak_segment_id or chunk_id:
        return f"{str(link.get('source_document_id', '')).strip()}|{weak_segment_id}|{chunk_id}"
    source_document_id = str(link.get("source_document_id", "")).strip()
    hash_suffix = source_document_id.rsplit(":", 1)[-1]
    if re.fullmatch(r"[0-9a-fA-F]{12,64}", hash_suffix):
        return hash_suffix.casefold()
    title = _normalize_name(str(link.get("title", "")))
    raw_file = Path(str(link.get("raw_file", ""))).name.casefold()
    return title or raw_file or source_document_id


def _context(text: str, start: int, end: int, *, radius: int = 90) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


def _normalize_name(value: str) -> str:
    value = value.casefold().replace("-", " ")
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _normalized_name_pattern(name: str) -> re.Pattern[str] | None:
    tokens = [re.escape(token) for token in _normalize_name(name).split() if token]
    if len(tokens) < 2:
        return None
    return re.compile(r"(?<!\w)" + r"[\W_]+".join(tokens) + r"(?!\w)", re.IGNORECASE)


def _candidate_reason(*, candidate: ProfileNameCandidate, match: dict[str, Any]) -> str:
    match_type = str(match.get("match_type", "exact")) or "exact"
    return f"{match_type}_{candidate.match_kind}_match"


def _candidate_score(*, candidate: ProfileNameCandidate, match: dict[str, Any]) -> float:
    score = candidate.confidence
    if candidate.match_kind.startswith("search_hint_"):
        score = min(score, 0.85)
    if str(match.get("match_type", "exact")) == "normalized":
        score = min(score, 0.92)
    return round(score, 2)


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera CandidateDocumentPersonLink offline da testi processati.")
    parser.add_argument("--text-dir", default="data/processed/documents")
    parser.add_argument("--metadata-dir", default="data/processed/documents")
    parser.add_argument("--profiles-index", required=True)
    parser.add_argument("--output-json", default="risultati/document_analysis/candidate_document_person_links.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/candidate_document_person_links.md")
    args = parser.parse_args()

    payload = build_candidate_document_person_links(
        text_dir=Path(args.text_dir),
        metadata_dir=Path(args.metadata_dir),
        profiles_index=Path(args.profiles_index),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"CandidateDocumentPersonLink JSON scritto in {args.output_json}")
    print(f"CandidateDocumentPersonLink Markdown scritto in {args.output_md}")
    print(f"Link candidati: {payload['link_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
