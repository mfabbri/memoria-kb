from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..profile_repository import ProfileRepository, is_legacy_seed_profile
from .mvp_pilot_summary_markdown import (
    render_document_intake_readiness as _render_document_intake_readiness,
    render_mvp_signal_diagnostics as _render_mvp_signal_diagnostics,
    render_pilot_package_scorecard as _render_pilot_package_scorecard,
)
from .mvp_pilot_package_status import pilot_package_status_and_action as _pilot_package_status_and_action
from .mvp_pilot_readiness import readiness_status_and_action as _readiness_status_and_action


def build_mvp_pilot_summary(
    *,
    run_dir: Path,
    local_run_dir: Path | None = None,
    profiles_index: Path | None = None,
    profile_ids: list[str] | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    document_dir = run_dir / "document_analysis"
    selected_profile_ids = _normalize_profile_ids(profile_ids or [])
    profiles, profile_warnings = _load_profiles(profiles_index=profiles_index, profile_ids=selected_profile_ids)

    quality = _load_json_object(document_dir / "document_quality_assessment.json")
    metadata = _load_json_object(document_dir / "document_metadata_extraction.json")
    links_payload = _load_json_object(document_dir / "candidate_document_person_links.json")
    entities_payload = _load_json_object(document_dir / "extracted_entities.json")
    claims_payload = _load_json_object(document_dir / "candidate_evidence_claims.json")
    feedback_payload = _load_json_object(document_dir / "research_feedback_actions.json")
    feedback_plan_payload = _load_json_object(document_dir / "feedback_search_plan.json")
    active_profile_ids = [str(profile.get("profile_id", "")) for profile in profiles if str(profile.get("profile_id", ""))]
    require_profile_filter = bool(selected_profile_ids) or bool(profile_warnings)

    links = _filter_by_profile(
        _list_items(links_payload.get("candidate_document_person_links")),
        active_profile_ids,
        require_filter=require_profile_filter,
    )
    linked_document_ids = {str(link.get("source_document_id", "")) for link in links if str(link.get("source_document_id", ""))}
    claims = _filter_by_profile(
        _list_items(claims_payload.get("candidate_evidence_claims")),
        active_profile_ids,
        require_filter=require_profile_filter,
    )
    claim_document_ids = {str(claim.get("source_document_id", "")) for claim in claims if str(claim.get("source_document_id", ""))}
    relevant_document_ids = linked_document_ids | claim_document_ids

    documents = _documents_from_quality_or_metadata(quality=quality, metadata=metadata, relevant_document_ids=relevant_document_ids)
    entities = _filter_by_document(_list_items(entities_payload.get("extracted_entities")), relevant_document_ids)
    skipped_claim_entities = _filter_by_document(_list_items(claims_payload.get("skipped_entities")), relevant_document_ids)
    skipped_structured_documents = _filter_by_document(
        _list_items(claims_payload.get("skipped_structured_documents")),
        relevant_document_ids,
    )
    claim_funnel_diagnostics = _claim_funnel_diagnostics_for_summary(
        claims=claims,
        skipped_claim_entities=skipped_claim_entities,
        source_diagnostics=claims_payload.get("claim_funnel_diagnostics"),
    )
    feedback_actions = _feedback_actions(feedback_payload, relevant_document_ids=relevant_document_ids)
    feedback_plans = _filter_by_profile(
        _list_items(feedback_plan_payload.get("plans")),
        active_profile_ids,
        require_filter=require_profile_filter,
    )
    reviewable_document_signals = _build_reviewable_document_signals(
        profiles=profiles,
        links=links,
        entities=entities,
        feedback_actions=feedback_actions,
        skipped_claim_entities=skipped_claim_entities,
        skipped_structured_documents=skipped_structured_documents,
    )
    signal_count = sum(len(_list_items(item.get("signals"))) for item in reviewable_document_signals)
    profile_readiness = _build_profile_readiness(
        profiles=profiles,
        documents=documents,
        links=links,
        claims=claims,
        reviewable_document_signals=reviewable_document_signals,
    )
    document_intake_readiness = _document_intake_readiness(local_run_dir=local_run_dir, mvp_document_count=len(documents))
    signal_diagnostics = _build_mvp_signal_diagnostics(
        profiles=profiles,
        documents=documents,
        links=links,
        claims=claims,
        claim_funnel_diagnostics=claim_funnel_diagnostics,
        profile_readiness=profile_readiness,
    )
    warnings = _warnings(
        selected_profile_ids=selected_profile_ids,
        profiles=profiles,
        documents=documents,
        links=links,
        claims=claims,
        signal_count=signal_count,
    )
    warnings.extend(profile_warnings)
    pilot_package_scorecard = _build_pilot_package_scorecard(
        profile_readiness=profile_readiness,
        document_intake_readiness=document_intake_readiness,
        profile_count=len(profiles),
        document_count=len(documents),
        link_count=len(links),
        claim_count=len(claims),
        signal_count=signal_count,
        warning_count=len(warnings),
    )

    payload: dict[str, Any] = {
        "@type": "MvpPilotSummary",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_dir": str(run_dir),
        "local_run_dir": str(local_run_dir) if local_run_dir else "",
        "document_analysis_dir": str(document_dir),
        "profiles_index": str(profiles_index) if profiles_index else "",
        "pilot_profile_ids": selected_profile_ids,
        "profile_count": len(profiles),
        "document_count": len(documents),
        "candidate_document_person_link_count": len(links),
        "extracted_entity_count": len(entities),
        "candidate_evidence_claim_count": len(claims),
        "reviewable_document_signal_count": signal_count,
        "research_feedback_action_count": len(feedback_actions),
        "feedback_search_plan_count": len(feedback_plans),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "profiles": profiles,
        "documents": documents,
        "candidate_document_person_links": links,
        "extracted_entities": entities,
        "candidate_evidence_claims": claims,
        "research_feedback_actions": feedback_actions,
        "feedback_search_plans": feedback_plans,
        "reviewable_document_signals": reviewable_document_signals,
        "profile_readiness": profile_readiness,
        "document_intake_readiness": document_intake_readiness,
        "mvp_signal_diagnostics": signal_diagnostics,
        "pilot_package_scorecard": pilot_package_scorecard,
        "warnings": warnings,
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_pilot_summary_markdown(payload), encoding="utf-8")
    return payload


def render_mvp_pilot_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# MVP pilot summary",
        "",
        f"- Run: `{payload.get('run_dir', '')}`",
        f"- Stato revisione: `{payload.get('review_status', '')}`",
        f"- Stato pubblicazione: `{payload.get('publication_status', '')}`",
        f"- Profili pilota: `{payload.get('profile_count', 0)}`",
        f"- Documenti: `{payload.get('document_count', 0)}`",
        f"- Link persona-documento candidati: `{payload.get('candidate_document_person_link_count', 0)}`",
        f"- Entita' estratte: `{payload.get('extracted_entity_count', 0)}`",
        f"- Claim candidati: `{payload.get('candidate_evidence_claim_count', 0)}`",
        f"- Piste documentali revisionabili: `{payload.get('reviewable_document_signal_count', 0)}`",
        f"- Piste di ricerca: `{payload.get('research_feedback_action_count', 0)}`",
        "",
        "## Profili pilota",
        "",
    ]
    profiles = _list_items(payload.get("profiles"))
    if profiles:
        for profile in profiles:
            lines.append(f"- `{profile.get('profile_id', '')}` - {profile.get('canonical_name', '')}")
    else:
        lines.append("_Nessun profilo pilota risolto._")

    lines.extend(["", "## Stato schede pilota", ""])
    readiness = _list_items(payload.get("profile_readiness"))
    if readiness:
        lines.extend(
            [
                "| Profilo | Documenti | Link | Claim | Piste | Stato | Prossima azione |",
                "|---|---:|---:|---:|---:|---|---|",
            ]
        )
        for item in readiness:
            lines.append(
                "| "
                f"`{item.get('profile_id', '')}` "
                f"| {item.get('document_count', 0)} "
                f"| {item.get('candidate_document_person_link_count', 0)} "
                f"| {item.get('candidate_evidence_claim_count', 0)} "
                f"| {item.get('reviewable_document_signal_count', 0)} "
                f"| `{item.get('readiness_status', '')}` "
                f"| {item.get('next_action', '')} |"
            )
    else:
        lines.append("_Nessuno stato scheda pilota disponibile._")

    lines.extend(["", "## Scorecard pacchetto MVP", ""])
    lines.extend(_render_pilot_package_scorecard(payload.get("pilot_package_scorecard")))

    lines.extend(["", "## Stato ingest documentale", ""])
    lines.extend(_render_document_intake_readiness(payload.get("document_intake_readiness")))

    lines.extend(["", "## Diagnostica segnale MVP", ""])
    lines.extend(_render_mvp_signal_diagnostics(payload.get("mvp_signal_diagnostics")))

    lines.extend(["", "## Evidenze candidate", ""])
    claims = _list_items(payload.get("candidate_evidence_claims"))
    if claims:
        for claim in claims:
            lines.extend(
                [
                    f"### {claim.get('field', '')}: {claim.get('value', '')}",
                    "",
                    f"- Profilo: `{claim.get('profile_id', claim.get('person_candidate_id', ''))}`",
                    f"- Documento: `{claim.get('source_document_id', '')}`",
                    f"- Stato revisione: `{claim.get('review_status', '')}`",
                    f"- Contesto: {claim.get('evidence_span', claim.get('context', ''))}",
                    "",
                ]
            )
    else:
        lines.append("_Nessun claim candidato nel perimetro pilota._")

    lines.extend(["", "## Piste documentali per profilo", ""])
    signal_groups = _list_items(payload.get("reviewable_document_signals"))
    if signal_groups:
        for group in signal_groups:
            signals = _list_items(group.get("signals"))
            if not signals:
                continue
            lines.extend([f"### {group.get('canonical_name') or group.get('profile_id', '')}", ""])
            for signal in signals:
                lines.extend(
                    [
                        f"- Tipo: `{signal.get('signal_type', '')}` | Documento: `{signal.get('source_document_id', '')}`",
                        f"  - Stato revisione: `{signal.get('review_status', '')}`",
                        f"  - Motivo: {', '.join(_list_strings(signal.get('reasons')))}",
                    ]
                )
                context = str(signal.get("context", "")).strip()
                if context:
                    lines.append(f"  - Contesto: {context}")
            lines.append("")
    else:
        lines.append("_Nessuna pista documentale revisionabile nel perimetro pilota._")

    lines.extend(["", "## Revisione", ""])
    warnings = _list_strings(payload.get("warnings"))
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- Output pronto per revisione umana; nessun fatto e' stato verificato automaticamente.")

    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Questo report e' derivato da output automatici e resta preview-only.",
            "- Nessun `CandidateEvidenceClaim` e' promosso a fatto verificato.",
            "- I profili JSON-LD reali non vengono modificati.",
            "",
        ]
    )
    return "\n".join(lines)


def _load_profiles(*, profiles_index: Path | None, profile_ids: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    if profiles_index is None or not profiles_index.exists():
        return [{"profile_id": profile_id, "canonical_name": "", "profile_source_file": ""} for profile_id in profile_ids], []
    repository = ProfileRepository(profiles_index)
    profiles = []
    legacy_profile_ids = []
    selected = set(profile_ids)
    for entry in repository.list_entries():
        if selected and entry.profile_id not in selected:
            continue
        profile = repository.load_entry(entry)
        if is_legacy_seed_profile(profile):
            legacy_profile_ids.append(profile.profile_id)
            continue
        profiles.append(
            {
                "profile_id": profile.profile_id,
                "canonical_name": profile.identity.canonical_name,
                "profile_source_file": str(profile.metadata.get("profile_source_file", "")),
            }
        )
    warnings = []
    if legacy_profile_ids:
        warnings.append(
            "Profili esclusi per seed legacy caduti_purocielo.csv: "
            + ", ".join(sorted(set(legacy_profile_ids)))
            + ". Rigenerare i profili da fonti strutturate correnti prima di usarli nel perimetro pilota."
        )
    return profiles, warnings


def _normalize_profile_ids(profile_ids: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in profile_ids:
        for item in str(raw).split(","):
            value = item.strip().strip('"').strip("'").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
    return normalized


def _documents_from_quality_or_metadata(
    *,
    quality: dict[str, Any],
    metadata: dict[str, Any],
    relevant_document_ids: set[str],
) -> list[dict[str, Any]]:
    quality_documents = _list_items(quality.get("documents"))
    metadata_documents = _list_items(metadata.get("documents"))
    source_documents = quality_documents or metadata_documents
    documents = []
    for document in source_documents:
        document_id = str(document.get("source_document_id", ""))
        if relevant_document_ids and document_id not in relevant_document_ids:
            continue
        documents.append(document)
    return documents


def _filter_by_profile(
    items: list[dict[str, Any]],
    profile_ids: list[str],
    *,
    require_filter: bool = False,
) -> list[dict[str, Any]]:
    if not profile_ids:
        return [] if require_filter else items
    selected = set(profile_ids)
    return [
        item
        for item in items
        if str(item.get("profile_id") or item.get("person_candidate_id") or item.get("person_id") or "") in selected
    ]


def _filter_by_document(items: list[dict[str, Any]], document_ids: set[str]) -> list[dict[str, Any]]:
    if not document_ids:
        return items
    return [item for item in items if str(item.get("source_document_id", "")) in document_ids]


def _feedback_actions(payload: dict[str, Any], *, relevant_document_ids: set[str]) -> list[dict[str, Any]]:
    actions = []
    for document in _list_items(payload.get("documents")):
        document_id = str(document.get("source_document_id", ""))
        if relevant_document_ids and document_id not in relevant_document_ids:
            continue
        actions.extend(_list_items(document.get("actions")))
    return actions


def _build_reviewable_document_signals(
    *,
    profiles: list[dict[str, str]],
    links: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    feedback_actions: list[dict[str, Any]],
    skipped_claim_entities: list[dict[str, Any]],
    skipped_structured_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links_by_profile: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        profile_id = _profile_id_from_item(link)
        if profile_id:
            links_by_profile.setdefault(profile_id, []).append(link)

    entities_by_document = _items_by_document(entities)
    actions_by_document = _items_by_document(feedback_actions)
    skipped_by_document = _items_by_document(skipped_claim_entities)
    skipped_structured_by_document = _items_by_document(skipped_structured_documents)

    groups: list[dict[str, Any]] = []
    for profile in profiles:
        profile_id = str(profile.get("profile_id", ""))
        profile_links = links_by_profile.get(profile_id, [])
        deduped = _build_profile_reviewable_document_signals(
            profile_id=profile_id,
            profile_links=profile_links,
            entities_by_document=entities_by_document,
            actions_by_document=actions_by_document,
            skipped_by_document=skipped_by_document,
            skipped_structured_by_document=skipped_structured_by_document,
        )
        if deduped:
            groups.append(
                {
                    "@type": "MvpProfileReviewableDocumentSignals",
                    "profile_id": profile_id,
                    "canonical_name": profile.get("canonical_name", ""),
                    "signal_count": len(deduped),
                    "signals": deduped,
                    "review_status": "unreviewed",
                    "publication_status": "not_publishable_without_human_review",
                }
            )
    return groups


def _build_profile_reviewable_document_signals(
    *,
    profile_id: str,
    profile_links: list[dict[str, Any]],
    entities_by_document: dict[str, list[dict[str, Any]]],
    actions_by_document: dict[str, list[dict[str, Any]]],
    skipped_by_document: dict[str, list[dict[str, Any]]],
    skipped_structured_by_document: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    document_ids = sorted(
        {
            str(link.get("source_document_id", ""))
            for link in profile_links
            if str(link.get("source_document_id", ""))
        }
    )
    signals: list[dict[str, Any]] = []
    for link in profile_links[:5]:
        signals.append(_signal_from_link(link))
    for document_id in document_ids:
        signals.extend(_signal_from_feedback_action(action) for action in actions_by_document.get(document_id, [])[:3])
        signals.extend(_signal_from_entity(entity) for entity in entities_by_document.get(document_id, [])[:3])
        applicable_skipped = [
            skipped
            for skipped in skipped_by_document.get(document_id, [])
            if _skipped_claim_applies_to_profile(skipped=skipped, profile_id=profile_id)
        ]
        signals.extend(_signal_from_skipped_claim(skipped) for skipped in applicable_skipped[:3])
        applicable_structured = [
            skipped
            for skipped in skipped_structured_by_document.get(document_id, [])
            if _skipped_claim_applies_to_profile(skipped=skipped, profile_id=profile_id)
        ]
        signals.extend(_signal_from_skipped_structured_document(skipped) for skipped in applicable_structured[:3])
    return _deduplicate_signals(signals)[:10]


def _signal_from_link(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "@type": "ReviewableDocumentSignal",
        "signal_type": "candidate_document_person_link",
        "source_document_id": str(link.get("source_document_id", "")),
        "source_item_id": str(link.get("@id") or link.get("link_id") or ""),
        "context": str(link.get("context") or link.get("evidence_span") or ""),
        "confidence": link.get("score", ""),
        "reasons": [*_list_strings(link.get("reasons")), "candidate_document_person_link_unreviewed"],
        "review_status": "unreviewed",
    }


def _signal_from_feedback_action(action: dict[str, Any]) -> dict[str, Any]:
    context = action.get("context", {})
    context_text = ""
    if isinstance(context, dict):
        context_text = str(context.get("quote") or context.get("context") or context.get("support_summary") or "")
    return {
        "@type": "ReviewableDocumentSignal",
        "signal_type": "research_feedback_action",
        "source_document_id": str(action.get("source_document_id", "")),
        "source_item_id": str(action.get("@id") or action.get("action_id") or action.get("source_candidate_id") or ""),
        "value": str(action.get("value", "")),
        "context": context_text,
        "confidence": action.get("confidence", ""),
        "reasons": [*_list_strings(action.get("reasons")), "research_feedback_action_unreviewed"],
        "review_status": "unreviewed",
    }


def _signal_from_entity(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "@type": "ReviewableDocumentSignal",
        "signal_type": "extracted_entity",
        "source_document_id": str(entity.get("source_document_id", "")),
        "source_item_id": str(entity.get("@id") or entity.get("entity_id") or ""),
        "value": str(entity.get("value", "")),
        "context": str(entity.get("context", "")),
        "confidence": entity.get("score", entity.get("confidence", "")),
        "reasons": [*_list_strings(entity.get("reasons")), "extracted_entity_unreviewed"],
        "review_status": "unreviewed",
    }


def _signal_from_skipped_claim(skipped: dict[str, Any]) -> dict[str, Any]:
    reason = str(skipped.get("reason", "candidate_claim_skipped"))
    return {
        "@type": "ReviewableDocumentSignal",
        "signal_type": "skipped_claim_candidate",
        "source_document_id": str(skipped.get("source_document_id", "")),
        "source_item_id": str(skipped.get("@id") or skipped.get("entity_id") or ""),
        "value": str(skipped.get("value", "")),
        "entity_type": str(skipped.get("entity_type", "")),
        "context": str(skipped.get("context", "")),
        "chunk_id": str(skipped.get("chunk_id", "")),
        "weak_segment_id": str(skipped.get("weak_segment_id", "")),
        "recommended_next_action": str(skipped.get("recommended_next_action", "")),
        "candidate_profile_ids": _list_strings(skipped.get("candidate_profile_ids")),
        "confidence": "",
        "reasons": [reason, "skipped_claim_candidate_unreviewed"],
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def _signal_from_skipped_structured_document(skipped: dict[str, Any]) -> dict[str, Any]:
    reason = str(skipped.get("reason", "structured_document_claim_skipped"))
    context_parts = [
        str(skipped.get("title", "")).strip(),
        str(skipped.get("url", "")).strip(),
        f"Motivo skip: {reason}",
    ]
    return {
        "@type": "ReviewableDocumentSignal",
        "signal_type": "skipped_structured_document_claim_candidate",
        "source_document_id": str(skipped.get("source_document_id", "")),
        "source_item_id": str(skipped.get("@id") or ""),
        "value": reason,
        "context": " | ".join(part for part in context_parts if part),
        "recommended_next_action": str(skipped.get("recommended_next_action", "")),
        "candidate_profile_ids": _list_strings(skipped.get("candidate_profile_ids")),
        "candidate_document_person_link_ids": _list_strings(skipped.get("candidate_document_person_link_ids")),
        "confidence": "",
        "reasons": [reason, "skipped_structured_document_claim_candidate_unreviewed"],
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def _skipped_claim_applies_to_profile(*, skipped: dict[str, Any], profile_id: str) -> bool:
    candidate_profile_ids = _list_strings(skipped.get("candidate_profile_ids"))
    if not candidate_profile_ids:
        return True
    return profile_id in candidate_profile_ids


def _items_by_document(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_document: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        document_id = str(item.get("source_document_id", ""))
        if document_id:
            by_document.setdefault(document_id, []).append(item)
    return by_document


def _deduplicate_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for signal in signals:
        key = (
            str(signal.get("signal_type", "")),
            str(signal.get("source_document_id", "")),
            str(signal.get("source_item_id", "")),
            str(signal.get("context", ""))[:80],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped


def _build_profile_readiness(
    *,
    profiles: list[dict[str, str]],
    documents: list[dict[str, Any]],
    links: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    reviewable_document_signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    document_ids = {str(document.get("source_document_id", "")) for document in documents if str(document.get("source_document_id", ""))}
    signals_by_profile = {
        str(group.get("profile_id", "")): _list_items(group.get("signals"))
        for group in reviewable_document_signals
        if str(group.get("profile_id", ""))
    }
    readiness = []
    for profile in profiles:
        profile_id = str(profile.get("profile_id", ""))
        profile_links = [link for link in links if _profile_id_from_item(link) == profile_id]
        profile_claims = [claim for claim in claims if _profile_id_from_item(claim) == profile_id]
        profile_signals = signals_by_profile.get(profile_id, [])
        profile_document_ids = {
            str(item.get("source_document_id", ""))
            for item in [*profile_links, *profile_claims, *profile_signals]
            if str(item.get("source_document_id", ""))
        }
        if document_ids:
            profile_document_ids &= document_ids
        status, next_action = _readiness_status_and_action(
            document_count=len(profile_document_ids),
            link_count=len(profile_links),
            claim_count=len(profile_claims),
            signal_count=len(profile_signals),
        )
        readiness.append(
            {
                "profile_id": profile_id,
                "canonical_name": profile.get("canonical_name", ""),
                "document_count": len(profile_document_ids),
                "candidate_document_person_link_count": len(profile_links),
                "candidate_evidence_claim_count": len(profile_claims),
                "reviewable_document_signal_count": len(profile_signals),
                "readiness_status": status,
                "next_action": next_action,
                "review_status": "unreviewed",
                "publication_status": "not_publishable_without_human_review",
            }
        )
    return readiness


def _build_pilot_package_scorecard(
    *,
    profile_readiness: list[dict[str, Any]],
    document_intake_readiness: dict[str, Any],
    profile_count: int,
    document_count: int,
    link_count: int,
    claim_count: int,
    signal_count: int,
    warning_count: int,
) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for item in profile_readiness:
        status = str(item.get("readiness_status", "") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    ready_count = status_counts.get("ready_for_review", 0)
    blockers = [
        blocker
        for blocker in _list_strings(document_intake_readiness.get("mvp_blockers"))
        if not blocker.startswith("Nessun blocco documentale evidente")
    ]
    package_status, next_action = _pilot_package_status_and_action(
        profile_count=profile_count,
        document_count=document_count,
        link_count=link_count,
        claim_count=claim_count,
        signal_count=signal_count,
        ready_count=ready_count,
        blockers=blockers,
    )
    return {
        "@type": "MvpPilotPackageScorecard",
        "package_status": package_status,
        "profile_count": profile_count,
        "ready_for_review_profile_count": ready_count,
        "blocked_profile_count": max(profile_count - ready_count, 0),
        "readiness_status_counts": status_counts,
        "document_count": document_count,
        "candidate_document_person_link_count": link_count,
        "candidate_evidence_claim_count": claim_count,
        "reviewable_document_signal_count": signal_count,
        "minimum_review_item_count": profile_count + link_count + claim_count + signal_count + warning_count,
        "document_intake_blocker_count": len(blockers),
        "top_blockers": blockers[:5],
        "next_action": next_action,
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def _build_mvp_signal_diagnostics(
    *,
    profiles: list[dict[str, str]],
    documents: list[dict[str, Any]],
    links: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    claim_funnel_diagnostics: dict[str, Any],
    profile_readiness: list[dict[str, Any]],
) -> dict[str, Any]:
    duplicate_diagnostics = _build_document_duplicate_diagnostics(documents)
    duplicate_groups = duplicate_diagnostics["duplicate_document_groups"]
    weak_nominal_links = [link for link in links if _is_weak_nominal_link(link)]
    claim_profile_ids = {_profile_id_from_item(claim) for claim in claims if _profile_id_from_item(claim)}
    link_profile_ids = {_profile_id_from_item(link) for link in links if _profile_id_from_item(link)}
    profiles_with_links_no_claims = []
    profiles_by_id = {str(profile.get("profile_id", "")): profile for profile in profiles}
    for profile_id in sorted(link_profile_ids - claim_profile_ids):
        readiness = next((item for item in profile_readiness if str(item.get("profile_id", "")) == profile_id), {})
        profiles_with_links_no_claims.append(
            {
                "profile_id": profile_id,
                "canonical_name": str(profiles_by_id.get(profile_id, {}).get("canonical_name", "")),
                "candidate_document_person_link_count": _int_value(readiness.get("candidate_document_person_link_count")),
                "reviewable_document_signal_count": _int_value(readiness.get("reviewable_document_signal_count")),
                "readiness_status": str(readiness.get("readiness_status", "")),
                "next_action": str(readiness.get("next_action", "")),
            }
        )

    total_duplicate_documents = duplicate_diagnostics["duplicate_document_count"]
    unique_document_count = duplicate_diagnostics["estimated_unique_document_count"]
    blockers = _mvp_signal_blockers(
        document_count=len(documents),
        unique_document_count=unique_document_count,
        duplicate_groups=duplicate_groups,
        weak_nominal_link_count=len(weak_nominal_links),
        link_count=len(links),
        claim_count=len(claims),
        profiles_with_links_no_claims=profiles_with_links_no_claims,
    )
    return {
        "@type": "MvpSignalDiagnostics",
        "document_count": len(documents),
        "estimated_unique_document_count": unique_document_count,
        "duplicate_document_group_count": len(duplicate_groups),
        "duplicate_document_count": total_duplicate_documents,
        "duplicate_document_groups": duplicate_groups[:10],
        "candidate_document_person_link_count": len(links),
        "weak_nominal_link_count": len(weak_nominal_links),
        "candidate_evidence_claim_count": len(claims),
        "claim_funnel_diagnostics": claim_funnel_diagnostics,
        "skipped_claim_entity_count": _int_value(claim_funnel_diagnostics.get("skipped_entity_count")),
        "skipped_claims_with_candidate_profiles_count": _int_value(
            claim_funnel_diagnostics.get("skipped_with_candidate_profiles_count")
        ),
        "claim_funnel_next_action": str(claim_funnel_diagnostics.get("next_action", "")),
        "profiles_with_links_no_claims_count": len(profiles_with_links_no_claims),
        "profiles_with_links_no_claims": profiles_with_links_no_claims,
        "mvp_blockers": blockers,
        "next_action": _mvp_signal_next_action(blockers),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def _build_document_duplicate_diagnostics(documents: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_groups = _document_duplicate_groups(documents)
    duplicate_document_count = sum(_int_value(group.get("document_count")) - 1 for group in duplicate_groups)
    return {
        "duplicate_document_groups": duplicate_groups,
        "duplicate_document_count": duplicate_document_count,
        "estimated_unique_document_count": max(len(documents) - duplicate_document_count, 0),
    }


def _document_duplicate_groups(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for document in documents:
        key = _document_identity_key(document)
        if key is None:
            continue
        grouped.setdefault(key, []).append(document)

    duplicate_groups = []
    for (key_kind, key_value), group in sorted(grouped.items(), key=lambda item: item[0]):
        if len(group) < 2:
            continue
        duplicate_groups.append(
            {
                "key_kind": key_kind,
                "key_value": key_value,
                "document_count": len(group),
                "source_document_ids": [
                    str(document.get("source_document_id", ""))
                    for document in group
                    if str(document.get("source_document_id", ""))
                ],
                "titles": sorted({str(document.get("title", "")) for document in group if str(document.get("title", ""))}),
                "raw_files": sorted({str(document.get("raw_file", "")) for document in group if str(document.get("raw_file", ""))}),
                "review_status": "unreviewed",
            }
        )
    return duplicate_groups


def _document_identity_key(document: dict[str, Any]) -> tuple[str, str] | None:
    for key in ("sha256", "content_sha256", "text_sha256", "raw_file", "url", "title"):
        value = str(document.get(key, "")).strip().lower()
        if value:
            return key, value
    return None


def _is_weak_nominal_link(link: dict[str, Any]) -> bool:
    reasons = set(_list_strings(link.get("reasons")))
    match_kind = str(link.get("match_kind", "")).strip()
    return (
        "capitalized_person_like_name_pattern" in reasons
        or "exact_canonical_name_match" in reasons
        or match_kind in {"canonical_name", "name_form", "alias"}
    ) and "segment_name_match" not in reasons


def _mvp_signal_blockers(
    *,
    document_count: int,
    unique_document_count: int,
    duplicate_groups: list[dict[str, Any]],
    weak_nominal_link_count: int,
    link_count: int,
    claim_count: int,
    profiles_with_links_no_claims: list[dict[str, Any]],
) -> list[str]:
    blockers: list[str] = []
    if document_count == 0:
        blockers.append("Nessun documento collegato al pacchetto MVP.")
    elif duplicate_groups:
        blockers.append(
            f"{document_count - unique_document_count} documenti sembrano duplicati o copie dello stesso contenuto."
        )
    if link_count > 0 and weak_nominal_link_count == link_count:
        blockers.append("Tutti i link persona-documento sono match nominali deboli: serve conferma contestuale.")
    elif weak_nominal_link_count > 0:
        blockers.append(f"{weak_nominal_link_count} link persona-documento sono match nominali deboli.")
    if profiles_with_links_no_claims:
        blockers.append(f"{len(profiles_with_links_no_claims)} profili hanno link candidati ma zero claim.")
    if claim_count == 0 and link_count > 0:
        blockers.append("Nessun claim candidato prodotto nonostante i link documento-persona.")
    if not blockers:
        blockers.append("Segnale MVP leggibile: passare a review queue e decisioni umane.")
    return blockers


def _mvp_signal_next_action(blockers: list[str]) -> str:
    joined = " ".join(blockers)
    if "duplicati" in joined or "copie dello stesso contenuto" in joined:
        return "Revisionare i gruppi duplicati e presentare il pacchetto usando i documenti unici stimati."
    if "match nominali deboli" in joined:
        return "Rafforzare i link con contesto segmentato, fonte dettaglio o documento piu' specifico."
    if "zero claim" in joined or "Nessun claim candidato" in joined:
        return "Revisionare segmentazione, qualita' testo e regole claim sui profili con link ma senza claim."
    return "Preparare review queue e pacchetto Obsidian per revisione storica."


def _claim_funnel_diagnostics_for_summary(
    *,
    claims: list[dict[str, Any]],
    skipped_claim_entities: list[dict[str, Any]],
    source_diagnostics: Any,
) -> dict[str, Any]:
    source = source_diagnostics if isinstance(source_diagnostics, dict) else {}
    counts_by_skip_reason = Counter(
        str(item.get("reason", ""))
        for item in skipped_claim_entities
        if str(item.get("reason", "")).strip()
    )
    counts_by_next_action = Counter(
        str(item.get("recommended_next_action", ""))
        for item in skipped_claim_entities
        if str(item.get("recommended_next_action", "")).strip()
    )
    claims_with_weak_segment = [
        claim for claim in claims if str(claim.get("weak_segment_id", "")).strip()
    ]
    claims_with_chunk_only = [
        claim
        for claim in claims
        if not str(claim.get("weak_segment_id", "")).strip()
        and str(claim.get("chunk_id", "")).strip()
    ]
    skipped_with_candidate_profiles = [
        item for item in skipped_claim_entities if _list_strings(item.get("candidate_profile_ids"))
    ]
    return {
        "@type": "MvpClaimFunnelDiagnostics",
        "source_type": str(source.get("@type", "ClaimFunnelDiagnostics")),
        "funnel_status": str(source.get("funnel_status", "")) or _summary_claim_funnel_status(
            claims=claims,
            skipped=skipped_claim_entities,
        ),
        "claim_count": len(claims),
        "skipped_entity_count": len(skipped_claim_entities),
        "skipped_structured_document_count": _int_value(source.get("skipped_structured_document_count")),
        "claims_with_weak_segment_id_count": len(claims_with_weak_segment),
        "claims_with_chunk_id_only_count": len(claims_with_chunk_only),
        "claims_without_segment_context_count": len(claims) - len(claims_with_weak_segment) - len(claims_with_chunk_only),
        "skipped_with_candidate_profiles_count": len(skipped_with_candidate_profiles),
        "skipped_without_candidate_profiles_count": len(skipped_claim_entities) - len(skipped_with_candidate_profiles),
        "counts_by_skip_reason": dict(sorted(counts_by_skip_reason.items())),
        "counts_by_recommended_next_action": dict(sorted(counts_by_next_action.items())),
        "next_action": _summary_claim_funnel_next_action(
            claims=claims,
            counts_by_skip_reason=counts_by_skip_reason,
            source_next_action=str(source.get("next_action", "")),
        ),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def _summary_claim_funnel_status(*, claims: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> str:
    if claims and skipped:
        return "claims_with_reviewable_skips"
    if claims:
        return "claims_available"
    if skipped:
        return "blocked_with_reviewable_skips"
    return "no_claim_signal"


def _summary_claim_funnel_next_action(
    *,
    claims: list[dict[str, Any]],
    counts_by_skip_reason: Counter[str],
    source_next_action: str,
) -> str:
    if counts_by_skip_reason.get("ambiguous_or_missing_document_person_link", 0):
        return "Rafforzare segmentazione o link documento-persona sui casi ambigui."
    if counts_by_skip_reason.get("unsupported_entity_context", 0):
        return "Revisionare manualmente entita' non mappate a campi claim supportati."
    if source_next_action:
        return source_next_action
    if claims:
        return "Portare claim candidati e blocchi residui in review queue."
    return "Produrre o rafforzare segnali documentali prima dei claim."


def _document_intake_readiness(*, local_run_dir: Path | None, mvp_document_count: int) -> dict[str, Any]:
    if local_run_dir is None:
        return {
            "available": False,
            "local_run_dir": "",
            "mvp_blockers": ["Nessuna run locale collegata al riepilogo MVP."],
            "next_action": "Passare LocalRunDir per spiegare lo stato raw-to-processed.",
        }
    local_document_dir = local_run_dir / "document_analysis"
    input_plan = _load_json_object(local_document_dir / "input_processing_plan.json")
    ocr_report = _load_json_object(local_document_dir / "ocr_batch_report.json")
    text_report = _load_json_object(local_document_dir / "document_text_extraction.json")
    metadata_report = _load_json_object(local_document_dir / "document_metadata_extraction.json")

    input_summary = {
        "available": bool(input_plan),
        "root_dir": str(input_plan.get("root_dir", "")),
        "asset_count": _int_value(input_plan.get("asset_count")),
        "action_counts": _dict_ints(input_plan.get("action_counts")),
        "assets": _list_items(input_plan.get("assets")),
    }
    ocr_summary = {
        "available": bool(ocr_report),
        "summary": _dict_ints(ocr_report.get("summary")),
        "log_file": str(ocr_report.get("log_file", "")),
    }
    text_summary = {
        "available": bool(text_report),
        "document_count": _int_value(text_report.get("document_count")),
        "extracted_count": _int_value(text_report.get("extracted_count")),
        "skipped_count": _int_value(text_report.get("skipped_count")),
    }
    metadata_summary = {
        "available": bool(metadata_report),
        "document_count": _int_value(metadata_report.get("document_count")),
        "documents": _list_items(metadata_report.get("documents")),
    }
    image_ocr_readiness = _image_ocr_readiness(input_plan=input_plan, metadata_report=metadata_report)
    blockers = _document_intake_blockers(
        input_summary=input_summary,
        ocr_summary=ocr_summary,
        text_summary=text_summary,
        metadata_summary=metadata_summary,
        image_ocr_readiness=image_ocr_readiness,
        mvp_document_count=mvp_document_count,
    )
    return {
        "available": True,
        "local_run_dir": str(local_run_dir),
        "local_document_analysis_dir": str(local_document_dir),
        "input_processing_plan": input_summary,
        "ocr_batch": ocr_summary,
        "text_extraction": text_summary,
        "metadata_extraction": metadata_summary,
        "image_ocr_readiness": image_ocr_readiness,
        "mvp_document_count": mvp_document_count,
        "mvp_blockers": blockers,
        "next_action": _document_intake_next_action(blockers),
        "warnings": _list_strings(image_ocr_readiness.get("warnings")),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def _document_intake_blockers(
    *,
    input_summary: dict[str, Any],
    ocr_summary: dict[str, Any],
    text_summary: dict[str, Any],
    metadata_summary: dict[str, Any],
    image_ocr_readiness: dict[str, Any],
    mvp_document_count: int,
) -> list[str]:
    blockers: list[str] = []
    action_counts = input_summary.get("action_counts", {})
    ocr_required = _int_value(action_counts.get("image_ocr_required") if isinstance(action_counts, dict) else 0)
    pdf_required = _int_value(action_counts.get("pdf_text_extraction_required") if isinstance(action_counts, dict) else 0)
    manual_review = _int_value(action_counts.get("manual_review_required") if isinstance(action_counts, dict) else 0)
    if input_summary.get("available") and input_summary.get("asset_count", 0) == 0:
        blockers.append("Nessun asset raw rilevato nella run locale.")
    if ocr_required > 0 and not ocr_summary.get("available"):
        blocking_images = _int_value(image_ocr_readiness.get("blocking_image_count"))
        unknown_images = _int_value(image_ocr_readiness.get("unknown_image_count"))
        priority_images = blocking_images + unknown_images
        if priority_images > 0:
            blockers.append(
                f"{priority_images} immagini richiedono OCR prioritario, ma non esiste un report OCR batch collegato."
            )
    if pdf_required > 0:
        blockers.append(f"{pdf_required} PDF richiedono estrazione testo o revisione manuale.")
    if manual_review > 0:
        blockers.append(f"{manual_review} asset richiedono revisione manuale prima di produrre evidenze.")
    ocr_counts = ocr_summary.get("summary", {})
    if isinstance(ocr_counts, dict) and _int_value(ocr_counts.get("error")) > 0:
        blockers.append(f"{_int_value(ocr_counts.get('error'))} documenti OCR sono in errore.")
    if text_summary.get("available") and text_summary.get("extracted_count", 0) == 0 and metadata_summary.get("document_count", 0) > 0:
        blockers.append("Nessun testo estratto dai documenti metadatati: servono OCR, trascrizione o text extraction.")
    if mvp_document_count == 0:
        blockers.append("Nessun documento raggiunge il riepilogo MVP come base per link o claim candidati.")
    return blockers


def _image_ocr_readiness(*, input_plan: dict[str, Any], metadata_report: dict[str, Any]) -> dict[str, Any]:
    assets = [
        asset
        for asset in _list_items(input_plan.get("assets"))
        if str(asset.get("recommended_action", "")) == "image_ocr_required"
    ]
    metadata_by_document_id: dict[str, dict[str, Any]] = {}
    metadata_by_raw_file: dict[str, dict[str, Any]] = {}
    for item in _list_items(metadata_report.get("documents")):
        document_id = str(item.get("source_document_id", "")).strip()
        raw_file = _normalized_path_key(item.get("raw_file"))
        if document_id:
            metadata_by_document_id[document_id] = item
        if raw_file:
            metadata_by_raw_file[raw_file] = item

    support_images: list[dict[str, str]] = []
    blocking_images: list[dict[str, str]] = []
    unknown_images: list[dict[str, str]] = []
    for asset in assets:
        metadata = _metadata_for_asset(asset, metadata_by_document_id, metadata_by_raw_file)
        item = {
            "source_document_id": str(asset.get("source_document_id", "")),
            "raw_file": str(asset.get("raw_file", "")),
        }
        if not metadata:
            unknown_images.append(item)
            continue
        if _is_false_like(metadata.get("claim_eligible")):
            support_images.append(item)
        else:
            blocking_images.append(item)

    warnings: list[str] = []
    if support_images:
        warnings.append(
            f"{len(support_images)} immagini di supporto claim_eligible=false non bloccano il pacchetto; restano da revisione/OCR se necessario."
        )
    if unknown_images:
        warnings.append(
            f"{len(unknown_images)} immagini richiedono metadata o sidecar piu' chiari prima di degradarle a warning."
        )

    return {
        "@type": "MvpImageOcrReadiness",
        "image_ocr_required_count": len(assets),
        "blocking_image_count": len(blocking_images),
        "support_image_count": len(support_images),
        "unknown_image_count": len(unknown_images),
        "blocking_images": blocking_images[:20],
        "support_images": support_images[:20],
        "unknown_images": unknown_images[:20],
        "warnings": warnings,
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def _metadata_for_asset(
    asset: dict[str, Any],
    metadata_by_document_id: dict[str, dict[str, Any]],
    metadata_by_raw_file: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    document_id = str(asset.get("source_document_id", "")).strip()
    if document_id and document_id in metadata_by_document_id:
        return metadata_by_document_id[document_id]
    raw_file = _normalized_path_key(asset.get("raw_file"))
    if raw_file and raw_file in metadata_by_raw_file:
        return metadata_by_raw_file[raw_file]
    return {}


def _normalized_path_key(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip().casefold()


def _is_false_like(value: Any) -> bool:
    if isinstance(value, bool):
        return value is False
    return str(value).strip().casefold() in {"0", "false", "no", "not_claim_eligible"}


def _document_intake_next_action(blockers: list[str]) -> str:
    joined = " ".join(blockers)
    if "richiedono OCR" in joined or "OCR sono in errore" in joined:
        return "Eseguire o correggere OCR batch sui documenti immagine prioritari."
    if "Nessun testo estratto" in joined:
        return "Produrre testo revisionabile con OCR, trascrizione o estrazione testo locale."
    if "Nessun documento raggiunge" in joined:
        return "Collegare documenti processati a profili pilota e rigenerare la pipeline MVP."
    return "Revisionare link documento-persona e claim candidati."


def _profile_id_from_item(item: dict[str, Any]) -> str:
    return str(item.get("profile_id") or item.get("person_candidate_id") or item.get("person_id") or "")


def _warnings(
    *,
    selected_profile_ids: list[str],
    profiles: list[dict[str, str]],
    documents: list[dict[str, Any]],
    links: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    signal_count: int,
) -> list[str]:
    warnings = [
        "Tutti gli output sono candidati o audit-only: serve revisione umana prima della pubblicazione.",
    ]
    if selected_profile_ids and len(profiles) < len(selected_profile_ids):
        warnings.append("Alcuni ProfileId pilota non sono stati risolti nell'indice profili.")
    if not documents:
        warnings.append("Nessun documento nel perimetro pilota: servono acquisizione o registrazione documentale.")
    if not links:
        warnings.append("Nessun link documento-persona candidato: le schede pilota non sono ancora dimostrabili end-to-end.")
    if not claims:
        if signal_count > 0:
            warnings.append("Nessun claim candidato, ma sono presenti piste documentali da revisionare o segmentare.")
        else:
            warnings.append("Nessun claim candidato: il passo successivo e' migliorare testi, link o regole di estrazione.")
    return warnings


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        if not path.exists() or not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _dict_ints(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _int_value(count) for key, count in value.items()}


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un riepilogo MVP pilota da una run documentale.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--local-run-dir", default="")
    parser.add_argument("--profiles-index", default="")
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    output_json = Path(args.output_json) if args.output_json else run_dir / "document_analysis" / "mvp_pilot_summary.json"
    output_md = Path(args.output_md) if args.output_md else run_dir / "document_analysis" / "mvp_pilot_summary.md"
    payload = build_mvp_pilot_summary(
        run_dir=run_dir,
        local_run_dir=Path(args.local_run_dir) if args.local_run_dir else None,
        profiles_index=Path(args.profiles_index) if args.profiles_index else None,
        profile_ids=args.profile_id,
        output_json=output_json,
        output_md=output_md,
    )
    print(f"Summary MVP pilota: {output_md}")
    print(f"Profili: {payload['profile_count']}")
    print(f"Claim candidati: {payload['candidate_evidence_claim_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
