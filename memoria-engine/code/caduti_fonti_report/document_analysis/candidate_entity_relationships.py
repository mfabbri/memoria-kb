"""Compose typed, preview-only document-reference-to-entity candidate relationships."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


_LINK_INPUTS = (
    ("person", "CandidateDocumentPersonLinkSet", "CandidateDocumentPersonLink", "candidate_document_person_links", "profile_id",
     "PersonResearchProfile", "identity_match_candidate"),
    ("place", "CandidateDocumentPlaceLinkSet", "CandidateDocumentPlaceLink", "candidate_document_place_links", "place_id",
     "Place", "place_mention_candidate"),
    ("event", "CandidateDocumentEventLinkSet", "CandidateDocumentEventLink", "candidate_document_event_links", "event_id",
     "HistoricalEvent", "event_mention_candidate"),
)


def build_candidate_entity_relationships(*, person_links_json: Path, place_links_json: Path,
                                        event_links_json: Path, output_dir: Path) -> dict[str, Any]:
    inputs = {"person": person_links_json, "place": place_links_json, "event": event_links_json}
    references = {}
    relations = []
    for kind, expected_type, link_type, collection_key, target_key, target_type, relation_kind in _LINK_INPUTS:
        path = inputs[kind].resolve()
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("@type") != expected_type:
            raise ValueError(f"Expected {expected_type} input for {kind} relationships.")
        links = payload.get(collection_key)
        if not isinstance(links, list) or any(not isinstance(link, dict) for link in links):
            raise ValueError(f"{expected_type} requires an object list: {collection_key}.")
        references[kind] = {"path": str(path), "sha256": _digest(raw)}
        for index, link in enumerate(links):
            relation = _candidate_relation(
                kind=kind, link=link, target_key=target_key, target_type=target_type,
                relation_kind=relation_kind, expected_link_type=link_type, source_ref=references[kind], index=index,
            )
            relations.append(relation)

    relations.sort(key=lambda item: (item["source_document_id"], item["relation_kind"],
                                     item["target_entity_id"], item["evidence"]["evidence_id"], item["@id"]))
    result = {
        "@type": "CandidateEntityRelationshipSet",
        "schema_version": "1.0",
        "input_link_sets": references,
        "candidate_relationships": relations,
        "relationship_count": len(relations),
        "source_document_count": len({item["source_document_id"] for item in relations}),
        "preview_only": True,
        "review_status": "unreviewed",
        "requires_human_review": True,
        "source_document_existence_verified": False,
        "historical_fact_asserted": False,
        "claim_promotion_allowed": False,
        "canonical_write_allowed": False,
    }
    _write_preview(output_dir=output_dir, payload=result)
    return result


def _candidate_relation(*, kind: str, link: dict[str, Any], target_key: str, target_type: str,
                        relation_kind: str, expected_link_type: str,
                        source_ref: dict[str, str], index: int) -> dict[str, Any]:
    source_id = _required_text(link, "source_id")
    document_id = _required_text(link, "source_document_id")
    target_id = _required_text(link, target_key)
    link_id = _required_text(link, "@id")
    if link.get("@type") != expected_link_type:
        raise ValueError(f"Expected {expected_link_type} candidate link: {link_id}.")
    if link.get("review_status") != "unreviewed":
        raise ValueError(f"{kind} link must remain unreviewed: {link_id}.")
    context = _text(link.get("context")) or _text(link.get("matched_name")) or _text(link.get("matched_label"))
    if not context:
        raise ValueError(f"Candidate relationship requires evidence text: {link_id}.")
    mention_id = _text(link.get("mention_id"))
    chunk_id = _text(link.get("chunk_id"))
    segment_id = _text(link.get("weak_segment_id"))
    evidence_id = mention_id or _text(link.get("evidence_id")) or "context:" + _digest(
        f"{source_id}|{document_id}|{chunk_id}|{segment_id}|{context}".encode("utf-8"))[:16]
    identity = [relation_kind, source_id, document_id, target_id, link_id, evidence_id]
    warnings = list(link.get("warnings", [])) if isinstance(link.get("warnings"), list) else []
    warnings.extend(["candidate_relationship_not_verified", "historical_fact_not_asserted"])
    if kind == "person":
        warnings.append("identity_match_requires_human_review")
    if kind == "event":
        warnings.append("event_mention_does_not_assert_person_participation")
    return {
        "@type": "CandidateEntityRelationship",
        "@id": "candidate-entity-relationship:" + _digest(json.dumps(identity, ensure_ascii=False).encode("utf-8"))[:16],
        "relation_kind": relation_kind,
        "subject_entity_type": "SourceDocumentReference",
        "subject_entity_id": document_id,
        "target_entity_type": target_type,
        "target_entity_id": target_id,
        "source_id": source_id,
        "source_document_id": document_id,
        "evidence": {
            "evidence_id": evidence_id,
            "mention_id": mention_id,
            "chunk_id": chunk_id,
            "weak_segment_id": segment_id,
            "text": context,
            "link_id": link_id,
            "link_set": source_ref,
            "link_index": index,
        },
        "review_status": "unreviewed",
        "requires_human_review": True,
        "historical_fact_asserted": False,
        "warnings": sorted(set(warnings)),
    }


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = _text(payload.get(key))
    if not value:
        raise ValueError(f"Candidate relationship requires {key}.")
    return value


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_preview(*, output_dir: Path, payload: dict[str, Any]) -> None:
    output_dir = output_dir.resolve()
    files = {
        "candidate_entity_relationships.json": (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "candidate_entity_relationships.md": _render_markdown(payload).encode("utf-8"),
    }
    manifest = {
        "@type": "CandidateEntityRelationshipManifest",
        "schema_version": "1.0",
        "relationship_count": payload["relationship_count"],
        "source_document_count": payload["source_document_count"],
        "input_link_sets": payload["input_link_sets"],
        "flags": {key: payload[key] for key in (
            "preview_only", "review_status", "requires_human_review", "source_document_existence_verified",
            "historical_fact_asserted", "claim_promotion_allowed", "canonical_write_allowed",
        )},
        "artifacts": {name: {"path": str((output_dir / name).resolve()), "sha256": _digest(data)}
                      for name, data in files.items()},
    }
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError("Relationship preview output must be a directory.")
        entries = list(output_dir.iterdir())
        if entries and (set(path.name for path in entries) != set(files)
                        or any(not (output_dir / name).is_file() or (output_dir / name).read_bytes() != data
                               for name, data in files.items())):
            raise ValueError("Relationship output must be new, empty, or an identical prior preview.")
        if entries:
            return
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (output_dir / name).write_bytes(data)


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Candidate entity relationships", "", "Candidate links require human review; no historical fact is asserted.",
             "", f"- Candidate relationships: `{payload['relationship_count']}`",
             f"- SourceDocuments represented: `{payload['source_document_count']}`", ""]
    for relation in payload["candidate_relationships"]:
        evidence = relation["evidence"]
        lines.extend([f"## {relation['relation_kind']}", "",
                      f"- SourceDocument: `{relation['source_document_id']}` (source `{relation['source_id']}`)",
                      f"- Target: `{relation['target_entity_type']}` `{relation['target_entity_id']}`",
                      f"- Evidence: `{evidence['evidence_id']}` — {evidence['text']}",
                      f"- Review: `{relation['review_status']}`", ""])
    return "\n".join(lines).rstrip() + "\n"
