from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_readiness_summary(
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
        reconciliation_status = "covered" if document_id in row_document_ids else "missing_reconciliation_row"
        profile_scope_status = "present_in_selected_profiles" if document_id in scoped_document_ids else "absent_from_selected_profiles"
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


def _document_blocking_reason(*, reconciliation_status: str, profile_scope_status: str, candidate_claim_status: str) -> str:
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
        by_family[item.get("source_family", "")].append(item)
    diagnostics: list[dict[str, Any]] = []
    for family, items in sorted(by_family.items()):
        covered_count = sum(1 for item in items if item.get("reconciliation_status") == "covered")
        missing_count = len(items) - covered_count
        coverage_status = "covered" if covered_count == len(items) else "partially_covered" if covered_count else "missing_reconciliation"
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
        actions.append("Produrre claim candidati nel ledger per i documenti selezionati senza claim: " + ", ".join(missing_documents_without_candidate_claims) + ".")
    if missing_documents_with_claims_outside_selected_profiles:
        actions.append("Ricondurre al profilo demo selezionato i claim gia' presenti fuori perimetro per: " + ", ".join(missing_documents_with_claims_outside_selected_profiles) + ".")
    if missing_documents_absent_from_scope:
        actions.append("Collegare ai profili demo selezionati i documenti T29 assenti dal perimetro: " + ", ".join(missing_documents_absent_from_scope) + ".")
    if not actions:
        actions.append("Verificare review, verified facts preview e ProfilePatch preview prima di creare il descrittore T30.")
    return actions


def _source_family(document_id: str) -> str:
    return document_id.split(":", 1)[0] if ":" in document_id else ""
