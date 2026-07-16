from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caduti_fonti_report.document_analysis.mvp_review_queue_markdown import render_mvp_review_queue_markdown

DEFAULT_ALLOWED_DECISIONS = [
    "confirm",
    "reject_false_positive",
    "uncertain",
    "request_more_sources",
    "accept_for_search",
    "needs_better_ocr",
    "needs_human_transcription",
]

DATE_HINT_PATTERN = re.compile(r"\b\d{1,2}\s+\w+\s+\d{4}\b|\b\d{4}\b")


def build_mvp_review_queue(
    *,
    summary_json: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
    decisions_template_json: Path | None = None,
) -> dict[str, Any]:
    if not summary_json.exists() or not summary_json.is_file():
        raise FileNotFoundError(f"Summary MVP non trovato: {summary_json}")
    payload = _load_json_object(summary_json)
    items = _build_items(payload)
    decisions_template = _build_decisions_template(items)
    queue: dict[str, Any] = {
        "@type": "HistorianReviewQueue",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_summary_json": str(summary_json),
        "source_summary_type": str(payload.get("@type", "")),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "item_count": len(items),
        "items": items,
        "decision_template": decisions_template,
        "warnings": [
            "La queue e' un derivato preview-only per revisione umana.",
            "Nessun item promuove claim candidati a fatti verificati.",
            "Nessun profilo JSON-LD reale viene modificato.",
        ],
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_review_queue_markdown(queue), encoding="utf-8")
    if decisions_template_json is not None:
        decisions_template_json.parent.mkdir(parents=True, exist_ok=True)
        decisions_template_json.write_text(json.dumps(decisions_template, ensure_ascii=False, indent=2), encoding="utf-8")
    return queue


def _build_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    profiles_by_id = {
        str(profile.get("profile_id", "")): profile
        for profile in _list_items(payload.get("profiles"))
        if str(profile.get("profile_id", ""))
    }
    items: list[dict[str, Any]] = []
    sequence = 1
    for readiness in _list_items(payload.get("profile_readiness")):
        status = str(readiness.get("readiness_status", ""))
        if status == "ready_for_review":
            continue
        profile_id = str(readiness.get("profile_id", ""))
        items.append(
            _queue_item(
                sequence=sequence,
                item_type="profile_readiness_review",
                subject_kind="workflow",
                question=str(readiness.get("next_action") or "Completare la scheda pilota prima della revisione."),
                decision_type="workflow_triage",
                allowed_decisions=_decisions_for_readiness(status),
                priority="high" if status == "needs_documents" else "medium",
                risk="medium",
                profile_id=profile_id,
                canonical_name=str(readiness.get("canonical_name") or profiles_by_id.get(profile_id, {}).get("canonical_name", "")),
                source_document_id="",
                source_item_id=profile_id,
                context=f"Stato scheda pilota: {status}",
                reasons=[f"readiness_status={status}"],
            )
        )
        sequence += 1

    for link in _list_items(payload.get("candidate_document_person_links")):
        profile_id = _profile_id_from_item(link)
        document_id = str(link.get("source_document_id", ""))
        items.append(
            _queue_item(
                sequence=sequence,
                item_type="person_document_link_review",
                subject_kind="person",
                question="Questo documento riguarda davvero la persona indicata?",
                decision_type="candidate_link",
                allowed_decisions=["confirm", "reject_false_positive", "uncertain", "request_more_sources"],
                priority="high",
                risk="medium",
                profile_id=profile_id,
                canonical_name=str(profiles_by_id.get(profile_id, {}).get("canonical_name", "")),
                source_document_id=document_id,
                source_item_id=str(link.get("@id") or link.get("link_id") or f"{profile_id}:{document_id}"),
                context=str(link.get("context") or link.get("evidence_span") or ""),
                reasons=_link_reasons(link),
                raw_file=str(link.get("raw_file", "")),
                metadata_file=str(link.get("metadata_file", "")),
            )
        )
        sequence += 1

    for claim in _list_items(payload.get("candidate_evidence_claims")):
        profile_id = _profile_id_from_item(claim)
        field = str(claim.get("field", ""))
        value = str(claim.get("value", ""))
        subject_kind = _subject_kind_for_claim_field(field)
        items.append(
            _queue_item(
                sequence=sequence,
                item_type=_item_type_for_subject_kind(subject_kind, "candidate_claim_review"),
                subject_kind=subject_kind,
                question=_question_for_claim(subject_kind=subject_kind, field=field, value=value),
                decision_type="candidate_claim",
                allowed_decisions=["confirm", "reject_false_positive", "uncertain", "request_more_sources", "needs_better_ocr"],
                priority="high",
                risk="high",
                profile_id=profile_id,
                canonical_name=str(profiles_by_id.get(profile_id, {}).get("canonical_name", "")),
                source_document_id=str(claim.get("source_document_id", "")),
                source_item_id=str(claim.get("@id") or claim.get("claim_id") or f"{profile_id}:{field}:{value}"),
                context=str(claim.get("evidence_span") or claim.get("context") or ""),
                reasons=[f"field={field}", "candidate_claim_unreviewed"],
                candidate={"field": field, "value": value},
                raw_file=str(claim.get("raw_file", "")),
                metadata_file=str(claim.get("metadata_file", "")),
            )
        )
        sequence += 1

    for group in _list_items(payload.get("reviewable_document_signals")):
        profile_id = str(group.get("profile_id", ""))
        canonical_name = str(group.get("canonical_name") or profiles_by_id.get(profile_id, {}).get("canonical_name", ""))
        for signal in _list_items(group.get("signals")):
            signal_type = str(signal.get("signal_type", ""))
            subject_kind = _subject_kind_for_signal(signal)
            items.append(
                _queue_item(
                    sequence=sequence,
                    item_type=_item_type_for_subject_kind(subject_kind, "document_signal_review"),
                    subject_kind=subject_kind,
                    question=_question_for_signal(subject_kind=subject_kind, signal_type=signal_type),
                    decision_type="document_signal",
                    allowed_decisions=["confirm", "reject_false_positive", "uncertain", "request_more_sources", "needs_better_ocr", "needs_human_transcription"],
                    priority="medium",
                    risk="medium",
                    profile_id=profile_id,
                    canonical_name=canonical_name,
                    source_document_id=str(signal.get("source_document_id", "")),
                    source_item_id=str(signal.get("source_item_id") or f"{profile_id}:{signal_type}:{sequence}"),
                    context=str(signal.get("context", "")),
                    reasons=[f"signal_type={signal_type}", *_list_strings(signal.get("reasons"))],
                    candidate={"field": "document_signal", "value": str(signal.get("value") or signal_type)},
                    raw_file=str(signal.get("raw_file", "")),
                    metadata_file=str(signal.get("metadata_file", "")),
                )
            )
            sequence += 1

    for warning in _list_strings(payload.get("warnings")):
        items.append(
            _queue_item(
                sequence=sequence,
                item_type="mvp_warning_review",
                subject_kind="workflow",
                question=warning,
                decision_type="workflow_triage",
                allowed_decisions=["uncertain", "request_more_sources", "accept_for_search", "needs_better_ocr", "needs_human_transcription"],
                priority="medium",
                risk="low",
                profile_id="",
                canonical_name="",
                source_document_id="",
                source_item_id=f"warning:{sequence}",
                context=warning,
                reasons=["mvp_summary_warning"],
            )
        )
        sequence += 1
    return items


def _queue_item(
    *,
    sequence: int,
    item_type: str,
    subject_kind: str,
    question: str,
    decision_type: str,
    allowed_decisions: list[str],
    priority: str,
    risk: str,
    profile_id: str,
    canonical_name: str,
    source_document_id: str,
    source_item_id: str,
    context: str,
    reasons: list[str],
    candidate: dict[str, str] | None = None,
    raw_file: str = "",
    metadata_file: str = "",
) -> dict[str, Any]:
    document_reference = _document_reference(source_document_id=source_document_id, raw_file=raw_file, metadata_file=metadata_file)
    item: dict[str, Any] = {
        "@type": "ReviewQueueItem",
        "item_id": f"mvp-review-item:{sequence:04d}",
        "item_type": item_type,
        "subject_kind": subject_kind,
        "question": question,
        "decision_type": decision_type,
        "allowed_decisions": allowed_decisions,
        "priority": priority,
        "risk": risk,
        "profile_id": profile_id,
        "canonical_name": canonical_name,
        "source_document_id": source_document_id,
        "raw_file": document_reference["raw_file"],
        "metadata_file": document_reference["metadata_file"],
        "document_reference_note": document_reference["note"],
        "source_item_id": source_item_id,
        "context": context,
        "reasons": reasons,
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }
    if candidate:
        item["candidate"] = candidate
    return item


def _document_reference(*, source_document_id: str, raw_file: str = "", metadata_file: str = "") -> dict[str, str]:
    source_document_id = source_document_id.strip()
    raw_file = raw_file.strip()
    metadata_file = metadata_file.strip()
    note = ""
    if source_document_id.startswith("legacy_csv:"):
        if not raw_file:
            raw_file = "ricerche/caduti_purocielo.csv"
        note = "seed legacy CSV, non documento storico verificato."
    return {"raw_file": raw_file, "metadata_file": metadata_file, "note": note}


def _build_decisions_template(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "@type": "ReviewDecisionTemplate",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "draft",
        "allowed_decisions": DEFAULT_ALLOWED_DECISIONS,
        "decisions": [
            {
                "@type": "ReviewDecision",
                "item_id": item.get("item_id", ""),
                "item_type": item.get("item_type", ""),
                "subject_kind": item.get("subject_kind", ""),
                "selected_action": "",
                "allowed_decisions": item.get("allowed_decisions", []),
                "reviewer": "",
                "reviewed_at": "",
                "notes": "",
                "review_status": "draft",
            }
            for item in items
        ],
    }


def _decisions_for_readiness(status: str) -> list[str]:
    if status == "needs_documents":
        return ["request_more_sources", "accept_for_search", "needs_human_transcription", "uncertain"]
    if status == "needs_links":
        return ["confirm", "reject_false_positive", "uncertain", "request_more_sources"]
    if status == "needs_claims":
        return ["needs_better_ocr", "needs_human_transcription", "request_more_sources", "uncertain"]
    return ["uncertain", "request_more_sources"]


def _link_reasons(link: dict[str, Any]) -> list[str]:
    reasons = ["candidate_link_unreviewed"]
    score = link.get("score")
    if score is not None:
        reasons.append(f"score={score}")
    for reason in _list_strings(link.get("reasons")):
        reasons.append(reason)
    return reasons


def _subject_kind_for_claim_field(field: str) -> str:
    key = field.casefold()
    if "place" in key or "luogo" in key or "localita" in key:
        return "place"
    if "date" in key or key.startswith(("birth.", "death.")):
        return "date"
    if any(token in key for token in ("event", "evento", "formation", "military", "battle", "brigade", "unit")):
        return "event_context"
    return "claim"


def _subject_kind_for_signal(signal: dict[str, Any]) -> str:
    if str(signal.get("signal_type", "")) == "skipped_structured_document_claim_candidate":
        return "claim"
    if str(signal.get("signal_type", "")) == "skipped_claim_candidate":
        entity_type = str(signal.get("entity_type", "")).casefold()
        if entity_type == "date":
            return "date"
        if entity_type in {"place", "location", "municipality"}:
            return "place"
        if entity_type in {"formation", "event"}:
            return "event_context"
        return "claim"
    text_parts = [
        str(signal.get("signal_type", "")),
        str(signal.get("value", "")),
        str(signal.get("context", "")),
        *_list_strings(signal.get("reasons")),
    ]
    text = " ".join(text_parts).casefold()
    if any(token in text for token in ("data", "date", "nascita", "morte")) or DATE_HINT_PATTERN.search(text):
        return "date"
    if any(token in text for token in ("luogo", "localita", "place", "comune", "provincia", "citta")):
        return "place"
    if any(token in text for token in ("evento", "event", "battaglia", "formazione", "brigata", "reparto", "caduto")):
        return "event_context"
    return "document_signal"


def _item_type_for_subject_kind(subject_kind: str, default: str) -> str:
    if subject_kind == "date":
        return "date_entity_review"
    if subject_kind == "place":
        return "place_entity_review"
    if subject_kind == "event_context":
        return "event_context_review"
    return default


def _question_for_claim(*, subject_kind: str, field: str, value: str) -> str:
    if subject_kind == "date":
        return f"La data candidata `{field}: {value}` e' attribuibile al profilo e supportata dal documento?"
    if subject_kind == "place":
        return f"Il luogo candidato `{field}: {value}` e' pertinente al profilo e supportato dal documento?"
    if subject_kind == "event_context":
        return f"Il contesto evento candidato `{field}: {value}` e' pertinente e supportato dal documento?"
    return f"Il claim candidato `{field}: {value}` e' supportato dal documento?"


def _question_for_signal(*, subject_kind: str, signal_type: str = "") -> str:
    if signal_type == "skipped_structured_document_claim_candidate":
        return "Questa scheda strutturata va mappata, esclusa o rimandata a revisione manuale?"
    if signal_type == "skipped_claim_candidate":
        return "Questo elemento saltato puo' diventare un claim solo dopo migliore segmentazione o conferma manuale?"
    if subject_kind == "date":
        return "Questa pista documentale contiene una data utile da revisionare per il profilo?"
    if subject_kind == "place":
        return "Questa pista documentale contiene un luogo utile da revisionare per il profilo?"
    if subject_kind == "event_context":
        return "Questa pista documentale contiene un contesto evento utile da revisionare per il profilo?"
    return "Questa pista documentale aiuta a produrre o revisionare un futuro claim per il profilo?"


def _profile_id_from_item(item: dict[str, Any]) -> str:
    return str(item.get("profile_id") or item.get("person_candidate_id") or item.get("person_id") or "")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera una review queue MVP da MvpPilotSummary.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--decisions-template-json", default="")
    args = parser.parse_args()

    summary_json = Path(args.summary_json)
    output_dir = summary_json.parent.parent / "historian_review"
    output_json = Path(args.output_json) if args.output_json else output_dir / "review_queue.json"
    output_md = Path(args.output_md) if args.output_md else output_dir / "review_queue.md"
    decisions_template_json = (
        Path(args.decisions_template_json)
        if args.decisions_template_json
        else output_dir / "review_decisions.template.json"
    )
    try:
        queue = build_mvp_review_queue(
            summary_json=summary_json,
            output_json=output_json,
            output_md=output_md,
            decisions_template_json=decisions_template_json,
        )
    except FileNotFoundError as error:
        print(str(error))
        return 2
    print(f"Review queue MVP: {output_md}")
    print(f"Item: {queue['item_count']}")
    print(f"Template decisioni: {decisions_template_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
