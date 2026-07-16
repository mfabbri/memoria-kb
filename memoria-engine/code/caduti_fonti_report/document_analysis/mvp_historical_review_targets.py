from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .evidence_store_records import EvidenceStoreRecord
from .preview_payloads import (
    dict_object,
    list_items,
    list_strings,
    load_optional_json_object,
    write_json,
    write_markdown,
)
from .mvp_historical_review_targets_markdown import render_mvp_historical_review_targets_markdown
from .review_queue_items import ReviewQueueItemRecord

DEFAULT_PILOT_PROFILE_IDS = [
    "person:purocielo:andreoli-dino",
    "person:purocielo:balboni-william",
    "person:purocielo:bendini-ateo",
]

HISTORICAL_ITEM_TYPES = {
    "person_document_link_review",
    "candidate_claim_review",
    "date_entity_review",
    "place_entity_review",
    "event_context_review",
    "document_signal_review",
}

HISTORICAL_DECISION_TYPES = {
    "candidate_link",
    "candidate_claim",
    "document_signal",
}

HISTORICAL_SUBJECT_KINDS = {
    "person",
    "claim",
    "date",
    "place",
    "event_context",
    "document_signal",
}


def build_mvp_historical_review_targets(
    *,
    review_queue_json: Path | None = None,
    review_session_json: Path | None = None,
    evidence_db: Path | None = None,
    evidence_source_run_id: list[str] | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
    limit: int = 10,
    preferred_profile_ids: list[str] | None = None,
) -> dict[str, Any]:
    if evidence_db is None and (review_queue_json is None or not review_queue_json.exists() or not review_queue_json.is_file()):
        raise FileNotFoundError(f"Review queue non trovata: {review_queue_json}")
    if evidence_db is not None and not evidence_db.is_file():
        raise FileNotFoundError(f"Evidence DB non trovato: {evidence_db}")
    if evidence_db is not None and not evidence_source_run_id:
        raise ValueError("Specificare almeno un evidence_source_run_id quando si usa evidence_db.")
    queue = load_optional_json_object(review_queue_json)
    session = load_optional_json_object(review_session_json)
    preferred_ids = preferred_profile_ids or DEFAULT_PILOT_PROFILE_IDS
    source_mode = "evidence_store" if evidence_db is not None else "review_queue"
    if evidence_db is not None:
        records = _fetch_evidence_records(evidence_db=evidence_db, source_run_ids=evidence_source_run_id or [])
        targets = _select_store_targets(records=records, preferred_profile_ids=preferred_ids, limit=limit)
    else:
        targets = _select_targets(
            queue=list_items(queue.get("items")),
            session=session,
            preferred_profile_ids=preferred_ids,
            limit=limit,
        )
    payload: dict[str, Any] = {
        "@type": "MvpHistoricalReviewTargets",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_mode": source_mode,
        "source_review_queue_json": str(review_queue_json or ""),
        "source_review_session_json": str(review_session_json or ""),
        "source_evidence_db": str(evidence_db or ""),
        "source_run_ids": sorted(evidence_source_run_id or []),
        "review_status": "pending_historian_review",
        "publication_status": "not_publishable_without_human_review",
        "preview_only": True,
        "target_count": len(targets),
        "preferred_profile_ids": preferred_ids,
        "targets": targets,
        "counts_by_item_type": dict(Counter(str(target.get("item_type", "")) for target in targets)),
        "counts_by_profile": dict(Counter(str(target.get("profile_id", "")) for target in targets)),
        "safety_notes": [
            "I target sono derivati preview-only dalla review queue o dallo evidence store.",
            "Nessun target crea fatti verificati, ProfilePatch o modifiche ai profili JSON-LD.",
            "Le decisioni vanno compilate e validate con workflow espliciti separati.",
        ],
    }
    if output_json is not None:
        write_json(output_json, payload)
    if output_md is not None:
        write_markdown(output_md, render_mvp_historical_review_targets_markdown(payload))
    return payload


def _select_targets(
    *,
    queue: list[dict[str, Any]],
    session: dict[str, Any],
    preferred_profile_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    profile_status_by_id = _profile_status_by_id(session)
    historical_items = [item for item in queue if _is_historical_item(item)]
    historical_items.sort(key=lambda item: _target_sort_key(item, preferred_profile_ids=preferred_profile_ids))
    selected = _balanced_target_items(
        historical_items=historical_items,
        preferred_profile_ids=preferred_profile_ids,
        limit=limit,
    )
    return [
        _target_from_item(item, sequence=index, profile_status_by_id=profile_status_by_id)
        for index, item in enumerate(selected, start=1)
    ]


def _select_store_targets(
    *,
    records: list[dict[str, Any]],
    preferred_profile_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    decisions_by_item_id = _historical_decisions_by_item_id(records)
    items = []
    for record in records:
        store_record = EvidenceStoreRecord.from_row(record)
        if store_record.record_kind != "review_queue_item":
            continue
        payload = store_record.payload
        if not _is_historical_item(payload):
            continue
        profile_id = store_record.primary_profile_id()
        source_document_id = store_record.effective_source_document_id
        if not profile_id or not source_document_id:
            continue
        item = store_record.scoped_payload(profile_id=profile_id)
        item["_store_record_id"] = store_record.record_id
        item["_store_source_run_id"] = store_record.source_run_id
        item["_store_payload_hash"] = store_record.payload_hash
        item["_current_decision"] = _current_decision_for_item(item=item, decisions_by_item_id=decisions_by_item_id)
        items.append(item)
    items.sort(key=lambda item: _target_sort_key(item, preferred_profile_ids=preferred_profile_ids))
    selected = _balanced_target_items(historical_items=items, preferred_profile_ids=preferred_profile_ids, limit=limit)
    return [_target_from_store_item(item, sequence=index) for index, item in enumerate(selected, start=1)]


def _historical_decisions_by_item_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    decisions = {}
    for record in records:
        store_record = EvidenceStoreRecord.from_row(record)
        if store_record.record_kind != "historical_review_decision":
            continue
        payload = store_record.payload
        decision = {
            "record_id": store_record.record_id,
            "selected_action": str(payload.get("selected_action", "")),
            "decision_status": str(payload.get("decision_status", "")),
            "reviewer": str(payload.get("reviewer", "")),
            "reviewed_at": str(payload.get("reviewed_at", "")),
        }
        for key in _decision_match_keys(payload):
            decisions.setdefault(key, decision)
    return decisions


def _current_decision_for_item(*, item: dict[str, Any], decisions_by_item_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for key in _decision_match_keys(item):
        decision = decisions_by_item_id.get(key)
        if decision:
            return decision
    return {}


def _decision_match_keys(payload: dict[str, Any]) -> list[str]:
    keys = []
    for field in ("item_id", "source_item_id"):
        value = str(payload.get(field, "")).strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def _balanced_target_items(
    *,
    historical_items: list[dict[str, Any]],
    preferred_profile_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    if limit == 0:
        return historical_items
    max_items = max(limit, 0)
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    for profile_id in preferred_profile_ids:
        if len(selected) >= max_items:
            return selected
        for item in historical_items:
            if id(item) in selected_ids:
                continue
            if str(item.get("profile_id", "")) == profile_id:
                selected.append(item)
                selected_ids.add(id(item))
                break
    for item in historical_items:
        if len(selected) >= max_items:
            break
        if id(item) in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(id(item))
    return selected


def _is_historical_item(item: dict[str, Any]) -> bool:
    record = ReviewQueueItemRecord.from_payload(item)
    if record.subject_kind == "workflow":
        return False
    if record.item_type in HISTORICAL_ITEM_TYPES:
        return True
    if str(item.get("decision_type", "")) in HISTORICAL_DECISION_TYPES:
        return True
    return record.subject_kind in HISTORICAL_SUBJECT_KINDS


def _target_from_item(
    item: dict[str, Any],
    *,
    sequence: int,
    profile_status_by_id: dict[str, str],
) -> dict[str, Any]:
    record = ReviewQueueItemRecord.from_payload(item)
    profile_id = record.profile_id
    source_document_id = record.source_document_id
    item_id = record.item_id
    provenance = [
        f"review_queue_item={item_id}",
        f"source_item_id={record.source_item_id}",
    ]
    if source_document_id:
        provenance.append(f"source_document_id={source_document_id}")
    if profile_status_by_id.get(profile_id):
        provenance.append(f"model_card_review_status={profile_status_by_id[profile_id]}")
    return {
        "@type": "HistoricalReviewTarget",
        "target_id": f"historical-review-target:{sequence:04d}",
        "source_review_queue_item_id": item_id,
        "profile_id": profile_id,
        "canonical_name": record.canonical_name,
        "source_document_id": source_document_id,
        "item_type": record.item_type,
        "subject_kind": record.subject_kind,
        "historian_question": record.question,
        "context": record.context,
        "allowed_decisions": list(record.allowed_decisions),
        "current_selected_action": "",
        "current_decision_status": "",
        "review_status": "pending",
        "publication_status": "not_publishable_without_human_review",
        "provenance": provenance,
        "safety_note": "Compilare la decisione non modifica profili JSON-LD, claim verificati o dati storici canonici.",
    }


def _target_from_store_item(item: dict[str, Any], *, sequence: int) -> dict[str, Any]:
    target = _target_from_item(item, sequence=sequence, profile_status_by_id={})
    decision = dict_object(item.get("_current_decision"))
    provenance = list_strings(target.get("provenance"))
    provenance.extend(
        [
            f"record_id={item.get('_store_record_id', '')}",
            f"source_run_id={item.get('_store_source_run_id', '')}",
            f"payload_hash={item.get('_store_payload_hash', '')}",
        ]
    )
    if decision:
        provenance.append(f"historical_review_decision_record_id={decision.get('record_id', '')}")
    target["source_record_id"] = str(item.get("_store_record_id", ""))
    target["source_run_id"] = str(item.get("_store_source_run_id", ""))
    target["payload_hash"] = str(item.get("_store_payload_hash", ""))
    target["current_selected_action"] = str(decision.get("selected_action", ""))
    target["current_decision_status"] = str(decision.get("decision_status", ""))
    target["current_decision_record_id"] = str(decision.get("record_id", ""))
    target["current_reviewer"] = str(decision.get("reviewer", ""))
    target["current_reviewed_at"] = str(decision.get("reviewed_at", ""))
    target["review_status"] = "decided" if decision else "pending"
    target["provenance"] = provenance
    return target


def _target_sort_key(item: dict[str, Any], *, preferred_profile_ids: list[str]) -> tuple[int, int, int, str]:
    profile_id = str(item.get("profile_id", ""))
    try:
        profile_rank = preferred_profile_ids.index(profile_id)
    except ValueError:
        profile_rank = len(preferred_profile_ids)
    priority_rank = {"high": 0, "medium": 1, "low": 2}.get(str(item.get("priority", "")), 3)
    type_rank = {
        "person_document_link_review": 0,
        "candidate_claim_review": 1,
        "date_entity_review": 1,
        "place_entity_review": 1,
        "event_context_review": 1,
        "document_signal_review": 2,
    }.get(str(item.get("item_type", "")), 3)
    return (profile_rank, priority_rank, type_rank, str(item.get("item_id", "")))


def _profile_status_by_id(session: dict[str, Any]) -> dict[str, str]:
    return {
        str(profile.get("profile_id", "")): str(profile.get("model_card_review_status", ""))
        for profile in list_items(session.get("profiles"))
        if str(profile.get("profile_id", ""))
    }


def _fetch_evidence_records(*, evidence_db: Path, source_run_ids: list[str]) -> list[dict[str, Any]]:
    uri = evidence_db.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in source_run_ids)
        rows = connection.execute(
            f"""
            SELECT record_id, source_run_id, record_kind, subject_id,
                   source_document_id, review_status, payload_hash, payload_json
            FROM evidence_records
            WHERE source_run_id IN ({placeholders})
            ORDER BY source_run_id ASC, record_kind ASC, record_id ASC
            """,
            tuple(source_run_ids),
        ).fetchall()
    return [dict(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera target storici revisionabili MVP da review queue.")
    parser.add_argument("--review-queue-json", default="")
    parser.add_argument("--review-session-json", default="")
    parser.add_argument("--evidence-db", default="")
    parser.add_argument("--evidence-source-run-id", action="append", default=[])
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preferred-profile-id", action="append", default=[])
    args = parser.parse_args()

    try:
        targets = build_mvp_historical_review_targets(
            review_queue_json=Path(args.review_queue_json) if args.review_queue_json else None,
            review_session_json=Path(args.review_session_json) if args.review_session_json else None,
            evidence_db=Path(args.evidence_db) if args.evidence_db else None,
            evidence_source_run_id=args.evidence_source_run_id,
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            limit=args.limit,
            preferred_profile_ids=args.preferred_profile_id or None,
        )
    except FileNotFoundError as exc:
        print(str(exc))
        return 2
    print(f"Target storici revisionabili MVP: {args.output_md}")
    print(f"Target: {targets['target_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
