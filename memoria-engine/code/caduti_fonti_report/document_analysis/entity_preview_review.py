"""Create review templates and hash-bound human decision receipts for entity previews."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


DECISIONS = {"accept_candidate", "reject_candidate", "needs_more_evidence"}


def build_entity_preview_review_template(*, manifest_json: Path) -> dict[str, Any]:
    manifest, manifest_hash, items, artifact_refs = _load_review_targets(manifest_json)
    return {
        "@type": "EntityPreviewHumanReviewDecisionSet",
        "preview_manifest": {"path": str(manifest_json.resolve()), "sha256": manifest_hash},
        "preview_type": manifest["@type"],
        "decision_values": sorted(DECISIONS),
        "review_status": "pending",
        "decisions": [
            {**item, "decision": "",
             "reviewer": "", "reviewed_at": "", "note": ""}
            for item in items
        ],
        "preview_artifacts": artifact_refs,
        "apply_allowed": False,
        "automatic_merge_allowed": False,
    }


def build_entity_preview_review_receipt(*, manifest_json: Path, decisions_json: Path) -> dict[str, Any]:
    payload = _load(decisions_json, "EntityPreviewHumanReviewDecisionSet")
    return _build_receipt(
        manifest_json=manifest_json, decisions_payload=payload,
        decisions_source={"method": "decision_file", "path": str(decisions_json.resolve()),
                          "sha256": _sha256(decisions_json)},
    )


def build_entity_preview_review_receipt_from_decisions(
    *, manifest_json: Path, decisions_payload: dict[str, Any],
) -> dict[str, Any]:
    canonical = json.dumps(decisions_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _build_receipt(
        manifest_json=manifest_json, decisions_payload=decisions_payload,
        decisions_source={"method": "interactive_cli_wizard", "sha256": hashlib.sha256(canonical).hexdigest()},
    )


def run_entity_preview_review_wizard(
    *, manifest_json: Path, input_fn=input, output_fn=print, now_fn=None,
) -> dict[str, Any] | None:
    template = build_entity_preview_review_template(manifest_json=manifest_json)
    output_fn(f"Preview: {template['preview_type']}")
    output_fn(f"Manifest: {template['preview_manifest']['sha256']}")
    reviewer = input_fn("Identificativo reviewer: ").strip()
    if not reviewer:
        raise ValueError("Reviewer is required; no receipt was written.")
    decisions = []
    choices = {"a": "accept_candidate", "r": "reject_candidate", "e": "needs_more_evidence"}
    for index, item in enumerate(template["decisions"], start=1):
        output_fn(f"\n[{index}/{len(template['decisions'])}] {item['artifact_kind']}: {item['candidate_id']}")
        output_fn("SourceDocument: " + (", ".join(item["source_document_ids"]) or "missing"))
        for key, value in item.get("review_context", {}).items():
            output_fn(f"{key}: {value}")
        for claim in item.get("source_claims", []):
            output_fn("Fonte: " + "; ".join(
                f"{key}={claim[key]}" for key in ("value", "evidence_span", "source_url", "source_document_id")
                if claim.get(key)))
        while True:
            answer = input_fn("Decisione: [a] accetta candidato / [r] respinge / [e] evidenza aggiuntiva / [q] annulla: ").strip().lower()
            if answer == "q":
                output_fn("Review annullata; nessuna receipt scritta.")
                return None
            if answer in choices:
                break
            output_fn("Scelta non valida; usa a, r, e o q.")
        note = input_fn("Nota (opzionale, Invio per nessuna): ").strip()
        timestamp = now_fn() if now_fn else datetime.now().astimezone()
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Wizard clock must provide a timezone-aware datetime.")
        decisions.append({**item, "decision": choices[answer], "reviewer": reviewer,
                          "reviewed_at": timestamp.isoformat(timespec="seconds"), "note": note})
    output_fn("\nRiepilogo: " + ", ".join(f"{key}={value}" for key, value in Counter(d["decision"] for d in decisions).items()))
    confirmation = input_fn("Confermare e scrivere la receipt review-only? [s/N]: ").strip().lower()
    if confirmation not in {"s", "si", "y", "yes"}:
        output_fn("Review non confermata; nessuna receipt scritta.")
        return None
    return {"@type": "EntityPreviewHumanReviewDecisionSet",
            "preview_manifest": template["preview_manifest"], "preview_type": template["preview_type"],
            "decisions": decisions, "review_status": "complete",
            "apply_allowed": False, "automatic_merge_allowed": False}


def _build_receipt(
    *, manifest_json: Path, decisions_payload: dict[str, Any], decisions_source: dict[str, str],
) -> dict[str, Any]:
    manifest, manifest_hash, expected, artifact_refs = _load_review_targets(manifest_json)
    payload = decisions_payload
    if payload.get("@type") != "EntityPreviewHumanReviewDecisionSet":
        raise ValueError("Review JSON has an unexpected object type.")
    manifest_ref = payload.get("preview_manifest")
    if not isinstance(manifest_ref, dict) or manifest_ref.get("sha256") != manifest_hash:
        raise ValueError("Review decisions are bound to a different preview manifest.")
    if Path(str(manifest_ref.get("path", ""))).resolve() != manifest_json.resolve():
        raise ValueError("Review decisions must reference this exact manifest path.")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("Review decision set requires a decisions list.")
    expected_by_key = {(item["artifact_kind"], item["candidate_id"]): item for item in expected}
    decisions_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError("Every review decision must be an object.")
        key = (_text(decision.get("artifact_kind")), _text(decision.get("candidate_id")))
        if key not in expected_by_key or key in decisions_by_key:
            raise ValueError("Review decisions contain an unknown or duplicate candidate ID.")
        if decision.get("decision") not in DECISIONS:
            raise ValueError("Every candidate requires an allowed human review decision.")
        if not _text(decision.get("reviewer")):
            raise ValueError("Every decision requires an explicit reviewer.")
        _validate_timestamp(decision.get("reviewed_at"))
        if not isinstance(decision.get("note", ""), str):
            raise ValueError("Review note must be text.")
        decisions_by_key[key] = decision
    if set(decisions_by_key) != set(expected_by_key):
        raise ValueError("Review decisions must cover every candidate link and update exactly once.")
    normalized = []
    for key in sorted(expected_by_key):
        expected_item = expected_by_key[key]
        decision = decisions_by_key[key]
        decision_document_ids = decision.get("source_document_ids")
        if not isinstance(decision_document_ids, list) or sorted(_text(v) for v in decision_document_ids) != expected_item["source_document_ids"]:
            raise ValueError("Review decision provenance does not match the preview candidate.")
        normalized.append({**expected_item, "decision": decision["decision"],
                           "reviewer": _text(decision["reviewer"]), "reviewed_at": decision["reviewed_at"],
                           "note": decision.get("note", "")})
    decision_counts = dict(sorted(Counter(item["decision"] for item in normalized).items()))
    return {
        "@type": "EntityPreviewHumanReviewReceipt",
        "preview_manifest": {"path": str(manifest_json.resolve()), "sha256": manifest_hash},
        "preview_type": manifest["@type"], "preview_artifacts": artifact_refs,
        "decisions_source": decisions_source,
        "review_status": "complete", "review_complete": True,
        "decision_count": len(normalized), "decision_counts": decision_counts,
        "decisions": normalized,
        "human_review_recorded": True, "reviewer_identity_authenticated": False,
        "apply_allowed": False, "automatic_merge_allowed": False, "canonical_write_allowed": False,
        "warnings": ["reviewer_identity_not_authenticated", "review_decisions_do_not_apply_canonical_changes"],
    }


def _load_review_targets(manifest_path: Path) -> tuple[dict[str, Any], str, list[dict[str, Any]], dict[str, Any]]:
    manifest = _load(manifest_path, None)
    if manifest.get("@type") not in {"PlacePreviewManifest", "HistoricalEventPreviewManifest"}:
        raise ValueError("Expected a PlacePreviewManifest or HistoricalEventPreviewManifest.")
    if manifest.get("preview_only") is not True or manifest.get("requires_human_review") is not True:
        raise ValueError("Manifest is not a pending human-review preview.")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("Preview manifest has no artifact references.")
    link_key = "place_links" if manifest["@type"] == "PlacePreviewManifest" else "event_links"
    update_key = "place_updates" if manifest["@type"] == "PlacePreviewManifest" else "event_updates"
    refs = {"links": artifacts.get(link_key), "updates": artifacts.get(update_key)}
    loaded: dict[str, dict[str, Any]] = {}
    for kind, reference in refs.items():
        if not isinstance(reference, dict):
            raise ValueError("Preview manifest is missing link/update artifact references.")
        path = Path(str(reference.get("path", "")))
        if not path.is_file() or _sha256(path) != reference.get("sha256"):
            raise ValueError("A preview artifact is missing or has changed.")
        loaded[kind] = _load(path, None)
    targets: list[dict[str, Any]] = []
    links = loaded["links"].get("candidate_document_place_links") or loaded["links"].get("candidate_document_event_links")
    if not isinstance(links, list):
        raise ValueError("Preview link artifact has no candidate links.")
    for item in links:
        targets.append(_target("candidate_link", item, ("source_document_id",)))
    updates = loaded["updates"].get("candidate_updates")
    if not isinstance(updates, list):
        raise ValueError("Preview update artifact has no candidate updates.")
    for item in updates:
        targets.append(_target("candidate_update", item, ("source_document_ids",)))
    keys = [(item["artifact_kind"], item["candidate_id"]) for item in targets]
    if len(keys) != len(set(keys)):
        raise ValueError("Preview artifact contains duplicate candidate IDs.")
    manifest_hash = _sha256(manifest_path)
    artifact_refs = {key: value for key, value in refs.items()}
    return manifest, manifest_hash, targets, artifact_refs


def _target(kind: str, value: Any, source_fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Preview candidate must be an object.")
    candidate_id = _text(value.get("@id") or value.get("candidate_id"))
    if not candidate_id:
        raise ValueError("Preview candidate is missing its identifier.")
    documents: set[str] = set()
    for field in source_fields:
        raw = value.get(field)
        if isinstance(raw, list):
            documents.update(_text(item) for item in raw if _text(item))
        elif isinstance(raw, str) and raw.strip():
            documents.add(raw.strip())
    context_keys = ("event_id", "event_label", "place_id", "place_label", "matched_label", "match_kind",
                    "field", "candidate_value", "current_values", "classification", "context")
    candidate = value
    review_context = {key: candidate[key] for key in context_keys if candidate.get(key) is not None}
    source_claims = candidate.get("source_claims")
    safe_claims = []
    if isinstance(source_claims, list):
        for claim in source_claims:
            if isinstance(claim, dict):
                safe_claims.append({key: claim[key] for key in
                                    ("value", "evidence_span", "source_url", "source_document_id")
                                    if isinstance(claim.get(key), (str, int, float))})
    return {"artifact_kind": kind, "candidate_id": candidate_id,
            "source_document_ids": sorted(documents), "review_context": review_context,
            "source_claims": safe_claims}


def _load(path: Path, expected_type: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Could not read review JSON input.") from error
    if not isinstance(payload, dict) or (expected_type and payload.get("@type") != expected_type):
        raise ValueError("Review JSON has an unexpected object type.")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Every decision requires an explicit reviewed_at timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Review timestamp must be ISO 8601 with timezone.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Review timestamp must include a timezone.")
