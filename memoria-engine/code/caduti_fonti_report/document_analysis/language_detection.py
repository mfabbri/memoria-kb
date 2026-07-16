from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

MIN_TEXT_CHARS = 40
SUPPORTED_LANGUAGES = ("it", "de", "en", "fr")
MARKERS = {
    "it": {
        "di",
        "che",
        "del",
        "della",
        "delle",
        "nato",
        "nata",
        "morto",
        "morta",
        "brigata",
        "partigiano",
        "partigiana",
        "comune",
        "documento",
        "archivio",
        "resistenza",
    },
    "de": {
        "der",
        "die",
        "das",
        "und",
        "geb",
        "geboren",
        "gestorben",
        "archiv",
        "akten",
        "krieg",
        "stand",
        "ort",
        "deutsch",
        "unterlagen",
    },
    "en": {
        "the",
        "and",
        "born",
        "died",
        "record",
        "archive",
        "service",
        "war",
        "place",
        "date",
        "document",
        "casualty",
    },
    "fr": {
        "le",
        "la",
        "les",
        "des",
        "est",
        "ne",
        "mort",
        "nee",
        "archive",
        "document",
        "guerre",
        "lieu",
        "date",
        "resistance",
    },
}


def detect_document_languages(
    *,
    text_dir: Path,
    output_dir: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
    min_text_chars: int = MIN_TEXT_CHARS,
    text_paths: list[Path] | None = None,
) -> dict[str, Any]:
    min_text_chars = _bounded_positive_int(min_text_chars, MIN_TEXT_CHARS)
    assessments: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    paths = sorted(text_paths) if text_paths is not None else sorted(text_dir.rglob("*.text.json"))
    for text_path in paths:
        payload = _load_json_object(text_path)
        skip_reason = _skip_reason(payload=payload, min_text_chars=min_text_chars)
        if skip_reason:
            skipped.append(_skip_record(payload=payload, text_path=text_path, reason=skip_reason))
            continue

        assessment = _assessment_for_text(payload=payload, text_path=text_path, min_text_chars=min_text_chars)
        assessments.append(assessment)
        if output_dir is not None:
            language_path = output_dir / _language_relative_path(assessment)
            language_path.parent.mkdir(parents=True, exist_ok=True)
            language_path.write_text(json.dumps(assessment, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "@type": "DocumentLanguageAssessmentSet",
        "text_dir": str(text_dir),
        "output_dir": str(output_dir or ""),
        "detection_method": "deterministic_marker_language_detection",
        "assessment_count": len(assessments),
        "skipped_count": len(skipped),
        "language_assessments": assessments,
        "skipped_documents": skipped,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_document_language_markdown(payload), encoding="utf-8")
    return payload


def render_document_language_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DocumentLanguageAssessment preview",
        "",
        f"- Metodo: `{payload.get('detection_method', '')}`",
        f"- Assessment: `{payload.get('assessment_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Lingue rilevate",
        "",
    ]
    assessments = payload.get("language_assessments", [])
    if not isinstance(assessments, list) or not assessments:
        lines.append("_Nessuna lingua rilevata._")
    else:
        for assessment in assessments:
            if not isinstance(assessment, dict):
                continue
            warnings = ", ".join(str(warning) for warning in assessment.get("warnings", []))
            lines.extend(
                [
                    f"### {assessment.get('source_document_id', '')}",
                    "",
                    f"- Lingua primaria: `{assessment.get('primary_language', '')}`",
                    f"- Confidence: `{assessment.get('confidence', '')}`",
                    f"- Multilingua: `{assessment.get('is_multilingual', '')}`",
                    f"- Stato revisione: `{assessment.get('review_status', '')}`",
                    f"- Warnings: {warnings}",
                    f"- Testo: `{assessment.get('text_file', '')}`",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _assessment_for_text(*, payload: dict[str, Any], text_path: Path, min_text_chars: int) -> dict[str, Any]:
    text = str(payload.get("text", ""))
    scores = _language_scores(text)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    total_score = sum(scores.values())
    primary_language = ranked[0][0] if ranked and ranked[0][1] > 0 else "und"
    confidence = _confidence(ranked=ranked, total_score=total_score)
    warnings: list[str] = []
    if len(text.strip()) < min_text_chars:
        primary_language = "und"
        confidence = min(confidence, 0.2)
        warnings.append("text_too_short")
    secondary_languages = _secondary_languages(ranked=ranked, primary_language=primary_language)
    if primary_language == "und":
        warnings.append("language_undetermined")
    if secondary_languages:
        warnings.append("mixed_language_signals")

    return {
        "@type": "DocumentLanguageAssessment",
        "@id": _assessment_id(str(payload.get("source_document_id", "")), scope="document"),
        "source_id": str(payload.get("source_id", "")),
        "source_document_id": str(payload.get("source_document_id", "")),
        "text_file": str(text_path),
        "text_sha256": str(payload.get("text_sha256", "")),
        "scope": "document",
        "language_candidates": [
            {"language": language, "confidence": _candidate_confidence(score=score, total_score=total_score)}
            for language, score in ranked
            if score > 0
        ],
        "primary_language": primary_language,
        "secondary_languages": secondary_languages,
        "is_multilingual": bool(secondary_languages),
        "script": _script_for_text(text),
        "confidence": confidence,
        "detection_method": "deterministic_marker_language_detection",
        "review_status": "unreviewed",
        "warnings": _dedupe(warnings),
    }


def _language_scores(text: str) -> dict[str, int]:
    tokens = _tokens(text)
    token_set = set(tokens)
    scores: dict[str, int] = {}
    for language in SUPPORTED_LANGUAGES:
        markers = MARKERS[language]
        scores[language] = sum(1 for token in tokens if token in markers) + sum(2 for marker in markers if marker in token_set)
    return scores


def _confidence(*, ranked: list[tuple[str, int]], total_score: int) -> float:
    if not ranked or total_score <= 0 or ranked[0][1] <= 0:
        return 0.15
    top_score = ranked[0][1]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    share = top_score / total_score
    margin = (top_score - second_score) / max(top_score, 1)
    return round(min(0.99, max(0.25, (share * 0.65) + (margin * 0.35))), 2)


def _candidate_confidence(*, score: int, total_score: int) -> float:
    if total_score <= 0:
        return 0.0
    return round(score / total_score, 2)


def _secondary_languages(*, ranked: list[tuple[str, int]], primary_language: str) -> list[str]:
    if primary_language == "und" or not ranked:
        return []
    top_score = ranked[0][1]
    if top_score <= 0:
        return []
    secondary: list[str] = []
    for language, score in ranked[1:]:
        if score >= max(2, int(top_score * 0.45)):
            secondary.append(language)
    return secondary


def _script_for_text(text: str) -> str:
    if re.search(r"[\u0400-\u04FF]", text):
        return "Cyrillic"
    return "Latin"


def _skip_reason(*, payload: dict[str, Any], min_text_chars: int) -> str:
    if not payload:
        return "text_unreadable"
    if str(payload.get("@type", "")) != "ProcessedDocumentText":
        return "unsupported_payload_type"
    if str(payload.get("text_status", "")) != "extracted":
        return "text_not_extracted"
    if not str(payload.get("text", "")).strip():
        return "empty_text"
    return ""


def _skip_record(*, payload: dict[str, Any], text_path: Path, reason: str) -> dict[str, str]:
    return {
        "source_document_id": str(payload.get("source_document_id", "")) if payload else "",
        "text_file": str(text_path),
        "reason": reason,
    }


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ]+", text.casefold())


def _language_relative_path(assessment: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(assessment.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(assessment.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.language.json"


def _assessment_id(source_document_id: str, *, scope: str) -> str:
    safe_id = _safe_path_part(source_document_id or "unknown")
    return f"document-language-assessment:{scope}:{safe_id}"


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def _bounded_positive_int(value: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera DocumentLanguageAssessment preview-only da testi processati.")
    parser.add_argument("--text-dir", default="data/processed/documents")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/document_language_assessments.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/document_language_assessments.md")
    parser.add_argument("--min-text-chars", type=int, default=MIN_TEXT_CHARS)
    args = parser.parse_args()

    payload = detect_document_languages(
        text_dir=Path(args.text_dir),
        output_dir=Path(args.output_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
        min_text_chars=args.min_text_chars,
    )
    print(f"DocumentLanguageAssessment JSON scritto in {args.output_json}")
    print(f"DocumentLanguageAssessment Markdown scritto in {args.output_md}")
    print(f"Assessment: {payload['assessment_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
