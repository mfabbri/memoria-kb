"""Deterministic, read-only view reconstructed from verified session inventories."""
from __future__ import annotations

import hashlib
import json
import re
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
                     "note": decision.get("note", ""),
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
    inventory_profile_ids = inventory.get("profile_ids", [])
    if feedback_outcome_paths and (
        not isinstance(inventory_profile_ids, list)
        or any(not isinstance(profile_id, str) or not profile_id.strip() for profile_id in inventory_profile_ids)
    ):
        raise ValueError("Invalid ResearchMemorySessionInventory profile_ids for feedback binding")
    inventory_profile_set = set(inventory_profile_ids) if feedback_outcome_paths else set()
    for path in feedback_outcome_paths or []:
        raw = path.resolve(strict=True).read_bytes()
        outcome = _object(raw, "FeedbackLoopOutcome")
        if outcome.get("@type") != "FeedbackLoopOutcome":
            raise ValueError(f"Expected FeedbackLoopOutcome: {path}")
        nested_preview = outcome.get("search_memory_update_preview", {})
        if nested_preview is None:
            nested_preview = {}
        if not isinstance(nested_preview, dict):
            raise ValueError(f"Invalid FeedbackLoopOutcome search_memory_update_preview: {path}")
        top_profile_id = outcome.get("profile_id", "")
        nested_profile_id = nested_preview.get("profile_id", "")
        if top_profile_id is not None and not isinstance(top_profile_id, str):
            raise ValueError(f"Invalid FeedbackLoopOutcome profile_id: {path}")
        if nested_profile_id is not None and not isinstance(nested_profile_id, str):
            raise ValueError(f"Invalid FeedbackLoopOutcome preview profile_id: {path}")
        top_profile_id = (top_profile_id or "").strip()
        nested_profile_id = (nested_profile_id or "").strip()
        if top_profile_id and nested_profile_id and top_profile_id != nested_profile_id:
            raise ValueError(f"Conflicting FeedbackLoopOutcome profile IDs: {path}")
        profile_id = top_profile_id or nested_profile_id
        if not profile_id or profile_id not in inventory_profile_set:
            raise ValueError(f"FeedbackLoopOutcome profile_id is not present in inventory: {path}")
        warnings = outcome.get("warnings", [])
        if not isinstance(warnings, list) or any(not isinstance(warning, str) or not warning.strip()
                                                 for warning in warnings):
            raise ValueError(f"Invalid FeedbackLoopOutcome warnings: {path}")
        (result_source_document_ids, result_source_documents_catalog,
         result_source_attribution_status) = _feedback_result_binding(
            outcome=outcome, nested_preview=nested_preview, path=path,
        )
        feedback.append({"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
                         "outcome_id": outcome.get("feedback_loop_outcome_id", ""),
                         "profile_id": profile_id,
                         "outcome_status": outcome.get("outcome_status", ""), "warnings": warnings,
                         "result_source_document_ids": result_source_document_ids,
                         "result_source_documents_catalog": result_source_documents_catalog,
                         "result_source_attribution_status": result_source_attribution_status})
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
    if feedback:
        lines += ["## Feedback outcomes", ""]
        for item in feedback:
            lines.append(
                f"- `{item['outcome_id']}` | profile `{item['profile_id']}` | status `{item['outcome_status']}` "
                f"| `{item['path']}` | SHA-256 `{item['sha256']}`"
            )
            for warning in item["warnings"]:
                lines.append(f"  - Warning: {_markdown_code(warning)}")
            lines.append(f"  - Result source attribution: `{item['result_source_attribution_status']}`")
            for document_id in item["result_source_document_ids"]:
                lines.append(f"  - Result SourceDocument: {_markdown_code(str(document_id))}")
            catalog = item["result_source_documents_catalog"]
            if isinstance(catalog, dict):
                catalog_path = _markdown_code(str(catalog.get("path", "")))
                catalog_sha256 = _markdown_code(str(catalog.get("sha256", "")))
                lines.append(
                    f"  - Result catalog: {catalog_path} | SHA-256 {catalog_sha256}"
                )
        lines.append("")
    for row in conflict_rows:
        lines += [f"## {row['profile_id']} / {row['field']}", ""]
        lines += [f"- {item['value']} | {item['source_document_id']} | {item['decision']}" for item in row["observations"]]
        lines.append("")
    lines += ["## Review decisions", ""]
    for row in decisions:
        lines.append(f"- `{row['claim_id']}` | `{row['decision']}` | `{row['source_document_id']}`")
        if row["note"]:
            lines.append(f"  - Reviewer note: {_markdown_code(row['note'])}")
    for row in lineage_links:
        lines.append(f"- Lineage `{row['source_document_id']}` {row['relation_type']} `{row['related_source_document_id']}` — unreviewed")
    for row in quote_checks:
        lines.append(
            f"- Quote `{row.get('claim_id', '')}`: `{row.get('status', '')}` "
            f"| SourceDocument `{row.get('source_document_id', '')}` | field `{row.get('field', '')}`"
        )
        if row.get("evidence_span"):
            lines.append(f"  - Evidence: {_markdown_code(str(row['evidence_span']))}")
        if row.get("verification_artifact"):
            lines.append(
                f"  - Verification artifact: {_markdown_code(str(row['verification_artifact']))} "
                f"(SHA-256 {_markdown_code(str(row.get('verification_sha256', '')))})"
            )
    (out / "research-memory-view.md").write_text("\n".join(lines), encoding="utf-8")
    return view


def _feedback_result_binding(*, outcome: dict[str, Any], nested_preview: dict[str, Any], path: Path
                              ) -> tuple[list[str], dict[str, Any] | None, str]:
    top_ids = outcome.get("result_source_document_ids")
    nested_ids = nested_preview.get("result_source_document_ids")
    if top_ids is not None and nested_ids is not None and top_ids != nested_ids:
        raise ValueError(f"Conflicting FeedbackLoopOutcome result document IDs: {path}")
    result_ids = top_ids if top_ids is not None else nested_ids
    if result_ids is None:
        result_ids = []
    if (not isinstance(result_ids, list)
            or any(not isinstance(document_id, str) or not document_id.strip() for document_id in result_ids)
            or len(result_ids) != len(set(result_ids))):
        raise ValueError(f"Invalid FeedbackLoopOutcome result_source_document_ids: {path}")

    top_catalog = outcome.get("result_source_documents_catalog")
    nested_catalog = nested_preview.get("result_source_documents_catalog")
    if top_catalog is not None and nested_catalog is not None and top_catalog != nested_catalog:
        raise ValueError(f"Conflicting FeedbackLoopOutcome result catalog metadata: {path}")
    catalog = top_catalog if top_catalog is not None else nested_catalog
    if catalog is None:
        return result_ids, None, "unavailable" if result_ids else "not_applicable"
    if not isinstance(catalog, dict):
        raise ValueError(f"Invalid FeedbackLoopOutcome result catalog metadata: {path}")

    catalog_path = catalog.get("path")
    catalog_sha256 = catalog.get("sha256")
    resolved_ids = catalog.get("resolved_document_ids")
    documents = catalog.get("documents")
    if (not isinstance(catalog_path, str) or not catalog_path.strip()
            or not isinstance(catalog_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", catalog_sha256)
            or not isinstance(resolved_ids, list)
            or any(not isinstance(document_id, str) or not document_id.strip() for document_id in resolved_ids)
            or len(resolved_ids) != len(set(resolved_ids))
            or not isinstance(documents, list)
            or any(not isinstance(document, dict) or not isinstance(document.get("document_id"), str)
                   or not document["document_id"].strip() for document in documents)):
        raise ValueError(f"Invalid FeedbackLoopOutcome result catalog metadata: {path}")
    document_ids = [document["document_id"] for document in documents]
    if (not result_ids or sorted(resolved_ids) != sorted(result_ids)
            or sorted(document_ids) != sorted(resolved_ids)):
        raise ValueError(f"FeedbackLoopOutcome result catalog does not match result document IDs: {path}")
    attribution_status = catalog.get("source_id_match_status")
    if attribution_status is not None and attribution_status not in {"matched", "unavailable"}:
        raise ValueError(f"Invalid FeedbackLoopOutcome result source attribution status: {path}")
    expected_source_id = outcome.get("source_id")
    if expected_source_id is not None and not isinstance(expected_source_id, str):
        raise ValueError(f"Invalid FeedbackLoopOutcome source_id: {path}")
    expected_source_id = (expected_source_id or "").strip()
    document_source_ids = [document.get("source_id") for document in documents]
    if any(source_id is not None and not isinstance(source_id, str) for source_id in document_source_ids):
        raise ValueError(f"Invalid FeedbackLoopOutcome result document source_id: {path}")
    known_source_ids = [source_id.strip() for source_id in document_source_ids if isinstance(source_id, str) and source_id.strip()]
    if expected_source_id and any(source_id != expected_source_id for source_id in known_source_ids):
        raise ValueError(f"FeedbackLoopOutcome result source attribution conflicts with source_id: {path}")
    all_documents_attributed = len(known_source_ids) == len(documents)
    if attribution_status == "matched" and (
            not expected_source_id or not all_documents_attributed
            or any(source_id != expected_source_id for source_id in known_source_ids)):
        raise ValueError(f"Invalid matched FeedbackLoopOutcome result source attribution: {path}")
    if attribution_status == "unavailable" and expected_source_id and all_documents_attributed:
        raise ValueError(f"Invalid unavailable FeedbackLoopOutcome result source attribution: {path}")
    return result_ids, catalog, attribution_status or "unavailable"


def _object(raw: bytes, expected_type: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid {expected_type} JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {expected_type}")
    return value


def _markdown_code(value: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * max(1, longest + 1)
    padding = " " if value.startswith(("`", " ")) or value.endswith(("`", " ")) else ""
    return f"{fence}{padding}{value}{padding}{fence}"
