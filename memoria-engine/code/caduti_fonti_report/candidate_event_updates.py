"""Review-only HistoricalEvent updates from claims bound to candidate links."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .models import historical_event_from_jsonld


EVENT_UPDATE_FIELDS = {
    "event.label": ("label", False),
    "event.event_type": ("event_type", False),
    "event.description": ("description", False),
    "event.date_start": ("date_start", False),
    "event.date_end": ("date_end", False),
    "event.place_labels": ("place_labels", True),
    "event.place_ids": ("place_ids", True),
}


def build_candidate_event_updates(
    *, candidate_claims_json: Path, candidate_event_links_json: Path, event_jsonld: Path,
) -> dict[str, Any]:
    """Return proposals for human review; this function never writes its inputs."""
    event_payload = _load(event_jsonld, "HistoricalEvent")
    event_id = _text(event_payload.get("event_id") or event_payload.get("@id"))
    if not event_id or any(_text(event_payload.get(key)) not in ("", event_id) for key in ("event_id", "@id")):
        raise ValueError("HistoricalEvent identifiers are missing or divergent.")
    event = historical_event_from_jsonld(event_payload)
    claims = _load(candidate_claims_json, "CandidateEvidenceClaimSet")
    links = _load(candidate_event_links_json, "CandidateDocumentEventLinkSet")
    if not isinstance(claims.get("candidate_evidence_claims"), list):
        raise ValueError("CandidateEvidenceClaimSet requires candidate_evidence_claims.")
    if not isinstance(links.get("candidate_document_event_links"), list):
        raise ValueError("CandidateDocumentEventLinkSet requires candidate_document_event_links.")
    if links.get("preview_only") is not True or links.get("event_write_allowed") is not False:
        raise ValueError("Event link set must be a preview with event writes disabled.")

    link_ids = Counter(_identifier(item) for item in links["candidate_document_event_links"] if isinstance(item, dict))
    valid_links, skipped_links = [], []
    for link in links["candidate_document_event_links"]:
        reason = _link_error(link, link_ids)
        if reason:
            skipped_links.append({"link_id": _identifier(link), "reason": reason})
        else:
            valid_links.append(link)
    claim_ids = Counter(_identifier(item) for item in claims["candidate_evidence_claims"] if isinstance(item, dict))
    grouped: dict[tuple[str, str], list[tuple[dict[str, Any], list[dict[str, Any]]]]] = defaultdict(list)
    skipped = []
    for claim in claims["candidate_evidence_claims"]:
        reason = _claim_error(claim, event_id, claim_ids)
        matches = []
        if not reason:
            matches = [link for link in valid_links if all(
                _text(link.get(key)) == _text(claim.get(key)) for key in ("source_id", "source_document_id")
            ) and link["event_id"] == event_id]
            for claim_key, link_key in (("candidate_document_event_link_id", "@id"), ("weak_segment_id", "weak_segment_id"), ("chunk_id", "chunk_id")):
                if _text(claim.get(claim_key)):
                    matches = [link for link in matches if _text(link.get(link_key)) == _text(claim[claim_key])]
            if not matches:
                reason = "missing_compatible_event_link"
        if reason:
            skipped.append({"claim_id": _identifier(claim), "reason": reason,
                            "source_document_id": _text(claim.get("source_document_id")) if isinstance(claim, dict) else ""})
        else:
            grouped[(claim["field"], claim["value"].strip())].append((claim, matches))

    values_by_field: dict[str, set[str]] = defaultdict(set)
    for field, value in grouped:
        values_by_field[field].add(value)
    updates = []
    for (field, value), evidence in sorted(grouped.items()):
        evidence.sort(key=lambda item: _identifier(item[0]))
        source_claims = [item[0] for item in evidence]
        bound_links = {link["@id"]: link for _, matches in evidence for link in matches}
        attribute, is_list = EVENT_UPDATE_FIELDS[field]
        current = getattr(event, attribute)
        current_values = list(current) if is_list else ([current] if current else [])
        competing = sorted(values_by_field[field] - {value}) if not is_list else []
        classification = "existing" if value in current_values else (
            "conflicting" if (current_values and not is_list) or competing else "new"
        )
        identity = [event_id, field, value, [_identifier(claim) for claim in source_claims], sorted(bound_links)]
        confidences = [float(claim["confidence"]) for claim in source_claims if claim.get("confidence") is not None]
        updates.append({
            "@type": "CandidateEventUpdate", "@id": "candidate-event-update:" + _digest(json.dumps(identity).encode())[:16],
            "event_id": event_id, "field": field, "candidate_value": value,
            "current_values": current_values, "classification": classification,
            "competing_candidate_values": competing, "review_status": "pending",
            "requires_human_review": True, "apply_allowed": False,
            "automatic_merge_allowed": False, "event_write_allowed": False,
            "confidence": max(confidences) if confidences else None,
            "source_claim_ids": [_identifier(claim) for claim in source_claims],
            "source_document_ids": sorted({claim["source_document_id"] for claim in source_claims}),
            "source_ids": sorted({claim["source_id"] for claim in source_claims}),
            "candidate_document_event_link_ids": sorted(bound_links),
            "source_claims": source_claims,
            "candidate_document_event_links": [bound_links[key] for key in sorted(bound_links)],
            "warnings": ["event_update_not_verified_fact", "event_update_not_person_participation"],
        })
    return {
        "@type": "CandidateEventUpdateSet", "event_id": event_id,
        "inputs": {name: {"path": str(path), "sha256": _digest(path.read_bytes())} for name, path in (
            ("event", event_jsonld), ("candidate_claims", candidate_claims_json), ("candidate_event_links", candidate_event_links_json))},
        "merge_policy": "preview_only_no_event_write", "preview_only": True,
        "review_status": "pending", "requires_human_review": True,
        "apply_allowed": False, "automatic_merge_allowed": False, "event_write_allowed": False,
        "candidate_updates": updates, "skipped_claims": skipped, "skipped_links": skipped_links,
    }


def _claim_error(claim: Any, event_id: str, identifiers: Counter) -> str:
    if not isinstance(claim, dict) or claim.get("@type") != "CandidateEvidenceClaim":
        return "unsupported_claim_type"
    if claim.get("review_status") != "unreviewed":
        return "claim_not_unreviewed"
    identities = {_text(claim.get(key)) for key in ("event_id", "subject_id") if _text(claim.get(key))}
    if len(identities) > 1:
        return "conflicting_event_identity"
    if not identities:
        return "missing_event_id"
    if identities != {event_id}:
        return "other_event"
    for key in ("source_document_id", "source_id"):
        if not _text(claim.get(key)):
            return "missing_" + key
    if not _identifier(claim):
        return "missing_claim_id"
    if identifiers[_identifier(claim)] != 1:
        return "duplicate_claim_id"
    if _text(claim.get("claim_id")) and _text(claim.get("@id")) and claim["claim_id"] != claim["@id"]:
        return "conflicting_claim_identity"
    if not isinstance(claim.get("field"), str) or claim["field"] not in EVENT_UPDATE_FIELDS:
        return "unsupported_field"
    if not _text(claim.get("value")):
        return "missing_or_invalid_value"
    confidence = claim.get("confidence")
    if confidence is not None:
        try:
            number = float(confidence)
        except (ValueError, TypeError):
            return "invalid_confidence"
        if isinstance(confidence, bool) or not math.isfinite(number) or not 0 <= number <= 1:
            return "invalid_confidence"
    return ""


def _link_error(link: Any, identifiers: Counter) -> str:
    if not isinstance(link, dict) or link.get("@type") != "CandidateDocumentEventLink":
        return "unsupported_link_type"
    for key in ("@id", "event_id", "source_id", "source_document_id"):
        if not _text(link.get(key)):
            return "missing_link_" + key
    if identifiers[_identifier(link)] != 1:
        return "duplicate_link_id"
    if link.get("review_status") != "unreviewed" or link.get("requires_human_review") is not True or link.get("event_write_allowed") is not False:
        return "link_not_review_only"
    return ""


def _identifier(item: Any) -> str:
    return _text(item.get("@id") or item.get("claim_id")) if isinstance(item, dict) else ""


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(path: Path, kind: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("@type") != kind:
        raise ValueError("Expected a " + kind + ".")
    return payload
