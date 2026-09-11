from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .candidate_new_profile_materialization import (
    CandidateNewProfileMaterializationPlan,
    build_candidate_new_profile_materialization_plan,
)


_RESOLUTIONS = {
    "Marciatori Adriano": ("create_new", ""),
    "Saba Mario": ("link_existing", "person:purocielo:saba-mario"),
    "Tacconi Rosa": ("create_new", ""),
    "Bergonzoni Lino": ("create_new", ""),
}
_DECISION_SET_ID = "decision-set:block5f"


def build_t34b_materialization_preflight(
    *,
    queue_payload: Mapping[str, Any],
    decision_set_block5f: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the four T34b plans from in-memory review artifacts only."""
    queue_items = _array(queue_payload, "items")
    decisions = _array(decision_set_block5f, "decisions")
    accepted = [decision for decision in decisions if _text(decision, "decision") == "accepted"]
    accepted_names = {_text(decision, "candidate_name") for decision in accepted}
    if accepted_names != set(_RESOLUTIONS) or len(accepted) != 4:
        raise ValueError("Decision set block5f deve contenere esattamente i quattro accepted T34b.")

    queue_by_id = {
        _text(item, "candidate_update_id"): item
        for item in queue_items
        if isinstance(item, Mapping) and _text(item, "item_type") == "CandidateNewProfile"
    }
    candidate_artifact_hash = _hash(queue_payload)
    decision_set = {"@id": _DECISION_SET_ID, "hash": _hash(decision_set_block5f)}
    plans: list[CandidateNewProfileMaterializationPlan] = []
    for index, decision in enumerate(decisions):
        if not isinstance(decision, Mapping) or _text(decision, "decision") != "accepted":
            continue
        candidate_id = _text(decision, "candidate_new_profile_id")
        item = queue_by_id.get(candidate_id)
        if item is None:
            raise ValueError(f"Candidate ID non trovato nella coda: {candidate_id}.")
        candidate = _normalize_queue_item(item)
        name = candidate["detected_name"]
        if name != _text(decision, "candidate_name"):
            raise ValueError("Resolution incoerente: candidate_name non coincide con la coda.")
        resolution, existing_profile_id = _RESOLUTIONS[name]
        if _text(item, "suggested_profile_id") != _text(decision, "suggested_profile_id"):
            raise ValueError("Resolution incoerente: suggested_profile_id divergente.")
        normalized_decision = {
            "decision": "accepted",
            "json_pointer": f"/decisions/{index}",
            "reviewer": _text(decision, "reviewer"),
            "reviewed_at": _text(decision, "reviewed_at"),
        }
        plans.append(
            build_candidate_new_profile_materialization_plan(
                candidate=candidate,
                decision=normalized_decision,
                candidate_artifact_hash=candidate_artifact_hash,
                decision_set=decision_set,
                resolution=resolution,
                existing_profile_id=existing_profile_id,
            )
        )

    plans.sort(key=lambda plan: plan["candidate"]["detected_name"])
    plan_hashes = [plan["plan_hash"] for plan in plans]
    return {
        "@type": "T34bCandidateNewProfileMaterializationPreflight",
        "preview_only": True,
        "canonical_profiles_modified": False,
        "plans": plans,
        "manifest": {
            "@type": "T34bCandidateNewProfileMaterializationManifest",
            "decision_set_id": _DECISION_SET_ID,
            "candidate_artifact_hash": candidate_artifact_hash,
            "decision_set_hash": decision_set["hash"],
            "plan_count": len(plans),
            "plan_hashes": plan_hashes,
            "canonical_write_count": 0,
        },
    }


def _normalize_queue_item(item: Mapping[str, Any]) -> dict[str, Any]:
    document_ids = _nonempty_array(item, "source_document_ids")
    urls = _nonempty_array(item, "source_urls")
    return {
        "@id": _text(item, "candidate_update_id"),
        "detected_name": _text(item, "candidate_value"),
        "source_profile_id": _text(item, "profile_id"),
        "source_run_id": _text(item, "run_id"),
        "source_document_id": document_ids[0],
        "source_url": urls[0],
        "context_quote": _text(item, "context_quote"),
        # The real T34 queue does not carry confidence: preserve that fact rather
        # than inventing a numeric confidence for an accepted human decision.
        "confidence": "not_recorded_in_t34_queue",
    }


def _array(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} deve essere un array.")
    return value


def _nonempty_array(payload: Mapping[str, Any], key: str) -> list[str]:
    values = [_text_value(value) for value in _array(payload, key)]
    values = [value for value in values if value]
    if not values:
        raise ValueError(f"{key} non puo' essere vuoto.")
    return values


def _text(payload: Mapping[str, Any], key: str) -> str:
    value = _text_value(payload.get(key, ""))
    if not value:
        raise ValueError(f"{key} obbligatorio.")
    return value


def _text_value(value: Any) -> str:
    return str(value).strip()


def _hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
