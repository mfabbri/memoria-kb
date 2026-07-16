from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ALLOWED_DECISIONS = {"BUONA", "DUBBIA", "INUTILE"}
TABLE_COLUMNS = [
    "decisione",
    "valore",
    "action_id",
    "documento",
    "fonti_suggerite",
    "indizi",
    "contesto",
    "note_storico",
]


def build_research_feedback_actions_review_table(
    *,
    actions_json: Path,
    output_md: Path | None = None,
    limit: int = 0,
) -> dict[str, Any]:
    payload = _load_json_object(actions_json)
    actions = _flatten_actions(payload)
    if limit > 0:
        actions = actions[:limit]
    table = {
        "@type": "ResearchFeedbackActionReviewTable",
        "source_actions_json": str(actions_json),
        "action_count": len(actions),
        "allowed_decisions": sorted(ALLOWED_DECISIONS),
        "columns": TABLE_COLUMNS,
        "rows": [_table_row(action) for action in actions],
        "review_status": "pending_historian_triage",
        "warnings": [
            "research_feedback_triage_is_audit_only",
            "decisions_do_not_create_verified_facts",
            "decisions_do_not_modify_profiles",
        ],
    }
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_research_feedback_actions_review_table(table), encoding="utf-8")
    return table


def summarize_research_feedback_actions_review_table(
    *,
    actions_json: Path,
    review_table_md: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    actions_payload = _load_json_object(actions_json)
    actions_by_id = {str(action.get("action_id", "")): action for action in _flatten_actions(actions_payload)}
    table_rows = _parse_review_table(review_table_md)
    decisions: list[dict[str, Any]] = []
    validation_errors: list[dict[str, str]] = []
    seen_action_ids: set[str] = set()
    counts_by_decision: Counter[str] = Counter()
    accepted_by_decision: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for index, row in enumerate(table_rows, start=1):
        action_id = str(row.get("action_id", "")).strip()
        raw_decision = str(row.get("decisione", "")).strip()
        decision = raw_decision.upper()
        action = actions_by_id.get(action_id)
        status = "pending"
        error_type = ""

        if not action_id:
            status = "invalid"
            error_type = "missing_action_id"
        elif action_id in seen_action_ids:
            status = "invalid"
            error_type = "duplicate_action_id"
        elif action is None:
            status = "invalid"
            error_type = "unknown_action_id"
        elif not decision:
            status = "pending"
        elif decision not in ALLOWED_DECISIONS:
            status = "invalid"
            error_type = "decision_not_allowed"
        else:
            status = "accepted"
            counts_by_decision[decision] += 1

        if action_id:
            seen_action_ids.add(action_id)
        if error_type:
            validation_errors.append(
                {
                    "row": str(index),
                    "action_id": action_id,
                    "error_type": error_type,
                    "decision": raw_decision,
                }
            )

        decision_record = {
            "@type": "ResearchFeedbackActionTriageDecision",
            "row": index,
            "decision_status": status,
            "decision": decision if decision in ALLOWED_DECISIONS else raw_decision,
            "action_id": action_id,
            "value": str(row.get("valore", "")),
            "source_document_id": str(row.get("documento", "")),
            "suggested_sources": _split_list(row.get("fonti_suggerite", "")),
            "notes": str(row.get("note_storico", "")),
            "review_status": "unreviewed",
        }
        if action is not None:
            decision_record.update(
                {
                    "person_id": str(action.get("person_id", "")),
                    "chunk_id": str(action.get("chunk_id", "")),
                    "weak_segment_id": str(action.get("weak_segment_id", "")),
                    "priority": str(action.get("priority", "")),
                    "risk": str(action.get("risk", "")),
                }
            )
        decisions.append(decision_record)
        if status == "accepted":
            accepted_by_decision[decision].append(decision_record)

    pending_count = sum(1 for decision in decisions if decision.get("decision_status") == "pending")
    invalid_count = sum(1 for decision in decisions if decision.get("decision_status") == "invalid")
    accepted_count = sum(1 for decision in decisions if decision.get("decision_status") == "accepted")
    summary = {
        "@type": "ResearchFeedbackActionReviewSummary",
        "source_actions_json": str(actions_json),
        "source_review_table_md": str(review_table_md),
        "review_status": _review_status(accepted_count=accepted_count, pending_count=pending_count, invalid_count=invalid_count),
        "action_count": len(actions_by_id),
        "row_count": len(table_rows),
        "accepted_count": accepted_count,
        "pending_count": pending_count,
        "invalid_count": invalid_count,
        "validation_error_count": len(validation_errors),
        "counts_by_decision": dict(sorted(counts_by_decision.items())),
        "validation_errors": validation_errors,
        "decisions": decisions,
        "accepted_by_decision": {key: value for key, value in sorted(accepted_by_decision.items())},
        "warnings": [
            "research_feedback_triage_summary_is_audit_only",
            "decisions_do_not_create_verified_facts",
            "decisions_do_not_modify_profiles",
        ],
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_research_feedback_actions_review_summary(summary), encoding="utf-8")
    return summary


def render_research_feedback_actions_review_table(table: dict[str, Any]) -> str:
    lines = [
        "# ResearchFeedbackAction triage table",
        "",
        "Compilare solo `decisione` e `note_storico`.",
        "",
        "Decisioni ammesse: `BUONA`, `DUBBIA`, `INUTILE`.",
        "",
        "Questa tabella e' audit-only: non valida fatti, non modifica profili e non crea claim verificati.",
        "",
        f"- Azioni: `{table.get('action_count', 0)}`",
        f"- Stato: `{table.get('review_status', '')}`",
        "",
        _markdown_table_header(TABLE_COLUMNS),
    ]
    for row in table.get("rows", []):
        if not isinstance(row, dict):
            continue
        lines.append("| " + " | ".join(_escape_cell(row.get(column, "")) for column in TABLE_COLUMNS) + " |")
    return "\n".join(lines).rstrip() + "\n"


def render_research_feedback_actions_review_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# ResearchFeedbackAction triage summary",
        "",
        f"- Stato: `{summary.get('review_status', '')}`",
        f"- Azioni sorgente: `{summary.get('action_count', 0)}`",
        f"- Righe tabella: `{summary.get('row_count', 0)}`",
        f"- Decisioni accettate: `{summary.get('accepted_count', 0)}`",
        f"- Pending: `{summary.get('pending_count', 0)}`",
        f"- Invalide: `{summary.get('invalid_count', 0)}`",
        "",
        "Nessuna decisione crea fatti verificati, patch profilo o claim validati.",
        "",
        "## Conteggi",
        "",
    ]
    counts = summary.get("counts_by_decision", {})
    if isinstance(counts, dict) and counts:
        for decision, count in counts.items():
            lines.append(f"- `{decision}`: `{count}`")
    else:
        lines.append("_Nessuna decisione compilata._")
    lines.extend(["", "## Piste accettate", ""])
    accepted = summary.get("accepted_by_decision", {})
    if isinstance(accepted, dict) and accepted:
        for decision in ["BUONA", "DUBBIA", "INUTILE"]:
            items = accepted.get(decision, [])
            if not items:
                continue
            lines.extend([f"### {decision}", ""])
            for item in items:
                lines.append(
                    f"- `{item.get('action_id', '')}` | {item.get('value', '')} | "
                    f"documento `{item.get('source_document_id', '')}` | note: {item.get('notes', '') or '-'}"
                )
            lines.append("")
    else:
        lines.append("_Nessuna pista classificata._")
        lines.append("")
    errors = summary.get("validation_errors", [])
    if isinstance(errors, list) and errors:
        lines.extend(["## Errori validazione", ""])
        for error in errors:
            if not isinstance(error, dict):
                continue
            lines.append(
                f"- Riga `{error.get('row', '')}` action `{error.get('action_id', '')}`: "
                f"`{error.get('error_type', '')}`"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _flatten_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    documents = payload.get("documents", [])
    if not isinstance(documents, list):
        return actions
    for document in documents:
        if not isinstance(document, dict):
            continue
        for action in document.get("actions", []):
            if not isinstance(action, dict):
                continue
            enriched = dict(action)
            enriched.setdefault("source_id", document.get("source_id", ""))
            enriched.setdefault("source_document_id", document.get("source_document_id", ""))
            actions.append(enriched)
    return sorted(actions, key=_action_sort_key)


def _action_sort_key(action: dict[str, Any]) -> tuple[int, int, str, str]:
    priority_rank = {"high": 0, "medium": 1, "low": 2}.get(str(action.get("priority", "")), 9)
    risk_rank = {"high": 0, "medium": 1, "low": 2}.get(str(action.get("risk", "")), 9)
    return (priority_rank, risk_rank, str(action.get("value", "")), str(action.get("action_id", "")))


def _table_row(action: dict[str, Any]) -> dict[str, str]:
    hints = []
    for hint in action.get("suggested_search_hints", []):
        if not isinstance(hint, dict):
            continue
        field = str(hint.get("field", "")).strip()
        value = str(hint.get("value", "")).strip()
        if field and value:
            hints.append(f"{field}: {value}")
    context = action.get("context", {})
    quote = str(context.get("quote", "")) if isinstance(context, dict) else ""
    return {
        "decisione": "",
        "valore": _shorten(action.get("value", ""), 80),
        "action_id": str(action.get("action_id", "")),
        "documento": str(action.get("source_document_id", "")),
        "fonti_suggerite": ", ".join(str(source) for source in action.get("suggested_sources", [])),
        "indizi": _shorten("; ".join(hints), 140),
        "contesto": _shorten(quote, 180),
        "note_storico": "",
    }


def _parse_review_table(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [_unescape_cell(cell.strip()) for cell in stripped.strip("|").split("|")]
        if len(cells) != len(TABLE_COLUMNS):
            continue
        normalized = [cell.strip().casefold() for cell in cells]
        if normalized == TABLE_COLUMNS:
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(dict(zip(TABLE_COLUMNS, cells)))
    return rows


def _markdown_table_header(columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    return header + "\n" + separator


def _escape_cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("\r", " ").replace("|", "&#124;").strip()


def _unescape_cell(value: str) -> str:
    return value.replace("&#124;", "|").strip()


def _shorten(value: Any, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _split_list(value: Any) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _review_status(*, accepted_count: int, pending_count: int, invalid_count: int) -> str:
    if invalid_count:
        return "invalid"
    if accepted_count and pending_count:
        return "partial_review"
    if accepted_count:
        return "reviewed"
    return "pending"


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera o riepiloga il triage Markdown delle ResearchFeedbackAction.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build-table", help="Genera tabella Markdown compilabile.")
    build_parser.add_argument("--actions-json", required=True)
    build_parser.add_argument("--output-md", required=True)
    build_parser.add_argument("--limit", type=int, default=0)

    summarize_parser = subparsers.add_parser("summarize-table", help="Riepiloga tabella Markdown compilata.")
    summarize_parser.add_argument("--actions-json", required=True)
    summarize_parser.add_argument("--review-table-md", required=True)
    summarize_parser.add_argument("--output-json", required=True)
    summarize_parser.add_argument("--output-md", required=True)

    args = parser.parse_args()
    if args.command == "build-table":
        table = build_research_feedback_actions_review_table(
            actions_json=Path(args.actions_json),
            output_md=Path(args.output_md),
            limit=args.limit,
        )
        print(f"Tabella triage ResearchFeedbackAction scritta in {args.output_md}")
        print(f"Azioni: {table['action_count']}")
        return 0
    if args.command == "summarize-table":
        summary = summarize_research_feedback_actions_review_table(
            actions_json=Path(args.actions_json),
            review_table_md=Path(args.review_table_md),
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
        )
        print(f"Summary triage ResearchFeedbackAction JSON scritto in {args.output_json}")
        print(f"Summary triage ResearchFeedbackAction Markdown scritto in {args.output_md}")
        print(f"Decisioni accettate: {summary['accepted_count']}")
        print(f"Decisioni invalide: {summary['invalid_count']}")
        return 0
    raise ValueError(f"Comando non supportato: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
