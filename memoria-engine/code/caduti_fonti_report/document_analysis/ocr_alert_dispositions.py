"""Fail-closed audit of page-scoped lexical alert dispositions.

Disposition records capture analysis tied to exact candidate bytes and a visual
observation. They do not correct, approve, or certify OCR text.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


_DISPOSITIONS = {"visually_confirmed_candidate", "visual_correction_proposed", "unresolved"}


def audit_ocr_alert_dispositions(*, structure_path: Path, lexicon_review_path: Path,
                                 visual_audit_path: Path, ledger_path: Path,
                                 dispositions_path: Path) -> dict[str, Any]:
    """Require exactly one position- and observation-bound record per alert."""
    paths = {"structure": Path(structure_path), "lexicon_review": Path(lexicon_review_path),
             "visual_audit": Path(visual_audit_path), "ledger": Path(ledger_path),
             "dispositions": Path(dispositions_path)}
    inputs: dict[str, dict[str, str]] = {}
    data: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, str]] = []

    def issue(code: str, unit: str = "") -> None:
        entry = {"code": code}
        if unit:
            entry["unit"] = unit
        issues.append(entry)

    for name, path in paths.items():
        try:
            raw = path.read_bytes()
            inputs[name] = {"path": str(path), "digest": _digest(raw)}
            parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                                parse_constant=_invalid_constant)
            if not isinstance(parsed, dict):
                raise ValueError("JSON object required")
            data[name] = parsed
        except (OSError, UnicodeError, ValueError):
            issue("invalid_input", name)

    counts = {"candidate_blocks": 0, "lexical_alerts": 0, "dispositions": 0,
              "visually_confirmed": 0, "correction_proposals": 0, "unresolved": 0,
              "manual_action_groups": 0}
    groups: list[dict[str, Any]] = []
    if not issues:
        structure, review, visual, ledger, supplied = (data[k] for k in (
            "structure", "lexicon_review", "visual_audit", "ledger", "dispositions"))
        if structure.get("@type") != "DocumentStructure" or structure.get("schema_version") != "1.0":
            issue("unsupported_structure")
        if review.get("@type") != "OcrDocumentLexiconReview" or review.get("schema_version") != "1.0":
            issue("unsupported_lexicon_review")
        if ledger.get("@type") != "OcrVisualReviewLedger" or ledger.get("schema_version") != "1.0":
            issue("unsupported_visual_ledger")
        if supplied.get("@type") != "OcrLexicalDispositionLedger" or supplied.get("schema_version") != "1.0":
            issue("unsupported_disposition_ledger")
        if supplied.get("template_status") == "incomplete":
            issue("incomplete_template", "dispositions")

        visual_inputs = visual.get("inputs") if isinstance(visual.get("inputs"), dict) else {}
        checks = visual.get("checks") if isinstance(visual.get("checks"), dict) else {}
        if (visual.get("processability_status") != "diagnostic_only"
                or visual.get("visual_coverage_status") != "complete_for_declared_units"
                or visual.get("semantic_accuracy_status") != "not_attested"
                or checks.get("issues") != [] or checks.get("issue_count") != 0
                or any(visual.get(k) is not False for k in (
                    "human_review_request_allowed", "machine_pass", "human_verified", "gold_promotion_allowed"))):
            issue("unsuccessful_visual_audit")
        visual_structure = visual_inputs.get("structure")
        visual_ledger = visual_inputs.get("ledger")
        if (not isinstance(visual_structure, dict) or not isinstance(visual_ledger, dict)
                or visual_structure.get("digest") != inputs["structure"]["digest"]
                or visual_ledger.get("digest") != inputs["ledger"]["digest"]):
            issue("visual_audit_identity_mismatch")
        if (ledger.get("source_structure_digest") != inputs["structure"]["digest"]
                or review.get("source_structure_digest") != inputs["structure"]["digest"]):
            issue("stale_candidate_artifact")
        for name in ("source_structure_digest", "source_lexicon_review_digest", "source_visual_audit_digest"):
            target = {"source_structure_digest": "structure", "source_lexicon_review_digest": "lexicon_review",
                     "source_visual_audit_digest": "visual_audit"}[name]
            if supplied.get(name) != inputs[target]["digest"]:
                issue("stale_disposition_input", target)

        page_id = structure.get("page_id")
        blocks = structure.get("blocks")
        review_blocks = review.get("blocks")
        observations = ledger.get("observations")
        records = supplied.get("dispositions")
        if not isinstance(page_id, str) or not page_id.strip():
            issue("missing_page_id")
        if not isinstance(blocks, list) or not blocks:
            issue("missing_candidate_blocks")
            blocks = []
        if not isinstance(review_blocks, list):
            issue("invalid_lexicon_blocks")
            review_blocks = []
        if not isinstance(observations, list):
            issue("invalid_visual_observations")
            observations = []
        if not isinstance(records, list):
            issue("invalid_dispositions")
            records = []

        candidate: dict[str, dict[str, Any]] = {}
        for block in blocks:
            block_id = block.get("block_id", block.get("id")) if isinstance(block, dict) else None
            if not isinstance(block_id, str) or not block_id.strip() or block_id in candidate:
                issue("invalid_or_duplicate_candidate_block", str(block_id or ""))
                continue
            candidate[block_id] = block
        counts["candidate_blocks"] = len(candidate)
        checked: dict[str, dict[str, Any]] = {}
        for item in review_blocks:
            block_id = item.get("block_id") if isinstance(item, dict) else None
            if not isinstance(block_id, str) or block_id in checked:
                issue("invalid_or_duplicate_lexicon_block", str(block_id or ""))
                continue
            checked[block_id] = item
        if set(checked) != set(candidate):
            issue("lexicon_block_coverage_mismatch")
        visual_blocks: dict[str, dict[str, Any]] = {}
        visual_block_counts: dict[str, int] = {}
        for observation in observations:
            if not isinstance(observation, dict):
                continue
            if observation.get("unit_type") == "block":
                key = observation.get("unit_id")
                if isinstance(key, str):
                    visual_block_counts[key] = visual_block_counts.get(key, 0) + 1
                    visual_blocks[key] = observation
        for block_id in candidate:
            if visual_block_counts.get(block_id) != 1:
                issue("visual_block_observation_coverage_mismatch", block_id)

        alerts: dict[tuple[str, int, int, str], dict[str, Any]] = {}
        for block_id, block in candidate.items():
            lex_block = checked.get(block_id)
            if (lex_block is None or lex_block.get("page_id") != page_id
                    or lex_block.get("text") != block.get("text")
                    or lex_block.get("source_region_ids") != block.get("source_region_ids")):
                issue("lexicon_candidate_mismatch", block_id)
                continue
            text = block.get("text")
            tokens = lex_block.get("tokens")
            if not isinstance(text, str) or not isinstance(tokens, list):
                issue("invalid_lexicon_tokens", block_id)
                continue
            for token in tokens:
                if not isinstance(token, dict) or token.get("status") not in ("not_found", "exact_match", "non_word"):
                    issue("invalid_lexicon_token", block_id)
                    continue
                if token.get("status") != "not_found":
                    continue
                start, end, raw_token = token.get("start"), token.get("end"), token.get("raw_token")
                if (type(start) is not int or type(end) is not int or start < 0 or end <= start
                        or end > len(text) or not isinstance(raw_token, str) or text[start:end] != raw_token):
                    issue("invalid_alert_span", block_id)
                    continue
                key = (block_id, start, end, raw_token)
                if key in alerts:
                    issue("duplicate_lexicon_alert", block_id)
                else:
                    alerts[key] = token
        counts["lexical_alerts"] = len(alerts)

        by_key: dict[tuple[str, int, int, str], dict[str, Any]] = {}
        for item in records:
            if not isinstance(item, dict):
                issue("invalid_disposition_record")
                continue
            key = (item.get("block_id"), item.get("start"), item.get("end"), item.get("raw_token"))
            if (item.get("page_id") != page_id or key in by_key
                    or not isinstance(key[0], str) or type(key[1]) is not int
                    or type(key[2]) is not int or not isinstance(key[3], str)):
                issue("invalid_or_duplicate_disposition", str(key[0] or ""))
                continue
            by_key[key] = item
        counts["dispositions"] = len(by_key)
        if set(by_key) != set(alerts):
            issue("disposition_coverage_mismatch")

        grouped: dict[str, list[dict[str, Any]]] = {}
        for key, alert in alerts.items():
            block_id, start, end, raw_token = key
            item = by_key.get(key)
            if item is None:
                continue
            disposition = item.get("disposition")
            reason = item.get("reason")
            observation = visual_blocks.get(block_id)
            if disposition not in _DISPOSITIONS or not isinstance(reason, str) or not reason.strip():
                issue("invalid_disposition_or_reason", block_id)
                continue
            if (not isinstance(item.get("visual_observation_id"), str)
                    or item.get("visual_observation_id") != (observation or {}).get("observation_id")
                    or observation is None or observation.get("outcome") != "readable"):
                issue("visual_observation_mismatch", block_id)
                continue
            observed_text = observation.get("text")
            if not isinstance(observed_text, str) or end > len(observed_text):
                issue("visual_observation_span_mismatch", block_id)
                continue
            observed_token = observed_text[start:end]
            if disposition == "visually_confirmed_candidate" and observed_token != raw_token:
                issue("visual_confirmation_mismatch", block_id)
            elif disposition == "visually_confirmed_candidate" and "replacement_text" in item:
                issue("unexpected_replacement_text", block_id)
            elif disposition == "visual_correction_proposed":
                replacement = item.get("replacement_text")
                if (not isinstance(replacement, str) or not replacement.strip()
                        or replacement != observed_token or replacement == raw_token):
                    issue("invalid_visual_correction_proposal", block_id)
                else:
                    counts["correction_proposals"] += 1
            elif disposition == "visually_confirmed_candidate":
                counts["visually_confirmed"] += 1
            elif disposition == "unresolved":
                if "replacement_text" in item:
                    issue("unexpected_replacement_text", block_id)
                counts["unresolved"] += 1
                grouped.setdefault(block_id, []).append({"start": start, "end": end,
                    "raw_token": raw_token, "reason": reason})
        for block_id, residuals in sorted(grouped.items()):
            groups.append({"page_id": page_id, "block_id": block_id,
                           "source_region_ids": candidate[block_id].get("source_region_ids", []),
                           "residual_count": len(residuals), "residuals": residuals})
        counts["manual_action_groups"] = len(groups)

    blocked = bool(issues)
    return {"@type": "OcrLexicalDispositionAudit", "schema_version": "1.0", "inputs": inputs,
            "counts": counts, "residual_groups": groups,
            "checks": {"issues": issues, "issue_count": len(issues)},
            "processability_status": "blocked" if blocked else "diagnostic_only",
            "disposition_status": "incomplete" if blocked else "complete_for_declared_alerts",
            "human_review_status": "pending" if counts["unresolved"] else "no_declared_residuals",
            "manual_action_count": counts["manual_action_groups"] if not blocked else None,
            "semantic_accuracy_status": "not_attested", "review_preparation_status": "incomplete",
            "human_review_request_allowed": False, "machine_pass": False, "human_verified": False,
            "gold_promotion_allowed": False, "claim_extraction_allowed": False, "preview_only": True}


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _invalid_constant(value: str) -> Any:
    raise ValueError("Invalid JSON constant: " + value)
