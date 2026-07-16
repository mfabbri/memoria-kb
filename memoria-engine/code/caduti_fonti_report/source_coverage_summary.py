from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DETAIL_ASSESSMENTS = {
    "detail_document_fetched",
    "detail_document_from_cache",
    "detail_document_reference",
}


def build_source_coverage_summary(
    *,
    input_json: list[Path],
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    reports = [_load_json_object(path) for path in input_json]
    entries = _collect_entries(reports)
    source_summaries = _summarize_sources(entries)
    profile_summaries = _summarize_profiles(entries)
    summary: dict[str, Any] = {
        "@type": "SourceCoverageSummary",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_report_json": [str(path) for path in input_json],
        "report_count": len(input_json),
        "entry_count": len(entries),
        "source_count": len(source_summaries),
        "profile_count": len(profile_summaries),
        "publication_status": "not_publishable_without_human_review",
        "review_status": "unreviewed",
        "sources": source_summaries,
        "profiles": profile_summaries,
        "entries": entries,
        "warnings": [
            "Il riepilogo misura copertura operativa, non assenza o presenza storica.",
            "Le pagine risultato non producono fatti storici.",
            "Nessun claim candidato viene promosso a fatto verificato.",
        ],
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_source_coverage_markdown(summary), encoding="utf-8")
    return summary


def render_source_coverage_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Source coverage summary",
        "",
        f"- Report analizzati: `{summary.get('report_count', 0)}`",
        f"- Profili: `{summary.get('profile_count', 0)}`",
        f"- Fonti: `{summary.get('source_count', 0)}`",
        f"- Voci fonte-profilo: `{summary.get('entry_count', 0)}`",
        f"- Stato revisione: `{summary.get('review_status', '')}`",
        f"- Stato pubblicazione: `{summary.get('publication_status', '')}`",
        "",
        "## Copertura per fonte",
        "",
    ]
    sources = _list_items(summary.get("sources"))
    if not sources:
        lines.append("_Nessuna fonte riepilogata._")
    for source in sources:
        lines.extend(
            [
                f"### {source.get('source_id', '')}",
                "",
                f"- Profili coperti: `{source.get('profile_count', 0)}`",
                f"- Risultati candidati: `{source.get('candidate_profile_count', 0)}`",
                f"- Profili con dettaglio: `{source.get('detail_profile_count', 0)}`",
                f"- Profili solo no results: `{source.get('no_results_profile_count', 0)}`",
                f"- Hit: `{source.get('hit_count', 0)}`",
                f"- Documenti: `{source.get('document_count', 0)}`",
                f"- Claim candidati: `{source.get('claim_count', 0)}`",
                f"- Azione consigliata: {source.get('recommended_action', '')}",
                "",
            ]
        )
        statuses = source.get("statuses")
        if isinstance(statuses, dict) and statuses:
            lines.append("Stati:")
            lines.extend(f"- `{status}`: {count}" for status, count in sorted(statuses.items()))
            lines.append("")

    lines.extend(["## Profili prioritari", ""])
    priority_profiles = [
        profile
        for profile in _list_items(summary.get("profiles"))
        if profile.get("recommended_action") in {"review_detail_documents", "review_candidate_results"}
    ]
    if not priority_profiles:
        lines.append("_Nessun profilo prioritario emerso dai report analizzati._")
    for profile in priority_profiles:
        lines.append(
            f"- `{profile.get('profile_id', '')}` {profile.get('canonical_name', '')}: "
            f"{profile.get('recommended_action', '')} "
            f"(hit={profile.get('hit_count', 0)}, documenti={profile.get('document_count', 0)}, "
            f"claim={profile.get('claim_count', 0)})"
        )
    lines.extend(["", "## Tutte le voci", ""])
    entries = _list_items(summary.get("entries"))
    if not entries:
        lines.append("_Nessuna voce fonte-profilo._")
    for entry in entries:
        lines.append(
            "- "
            f"`{entry.get('profile_id', '')}` / `{entry.get('source_id', '')}` "
            f"status=`{entry.get('status', '')}` "
            f"hit=`{entry.get('hit_count', 0)}` "
            f"documenti=`{entry.get('document_count', 0)}` "
            f"dettagli=`{entry.get('detail_document_count', 0)}` "
            f"azione={entry.get('recommended_action', '')}"
        )
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Questo report non interroga fonti live.",
            "- Questo report non modifica profili o cache.",
            "- Questo report non crea `verified_facts`.",
            "",
        ]
    )
    return "\n".join(lines)


def _collect_entries(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for report in reports:
        for profile in _list_items(report.get("profiles")):
            profile_id = str(profile.get("profile_id", ""))
            canonical_name = str(profile.get("canonical_name", ""))
            for result_entry in _list_items(profile.get("results")):
                result = result_entry.get("result")
                if not isinstance(result, dict):
                    continue
                documents = _list_items(result_entry.get("documents"))
                claims = _list_items(result_entry.get("claims"))
                status = str(result.get("status", ""))
                source_id = str(result.get("source_id", ""))
                hits = _list_items(result.get("hits"))
                detail_documents = [document for document in documents if _is_detail_document(document)]
                entry = {
                    "@type": "SourceCoverageEntry",
                    "profile_id": profile_id,
                    "canonical_name": canonical_name,
                    "source_id": source_id,
                    "source_name": str(result.get("source_name", "")),
                    "status": status,
                    "query": str(result.get("query", "")),
                    "search_url": str(result.get("search_url", "")),
                    "hit_count": len(hits),
                    "document_count": len(documents),
                    "detail_document_count": len(detail_documents),
                    "claim_count": len(claims),
                    "planned_attempt_status": str(result_entry.get("matched_planned_attempt_status", "")),
                    "planned_attempt_id": str(result_entry.get("matched_planned_attempt_id", "")),
                    "review_status": "unreviewed",
                    "publication_status": "not_publishable_without_human_review",
                }
                entry["recommended_action"] = _recommended_action(entry)
                entries.append(entry)
    return entries


def _summarize_sources(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_source.setdefault(str(entry.get("source_id", "")), []).append(entry)
    summaries: list[dict[str, Any]] = []
    for source_id, source_entries in sorted(by_source.items()):
        profile_ids = {str(entry.get("profile_id", "")) for entry in source_entries if entry.get("profile_id")}
        candidate_profiles = {
            str(entry.get("profile_id", ""))
            for entry in source_entries
            if str(entry.get("status", "")) == "candidate_results"
        }
        detail_profiles = {
            str(entry.get("profile_id", ""))
            for entry in source_entries
            if int(entry.get("detail_document_count", 0)) > 0
        }
        no_results_profiles = {
            str(entry.get("profile_id", ""))
            for entry in source_entries
            if str(entry.get("status", "")) == "no_results"
        }
        statuses = Counter(str(entry.get("status", "")) for entry in source_entries)
        source_summary = {
            "@type": "SourceCoverageBySource",
            "source_id": source_id,
            "source_name": _first_non_empty(source_entries, "source_name"),
            "profile_count": len(profile_ids),
            "candidate_profile_count": len(candidate_profiles),
            "detail_profile_count": len(detail_profiles),
            "no_results_profile_count": len(no_results_profiles),
            "hit_count": sum(int(entry.get("hit_count", 0)) for entry in source_entries),
            "document_count": sum(int(entry.get("document_count", 0)) for entry in source_entries),
            "detail_document_count": sum(int(entry.get("detail_document_count", 0)) for entry in source_entries),
            "claim_count": sum(int(entry.get("claim_count", 0)) for entry in source_entries),
            "statuses": dict(sorted(statuses.items())),
            "review_status": "unreviewed",
        }
        source_summary["recommended_action"] = _recommended_action(source_summary)
        summaries.append(source_summary)
    return summaries


def _summarize_profiles(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_profile: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_profile.setdefault(str(entry.get("profile_id", "")), []).append(entry)
    summaries: list[dict[str, Any]] = []
    for profile_id, profile_entries in sorted(by_profile.items()):
        statuses = Counter(str(entry.get("status", "")) for entry in profile_entries)
        profile_summary = {
            "@type": "SourceCoverageByProfile",
            "profile_id": profile_id,
            "canonical_name": _first_non_empty(profile_entries, "canonical_name"),
            "source_count": len({str(entry.get("source_id", "")) for entry in profile_entries if entry.get("source_id")}),
            "hit_count": sum(int(entry.get("hit_count", 0)) for entry in profile_entries),
            "document_count": sum(int(entry.get("document_count", 0)) for entry in profile_entries),
            "detail_document_count": sum(int(entry.get("detail_document_count", 0)) for entry in profile_entries),
            "claim_count": sum(int(entry.get("claim_count", 0)) for entry in profile_entries),
            "statuses": dict(sorted(statuses.items())),
            "review_status": "unreviewed",
        }
        profile_summary["recommended_action"] = _recommended_action(profile_summary)
        summaries.append(profile_summary)
    return summaries


def _is_detail_document(document: dict[str, Any]) -> bool:
    metadata = document.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    assessment = str(metadata.get("detail_assessment", ""))
    access_mode = str(metadata.get("access_mode", ""))
    source_result_status = str(metadata.get("source_result_status", ""))
    if assessment in DETAIL_ASSESSMENTS:
        return True
    if access_mode in {"detail_page", "authenticated_detail_cache"}:
        return True
    return bool(document.get("url")) and source_result_status not in {"no_results", "search_url_ready"}


def _recommended_action(entry: dict[str, Any]) -> str:
    status = str(entry.get("status", ""))
    statuses = entry.get("statuses")
    statuses = statuses if isinstance(statuses, dict) else {}
    if int(entry.get("detail_document_count", 0)) > 0 or int(entry.get("claim_count", 0)) > 0:
        return "review_detail_documents"
    if int(entry.get("hit_count", 0)) > 0 or status == "candidate_results" or int(statuses.get("candidate_results", 0)) > 0:
        return "review_candidate_results"
    if status == "no_results" or int(entry.get("no_results_profile_count", 0)) > 0 or int(statuses.get("no_results", 0)) > 0:
        return "try_other_sources_or_queries"
    if status in {"needs_credentials", "blocked_or_dynamic"} or any(
        int(statuses.get(value, 0)) > 0 for value in ("needs_credentials", "blocked_or_dynamic")
    ):
        return "check_authenticated_access"
    if status == "error" or int(statuses.get("error", 0)) > 0 or int(entry.get("validation_error_count", 0)) > 0:
        return "inspect_error"
    return "manual_review"


def _first_non_empty(entries: list[dict[str, Any]], key: str) -> str:
    for entry in entries:
        value = str(entry.get(key, "")).strip()
        if value:
            return value
    return ""


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un riepilogo di copertura fonte-profilo da report JSON.")
    parser.add_argument("--input-json", action="append", required=True, help="Report JSON prodotto da run_profiles_meta_search.")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    input_json = [Path(path) for path in args.input_json]
    output_base = input_json[0].parent if input_json else Path("risultati")
    output_json = Path(args.output_json) if args.output_json else output_base / "source_coverage_summary.json"
    output_md = Path(args.output_md) if args.output_md else output_base / "source_coverage_summary.md"
    summary = build_source_coverage_summary(input_json=input_json, output_json=output_json, output_md=output_md)
    print(f"Source coverage summary: {output_md}")
    print(f"Report: {summary['report_count']}")
    print(f"Profili: {summary['profile_count']}")
    print(f"Fonti: {summary['source_count']}")
    print(f"Voci: {summary['entry_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
