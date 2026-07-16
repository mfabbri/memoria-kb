from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .preview_payloads import (
    dict_object,
    list_items,
    list_strings,
    load_json_object,
    unique_non_empty,
    write_json,
    write_markdown,
    yaml_value,
)

ALLOWED_STATES = ["approved", "rejected", "uncertain", "request_more_sources", "superseded", "conflict_open", "unknown"]
TERMINAL_STATES = ["approved", "rejected", "superseded"]
OPEN_STATES = ["uncertain", "request_more_sources", "conflict_open", "unknown"]


@dataclass(frozen=True)
class ReviewStoreDecisionPreview:
    decision_id: str
    version: str
    state: str
    decision_scope: str
    profile_id: str
    source_document_id: str
    source_record_id: str
    source_run_id: str
    review_item_id: str
    selected_action: str
    decision_status: str
    reviewer: str
    reviewed_at: str
    supersedes: tuple[str, ...]
    superseded_by: tuple[str, ...]
    provenance: dict[str, Any]

    @classmethod
    def from_register_decision(cls, decision: dict[str, Any]) -> "ReviewStoreDecisionPreview":
        source_record_id = str(decision.get("record_id") or decision.get("source_record_id") or "").strip()
        state = str(decision.get("normalized_state") or decision.get("state") or "unknown").strip() or "unknown"
        return cls(
            decision_id=f"review-decision-preview:{_slug(source_record_id)}",
            version="v1",
            state=state if state in ALLOWED_STATES else "unknown",
            decision_scope=str(decision.get("decision_scope", "")).strip(),
            profile_id=str(decision.get("profile_id", "")).strip(),
            source_document_id=str(decision.get("source_document_id", "")).strip(),
            source_record_id=source_record_id,
            source_run_id=str(decision.get("source_run_id", "")).strip(),
            review_item_id=str(decision.get("review_item_id") or decision.get("item_id") or "").strip(),
            selected_action=str(decision.get("selected_action", "")).strip(),
            decision_status=str(decision.get("decision_status", "")).strip(),
            reviewer=str(decision.get("reviewer", "")).strip(),
            reviewed_at=str(decision.get("reviewed_at", "")).strip(),
            supersedes=tuple(list_strings(decision.get("supersedes"))),
            superseded_by=tuple(list_strings(decision.get("superseded_by"))),
            provenance=dict_object(decision.get("provenance")),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "@type": "ReviewDecisionStoreEntryPreview",
            "decision_id": self.decision_id,
            "version": self.version,
            "state": self.state,
            "decision_scope": self.decision_scope,
            "profile_id": self.profile_id,
            "source_document_id": self.source_document_id,
            "source_record_id": self.source_record_id,
            "source_run_id": self.source_run_id,
            "review_item_id": self.review_item_id,
            "selected_action": self.selected_action,
            "decision_status": self.decision_status,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "supersedes": list(self.supersedes),
            "superseded_by": list(self.superseded_by),
            "versioning_policy": "append_new_version_for_corrections",
            "superseding_policy": "requires_explicit_human_decision_link",
            "provenance": dict(self.provenance),
        }


def build_review_store_preview(
    *,
    review_register_json: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
    profile_id: list[str] | None = None,
    evidence_db: Path | None = None,
    evidence_source_run_id: list[str] | None = None,
    limit: int = 0,
) -> dict[str, Any]:
    if not review_register_json.is_file():
        raise FileNotFoundError(f"Registro decisioni/conflitti non trovato: {review_register_json}")
    profile_filter = unique_non_empty(profile_id or [])
    register = load_json_object(review_register_json)
    decisions = [
        ReviewStoreDecisionPreview.from_register_decision(decision).to_payload()
        for decision in list_items(register.get("decisions"))
        if not profile_filter or str(decision.get("profile_id", "")).strip() in profile_filter
    ]
    decisions.sort(key=lambda item: (str(item.get("profile_id", "")), str(item.get("decision_id", ""))))
    if limit > 0:
        decisions = decisions[:limit]

    decision_ids_by_record = {str(item.get("source_record_id", "")): str(item.get("decision_id", "")) for item in decisions}
    conflicts = [
        _conflict_entry(conflict, decision_ids_by_record=decision_ids_by_record)
        for conflict in list_items(register.get("open_conflicts"))
        if not profile_filter or str(conflict.get("profile_id", "")).strip() in profile_filter
    ]
    conflicts.sort(key=lambda item: (str(item.get("profile_id", "")), str(item.get("conflict_id", ""))))

    source_run_ids = unique_non_empty(evidence_source_run_id or [])
    evidence_validation = _validate_evidence_records(
        evidence_db=evidence_db,
        source_run_ids=source_run_ids,
        record_ids=[str(item.get("source_record_id", "")) for item in decisions if str(item.get("source_record_id", "")).strip()],
    )
    state_coverage = _state_coverage(decisions)
    payload: dict[str, Any] = {
        "@type": "ReviewStorePreview",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_review_decision_conflict_register": str(review_register_json),
        "source_evidence_db": str(evidence_db) if evidence_db is not None else "",
        "source_run_ids": source_run_ids,
        "profile_ids": profile_filter,
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "schema_policy": _schema_policy(),
        "decision_count": len(decisions),
        "conflict_count": len(conflicts),
        **state_coverage,
        "review_decisions": decisions,
        "conflicts": conflicts,
        "evidence_validation": evidence_validation,
        "safety_notes": [
            "Preview read-only del futuro review store canonico.",
            "Non crea tabelle canoniche e non migra dati reali.",
            "Non crea verified_facts canonici.",
            "Non modifica profili JSON-LD e non applica ProfilePatch.",
        ],
    }
    if output_json is not None:
        write_json(output_json, payload)
    if output_md is not None:
        write_markdown(output_md, render_review_store_preview_markdown(payload))
    return payload


def render_review_store_preview_markdown(payload: dict[str, Any]) -> str:
    validation = dict_object(payload.get("evidence_validation"))
    lines = [
        "---",
        "type: review_store_preview",
        f"review_status: {yaml_value(payload.get('review_status', 'preview-only'))}",
        f"publication_status: {yaml_value(payload.get('publication_status', 'not_publishable_without_editorial_review'))}",
        "preview_only: true",
        "---",
        "",
        "# Review store preview",
        "",
        "Preview tecnica del futuro review store versionato. Non e' ancora uno store canonico persistente.",
        "",
        "## Sintesi",
        "",
        f"- Decisioni versionate: `{payload.get('decision_count', 0)}`",
        f"- Conflitti aperti: `{payload.get('conflict_count', 0)}`",
        f"- Decisioni terminali: `{payload.get('terminal_decision_count', 0)}`",
        f"- Decisioni aperte: `{payload.get('open_decision_count', 0)}`",
        f"- Validazione evidence: `{validation.get('status', 'not_requested')}`",
        f"- Registro sorgente: `{payload.get('source_review_decision_conflict_register', '')}`",
        "",
        "## Copertura stati",
        "",
    ]
    counts_by_state = dict_object(payload.get("counts_by_state"))
    if counts_by_state:
        for state in ALLOWED_STATES:
            lines.append(f"- `{state}`: `{counts_by_state.get(state, 0)}`")
    else:
        lines.append("_Nessuno stato decisionale._")
    lines.extend(
        [
            f"- Decisioni senza revisore: `{payload.get('missing_reviewer_count', 0)}`",
            f"- Decisioni senza data revisione: `{payload.get('missing_reviewed_at_count', 0)}`",
            "",
        ]
    )
    lines.extend(
        [
            "## Policy schema",
            "",
            f"- Stati ammessi: `{', '.join(list_strings(dict_object(payload.get('schema_policy')).get('allowed_states')))}`",
            "- Versioning: ogni correzione futura deve creare una nuova versione, non modificare in-place.",
            "- Superseding: una decisione puo' superarne un'altra solo con collegamento esplicito.",
            "",
            "## Decisioni",
            "",
        ]
    )
    decisions = list_items(payload.get("review_decisions"))
    if not decisions:
        lines.extend(["_Nessuna decisione nella preview._", ""])
    for decision in decisions:
        lines.extend(
            [
                f"### {decision.get('decision_id', '')}",
                "",
                f"- Versione: `{decision.get('version', '')}`",
                f"- Stato: `{decision.get('state', '')}`",
                f"- Ambito: `{decision.get('decision_scope', '')}`",
                f"- Profilo: `{decision.get('profile_id', '')}`",
                f"- Documento: `{decision.get('source_document_id', '')}`",
                f"- Record sorgente: `{decision.get('source_record_id', '')}`",
                "",
            ]
        )
    lines.extend(["## Conflitti", ""])
    conflicts = list_items(payload.get("conflicts"))
    if not conflicts:
        lines.extend(["_Nessun conflitto aperto nella preview._", ""])
    for conflict in conflicts:
        lines.append(
            f"- `{conflict.get('conflict_id', '')}` stato `{conflict.get('state', '')}` "
            f"profilo `{conflict.get('profile_id', '')}` policy `{conflict.get('resolution_policy', '')}`"
        )
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Output automatico preview-only.",
            "- Non scrive nello evidence store.",
            "- Non crea tabelle canoniche.",
            "- Non crea fatti canonici.",
            "- Non modifica profili JSON-LD.",
            "- Non applica ProfilePatch.",
            "",
        ]
    )
    return "\n".join(lines)


def _conflict_entry(conflict: dict[str, Any], *, decision_ids_by_record: dict[str, str]) -> dict[str, Any]:
    source_record = str(conflict.get("source_decision_record_id", "")).strip()
    linked = [decision_ids_by_record[source_record]] if source_record in decision_ids_by_record else []
    return {
        "@type": "ConflictCaseStoreEntryPreview",
        "conflict_id": str(conflict.get("conflict_id") or f"conflict-preview:{_slug(source_record)}").strip(),
        "state": str(conflict.get("normalized_state") or "conflict_open").strip(),
        "resolution_policy": str(conflict.get("resolution_policy") or "requires_human_review").strip(),
        "linked_decision_ids": linked,
        "profile_id": str(conflict.get("profile_id", "")).strip(),
        "source_document_id": str(conflict.get("source_document_id", "")).strip(),
        "source_record_id": source_record,
        "source_run_id": str(conflict.get("source_run_id", "")).strip(),
        "provenance": dict_object(conflict.get("provenance")),
    }


def _schema_policy() -> dict[str, Any]:
    return {
        "allowed_states": ALLOWED_STATES,
        "terminal_states": TERMINAL_STATES,
        "open_states": OPEN_STATES,
        "versioning_policy": "append_only_versions_no_in_place_mutation",
        "superseding_policy": "requires_explicit_supersedes_or_superseded_by_links",
        "conflict_resolution_policy": "requires_human_review",
        "canonicalization_status": "preview_schema_not_canonical_store",
    }


def _state_coverage(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(decision.get("state", "unknown")).strip() or "unknown" for decision in decisions)
    counts_by_state = {state: counts.get(state, 0) for state in ALLOWED_STATES}
    return {
        "counts_by_state": counts_by_state,
        "terminal_decision_count": sum(counts.get(state, 0) for state in TERMINAL_STATES),
        "open_decision_count": sum(counts.get(state, 0) for state in OPEN_STATES),
        "unknown_state_count": counts_by_state.get("unknown", 0),
        "missing_reviewer_count": sum(1 for decision in decisions if not str(decision.get("reviewer", "")).strip()),
        "missing_reviewed_at_count": sum(1 for decision in decisions if not str(decision.get("reviewed_at", "")).strip()),
    }


def _validate_evidence_records(*, evidence_db: Path | None, source_run_ids: list[str], record_ids: list[str]) -> dict[str, Any]:
    if evidence_db is None:
        return {"status": "not_requested", "checked_record_count": 0, "missing_record_ids": []}
    if not evidence_db.is_file():
        raise FileNotFoundError(f"Evidence DB non trovato: {evidence_db}")
    if not source_run_ids:
        raise ValueError("Specificare almeno un evidence_source_run_id quando si passa evidence_db.")
    unique_record_ids = unique_non_empty(record_ids)
    if not unique_record_ids:
        return {"status": "checked", "checked_record_count": 0, "present_record_count": 0, "missing_record_ids": []}
    uri = evidence_db.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        placeholders_records = ",".join("?" for _ in unique_record_ids)
        placeholders_runs = ",".join("?" for _ in source_run_ids)
        rows = connection.execute(
            f"""
            SELECT record_id
            FROM evidence_records
            WHERE record_id IN ({placeholders_records})
              AND source_run_id IN ({placeholders_runs})
            """,
            tuple(unique_record_ids + source_run_ids),
        ).fetchall()
    present = {str(row[0]) for row in rows}
    missing = [record_id for record_id in unique_record_ids if record_id not in present]
    return {
        "status": "checked",
        "checked_record_count": len(unique_record_ids),
        "present_record_count": len(present),
        "missing_record_ids": missing,
    }

def _slug(value: str) -> str:
    text = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in text.split("-") if part) or "record"


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera una preview read-only del review store versionato.")
    parser.add_argument("--review-register-json", required=True)
    parser.add_argument("--evidence-db", default="")
    parser.add_argument("--evidence-source-run-id", action="append", default=[])
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    evidence_db = Path(args.evidence_db) if str(args.evidence_db).strip() else None
    try:
        payload = build_review_store_preview(
            review_register_json=Path(args.review_register_json),
            evidence_db=evidence_db,
            evidence_source_run_id=args.evidence_source_run_id,
            profile_id=args.profile_id,
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            limit=args.limit,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(str(exc))
        return 2
    print(f"Review store preview: {args.output_md}")
    print(f"Decisioni: {payload['decision_count']}")
    print(f"Conflitti: {payload['conflict_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
