from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import place_from_jsonld


PLACE_UPDATE_FIELDS = {
    "place.preferred_label": ("preferred_label", False),
    "place.alternate_label": ("alternate_labels", True),
    "place.same_as": ("same_as", True),
    "place.type": ("place_type", False),
    "place.description": ("description", False),
}


def build_candidate_place_updates(*, candidate_claims_json: Path, place_jsonld: Path) -> dict[str, Any]:
    """Build review candidates without modifying the selected Place or its claims."""
    place_payload = _load_object(place_jsonld)
    if place_payload.get("@type") != "Place":
        raise ValueError("Expected a Place JSON-LD document.")
    place_id = _text(place_payload.get("place_id") or place_payload.get("@id"))
    if not place_id or any(
        _text(place_payload.get(key)) not in ("", place_id) for key in ("place_id", "@id")
    ):
        raise ValueError("Place identifiers are missing or divergent.")
    place = place_from_jsonld(place_payload)
    claims_payload = _load_object(candidate_claims_json)
    if claims_payload.get("@type") != "CandidateEvidenceClaimSet" or not isinstance(
        claims_payload.get("candidate_evidence_claims"), list
    ):
        raise ValueError("Expected a CandidateEvidenceClaimSet.")

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    skipped: list[dict[str, Any]] = []
    for claim in claims_payload["candidate_evidence_claims"]:
        reason = _skip_reason(claim, place_id=place_id)
        if reason:
            skipped.append(
                {
                    "claim_id": _text(claim.get("@id") or claim.get("claim_id")) if isinstance(claim, dict) else "",
                    "reason": reason,
                    "source_document_id": _text(claim.get("source_document_id")) if isinstance(claim, dict) else "",
                }
            )
            continue
        grouped[(_text(claim["field"]), claim["value"].strip())].append(claim)

    values_by_field: dict[str, set[str]] = defaultdict(set)
    for field, value in grouped:
        values_by_field[field].add(value)
    updates: list[dict[str, Any]] = []
    for (field, value), claims in sorted(grouped.items()):
        claims = sorted(claims, key=lambda item: (_claim_id(item), _text(item["source_document_id"])))
        attribute, is_list = PLACE_UPDATE_FIELDS[field]
        current = getattr(place, attribute)
        current_values = list(current) if is_list else ([current] if current else [])
        classification = "existing" if value in current_values else ("new" if is_list or not current_values else "conflicting")
        competing = sorted(values_by_field[field] - {value}) if not is_list else []
        if classification == "new" and competing:
            classification = "conflicting"
        confidences = [float(item["confidence"]) for item in claims if item.get("confidence") is not None]
        identity = [place_id, field, value, [(_claim_id(item), item["source_document_id"]) for item in claims]]
        digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        updates.append(
            {
                "@type": "CandidatePlaceUpdate",
                "@id": f"candidate-place-update:{digest}",
                "place_id": place_id,
                "field": field,
                "candidate_value": value,
                "current_values": current_values,
                "classification": classification,
                "competing_candidate_values": competing,
                "review_status": "pending",
                "requires_human_review": True,
                "apply_allowed": False,
                "automatic_merge_allowed": False,
                "proposed_action": "review_same_as" if field == "place.same_as" else (
                    "review_alternate_label" if field == "place.alternate_label" else "review_value"
                ),
                "confidence": max(confidences) if confidences else None,
                "source_claim_ids": [_claim_id(item) for item in claims],
                "source_document_ids": sorted({_text(item["source_document_id"]) for item in claims}),
                "source_ids": sorted({_text(item["source_id"]) for item in claims}),
                "source_urls": sorted({_text(item.get(key)) for item in claims for key in ("source_url", "url") if _text(item.get(key))}),
                "evidence_spans": sorted({_text(item.get(key)) for item in claims for key in ("evidence_span", "quote") if _text(item.get(key))}),
                "source_claims": claims,
            }
        )
    return {
        "@type": "CandidatePlaceUpdateSet",
        "place_id": place_id,
        "place_source_file": str(place_jsonld),
        "input_candidate_claims": str(candidate_claims_json),
        "merge_policy": "preview_only_no_place_write",
        "preview_only": True,
        "place_write_allowed": False,
        "candidate_updates": updates,
        "skipped_claims": skipped,
    }


def _skip_reason(claim: Any, *, place_id: str) -> str:
    if not isinstance(claim, dict) or claim.get("@type", "CandidateEvidenceClaim") != "CandidateEvidenceClaim":
        return "unsupported_claim_type"
    if claim.get("review_status") != "unreviewed":
        return "claim_not_unreviewed"
    identities = {_text(claim.get(key)) for key in ("place_id", "subject_id") if _text(claim.get(key))}
    if len(identities) > 1:
        return "conflicting_place_identity"
    if not identities:
        return "missing_place_id"
    if identities != {place_id}:
        return "other_place"
    for field in ("source_document_id", "source_id"):
        if not _text(claim.get(field)):
            return f"missing_{field}"
    if not _claim_id(claim):
        return "missing_claim_id"
    if _text(claim.get("field")) not in PLACE_UPDATE_FIELDS:
        return "unsupported_field"
    if not isinstance(claim.get("value"), str) or not claim["value"].strip():
        return "missing_or_invalid_value"
    confidence = claim.get("confidence")
    if confidence is not None:
        try:
            number = float(confidence)
        except (TypeError, ValueError):
            return "invalid_confidence"
        if isinstance(confidence, bool) or not math.isfinite(number) or not 0 <= number <= 1:
            return "invalid_confidence"
    return ""


def _claim_id(claim: dict[str, Any]) -> str:
    return _text(claim.get("@id") or claim.get("claim_id"))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload
