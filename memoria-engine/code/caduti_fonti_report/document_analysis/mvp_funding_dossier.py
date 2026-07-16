from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_mvp_funding_dossier(
    *,
    package_readiness_json: Path,
    summary_json: Path,
    review_decisions_summary_json: Path,
    curatorial_brief_md: Path | None = None,
    source_coverage_summary_json: Path | None = None,
    consolidated_ledger_json: Path | None = None,
    verified_facts_preview_json: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    readiness = _load_json_object(package_readiness_json)
    summary = _load_json_object(summary_json)
    review_summary = _load_json_object(review_decisions_summary_json)
    source_coverage = _load_json_object(source_coverage_summary_json) if source_coverage_summary_json is not None else {}
    consolidated_ledger = _load_json_object(consolidated_ledger_json) if consolidated_ledger_json is not None else {}
    verified_facts_preview = _load_json_object(verified_facts_preview_json) if verified_facts_preview_json is not None else {}
    brief_path = curatorial_brief_md or _default_brief_path(readiness)
    profile_readiness = _profile_readiness(readiness, summary)
    dossier = {
        "@type": "MvpFundingDossier",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_curator_review",
        "source_package_readiness_json": str(package_readiness_json),
        "source_summary_json": str(summary_json),
        "source_review_decisions_summary_json": str(review_decisions_summary_json),
        "source_curatorial_brief_md": str(brief_path) if brief_path is not None else "",
        "source_coverage_summary_json": str(source_coverage_summary_json) if source_coverage_summary_json is not None else "",
        "source_consolidated_ledger_json": str(consolidated_ledger_json) if consolidated_ledger_json is not None else "",
        **(
            {"source_verified_facts_preview_json": str(verified_facts_preview_json)}
            if verified_facts_preview_json is not None
            else {}
        ),
        "readiness_status": str(readiness.get("readiness_status", "")),
        "package_status": str(_dict_object(summary.get("pilot_package_scorecard")).get("package_status", "")),
        "profile_count": _integer(readiness.get("profile_count"), default=len(profile_readiness)),
        "ready_profile_count": _integer(readiness.get("ready_profile_count")),
        "publication_candidate_count": _integer(readiness.get("publication_candidate_count")),
        "review_queue_item_count": _integer(readiness.get("review_queue_item_count")),
        "pending_review_count": _integer(readiness.get("pending_review_count")),
        "blockers": _list_items(readiness.get("blockers")),
        "next_actions": _list_strings(readiness.get("next_actions")),
        "profiles": profile_readiness,
        "materials": _materials(readiness, brief_path),
        "signal_diagnostics": _dict_object(summary.get("mvp_signal_diagnostics")),
        "source_coverage": _funding_source_coverage(source_coverage),
        "step2_historical_raccordo": _step2_historical_raccordo(
            review_summary=review_summary,
            consolidated_ledger=consolidated_ledger,
            verified_facts_preview=verified_facts_preview,
            verified_facts_preview_json=verified_facts_preview_json,
        ),
        "review_session": _dict_object(review_summary.get("review_session")),
        "warnings": [
            "Dossier preview-only per demo e finanziamento.",
            "Non e' una scheda storica pubblicabile.",
            "Le decisioni storiche e curatorali restano manuali.",
        ],
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_funding_dossier_markdown(dossier), encoding="utf-8")
    return dossier


def render_mvp_funding_dossier_markdown(dossier: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_funding_dossier",
        f"review_status: {_yaml_value(dossier.get('review_status', 'unreviewed'))}",
        f"publication_status: {_yaml_value(dossier.get('publication_status', 'not_publishable_without_curator_review'))}",
        "---",
        "",
        "# Dossier finanziamento MVP Purocielo",
        "",
        "## Obiettivo culturale",
        "",
        "Archivio digitale verificabile dei caduti di Purocielo: un pacchetto pilota per mostrare metodo, materiali e stato della revisione umana.",
        "",
        "## Stato demo",
        "",
        f"- Readiness: `{dossier.get('readiness_status', '')}`",
        f"- Stato pacchetto: `{dossier.get('package_status', '')}`",
        f"- Profili pilota: `{dossier.get('profile_count', 0)}`",
        f"- Profili pronti per review: `{dossier.get('ready_profile_count', 0)}`",
        f"- Schede candidate: `{dossier.get('publication_candidate_count', 0)}`",
        f"- Item review queue: `{dossier.get('review_queue_item_count', 0)}`",
        f"- Decisioni pending: `{dossier.get('pending_review_count', 0)}`",
        "",
        "## Materiali disponibili",
        "",
    ]
    materials = _list_items(dossier.get("materials"))
    if materials:
        for item in materials:
            present = "si" if item.get("exists") else "no"
            lines.append(f"- `{item.get('label', '')}`: {present} - `{item.get('path', '')}`")
    else:
        lines.append("- Nessun materiale elencato.")
    lines.extend(["", "## Profili pilota", ""])
    profiles = _list_items(dossier.get("profiles"))
    if profiles:
        lines.extend(["| Profilo | Stato | Prossima azione |", "|---|---|---|"])
        for profile in profiles:
            label = str(profile.get("canonical_name") or profile.get("profile_id", ""))
            lines.append(
                f"| {label} | `{profile.get('readiness_status', '')}` | {profile.get('next_action', '')} |"
            )
    else:
        lines.append("_Nessun profilo pilota nel riepilogo._")
    lines.extend(["", "## Diagnostica segnale", ""])
    lines.extend(_signal_diagnostics_markdown(dossier.get("signal_diagnostics")))
    lines.extend(["", "## Copertura fonti", ""])
    lines.extend(_source_coverage_markdown(dossier.get("source_coverage")))
    lines.extend(["", "## Raccordo step 2 storico", ""])
    lines.extend(_step2_historical_raccordo_markdown(dossier.get("step2_historical_raccordo")))
    lines.extend(["", "## Blocchi e prossime azioni", ""])
    blockers = _list_items(dossier.get("blockers"))
    if blockers:
        for blocker in blockers:
            lines.append(f"- `{blocker.get('blocker_type', '')}`: {blocker.get('message', '')}")
    else:
        lines.append("- Nessun blocker pratico rilevato dal report di readiness.")
    next_actions = _list_strings(dossier.get("next_actions"))
    if next_actions:
        lines.extend(["", "### Prossime azioni", ""])
        lines.extend(f"- {action}" for action in next_actions)
    lines.extend(
        [
            "",
            "## Vincoli editoriali",
            "",
            "- Questo dossier e' generato automaticamente per demo e finanziamento.",
            "- Non e' una pubblicazione storica definitiva.",
            "- Nessun claim candidato viene trattato come fatto storico.",
            "- Nessun profilo JSON-LD canonico viene modificato.",
            "- Le schede candidate richiedono revisione curatoriale prima di qualunque uso pubblico.",
            "",
        ]
    )
    return "\n".join(lines)


def _step2_historical_raccordo(
    *,
    review_summary: dict[str, Any],
    consolidated_ledger: dict[str, Any],
    verified_facts_preview: dict[str, Any],
    verified_facts_preview_json: Path | None,
) -> dict[str, Any]:
    ledger_coverage = _dict_object(consolidated_ledger.get("evidence_store_coverage"))
    decision_file_coverage = _dict_object(review_summary.get("decision_file_coverage"))
    verified_facts_summary = _verified_facts_preview_summary(
        verified_facts_preview,
        source_path=verified_facts_preview_json,
    )
    raccordo = {
        "@type": "MvpStep2HistoricalRaccordo",
        "available": bool(review_summary or consolidated_ledger),
        "review_status": str(review_summary.get("review_status", "")),
        "decision_count": _integer(review_summary.get("decision_count")),
        "accepted_count": _integer(review_summary.get("accepted_count")),
        "pending_count": _integer(review_summary.get("pending_count")),
        "invalid_count": _integer(review_summary.get("invalid_count")),
        "validation_error_count": _integer(review_summary.get("validation_error_count")),
        "decision_file_coverage_status": str(decision_file_coverage.get("coverage_status", "")),
        "provided_decision_count": _integer(decision_file_coverage.get("provided_decision_count")),
        "queue_item_count": _integer(decision_file_coverage.get("queue_item_count")),
        "ledger_available": bool(consolidated_ledger),
        "ledger_profile_count": _integer(consolidated_ledger.get("profile_count")),
        "ledger_document_count": _integer(consolidated_ledger.get("document_count")),
        "ledger_candidate_document_person_link_count": _integer(
            consolidated_ledger.get("candidate_document_person_link_count")
        ),
        "ledger_candidate_evidence_claim_count": _integer(consolidated_ledger.get("candidate_evidence_claim_count")),
        "ledger_reviewable_document_signal_count": _integer(consolidated_ledger.get("reviewable_document_signal_count")),
        "evidence_store_coverage_enabled": bool(ledger_coverage.get("enabled")),
        "evidence_store_record_count": _integer(ledger_coverage.get("record_count")),
        "evidence_store_profiles_with_records_count": _integer(ledger_coverage.get("profiles_with_records_count")),
        "evidence_store_unscoped_record_count": _integer(ledger_coverage.get("unscoped_record_count")),
        "review_status_note": (
            "Raccordo preview-only: mostra contenuto revisionabile e decisioni tracciate, "
            "ma non pubblica schede e non crea fatti verificati."
        ),
    }
    if verified_facts_summary:
        raccordo["verified_facts_preview"] = verified_facts_summary
    return raccordo


def _step2_historical_raccordo_markdown(value: Any) -> list[str]:
    raccordo = _dict_object(value)
    if not raccordo.get("available"):
        return ["- Raccordo step 2 non disponibile: ledger o riepilogo decisioni non collegati al dossier."]
    lines = [
        f"- Stato review storica: `{raccordo.get('review_status', '')}`",
        f"- Decisioni totali: `{raccordo.get('decision_count', 0)}`",
        f"- Decisioni accettate: `{raccordo.get('accepted_count', 0)}`",
        f"- Decisioni pending: `{raccordo.get('pending_count', 0)}`",
        f"- Errori/invalidi: `{raccordo.get('validation_error_count', 0)}` / `{raccordo.get('invalid_count', 0)}`",
    ]
    coverage_status = str(raccordo.get("decision_file_coverage_status", "")).strip()
    if coverage_status:
        lines.extend(
            [
                f"- Copertura file decisioni: `{coverage_status}`",
                f"- Decisioni fornite: `{raccordo.get('provided_decision_count', 0)}` su `{raccordo.get('queue_item_count', 0)}` item coda",
            ]
        )
    if raccordo.get("ledger_available"):
        lines.extend(
            [
                "",
                "Sintesi ledger:",
                f"- Profili nel ledger: `{raccordo.get('ledger_profile_count', 0)}`",
                f"- Documenti collegati: `{raccordo.get('ledger_document_count', 0)}`",
                f"- Link persona-documento candidati: `{raccordo.get('ledger_candidate_document_person_link_count', 0)}`",
                f"- Claim candidati: `{raccordo.get('ledger_candidate_evidence_claim_count', 0)}`",
                f"- Piste documentali: `{raccordo.get('ledger_reviewable_document_signal_count', 0)}`",
            ]
        )
    if raccordo.get("evidence_store_coverage_enabled"):
        lines.extend(
            [
                "",
                "Copertura evidence store dal ledger:",
                f"- Record store: `{raccordo.get('evidence_store_record_count', 0)}`",
                f"- Profili con record: `{raccordo.get('evidence_store_profiles_with_records_count', 0)}`",
                f"- Record non scopiati: `{raccordo.get('evidence_store_unscoped_record_count', 0)}`",
            ]
        )
    preview = _dict_object(raccordo.get("verified_facts_preview"))
    if preview:
        lines.extend(["", "Verified facts preview:"])
        if not preview.get("available"):
            lines.append(f"- Stato: `{preview.get('status', 'missing')}`")
            note = str(preview.get("note", "")).strip()
            if note:
                lines.append(f"- Nota: {note}")
        else:
            lines.extend(
                [
                    f"- Stato: `{preview.get('status', '')}`",
                    f"- Fatti preview: `{preview.get('fact_count', 0)}`",
                    f"- Decisioni escluse: `{preview.get('excluded_decision_count', 0)}`",
                    "- Preview-only: non e' dataset canonico e non e' materiale pubblicabile.",
                ]
            )
    lines.extend(["", f"- {raccordo.get('review_status_note', '')}"])
    return lines


def _verified_facts_preview_summary(
    payload: dict[str, Any],
    *,
    source_path: Path | None,
) -> dict[str, Any]:
    if source_path is None:
        return {}
    if not payload:
        return {
            "available": False,
            "status": "missing",
            "source_path": str(source_path),
            "note": "File preview non presente o non leggibile.",
        }
    status = str(payload.get("status") or payload.get("review_status") or "")
    if status == "skipped":
        return {
            "available": False,
            "status": "skipped",
            "source_path": str(source_path),
            "reason": str(payload.get("reason", "")),
            "note": str(payload.get("note", "")),
        }
    return {
        "available": True,
        "status": status or "preview-only",
        "source_path": str(source_path),
        "fact_count": _integer(payload.get("fact_count")),
        "excluded_decision_count": _integer(payload.get("excluded_decision_count")),
        "counts_by_profile": _dict_int_counts(payload.get("counts_by_profile")),
        "preview_only": bool(payload.get("preview_only", True)),
        "publication_status": str(payload.get("publication_status", "")),
    }


def _funding_source_coverage(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return {}
    sources = []
    for source in _list_items(summary.get("sources")):
        sources.append(
            {
                "source_id": str(source.get("source_id", "")),
                "source_name": str(source.get("source_name", "")),
                "profile_count": _integer(source.get("profile_count")),
                "candidate_profile_count": _integer(source.get("candidate_profile_count")),
                "detail_profile_count": _integer(source.get("detail_profile_count")),
                "no_results_profile_count": _integer(source.get("no_results_profile_count")),
                "document_count": _integer(source.get("document_count")),
                "claim_count": _integer(source.get("claim_count")),
                "recommended_action": str(source.get("recommended_action", "")),
                "review_status": str(source.get("review_status", "unreviewed")) or "unreviewed",
            }
        )
    return {
        "@type": "MvpFundingSourceCoverage",
        "available": True,
        "source_count": _integer(summary.get("source_count"), default=len(sources)),
        "profile_count": _integer(summary.get("profile_count")),
        "entry_count": _integer(summary.get("entry_count")),
        "sources": sources[:10],
        "warnings": _list_strings(summary.get("warnings")),
        "review_status": str(summary.get("review_status", "unreviewed")) or "unreviewed",
        "publication_status": str(summary.get("publication_status", "not_publishable_without_human_review")),
    }


def _source_coverage_markdown(value: Any) -> list[str]:
    coverage = _dict_object(value)
    if not coverage:
        return ["- Copertura fonti non disponibile: nessun report online collegato al dossier."]
    lines = [
        f"- Fonti riepilogate: `{coverage.get('source_count', 0)}`",
        f"- Profili coperti: `{coverage.get('profile_count', 0)}`",
        f"- Voci fonte-profilo: `{coverage.get('entry_count', 0)}`",
    ]
    sources = _list_items(coverage.get("sources"))
    if sources:
        lines.extend(["", "| Fonte | Profili | Candidati | Dettagli | No results | Documenti | Claim | Azione |"])
        lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
        for source in sources:
            label = str(source.get("source_name") or source.get("source_id", ""))
            lines.append(
                "| "
                f"`{source.get('source_id', '')}` {label} "
                f"| {source.get('profile_count', 0)} "
                f"| {source.get('candidate_profile_count', 0)} "
                f"| {source.get('detail_profile_count', 0)} "
                f"| {source.get('no_results_profile_count', 0)} "
                f"| {source.get('document_count', 0)} "
                f"| {source.get('claim_count', 0)} "
                f"| {source.get('recommended_action', '')} |"
            )
    warnings = _list_strings(coverage.get("warnings"))
    if warnings:
        lines.extend(["", "Note copertura:"])
        lines.extend(f"- {warning}" for warning in warnings[:3])
    return lines


def _signal_diagnostics_markdown(value: Any) -> list[str]:
    diagnostics = _dict_object(value)
    if not diagnostics:
        return ["- Diagnostica segnale non disponibile nel riepilogo MVP."]
    lines = [
        f"- Documenti nel pacchetto: `{diagnostics.get('document_count', 0)}`",
        f"- Documenti unici stimati: `{diagnostics.get('estimated_unique_document_count', 0)}`",
        f"- Gruppi duplicati: `{diagnostics.get('duplicate_document_group_count', 0)}`",
        f"- Link nominali deboli: `{diagnostics.get('weak_nominal_link_count', 0)}` / `{diagnostics.get('candidate_document_person_link_count', 0)}`",
        f"- Profili con link ma zero claim: `{diagnostics.get('profiles_with_links_no_claims_count', 0)}`",
        f"- Prossima azione segnale: {diagnostics.get('next_action', '')}",
    ]
    blockers = _list_strings(diagnostics.get("mvp_blockers"))
    if blockers:
        lines.extend(["", "Blocchi segnale:"])
        lines.extend(f"- {blocker}" for blocker in blockers[:5])
    return lines


def _default_brief_path(readiness: dict[str, Any]) -> Path | None:
    vault_dir = str(readiness.get("source_vault_dir", "")).strip()
    if not vault_dir:
        return None
    return Path(vault_dir) / "10_Output" / "mvp_curatorial_brief.md"


def _materials(readiness: dict[str, Any], brief_path: Path | None) -> list[dict[str, Any]]:
    materials: list[dict[str, Any]] = []
    for item in _list_items(readiness.get("required_outputs")):
        materials.append(
            {
                "label": str(item.get("label", "")),
                "path": str(item.get("path", "")),
                "kind": str(item.get("kind", "")),
                "exists": bool(item.get("exists")),
            }
        )
    if brief_path is not None and not any(item["path"] == str(brief_path) for item in materials):
        materials.append(
            {
                "label": "mvp_curatorial_brief_md",
                "path": str(brief_path),
                "kind": "file",
                "exists": brief_path.is_file(),
            }
        )
    return materials


def _profile_readiness(readiness: dict[str, Any], summary: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = _list_items(readiness.get("profile_readiness")) or _list_items(summary.get("profile_readiness"))
    result: list[dict[str, Any]] = []
    for item in profiles:
        result.append(
            {
                "profile_id": str(item.get("profile_id", "")),
                "canonical_name": str(item.get("canonical_name") or item.get("name", "")),
                "readiness_status": str(item.get("readiness_status", "")),
                "next_action": str(item.get("next_action", "")),
                "review_status": str(item.get("review_status", "")) or "unreviewed",
            }
        )
    return result


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
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


def _dict_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_int_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _integer(count) for key, count in sorted(value.items())}


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _yaml_value(value: Any) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un dossier di finanziamento preview-only per il pacchetto MVP.")
    parser.add_argument("--package-readiness-json", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--review-decisions-summary-json", required=True)
    parser.add_argument("--curatorial-brief-md", default="")
    parser.add_argument("--source-coverage-summary-json", default="")
    parser.add_argument("--consolidated-ledger-json", default="")
    parser.add_argument("--verified-facts-preview-json", default="")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    package_readiness_json = Path(args.package_readiness_json)
    run_dir = package_readiness_json.parent
    output_json = Path(args.output_json) if args.output_json else run_dir / "mvp_funding_dossier.json"
    output_md = Path(args.output_md) if args.output_md else run_dir / "mvp_funding_dossier.md"
    dossier = build_mvp_funding_dossier(
        package_readiness_json=package_readiness_json,
        summary_json=Path(args.summary_json),
        review_decisions_summary_json=Path(args.review_decisions_summary_json),
        curatorial_brief_md=Path(args.curatorial_brief_md) if args.curatorial_brief_md else None,
        source_coverage_summary_json=Path(args.source_coverage_summary_json) if args.source_coverage_summary_json else None,
        consolidated_ledger_json=Path(args.consolidated_ledger_json) if args.consolidated_ledger_json else None,
        verified_facts_preview_json=Path(args.verified_facts_preview_json) if args.verified_facts_preview_json else None,
        output_json=output_json,
        output_md=output_md,
    )
    print(f"Dossier finanziamento MVP: {output_md}")
    print(f"Readiness: {dossier['readiness_status']}")
    print(f"Profili pilota: {dossier['profile_count']}")
    print(f"Schede candidate: {dossier['publication_candidate_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
