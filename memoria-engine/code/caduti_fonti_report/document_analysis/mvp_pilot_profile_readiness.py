from __future__ import annotations

from typing import Any

from .mvp_pilot_readiness import readiness_status_and_action


def build_profile_readiness(
    *,
    profiles: list[dict[str, str]],
    documents: list[dict[str, Any]],
    links: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    reviewable_document_signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    document_ids = {
        str(document.get("source_document_id", ""))
        for document in documents
        if str(document.get("source_document_id", ""))
    }
    signals_by_profile = {
        str(group.get("profile_id", "")): [item for item in group.get("signals", []) if isinstance(item, dict)]
        for group in reviewable_document_signals
        if str(group.get("profile_id", ""))
    }
    readiness = []
    for profile in profiles:
        profile_id = str(profile.get("profile_id", ""))
        profile_links = [link for link in links if _profile_id_from_item(link) == profile_id]
        profile_claims = [claim for claim in claims if _profile_id_from_item(claim) == profile_id]
        profile_signals = signals_by_profile.get(profile_id, [])
        profile_document_ids = {
            str(item.get("source_document_id", ""))
            for item in [*profile_links, *profile_claims, *profile_signals]
            if str(item.get("source_document_id", ""))
        }
        if document_ids:
            profile_document_ids &= document_ids
        status, next_action = readiness_status_and_action(
            document_count=len(profile_document_ids),
            link_count=len(profile_links),
            claim_count=len(profile_claims),
            signal_count=len(profile_signals),
        )
        readiness.append(
            {
                "profile_id": profile_id,
                "canonical_name": profile.get("canonical_name", ""),
                "document_count": len(profile_document_ids),
                "candidate_document_person_link_count": len(profile_links),
                "candidate_evidence_claim_count": len(profile_claims),
                "reviewable_document_signal_count": len(profile_signals),
                "readiness_status": status,
                "next_action": next_action,
                "review_status": "unreviewed",
                "publication_status": "not_publishable_without_human_review",
            }
        )
    return readiness


def _profile_id_from_item(item: dict[str, Any]) -> str:
    return str(item.get("profile_id") or item.get("person_candidate_id") or item.get("person_id") or "")
