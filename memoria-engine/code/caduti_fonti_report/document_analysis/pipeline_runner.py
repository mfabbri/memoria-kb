from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from ..profiles_runner import run_profiles_report
from ..knowledge_catalog import default_places_index_path
from .candidate_claims import build_candidate_document_claims
from .document_clusters import find_document_clusters
from .document_duplicates import find_candidate_duplicate_documents
from .document_quality import assess_document_quality
from .entity_extraction import extract_document_entities
from .feedback_search_plan import build_feedback_search_plan
from .mvp_pilot_summary import build_mvp_pilot_summary
from .person_linking import build_candidate_document_person_links
from .place_linking import build_candidate_document_place_links
from .research_feedback_actions import build_document_research_feedback_actions


def run_document_research_pipeline(
    *,
    run_id: str,
    processed_dir: Path,
    results_dir: Path,
    research_dir: Path = Path("ricerche"),
    profiles_index: Path | None = None,
    sources_yaml: Path | None = None,
    places_index: Path | None = None,
    profile_id: str = "",
    source_id: str = "",
    limit: int = 0,
    skip_online: bool = False,
    include_search_plan: bool = False,
    execute_first_planned_attempt: bool = False,
    acquire_documents_root: Path | None = None,
    similarity_threshold: float = 0.86,
) -> dict[str, Any]:
    resolved_profiles_index = profiles_index or research_dir / "person_profiles" / "purocielo.index.jsonld"
    resolved_sources_yaml = sources_yaml or research_dir / "camalanca_fonti.yaml"
    resolved_places_index = places_index or default_places_index_path(research_dir)
    resolved_run_id = run_id.strip() or _default_run_id()
    run_dir = results_dir / "runs" / resolved_run_id
    document_dir = run_dir / "document_analysis"
    online_dir = run_dir / "online"
    document_dir.mkdir(parents=True, exist_ok=True)
    if not skip_online:
        online_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "run.log"
    logger = _RunLogger(log_path)
    started_at = _now()

    manifest: dict[str, Any] = {
        "@type": "DocumentResearchRunManifest",
        "run_id": resolved_run_id,
        "started_at": started_at,
        "finished_at": "",
        "status": "running",
        "inputs": {
            "processed_dir": str(processed_dir),
            "research_dir": str(research_dir),
            "profiles_index": str(resolved_profiles_index),
            "sources_yaml": str(resolved_sources_yaml),
            "places_index": str(resolved_places_index),
            "profile_id": profile_id,
            "source_id": source_id,
            "limit": limit,
            "skip_online": skip_online,
            "include_search_plan": include_search_plan,
            "execute_first_planned_attempt": execute_first_planned_attempt,
            "acquire_documents_root": str(acquire_documents_root) if acquire_documents_root is not None else "",
            "similarity_threshold": similarity_threshold,
        },
        "outputs": {
            "run_dir": str(run_dir),
            "document_analysis_dir": str(document_dir),
            "online_dir": "" if skip_online else str(online_dir),
            "run_log": str(log_path),
        },
        "steps": [],
    }
    logger.write(f"RUN START document_research_pipeline run_id={resolved_run_id}")
    logger.write(f"ProcessedDir={processed_dir}")
    logger.write(f"ResultsDir={results_dir}")

    context: dict[str, Any] = {}
    _run_step(
        manifest,
        name="document_quality",
        output_paths=[document_dir / "document_quality_assessment.json"],
        body=lambda: _quality_step(
            processed_dir=processed_dir,
            output_json=document_dir / "document_quality_assessment.json",
            progress_callback=lambda message: logger.write(f"STEP PROGRESS document_quality {message}"),
        ),
        context=context,
        logger=logger,
    )
    _run_step(
        manifest,
        name="candidate_document_person_links",
        output_paths=[
            document_dir / "candidate_document_person_links.json",
            document_dir / "candidate_document_person_links.md",
        ],
        body=lambda: build_candidate_document_person_links(
            text_dir=processed_dir,
            metadata_dir=processed_dir,
            profiles_index=resolved_profiles_index,
            output_json=document_dir / "candidate_document_person_links.json",
            output_md=document_dir / "candidate_document_person_links.md",
        ),
        context=context,
        logger=logger,
    )
    _run_step(
        manifest,
        name="extracted_entities",
        output_paths=[document_dir / "extracted_entities.json", document_dir / "extracted_entities.md"],
        body=lambda: extract_document_entities(
            text_dir=processed_dir,
            metadata_dir=processed_dir,
            output_json=document_dir / "extracted_entities.json",
            output_md=document_dir / "extracted_entities.md",
        ),
        context=context,
        logger=logger,
    )
    _run_step(
        manifest,
        name="candidate_evidence_claims",
        output_paths=[document_dir / "candidate_evidence_claims.json", document_dir / "candidate_evidence_claims.md"],
        body=lambda: build_candidate_document_claims(
            entities_json=document_dir / "extracted_entities.json",
            links_json=document_dir / "candidate_document_person_links.json",
            quality_dir=processed_dir,
            sources_yaml=resolved_sources_yaml,
            output_json=document_dir / "candidate_evidence_claims.json",
            output_md=document_dir / "candidate_evidence_claims.md",
        ),
        context=context,
        logger=logger,
    )
    _run_step(
        manifest,
        name="candidate_duplicate_documents",
        output_paths=[
            document_dir / "candidate_duplicate_documents.json",
            document_dir / "candidate_duplicate_documents.md",
        ],
        body=lambda: find_candidate_duplicate_documents(
            metadata_dir=processed_dir,
            output_json=document_dir / "candidate_duplicate_documents.json",
            output_md=document_dir / "candidate_duplicate_documents.md",
        ),
        context=context,
        logger=logger,
    )
    _run_step(
        manifest,
        name="document_clusters",
        output_paths=[document_dir / "document_clusters.json", document_dir / "document_clusters.md"],
        body=lambda: find_document_clusters(
            text_dir=processed_dir,
            output_json=document_dir / "document_clusters.json",
            output_md=document_dir / "document_clusters.md",
            similarity_threshold=similarity_threshold,
        ),
        context=context,
        logger=logger,
    )
    _run_step(
        manifest,
        name="candidate_document_place_links",
        output_paths=[
            document_dir / "candidate_document_place_links.json",
            document_dir / "candidate_document_place_links.md",
        ],
        body=lambda: build_candidate_document_place_links(
            mentions_dir=processed_dir,
            places_index=resolved_places_index,
            output_json=document_dir / "candidate_document_place_links.json",
            output_md=document_dir / "candidate_document_place_links.md",
        ),
        context=context,
        logger=logger,
    )
    _run_step(
        manifest,
        name="research_feedback_actions",
        output_paths=[document_dir / "research_feedback_actions.json", document_dir / "research_feedback_actions.md"],
        body=lambda: build_document_research_feedback_actions(
            mentions_dir=processed_dir,
            output_dir=None,
            output_json=document_dir / "research_feedback_actions.json",
            output_md=document_dir / "research_feedback_actions.md",
        ),
        context=context,
        logger=logger,
    )
    _run_step(
        manifest,
        name="feedback_search_plan",
        output_paths=[document_dir / "feedback_search_plan.json", document_dir / "feedback_search_plan.md"],
        body=lambda: build_feedback_search_plan(
            actions_json=document_dir / "research_feedback_actions.json",
            links_json=document_dir / "candidate_document_person_links.json",
            profiles_index=resolved_profiles_index,
            sources_yaml=resolved_sources_yaml,
            output_json=document_dir / "feedback_search_plan.json",
            output_md=document_dir / "feedback_search_plan.md",
        ),
        context=context,
        logger=logger,
    )
    _run_step(
        manifest,
        name="mvp_pilot_summary",
        output_paths=[document_dir / "mvp_pilot_summary.json", document_dir / "mvp_pilot_summary.md"],
        body=lambda: build_mvp_pilot_summary(
            run_dir=run_dir,
            profiles_index=resolved_profiles_index,
            profile_ids=[profile_id] if profile_id.strip() else [],
            output_json=document_dir / "mvp_pilot_summary.json",
            output_md=document_dir / "mvp_pilot_summary.md",
        ),
        context=context,
        logger=logger,
    )

    if skip_online:
        _append_status_step(
            manifest,
            name="online_profile_search",
            status="skipped",
            reason="skip_online",
            logger=logger,
        )
    elif not profile_id.strip() or not source_id.strip() or limit <= 0:
        _append_status_step(
            manifest,
            name="online_profile_search",
            status="failed",
            reason="online_requires_explicit_profile_source_and_limit",
            error="Per abilitare l'online servono ProfileId, Source e Limit maggiore di 0.",
            logger=logger,
        )
    else:
        _run_step(
            manifest,
            name="online_profile_search",
            output_paths=[online_dir / "profiles_meta_search.json", online_dir / "profiles_meta_search.md"],
            body=lambda: run_profiles_report(
                profiles_index=resolved_profiles_index,
                sources_yaml=resolved_sources_yaml,
                output_json=online_dir / "profiles_meta_search.json",
                output_md=online_dir / "profiles_meta_search.md",
                output_dir=online_dir / "schede",
                limit=limit,
                source_id=source_id,
                profile_id=profile_id,
                include_search_plan=include_search_plan,
                execute_first_planned_attempt=execute_first_planned_attempt,
                acquire_documents_root=acquire_documents_root,
            ),
            context=context,
            logger=logger,
        )

    failed_steps = [step for step in manifest["steps"] if step.get("status") == "failed"]
    manifest["status"] = "failed" if failed_steps else "completed"
    manifest["finished_at"] = _now()
    manifest["outputs"]["manifest_json"] = str(run_dir / "manifest.json")
    manifest["outputs"]["run_summary_md"] = str(run_dir / "run_summary.md")
    manifest["outputs"]["mvp_pilot_summary_json"] = str(document_dir / "mvp_pilot_summary.json")
    manifest["outputs"]["mvp_pilot_summary_md"] = str(document_dir / "mvp_pilot_summary.md")
    logger.write(
        "RUN END document_research_pipeline "
        f"run_id={resolved_run_id} status={manifest['status']} duration={_duration_text(started_at, manifest['finished_at'])}"
    )

    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "run_summary.md").write_text(_render_run_summary(manifest), encoding="utf-8")
    return manifest


def _quality_step(
    *,
    processed_dir: Path,
    output_json: Path,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    payload = assess_document_quality(
        metadata_dir=processed_dir,
        text_dir=processed_dir,
        output_dir=processed_dir,
        progress_callback=progress_callback,
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _append_status_step(
    manifest: dict[str, Any],
    *,
    name: str,
    status: str,
    reason: str,
    error: str = "",
    logger: "_RunLogger | None" = None,
) -> None:
    started = _now()
    finished = _now()
    if logger is not None:
        logger.write(f"STEP START {name} inputs=0 outputs=0")
        logger.write(
            f"STEP END {name} status={status} duration={_duration_text(started, finished)} "
            f"reason={reason} error={error}"
        )
    step = {
        "name": name,
        "started_at": started,
        "finished_at": finished,
        "status": status,
        "reason": reason,
        "outputs": [],
    }
    if error:
        step["error"] = error
    manifest["steps"].append(step)


def _run_step(
    manifest: dict[str, Any],
    *,
    name: str,
    output_paths: list[Path],
    body: Callable[[], dict[str, Any]],
    context: dict[str, Any],
    logger: "_RunLogger | None" = None,
) -> None:
    step: dict[str, Any] = {
        "name": name,
        "started_at": _now(),
        "finished_at": "",
        "status": "running",
        "outputs": [str(path) for path in output_paths],
    }
    if logger is not None:
        logger.write(f"STEP START {name} outputs={len(output_paths)}")
    try:
        payload = body()
        step["status"] = _step_status_from_payload(payload)
        step["summary"] = _step_summary(payload)
        step["error"] = str(payload.get("error", "")) if isinstance(payload, dict) else ""
        context[name] = payload
    except Exception as exc:  # pragma: no cover - exercised through callers in integration.
        step["status"] = "failed"
        step["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        step["finished_at"] = _now()
        if logger is not None:
            logger.write(
                "STEP END "
                f"{name} status={step.get('status', '')} "
                f"duration={_duration_text(step['started_at'], step['finished_at'])} "
                f"reason={step.get('reason', '')} error={step.get('error', '')}"
            )
        manifest["steps"].append(step)


def _step_status_from_payload(payload: dict[str, Any]) -> str:
    if int(payload.get("exit_code", 0) or 0) != 0:
        return "failed"
    return "completed"


def _step_summary(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "document_count",
        "link_count",
        "entity_count",
        "claim_count",
        "duplicate_group_count",
        "cluster_count",
        "action_count",
        "plan_count",
        "profile_count",
        "candidate_document_person_link_count",
        "extracted_entity_count",
        "candidate_evidence_claim_count",
        "research_feedback_action_count",
        "feedback_search_plan_count",
        "skipped_count",
        "profiles_count",
        "sources_count",
        "acquired_documents_count",
    ]
    return {key: payload[key] for key in keys if key in payload}


def _render_run_summary(manifest: dict[str, Any]) -> str:
    lines = [
        "# Document research run",
        "",
        f"- Run ID: `{manifest.get('run_id', '')}`",
        f"- Stato: `{manifest.get('status', '')}`",
        f"- Processed dir: `{manifest.get('inputs', {}).get('processed_dir', '')}`",
        f"- Profili: `{manifest.get('inputs', {}).get('profiles_index', '')}`",
        f"- Online saltato: `{manifest.get('inputs', {}).get('skip_online', '')}`",
        "",
        "## Step",
        "",
    ]
    for step in manifest.get("steps", []):
        if not isinstance(step, dict):
            continue
        lines.append(f"- `{step.get('name', '')}`: `{step.get('status', '')}`")
        summary = step.get("summary", {})
        if isinstance(summary, dict) and summary:
            joined = ", ".join(f"{key}={value}" for key, value in summary.items())
            lines.append(f"  - Summary: {joined}")
        if step.get("error"):
            lines.append(f"  - Errore: {step.get('error')}")
    lines.extend(
        [
            "",
            f"MVP pilot summary: `{manifest.get('outputs', {}).get('mvp_pilot_summary_md', '')}`",
            "",
            "## Note operative",
            "",
            "- Gli output automatici restano candidati di revisione.",
            "- Nessun claim viene promosso a fatto verificato da questa run.",
            "- I profili JSON-LD reali non vengono modificati.",
            "",
        ]
    )
    return "\n".join(lines)


def _default_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class _RunLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        line = f"[{_now()}] {message}"
        print(line, flush=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _duration_text(started_at: str, finished_at: str) -> str:
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return ""
    return f"{(finished - started).total_seconds():.2f}s"


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue una run documentale/online ripetibile con manifest.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--processed-dir", default="data/processed/documents")
    parser.add_argument("--results-dir", "--remote-results-dir", dest="results_dir", default="risultati")
    parser.add_argument("--research-dir", default="ricerche")
    parser.add_argument("--profiles-index", default="")
    parser.add_argument("--sources-yaml", default="")
    parser.add_argument("--places-index", default="")
    parser.add_argument("--profile-id", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-online", action="store_true")
    parser.add_argument("--include-search-plan", action="store_true")
    parser.add_argument("--execute-first-planned-attempt", action="store_true")
    parser.add_argument("--acquire-documents-root", default="")
    parser.add_argument("--similarity-threshold", type=float, default=0.86)
    args = parser.parse_args()

    manifest = run_document_research_pipeline(
        run_id=args.run_id,
        processed_dir=Path(args.processed_dir),
        results_dir=Path(args.results_dir),
        research_dir=Path(args.research_dir),
        profiles_index=Path(args.profiles_index) if args.profiles_index else None,
        sources_yaml=Path(args.sources_yaml) if args.sources_yaml else None,
        places_index=Path(args.places_index) if args.places_index else None,
        profile_id=args.profile_id,
        source_id=args.source,
        limit=args.limit,
        skip_online=args.skip_online,
        include_search_plan=args.include_search_plan,
        execute_first_planned_attempt=args.execute_first_planned_attempt,
        acquire_documents_root=Path(args.acquire_documents_root) if args.acquire_documents_root else None,
        similarity_threshold=args.similarity_threshold,
    )
    print(f"Run documentale: {manifest['run_id']}")
    print(f"Stato: {manifest['status']}")
    print(f"Manifest: {manifest['outputs']['manifest_json']}")
    print(f"Summary: {manifest['outputs']['run_summary_md']}")
    return 0 if manifest["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
