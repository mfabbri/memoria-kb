from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .candidate_evidence_claims import CandidateEvidenceClaimRecord
from .evidence_store_records import EvidenceStoreRecord
from .mvp_consolidated_review_ledger_markdown import render_mvp_consolidated_review_ledger_markdown
from .review_queue_items import ReviewQueueItemRecord


def build_mvp_consolidated_review_ledger(
    *,
    summary_json: list[Path] | None = None,
    run_dir: list[Path] | None = None,
    evidence_db: Path | None = None,
    evidence_source_run_id: list[str] | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    summary_paths = _resolve_summary_paths(summary_json or [], run_dir or [], allow_empty=evidence_db is not None)
    if not summary_paths and evidence_db is not None and not evidence_source_run_id:
        raise ValueError("Specificare almeno un --evidence-source-run-id quando il ledger usa solo --evidence-db.")
    summaries = [_load_json_object(path) for path in summary_paths]
    profiles_by_id: dict[str, dict[str, Any]] = {}
    source_runs = []
    ledger_source_mode = "summary_fallback"
    if evidence_db is not None and not summary_paths:
        ledger_source_mode = "store_first"
    elif evidence_db is not None:
        ledger_source_mode = "summary_with_store_coverage"

    for path, summary in zip(summary_paths, summaries, strict=False):
        source_run = _source_run(path=path, summary=summary)
        source_runs.append(source_run)
        for profile in _list_items(summary.get("profiles")):
            profile_id = str(profile.get("profile_id", "")).strip()
            if profile_id:
                _profile_record(profiles_by_id, profile_id, profile).setdefault("source_runs", set()).add(source_run["run_dir"])
        for document in _list_items(summary.get("documents")):
            _add_document(profiles_by_id, document=document, summary=summary, source_run=source_run)
        for link in _list_items(summary.get("candidate_document_person_links")):
            _add_link(profiles_by_id, link=link, source_run=source_run)
        for claim in _list_items(summary.get("candidate_evidence_claims")):
            _add_claim(profiles_by_id, claim=claim, source_run=source_run)
        for signal_group in _list_items(summary.get("reviewable_document_signals")):
            _add_signal_group(profiles_by_id, signal_group=signal_group, source_run=source_run)

    _add_link_scoped_candidate_claims(profiles_by_id)

    if ledger_source_mode == "store_first" and evidence_db is not None:
        store_rows = _fetch_evidence_records(evidence_db=evidence_db, source_run_ids=evidence_source_run_id or [])
        _add_store_records(profiles_by_id, rows=store_rows)
        source_runs = _store_source_runs(store_rows)

    profiles = [_finalize_profile(record) for record in profiles_by_id.values()]
    profiles.sort(key=lambda item: (str(item.get("canonical_name", "")).casefold(), str(item.get("profile_id", ""))))
    evidence_store_coverage = _build_evidence_store_coverage(
        evidence_db=evidence_db,
        source_run_ids=evidence_source_run_id or [],
        profiles=profiles,
    )
    warnings = _warnings(summary_paths=summary_paths, profiles=profiles, evidence_store_coverage=evidence_store_coverage)
    ledger = {
        "@type": "MvpConsolidatedReviewLedger",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_curator_review",
        "ledger_source_mode": ledger_source_mode,
        "source_summary_json": [str(path) for path in summary_paths],
        "source_runs": source_runs,
        "source_run_count": len(source_runs),
        "profile_count": len(profiles),
        "document_count": sum(_int_value(profile.get("document_count")) for profile in profiles),
        "candidate_document_person_link_count": sum(_int_value(profile.get("candidate_document_person_link_count")) for profile in profiles),
        "candidate_evidence_claim_count": sum(_int_value(profile.get("candidate_evidence_claim_count")) for profile in profiles),
        "reviewable_document_signal_count": sum(_int_value(profile.get("reviewable_document_signal_count")) for profile in profiles),
        "evidence_store_coverage": evidence_store_coverage,
        "profiles": profiles,
        "warnings": warnings,
        "note": "Preview-only: non modifica profili JSON-LD, non applica decisioni e non promuove claim candidati.",
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_consolidated_review_ledger_markdown(ledger), encoding="utf-8")
    return ledger


def _resolve_summary_paths(summary_json: list[Path], run_dir: list[Path], *, allow_empty: bool = False) -> list[Path]:
    paths: list[Path] = []
    for path in summary_json:
        if path not in paths:
            paths.append(path)
    for directory in run_dir:
        candidate = directory / "document_analysis" / "mvp_pilot_summary.json"
        if candidate not in paths:
            paths.append(candidate)
    if not paths and allow_empty:
        return []
    if not paths:
        raise ValueError("Specificare almeno un --summary-json o --run-dir.")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Summary MVP non trovato: " + ", ".join(missing))
    return paths


def _source_run(*, path: Path, summary: dict[str, Any]) -> dict[str, str]:
    return {
        "summary_json": str(path),
        "run_dir": str(summary.get("run_dir") or path.parent.parent),
        "document_analysis_dir": str(summary.get("document_analysis_dir") or path.parent),
    }


def _profile_record(profiles_by_id: dict[str, dict[str, Any]], profile_id: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    record = profiles_by_id.setdefault(
        profile_id,
        {
            "@type": "MvpConsolidatedReviewLedgerProfile",
            "profile_id": profile_id,
            "canonical_name": "",
            "source_runs": set(),
            "_documents": {},
            "_links": {},
            "_claims": {},
            "_signals": {},
            "_review_items": {},
            "_review_decisions": {},
            "review_status": "unreviewed",
            "publication_status": "not_publishable_without_curator_review",
        },
    )
    if profile:
        record["canonical_name"] = record.get("canonical_name") or str(profile.get("canonical_name") or profile.get("name") or profile_id)
        if profile.get("profile_source_file") and not record.get("profile_source_file"):
            record["profile_source_file"] = str(profile.get("profile_source_file"))
    return record


def _add_document(
    profiles_by_id: dict[str, dict[str, Any]],
    *,
    document: dict[str, Any],
    summary: dict[str, Any],
    source_run: dict[str, str],
) -> None:
    document_id = str(document.get("source_document_id", "")).strip()
    if not document_id:
        return
    profile_ids = set()
    for link in _list_items(summary.get("candidate_document_person_links")):
        if str(link.get("source_document_id", "")).strip() == document_id and str(link.get("profile_id", "")).strip():
            profile_ids.add(str(link.get("profile_id", "")).strip())
    for claim in _list_items(summary.get("candidate_evidence_claims")):
        if str(claim.get("source_document_id", "")).strip() == document_id:
            profile_id = str(claim.get("profile_id") or claim.get("person_candidate_id") or "").strip()
            if profile_id:
                profile_ids.add(profile_id)
    for profile_id in profile_ids:
        record = _profile_record(profiles_by_id, profile_id)
        documents = record["_documents"]
        item = documents.setdefault(document_id, _document_summary(document))
        _append_unique(item.setdefault("source_runs", []), source_run["run_dir"])


def _add_link(profiles_by_id: dict[str, dict[str, Any]], *, link: dict[str, Any], source_run: dict[str, str]) -> None:
    profile_id = str(link.get("profile_id", "")).strip()
    document_id = str(link.get("source_document_id", "")).strip()
    if not profile_id or not document_id:
        return
    record = _profile_record(profiles_by_id, profile_id, {"canonical_name": link.get("canonical_name", "")})
    key = "|".join(
        [
            profile_id,
            document_id,
            str(link.get("weak_segment_id", "")),
            str(link.get("chunk_id", "")),
            str(link.get("match_kind", "")),
        ]
    )
    item = record["_links"].setdefault(key, _link_summary(link))
    _append_unique(item.setdefault("source_runs", []), source_run["run_dir"])


def _add_claim(profiles_by_id: dict[str, dict[str, Any]], *, claim: dict[str, Any], source_run: dict[str, str]) -> None:
    profile_id = str(claim.get("profile_id") or claim.get("person_candidate_id") or "").strip()
    document_id = str(claim.get("source_document_id", "")).strip()
    if not profile_id or not document_id:
        return
    record = _profile_record(profiles_by_id, profile_id)
    key = "|".join(
        [
            profile_id,
            document_id,
            str(claim.get("field", "")),
            _normalized_value(claim),
            str(claim.get("extraction_method", "")),
        ]
    )
    item = record["_claims"].setdefault(key, _claim_summary(claim))
    _append_unique(item.setdefault("source_runs", []), source_run["run_dir"])


def _add_link_scoped_candidate_claims(profiles_by_id: dict[str, dict[str, Any]]) -> None:
    claims_by_document: dict[str, list[dict[str, Any]]] = {}
    for record in profiles_by_id.values():
        for claim in record["_claims"].values():
            document_id = str(claim.get("source_document_id", "")).strip()
            if document_id:
                claims_by_document.setdefault(document_id, []).append(claim)

    for record in profiles_by_id.values():
        profile_id = str(record.get("profile_id", "")).strip()
        if not profile_id:
            continue
        claim_document_ids = {
            str(claim.get("source_document_id", "")).strip()
            for claim in record["_claims"].values()
            if str(claim.get("source_document_id", "")).strip()
        }
        for link in record["_links"].values():
            document_id = str(link.get("source_document_id", "")).strip()
            if not document_id or document_id in claim_document_ids:
                continue
            projected_claims = [
                _project_linked_document_claim(profile_id=profile_id, link=link, claim=claim)
                for claim in claims_by_document.get(document_id, [])
                if str(claim.get("profile_id", "")).strip() != profile_id
                and not str(claim.get("ledger_derivation_status", "")).strip()
            ]
            derived_claims = projected_claims or [_identity_claim_from_link(profile_id=profile_id, link=link)]
            for claim in derived_claims:
                if not claim:
                    continue
                key = "|".join(
                    [
                        profile_id,
                        document_id,
                        str(claim.get("field", "")),
                        _normalized_value(claim),
                        str(claim.get("extraction_method", "")),
                    ]
                )
                record["_claims"].setdefault(key, claim)
                claim_document_ids.add(document_id)


def _project_linked_document_claim(*, profile_id: str, link: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    document_id = str(link.get("source_document_id", "")).strip()
    field = str(claim.get("field", "")).strip()
    value = str(claim.get("value", "")).strip()
    normalized_value = str(claim.get("normalized_value") or value).strip().casefold()
    if not document_id or not field or not value:
        return {}
    source_runs = []
    for run_id in _list_strings(claim.get("source_runs")) + _list_strings(link.get("source_runs")):
        _append_unique(source_runs, run_id)
    return {
        "@id": _derived_claim_id(
            profile_id=profile_id,
            source_document_id=document_id,
            field=field,
            normalized_value=normalized_value,
            method="ledger_standard_projection_from_linked_document_claim",
        ),
        "profile_id": profile_id,
        "source_document_id": document_id,
        "source_id": str(claim.get("source_id") or link.get("source_id") or ""),
        "field": field,
        "value": value,
        "normalized_value": normalized_value,
        "extraction_method": _with_method_suffix(
            str(claim.get("extraction_method", "")),
            "ledger_standard_projection_from_linked_document_claim",
        ),
        "evidence_span": str(claim.get("evidence_span", "")),
        "review_status": "unreviewed",
        "source_runs": source_runs,
        "ledger_derivation_status": "standard_preview_candidate",
        "ledger_derivation_source_profile_id": str(claim.get("profile_id", "")).strip(),
        "ledger_derivation_note": "Claim candidato proiettato sul profilo collegato dal link documento-persona; richiede review.",
    }


def _identity_claim_from_link(*, profile_id: str, link: dict[str, Any]) -> dict[str, Any]:
    document_id = str(link.get("source_document_id", "")).strip()
    value = str(link.get("matched_name") or "").strip()
    normalized_value = value.casefold()
    if not document_id or not value:
        return {}
    return {
        "@id": _derived_claim_id(
            profile_id=profile_id,
            source_document_id=document_id,
            field="identity.canonical_name",
            normalized_value=normalized_value,
            method="ledger_standard_from_candidate_document_person_link",
        ),
        "profile_id": profile_id,
        "source_document_id": document_id,
        "source_id": str(link.get("source_id", "")),
        "field": "identity.canonical_name",
        "value": value,
        "normalized_value": normalized_value,
        "extraction_method": "ledger_standard_from_candidate_document_person_link",
        "evidence_span": f"candidate_document_person_link matched_name: {value}",
        "review_status": "unreviewed",
        "source_runs": _list_strings(link.get("source_runs")),
        "ledger_derivation_status": "standard_preview_candidate",
        "ledger_derivation_note": "Claim candidato di identita' derivato dal link documento-persona; richiede review.",
    }


def _derived_claim_id(*, profile_id: str, source_document_id: str, field: str, normalized_value: str, method: str) -> str:
    digest = hashlib.sha256(f"{profile_id}|{source_document_id}|{field}|{normalized_value}|{method}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-evidence-claim:ledger-standard:{digest}"


def _with_method_suffix(method: str, suffix: str) -> str:
    method = method.strip()
    if not method:
        return suffix
    if method.endswith(f"|{suffix}"):
        return method
    return f"{method}|{suffix}"


def _add_signal_group(profiles_by_id: dict[str, dict[str, Any]], *, signal_group: dict[str, Any], source_run: dict[str, str]) -> None:
    profile_id = str(signal_group.get("profile_id", "")).strip()
    if not profile_id:
        return
    record = _profile_record(profiles_by_id, profile_id, {"canonical_name": signal_group.get("canonical_name", "")})
    for signal in _list_items(signal_group.get("signals")):
        key = "|".join(
            [
                profile_id,
                str(signal.get("source_document_id", "")),
                str(signal.get("signal_type", "")),
                str(signal.get("summary", "")),
            ]
        )
        item = record["_signals"].setdefault(key, _signal_summary(signal))
        _append_unique(item.setdefault("source_runs", []), source_run["run_dir"])


def _finalize_profile(record: dict[str, Any]) -> dict[str, Any]:
    documents = sorted(record.pop("_documents").values(), key=lambda item: str(item.get("source_document_id", "")))
    links = sorted(record.pop("_links").values(), key=lambda item: str(item.get("source_document_id", "")))
    claims = sorted(record.pop("_claims").values(), key=lambda item: (str(item.get("field", "")), str(item.get("value", ""))))
    signals = sorted(record.pop("_signals").values(), key=lambda item: str(item.get("source_document_id", "")))
    review_items = sorted(record.pop("_review_items").values(), key=lambda item: str(item.get("record_id", "")))
    review_decisions = sorted(record.pop("_review_decisions").values(), key=lambda item: str(item.get("record_id", "")))
    record["source_runs"] = sorted(record.get("source_runs", set()))
    record["documents"] = documents
    record["candidate_document_person_links"] = links
    record["candidate_evidence_claims"] = claims
    record["reviewable_document_signals"] = signals
    record["review_items"] = review_items
    record["review_decisions"] = review_decisions
    record["document_count"] = len(documents)
    record["candidate_document_person_link_count"] = len(links)
    record["candidate_evidence_claim_count"] = len(claims)
    record["reviewable_document_signal_count"] = len(signals)
    record["review_item_count"] = len(review_items)
    record["review_decision_count"] = len(review_decisions)
    return record


def _document_summary(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_document_id": str(document.get("source_document_id", "")),
        "source_id": str(document.get("source_id", "")),
        "title": str(document.get("title", "")),
        "url": str(document.get("url", "")),
        "document_class": str(document.get("document_class", "")),
        "quality_status": str(document.get("quality_status", "")),
        "review_status": str(document.get("review_status", "unreviewed")) or "unreviewed",
    }


def _link_summary(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": str(link.get("profile_id", "")),
        "source_document_id": str(link.get("source_document_id", "")),
        "source_id": str(link.get("source_id", "")),
        "matched_name": str(link.get("matched_name", "")),
        "match_kind": str(link.get("match_kind", "")),
        "score": link.get("score", ""),
        "chunk_id": str(link.get("chunk_id", "")),
        "weak_segment_id": str(link.get("weak_segment_id", "")),
        "review_status": str(link.get("review_status", "unreviewed")) or "unreviewed",
    }


def _claim_summary(claim: dict[str, Any]) -> dict[str, Any]:
    record = CandidateEvidenceClaimRecord.from_payload(claim)
    return {
        "@id": record.claim_id,
        "profile_id": record.effective_profile_id,
        "source_document_id": record.source_document_id,
        "source_id": record.source_id,
        "field": record.field,
        "value": record.value,
        "normalized_value": _normalized_value(claim),
        "extraction_method": record.extraction_method,
        "evidence_span": record.evidence_span or record.context,
        "review_status": record.review_status or "unreviewed",
    }


def _signal_summary(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_type": str(signal.get("signal_type", "")),
        "source_document_id": str(signal.get("source_document_id", "")),
        "summary": str(signal.get("summary", "")),
        "next_action": str(signal.get("next_action", "")),
        "review_status": str(signal.get("review_status", "unreviewed")) or "unreviewed",
    }


def _add_store_records(profiles_by_id: dict[str, dict[str, Any]], *, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        store_record = EvidenceStoreRecord.from_row(row)
        source_document_id = store_record.effective_source_document_id
        for profile_id in store_record.profile_ids():
            scoped_payload = store_record.scoped_payload(profile_id=profile_id)
            record = _profile_record(
                profiles_by_id,
                profile_id,
                {"canonical_name": scoped_payload.get("canonical_name") or scoped_payload.get("person_name") or ""},
            )
            record.setdefault("source_runs", set()).add(store_record.source_run_id)
            if source_document_id:
                document = record["_documents"].setdefault(source_document_id, _store_document_summary(scoped_payload, store_record=store_record))
                _append_store_provenance(document, store_record=store_record)
            if store_record.record_kind == "candidate_document_person_link":
                key = store_record.store_key(profile_id, source_document_id, scoped_payload.get("match_kind", ""))
                item = record["_links"].setdefault(key, _link_summary(scoped_payload))
                _append_store_provenance(item, store_record=store_record)
            elif store_record.record_kind == "candidate_evidence_claim":
                claim_record = CandidateEvidenceClaimRecord.from_payload(scoped_payload)
                key = store_record.store_key(profile_id, source_document_id, claim_record.field, _normalized_value(scoped_payload))
                item = record["_claims"].setdefault(key, _claim_summary(scoped_payload))
                _append_store_provenance(item, store_record=store_record)
            elif store_record.record_kind in {"reviewable_document_signal", "skipped_candidate_claim", "extracted_entity"}:
                signal = _store_signal_summary(scoped_payload, kind=store_record.record_kind, source_document_id=source_document_id)
                key = store_record.store_key(profile_id, source_document_id, signal.get("signal_type", ""), signal.get("summary", ""))
                item = record["_signals"].setdefault(key, signal)
                _append_store_provenance(item, store_record=store_record)
            elif store_record.record_kind == "review_queue_item":
                key = store_record.store_key(profile_id, source_document_id, scoped_payload.get("item_id", ""))
                item = record["_review_items"].setdefault(key, _store_review_item_summary(scoped_payload, store_record=store_record))
                _append_store_provenance(item, store_record=store_record)
            elif store_record.record_kind in {"review_decision", "historical_review_decision"}:
                key = store_record.store_key(profile_id, source_document_id, scoped_payload.get("decision_id", ""), scoped_payload.get("item_id", ""))
                item = record["_review_decisions"].setdefault(key, _store_review_decision_summary(scoped_payload, store_record=store_record))
                _append_store_provenance(item, store_record=store_record)


def _store_source_runs(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    runs: dict[str, dict[str, str]] = {}
    for row in rows:
        source_run_id = str(row.get("source_run_id", "")).strip()
        if not source_run_id:
            continue
        runs.setdefault(source_run_id, {"run_dir": source_run_id, "summary_json": "", "document_analysis_dir": ""})
    return [runs[key] for key in sorted(runs)]


def _store_document_summary(payload: dict[str, Any], *, store_record: EvidenceStoreRecord) -> dict[str, Any]:
    source_document_id = store_record.effective_source_document_id
    return {
        "source_document_id": source_document_id,
        "source_id": str(payload.get("source_id", "")),
        "title": str(payload.get("title") or payload.get("source_document_title") or source_document_id),
        "url": str(payload.get("url", "")),
        "document_class": str(payload.get("document_class", "")),
        "quality_status": str(payload.get("quality_status", "")),
        "review_status": str(store_record.review_status or payload.get("review_status") or "unreviewed"),
    }


def _store_signal_summary(payload: dict[str, Any], *, kind: str, source_document_id: str) -> dict[str, Any]:
    return {
        "signal_type": str(payload.get("signal_type") or kind),
        "source_document_id": source_document_id,
        "summary": str(payload.get("summary") or payload.get("reason") or payload.get("value") or payload.get("@type") or kind),
        "next_action": str(payload.get("next_action", "")),
        "review_status": str(payload.get("review_status", "unreviewed")) or "unreviewed",
    }


def _store_review_item_summary(payload: dict[str, Any], *, store_record: EvidenceStoreRecord) -> dict[str, Any]:
    item = ReviewQueueItemRecord.from_payload(payload)
    return {
        "record_id": store_record.record_id,
        "item_id": item.item_id,
        "subject_kind": item.subject_kind,
        "source_document_id": store_record.effective_source_document_id,
        "question": item.question or str(payload.get("summary") or ""),
        "review_status": str(store_record.review_status or payload.get("review_status") or "unreviewed"),
    }


def _store_review_decision_summary(payload: dict[str, Any], *, store_record: EvidenceStoreRecord) -> dict[str, Any]:
    decision_status = str(payload.get("decision_status", "")).strip()
    return {
        "record_id": store_record.record_id,
        "decision_id": str(payload.get("decision_id", "")),
        "item_id": str(payload.get("item_id", "")),
        "selected_action": str(payload.get("selected_action", "")),
        "decision_status": decision_status,
        "reviewer": str(payload.get("reviewer", "")),
        "reviewed_at": str(payload.get("reviewed_at", "")),
        "source_document_id": store_record.effective_source_document_id,
        "review_status": decision_status or str(store_record.review_status or payload.get("review_status") or "pending"),
    }


def _append_store_provenance(item: dict[str, Any], *, store_record: EvidenceStoreRecord) -> None:
    _append_unique(item.setdefault("record_ids", []), store_record.record_id)
    _append_unique(item.setdefault("source_run_ids", []), store_record.source_run_id)
    _append_unique(item.setdefault("payload_hashes", []), store_record.payload_hash)


def _build_evidence_store_coverage(
    *,
    evidence_db: Path | None,
    source_run_ids: list[str],
    profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    if evidence_db is None:
        return {"enabled": False}
    coverage = {
        "enabled": True,
        "db": str(evidence_db),
        "source_run_ids": sorted({value for value in source_run_ids if value}),
        "record_count": 0,
        "profiles_with_records_count": 0,
        "unscoped_record_count": 0,
        "workflow_unscoped_record_count": 0,
        "by_kind": {},
        "by_review_status": {},
    }
    if not evidence_db.is_file():
        coverage["warning"] = f"Evidence DB non trovato: {evidence_db}"
        return coverage
    rows = _fetch_evidence_records(evidence_db=evidence_db, source_run_ids=coverage["source_run_ids"])
    profile_by_id = {str(profile.get("profile_id", "")).strip(): profile for profile in profiles}
    profile_coverage: dict[str, dict[str, Any]] = {}
    for row in rows:
        store_record = EvidenceStoreRecord.from_row(row)
        kind = store_record.record_kind
        status = store_record.review_status
        profile_ids = store_record.profile_ids()
        source_document_id = store_record.effective_source_document_id
        subject_kind = store_record.subject_kind
        coverage["record_count"] += 1
        _increment(coverage["by_kind"], kind)
        _increment(coverage["by_review_status"], status)
        kind_bucket = coverage.setdefault("_kind_buckets", {}).setdefault(
            kind,
            {"total": 0, "with_subject": 0, "with_source_document": 0, "workflow_unscoped": 0},
        )
        kind_bucket["total"] += 1
        if profile_ids:
            kind_bucket["with_subject"] += 1
        if source_document_id:
            kind_bucket["with_source_document"] += 1
        if subject_kind == "workflow" and not profile_ids:
            kind_bucket["workflow_unscoped"] += 1
            coverage["workflow_unscoped_record_count"] += 1
        if not profile_ids:
            coverage["unscoped_record_count"] += 1
        for profile_id in profile_ids:
            profile_bucket = profile_coverage.setdefault(
                profile_id,
                {"record_count": 0, "source_document_ids": set(), "by_kind": {}, "by_review_status": {}},
            )
            profile_bucket["record_count"] += 1
            if source_document_id:
                profile_bucket["source_document_ids"].add(source_document_id)
            _increment(profile_bucket["by_kind"], kind)
            _increment(profile_bucket["by_review_status"], status)
    coverage["by_kind"] = dict(sorted(coverage.pop("_kind_buckets", {}).items()))
    coverage["profiles_with_records_count"] = len(profile_coverage)
    for profile_id, profile in profile_by_id.items():
        bucket = profile_coverage.get(profile_id)
        if not bucket:
            continue
        profile["evidence_store_coverage"] = {
            "record_count": bucket["record_count"],
            "source_document_count": len(bucket["source_document_ids"]),
            "by_kind": dict(sorted(bucket["by_kind"].items())),
            "by_review_status": dict(sorted(bucket["by_review_status"].items())),
        }
    return coverage


def _fetch_evidence_records(*, evidence_db: Path, source_run_ids: list[str]) -> list[dict[str, Any]]:
    connection = sqlite3.connect(evidence_db)
    connection.row_factory = sqlite3.Row
    try:
        if source_run_ids:
            placeholders = ",".join("?" for _ in source_run_ids)
            query = f"""
                SELECT record_id, source_run_id, record_kind, subject_id, source_document_id,
                       review_status, payload_hash, payload_json
                FROM evidence_records
                WHERE source_run_id IN ({placeholders})
                ORDER BY source_run_id ASC, record_kind ASC, record_id ASC
            """
            rows = connection.execute(query, tuple(source_run_ids)).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT record_id, source_run_id, record_kind, subject_id, source_document_id,
                       review_status, payload_hash, payload_json
                FROM evidence_records
                ORDER BY source_run_id ASC, record_kind ASC, record_id ASC
                """
            ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def _warnings(
    *,
    summary_paths: list[Path],
    profiles: list[dict[str, Any]],
    evidence_store_coverage: dict[str, Any] | None = None,
) -> list[str]:
    warnings = []
    if len(summary_paths) == 1:
        warnings.append("Ledger costruito da una sola run: utile come output stabile, ma non ancora cumulativo.")
    if not profiles:
        warnings.append("Nessun profilo consolidato dai summary indicati.")
    coverage = evidence_store_coverage or {}
    if coverage.get("warning"):
        warnings.append(str(coverage["warning"]))
    if coverage.get("enabled") and coverage.get("record_count", 0) and not coverage.get("profiles_with_records_count", 0):
        warnings.append("Evidence store collegato, ma nessun record importato e' associato ai profili del ledger.")
    if (
        coverage.get("enabled")
        and coverage.get("record_count", 0) > 0
        and coverage.get("record_count", 0) == coverage.get("workflow_unscoped_record_count", -1)
    ):
        warnings.append("Evidence store contiene solo record workflow non scopiati per il filtro indicato.")
    return warnings


def _normalized_value(claim: dict[str, Any]) -> str:
    return str(claim.get("normalized_value") or claim.get("value") or "").strip().casefold()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _increment(counts: dict[str, int], key: str) -> None:
    key = key or "unknown"
    counts[key] = counts.get(key, 0) + 1


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Costruisce un Consolidated Review Ledger MVP preview-only.")
    parser.add_argument("--summary-json", action="append", default=[], help="Path a mvp_pilot_summary.json. Ripetibile.")
    parser.add_argument("--run-dir", action="append", default=[], help="Directory run pipeline con document_analysis/mvp_pilot_summary.json. Ripetibile.")
    parser.add_argument("--evidence-db", default="", help="Database SQLite evidence store da leggere in sola lettura.")
    parser.add_argument("--evidence-source-run-id", action="append", default=[], help="Filtra record evidence store per source_run_id. Ripetibile.")
    parser.add_argument("--output-json", default="", help="Path output JSON.")
    parser.add_argument("--output-md", default="", help="Path output Markdown.")
    args = parser.parse_args()

    ledger = build_mvp_consolidated_review_ledger(
        summary_json=[Path(value) for value in args.summary_json],
        run_dir=[Path(value) for value in args.run_dir],
        evidence_db=Path(args.evidence_db) if args.evidence_db else None,
        evidence_source_run_id=args.evidence_source_run_id,
        output_json=Path(args.output_json) if args.output_json else None,
        output_md=Path(args.output_md) if args.output_md else None,
    )
    if args.output_json:
        print(f"Consolidated Review Ledger MVP JSON scritto in {args.output_json}")
    if args.output_md:
        print(f"Consolidated Review Ledger MVP Markdown scritto in {args.output_md}")
    if not args.output_json and not args.output_md:
        print(json.dumps(ledger, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
