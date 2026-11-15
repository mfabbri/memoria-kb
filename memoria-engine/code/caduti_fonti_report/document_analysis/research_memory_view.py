"""Deterministic, read-only view reconstructed from verified session inventories."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def build_research_memory_view(*, inventory_path: Path, output_dir: Path,
                               feedback_outcome_paths: list[Path] | None = None,
                               lineage_paths: list[Path] | None = None,
                               quote_verification_paths: list[Path] | None = None) -> dict[str, Any]:
    inventory_path = inventory_path.resolve(strict=True)
    inventory_raw = inventory_path.read_bytes()
    inventory = _object(inventory_raw, "ResearchMemorySessionInventory")
    if inventory.get("@type") != "ResearchMemorySessionInventory" or inventory.get("preview_only") is not True:
        raise ValueError("Expected a preview-only ResearchMemorySessionInventory")
    sessions = inventory.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise ValueError("Inventory has no sessions")
    receipts = []
    for session in sessions:
        if not isinstance(session, dict):
            raise ValueError("Invalid session record")
        path = Path(str(session.get("receipt_path", ""))).resolve(strict=True)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != session.get("receipt_sha256"):
            raise ValueError(f"Receipt changed since inventory: {path}")
        receipt = _object(raw, "CandidateEvidenceClaimReviewReceipt")
        if receipt.get("@type") != "CandidateEvidenceClaimReviewReceipt" or receipt.get("review_complete") is not True:
            raise ValueError(f"Receipt is not complete: {path}")
        receipts.append((session, receipt))
    decisions = []
    docs: dict[str, dict[str, Any]] = {}
    conflicts: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for session, receipt in receipts:
        for decision in receipt.get("decisions", []):
            if not isinstance(decision, dict):
                continue
            profile_id = str(decision.get("profile_id", ""))
            claim_id = str(decision.get("claim_id", ""))
            source_id = str(decision.get("source_id", ""))
            source_document_id = str(decision.get("source_document_id", ""))
            candidate = decision.get("candidate", {})
            source_claim = decision.get("source_claim", {})
            if isinstance(source_claim, dict):
                candidate = {"field": source_claim.get("field", ""), "value": source_claim.get("value", ""),
                             "normalized_value": source_claim.get("normalized_value", "")}
            event = {"claim_id": claim_id, "profile_id": profile_id, "decision": decision.get("decision", ""),
                     "reviewer": decision.get("reviewer", ""), "reviewed_at": decision.get("reviewed_at", ""),
                     "candidate": candidate, "source_id": source_id, "source_document_id": source_document_id,
                     "source_document_title": decision.get("source_document_title", ""),
                     "evidence_span": decision.get("evidence_span", ""),
                     "receipt_path": session["receipt_path"], "receipt_sha256": session["receipt_sha256"]}
            decisions.append(event)
            if source_document_id:
                docs.setdefault(source_document_id, {"source_document_id": source_document_id,
                    "source_id": source_id, "title": decision.get("source_document_title", ""),
                    "source_url": decision.get("source_document_url", ""), "receipt_paths": []})
                if session["receipt_path"] not in docs[source_document_id]["receipt_paths"]:
                    docs[source_document_id]["receipt_paths"].append(session["receipt_path"])
            if profile_id and isinstance(candidate, dict) and candidate.get("field"):
                conflicts[(profile_id, str(candidate["field"]))].append({"claim_id": claim_id,
                    "value": candidate.get("value", ""), "source_document_id": source_document_id,
                    "decision": decision.get("decision", ""), "receipt_path": session["receipt_path"]})
    decisions.sort(key=lambda x: (str(x["reviewed_at"]), x["receipt_path"], x["claim_id"]))
    feedback = []
    for path in feedback_outcome_paths or []:
        raw = path.resolve(strict=True).read_bytes()
        outcome = _object(raw, "FeedbackLoopOutcome")
        if outcome.get("@type") != "FeedbackLoopOutcome":
            raise ValueError(f"Expected FeedbackLoopOutcome: {path}")
        feedback.append({"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
                         "outcome_id": outcome.get("feedback_loop_outcome_id", ""),
                         "profile_id": outcome.get("profile_id", outcome.get("search_memory_update_preview", {}).get("profile_id", "")),
                         "outcome_status": outcome.get("outcome_status", "")})
    conflict_rows = []
    for (profile_id, field), values in sorted(conflicts.items()):
        unique = {(str(v["value"]), str(v["source_document_id"])) for v in values}
        if len(unique) > 1:
            conflict_rows.append({"profile_id": profile_id, "field": field, "observations": values})
    lineage_links = []
    for path in lineage_paths or []:
        raw = path.resolve(strict=True).read_bytes()
        lineage = _object(raw, "CandidateSourceDocumentLineageSet")
        if lineage.get("@type") != "CandidateSourceDocumentLineageSet" or lineage.get("preview_only") is not True:
            raise ValueError(f"Expected preview-only CandidateSourceDocumentLineageSet: {path}")
        for link in lineage.get("links", []):
            if not isinstance(link, dict) or link.get("review_status") != "unreviewed":
                raise ValueError(f"Invalid or reviewed lineage link: {path}")
            lineage_links.append({**link, "lineage_artifact": str(path.resolve()),
                "lineage_sha256": hashlib.sha256(raw).hexdigest()})
    quote_checks = []
    for path in quote_verification_paths or []:
        raw = path.resolve(strict=True).read_bytes()
        verification = _object(raw, "CandidateEvidenceQuoteVerification")
        if verification.get("@type") != "CandidateEvidenceQuoteVerification" or verification.get("preview_only") is not True:
            raise ValueError(f"Expected preview-only CandidateEvidenceQuoteVerification: {path}")
        for row in verification.get("claims", []):
            if not isinstance(row, dict):
                raise ValueError(f"Invalid quote verification row: {path}")
            quote_checks.append({**row, "verification_artifact": str(path.resolve()),
                "verification_sha256": hashlib.sha256(raw).hexdigest()})
    view = {"@type": "ResearchMemoryView", "schema_version": "1.0",
        "source_inventory": {"path": str(inventory_path), "sha256": hashlib.sha256(inventory_raw).hexdigest()},
        "profile_ids": sorted(set(inventory.get("profile_ids", []))), "session_count": len(receipts),
        "documents": [docs[key] for key in sorted(docs)], "claim_decisions": decisions,
        "conflicts": conflict_rows, "feedback_outcomes": feedback,
        "source_document_lineage": lineage_links, "evidence_quote_checks": quote_checks,
        "feedback_state": "present" if feedback else "not_provided",
        "preview_only": True, "canonical_write_allowed": False, "claim_promotion_allowed": False}
    out = output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("output_dir must be new or empty")
    out.mkdir(parents=True, exist_ok=True)
    (out / "research-memory-view.json").write_text(json.dumps(view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Research memory view", "", f"- Profiles: {', '.join(view['profile_ids'])}",
        f"- Sessions: {view['session_count']}", f"- Documents: {len(view['documents'])}",
        f"- Claim decisions: {len(decisions)}", f"- Conflicts: {len(conflict_rows)}",
        f"- Explicit document lineage links: {len(lineage_links)} (unreviewed)",
        f"- Evidence quote checks: {len(quote_checks)}",
        f"- Feedback: {view['feedback_state']}", "- Canonical writes: disabled", ""]
    for row in conflict_rows:
        lines += [f"## {row['profile_id']} / {row['field']}", ""]
        lines += [f"- {item['value']} | {item['source_document_id']} | {item['decision']}" for item in row["observations"]]
        lines.append("")
    for row in lineage_links:
        lines.append(f"- Lineage `{row['source_document_id']}` {row['relation_type']} `{row['related_source_document_id']}` — unreviewed")
    for row in quote_checks:
        lines.append(f"- Quote `{row.get('claim_id', '')}`: `{row.get('status', '')}`")
    (out / "research-memory-view.md").write_text("\n".join(lines), encoding="utf-8")
    return view


def _object(raw: bytes, expected_type: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid {expected_type} JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {expected_type}")
    return value
