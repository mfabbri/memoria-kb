from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from caduti_fonti_report.document_analysis.mvp_review_markdown import (
    escape_cell as _escape_cell,
    markdown_table_header as _markdown_table_header,
    parse_review_table as _parse_review_table_base,
    shorten as _shorten,
    split_list as _split_list,
)
from caduti_fonti_report.document_analysis.review_queue_items import ReviewQueueItemRecord

TABLE_COLUMNS = [
    "selected_action",
    "reviewer",
    "reviewed_at",
    "item_id",
    "profilo",
    "tipo",
    "oggetto",
    "azioni_ammesse",
    "documento",
    "documento_label",
    "riferimento_documento",
    "domanda",
    "contesto",
    "note",
]


def build_mvp_review_focus_decisions_table(
    *,
    review_session_json: Path,
    output_md: Path | None = None,
    limit: int = 0,
    profile_ids: list[str] | None = None,
) -> dict[str, Any]:
    session = _load_json_object(review_session_json)
    decisions = _focus_decisions(session=session, review_session_json=review_session_json)
    decisions = _filter_by_profile_ids(decisions, profile_ids)
    if limit > 0:
        decisions = decisions[:limit]
    document_lookup = _document_lookup(session=session, review_session_json=review_session_json)
    table = {
        "@type": "MvpReviewFocusDecisionsTable",
        "source_review_session_json": str(review_session_json),
        "decision_count": len(decisions),
        "columns": TABLE_COLUMNS,
        "rows": [_table_row(decision, document_lookup=document_lookup) for decision in decisions],
        "review_status": "pending_historian_review",
        "warnings": [
            "review_focus_table_is_a_human_input_adapter",
            "decisions_do_not_create_verified_historical_facts",
            "decisions_do_not_modify_profiles",
        ],
    }
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_review_focus_decisions_table(table), encoding="utf-8")
    return table


def build_mvp_review_focus_decisions_cards(
    *,
    review_session_json: Path,
    output_md: Path | None = None,
    limit: int = 0,
    profile_ids: list[str] | None = None,
) -> dict[str, Any]:
    session = _load_json_object(review_session_json)
    decisions = _focus_decisions(session=session, review_session_json=review_session_json)
    decisions = _filter_by_profile_ids(decisions, profile_ids)
    if limit > 0:
        decisions = decisions[:limit]
    document_lookup = _document_lookup(session=session, review_session_json=review_session_json)
    cards = {
        "@type": "MvpReviewFocusDecisionCards",
        "source_review_session_json": str(review_session_json),
        "decision_count": len(decisions),
        "cards": [_card_row(decision, document_lookup=document_lookup, index=index) for index, decision in enumerate(decisions, start=1)],
        "review_status": "pending_historian_review",
        "warnings": [
            "human_readable_review_aid_only",
            "cards_do_not_create_verified_historical_facts",
            "cards_do_not_modify_profiles",
        ],
    }
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_review_focus_decisions_cards(cards), encoding="utf-8")
    return cards


def build_mvp_review_queue_decisions_cards(
    *,
    review_queue_json: Path,
    output_md: Path | None = None,
    item_ids: list[str] | None = None,
    profile_ids: list[str] | None = None,
    limit: int = 0,
) -> dict[str, Any]:
    queue = _load_json_object(review_queue_json)
    decisions = _list_items(queue.get("items"))
    decisions = _filter_by_item_ids(decisions, item_ids)
    decisions = _filter_by_profile_ids(decisions, profile_ids)
    if limit > 0:
        decisions = decisions[:limit]
    document_lookup = _document_lookup_from_queue(queue=queue, review_queue_json=review_queue_json)
    cards = {
        "@type": "MvpReviewQueueDecisionCards",
        "source_review_queue_json": str(review_queue_json),
        "decision_count": len(decisions),
        "cards": [_card_row(decision, document_lookup=document_lookup, index=index) for index, decision in enumerate(decisions, start=1)],
        "review_status": "pending_historian_review",
        "warnings": [
            "human_readable_review_aid_only",
            "cards_do_not_create_verified_historical_facts",
            "cards_do_not_modify_profiles",
        ],
    }
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_review_focus_decisions_cards(cards), encoding="utf-8")
    return cards


def convert_mvp_review_focus_decisions_table(
    *,
    review_table_md: Path,
    output_decisions_json: Path | None = None,
    output_summary_json: Path | None = None,
    output_summary_md: Path | None = None,
) -> dict[str, Any]:
    rows = _parse_review_table(review_table_md)
    decisions: list[dict[str, Any]] = []
    validation_errors: list[dict[str, str]] = []
    seen_item_ids: set[str] = set()
    counts_by_status: Counter[str] = Counter()
    counts_by_action: Counter[str] = Counter()

    for row_number, row in enumerate(rows, start=1):
        item_id = str(row.get("item_id", "")).strip()
        selected_action = str(row.get("selected_action", "")).strip()
        allowed_decisions = _split_list(row.get("azioni_ammesse", ""))
        status = "pending"
        error_type = ""
        if not item_id:
            status = "invalid"
            error_type = "missing_item_id"
        elif item_id in seen_item_ids:
            status = "invalid"
            error_type = "duplicate_item_id"
        elif selected_action and allowed_decisions and selected_action not in allowed_decisions:
            status = "invalid"
            error_type = "action_not_listed_in_table"
        elif selected_action:
            status = "provided"

        if item_id:
            seen_item_ids.add(item_id)
        if error_type:
            validation_errors.append(
                {
                    "row": str(row_number),
                    "item_id": item_id,
                    "error_type": error_type,
                    "selected_action": selected_action,
                }
            )
        counts_by_status[status] += 1
        counts_by_action[selected_action or "pending"] += 1
        if status != "invalid":
            decisions.append(
                {
                    "@type": "ReviewDecision",
                    "item_id": item_id,
                    "selected_action": selected_action,
                    "reviewer": str(row.get("reviewer", "")).strip(),
                    "reviewed_at": str(row.get("reviewed_at", "")).strip(),
                    "notes": str(row.get("note", "")).strip(),
                }
            )

    decisions_payload = {
        "@type": "MvpReviewDecisions",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_review_table_md": str(review_table_md),
        "decisions": decisions,
        "warnings": [
            "compiled_from_markdown_review_focus_table",
            "validate_with_summarize_mvp_review_decisions",
            "does_not_create_verified_historical_facts_or_profile_patches",
        ],
    }
    summary = {
        "@type": "MvpReviewFocusDecisionsTableSummary",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_review_table_md": str(review_table_md),
        "output_decisions_json": str(output_decisions_json or ""),
        "review_status": _review_status(counts_by_status=counts_by_status),
        "row_count": len(rows),
        "decision_count": len(decisions),
        "provided_count": counts_by_status.get("provided", 0),
        "pending_count": counts_by_status.get("pending", 0),
        "invalid_count": counts_by_status.get("invalid", 0),
        "validation_error_count": len(validation_errors),
        "counts_by_status": dict(sorted(counts_by_status.items())),
        "counts_by_action": dict(sorted(counts_by_action.items())),
        "validation_errors": validation_errors,
        "warnings": [
            "summary_is_for_table_conversion_only",
            "canonical_validation_remains_mvp_review_decisions_summary",
            "decisions_do_not_create_verified_historical_facts",
            "decisions_do_not_modify_profiles",
        ],
    }
    if output_decisions_json is not None:
        output_decisions_json.parent.mkdir(parents=True, exist_ok=True)
        output_decisions_json.write_text(json.dumps(decisions_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_summary_json is not None:
        output_summary_json.parent.mkdir(parents=True, exist_ok=True)
        output_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_summary_md is not None:
        output_summary_md.parent.mkdir(parents=True, exist_ok=True)
        output_summary_md.write_text(render_mvp_review_focus_decisions_table_summary(summary), encoding="utf-8")
    return summary


def render_mvp_review_focus_decisions_table(table: dict[str, Any]) -> str:
    lines = [
        "# Review focus decisions table MVP",
        "",
        "Compilare solo `selected_action`, `reviewer`, `reviewed_at` e `note`.",
        "",
        "La tabella e' un adattatore umano: validare sempre il JSON generato con `summarize_mvp_review_decisions.ps1`.",
        "",
        f"- Item focus: `{table.get('decision_count', 0)}`",
        f"- Stato: `{table.get('review_status', '')}`",
        "",
        _markdown_table_header(TABLE_COLUMNS),
    ]
    for row in _list_items(table.get("rows")):
        lines.append("| " + " | ".join(_escape_cell(row.get(column, "")) for column in TABLE_COLUMNS) + " |")
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Questa tabella non applica patch.",
            "- Questa tabella non crea fatti verificati.",
            "- Gli item non compilati restano pending.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_mvp_review_focus_decisions_table_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Review focus decisions table summary MVP",
        "",
        f"- Stato conversione: `{summary.get('review_status', '')}`",
        f"- Righe tabella: `{summary.get('row_count', 0)}`",
        f"- Decisioni JSON prodotte: `{summary.get('decision_count', 0)}`",
        f"- Azioni compilate: `{summary.get('provided_count', 0)}`",
        f"- Pending: `{summary.get('pending_count', 0)}`",
        f"- Invalide: `{summary.get('invalid_count', 0)}`",
        f"- Output decisioni: `{summary.get('output_decisions_json', '')}`",
        "",
        "La validazione storica canonica resta `review_decisions_summary.md/json`.",
        "",
        "## Conteggi per azione",
        "",
    ]
    counts_by_action = _dict_object(summary.get("counts_by_action"))
    if counts_by_action:
        for action, count in sorted(counts_by_action.items()):
            lines.append(f"- `{action}`: `{count}`")
    else:
        lines.append("_Nessuna azione registrata._")
    errors = _list_items(summary.get("validation_errors"))
    if errors:
        lines.extend(["", "## Errori tabella", ""])
        for error in errors:
            lines.append(
                f"- Riga `{error.get('row', '')}` item `{error.get('item_id', '')}`: "
                f"`{error.get('error_type', '')}`"
            )
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Questo summary non applica decisioni.",
            "- Questo summary non crea fatti verificati.",
            "- Questo summary non modifica profili JSON-LD.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_mvp_review_focus_decisions_cards(cards: dict[str, Any]) -> str:
    lines = [
        "# Dossier review focus MVP",
        "",
        "Documento leggibile per revisione storica. Non applica decisioni e non crea fatti verificati.",
        "",
        "Per ogni scheda scegliere una sola `selected_action` tra le azioni ammesse. Gli item non compilati restano `pending`.",
        "",
        f"- Item focus: `{cards.get('decision_count', 0)}`",
        f"- Stato: `{cards.get('review_status', '')}`",
        "",
    ]
    for card in _list_items(cards.get("cards")):
        title = " - ".join(part for part in [card.get("canonical_name", ""), card.get("item_id", "")] if part)
        lines.extend(
            [
                f"## {card.get('index', '')}. {title}",
                "",
                f"- Profilo: `{card.get('profile_id', '')}`",
                f"- Tipo decisione: `{card.get('item_type', '')}` / `{card.get('subject_kind', '')}`",
                f"- Documento: {card.get('document_label', '')}",
                f"- Riferimento documento: `{card.get('document_reference', '')}`",
                f"- Domanda: {card.get('question', '')}",
                "",
                *_document_access_lines(card),
                "",
                "Contesto:",
                "",
                f"> {card.get('context', '') or 'Nessun contesto disponibile.'}",
                "",
            ]
        )
        lines.extend(_candidate_lines(card))
        lines.extend(
            [
                f"Azioni ammesse: `{card.get('allowed_decisions', '')}`",
                "",
                "| selected_action | reviewer | reviewed_at | note |",
                "| --- | --- | --- | --- |",
                "|  |  |  |  |",
                "",
            ]
        )
    lines.extend(
        [
            "## Vincoli",
            "",
            "- Questo dossier e' preview-only.",
            "- Le decisioni vanno riportate nella tabella tecnica o convertite con workflow esplicito.",
            "- Nessun item confermato diventa automaticamente fatto storico verificato.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _table_row(decision: dict[str, Any], *, document_lookup: dict[str, dict[str, str]] | None = None) -> dict[str, str]:
    source_document_id = str(decision.get("source_document_id", ""))
    document = (document_lookup or {}).get(source_document_id, {})
    return {
        "selected_action": str(decision.get("selected_action", "")),
        "reviewer": str(decision.get("reviewer", "")),
        "reviewed_at": str(decision.get("reviewed_at", "")),
        "item_id": str(decision.get("item_id", "")),
        "profilo": str(decision.get("profile_id", "")),
        "tipo": str(decision.get("item_type", "")),
        "oggetto": str(decision.get("subject_kind", "")),
        "azioni_ammesse": ", ".join(_list_strings(decision.get("allowed_decisions"))),
        "documento": source_document_id,
        "documento_label": _document_label(source_document_id=source_document_id, document=document),
        "riferimento_documento": _document_reference(document),
        "domanda": _shorten(decision.get("question", ""), 180),
        "contesto": _shorten(decision.get("context", ""), 220),
        "note": str(decision.get("notes", "")),
    }


def _card_row(
    decision: dict[str, Any],
    *,
    document_lookup: dict[str, dict[str, str]] | None = None,
    index: int,
) -> dict[str, Any]:
    item = ReviewQueueItemRecord.from_payload(decision)
    source_document_id = item.source_document_id
    document = (document_lookup or {}).get(source_document_id, {})
    document_access = _document_access(source_document_id=source_document_id, document=document)
    return {
        "index": str(index),
        "item_id": item.item_id,
        "profile_id": item.profile_id,
        "canonical_name": item.canonical_name,
        "item_type": item.item_type,
        "subject_kind": item.subject_kind,
        "document_id": source_document_id,
        "document_label": _document_label(source_document_id=source_document_id, document=document),
        "document_reference": _document_reference(document),
        "document_access": document_access,
        "question": _shorten(item.question, 280),
        "context": _shorten(item.context, 600),
        "allowed_decisions": item.allowed_decisions_text,
        "candidate_field": item.candidate_field,
        "candidate_value": item.candidate_value,
    }


def _focus_decisions(*, session: dict[str, Any], review_session_json: Path) -> list[dict[str, Any]]:
    decisions = _list_items(_dict_object(session.get("review_focus_decisions_template")).get("decisions"))
    if not decisions:
        fallback_decisions = _fallback_focus_decisions(session=session, review_session_json=review_session_json)
        if fallback_decisions:
            return fallback_decisions
        return _fallback_review_queue_decisions(session=session, review_session_json=review_session_json)
    return _enrich_focus_decisions(session=session, review_session_json=review_session_json, decisions=decisions)


def _filter_by_profile_ids(decisions: list[dict[str, Any]], profile_ids: list[str] | None) -> list[dict[str, Any]]:
    allowed = {profile_id.strip() for profile_id in profile_ids or [] if profile_id.strip()}
    if not allowed:
        return decisions
    return [decision for decision in decisions if str(decision.get("profile_id", "")).strip() in allowed]


def _filter_by_item_ids(decisions: list[dict[str, Any]], item_ids: list[str] | None) -> list[dict[str, Any]]:
    allowed = {item_id.strip() for item_id in item_ids or [] if item_id.strip()}
    if not allowed:
        return decisions
    return [decision for decision in decisions if str(decision.get("item_id", "")).strip() in allowed]


def _candidate_lines(card: dict[str, Any]) -> list[str]:
    field = str(card.get("candidate_field", "")).strip()
    value = str(card.get("candidate_value", "")).strip()
    if not field and not value:
        return []
    return [
        "Candidate:",
        "",
        f"- field: `{field}`",
        f"- value: `{value}`",
        "",
    ]


def _document_access_lines(card: dict[str, Any]) -> list[str]:
    document_id = str(card.get("document_id", "")).strip()
    if not document_id:
        return [
            "### Come aprire il documento",
            "",
            "- Documento: `non disponibile`",
        ]
    access = _dict_object(card.get("document_access"))
    image_paths = _list_strings(access.get("image_paths"))
    lines = [
        "### Come aprire il documento",
        "",
        f"- Documento: `{document_id}`",
        f"- Titolo: `{_access_value(access.get('title'))}`",
        f"- URL fonte: `{_access_value(access.get('source_url'))}`",
        f"- Raw locale: `{_access_value(access.get('raw_local_path') or access.get('raw_file'))}`",
        f"- Testo processato: `{_access_value(access.get('text_json'))}`",
        f"- Metadati: `{_access_value(access.get('metadata_json'))}`",
        f"- Immagini: `{len(image_paths)}`",
    ]
    for image_path in image_paths[:5]:
        lines.append(f"  - `{image_path}`")
    if len(image_paths) > 5:
        lines.append(f"  - altri file immagine: `{len(image_paths) - 5}`")
    return lines


def _enrich_focus_decisions(
    *,
    session: dict[str, Any],
    review_session_json: Path,
    decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    queue_by_id = _review_queue_items_by_id(session=session, review_session_json=review_session_json)
    enriched: list[dict[str, Any]] = []
    for decision in decisions:
        item_id = str(decision.get("item_id", ""))
        queue_item = queue_by_id.get(item_id, {})
        enriched.append({**queue_item, **decision})
    return enriched


def _fallback_focus_decisions(*, session: dict[str, Any], review_session_json: Path) -> list[dict[str, Any]]:
    queue_by_id = _review_queue_items_by_id(session=session, review_session_json=review_session_json)
    decisions: list[dict[str, Any]] = []
    seen_item_ids: set[str] = set()
    for profile in _list_items(session.get("profiles")):
        profile_id = str(profile.get("profile_id", ""))
        for item in _list_items(profile.get("priority_review_items")):
            item_id = str(item.get("item_id", "")).strip()
            if not item_id or item_id in seen_item_ids:
                continue
            seen_item_ids.add(item_id)
            queue_item = queue_by_id.get(item_id, {})
            merged = {**item, **queue_item}
            merged.setdefault("profile_id", profile_id)
            merged.setdefault("selected_action", "")
            merged.setdefault("reviewer", "")
            merged.setdefault("reviewed_at", "")
            merged.setdefault("notes", "")
            decisions.append(merged)
    return decisions


def _fallback_review_queue_decisions(*, session: dict[str, Any], review_session_json: Path) -> list[dict[str, Any]]:
    queue_by_id = _review_queue_items_by_id(session=session, review_session_json=review_session_json)
    decisions: list[dict[str, Any]] = []
    for item in queue_by_id.values():
        decision = dict(item)
        decision.setdefault("selected_action", "")
        decision.setdefault("reviewer", "")
        decision.setdefault("reviewed_at", "")
        decision.setdefault("notes", "")
        decisions.append(decision)
    return decisions


def _review_queue_items_by_id(*, session: dict[str, Any], review_session_json: Path) -> dict[str, dict[str, Any]]:
    queue_path_text = str(session.get("source_review_queue_json", "")).strip()
    if not queue_path_text:
        return {}
    queue_path = Path(queue_path_text)
    if not queue_path.is_absolute():
        queue_path = review_session_json.parent / queue_path
    if not queue_path.exists():
        return {}
    queue = _load_json_object(queue_path)
    return {
        str(item.get("item_id", "")): item
        for item in _list_items(queue.get("items"))
        if str(item.get("item_id", "")).strip()
    }


def _document_lookup_from_queue(*, queue: dict[str, Any], review_queue_json: Path) -> dict[str, dict[str, str]]:
    summary_path_text = str(queue.get("source_summary_json", "")).strip()
    if not summary_path_text:
        summary_path = review_queue_json.parent.parent / "document_analysis" / "mvp_pilot_summary.json"
    else:
        summary_path = Path(summary_path_text)
        if not summary_path.is_absolute():
            summary_path = review_queue_json.parent / summary_path
    return _document_lookup_from_summary_path(summary_path)


def _document_lookup(*, session: dict[str, Any], review_session_json: Path) -> dict[str, dict[str, str]]:
    summary_path_text = str(session.get("source_summary_json", "")).strip()
    if not summary_path_text:
        return {}
    summary_path = Path(summary_path_text)
    if not summary_path.is_absolute():
        summary_path = review_session_json.parent / summary_path
    return _document_lookup_from_summary_path(summary_path)


def _document_lookup_from_summary_path(summary_path: Path) -> dict[str, dict[str, str]]:
    if not summary_path.exists():
        return {}
    summary = _load_json_object(summary_path)
    lookup: dict[str, dict[str, str]] = {}
    for section in [
        "documents",
        "candidate_document_person_links",
        "candidate_evidence_claims",
        "reviewable_document_signals",
    ]:
        for item in _iter_document_records(summary.get(section)):
            document_id = str(item.get("source_document_id", "")).strip()
            if not document_id:
                continue
            info = lookup.setdefault(document_id, {})
            for key in [
                "title",
                "url",
                "archival_reference",
                "raw_file",
                "metadata_file",
                "text_file",
                "text_path",
                "quality_path",
                "document_class",
                "quality_status",
                "classification",
                "source_url",
            ]:
                value = str(item.get(key, "")).strip()
                if value and not info.get(key):
                    info[key] = value
    return lookup


def _iter_document_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in _list_items(value):
        records.append(item)
        records.extend(_list_items(item.get("signals")))
    return records


def _document_label(*, source_document_id: str, document: dict[str, str]) -> str:
    title = str(document.get("title", "")).strip()
    document_class = str(document.get("document_class", "")).strip()
    if title and document_class:
        return f"{title} ({document_class})"
    if title:
        return title
    if document_class:
        return document_class
    return source_document_id


def _document_reference(document: dict[str, str]) -> str:
    for key in ["raw_file", "source_url", "url", "archival_reference", "metadata_file", "text_file", "text_path", "quality_path"]:
        value = str(document.get(key, "")).strip()
        if value:
            return value
    return ""


def _document_access(*, source_document_id: str, document: dict[str, str]) -> dict[str, Any]:
    access: dict[str, Any] = {
        "title": str(document.get("title", "")).strip(),
        "source_url": str(document.get("source_url", "") or document.get("url", "")).strip(),
        "raw_file": str(document.get("raw_file", "")).strip(),
        "raw_local_path": "",
        "text_json": str(document.get("text_file", "") or document.get("text_path", "")).strip(),
        "metadata_json": str(document.get("metadata_file", "")).strip(),
        "image_paths": [],
    }
    metadata_path = Path(access["metadata_json"]) if access["metadata_json"] else _candidate_metadata_path(source_document_id)
    if metadata_path and metadata_path.exists():
        access["metadata_json"] = str(metadata_path)
        metadata = _load_json_object(metadata_path)
        access["title"] = access["title"] or str(metadata.get("title", "")).strip()
        access["source_url"] = access["source_url"] or str(metadata.get("source_url", "") or metadata.get("url", "")).strip()
        access["raw_file"] = access["raw_file"] or str(metadata.get("raw_file", "")).strip()
    text_path = Path(access["text_json"]) if access["text_json"] else _sibling_processed_path(metadata_path, ".text.json")
    if text_path and text_path.exists():
        access["text_json"] = str(text_path)
    if not access["raw_local_path"] and access["raw_file"]:
        access["raw_local_path"] = _resolve_raw_local_path(raw_file=access["raw_file"], processed_path=metadata_path or text_path)
    access["image_paths"] = _image_paths(metadata_path or text_path)
    return access


def _candidate_metadata_path(source_document_id: str) -> Path | None:
    source_id, suffix = _source_document_parts(source_document_id)
    if not source_id or not suffix:
        return None
    return Path("processed_documents") / source_id / f"{source_id}-{suffix}.metadata.json"


def _source_document_parts(source_document_id: str) -> tuple[str, str]:
    text = source_document_id.strip()
    if ":" not in text:
        return "", ""
    source_id, suffix = text.rsplit(":", 1)
    source_id = source_id.replace(":", "_")
    return source_id, suffix


def _sibling_processed_path(path: Path | None, suffix: str) -> Path | None:
    if not path:
        return None
    name = path.name
    if name.endswith(".metadata.json"):
        return path.with_name(name[: -len(".metadata.json")] + suffix)
    return None


def _resolve_raw_local_path(*, raw_file: str, processed_path: Path | None) -> str:
    if not raw_file:
        return ""
    raw_path = Path(raw_file)
    if raw_path.is_absolute():
        return str(raw_path)
    workspace_root = _workspace_root_from_processed_path(processed_path)
    if not workspace_root:
        return raw_file
    candidates = [
        workspace_root / "documenti_da_processare" / raw_file,
        workspace_root / "documenti_da_processare" / "mvp_purocielo" / raw_file,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[-1])


def _workspace_root_from_processed_path(path: Path | None) -> Path | None:
    if not path:
        return None
    parts = path.parts
    for index, part in enumerate(parts):
        if part == "risultati" and index > 0:
            return Path(*parts[:index])
    return None


def _image_paths(path: Path | None) -> list[str]:
    if not path or not path.parent.exists():
        return []
    stem = path.name
    for suffix in [".metadata.json", ".text.json"]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    paths = sorted(path.parent.glob(f"{stem}-image-*.*.json"))
    return [str(item) for item in paths if item.name.endswith(".metadata.json") or item.name.endswith(".text.json")]


def _access_value(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "non disponibile"


def _parse_review_table(path: Path) -> list[dict[str, str]]:
    return _parse_review_table_base(path, table_columns=TABLE_COLUMNS)


def _review_status(*, counts_by_status: Counter[str]) -> str:
    if counts_by_status.get("invalid", 0):
        return "invalid"
    if counts_by_status.get("provided", 0) and counts_by_status.get("pending", 0):
        return "partial_review"
    if counts_by_status.get("provided", 0):
        return "compiled"
    return "pending_review"


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _dict_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera o converte gli output Markdown focus decisioni MVP.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build-table", help="Genera tabella Markdown compilabile.")
    build_parser.add_argument("--review-session-json", required=True)
    build_parser.add_argument("--output-md", required=True)
    build_parser.add_argument("--limit", type=int, default=0)
    build_parser.add_argument("--profile-id", action="append", default=[])

    cards_parser = subparsers.add_parser("build-cards", help="Genera dossier Markdown leggibile a schede.")
    cards_parser.add_argument("--review-session-json", required=True)
    cards_parser.add_argument("--output-md", required=True)
    cards_parser.add_argument("--limit", type=int, default=0)
    cards_parser.add_argument("--profile-id", action="append", default=[])

    queue_cards_parser = subparsers.add_parser("build-queue-cards", help="Genera cards Markdown da review_queue e item espliciti.")
    queue_cards_parser.add_argument("--review-queue-json", required=True)
    queue_cards_parser.add_argument("--output-md", required=True)
    queue_cards_parser.add_argument("--item-id", action="append", default=[])
    queue_cards_parser.add_argument("--profile-id", action="append", default=[])
    queue_cards_parser.add_argument("--limit", type=int, default=0)

    convert_parser = subparsers.add_parser("convert-table", help="Converte tabella Markdown compilata in JSON decisioni.")
    convert_parser.add_argument("--review-table-md", required=True)
    convert_parser.add_argument("--output-decisions-json", required=True)
    convert_parser.add_argument("--output-summary-json", required=True)
    convert_parser.add_argument("--output-summary-md", required=True)

    args = parser.parse_args()
    if args.command == "build-table":
        table = build_mvp_review_focus_decisions_table(
            review_session_json=Path(args.review_session_json),
            output_md=Path(args.output_md),
            limit=args.limit,
            profile_ids=_cli_profile_ids(args.profile_id),
        )
        print(f"Tabella focus decisioni MVP: {args.output_md}")
        print(f"Item focus: {table['decision_count']}")
        return 0
    if args.command == "build-cards":
        cards = build_mvp_review_focus_decisions_cards(
            review_session_json=Path(args.review_session_json),
            output_md=Path(args.output_md),
            limit=args.limit,
            profile_ids=_cli_profile_ids(args.profile_id),
        )
        print(f"Dossier focus decisioni MVP: {args.output_md}")
        print(f"Item focus: {cards['decision_count']}")
        return 0
    if args.command == "build-queue-cards":
        cards = build_mvp_review_queue_decisions_cards(
            review_queue_json=Path(args.review_queue_json),
            output_md=Path(args.output_md),
            item_ids=_cli_item_ids(args.item_id),
            profile_ids=_cli_profile_ids(args.profile_id),
            limit=args.limit,
        )
        print(f"Dossier queue decisioni MVP: {args.output_md}")
        print(f"Item: {cards['decision_count']}")
        return 0
    if args.command == "convert-table":
        summary = convert_mvp_review_focus_decisions_table(
            review_table_md=Path(args.review_table_md),
            output_decisions_json=Path(args.output_decisions_json),
            output_summary_json=Path(args.output_summary_json),
            output_summary_md=Path(args.output_summary_md),
        )
        print(f"Decisioni compilate MVP: {args.output_decisions_json}")
        print(f"Summary tabella focus MVP: {args.output_summary_md}")
        print(f"Stato: {summary['review_status']}")
        return 1 if summary["review_status"] == "invalid" else 0
    raise ValueError(f"Comando non supportato: {args.command}")


def _cli_profile_ids(values: list[str]) -> list[str]:
    profile_ids: list[str] = []
    for value in values:
        profile_ids.extend(item.strip() for item in str(value).split(",") if item.strip())
    return profile_ids


def _cli_item_ids(values: list[str]) -> list[str]:
    item_ids: list[str] = []
    for value in values:
        item_ids.extend(item.strip() for item in str(value).split(",") if item.strip())
    return item_ids


if __name__ == "__main__":
    raise SystemExit(main())
