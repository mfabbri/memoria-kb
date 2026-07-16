from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_SOURCES = ("storia_memoria_bo", "partigiani_italia")
ARCHIVAL_SOURCES = ("bundesarchiv_invenio",)
SUPPORTING_MENTION_KINDS = {"formation", "archival_reference", "place", "date"}


def build_document_research_feedback_actions(
    *,
    mentions_dir: Path,
    output_dir: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
    mention_paths: list[Path] | None = None,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    paths = sorted(mention_paths) if mention_paths is not None else sorted(mentions_dir.rglob("*.mentions.json"))
    for mentions_path in paths:
        payload = _load_json_object(mentions_path)
        skip_reason = _skip_reason(payload=payload)
        if skip_reason:
            skipped.append(_skip_record(payload=payload, mentions_path=mentions_path, reason=skip_reason))
            continue

        actions = _actions_for_document(payload=payload, mentions_path=mentions_path)
        document_entry = {
            "@type": "ResearchFeedbackActionDocument",
            "source_id": str(payload.get("source_id", "")),
            "source_document_id": str(payload.get("source_document_id", "")),
            "mentions_file": str(mentions_path),
            "review_status": "unreviewed",
            "action_count": len(actions),
            "actions": actions,
        }
        documents.append(document_entry)
        if output_dir is not None:
            action_path = output_dir / _actions_relative_path(document_entry)
            action_path.parent.mkdir(parents=True, exist_ok=True)
            action_path.write_text(json.dumps(document_entry, ensure_ascii=False, indent=2), encoding="utf-8")

    action_count = sum(int(document.get("action_count", 0) or 0) for document in documents)
    result = {
        "@type": "ResearchFeedbackActionSet",
        "mentions_dir": str(mentions_dir),
        "output_dir": str(output_dir or ""),
        "generation_method": "deterministic_research_feedback_action_rules",
        "document_count": len(documents),
        "action_count": action_count,
        "skipped_count": len(skipped),
        "documents": documents,
        "skipped_documents": skipped,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_research_feedback_actions_markdown(result), encoding="utf-8")
    return result


def render_research_feedback_actions_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# ResearchFeedbackAction preview",
        "",
        f"- Metodo: `{payload.get('generation_method', '')}`",
        f"- Documenti processati: `{payload.get('document_count', 0)}`",
        f"- Azioni candidate: `{payload.get('action_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Azioni candidate",
        "",
    ]
    documents = payload.get("documents", [])
    if not isinstance(documents, list) or not documents:
        lines.append("_Nessuna azione candidata generata._")
    else:
        for document in documents:
            if not isinstance(document, dict):
                continue
            lines.extend(
                [
                    f"### {document.get('source_document_id', '')}",
                    "",
                    f"- Fonte: `{document.get('source_id', '')}`",
                    f"- Stato revisione: `{document.get('review_status', '')}`",
                    f"- Azioni: `{document.get('action_count', 0)}`",
                    f"- Menzioni: `{document.get('mentions_file', '')}`",
                    "",
                ]
            )
            for action in document.get("actions", []):
                if not isinstance(action, dict):
                    continue
                sources = ", ".join(str(source) for source in action.get("suggested_sources", []))
                lines.append(
                    f"- `{action.get('action_id', '')}` | "
                    f"{action.get('value', '')} | "
                    f"priority `{action.get('priority', '')}` | "
                    f"risk `{action.get('risk', '')}` | "
                    f"sources `{sources}`"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _actions_for_document(*, payload: dict[str, Any], mentions_path: Path) -> list[dict[str, Any]]:
    mentions = [mention for mention in payload.get("mentions", []) if isinstance(mention, dict)]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for mention in mentions:
        key = "|".join(
            [
                str(mention.get("source_document_id", "")),
                str(mention.get("chunk_id", "")),
            ]
        )
        grouped.setdefault(key, []).append(mention)

    actions: list[dict[str, Any]] = []
    for group_mentions in grouped.values():
        people = [mention for mention in group_mentions if str(mention.get("mention_kind", "")) == "person"]
        supporting = [
            mention
            for mention in group_mentions
            if str(mention.get("mention_kind", "")) in SUPPORTING_MENTION_KINDS
        ]
        if not people or not supporting:
            continue
        for person in people:
            same_segment_support = [
                mention for mention in supporting if str(mention.get("weak_segment_id", "")) == str(person.get("weak_segment_id", ""))
            ]
            scoped_support = same_segment_support or supporting
            support_scope = "same_segment" if same_segment_support else "same_chunk"
            actions.append(
                _action_candidate(
                    person=person,
                    supporting=scoped_support,
                    mentions_path=mentions_path,
                    support_scope=support_scope,
                )
            )
    return _deduplicate_actions(actions)


def _action_candidate(
    *,
    person: dict[str, Any],
    supporting: list[dict[str, Any]],
    mentions_path: Path,
    support_scope: str,
) -> dict[str, Any]:
    support_kinds = sorted({str(mention.get("mention_kind", "")) for mention in supporting})
    source_document_id = str(person.get("source_document_id", ""))
    weak_segment_id = str(person.get("weak_segment_id", ""))
    chunk_id = str(person.get("chunk_id", ""))
    value = str(person.get("value", ""))
    confidence = _bounded_confidence([person, *supporting])
    suggested_hints = [{"field": "person_name", "value": value, "source": "person_mention_candidate"}]
    for support in supporting:
        kind = str(support.get("mention_kind", ""))
        suggested_hints.append(
            {
                "field": kind,
                "value": str(support.get("value", "")),
                "source": f"{kind}_mention_candidate",
            }
        )
    suggested_sources = list(DEFAULT_SOURCES)
    risk = "medium"
    if "archival_reference" in support_kinds:
        suggested_sources.extend(source for source in ARCHIVAL_SOURCES if source not in suggested_sources)
        risk = "high"
    action_id = _action_id(
        source_document_id=source_document_id,
        weak_segment_id=weak_segment_id,
        chunk_id=chunk_id,
        normalized_value=str(person.get("normalized_value", "")),
        support_kinds=support_kinds,
    )
    return {
        "@type": "ResearchFeedbackAction",
        "@id": action_id,
        "action_id": action_id,
        "trigger_type": "weak_candidate",
        "action_kind": "request_source_specific_search",
        "source_candidate_id": str(person.get("mention_id", "")),
        "supporting_candidate_ids": [str(mention.get("mention_id", "")) for mention in supporting],
        "person_id": str(person.get("candidate_profile_id", "")),
        "field": "research.search_hint",
        "value": value,
        "source_id": str(person.get("source_id", "")),
        "source_document_id": source_document_id,
        "mentions_file": str(mentions_path),
        "chunk_id": chunk_id,
        "weak_segment_id": weak_segment_id,
        "context": {
            "quote": str(person.get("context", "")),
            "confidence": confidence,
            "support_scope": support_scope,
            "warnings": _dedupe([*_string_list(person.get("warnings", [])), *_support_warnings(supporting)]),
        },
        "suggested_search_hints": suggested_hints,
        "suggested_sources": suggested_sources,
        "priority": "medium",
        "risk": risk,
        "reasons": [f"person_mention_with_{kind}" for kind in support_kinds],
        "warnings": [
            "research_feedback_action_not_verified_fact",
            "requires_human_review_before_search",
            f"support_scope:{support_scope}",
        ],
        "generation_method": "deterministic_research_feedback_action_rules",
        "review_status": "unreviewed",
    }


def _skip_reason(*, payload: dict[str, Any]) -> str:
    if not payload:
        return "mentions_unreadable"
    if str(payload.get("@type", "")) != "DocumentMentionCandidateDocument":
        return "unsupported_payload_type"
    mentions = payload.get("mentions", [])
    if not isinstance(mentions, list):
        return "mentions_not_list"
    return ""


def _skip_record(*, payload: dict[str, Any], mentions_path: Path, reason: str) -> dict[str, str]:
    return {
        "source_document_id": str(payload.get("source_document_id", "")) if payload else "",
        "mentions_file": str(mentions_path),
        "reason": reason,
    }


def _deduplicate_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for action in actions:
        action_id = str(action.get("action_id", ""))
        if action_id in seen:
            continue
        seen.add(action_id)
        deduped.append(action)
    return deduped


def _actions_relative_path(document: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(document.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(document.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.research-feedback-actions.json"


def _action_id(
    *,
    source_document_id: str,
    weak_segment_id: str,
    chunk_id: str,
    normalized_value: str,
    support_kinds: list[str],
) -> str:
    digest = hashlib.sha256(
        f"{source_document_id}|{weak_segment_id}|{chunk_id}|{normalized_value}|{','.join(support_kinds)}".encode(
            "utf-8"
        )
    ).hexdigest()[:16]
    return f"research-feedback-action:{digest}"


def _bounded_confidence(mentions: list[dict[str, Any]]) -> float:
    values: list[float] = []
    for mention in mentions:
        try:
            values.append(float(mention.get("confidence", 0.0)))
        except (TypeError, ValueError):
            continue
    if not values:
        return 0.25
    return round(max(0.0, min(min(values), 0.99)), 2)


def _support_warnings(supporting: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for mention in supporting:
        warnings.extend(_string_list(mention.get("warnings", [])))
    return warnings


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = str(value).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera ResearchFeedbackAction preview-only da DocumentMentionCandidate.")
    parser.add_argument("--mentions-dir", default="data/processed/documents")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/research_feedback_actions.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/research_feedback_actions.md")
    args = parser.parse_args()

    payload = build_document_research_feedback_actions(
        mentions_dir=Path(args.mentions_dir),
        output_dir=Path(args.output_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"ResearchFeedbackAction JSON scritto in {args.output_json}")
    print(f"ResearchFeedbackAction Markdown scritto in {args.output_md}")
    print(f"Documenti processati: {payload['document_count']}")
    print(f"Azioni candidate: {payload['action_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
