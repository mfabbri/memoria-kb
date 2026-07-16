from __future__ import annotations

from typing import Any


def render_document_intake_readiness(value: Any) -> list[str]:
    intake = value if isinstance(value, dict) else {}
    if not intake or not intake.get("available"):
        return [
            f"- Stato: `not_available`",
            f"- Prossima azione: {intake.get('next_action', 'Collegare la run locale al riepilogo MVP.')}",
        ]
    input_plan = intake.get("input_processing_plan", {})
    text = intake.get("text_extraction", {})
    ocr = intake.get("ocr_batch", {})
    metadata = intake.get("metadata_extraction", {})
    lines = [
        f"- Run locale: `{intake.get('local_run_dir', '')}`",
        f"- Asset raw rilevati: `{input_plan.get('asset_count', 0)}`",
        f"- Documenti metadatati: `{metadata.get('document_count', 0)}`",
        f"- Testi estratti: `{text.get('extracted_count', 0)}` / `{text.get('document_count', 0)}`",
        f"- Documenti nel riepilogo MVP: `{intake.get('mvp_document_count', 0)}`",
    ]
    action_counts = input_plan.get("action_counts", {})
    if isinstance(action_counts, dict) and action_counts:
        lines.extend(["", "Azioni raw principali:"])
        for action, count in sorted(action_counts.items()):
            lines.append(f"- `{action}`: `{count}`")
    image_ocr = intake.get("image_ocr_readiness", {})
    if isinstance(image_ocr, dict) and image_ocr:
        lines.extend(
            [
                "",
                "Readiness immagini OCR:",
                f"- Immagini OCR richiesto: `{image_ocr.get('image_ocr_required_count', 0)}`",
                f"- Immagini bloccanti: `{image_ocr.get('blocking_image_count', 0)}`",
                f"- Immagini di supporto: `{image_ocr.get('support_image_count', 0)}`",
                f"- Immagini non classificate: `{image_ocr.get('unknown_image_count', 0)}`",
            ]
        )
        warnings = _list_strings(image_ocr.get("warnings"))
        if warnings:
            lines.extend(f"- Warning: {warning}" for warning in warnings)
    ocr_summary = ocr.get("summary", {})
    if isinstance(ocr_summary, dict) and ocr_summary:
        lines.extend(["", "OCR batch:"])
        for key in (
            "processed",
            "skipped_existing_text",
            "skipped_missing_sidecar",
            "skipped_unreadable_sidecar",
            "skipped_sidecar_mismatch",
            "skipped_duplicate_output",
            "error",
        ):
            lines.append(f"- `{key}`: `{ocr_summary.get(key, 0)}`")
    lines.extend(["", "Blocchi/prossime azioni:"])
    for blocker in _list_strings(intake.get("mvp_blockers")):
        lines.append(f"- {blocker}")
    lines.append(f"- Prossima azione consigliata: {intake.get('next_action', '')}")
    return lines


def render_mvp_signal_diagnostics(value: Any) -> list[str]:
    diagnostics = value if isinstance(value, dict) else {}
    if not diagnostics:
        return ["_Diagnostica segnale MVP non disponibile._"]
    lines = [
        f"- Documenti nel pacchetto: `{diagnostics.get('document_count', 0)}`",
        f"- Documenti unici stimati: `{diagnostics.get('estimated_unique_document_count', 0)}`",
        f"- Gruppi duplicati: `{diagnostics.get('duplicate_document_group_count', 0)}`",
        f"- Link nominali deboli: `{diagnostics.get('weak_nominal_link_count', 0)}` / `{diagnostics.get('candidate_document_person_link_count', 0)}`",
        f"- Profili con link ma zero claim: `{diagnostics.get('profiles_with_links_no_claims_count', 0)}`",
        f"- Prossima azione: {diagnostics.get('next_action', '')}",
    ]
    claim_funnel = diagnostics.get("claim_funnel_diagnostics")
    if isinstance(claim_funnel, dict) and claim_funnel:
        lines.extend(
            [
                "",
                "Funnel claim:",
                f"- Stato funnel: `{claim_funnel.get('funnel_status', '')}`",
                f"- Entita saltate: `{claim_funnel.get('skipped_entity_count', 0)}`",
                f"- Skipped con profili candidati: `{claim_funnel.get('skipped_with_candidate_profiles_count', 0)}`",
                f"- Claim con segmento: `{claim_funnel.get('claims_with_weak_segment_id_count', 0)}`",
                f"- Claim con solo chunk: `{claim_funnel.get('claims_with_chunk_id_only_count', 0)}`",
                f"- Prossima azione funnel: {claim_funnel.get('next_action', '')}",
            ]
        )
        counts_by_skip_reason = claim_funnel.get("counts_by_skip_reason")
        if isinstance(counts_by_skip_reason, dict) and counts_by_skip_reason:
            lines.append("Motivi skip claim:")
            for reason, count in sorted(counts_by_skip_reason.items()):
                lines.append(f"- `{reason}`: `{count}`")
    duplicate_groups = _list_items(diagnostics.get("duplicate_document_groups"))
    if duplicate_groups:
        lines.extend(["", "Duplicati da revisionare:"])
        for group in duplicate_groups[:5]:
            source_ids = ", ".join(_list_strings(group.get("source_document_ids")))
            lines.append(
                f"- `{group.get('key_kind', '')}` = `{group.get('key_value', '')}` "
                f"({group.get('document_count', 0)} documenti: {source_ids})"
            )
    profiles = _list_items(diagnostics.get("profiles_with_links_no_claims"))
    if profiles:
        lines.extend(["", "Profili con link ma zero claim:"])
        for profile in profiles[:10]:
            label = profile.get("canonical_name") or profile.get("profile_id", "")
            lines.append(
                f"- `{profile.get('profile_id', '')}` - {label}: "
                f"{profile.get('candidate_document_person_link_count', 0)} link, "
                f"{profile.get('reviewable_document_signal_count', 0)} piste, "
                f"stato `{profile.get('readiness_status', '')}`"
            )
    blockers = _list_strings(diagnostics.get("mvp_blockers"))
    if blockers:
        lines.extend(["", "Blocchi segnale:"])
        lines.extend(f"- {blocker}" for blocker in blockers)
    return lines


def render_pilot_package_scorecard(value: Any) -> list[str]:
    scorecard = value if isinstance(value, dict) else {}
    if not scorecard:
        return ["_Scorecard pacchetto MVP non disponibile._"]
    lines = [
        f"- Stato pacchetto: `{scorecard.get('package_status', '')}`",
        f"- Profili pronti per review: `{scorecard.get('ready_for_review_profile_count', 0)}` / `{scorecard.get('profile_count', 0)}`",
        f"- Profili con blocchi: `{scorecard.get('blocked_profile_count', 0)}`",
        f"- Documenti collegati nel pacchetto: `{scorecard.get('document_count', 0)}`",
        f"- Link persona-documento candidati: `{scorecard.get('candidate_document_person_link_count', 0)}`",
        f"- Claim candidati: `{scorecard.get('candidate_evidence_claim_count', 0)}`",
        f"- Piste documentali revisionabili: `{scorecard.get('reviewable_document_signal_count', 0)}`",
        f"- Item minimi di revisione: `{scorecard.get('minimum_review_item_count', 0)}`",
        f"- Prossima azione: {scorecard.get('next_action', '')}",
    ]
    blockers = _list_strings(scorecard.get("top_blockers"))
    if blockers:
        lines.extend(["", "Blocchi principali:"])
        lines.extend(f"- {blocker}" for blocker in blockers)
    return lines


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]
