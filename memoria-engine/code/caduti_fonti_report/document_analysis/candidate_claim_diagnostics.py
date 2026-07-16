from __future__ import annotations

from collections import Counter
from typing import Any


def build_claim_funnel_diagnostics(
    *,
    claims: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    skipped_structured_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    claims_with_weak_segment = [
        claim for claim in claims if str(claim.get("weak_segment_id", "")).strip()
    ]
    claims_with_chunk_only = [
        claim
        for claim in claims
        if not str(claim.get("weak_segment_id", "")).strip()
        and str(claim.get("chunk_id", "")).strip()
    ]
    skipped_with_weak_segment = [
        item for item in skipped if str(item.get("weak_segment_id", "")).strip()
    ]
    skipped_with_chunk_only = [
        item
        for item in skipped
        if not str(item.get("weak_segment_id", "")).strip()
        and str(item.get("chunk_id", "")).strip()
    ]
    skipped_with_candidate_profiles = [
        item for item in skipped if _list_strings(item.get("candidate_profile_ids"))
    ]
    counts_by_skip_reason = Counter(
        str(item.get("reason", ""))
        for item in skipped
        if str(item.get("reason", "")).strip()
    )
    counts_by_structured_skip_reason = Counter(
        str(item.get("reason", ""))
        for item in skipped_structured_documents
        if str(item.get("reason", "")).strip()
    )
    counts_by_next_action = Counter(
        str(item.get("recommended_next_action", ""))
        for item in skipped
        if str(item.get("recommended_next_action", "")).strip()
    )
    return {
        "@type": "ClaimFunnelDiagnostics",
        "funnel_status": claim_funnel_status(claims=claims, skipped=skipped),
        "claim_count": len(claims),
        "skipped_entity_count": len(skipped),
        "skipped_structured_document_count": len(skipped_structured_documents),
        "claims_with_weak_segment_id_count": len(claims_with_weak_segment),
        "claims_with_chunk_id_only_count": len(claims_with_chunk_only),
        "claims_without_segment_context_count": len(claims) - len(claims_with_weak_segment) - len(claims_with_chunk_only),
        "skipped_with_weak_segment_id_count": len(skipped_with_weak_segment),
        "skipped_with_chunk_id_only_count": len(skipped_with_chunk_only),
        "skipped_with_candidate_profiles_count": len(skipped_with_candidate_profiles),
        "skipped_without_candidate_profiles_count": len(skipped) - len(skipped_with_candidate_profiles),
        "counts_by_skip_reason": dict(sorted(counts_by_skip_reason.items())),
        "counts_by_structured_skip_reason": dict(sorted(counts_by_structured_skip_reason.items())),
        "counts_by_recommended_next_action": dict(sorted(counts_by_next_action.items())),
        "next_action": claim_funnel_next_action(
            claims=claims,
            counts_by_skip_reason=counts_by_skip_reason,
            counts_by_next_action=counts_by_next_action,
        ),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def claim_funnel_status(*, claims: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> str:
    if claims and skipped:
        return "claims_with_reviewable_skips"
    if claims:
        return "claims_available"
    if skipped:
        return "blocked_with_reviewable_skips"
    return "no_claim_signal"


def claim_funnel_next_action(
    *,
    claims: list[dict[str, Any]],
    counts_by_skip_reason: Counter[str],
    counts_by_next_action: Counter[str],
) -> str:
    if counts_by_skip_reason.get("ambiguous_or_missing_document_person_link", 0):
        return "Rafforzare segmentazione o link documento-persona sui casi ambigui."
    if counts_by_next_action.get("quality_review", 0):
        return "Revisionare qualita' documento, OCR o classi documentali prima dei claim."
    if counts_by_skip_reason.get("unsupported_entity_context", 0):
        return "Revisionare manualmente entita' non mappate a campi claim supportati."
    if claims:
        return "Portare i claim candidati e gli skip residui in review queue."
    return "Produrre link, entita' o documenti revisionabili prima dei claim."


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
