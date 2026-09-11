from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any


_RESOLUTIONS = {"create_new", "link_existing", "blocked_collision"}
_REQUIRED_PROVENANCE = (
    "candidate_id",
    "candidate_artifact_hash",
    "decision_set_id",
    "decision_set_hash",
    "decision_json_pointer",
    "accepted_decision",
    "reviewer",
    "reviewed_at",
    "source_profile_id",
    "source_run_id",
    "source_document_id",
    "source_url",
    "context_quote",
    "confidence",
)


@dataclass(frozen=True)
class CandidateNewProfileMaterializationPlan(Mapping[str, Any]):
    """Read-only preview plan; it never writes a canonical profile."""

    _payload: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self._payload[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._payload)

    def __len__(self) -> int:
        return len(self._payload)

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self._payload)


def build_candidate_new_profile_materialization_plan(
    *,
    candidate: Mapping[str, Any],
    decision: Mapping[str, Any],
    candidate_artifact_hash: str,
    decision_set: Mapping[str, Any],
    resolution: str,
    existing_profile_id: str = "",
) -> CandidateNewProfileMaterializationPlan:
    """Build and validate one deterministic, preview-only candidate plan."""
    if resolution not in _RESOLUTIONS:
        raise ValueError("resolution deve essere create_new, link_existing o blocked_collision.")
    if str(decision.get("decision", "")).strip() != "accepted":
        raise ValueError("Solo una decisione accepted puo' autorizzare un piano dry-run.")

    name = _required(candidate, "detected_name")
    slug = _slugify(name)
    target_profile_id = f"person:purocielo:{slug}"
    target_profile_path = f"ricerche/person_profiles/purocielo-{slug}.jsonld"
    provenance = {
        "candidate_id": _required(candidate, "@id"),
        "candidate_artifact_hash": _required_value(candidate_artifact_hash, "candidate_artifact_hash"),
        "decision_set_id": _required(decision_set, "@id"),
        "decision_set_hash": _required(decision_set, "hash"),
        "decision_json_pointer": _required(decision, "json_pointer"),
        "accepted_decision": "accepted",
        "reviewer": _required(decision, "reviewer"),
        "reviewed_at": _required(decision, "reviewed_at"),
        "source_profile_id": _required(candidate, "source_profile_id"),
        "source_run_id": _required(candidate, "source_run_id"),
        "source_document_id": _required(candidate, "source_document_id"),
        "source_url": _required(candidate, "source_url"),
        "context_quote": _required(candidate, "context_quote"),
        "confidence": _required(candidate, "confidence"),
    }
    target: dict[str, Any] = {
        "profile_id": target_profile_id,
        "profile_path": target_profile_path,
    }
    if resolution == "link_existing":
        target["existing_profile_id"] = _required_value(existing_profile_id, "existing_profile_id")

    profile_seed: dict[str, Any] | None = None
    if resolution == "create_new":
        profile_seed = {
            "@id": target_profile_id,
            "@type": "PersonProfile",
            "identity": {"canonical_name": name},
            "seed_provenance": provenance,
        }

    plan: dict[str, Any] = {
        "@type": "CandidateNewProfileMaterializationPlan",
        "preview_only": True,
        "canonical_profiles_modified": False,
        "resolution": resolution,
        "authorization": {"accepted_authorizes": "plan_and_dry_run_only", "canonical_write_authorized": False},
        "candidate": {"id": provenance["candidate_id"], "detected_name": name, "review_status": "accepted"},
        "provenance": provenance,
        "target": target,
        "profile_seed": profile_seed,
        "manifest": {
            "@type": "CandidateNewProfileMaterializationManifestEntry",
            "candidate_id": provenance["candidate_id"],
            "resolution": resolution,
            "dry_run": True,
            "canonical_write_count": 0,
        },
        "rollback": {
            "rollback_required": False,
            "rollback_action": "no_canonical_write_to_revert",
            "backup_required_before_canonical_write": True,
        },
        "audit": {
            "@type": "CandidateNewProfileMaterializationAudit",
            "candidate_id": provenance["candidate_id"],
            "accepted_decision": "accepted",
            "review_status": "accepted",
            "reviewer": provenance["reviewer"],
            "reviewed_at": provenance["reviewed_at"],
            "status": "planned_preview_only",
        },
    }
    plan_hash = _payload_hash(plan)
    plan["plan_hash"] = plan_hash
    plan["manifest"]["plan_hash"] = plan_hash
    frozen = CandidateNewProfileMaterializationPlan(_freeze(plan))
    validate_candidate_new_profile_materialization_plan(frozen)
    return frozen


def validate_candidate_new_profile_materialization_plan(plan: Mapping[str, Any]) -> None:
    """Reject plans missing provenance or attempting canonical materialization."""
    if str(plan.get("@type", "")) != "CandidateNewProfileMaterializationPlan":
        raise ValueError("Piano non valido: @type richiesto.")
    if plan.get("preview_only") is not True or plan.get("canonical_profiles_modified") is not False:
        raise ValueError("Piano non valido: deve restare preview-only senza scritture canoniche.")
    authorization = _mapping(plan.get("authorization"), "authorization")
    if authorization.get("accepted_authorizes") != "plan_and_dry_run_only" or authorization.get("canonical_write_authorized") is not False:
        raise ValueError("Piano non valido: accepted autorizza soltanto piano e dry-run.")
    resolution = str(plan.get("resolution", ""))
    if resolution not in _RESOLUTIONS:
        raise ValueError("Piano non valido: resolution non supportata.")
    provenance = _mapping(plan.get("provenance"), "provenance")
    for key in _REQUIRED_PROVENANCE:
        _required(provenance, key)
    if provenance["accepted_decision"] != "accepted":
        raise ValueError("Piano non valido: decisione non accepted.")
    target = _mapping(plan.get("target"), "target")
    name = _required(_mapping(plan.get("candidate"), "candidate"), "detected_name")
    slug = _slugify(name)
    if target.get("profile_id") != f"person:purocielo:{slug}" or target.get("profile_path") != f"ricerche/person_profiles/purocielo-{slug}.jsonld":
        raise ValueError("Piano non valido: target non canonico per il nome candidato.")
    seed = plan.get("profile_seed")
    if resolution == "create_new":
        seed_data = _mapping(seed, "profile_seed")
        if set(seed_data) != {"@id", "@type", "identity", "seed_provenance"}:
            raise ValueError("Piano non valido: il seed create_new deve restare minimale.")
        if _mapping(seed_data.get("identity"), "profile_seed.identity") != {"canonical_name": name}:
            raise ValueError("Piano non valido: identity seed non coerente.")
    elif seed is not None:
        raise ValueError("Piano non valido: solo create_new puo' avere un profile_seed.")
    if resolution == "link_existing" and not str(target.get("existing_profile_id", "")).strip():
        raise ValueError("Piano non valido: link_existing richiede existing_profile_id.")
    rollback = _mapping(plan.get("rollback"), "rollback")
    if rollback.get("rollback_required") is not False or rollback.get("rollback_action") != "no_canonical_write_to_revert":
        raise ValueError("Piano non valido: rollback preview incoerente.")
    provided_hash = _required(plan, "plan_hash")
    unsigned = _thaw(plan)
    unsigned.pop("plan_hash", None)
    _mapping(unsigned.get("manifest"), "manifest").pop("plan_hash", None)
    if provided_hash != _payload_hash(unsigned):
        raise ValueError("Piano non valido: plan_hash divergente.")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return _FrozenMapping({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


class _FrozenMapping(Mapping[str, Any]):
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_thaw(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _required(payload: Mapping[str, Any], key: str) -> str:
    return _required_value(payload.get(key, ""), key)


def _required_value(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"Piano non valido: {label} obbligatorio.")
    return text


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Piano non valido: {label} deve essere un oggetto.")
    return value


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")
    if not slug:
        raise ValueError("Piano non valido: detected_name non produce uno slug.")
    return slug
