from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

OCR_LANGUAGES = {
    "it": "ita",
    "de": "deu",
    "en": "eng",
    "fr": "fra",
}
PROMPT_LANGUAGES = {
    "it": "it",
    "de": "de",
    "en": "en",
    "fr": "fr",
}
RULE_SETS = {
    "it": ("it_dates", "it_places", "it_resistance_terms"),
    "de": ("de_dates", "de_archival_terms", "de_military_terms"),
    "en": ("en_dates", "en_archival_terms"),
    "fr": ("fr_dates", "fr_archival_terms"),
}
LOW_CONFIDENCE_THRESHOLD = 0.45


def build_document_language_routing_plans(
    *,
    language_dir: Path,
    language_json: Path | None = None,
    output_dir: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    assessments, skipped = _load_assessments(language_dir=language_dir, language_json=language_json)
    plans = [_routing_plan_for_assessment(assessment=assessment) for assessment in assessments]

    if output_dir is not None:
        for plan in plans:
            plan_path = output_dir / _routing_relative_path(plan)
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "@type": "DocumentLanguageRoutingPlanSet",
        "language_dir": str(language_dir),
        "language_json": str(language_json or ""),
        "output_dir": str(output_dir or ""),
        "routing_method": "deterministic_language_routing_rules",
        "routing_count": len(plans),
        "skipped_count": len(skipped),
        "routing_plans": plans,
        "skipped_assessments": skipped,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_document_language_routing_markdown(payload), encoding="utf-8")
    return payload


def render_document_language_routing_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DocumentLanguageRoutingPlan preview",
        "",
        f"- Metodo: `{payload.get('routing_method', '')}`",
        f"- Routing plan: `{payload.get('routing_count', 0)}`",
        f"- Assessment saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Routing",
        "",
    ]
    plans = payload.get("routing_plans", [])
    if not isinstance(plans, list) or not plans:
        lines.append("_Nessun routing generato._")
    else:
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            warnings = ", ".join(str(warning) for warning in plan.get("warnings", []))
            rule_sets = ", ".join(str(item) for item in plan.get("recommended_rule_sets", []))
            ocr_languages = ", ".join(str(item) for item in plan.get("recommended_ocr_languages", []))
            lines.extend(
                [
                    f"### {plan.get('source_document_id', '')}",
                    "",
                    f"- Lingua primaria: `{plan.get('primary_language', '')}`",
                    f"- OCR suggerito: `{ocr_languages}`",
                    f"- Rule set: `{rule_sets}`",
                    f"- Prompt: `{plan.get('recommended_prompt_language', '')}`",
                    f"- Revisione manuale: `{plan.get('manual_review_required', '')}`",
                    f"- Stato revisione: `{plan.get('review_status', '')}`",
                    f"- Warnings: {warnings}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _load_assessments(*, language_dir: Path, language_json: Path | None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if language_json is not None:
        payload = _load_json_object(language_json)
        if str(payload.get("@type", "")) == "DocumentLanguageAssessmentSet":
            assessments = payload.get("language_assessments", [])
            if isinstance(assessments, list):
                return ([item for item in assessments if isinstance(item, dict)], [])
        if str(payload.get("@type", "")) == "DocumentLanguageAssessment":
            return [payload], []
        return [], [{"language_file": str(language_json), "reason": "unsupported_payload_type"}]

    assessments: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for path in sorted(language_dir.rglob("*.language.json")):
        payload = _load_json_object(path)
        if str(payload.get("@type", "")) != "DocumentLanguageAssessment":
            skipped.append({"language_file": str(path), "reason": "unsupported_payload_type"})
            continue
        assessments.append(payload)
    return assessments, skipped


def _routing_plan_for_assessment(*, assessment: dict[str, Any]) -> dict[str, Any]:
    primary_language = str(assessment.get("primary_language", "") or "und")
    secondary_languages = _string_list(assessment.get("secondary_languages", []))
    confidence = _float_value(assessment.get("confidence", 0.0))
    languages = _dedupe([primary_language, *secondary_languages])
    routed_languages = [language for language in languages if language in OCR_LANGUAGES]
    warnings = _string_list(assessment.get("warnings", []))
    if not routed_languages:
        warnings.append("language_routing_requires_manual_review")
    if primary_language == "und":
        warnings.append("language_undetermined_no_automatic_routing")
    if secondary_languages:
        warnings.append("multilingual_routing_requires_review")
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        warnings.append("low_confidence_language_routing")

    manual_review_required = bool(
        not routed_languages
        or primary_language == "und"
        or secondary_languages
        or confidence < LOW_CONFIDENCE_THRESHOLD
    )
    recommended_ocr_languages = [OCR_LANGUAGES[language] for language in routed_languages]
    recommended_rule_sets = _dedupe(
        [rule_set for language in routed_languages for rule_set in RULE_SETS.get(language, ())]
    )
    prompt_language = PROMPT_LANGUAGES.get(primary_language, "manual_review_required")
    source_document_id = str(assessment.get("source_document_id", ""))
    plan_id = _routing_id(source_document_id=source_document_id, primary_language=primary_language)

    return {
        "@type": "DocumentLanguageRoutingPlan",
        "@id": plan_id,
        "routing_plan_id": plan_id,
        "source_id": str(assessment.get("source_id", "")),
        "source_document_id": source_document_id,
        "text_file": str(assessment.get("text_file", "")),
        "language_assessment_id": str(assessment.get("@id", "")),
        "primary_language": primary_language,
        "secondary_languages": secondary_languages,
        "language_confidence": confidence,
        "recommended_ocr_languages": recommended_ocr_languages,
        "recommended_rule_sets": recommended_rule_sets,
        "recommended_prompt_language": prompt_language,
        "manual_review_required": manual_review_required,
        "routing_method": "deterministic_language_routing_rules",
        "warnings": _dedupe(warnings),
        "review_status": "unreviewed",
        "claim_extraction_allowed": False,
        "translation_generated": False,
        "ocr_started": False,
        "llm_started": False,
    }


def _routing_relative_path(plan: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(plan.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(plan.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.language-routing.json"


def _routing_id(*, source_document_id: str, primary_language: str) -> str:
    digest = hashlib.sha256(f"{source_document_id}|{primary_language}".encode("utf-8")).hexdigest()[:16]
    return f"document-language-routing:{digest}"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera DocumentLanguageRoutingPlan preview-only da assessment lingua.")
    parser.add_argument("--language-dir", default="data/processed/documents")
    parser.add_argument("--language-json", default="")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/document_language_routing.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/document_language_routing.md")
    args = parser.parse_args()

    payload = build_document_language_routing_plans(
        language_dir=Path(args.language_dir),
        language_json=Path(args.language_json) if args.language_json.strip() else None,
        output_dir=Path(args.output_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"DocumentLanguageRoutingPlan JSON scritto in {args.output_json}")
    print(f"DocumentLanguageRoutingPlan Markdown scritto in {args.output_md}")
    print(f"Routing plan: {payload['routing_count']}")
    print(f"Assessment saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
