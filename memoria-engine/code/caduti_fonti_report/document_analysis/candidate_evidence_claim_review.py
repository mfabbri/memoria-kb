"""Prepare a deterministic, review-only queue from explicit person claim candidates."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .source_document_catalog import resolve_source_documents

DECISIONS = ("accept_candidate", "reject_candidate", "needs_more_evidence")


def _build_review_queue(*, claims_json: Path, source_documents_db: Path) -> dict[str, Any]:
    raw = claims_json.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("@type") != "CandidateEvidenceClaimSet":
        raise ValueError("Expected a CandidateEvidenceClaimSet object.")
    claims = payload.get("candidate_evidence_claims")
    if not isinstance(claims, list):
        raise ValueError("CandidateEvidenceClaimSet requires a candidate_evidence_claims list.")
    input_ref = {"path": str(claims_json.resolve()), "sha256": _digest(raw)}
    items = []
    seen: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict) or claim.get("@type") != "CandidateEvidenceClaim":
            raise ValueError("Every claim must be a CandidateEvidenceClaim object.")
        claim_id = _required_text(claim, "@id", fallback="claim_id")
        if claim_id in seen:
            raise ValueError(f"Duplicate claim ID: {claim_id}")
        seen.add(claim_id)
        profile_id = _required_text(claim, "profile_id", fallback="person_candidate_id")
        for key in ("source_id", "source_document_id", "field", "value", "extraction_method"):
            _required_text(claim, key)
        if claim.get("review_status") != "unreviewed":
            raise ValueError(f"Claim {claim_id} must have review_status=unreviewed.")
        confidence = claim.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (float, int)) or not 0 <= confidence <= 1 or not math.isfinite(confidence):
            raise ValueError(f"Claim {claim_id} requires a numeric confidence in [0, 1].")
        evidence = _optional_text(claim, "evidence_span")
        context = _optional_text(claim, "context")
        if not evidence and not context:
            raise ValueError(f"Claim {claim_id} requires evidence_span or context.")
        item_digest = _digest(_json_bytes(claim))
        items.append({
            "@type": "CandidateEvidenceClaimReviewItem",
            "item_id": f"claim-review:{item_digest}",
            "claim_id": claim_id,
            "profile_id": profile_id,
            "person_candidate_id": _optional_text(claim, "person_candidate_id"),
            "source_id": claim["source_id"],
            "source_document_id": claim["source_document_id"],
            "candidate": {"field": claim["field"], "value": claim["value"],
                          "normalized_value": _optional_text(claim, "normalized_value")},
            "question": f"Accettare come candidato {claim['field']} = {claim['value']} per {profile_id}?",
            "evidence_span": evidence,
            "context": context,
            "confidence": confidence,
            "extraction_method": claim["extraction_method"],
            "allowed_decisions": list(DECISIONS),
            "review_status": "unreviewed",
            "source_claim": claim,
        })
    document_ids = {item["source_document_id"] for item in items}
    catalog_reference = resolve_source_documents(source_documents_db, document_ids)
    if catalog_reference["resolved_document_ids"] != sorted(document_ids):
        raise ValueError("Claim SourceDocument IDs must match catalog IDs exactly.")
    return {
        "@type": "CandidateEvidenceClaimReviewQueue",
        "claims_input": input_ref,
        "review_status": "unreviewed",
        "source_documents_catalog": catalog_reference,
        "source_document_existence_verified": True,
        "items": items,
        **_review_only_flags(),
    }


def build_candidate_evidence_claim_review(
    *, claims_json: Path, source_documents_db: Path, output_dir: Path,
) -> dict[str, Any]:
    queue = _build_review_queue(claims_json=claims_json, source_documents_db=source_documents_db)
    input_ref, items = queue["claims_input"], queue["items"]
    queue_bytes = _json_bytes(queue)
    markdown = _render_markdown(queue).encode("utf-8")
    output_dir = output_dir.resolve()
    queue_path = output_dir / "candidate_claim_review_queue.json"
    markdown_path = output_dir / "candidate_claim_review_queue.md"
    manifest = {
        "@type": "CandidateEvidenceClaimReviewManifest",
        "schema_version": "1.1",
        "claims_input": input_ref,
        "artifacts": {
            "review_queue": {"path": str(queue_path), "sha256": _digest(queue_bytes)},
            "review_markdown": {"path": str(markdown_path), "sha256": _digest(markdown)},
        },
        "counts": {"claims": len(items), "profiles": len({item["profile_id"] for item in items}),
                   "source_documents": len({item["source_document_id"] for item in items})},
        "review_status": "unreviewed",
        "source_document_existence_verified": True,
        "source_documents_catalog": queue["source_documents_catalog"],
        "warnings": ["catalog_membership_does_not_validate_claim_content",
                     "claim_acceptance_does_not_resolve_person_identity"],
        **_review_only_flags(),
    }
    files = {queue_path.name: queue_bytes, markdown_path.name: markdown,
             "candidate_claim_review_manifest.json": _json_bytes(manifest)}
    _protect_catalog_output(output_dir, queue["source_documents_catalog"])
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError("Review output must be a directory.")
        entries = list(output_dir.iterdir())
        if entries and (set(path.name for path in entries) != set(files)
                        or any(not (output_dir / name).is_file() or (output_dir / name).read_bytes() != data
                               for name, data in files.items())):
            raise ValueError("Review output must be new, empty, or an identical prior preview.")
        if entries:
            return manifest
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (output_dir / name).write_bytes(data)
    return manifest


def run_candidate_evidence_claim_review_wizard(
    *, manifest_json: Path, input_fn=None, output_fn=print, now_fn=None,
) -> dict[str, Any] | None:
    manifest, manifest_hash, queue = _load_review_preview(manifest_json)
    items = queue["items"]
    if not items:
        raise ValueError("The review queue contains no claims.")
    ask = input_fn or input
    output_fn(f"Claim da revisionare: {len(items)}; manifest SHA-256: {manifest_hash}")
    output_fn("SourceDocument: presenza verificata nel catalogo; contenuti e identita restano da revisionare.")
    output_fn("Accettare un candidato non crea fatti verificati e non risolve l'identita della persona.")
    reviewer = ask("Identificativo reviewer ([q] annulla): ").strip()
    if reviewer.lower() == "q":
        return None
    if not reviewer:
        raise ValueError("An explicit reviewer is required.")
    decisions = []
    choices = {"a": "accept_candidate", "r": "reject_candidate", "e": "needs_more_evidence"}
    for index, item in enumerate(items, start=1):
        output_fn(f"\n[{index}/{len(items)}] {item['question']}")
        output_fn(f"Claim: {item['claim_id']}; profilo: {item['profile_id']}")
        output_fn(f"Fonte: {item['source_id']}; SourceDocument: {item['source_document_id']}")
        source_claim = item["source_claim"]
        provenance = source_claim.get("provenance") if isinstance(source_claim.get("provenance"), dict) else {}
        for key in ("source_url", "raw_file", "weak_segment_id", "chunk_id"):
            reference = source_claim.get(key) or provenance.get(key)
            if reference:
                output_fn(f"{key}: {reference}")
        output_fn(f"Metodo: {item['extraction_method']}; confidence: {item['confidence']}")
        output_fn("Evidenza: " + (item["evidence_span"] or item["context"]))
        if item["context"] and item["context"] != item["evidence_span"]:
            output_fn("Contesto: " + item["context"])
        while True:
            answer = ask("Decisione: [a] accetta candidato / [r] respinge / [e] altra evidenza / [q] annulla: ").strip().lower()
            if answer == "q":
                return None
            if answer in choices:
                break
            output_fn("Scelta non valida; usa a, r, e o q.")
        timestamp = now_fn() if now_fn else datetime.now().astimezone()
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("The review clock must provide a timezone-aware datetime.")
        note = ask("Nota (opzionale, [q] annulla): ").strip()
        if note.lower() == "q":
            return None
        decisions.append({**item, "decision": choices[answer], "reviewer": reviewer,
                          "reviewed_at": timestamp.isoformat(), "note": note})
    counts = dict(sorted(Counter(item["decision"] for item in decisions).items()))
    output_fn("\nRiepilogo: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    if ask("Confermare e scrivere la receipt review-only? [s/N]: ").strip().lower() not in {"s", "si", "y", "yes"}:
        return None
    _, final_hash, final_queue = _load_review_preview(manifest_json)
    if final_hash != manifest_hash or final_queue != queue:
        raise ValueError("Review inputs changed while collecting decisions; no receipt can be recorded.")
    return {
        "@type": "CandidateEvidenceClaimReviewReceipt",
        "preview_manifest": {"path": str(manifest_json.resolve()), "sha256": manifest_hash},
        "claims_input": manifest["claims_input"],
        "source_documents_catalog": manifest["source_documents_catalog"],
        "preview_artifacts": manifest["artifacts"],
        "decisions_source": {"method": "interactive_cli_wizard", "sha256": _digest(_json_bytes({"decisions": decisions}))},
        "review_status": "complete", "review_complete": True,
        "decision_count": len(decisions), "decision_counts": counts, "decisions": decisions,
        **_review_only_flags(), "decisions_recorded": True, "human_review_recorded": True,
        "reviewer_identity_authenticated": False, "person_identity_resolved": False,
        "source_document_existence_verified": True,
        "warnings": ["candidate_decisions_do_not_create_verified_facts_or_resolve_person_identity",
                     "reviewer_identity_not_authenticated", "catalog_membership_does_not_validate_claim_content"],
    }


def _load_review_preview(manifest_json: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    raw = manifest_json.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get("@type") != "CandidateEvidenceClaimReviewManifest" or manifest.get("schema_version") != "1.1":
        raise ValueError("Expected a catalog-bound CandidateEvidenceClaimReviewManifest v1.1.")
    for key, value in {**_review_only_flags(), "source_document_existence_verified": True}.items():
        if manifest.get(key) is not value:
            raise ValueError(f"Review manifest has an invalid {key} flag.")
    if manifest.get("review_status") != "unreviewed":
        raise ValueError("Review manifest must be unreviewed.")
    claims_path, _ = _checked_reference(manifest.get("claims_input"), "claims input")
    catalog = manifest.get("source_documents_catalog")
    if not isinstance(catalog, dict) or not isinstance(catalog.get("path"), str) or not Path(catalog["path"]).is_absolute():
        raise ValueError("Review manifest requires an absolute SourceDocument catalog reference.")
    expected_queue = _build_review_queue(claims_json=claims_path, source_documents_db=Path(catalog["path"]))
    if catalog != expected_queue["source_documents_catalog"]:
        raise ValueError("SourceDocument catalog changed or referenced IDs differ from the preview.")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"review_queue", "review_markdown"}:
        raise ValueError("Review manifest requires the exact queue and Markdown artifact references.")
    _, queue_raw = _checked_reference(artifacts["review_queue"], "review queue")
    _, markdown_raw = _checked_reference(artifacts["review_markdown"], "review Markdown")
    queue = json.loads(queue_raw)
    if queue != expected_queue or queue_raw != _json_bytes(expected_queue):
        raise ValueError("Review queue items do not match the original candidate claims.")
    if markdown_raw != _render_markdown(expected_queue).encode("utf-8"):
        raise ValueError("Review Markdown does not match the original candidate claims.")
    if manifest["claims_input"] != expected_queue["claims_input"]:
        raise ValueError("Review manifest refers to a different claims input.")
    items = queue["items"]
    counts = {"claims": len(items), "profiles": len({item["profile_id"] for item in items}),
              "source_documents": len({item["source_document_id"] for item in items})}
    if manifest.get("counts") != counts:
        raise ValueError("Review manifest counts do not match the queue.")
    return manifest, _digest(raw), queue


def _checked_reference(reference: Any, label: str) -> tuple[Path, bytes]:
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str) or not reference["path"]:
        raise ValueError(f"Missing {label} path.")
    path = Path(reference["path"])
    if not path.is_absolute():
        raise ValueError(f"The {label} path must be absolute.")
    raw = path.read_bytes()
    if reference.get("sha256") != _digest(raw):
        raise ValueError(f"SHA-256 mismatch for {label}.")
    return path, raw


def _review_only_flags() -> dict[str, bool]:
    return {"preview_only": True, "decisions_recorded": False, "human_review_recorded": False,
            "claim_promotion_allowed": False, "canonical_write_allowed": False, "profile_write_allowed": False}


def _protect_catalog_output(output_dir: Path, catalog: dict[str, Any]) -> None:
    database = Path(catalog["path"]).resolve()
    reserved = (database, Path(str(database) + "-wal"), Path(str(database) + "-shm"))
    if any(path == output_dir or path in output_dir.parents for path in reserved):
        raise ValueError("Review output must not replace a catalog or its SQLite sidecars.")


def _required_text(payload: dict[str, Any], key: str, *, fallback: str = "") -> str:
    value = _optional_text(payload, key)
    if not value and fallback:
        value = _optional_text(payload, fallback)
    if not value:
        raise ValueError(f"Candidate claim requires non-empty text: {key}.")
    return value


def _optional_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"Candidate claim {key} must be text.")
    return value.strip()


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _render_markdown(queue: dict[str, Any]) -> str:
    lines = ["# Review dei claim persona candidati", "", f"Input SHA-256: `{queue['claims_input']['sha256']}`", "",
             f"Catalogo SHA-256 (DB + eventuale WAL): `{queue['source_documents_catalog']['sha256']}`", "",
             "Stato: unreviewed. Nessuna decisione o modifica canonica registrata.", ""]
    for index, item in enumerate(queue["items"], start=1):
        lines.extend([f"## {index}. {item['question']}", "", f"- Claim: `{item['claim_id']}`",
                      f"- Fonte: `{item['source_id']}`; SourceDocument: `{item['source_document_id']}`",
                      f"- Metodo: `{item['extraction_method']}`; confidence: `{item['confidence']}`", "",
                      item["evidence_span"] or item["context"], ""])
        if item["context"] and item["context"] != item["evidence_span"]:
            lines.extend(["Contesto: " + item["context"], ""])
    return "\n".join(lines) + "\n"
