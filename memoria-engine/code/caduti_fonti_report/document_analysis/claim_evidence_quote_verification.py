"""Read-only exact-substring verification of candidate evidence spans."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def verify_claim_evidence_quotes(*, claims_json: Path, processed_text_paths: list[Path], output_dir: Path) -> dict[str, Any]:
    claims_path = claims_json.resolve(strict=True)
    claims_raw = claims_path.read_bytes()
    claims_payload = _object(claims_raw, "CandidateEvidenceClaimSet")
    if claims_payload.get("@type") != "CandidateEvidenceClaimSet":
        raise ValueError("Expected CandidateEvidenceClaimSet")
    claims = claims_payload.get("candidate_evidence_claims")
    if not isinstance(claims, list):
        raise ValueError("candidate_evidence_claims must be a list")
    documents: dict[str, tuple[dict[str, Any], str]] = {}
    input_refs = []
    for text_path in processed_text_paths:
        path = text_path.resolve(strict=True)
        raw = path.read_bytes()
        payload = _object(raw, "ProcessedDocumentText")
        if payload.get("@type") != "ProcessedDocumentText":
            raise ValueError(f"Expected ProcessedDocumentText: {path}")
        document_id = _text(payload.get("source_document_id"))
        if not document_id:
            raise ValueError(f"ProcessedDocumentText has no source_document_id: {path}")
        if document_id in documents:
            raise ValueError(f"Duplicate ProcessedDocumentText for {document_id}")
        text = payload.get("text")
        if not isinstance(text, str):
            raise ValueError(f"ProcessedDocumentText text must be a string: {path}")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if payload.get("text_sha256") and payload["text_sha256"] != digest:
            raise ValueError(f"ProcessedDocumentText text_sha256 mismatch: {path}")
        documents[document_id] = (payload, text)
        input_refs.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                           "source_document_id": document_id, "text_sha256": digest})
    rows = []
    for claim in claims:
        if not isinstance(claim, dict) or claim.get("@type") != "CandidateEvidenceClaim":
            raise ValueError("Every item must be a CandidateEvidenceClaim")
        claim_id = _text(claim.get("@id") or claim.get("claim_id"))
        document_id = _text(claim.get("source_document_id"))
        document = documents.get(document_id)
        span = claim.get("evidence_span")
        status = "missing_document_text"
        if document is not None:
            metadata, body = document
            if _text(claim.get("source_id")) != _text(metadata.get("source_id")):
                status = "source_id_mismatch"
            elif not isinstance(span, str) or not span:
                status = "empty_evidence_span"
            elif span in body:
                status = "exact_match"
            else:
                status = "not_exact"
        rows.append({"claim_id": claim_id, "source_id": _text(claim.get("source_id")),
                     "source_document_id": document_id, "field": _text(claim.get("field")),
                     "value": _text(claim.get("value")), "evidence_span": span if isinstance(span, str) else "",
                     "status": status, "claim_review_status": claim.get("review_status", "")})
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    report = {"@type": "CandidateEvidenceQuoteVerification", "schema_version": "1.0",
        "claims_input": {"path": str(claims_path), "sha256": hashlib.sha256(claims_raw).hexdigest()},
        "processed_text_inputs": input_refs, "claim_count": len(rows), "status_counts": counts,
        "claims": rows, "preview_only": True, "claims_modified": False,
        "canonical_write_allowed": False, "review_receipt_modified": False}
    out = output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("output_dir must be new or empty")
    out.mkdir(parents=True, exist_ok=True)
    (out / "quote-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Candidate evidence quote verification", "", f"- Claims: {len(rows)}", f"- Status counts: `{counts}`", "- Exact-match only; no normalization or rewrite.", ""]
    lines.extend(f"- `{r['claim_id']}` ({r['field']}): `{r['status']}` | `{r['evidence_span']}`" for r in rows)
    (out / "quote-verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _object(raw: bytes, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid {name} JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{name} must be an object")
    return payload


def _text(value: Any) -> str:
    return str(value or "").strip()
