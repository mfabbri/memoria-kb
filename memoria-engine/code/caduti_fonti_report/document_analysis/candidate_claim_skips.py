from __future__ import annotations

import hashlib
from typing import Any


def skipped_candidate_claim(*, entity: dict[str, Any], reason: str, links: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_links = candidate_links_for_skipped_entity(entity=entity, links=links)
    candidate_profile_ids = sorted(
        {
            str(link.get("profile_id", "")).strip()
            for link in candidate_links
            if str(link.get("profile_id", "")).strip()
        }
    )
    candidate_link_ids = [
        str(link.get("@id") or link.get("link_id") or "").strip()
        for link in candidate_links
        if str(link.get("@id") or link.get("link_id") or "").strip()
    ]
    return {
        "@type": "SkippedCandidateClaim",
        "@id": skipped_candidate_claim_id(entity=entity, reason=reason),
        "source_document_id": str(entity.get("source_document_id", "")).strip(),
        "source_id": str(entity.get("source_id", "")).strip(),
        "title": str(entity.get("title", "")).strip(),
        "entity_id": str(entity.get("@id") or entity.get("entity_id") or "").strip(),
        "entity_type": str(entity.get("entity_type", "")).strip(),
        "value": str(entity.get("value", "")).strip(),
        "normalized_value": str(entity.get("normalized_value", "")).strip(),
        "context": str(entity.get("context", "")).strip(),
        "chunk_id": str(entity.get("chunk_id", "")).strip(),
        "weak_segment_id": str(entity.get("weak_segment_id", "")).strip(),
        "reason": reason,
        "recommended_next_action": recommended_next_action_for_skipped_claim(reason),
        "candidate_profile_ids": candidate_profile_ids,
        "candidate_document_person_link_ids": candidate_link_ids,
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def skipped_structured_document(
    *,
    document_id: str,
    reason: str,
    quality: dict[str, Any],
    metadata: dict[str, Any],
    links: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_profile_ids = sorted(
        {
            str(link.get("profile_id", "")).strip()
            for link in links
            if str(link.get("profile_id", "")).strip()
        }
    )
    candidate_link_ids = [
        str(link.get("@id") or link.get("link_id") or "").strip()
        for link in links
        if str(link.get("@id") or link.get("link_id") or "").strip()
    ]
    source_id = str(metadata.get("source_id") or quality.get("source_id") or "").strip()
    return {
        "@type": "SkippedStructuredDocumentClaimCandidate",
        "@id": skipped_structured_document_id(document_id=document_id, reason=reason),
        "source_document_id": document_id,
        "source_id": source_id,
        "title": str(metadata.get("title") or quality.get("title") or "").strip(),
        "url": str(metadata.get("url") or quality.get("url") or "").strip(),
        "archival_reference": str(
            metadata.get("archival_reference") or quality.get("archival_reference") or ""
        ).strip(),
        "reason": reason,
        "recommended_next_action": recommended_next_action_for_skipped_claim(reason),
        "candidate_profile_ids": candidate_profile_ids,
        "candidate_document_person_link_ids": candidate_link_ids,
        "detail_assessment": str(metadata.get("detail_assessment", "")).strip(),
        "metadata_file": str(quality.get("metadata_file", "")).strip(),
        "quality_assessment_file": str(quality.get("_quality_file", "")).strip(),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def candidate_links_for_skipped_entity(*, entity: dict[str, Any], links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weak_segment_id = str(entity.get("weak_segment_id", "")).strip()
    if weak_segment_id:
        segment_links = [link for link in links if str(link.get("weak_segment_id", "")).strip() == weak_segment_id]
        if segment_links:
            return segment_links

    chunk_id = str(entity.get("chunk_id", "")).strip()
    if chunk_id:
        chunk_links = [link for link in links if str(link.get("chunk_id", "")).strip() == chunk_id]
        if chunk_links:
            return chunk_links

    return links


def recommended_next_action_for_skipped_claim(reason: str) -> str:
    if reason == "ambiguous_or_missing_document_person_link":
        return "better_segmentation_or_link_review"
    if reason in {"unsupported_entity_context", "entity_review_status_not_unreviewed"}:
        return "manual_review"
    if reason.startswith("quality_") or reason.startswith("skipped_"):
        return "quality_review"
    return "manual_review"


def skipped_candidate_claim_id(*, entity: dict[str, Any], reason: str) -> str:
    raw_id = str(entity.get("@id") or entity.get("entity_id") or "").strip()
    if raw_id:
        return f"skipped-candidate-claim:{raw_id}"
    digest = hashlib.sha256(
        "|".join(
            [
                str(entity.get("source_document_id", "")),
                str(entity.get("entity_type", "")),
                str(entity.get("value", "")),
                str(entity.get("context", "")),
                reason,
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"skipped-candidate-claim:{digest}"


def skipped_structured_document_id(*, document_id: str, reason: str) -> str:
    digest = hashlib.sha256(f"{document_id}|{reason}".encode("utf-8")).hexdigest()[:16]
    return f"skipped-structured-document-claim:{digest}"
