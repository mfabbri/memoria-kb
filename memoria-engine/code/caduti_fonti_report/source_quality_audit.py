from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .models import SourceQualityAssessment, SourceQualityAudit, SourceQualityIssue, to_json_safe
from .detail_page_logic import load_source_detail_logic
from .search_result_logic import load_source_result_logic
from .source_catalog import resolve_source_catalog_root, resolve_source_registry_path, source_catalog_relative_path, source_level_path

LEVEL_DIRS = {
    "profile": "source_profiles",
    "strategy": "source_strategies",
    "result_logic": "source_result_logic",
    "detail_logic": "source_detail_logic",
}

GENERIC_LINK_SELECTORS = {"a[href]", "a"}
NOISY_URL_PATTERNS = ("javascript:", "#", "login", "logout", "language", "hilfe", "help")
NOISY_TITLE_PATTERNS = ("login", "logout", "home", "search", "cerca", "english", "deutsch", "italiano", "hilfe", "help")
DETAIL_LEVELS = {"claims_extractable", "detail_document_only", "reference_only", "manual_review_only"}


def run_source_quality_audit(*, repo_root: Path, registry_path: Path) -> SourceQualityAudit:
    catalog_root = resolve_source_catalog_root(repo_root, registry_path=registry_path)
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    sources = registry.get("sources", []) if isinstance(registry, dict) else []
    assessments: list[SourceQualityAssessment] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("id", "")).strip()
        if not source_id:
            continue
        assessments.append(
            _assess_source(
                repo_root=repo_root,
                catalog_root=catalog_root,
                source_id=source_id,
                source_name=str(source.get("name", "")).strip(),
            )
        )
    return SourceQualityAudit(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        source_count=len(assessments),
        assessments=assessments,
    )


def write_audit_outputs(audit: SourceQualityAudit, *, output_json: Path, output_md: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(to_json_safe(audit), ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_source_quality_audit_markdown(audit), encoding="utf-8")


def render_source_quality_audit_markdown(audit: SourceQualityAudit) -> str:
    lines = [
        "# Audit qualità fonti",
        "",
        f"Generato il: {audit.generated_at}",
        f"Fonti analizzate: {audit.source_count}",
        "",
        "L'audit distingue copertura strutturale, rischio rumore dei candidati e livello archivistico del dettaglio.",
        "",
        "| Fonte | Qualità candidati | Livello dettaglio | Problemi | Azioni consigliate |",
        "|---|---|---|---:|---|",
    ]
    for item in audit.assessments:
        issues = len(item.issues)
        actions = "; ".join(item.recommended_actions) or "-"
        lines.append(
            f"| `{item.source_id}` | `{item.candidate_quality}` | `{item.detail_level}` | {issues} | {actions} |"
        )
    lines.append("")
    lines.append("## Dettaglio problemi")
    lines.append("")
    for item in audit.assessments:
        if not item.issues and not item.noise_indicators:
            continue
        lines.append(f"### {item.source_id}")
        lines.append("")
        if item.noise_indicators:
            lines.append("Indicatori di rumore:")
            for noise in item.noise_indicators:
                lines.append(f"- {noise}")
        if item.issues:
            lines.append("Problemi:")
            for issue in item.issues:
                lines.append(f"- `{issue.severity}` `{issue.code}`: {issue.message}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _assess_source(*, repo_root: Path, catalog_root: Path, source_id: str, source_name: str) -> SourceQualityAssessment:
    paths = {name: source_level_path(catalog_root, directory, source_id) for name, directory in LEVEL_DIRS.items()}
    assessment = SourceQualityAssessment(
        source_id=source_id,
        source_name=source_name,
        has_profile=paths["profile"].exists(),
        has_strategy=paths["strategy"].exists(),
        has_result_logic=paths["result_logic"].exists(),
        has_detail_logic=paths["detail_logic"].exists(),
        has_result_fixture=_has_fixture(repo_root, "source_results", source_id),
        has_detail_fixture=_has_fixture(repo_root, "source_details", source_id),
        has_result_logic_test=_has_test_reference(repo_root, source_id, "result"),
        has_detail_logic_test=_has_test_reference(repo_root, source_id, "detail"),
    )

    for key, path in paths.items():
        if not path.exists():
            assessment.issues.append(
                _issue(source_id, "error", f"missing_{key}", f"Manca {source_catalog_relative_path(repo_root, path)}")
            )

    if paths["result_logic"].exists():
        try:
            result_logic = load_source_result_logic(paths["result_logic"])
            selector = str(result_logic.signals.get("result_link_selector", "")).strip()
            if selector.casefold() in GENERIC_LINK_SELECTORS:
                assessment.noise_indicators.append(f"result_link_selector troppo generico: {selector}")
            if selector.casefold() in GENERIC_LINK_SELECTORS and not result_logic.candidate_filters.exclude_url_patterns:
                assessment.issues.append(_issue(source_id, "warning", "missing_candidate_filters", "Selettore generico senza candidate_filters.exclude_url_patterns."))
            if result_logic.candidate_filters.exclude_url_patterns or result_logic.candidate_filters.exclude_title_patterns:
                assessment.candidate_quality = "good" if selector.casefold() not in GENERIC_LINK_SELECTORS else "guarded"
            elif selector.casefold() in GENERIC_LINK_SELECTORS:
                assessment.candidate_quality = "noisy"
            else:
                assessment.candidate_quality = "unknown"
        except Exception as exc:  # pragma: no cover - defensive audit reporting
            assessment.issues.append(_issue(source_id, "error", "result_logic_parse_error", str(exc)))

    if paths["detail_logic"].exists():
        try:
            detail_logic = load_source_detail_logic(paths["detail_logic"])
            assessment.detail_level = detail_logic.detail_level
            if detail_logic.detail_level not in DETAIL_LEVELS:
                assessment.issues.append(_issue(source_id, "warning", "invalid_detail_level", f"detail_level non ammesso: {detail_logic.detail_level}"))
            if detail_logic.detail_level in {"reference_only", "manual_review_only"} and not detail_logic.review_notes:
                assessment.issues.append(_issue(source_id, "warning", "missing_review_notes", "Le fonti reference/manual richiedono review_notes."))
            if detail_logic.detail_level == "claims_extractable" and not detail_logic.claim_mappings:
                assessment.issues.append(_issue(source_id, "warning", "missing_claim_mappings", "claims_extractable senza claim_mappings."))
        except Exception as exc:  # pragma: no cover
            assessment.issues.append(_issue(source_id, "error", "detail_logic_parse_error", str(exc)))

    if not assessment.has_result_fixture:
        assessment.recommended_actions.append("aggiungere fixture risultati")
    if assessment.candidate_quality in {"noisy", "guarded"}:
        assessment.recommended_actions.append("raffinare candidate_filters")
    if assessment.detail_level in {"reference_only", "manual_review_only"}:
        assessment.recommended_actions.append("mantenere revisione manuale prima dei claim")
    return assessment


def _has_fixture(repo_root: Path, fixture_group: str, source_id: str) -> bool:
    root = repo_root / "tests" / "fixtures" / fixture_group / source_id
    return root.exists() and any(path.is_file() for path in root.rglob("*"))


def _has_test_reference(repo_root: Path, source_id: str, kind: str) -> bool:
    tests_root = repo_root / "tests"
    if not tests_root.exists():
        return False
    needle = source_id.casefold()
    kind_needle = kind.casefold()
    for path in tests_root.glob("test_*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore").casefold()
        if needle in text and kind_needle in path.name.casefold():
            return True
    return False


def _issue(source_id: str, severity: str, code: str, message: str) -> SourceQualityIssue:
    return SourceQualityIssue(source_id=source_id, severity=severity, code=code, message=message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un audit qualitativo delle fonti configurate.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--registry", default="ricerche/camalanca_fonti.yaml")
    parser.add_argument("--output-json", default="risultati/source_quality_audit.json")
    parser.add_argument("--output-md", default="risultati/source_quality_audit.md")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = repo_root / registry_path
    if args.registry == "ricerche/camalanca_fonti.yaml":
        registry_path = resolve_source_registry_path(repo_root)
    audit = run_source_quality_audit(repo_root=repo_root, registry_path=registry_path)
    write_audit_outputs(audit, output_json=repo_root / args.output_json, output_md=repo_root / args.output_md)
    print(f"Audit qualità fonti generato: {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
