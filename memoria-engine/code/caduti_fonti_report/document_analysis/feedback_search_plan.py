from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import load_source_registry
from ..planned_search_attempts import planned_search_attempts_to_dict
from ..profile_repository import ProfileRepository
from ..search_strategy_planner import plan_profile_search
from ..source_definitions import load_source_definition


def build_feedback_search_plan(
    *,
    actions_json: Path,
    profiles_index: Path,
    sources_yaml: Path,
    links_json: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    actions_payload = _load_json_object(actions_json)
    documents = actions_payload.get("documents", []) if isinstance(actions_payload, dict) else []
    if not isinstance(documents, list):
        documents = []

    source_registry = _load_sources_if_possible(sources_yaml)
    repository = ProfileRepository(profiles_index) if profiles_index.exists() else None
    repo_root = repo_root or _repo_root_from_sources_yaml(sources_yaml)
    links_by_document = _load_candidate_links_by_document(links_json)

    plans: list[dict[str, Any]] = []
    skipped_actions: list[dict[str, str]] = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        for action in document.get("actions", []):
            if not isinstance(action, dict):
                continue
            plan = _plan_for_action(
                action=action,
                repository=repository,
                source_registry=source_registry,
                sources_yaml=sources_yaml,
                repo_root=repo_root,
                links_by_document=links_by_document,
            )
            if plan.get("status") == "skipped":
                skipped_actions.append(
                    {
                        "action_id": str(action.get("action_id", "")),
                        "reason": str(plan.get("reason", "")),
                    }
                )
            plans.append(plan)

    result = {
        "@type": "FeedbackSearchPlanSet",
        "generated_at": datetime.now(UTC).isoformat(),
        "actions_json": str(actions_json),
        "links_json": str(links_json or ""),
        "profiles_index": str(profiles_index),
        "sources_yaml": str(sources_yaml),
        "generation_method": "deterministic_feedback_search_plan_preview",
        "review_status": "unreviewed",
        "execution_allowed": False,
        "online_search_started": False,
        "profile_write_allowed": False,
        "plan_count": len(plans),
        "skipped_count": len(skipped_actions),
        "plans": plans,
        "skipped_actions": skipped_actions,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_feedback_search_plan_markdown(result), encoding="utf-8")
    return result


def render_feedback_search_plan_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# FeedbackSearchPlan preview",
        "",
        f"- Metodo: `{payload.get('generation_method', '')}`",
        f"- Piani: `{payload.get('plan_count', 0)}`",
        f"- Azioni saltate: `{payload.get('skipped_count', 0)}`",
        f"- Stato revisione: `{payload.get('review_status', '')}`",
        f"- Ricerca online avviata: `{payload.get('online_search_started', False)}`",
        "",
        "## Piani",
        "",
    ]
    plans = payload.get("plans", [])
    if not isinstance(plans, list) or not plans:
        lines.append("_Nessun piano generato._")
    else:
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            lines.extend(
                [
                    f"### {plan.get('action_id', '')}",
                    "",
                    f"- Stato: `{plan.get('status', '')}`",
                    f"- Profilo: `{plan.get('profile_id', '')}`",
                    f"- Persona candidata: `{plan.get('person_name', '')}`",
                    f"- Revisione manuale: `{plan.get('manual_review_required', '')}`",
                    f"- Motivo: {plan.get('reason', '')}",
                    "",
                ]
            )
            source_plans = plan.get("source_plans", [])
            if isinstance(source_plans, list) and source_plans:
                lines.append("#### Fonti")
                lines.append("")
                for source_plan in source_plans:
                    if not isinstance(source_plan, dict):
                        continue
                    lines.append(
                        f"- `{source_plan.get('source_id', '')}`: "
                        f"`{source_plan.get('status', '')}`, "
                        f"tentativi `{source_plan.get('planned_attempt_count', 0)}`"
                    )
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _plan_for_action(
    *,
    action: dict[str, Any],
    repository: ProfileRepository | None,
    source_registry: dict[str, Any],
    sources_yaml: Path,
    repo_root: Path,
    links_by_document: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    action_id = str(action.get("action_id", ""))
    person_name = str(action.get("value", ""))
    resolution = _resolve_profile_from_candidate_links(action=action, links_by_document=links_by_document)
    profile_id = str(action.get("person_id", "")).strip() or str(resolution.get("profile_id", "")).strip()
    plan_id = _plan_id(action_id=action_id, profile_id=profile_id, person_name=person_name)
    base = {
        "@type": "FeedbackSearchPlan",
        "@id": plan_id,
        "feedback_search_plan_id": plan_id,
        "action_id": action_id,
        "source_candidate_id": str(action.get("source_candidate_id", "")),
        "supporting_candidate_ids": _string_list(action.get("supporting_candidate_ids", [])),
        "source_document_id": str(action.get("source_document_id", "")),
        "chunk_id": str(action.get("chunk_id", "")),
        "weak_segment_id": str(action.get("weak_segment_id", "")),
        "profile_id": profile_id,
        "person_name": person_name,
        "suggested_search_hints": action.get("suggested_search_hints", []),
        "review_status": "unreviewed",
        "execution_allowed": False,
        "online_search_started": False,
        "profile_write_allowed": False,
        "claim_extraction_allowed": False,
        "manual_review_required": True,
        "profile_resolution": resolution,
        "source_plans": [],
        "warnings": [
            "feedback_search_plan_preview_only",
            "requires_human_review_before_execution",
        ],
    }
    if not profile_id:
        return {
            **base,
            "status": "skipped",
            "reason": "manual_profile_resolution_required",
            "warnings": [*base["warnings"], *_resolution_warnings(resolution)],
        }
    if repository is None:
        return {
            **base,
            "status": "skipped",
            "reason": "profiles_index_unavailable",
            "warnings": [*base["warnings"], "profiles_index_not_read"],
        }

    profiles = repository.load_profiles(profile_id=profile_id, limit=1)
    if not profiles:
        return {
            **base,
            "status": "skipped",
            "reason": "profile_not_found",
            "warnings": [*base["warnings"], "person_id_not_found_in_profiles_index"],
        }

    profile = profiles[0]
    source_plans = []
    for source_id in _string_list(action.get("suggested_sources", [])):
        source = source_registry.get(source_id)
        if source is None:
            source_plans.append(
                {
                    "@type": "FeedbackSearchSourcePlan",
                    "source_id": source_id,
                    "status": "skipped",
                    "reason": "source_not_registered",
                    "planned_attempt_count": 0,
                    "planned_attempts": [],
                }
            )
            continue
        try:
            definition = load_source_definition(source, repo_root=repo_root)
            planned = plan_profile_search(profile=profile, source=source, source_definition=definition)
            source_plans.append(
                {
                    "@type": "FeedbackSearchSourcePlan",
                    "source_id": source_id,
                    "status": "planned",
                    "reason": "planned_from_person_research_profile",
                    "planned_attempt_count": len(planned),
                    "planned_attempts": planned_search_attempts_to_dict(planned),
                }
            )
        except Exception as exc:  # pragma: no cover - defensive for local operator inputs.
            source_plans.append(
                {
                    "@type": "FeedbackSearchSourcePlan",
                    "source_id": source_id,
                    "status": "skipped",
                    "reason": f"planning_error:{type(exc).__name__}",
                    "error": str(exc),
                    "planned_attempt_count": 0,
                    "planned_attempts": [],
                }
            )

    planned_count = sum(1 for source_plan in source_plans if source_plan.get("status") == "planned")
    return {
        **base,
        "status": "ready_for_review" if planned_count else "skipped",
        "reason": "planned_sources_require_review" if planned_count else "no_registered_sources_planned",
        "profile_source_file": profile.metadata.get("profile_source_file", ""),
        "source_plans": source_plans,
        "planned_source_count": planned_count,
        "sources_yaml": str(sources_yaml),
    }


def _load_candidate_links_by_document(links_json: Path | None) -> dict[str, list[dict[str, Any]]]:
    if links_json is None:
        return {}
    payload = _load_json_object(links_json)
    links = payload.get("candidate_document_person_links", []) if isinstance(payload, dict) else []
    if not isinstance(links, list):
        return {}
    by_document: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        if not isinstance(link, dict):
            continue
        document_id = str(link.get("source_document_id", "")).strip()
        if not document_id:
            continue
        by_document.setdefault(document_id, []).append(link)
    return by_document


def _resolve_profile_from_candidate_links(
    *,
    action: dict[str, Any],
    links_by_document: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    explicit_profile_id = str(action.get("person_id", "")).strip()
    if explicit_profile_id:
        return {
            "status": "explicit_person_id",
            "profile_id": explicit_profile_id,
            "method": "research_feedback_action_person_id",
            "warnings": [],
        }

    source_document_id = str(action.get("source_document_id", "")).strip()
    person_name = str(action.get("value", "")).strip()
    candidates = [
        link
        for link in links_by_document.get(source_document_id, [])
        if _normalize_name(str(link.get("matched_name", ""))) == _normalize_name(person_name)
    ]
    if not candidates:
        return {
            "status": "unresolved",
            "method": "candidate_document_person_link",
            "reason": "no_matching_candidate_document_person_link",
            "warnings": ["missing_person_id_no_profile_lookup"],
        }

    profile_ids = {str(candidate.get("profile_id", "")).strip() for candidate in candidates if str(candidate.get("profile_id", "")).strip()}
    if len(profile_ids) != 1:
        return {
            "status": "ambiguous",
            "method": "candidate_document_person_link",
            "reason": "multiple_matching_candidate_document_person_links",
            "candidate_link_ids": [str(candidate.get("@id", "")) for candidate in candidates],
            "candidate_profile_ids": sorted(profile_ids),
            "warnings": ["ambiguous_candidate_document_person_link_requires_review"],
        }

    candidate = _candidate_link_for_action(action=action, candidates=candidates)
    return {
        "status": "resolved",
        "method": "candidate_document_person_link",
        "reason": "unique_matching_candidate_document_person_link",
        "profile_id": str(candidate.get("profile_id", "")),
        "profile_source_file": str(candidate.get("profile_source_file", "")),
        "candidate_link_id": str(candidate.get("@id", "")),
        "matched_name": str(candidate.get("matched_name", "")),
        "match_kind": str(candidate.get("match_kind", "")),
        "score": candidate.get("score", 0),
        "review_status": str(candidate.get("review_status", "")) or "unreviewed",
        "warnings": ["resolved_from_candidate_document_person_link_preview_only"],
    }


def _candidate_link_for_action(*, action: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    weak_segment_id = str(action.get("weak_segment_id", "")).strip()
    if weak_segment_id:
        segment_candidates = [candidate for candidate in candidates if str(candidate.get("weak_segment_id", "")).strip() == weak_segment_id]
        if segment_candidates:
            return sorted(segment_candidates, key=lambda candidate: float(candidate.get("score", 0.0) or 0.0), reverse=True)[0]

    chunk_id = str(action.get("chunk_id", "")).strip()
    if chunk_id:
        chunk_candidates = [candidate for candidate in candidates if str(candidate.get("chunk_id", "")).strip() == chunk_id]
        if chunk_candidates:
            return sorted(chunk_candidates, key=lambda candidate: float(candidate.get("score", 0.0) or 0.0), reverse=True)[0]

    return sorted(candidates, key=lambda candidate: float(candidate.get("score", 0.0) or 0.0), reverse=True)[0]


def _resolution_warnings(resolution: dict[str, Any]) -> list[str]:
    warnings = _string_list(resolution.get("warnings", []))
    return warnings or ["missing_person_id_no_profile_lookup"]


def _load_sources_if_possible(sources_yaml: Path) -> dict[str, Any]:
    if not sources_yaml.exists():
        return {}
    try:
        return load_source_registry(sources_yaml)
    except Exception:
        return {}


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        if not path.exists() or not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_name(value: str) -> str:
    return " ".join("".join(ch.casefold() if ch.isalnum() else " " for ch in value).split())


def _plan_id(*, action_id: str, profile_id: str, person_name: str) -> str:
    digest = hashlib.sha256(f"{action_id}|{profile_id}|{person_name}".encode("utf-8")).hexdigest()[:16]
    return f"feedback-search-plan:{digest}"


def _repo_root_from_sources_yaml(sources_yaml: Path) -> Path:
    resolved = sources_yaml.resolve()
    if resolved.parent.name == "ricerche":
        return resolved.parent.parent
    return resolved.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera FeedbackSearchPlan preview-only da ResearchFeedbackAction.")
    parser.add_argument("--actions-json", default="risultati/document_analysis/research_feedback_actions.json")
    parser.add_argument("--links-json", default="")
    parser.add_argument("--profiles-index", required=True)
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml")
    parser.add_argument("--output-json", default="risultati/document_analysis/feedback_search_plan.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/feedback_search_plan.md")
    args = parser.parse_args()

    payload = build_feedback_search_plan(
        actions_json=Path(args.actions_json),
        links_json=Path(args.links_json) if args.links_json.strip() else None,
        profiles_index=Path(args.profiles_index),
        sources_yaml=Path(args.sources_yaml),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"FeedbackSearchPlan JSON scritto in {args.output_json}")
    print(f"FeedbackSearchPlan Markdown scritto in {args.output_md}")
    print(f"Piani: {payload['plan_count']}")
    print(f"Azioni saltate: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
