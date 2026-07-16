from __future__ import annotations

from dataclasses import dataclass, field
import html as html_lib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin

import yaml

from .http_utils import page_title, strip_tags


@dataclass(frozen=True)
class DetailPageSignals:
    source_id: str
    engine: str = ""
    heading: str = ""
    body_text: str = ""
    blocked: bool = False
    error: str = ""
    extracted_fields: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DetailPageAssessment:
    assessment: str
    review_required: bool = False
    extracted_fields: dict[str, str] = field(default_factory=dict)
    note: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DetailFieldPattern:
    field_id: str
    source: str = "body_text"
    pattern: str = ""
    group: int = 1


@dataclass(frozen=True)
class DetailClaimMapping:
    field: str
    signal_field: str
    confidence: float = 0.0


@dataclass(frozen=True)
class DetailLogicRule:
    rule_id: str
    when: dict[str, Any] = field(default_factory=dict)
    assessment: str = ""
    review_required: bool = False


@dataclass(frozen=True)
class SourceDetailLogicDefinition:
    source_id: str
    engine: str = ""
    detail_level: str = "detail_document_only"
    blocked_text: list[str] = field(default_factory=list)
    field_patterns: list[DetailFieldPattern] = field(default_factory=list)
    claim_mappings: list[DetailClaimMapping] = field(default_factory=list)
    rules: list[DetailLogicRule] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)


def load_source_detail_logic(path: Path | str) -> SourceDetailLogicDefinition:
    raw_payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if "detail_logic" in raw_payload and isinstance(raw_payload["detail_logic"], dict):
        raw_payload = raw_payload["detail_logic"]
    if not isinstance(raw_payload, dict):
        raise ValueError("Logica dettaglio fonte non valida: atteso mapping YAML.")
    return source_detail_logic_from_dict(raw_payload)


def source_detail_logic_from_dict(payload: dict[str, Any]) -> SourceDetailLogicDefinition:
    field_patterns: list[DetailFieldPattern] = []
    for item in payload.get("field_patterns", []) or []:
        if not isinstance(item, dict):
            continue
        field_patterns.append(
            DetailFieldPattern(
                field_id=str(item.get("id") or item.get("field_id") or ""),
                source=str(item.get("from") or item.get("source") or "body_text"),
                pattern=str(item.get("pattern", "")),
                group=_as_positive_int(item.get("group", 1), 1),
            )
        )

    claim_mappings: list[DetailClaimMapping] = []
    for item in payload.get("claim_mappings", []) or []:
        if not isinstance(item, dict):
            continue
        claim_mappings.append(
            DetailClaimMapping(
                field=str(item.get("field", "")),
                signal_field=str(item.get("signal_field", "")),
                confidence=_float_or_default(item.get("confidence"), 0.0),
            )
        )

    rules: list[DetailLogicRule] = []
    for item in payload.get("rules", []) or []:
        if not isinstance(item, dict):
            continue
        rules.append(
            DetailLogicRule(
                rule_id=str(item.get("id") or item.get("rule_id") or ""),
                when=dict(item.get("when", {}) or {}),
                assessment=str(item.get("assessment", "")),
                review_required=bool(item.get("review_required", False)),
            )
        )

    return SourceDetailLogicDefinition(
        source_id=str(payload.get("source_id", "")),
        engine=str(payload.get("engine", "")),
        detail_level=_detail_level(payload.get("detail_level", "detail_document_only")),
        blocked_text=[str(item) for item in payload.get("blocked_text", []) or []],
        field_patterns=field_patterns,
        claim_mappings=claim_mappings,
        rules=rules,
        review_notes=[str(item) for item in payload.get("review_notes", []) or []],
    )


class DetailPageInterpreter:
    def __init__(self, definition: SourceDetailLogicDefinition) -> None:
        self.definition = definition

    def interpret(self, signals: DetailPageSignals) -> DetailPageAssessment:
        for rule in self.definition.rules:
            if not rule.assessment or not _rule_matches(rule, signals):
                continue
            return DetailPageAssessment(
                assessment=rule.assessment,
                review_required=rule.review_required,
                extracted_fields=signals.extracted_fields,
                note=_assessment_note(rule.assessment, signals),
                metadata={"rule_id": rule.rule_id, "source_id": signals.source_id, "engine": signals.engine or self.definition.engine},
            )
        return _fallback_assessment(signals, self.definition)


def extract_detail_page_signals(
    *,
    source_id: str,
    engine: str,
    html_text: str,
    detail_logic: SourceDetailLogicDefinition,
    result_url: str,
) -> DetailPageSignals:
    body_text = _body_text_for_source(source_id=source_id, engine=engine, html_text=html_text)
    heading = _heading_for_source(
        source_id=source_id,
        engine=engine,
        html_text=html_text,
        body_text=body_text,
    )
    blocked = _contains_any(body_text, detail_logic.blocked_text)
    extracted_fields: dict[str, str] = {}
    for field_pattern in detail_logic.field_patterns:
        if field_pattern.field_id in extracted_fields:
            continue
        candidate_text = heading if field_pattern.source == "heading" else body_text
        value = _extract_field(candidate_text, field_pattern)
        if value:
            extracted_fields[field_pattern.field_id] = value
    metadata = {"result_url": result_url}
    metadata.update(_metadata_for_source(source_id=source_id, engine=engine, html_text=html_text, result_url=result_url))
    return DetailPageSignals(
        source_id=source_id,
        engine=engine,
        heading=heading,
        body_text=body_text,
        blocked=blocked,
        extracted_fields=extracted_fields,
        metadata=metadata,
    )


def _extract_heading(html_text: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.I | re.S)
    return strip_tags(match.group(1)) if match else ""


def _body_text(html_text: str) -> str:
    return " ".join(strip_tags(html_text).split())


def _body_text_for_source(*, source_id: str, engine: str, html_text: str) -> str:
    if source_id == "partigiani_italia" and engine == "partigiani_italia_person_detail":
        return _partigiani_italia_body_text(html_text)
    return _body_text(html_text)


def _heading_for_source(*, source_id: str, engine: str, html_text: str, body_text: str) -> str:
    heading = _extract_heading(html_text) or page_title(html_text)
    if source_id == "partigiani_italia" and engine == "partigiani_italia_person_detail":
        person_heading = _partigiani_italia_person_heading(body_text)
        if person_heading:
            return person_heading
    return heading


def _metadata_for_source(*, source_id: str, engine: str, html_text: str, result_url: str) -> dict[str, str]:
    if source_id != "partigiani_italia" or engine != "partigiani_italia_person_detail":
        return {}
    images = _partigiani_italia_image_candidates(html_text, result_url)
    metadata = {"content_cleaning": "partigiani_italia_detail_v1"}
    if images:
        metadata["partigiani_italia_image_urls_json"] = json.dumps(images, ensure_ascii=False)
    return metadata


def _partigiani_italia_body_text(html_text: str) -> str:
    content_html = _partigiani_italia_content_html(html_text)
    table_text = _partigiani_italia_table_text(content_html)
    if table_text:
        return table_text
    text = _body_text(content_html)
    text = _drop_before_marker(text, "Home >")
    text = _drop_before_marker(text, "Risultati trovati")
    text = _truncate_before_markers(
        text,
        [
            "ISTITUTO CENTRALE PER GLI ARCHIVI",
            "Privacy Overview",
            "Questo sito utilizza cookies",
            "Cookie Policy",
        ],
    )
    text = _collapse_repeated_leading_phrase(text)
    return text.strip()


def _partigiani_italia_content_html(html_text: str) -> str:
    for tag_name in ("main", "article", "section"):
        for tag_html in _tag_html_blocks(html_text, tag_name):
            if "Dati anagrafici" in tag_html or "slim-table-xl" in tag_html:
                return tag_html
    return _first_tag_html(html_text, "main") or _first_tag_html(html_text, "article") or _first_tag_html(html_text, "section") or html_text


def _partigiani_italia_table_text(html_text: str) -> str:
    if "slim-table-xl" not in html_text and "Dati anagrafici" not in html_text:
        return ""
    parts: list[str] = []
    heading_match = re.search(r"<h[1-6][^>]*class=['\"][^'\"]*slim-t-big[^'\"]*['\"][^>]*>(.*?)</h[1-6]>", html_text, flags=re.I | re.S)
    if heading_match:
        heading = strip_tags(heading_match.group(1)).strip()
        if heading:
            parts.append(heading)
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", html_text, flags=re.I | re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)
        cleaned_cells = [strip_tags(cell).strip() for cell in cells if strip_tags(cell).strip()]
        if len(cleaned_cells) == 1:
            parts.append(cleaned_cells[0].rstrip(":"))
        elif len(cleaned_cells) >= 2:
            label = cleaned_cells[0].rstrip(":").strip()
            value = cleaned_cells[1].strip()
            if label and value:
                parts.append(f"{label}: {value}")
    text = " ".join(part for part in parts if part)
    return _truncate_before_markers(
        text,
        [
            "ISTITUTO CENTRALE PER GLI ARCHIVI",
            "Privacy Overview",
            "Questo sito utilizza cookies",
            "Cookie Policy",
        ],
    ).strip()


def _partigiani_italia_person_heading(body_text: str) -> str:
    marker_index = body_text.casefold().find("dati anagrafici")
    if marker_index < 0:
        return ""
    prefix = body_text[:marker_index].strip()
    prefix = _collapse_repeated_leading_phrase(prefix)
    if len(prefix) > 120:
        return ""
    return prefix


def _partigiani_italia_image_candidates(html_text: str, result_url: str) -> list[dict[str, str]]:
    content_html = _partigiani_italia_content_html(html_text)
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for image_tag in re.findall(r"<img\b[^>]*>", content_html, flags=re.I | re.S):
        src = _html_attr(image_tag, "src") or _html_attr(image_tag, "data-src") or _html_attr(image_tag, "data-lazy-src")
        if not src or src.strip().lower().startswith("data:"):
            continue
        absolute_url = urljoin(result_url, src.strip())
        alt = _html_attr(image_tag, "alt")
        title = _html_attr(image_tag, "title")
        classes = _html_attr(image_tag, "class")
        haystack = f"{absolute_url} {alt} {title} {classes}".casefold()
        if _is_partigiani_noise_image(haystack):
            continue
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        candidates.append({"url": absolute_url, "alt": alt, "title": title})
    return candidates


def _first_tag_html(html_text: str, tag_name: str) -> str:
    match = re.search(rf"<{tag_name}\b[^>]*>(.*?)</{tag_name}>", html_text, flags=re.I | re.S)
    return match.group(1) if match else ""


def _tag_html_blocks(html_text: str, tag_name: str) -> list[str]:
    return re.findall(rf"<{tag_name}\b[^>]*>(.*?)</{tag_name}>", html_text, flags=re.I | re.S)


def _html_attr(tag_html: str, attr_name: str) -> str:
    match = re.search(rf"""{attr_name}\s*=\s*(['"])(.*?)\1""", tag_html, flags=re.I | re.S)
    if not match:
        return ""
    return " ".join(strip_tags(html_lib.unescape(match.group(2))).split()).strip()


def _is_partigiani_noise_image(haystack: str) -> bool:
    positive_tokens = {"scheda", "persona", "partigian", "uploads", "foto", "tessera"}
    if any(token in haystack for token in positive_tokens):
        return False
    noise_tokens = {
        "logo",
        "icon",
        "cookie",
        "avatar",
        "gravatar",
        "spid",
        "cie",
        "ministero",
        "loader",
        "blank",
        "transparent",
    }
    return any(token in haystack for token in noise_tokens)


def _truncate_before_markers(text: str, markers: list[str]) -> str:
    end = len(text)
    lowered = text.casefold()
    for marker in markers:
        index = lowered.find(marker.casefold())
        if index >= 0:
            end = min(end, index)
    return text[:end].strip()


def _drop_before_marker(text: str, marker: str) -> str:
    index = text.casefold().find(marker.casefold())
    if index < 0:
        return text
    return text[index + len(marker) :].strip()


def _collapse_repeated_leading_phrase(text: str) -> str:
    words = text.split()
    for size in range(1, min(8, len(words) // 2) + 1):
        if [word.casefold() for word in words[:size]] == [word.casefold() for word in words[size : size * 2]]:
            return " ".join(words[size:])
    return text


def _extract_field(text: str, pattern: DetailFieldPattern) -> str:
    if not pattern.pattern:
        return ""
    match = re.search(pattern.pattern, text, flags=re.I)
    if not match:
        return ""
    try:
        return " ".join((match.group(pattern.group) or "").split()).strip()
    except IndexError:
        return ""


def _rule_matches(rule: DetailLogicRule, signals: DetailPageSignals) -> bool:
    for key, expected in rule.when.items():
        if key == "blocked" and _as_bool(expected) != signals.blocked:
            return False
        if key == "has_error" and _as_bool(expected) != bool(signals.error):
            return False
        if key == "extracted_field_count_equals" and len(signals.extracted_fields) != _as_non_negative_int(expected):
            return False
        if key == "extracted_field_count_greater_than" and len(signals.extracted_fields) <= _as_non_negative_int(expected):
            return False
    return True


def _fallback_assessment(signals: DetailPageSignals, definition: SourceDetailLogicDefinition) -> DetailPageAssessment:
    if signals.error:
        assessment = "detail_parse_error"
        review_required = True
    elif signals.blocked:
        assessment = "detail_needs_manual_review"
        review_required = True
    elif signals.extracted_fields:
        assessment = "claim_candidates_extracted"
        review_required = True
    else:
        assessment = "detail_document_fetched"
        review_required = True
    return DetailPageAssessment(
        assessment=assessment,
        review_required=review_required,
        extracted_fields=signals.extracted_fields,
        note=_assessment_note(assessment, signals),
        metadata={"rule_id": "fallback", "source_id": signals.source_id, "engine": signals.engine or definition.engine},
    )


def _assessment_note(assessment: str, signals: DetailPageSignals) -> str:
    if assessment == "detail_needs_manual_review":
        return "Scheda dettaglio non pienamente accessibile o da revisionare manualmente."
    if assessment == "claim_candidates_extracted":
        return f"Scheda dettaglio letta con {len(signals.extracted_fields)} campi candidati."
    if assessment == "detail_document_fetched":
        return "Scheda dettaglio acquisita senza campi sufficienti per claim candidati."
    if assessment == "detail_parse_error":
        return signals.error or "Errore nella lettura della scheda dettaglio."
    return assessment


def _contains_any(text: str, candidates: list[str]) -> bool:
    lowered = text.casefold()
    return any(candidate.strip().casefold() in lowered for candidate in candidates if candidate.strip())


def _as_bool(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "si", "sì"}


def _as_positive_int(value: Any, default: int) -> int:
    parsed = _as_non_negative_int(value)
    return parsed if parsed > 0 else default


def _as_non_negative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError:
        return default
    return parsed if parsed >= 0 else default


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default



def _detail_level(value: Any) -> str:
    accepted = {"claims_extractable", "detail_document_only", "reference_only", "manual_review_only"}
    text = str(value).strip()
    return text if text in accepted else "detail_document_only"
