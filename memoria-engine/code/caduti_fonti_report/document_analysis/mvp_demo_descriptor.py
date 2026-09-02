from __future__ import annotations

import copy
import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .preview_payloads import (
    dict_object,
    list_items,
    list_strings,
    load_json_object,
    load_optional_json_object,
    unique_non_empty,
    write_json,
    write_markdown,
)
from .mvp_demo_reconciliation_markdown import render_mvp_demo_reconciliation_markdown


CONTRACT_VERSION = "memoria_mvp_demo.v1"
DEFAULT_PRIMARY_PROFILE_IDS = ("person:purocielo:andreoli-dino",)
DEFAULT_CONTRAST_PROFILE_IDS = ("person:purocielo:balboni-william",)
DEFAULT_SOURCE_DOCUMENT_IDS = (
    "legacy_csv:a4ac96061a2381b5",
    "local_docx:4c2ad1d2ab937913",
    "partigiani_italia:b45553cd6b1673d8",
    "partigiani_italia:b6b3c9e526723a27",
)


def build_mvp_demo_aligned_ledger(
    *,
    data_root: Path,
    run_id: str,
    primary_profile_id: list[str] | None = None,
    contrast_profile_id: list[str] | None = None,
    source_document_id: list[str] | None = None,
    ledger_json: Path | None = None,
    output_json: Path | None = None,
) -> dict[str, Any]:
    """Create a preview-only sidecar ledger aligned to the T30 demo scope."""
    selected_run_id = str(run_id).strip()
    if not selected_run_id:
        raise ValueError("Specificare run_id.")
    run_dir = data_root / "risultati" / "runs" / selected_run_id
    ledger_path = ledger_json or run_dir / "mvp_consolidated_review_ledger.json"
    if not ledger_path.is_file():
        raise FileNotFoundError(f"Ledger consolidato non trovato: {ledger_path}")

    primary_ids = tuple(unique_non_empty(primary_profile_id or list(DEFAULT_PRIMARY_PROFILE_IDS)))
    contrast_ids = tuple(unique_non_empty(contrast_profile_id or list(DEFAULT_CONTRAST_PROFILE_IDS)))
    selected_profile_ids = primary_ids + tuple(profile_id for profile_id in contrast_ids if profile_id not in primary_ids)
    document_ids = tuple(unique_non_empty(source_document_id or list(DEFAULT_SOURCE_DOCUMENT_IDS)))

    original = load_json_object(ledger_path)
    aligned = copy.deepcopy(original)
    profiles = list_items(aligned.get("profiles"))
    target_profile = _find_profile(profiles, primary_ids[0] if primary_ids else "")
    if not target_profile:
        raise ValueError("Profilo principale T30 non trovato nel ledger.")

    added_claims: list[dict[str, Any]] = []
    existing_selected_claim_docs = set(_claim_document_ids_for_profiles(ledger=aligned, profile_ids=selected_profile_ids))
    for document_id in document_ids:
        if document_id in existing_selected_claim_docs:
            continue
        if document_id == "legacy_csv:a4ac96061a2381b5":
            claim = _legacy_csv_alignment_claim(target_profile=target_profile, document_id=document_id)
        else:
            claim = _copy_claim_from_outside_scope(
                profiles=profiles,
                selected_profile_ids=selected_profile_ids,
                target_profile=target_profile,
                document_id=document_id,
            )
        if claim:
            target_profile.setdefault("candidate_evidence_claims", []).append(claim)
            added_claims.append(claim)
            existing_selected_claim_docs.add(document_id)

    _refresh_ledger_counts(aligned)
    aligned["t30_alignment"] = {
        "preview_only": True,
        "source_ledger_json": str(ledger_path),
        "run_id": selected_run_id,
        "primary_profile_ids": list(primary_ids),
        "contrast_profile_ids": list(contrast_ids),
        "source_document_ids": list(document_ids),
        "added_candidate_claim_count": len(added_claims),
        "added_candidate_claim_ids": [str(claim.get("@id", "")) for claim in added_claims],
        "policy": "sidecar_preview_only_no_canonical_profile_patch",
    }
    aligned.setdefault("notes", [])
    if isinstance(aligned["notes"], list):
        aligned["notes"].append("T30 preview alignment sidecar: aggiunge solo claim candidati unreviewed per la golden run.")

    if output_json is not None:
        write_json(output_json, aligned)
    return aligned


def build_mvp_demo_descriptor(
    *,
    data_root: Path,
    run_id: str,
    primary_profile_id: list[str] | None = None,
    contrast_profile_id: list[str] | None = None,
    source_document_id: list[str] | None = None,
    ledger_json: Path | None = None,
    review_queue_json: Path | None = None,
    review_decisions_summary_json: Path | None = None,
    verified_facts_preview_json: Path | None = None,
    profile_patch_preview_json: Path | None = None,
    readiness_report_json: Path | None = None,
    output_json: Path | None = None,
    output_reconciliation_md: Path | None = None,
    status: str = "candidate_for_internal_demo",
) -> dict[str, Any]:
    """Build the preview-only active demo descriptor from one canonical run."""
    selected_run_id = str(run_id).strip()
    if not selected_run_id:
        raise ValueError("Specificare run_id.")
    run_dir = data_root / "risultati" / "runs" / selected_run_id
    ledger_path = ledger_json or run_dir / "mvp_consolidated_review_ledger.json"
    if not ledger_path.is_file():
        raise FileNotFoundError(f"Ledger consolidato non trovato: {ledger_path}")

    primary_ids = tuple(unique_non_empty(primary_profile_id or list(DEFAULT_PRIMARY_PROFILE_IDS)))
    contrast_ids = tuple(unique_non_empty(contrast_profile_id or list(DEFAULT_CONTRAST_PROFILE_IDS)))
    document_ids = tuple(unique_non_empty(source_document_id or list(DEFAULT_SOURCE_DOCUMENT_IDS)))
    selected_profile_ids = primary_ids + tuple(profile_id for profile_id in contrast_ids if profile_id not in primary_ids)

    review_dir = run_dir / "historian_review"
    review_queue_path = review_queue_json or review_dir / "review_queue.json"
    decisions_path = review_decisions_summary_json or review_dir / "review_decisions_summary.json"
    verified_path = verified_facts_preview_json or review_dir / "verified_facts.preview.json"
    patch_path = profile_patch_preview_json or review_dir / "profile_patch.preview.json"
    readiness_path = readiness_report_json or run_dir / "mvp_package_readiness.json"
    reconciliation_path = output_reconciliation_md or run_dir / "mvp_demo_reconciliation_table.md"

    ledger = load_json_object(ledger_path)
    rows = _reconciliation_rows(
        ledger=ledger,
        profile_ids=selected_profile_ids,
        source_document_ids=document_ids,
    )
    scoped_document_ids = _document_ids_for_profiles(ledger=ledger, profile_ids=selected_profile_ids)
    scoped_claim_document_ids = _claim_document_ids_for_profiles(ledger=ledger, profile_ids=selected_profile_ids)
    ledger_claim_document_ids = _claim_document_ids_for_profiles(ledger=ledger, profile_ids=())
    source_families = tuple(sorted({row["source_family"] for row in rows if row.get("source_family")}))
    readiness = _readiness_summary(
        rows=rows,
        primary_profile_ids=primary_ids,
        selected_document_ids=document_ids,
        source_families=source_families,
        scoped_document_ids=scoped_document_ids,
        scoped_claim_document_ids=scoped_claim_document_ids,
        ledger_claim_document_ids=ledger_claim_document_ids,
    )
    generated_at = datetime.now(UTC).isoformat()
    artifacts = _artifact_paths(
        {
            "ledger": ledger_path,
            "reconciliation_table": reconciliation_path,
            "review_queue": review_queue_path,
            "review_decisions_summary": decisions_path,
            "verified_facts_preview": verified_path,
            "profile_patch_preview": patch_path,
            "readiness_report": readiness_path,
        }
    )
    payload: dict[str, Any] = {
        "@type": "MemoriaMvpDemoDescriptor",
        "contract_version": CONTRACT_VERSION,
        "generated_at": generated_at,
        "status": readiness.get("status", status) if status == "candidate_for_internal_demo" else status,
        "run_id": selected_run_id,
        "run_dir": str(run_dir),
        "preview_only": True,
        "publication_status": "not_publishable_without_human_review",
        "primary_profile_ids": list(primary_ids),
        "contrast_profile_ids": list(contrast_ids),
        "source_document_ids": list(document_ids),
        "source_families": list(source_families),
        "readiness": readiness,
        "reconciliation": {
            "row_count": len(rows),
            "field_count": len({(row["profile_id"], row["field"]) for row in rows}),
            "compatibility_counts": _counts(row["compatibility"] for row in rows),
            "rows": rows,
        },
        "review": _review_summary(
            review_queue_path=review_queue_path,
            decisions_path=decisions_path,
            verified_path=verified_path,
            patch_path=patch_path,
        ),
        "artifacts": artifacts,
        "safety": {
            "preview_only": True,
            "applies_review_decisions": False,
            "creates_canonical_verified_facts": False,
            "applies_profile_patch": False,
            "modifies_canonical_profiles": False,
            "publication_ready": False,
        },
        "notes": [
            "Descrittore preview-only della golden run MVP demo.",
            "La tabella di riconciliazione mantiene provenance e divergenze; non applica decisioni o patch.",
        ],
    }
    if output_json is not None:
        write_json(output_json, payload)
    if output_reconciliation_md is not None:
        write_markdown(output_reconciliation_md, render_mvp_demo_reconciliation_markdown(payload))
    return payload


def _reconciliation_rows(
    *,
    ledger: dict[str, Any],
    profile_ids: tuple[str, ...],
    source_document_ids: tuple[str, ...],
) -> list[dict[str, str]]:
    selected_profiles = set(profile_ids)
    selected_documents = set(source_document_ids)
    rows: list[dict[str, str]] = []
    for profile in list_items(ledger.get("profiles")):
        profile_id = str(profile.get("profile_id", "")).strip()
        if selected_profiles and profile_id not in selected_profiles:
            continue
        documents = _documents_by_id(profile)
        for claim in list_items(profile.get("candidate_evidence_claims")):
            document_id = str(claim.get("source_document_id", "")).strip()
            if selected_documents and document_id not in selected_documents:
                continue
            document = documents.get(document_id, {})
            source_family = str(claim.get("source_id") or document.get("source_id") or _source_family(document_id)).strip()
            value = str(claim.get("value") or claim.get("normalized_value") or "").strip()
            normalized_value = str(claim.get("normalized_value") or value).strip().casefold()
            rows.append(
                {
                    "profile_id": profile_id,
                    "canonical_name": str(profile.get("canonical_name", "")).strip(),
                    "field": str(claim.get("field", "")).strip(),
                    "value": value,
                    "normalized_value": normalized_value,
                    "source_document_id": document_id,
                    "source_family": source_family,
                    "extraction_method": str(claim.get("extraction_method", "")).strip(),
                    "review_status": str(claim.get("review_status", "unreviewed")).strip() or "unreviewed",
                    "compatibility": "single_source",
                }
            )
    _annotate_compatibility(rows)
    return sorted(rows, key=lambda item: (item["profile_id"], item["field"], item["source_document_id"], item["value"]))


def _annotate_compatibility(rows: list[dict[str, str]]) -> None:
    by_field: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_field[(row["profile_id"], row["field"])].append(row)
    for field_rows in by_field.values():
        values = {row["normalized_value"] for row in field_rows if row.get("normalized_value")}
        if len(values) > 1:
            for row in field_rows:
                row["compatibility"] = "divergent"
            continue
        document_count = len({row["source_document_id"] for row in field_rows if row.get("source_document_id")})
        family_count = len({row["source_family"] for row in field_rows if row.get("source_family")})
        compatibility = "corroborated" if document_count > 1 or family_count > 1 else "single_source"
        for row in field_rows:
            row["compatibility"] = compatibility


def _documents_by_id(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for document in list_items(profile.get("documents")):
        document_id = str(document.get("source_document_id", "")).strip()
        if document_id:
            documents[document_id] = document
    return documents


def _review_summary(
    *,
    review_queue_path: Path,
    decisions_path: Path,
    verified_path: Path,
    patch_path: Path,
) -> dict[str, Any]:
    review_queue = load_optional_json_object(review_queue_path)
    decisions = load_optional_json_object(decisions_path)
    verified = load_optional_json_object(verified_path)
    patch = load_optional_json_object(patch_path)
    decision_items = _decision_items(decisions)
    profile_patches = list_items(patch.get("profile_patches"))
    return {
        "review_queue_item_count": _item_count(review_queue, ("items", "review_items")),
        "decision_count": len(decision_items),
        "substantive_decision_count": sum(1 for item in decision_items if _substantive_decision(item)),
        "verified_fact_preview_count": _int_value(verified.get("fact_count"), len(list_items(verified.get("facts")))),
        "profile_patch_preview_count": _int_value(patch.get("patch_count"), len(profile_patches)),
        "profile_patch_operation_count": _int_value(
            patch.get("operation_count"),
            sum(len(list_items(item.get("operations"))) for item in profile_patches),
        ),
    }


def _find_profile(profiles: list[dict[str, Any]], profile_id: str) -> dict[str, Any]:
    for profile in profiles:
        if str(profile.get("profile_id", "")).strip() == profile_id:
            return profile
    return {}


def _legacy_csv_alignment_claim(*, target_profile: dict[str, Any], document_id: str) -> dict[str, Any]:
    link = next(
        (
            item
            for item in list_items(target_profile.get("candidate_document_person_links"))
            if str(item.get("source_document_id", "")).strip() == document_id
        ),
        {},
    )
    value = str(link.get("matched_name") or target_profile.get("canonical_name") or "").strip()
    if not value:
        return {}
    return {
        "@id": _alignment_claim_id(
            profile_id=str(target_profile.get("profile_id", "")),
            document_id=document_id,
            field="identity.canonical_name",
            value=value,
            method="t30_preview_alignment_from_candidate_document_person_link",
        ),
        "profile_id": str(target_profile.get("profile_id", "")),
        "source_document_id": document_id,
        "source_id": _source_family(document_id),
        "field": "identity.canonical_name",
        "value": value,
        "normalized_value": value.casefold(),
        "extraction_method": "t30_preview_alignment_from_candidate_document_person_link",
        "evidence_span": f"candidate_document_person_link matched_name: {value}",
        "review_status": "unreviewed",
        "alignment_status": "t30_preview_candidate",
        "alignment_note": "Sidecar preview per coprire la fonte legacy_csv nella golden run; non e' un fatto verificato.",
        "source_runs": list_strings(link.get("source_runs")),
    }


def _copy_claim_from_outside_scope(
    *,
    profiles: list[dict[str, Any]],
    selected_profile_ids: tuple[str, ...],
    target_profile: dict[str, Any],
    document_id: str,
) -> dict[str, Any]:
    selected = set(selected_profile_ids)
    for profile in profiles:
        profile_id = str(profile.get("profile_id", "")).strip()
        if profile_id in selected:
            continue
        for claim in list_items(profile.get("candidate_evidence_claims")):
            if str(claim.get("source_document_id", "")).strip() != document_id:
                continue
            copied = copy.deepcopy(claim)
            copied["profile_id"] = str(target_profile.get("profile_id", ""))
            copied["@id"] = _alignment_claim_id(
                profile_id=copied["profile_id"],
                document_id=document_id,
                field=str(copied.get("field", "")),
                value=str(copied.get("value", "")),
                method="t30_preview_alignment_from_existing_claim",
            )
            copied["source_id"] = str(copied.get("source_id") or _source_family(document_id))
            copied["extraction_method"] = _aligned_method(str(copied.get("extraction_method", "")))
            copied["review_status"] = "unreviewed"
            copied["alignment_status"] = "t30_preview_candidate"
            copied["alignment_source_profile_id"] = profile_id
            copied["alignment_note"] = (
                "Sidecar preview: claim candidato esistente ricondotto al profilo demo per review; "
                "non e' un fatto verificato e non modifica profili canonici."
            )
            return copied
    return {}


def _alignment_claim_id(*, profile_id: str, document_id: str, field: str, value: str, method: str) -> str:
    digest = hashlib.sha256(f"{profile_id}|{document_id}|{field}|{value}|{method}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-evidence-claim:t30-preview:{digest}"


def _aligned_method(method: str) -> str:
    method = method.strip()
    if not method:
        return "t30_preview_alignment_from_existing_claim"
    if method.endswith("|t30_preview_alignment_from_existing_claim"):
        return method
    return f"{method}|t30_preview_alignment_from_existing_claim"


def _refresh_ledger_counts(ledger: dict[str, Any]) -> None:
    profiles = list_items(ledger.get("profiles"))
    for profile in profiles:
        profile["document_count"] = len(list_items(profile.get("documents")))
        profile["candidate_document_person_link_count"] = len(list_items(profile.get("candidate_document_person_links")))
        profile["candidate_evidence_claim_count"] = len(list_items(profile.get("candidate_evidence_claims")))
        profile["reviewable_document_signal_count"] = len(list_items(profile.get("reviewable_document_signals")))
        profile["review_item_count"] = len(list_items(profile.get("review_items")))
        profile["review_decision_count"] = len(list_items(profile.get("review_decisions")))
    ledger["profile_count"] = len(profiles)
    ledger["document_count"] = sum(_int_value(profile.get("document_count")) for profile in profiles)
    ledger["candidate_document_person_link_count"] = sum(
        _int_value(profile.get("candidate_document_person_link_count")) for profile in profiles
    )
    ledger["candidate_evidence_claim_count"] = sum(_int_value(profile.get("candidate_evidence_claim_count")) for profile in profiles)
    ledger["reviewable_document_signal_count"] = sum(_int_value(profile.get("reviewable_document_signal_count")) for profile in profiles)


def _readiness_summary(
    *,
    rows: list[dict[str, str]],
    primary_profile_ids: tuple[str, ...],
    selected_document_ids: tuple[str, ...],
    source_families: tuple[str, ...],
    scoped_document_ids: tuple[str, ...] = (),
    scoped_claim_document_ids: tuple[str, ...] = (),
    ledger_claim_document_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    row_document_ids = {row["source_document_id"] for row in rows if row.get("source_document_id")}
    row_profile_ids = {row["profile_id"] for row in rows if row.get("profile_id")}
    scoped_document_id_set = set(scoped_document_ids)
    scoped_claim_document_id_set = set(scoped_claim_document_ids)
    ledger_claim_document_id_set = set(ledger_claim_document_ids)
    selected_source_families = tuple(
        sorted({source_family for source_family in (_source_family(document_id) for document_id in selected_document_ids) if source_family})
    )
    missing_source_families = [
        source_family for source_family in selected_source_families if source_family and source_family not in source_families
    ]
    missing_documents = [document_id for document_id in selected_document_ids if document_id not in row_document_ids]
    missing_documents_present_in_scope = [
        document_id for document_id in missing_documents if document_id in scoped_document_id_set
    ]
    missing_documents_absent_from_scope = [
        document_id for document_id in missing_documents if document_id not in scoped_document_id_set
    ]
    missing_documents_without_candidate_claims = [
        document_id for document_id in missing_documents if document_id not in ledger_claim_document_id_set
    ]
    missing_documents_with_claims_outside_selected_profiles = [
        document_id
        for document_id in missing_documents
        if document_id in ledger_claim_document_id_set and document_id not in scoped_claim_document_id_set
    ]
    missing_primary_profiles = [profile_id for profile_id in primary_profile_ids if profile_id not in row_profile_ids]
    document_diagnostics = _document_diagnostics(
        selected_document_ids=selected_document_ids,
        row_document_ids=row_document_ids,
        scoped_document_ids=scoped_document_id_set,
        scoped_claim_document_ids=scoped_claim_document_id_set,
        ledger_claim_document_ids=ledger_claim_document_id_set,
    )
    source_family_diagnostics = _source_family_diagnostics(document_diagnostics)
    alignment_plan = _alignment_plan(document_diagnostics)

    if not rows:
        errors.append("no_reconciliation_rows_for_selected_scope")
    if len(source_families) < 2:
        errors.append("multi_source_reconciliation_requires_at_least_two_source_families")
    if missing_primary_profiles:
        errors.append("primary_profile_without_reconciliation_rows")
    if missing_documents:
        warnings.append("selected_documents_without_reconciliation_rows")
    next_actions = _readiness_next_actions(
        errors=errors,
        missing_source_families=missing_source_families,
        missing_documents_without_candidate_claims=missing_documents_without_candidate_claims,
        missing_documents_with_claims_outside_selected_profiles=missing_documents_with_claims_outside_selected_profiles,
        missing_documents_absent_from_scope=missing_documents_absent_from_scope,
    )

    return {
        "status": "ready_for_internal_demo" if not errors else "blocked_for_internal_demo",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "next_actions": next_actions,
        "source_family_count": len(source_families),
        "selected_source_families": list(selected_source_families),
        "covered_source_families": list(source_families),
        "missing_source_families": missing_source_families,
        "selected_document_count": len(selected_document_ids),
        "covered_document_count": len(row_document_ids),
        "covered_source_document_ids": sorted(row_document_ids),
        "source_family_diagnostics": source_family_diagnostics,
        "document_diagnostics": document_diagnostics,
        "alignment_plan": alignment_plan,
        "missing_source_document_ids": missing_documents,
        "missing_documents_present_in_selected_profiles": missing_documents_present_in_scope,
        "missing_documents_absent_from_selected_profiles": missing_documents_absent_from_scope,
        "missing_documents_without_candidate_claims": missing_documents_without_candidate_claims,
        "missing_documents_with_claims_outside_selected_profiles": missing_documents_with_claims_outside_selected_profiles,
        "missing_primary_profile_ids": missing_primary_profiles,
        "checks": {
            "has_reconciliation_rows": bool(rows),
            "has_multi_source_reconciliation": len(source_families) >= 2,
            "primary_profiles_have_rows": not missing_primary_profiles,
            "all_selected_documents_have_rows": not missing_documents,
        },
    }


def _document_diagnostics(
    *,
    selected_document_ids: tuple[str, ...],
    row_document_ids: set[str],
    scoped_document_ids: set[str],
    scoped_claim_document_ids: set[str],
    ledger_claim_document_ids: set[str],
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    for document_id in selected_document_ids:
        if document_id in row_document_ids:
            reconciliation_status = "covered"
        else:
            reconciliation_status = "missing_reconciliation_row"
        if document_id in scoped_document_ids:
            profile_scope_status = "present_in_selected_profiles"
        else:
            profile_scope_status = "absent_from_selected_profiles"
        if document_id in scoped_claim_document_ids:
            candidate_claim_status = "claims_in_selected_profiles"
        elif document_id in ledger_claim_document_ids:
            candidate_claim_status = "claims_outside_selected_profiles"
        else:
            candidate_claim_status = "no_candidate_claims"
        blocking_reason = _document_blocking_reason(
            reconciliation_status=reconciliation_status,
            profile_scope_status=profile_scope_status,
            candidate_claim_status=candidate_claim_status,
        )
        diagnostics.append(
            {
                "source_document_id": document_id,
                "source_family": _source_family(document_id),
                "reconciliation_status": reconciliation_status,
                "profile_scope_status": profile_scope_status,
                "candidate_claim_status": candidate_claim_status,
                "blocking_reason": blocking_reason,
            }
        )
    return diagnostics


def _document_blocking_reason(
    *,
    reconciliation_status: str,
    profile_scope_status: str,
    candidate_claim_status: str,
) -> str:
    if reconciliation_status == "covered":
        return "covered"
    if candidate_claim_status == "no_candidate_claims":
        return "candidate_claims_missing"
    if candidate_claim_status == "claims_outside_selected_profiles":
        return "claims_outside_demo_scope"
    if profile_scope_status == "absent_from_selected_profiles":
        return "document_outside_demo_scope"
    return "reconciliation_row_missing"


def _source_family_diagnostics(document_diagnostics: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in document_diagnostics:
        family = item.get("source_family", "")
        by_family[family].append(item)
    diagnostics: list[dict[str, Any]] = []
    for family, items in sorted(by_family.items()):
        covered_count = sum(1 for item in items if item.get("reconciliation_status") == "covered")
        missing_count = len(items) - covered_count
        if covered_count == len(items):
            coverage_status = "covered"
        elif covered_count:
            coverage_status = "partially_covered"
        else:
            coverage_status = "missing_reconciliation"
        blocking_reasons = sorted(
            {
                reason
                for item in items
                if (reason := str(item.get("blocking_reason", "")).strip()) and reason != "covered"
            }
        )
        diagnostics.append(
            {
                "source_family": family,
                "coverage_status": coverage_status,
                "blocking_reason": ", ".join(blocking_reasons) if blocking_reasons else "covered",
                "selected_document_count": len(items),
                "covered_document_count": covered_count,
                "missing_document_count": missing_count,
            }
        )
    return diagnostics


def _alignment_plan(document_diagnostics: list[dict[str, str]]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for item in document_diagnostics:
        reason = str(item.get("blocking_reason", "")).strip()
        if not reason or reason == "covered":
            continue
        plan.append(
            {
                "step": len(plan) + 1,
                "action": _alignment_action(reason),
                "source_document_id": item.get("source_document_id", ""),
                "source_family": item.get("source_family", ""),
                "reason": reason,
                "preview_only": True,
                "target": "mvp_consolidated_review_ledger",
            }
        )
    return plan


def _alignment_action(reason: str) -> str:
    if reason == "candidate_claims_missing":
        return "produce_candidate_claims"
    if reason == "claims_outside_demo_scope":
        return "attach_existing_claims_to_demo_profile"
    if reason == "document_outside_demo_scope":
        return "attach_document_to_demo_profile"
    return "add_reconciliation_row"


def _readiness_next_actions(
    *,
    errors: list[str],
    missing_source_families: list[str],
    missing_documents_without_candidate_claims: list[str],
    missing_documents_with_claims_outside_selected_profiles: list[str],
    missing_documents_absent_from_scope: list[str],
) -> list[str]:
    actions: list[str] = []
    if "no_reconciliation_rows_for_selected_scope" in errors:
        actions.append("Rigenerare o riallineare il ledger consolidato sul perimetro Andreoli/Balboni selezionato per T30.")
    if "multi_source_reconciliation_requires_at_least_two_source_families" in errors:
        families = ", ".join(missing_source_families) if missing_source_families else "una seconda famiglia fonte T29"
        actions.append(f"Aggiungere alla riconciliazione della run canonica claim da {families}.")
    if missing_documents_without_candidate_claims:
        actions.append(
            "Produrre claim candidati nel ledger per i documenti selezionati senza claim: "
            + ", ".join(missing_documents_without_candidate_claims)
            + "."
        )
    if missing_documents_with_claims_outside_selected_profiles:
        actions.append(
            "Ricondurre al profilo demo selezionato i claim gia' presenti fuori perimetro per: "
            + ", ".join(missing_documents_with_claims_outside_selected_profiles)
            + "."
        )
    if missing_documents_absent_from_scope:
        actions.append(
            "Collegare ai profili demo selezionati i documenti T29 assenti dal perimetro: "
            + ", ".join(missing_documents_absent_from_scope)
            + "."
        )
    if not actions:
        actions.append("Verificare review, verified facts preview e ProfilePatch preview prima di creare il descrittore T30.")
    return actions


def _decision_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list_items(payload.get("decisions")) or list_items(payload.get("provided_decisions"))


def _document_ids_for_profiles(*, ledger: dict[str, Any], profile_ids: tuple[str, ...]) -> tuple[str, ...]:
    selected_profiles = set(profile_ids)
    document_ids: set[str] = set()
    for profile in list_items(ledger.get("profiles")):
        profile_id = str(profile.get("profile_id", "")).strip()
        if selected_profiles and profile_id not in selected_profiles:
            continue
        for document in list_items(profile.get("documents")):
            document_id = str(document.get("source_document_id", "")).strip()
            if document_id:
                document_ids.add(document_id)
    return tuple(sorted(document_ids))


def _claim_document_ids_for_profiles(*, ledger: dict[str, Any], profile_ids: tuple[str, ...]) -> tuple[str, ...]:
    selected_profiles = set(profile_ids)
    document_ids: set[str] = set()
    for profile in list_items(ledger.get("profiles")):
        profile_id = str(profile.get("profile_id", "")).strip()
        if selected_profiles and profile_id not in selected_profiles:
            continue
        for claim in list_items(profile.get("candidate_evidence_claims")):
            document_id = str(claim.get("source_document_id", "")).strip()
            if document_id:
                document_ids.add(document_id)
    return tuple(sorted(document_ids))


def _substantive_decision(item: dict[str, Any]) -> bool:
    action = str(item.get("selected_action", "")).strip().casefold()
    status = str(item.get("decision_status", "")).strip().casefold()
    return action not in {"", "pending"} or status not in {"", "pending"}


def _item_count(payload: dict[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        items = payload.get(key)
        if isinstance(items, list):
            return len(items)
    return _int_value(payload.get("item_count"))


def _artifact_paths(artifacts: dict[str, Path]) -> dict[str, str]:
    return {name: str(path) for name, path in artifacts.items()}


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value).strip() or "unknown"
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))


def _source_family(document_id: str) -> str:
    return document_id.split(":", 1)[0] if ":" in document_id else ""


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default
