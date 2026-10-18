"""Identity-bound diagnostics for a structured OCR candidate.

This first assessment gate is diagnostic only. It checks that the structure,
rendered Markdown, OCR evidence, and lexical review describe the same page and
candidate; it does not calibrate accuracy or emit a machine pass.
Region coverage concerns only regions already present in OCR evidence. It cannot
measure image-page coverage or omissions shared by OCR engines.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .document_structure import DocumentBlock, DocumentStructure, EvidenceReference, render_document_structure_markdown


def build_ocr_candidate_assessment(
    *, structure_path: Path, markdown_path: Path, evidence_path: Path,
    lexicon_review_path: Path, output_path: Path, apply: bool = False,
) -> dict[str, Any]:
    """Assess consistency and aggregate lexical alerts without inventing actions."""
    paths = {
        "structure": Path(structure_path), "markdown": Path(markdown_path),
        "evidence": Path(evidence_path), "lexicon_review": Path(lexicon_review_path),
    }
    loaded: dict[str, Any] = {}
    digests: dict[str, str | None] = {}
    missing: list[str] = []
    for name, path in paths.items():
        try:
            raw = path.read_bytes()
            loaded[name] = json.loads(raw.decode("utf-8")) if name != "markdown" else raw.decode("utf-8")
            digests[name] = "sha256:" + hashlib.sha256(raw).hexdigest()
        except FileNotFoundError:
            missing.append(name)
            digests[name] = None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Input {name} non leggibile o non valido: {exc}") from exc

    issues: list[dict[str, str]] = [{"code": "missing_input", "input": name} for name in missing]
    alert_groups: list[dict[str, Any]] = []
    alert_count = 0
    region_coverage: dict[str, Any] = {
        "scope": "ocr_evidence_regions_only",
        "evidence_region_count": None,
        "represented_region_count": None,
        "unrepresented_region_ids": None,
        "coverage_ratio": None,
    }
    if not missing:
        structure = loaded["structure"]
        evidence = loaded["evidence"]
        review = loaded["lexicon_review"]
        if not isinstance(structure, dict) or structure.get("@type") != "DocumentStructure":
            raise ValueError("structure deve essere un DocumentStructure JSON.")
        if structure.get("schema_version") != "1.0" or not isinstance(structure.get("blocks"), list):
            raise ValueError("DocumentStructure non supportata o senza blocks.")
        if not isinstance(evidence, dict) or evidence.get("@type") != "OcrPageEvidence":
            raise ValueError("evidence deve essere un OcrPageEvidence JSON.")
        if not isinstance(review, dict) or review.get("@type") != "OcrDocumentLexiconReview":
            raise ValueError("lexicon review deve essere OcrDocumentLexiconReview JSON.")
        if review.get("schema_version") != "1.0":
            raise ValueError("Review lessicale con schema_version non supportata.")

        source = structure.get("source_evidence")
        if not isinstance(source, dict):
            raise ValueError("DocumentStructure senza source_evidence.")
        for field in ("page_id", "source_image_hash", "transform_id", "engine", "language"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                issues.append({"code": "missing_evidence_identity", "field": field})
            if source.get(field) != evidence.get(field):
                issues.append({"code": "evidence_identity_mismatch", "field": field})
        if structure.get("page_id") != source.get("page_id"):
            issues.append({"code": "candidate_page_identity_mismatch"})
        for field in ("source_page", "model"):
            if not isinstance(source.get(field), dict):
                issues.append({"code": "missing_evidence_identity", "field": field})
        if source.get("image_transform") is not None and not isinstance(source["image_transform"], dict):
            issues.append({"code": "invalid_evidence_identity", "field": "image_transform"})
        for field in ("source_page", "model", "image_transform"):
            if source.get(field) != evidence.get(field):
                issues.append({"code": "evidence_identity_mismatch", "field": field})

        regions = evidence.get("regions")
        if not isinstance(regions, list):
            raise ValueError("OcrPageEvidence senza lista regions valida.")
        valid_region_ids: set[str] = set()
        for region in regions:
            region_id = region.get("region_id") if isinstance(region, dict) else None
            if not isinstance(region_id, str) or not region_id.strip():
                issues.append({"code": "invalid_evidence_region"})
            elif region_id in valid_region_ids:
                issues.append({"code": "duplicate_evidence_region", "region_id": region_id})
            else:
                valid_region_ids.add(region_id)
        # Count each valid ID once, even when several blocks reference it.
        # Invalid/duplicate evidence entries retain their own blocking issues.
        linked_region_ids = {
            region_id
            for block in structure["blocks"]
            if isinstance(block, dict) and isinstance(block.get("source_region_ids"), list)
            for region_id in block["source_region_ids"]
            if isinstance(region_id, str)
        }
        represented_region_ids = valid_region_ids & linked_region_ids
        unrepresented_region_ids = sorted(valid_region_ids - represented_region_ids)
        region_owners: dict[str, list[str]] = {}
        for block in structure["blocks"]:
            if not isinstance(block, dict):
                continue
            block_id = block.get("block_id", block.get("id"))
            region_ids = block.get("source_region_ids")
            if not isinstance(region_ids, list):
                continue
            seen_in_block: set[str] = set()
            for region_id in region_ids:
                if not isinstance(region_id, str):
                    continue
                if region_id in seen_in_block:
                    issues.append({"code": "duplicate_region_link", "block_id": str(block_id),
                                   "region_id": region_id})
                seen_in_block.add(region_id)
                region_owners.setdefault(region_id, []).append(str(block_id))
        for region_id, owners in sorted(region_owners.items()):
            if len(owners) > 1:
                issues.append({"code": "multiple_region_owners", "region_id": region_id,
                               "block_ids": owners})
        region_coverage.update({
            "evidence_region_count": len(regions),
            "represented_region_count": len(represented_region_ids),
            "unrepresented_region_ids": unrepresented_region_ids,
            "coverage_ratio": len(represented_region_ids) / len(regions) if regions else None,
        })
        if not regions:
            issues.append({"code": "empty_evidence_regions"})
        if unrepresented_region_ids:
            issues.append({"code": "unrepresented_evidence_regions"})
        candidate_blocks: dict[str, dict[str, Any]] = {}
        for block in structure["blocks"]:
            block_id = block.get("block_id", block.get("id")) if isinstance(block, dict) else None
            if not isinstance(block_id, str) or not block_id.strip():
                issues.append({"code": "invalid_candidate_block"})
            elif block_id in candidate_blocks:
                issues.append({"code": "duplicate_candidate_block", "block_id": block_id})
            else:
                candidate_blocks[block_id] = block
        for block_id, block in candidate_blocks.items():
            region_ids = block.get("source_region_ids")
            if not isinstance(region_ids, list) or not region_ids:
                issues.append({"code": "missing_region_links", "block_id": str(block_id)})
            else:
                for region_id in region_ids:
                    if not isinstance(region_id, str) or region_id not in valid_region_ids:
                        issues.append({"code": "invalid_region_link", "block_id": str(block_id),
                                       "region_id": str(region_id)})

        actual_structure_digest = digests["structure"]
        if not isinstance(review.get("blocks"), list):
            raise ValueError("Review lessicale senza lista blocks valida.")
        if review.get("source_structure_digest") != actual_structure_digest:
            issues.append({"code": "stale_lexicon_review", "expected_structure_digest": actual_structure_digest or ""})
        else:
            review_blocks: dict[tuple[str, str], dict[str, Any]] = {}
            for checked in review["blocks"]:
                if not isinstance(checked, dict) or not all(
                    isinstance(checked.get(field), str) and checked[field].strip()
                    for field in ("page_id", "block_id")
                ):
                    issues.append({"code": "invalid_lexicon_block"})
                    continue
                key = (checked["page_id"], checked["block_id"])
                if key in review_blocks:
                    issues.append({"code": "duplicate_lexicon_block", "block_id": key[1]})
                else:
                    review_blocks[key] = checked
            page_id = structure.get("page_id")
            for checked_page_id, checked_block_id in review_blocks:
                if checked_page_id != page_id or checked_block_id not in candidate_blocks:
                    issues.append({"code": "unexpected_lexicon_block", "block_id": checked_block_id})
            for block_id, block in candidate_blocks.items():
                checked = review_blocks.get((page_id, block_id))
                if checked is None or checked.get("text") != block.get("text") or checked.get("source_region_ids") != block.get("source_region_ids"):
                    issues.append({"code": "lexicon_candidate_mismatch", "block_id": str(block_id)})
                    continue
                tokens = checked.get("tokens")
                if not isinstance(tokens, list) or any(
                    not isinstance(token, dict)
                    or token.get("status") not in ("not_found", "exact_match", "non_word")
                    or not isinstance(token.get("raw_token"), str)
                    for token in tokens
                ):
                    issues.append({"code": "invalid_lexicon_tokens", "block_id": block_id})
                    continue
                alerts = [token for token in tokens if token["status"] == "not_found"]
                if alerts:
                    alert_count += len(alerts)
                    alert_groups.append({"page_id": page_id, "block_id": block_id,
                                         "source_region_ids": block.get("source_region_ids", []),
                                         "alert_count": len(alerts),
                                         "tokens": [token.get("raw_token", "") for token in alerts],
                                         "status": "pending_classification"})

        try:
            expected_markdown = _render_structure(structure)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            issues.append({"code": "invalid_candidate_structure", "detail": str(exc)})
        else:
            if loaded["markdown"].replace("\r\n", "\n") != expected_markdown:
                issues.append({"code": "markdown_mismatch"})

    status = "blocked" if missing or issues else "diagnostic_only"
    payload: dict[str, Any] = {
        "@type": "OcrCandidateAssessment", "schema_version": "1.0",
        "inputs": {name: {"path": str(path), "digest": digests.get(name)} for name, path in paths.items()},
        "checks": {"issues": issues, "issue_count": len(issues)},
        "diagnostics": {"lexical_alert_count": alert_count, "groups": alert_groups,
                        "pending_classification_group_count": len(alert_groups),
                        "region_coverage": region_coverage},
        "processability_status": status,
        "routing_status": "not_calibrated",
        "human_review_status": "pending_classification" if alert_groups else "not_assessed",
        "review_preparation_status": "incomplete",
        "human_review_request_allowed": False,
        "visual_coverage_status": "not_assessed",
        "missing_stage_artifacts": [
            "visual_observations", "typed_structure_validation", "alert_dispositions",
        ],
        "manual_action_count": None,
        "machine_pass": False,
        "human_verified": False,
        "claim_extraction_allowed": False,
        "preview_only": True,
    }
    payload["@id"] = "ocr-candidate-assessment:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    operation_status = "preview"
    if apply:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        target = Path(output_path)
        if target.exists():
            if target.read_text(encoding="utf-8") != encoded:
                raise ValueError(f"Output gia' esistente e diverso: {target}")
            operation_status = "skipped_existing"
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
            operation_status = "written"
    payload["operation_status"] = operation_status
    payload["output_path"] = str(output_path)
    return payload


def _render_structure(payload: dict[str, Any]) -> str:
    source = payload["source_evidence"]
    evidence_ref = EvidenceReference(
        page_id=source["page_id"], source_image_hash=source["source_image_hash"],
        transform_id=source["transform_id"], engine=source["engine"], language=source["language"],
        source_page_json=_canonical(source["source_page"]), model_json=_canonical(source["model"]),
        image_transform_json=_canonical(source["image_transform"]) if source.get("image_transform") is not None else None,
    )
    blocks = tuple(DocumentBlock(
        block_id=block.get("block_id", block.get("id")), kind=block["kind"],
        source_region_ids=tuple(block["source_region_ids"]), text=block["text"],
        status=block["status"], structure_confidence=block["structure_confidence"],
        value=block.get("value"),
    ) for block in payload["blocks"])
    return render_document_structure_markdown(DocumentStructure(
        page_id=payload["page_id"], profile=payload["profile"], blocks=blocks,
        source_evidence=evidence_ref, source_evidence_type=payload.get("source_evidence_type", "OcrPageEvidence"),
        schema_version=payload["schema_version"],
    ))


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
