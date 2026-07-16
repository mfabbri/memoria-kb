from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..detail_page_logic import SourceDetailLogicDefinition, load_source_detail_logic
from ..source_catalog import resolve_source_catalog_root
from .candidate_claim_diagnostics import (
    build_claim_funnel_diagnostics as _build_claim_funnel_diagnostics,
)
from .candidate_claim_skips import (
    skipped_candidate_claim as _skipped_candidate_claim,
    skipped_structured_document as _skipped_structured_document,
)
from .candidate_evidence_claims import CandidateEvidenceClaimRecord

SKIPPED_DOCUMENT_CLASSES = {"result_page", "reference_page"}
STRUCTURED_EXTRACTION_METHOD = "online_detail_structured_fields"


def build_candidate_document_claims(
    *,
    entities_json: Path,
    links_json: Path,
    quality_dir: Path,
    sources_yaml: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    entity_payload = _load_json_object(entities_json)
    link_payload = _load_json_object(links_json)
    entities = _list_items(entity_payload.get("extracted_entities"))
    links = _list_items(link_payload.get("candidate_document_person_links"))
    qualities = _quality_by_document(quality_dir)
    metadata_by_document = _metadata_by_document(qualities)
    links_by_document = _links_by_document(links)
    detail_logic_by_source = _detail_logic_by_source(sources_yaml=sources_yaml)

    claims: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    skipped_structured_documents: list[dict[str, Any]] = []

    for document_id, quality in sorted(qualities.items()):
        metadata = metadata_by_document.get(document_id, {})
        structured_claims, structured_skipped = _structured_claims_from_document(
            document_id=document_id,
            quality=quality,
            metadata=metadata,
            links=links_by_document.get(document_id, []),
            detail_logic_by_source=detail_logic_by_source,
        )
        claims.extend(structured_claims)
        skipped_structured_documents.extend(structured_skipped)

    for entity in entities:
        document_id = str(entity.get("source_document_id", "")).strip()
        if not document_id:
            skipped.append(_skipped_candidate_claim(entity=entity, reason="missing_source_document_id", links=[]))
            continue

        quality = qualities.get(document_id, {})
        document_links = links_by_document.get(document_id, [])
        skip_reason = _skip_reason(entity=entity, quality=quality, links=document_links)
        if skip_reason:
            skipped.append(_skipped_candidate_claim(entity=entity, reason=skip_reason, links=document_links))
            continue

        link = _link_for_entity(entity=entity, links=document_links)
        if not link:
            skipped.append(_skipped_candidate_claim(entity=entity, reason="ambiguous_or_missing_document_person_link", links=document_links))
            continue

        claim = _claim_from_entity(entity=entity, link=link, quality=quality)
        if claim:
            claims.append(claim)
        else:
            skipped.append(_skipped_candidate_claim(entity=entity, reason="unsupported_entity_context", links=document_links))

    claims = _deduplicate_claims(claims)
    claim_funnel_diagnostics = _build_claim_funnel_diagnostics(
        claims=claims,
        skipped=skipped,
        skipped_structured_documents=skipped_structured_documents,
    )
    payload = {
        "@type": "CandidateEvidenceClaimSet",
        "entities_json": str(entities_json),
        "links_json": str(links_json),
        "quality_dir": str(quality_dir),
        "claim_count": len(claims),
        "skipped_count": len(skipped),
        "skipped_structured_document_count": len(skipped_structured_documents),
        "candidate_evidence_claims": claims,
        "skipped_entities": skipped,
        "skipped_structured_documents": skipped_structured_documents,
        "claim_funnel_diagnostics": claim_funnel_diagnostics,
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_candidate_document_claims_markdown(payload), encoding="utf-8")

    return payload


def render_candidate_document_claims_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CandidateEvidenceClaim preview",
        "",
        f"- Claim candidati: `{payload.get('claim_count', 0)}`",
        f"- Entita saltate: `{payload.get('skipped_count', 0)}`",
        "",
        "## Diagnostica funnel claim",
        "",
    ]
    diagnostics = payload.get("claim_funnel_diagnostics")
    if isinstance(diagnostics, dict) and diagnostics:
        lines.extend(
            [
                f"- Stato funnel: `{diagnostics.get('funnel_status', '')}`",
                f"- Claim con segmento: `{diagnostics.get('claims_with_weak_segment_id_count', 0)}`",
                f"- Claim con solo chunk: `{diagnostics.get('claims_with_chunk_id_only_count', 0)}`",
                f"- Claim senza contesto segmentato: `{diagnostics.get('claims_without_segment_context_count', 0)}`",
                f"- Skipped con profili candidati: `{diagnostics.get('skipped_with_candidate_profiles_count', 0)}`",
                f"- Skipped senza profili candidati: `{diagnostics.get('skipped_without_candidate_profiles_count', 0)}`",
                f"- Prossima azione: {diagnostics.get('next_action', '')}",
            ]
        )
        counts_by_skip_reason = diagnostics.get("counts_by_skip_reason")
        if isinstance(counts_by_skip_reason, dict) and counts_by_skip_reason:
            lines.extend(["", "Motivi skip:"])
            for reason, count in sorted(counts_by_skip_reason.items()):
                lines.append(f"- `{reason}`: `{count}`")
        counts_by_next_action = diagnostics.get("counts_by_recommended_next_action")
        if isinstance(counts_by_next_action, dict) and counts_by_next_action:
            lines.extend(["", "Azioni consigliate:"])
            for action, count in sorted(counts_by_next_action.items()):
                lines.append(f"- `{action}`: `{count}`")
    else:
        lines.append("_Diagnostica funnel claim non disponibile._")
    lines.extend(
        [
            "",
        "## Claim candidati",
        "",
        ]
    )
    claims = payload.get("candidate_evidence_claims", [])
    if not isinstance(claims, list) or not claims:
        lines.append("_Nessun claim candidato._")
    else:
        for claim in claims:
            record = CandidateEvidenceClaimRecord.from_payload(claim)
            lines.extend(
                [
                    f"### {record.field}: {record.value}",
                    "",
                    f"- Profilo: `{record.profile_id}`",
                    f"- Documento: `{record.source_document_id}`",
                    f"- Fonte: `{record.source_id}`",
                    f"- Stato revisione: `{record.review_status}`",
                    f"- Metodo estrazione: `{record.extraction_method}`",
                    f"- Confidenza: `{record.confidence}`",
                    f"- Motivi: {record.reasons_text}",
                    f"- Segmento: `{record.weak_segment_id}`",
                    f"- Chunk: `{record.chunk_id}`",
                    f"- Evidenza: {record.evidence_span}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _structured_claims_from_document(
    *,
    document_id: str,
    quality: dict[str, Any],
    metadata: dict[str, Any],
    links: list[dict[str, Any]],
    detail_logic_by_source: dict[str, SourceDetailLogicDefinition],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    has_detail_metadata = _has_value(metadata.get("detail_assessment")) or _has_value(metadata.get("detail_extracted_fields_json"))
    if not has_detail_metadata:
        return [], []
    if str(quality.get("document_class", "")) in SKIPPED_DOCUMENT_CLASSES:
        return [], [_skipped_structured_document(document_id=document_id, reason=f"skipped_{quality.get('document_class')}", quality=quality, metadata=metadata, links=links)]
    if str(quality.get("quality_status", "")) != "ready_for_manual_review":
        return [], [_skipped_structured_document(document_id=document_id, reason="quality_not_ready_for_manual_review", quality=quality, metadata=metadata, links=links)]
    if _has_value(metadata.get("claim_eligible")) and not _as_bool(metadata.get("claim_eligible")):
        return [], [_skipped_structured_document(document_id=document_id, reason="metadata_claim_not_eligible", quality=quality, metadata=metadata, links=links)]
    if str(metadata.get("detail_assessment", "")) != "claim_candidates_extracted":
        return [], [_skipped_structured_document(document_id=document_id, reason="detail_assessment_not_claim_candidates_extracted", quality=quality, metadata=metadata, links=links)]

    link = _link_for_document(links)
    if not link:
        return [], [_skipped_structured_document(document_id=document_id, reason="ambiguous_or_missing_document_person_link", quality=quality, metadata=metadata, links=links)]

    source_id = str(metadata.get("source_id") or quality.get("source_id") or link.get("source_id") or "").strip()
    detail_logic = detail_logic_by_source.get(source_id)
    if detail_logic is None or not detail_logic.claim_mappings:
        return [], [_skipped_structured_document(document_id=document_id, reason="missing_source_detail_claim_mappings", quality=quality, metadata=metadata, links=links)]

    extracted_fields = _detail_extracted_fields(metadata.get("detail_extracted_fields_json"))
    if not extracted_fields:
        return [], [_skipped_structured_document(document_id=document_id, reason="missing_or_invalid_detail_extracted_fields_json", quality=quality, metadata=metadata, links=links)]

    claims: list[dict[str, Any]] = []
    profile_id = str(link.get("profile_id", "")).strip()
    for mapping in detail_logic.claim_mappings:
        value = str(extracted_fields.get(mapping.signal_field, "")).strip()
        if not value:
            continue
        normalized_value = _normalize_value(value)
        confidence = min(
            float(mapping.confidence or 0.0) if mapping.confidence else 0.85,
            float(link.get("score", 0.0) or 0.0),
            0.9,
        )
        reasons = [
            "detail_extracted_fields_json",
            f"source_detail_logic:{source_id}",
            f"detail_signal_field:{mapping.signal_field}",
            f"single_document_person_link:{profile_id}",
            "quality_ready_for_manual_review",
        ]
        claims.append(
            {
                "@type": "CandidateEvidenceClaim",
                "@id": _claim_id(
                    profile_id=profile_id,
                    source_document_id=document_id,
                    field=mapping.field,
                    normalized_value=normalized_value,
                ),
                "person_candidate_id": profile_id,
                "profile_id": profile_id,
                "profile_source_file": str(link.get("profile_source_file", "")),
                "field": mapping.field,
                "value": value,
                "normalized_value": normalized_value,
                "source_id": source_id,
                "source_document_id": document_id,
                "title": str(metadata.get("title") or quality.get("title") or link.get("title") or ""),
                "url": str(metadata.get("url") or quality.get("url") or link.get("url") or ""),
                "archival_reference": str(
                    metadata.get("archival_reference") or quality.get("archival_reference") or link.get("archival_reference") or ""
                ),
                "evidence_span": f"{mapping.signal_field}: {value}",
                "context": f"{mapping.signal_field}: {value}",
                "chunk_id": str(link.get("chunk_id") or ""),
                "weak_segment_id": str(link.get("weak_segment_id") or ""),
                "extraction_method": STRUCTURED_EXTRACTION_METHOD,
                "confidence": round(confidence, 3),
                "reasons": reasons,
                "review_status": "unreviewed",
                "entity_id": "",
                "candidate_document_person_link_id": str(link.get("@id", "")),
                "quality_assessment_file": str(quality.get("_quality_file", "")),
                "metadata_file": str(quality.get("metadata_file", "")),
                "detail_signal_field": mapping.signal_field,
            }
        )

    if not claims:
        return [], [_skipped_structured_document(document_id=document_id, reason="no_mapped_structured_field_values", quality=quality, metadata=metadata, links=links)]
    return claims, []


def _claim_from_entity(*, entity: dict[str, Any], link: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any] | None:
    field = _field_for_entity(entity)
    if not field:
        return None
    value = str(entity.get("value", "")).strip()
    normalized_value = str(entity.get("normalized_value", "")).strip() or value.casefold()
    document_id = str(entity.get("source_document_id", ""))
    profile_id = str(link.get("profile_id", ""))
    reasons = [*_list_strings(entity.get("reasons")), f"single_document_person_link:{profile_id}", "quality_ready_for_manual_review"]
    if str(entity.get("weak_segment_id", "")) and str(link.get("weak_segment_id", "")) == str(entity.get("weak_segment_id", "")):
        reasons.append("segment_scoped_document_person_link")
    elif str(entity.get("chunk_id", "")) and str(link.get("chunk_id", "")) == str(entity.get("chunk_id", "")):
        reasons.append("chunk_scoped_document_person_link")
    confidence = min(float(entity.get("score", 0.0) or 0.0), float(link.get("score", 0.0) or 0.0), 0.85)
    return {
        "@type": "CandidateEvidenceClaim",
        "@id": _claim_id(profile_id=profile_id, source_document_id=document_id, field=field, normalized_value=normalized_value),
        "person_candidate_id": profile_id,
        "profile_id": profile_id,
        "profile_source_file": str(link.get("profile_source_file", "")),
        "field": field,
        "value": value,
        "normalized_value": normalized_value,
        "source_id": str(entity.get("source_id") or link.get("source_id") or quality.get("source_id") or ""),
        "source_document_id": document_id,
        "title": str(entity.get("title") or link.get("title") or quality.get("title") or ""),
        "url": str(entity.get("url") or link.get("url") or quality.get("url") or ""),
        "archival_reference": str(entity.get("archival_reference") or link.get("archival_reference") or quality.get("archival_reference") or ""),
        "evidence_span": str(entity.get("context", "")),
        "context": str(entity.get("context", "")),
        "chunk_id": str(entity.get("chunk_id") or link.get("chunk_id") or ""),
        "weak_segment_id": str(entity.get("weak_segment_id") or link.get("weak_segment_id") or ""),
        "extraction_method": "document_entity_context_rules",
        "confidence": round(confidence, 3),
        "reasons": reasons,
        "review_status": "unreviewed",
        "entity_id": str(entity.get("@id", "")),
        "candidate_document_person_link_id": str(link.get("@id", "")),
        "quality_assessment_file": str(quality.get("_quality_file", "")),
    }


def _field_for_entity(entity: dict[str, Any]) -> str:
    entity_type = str(entity.get("entity_type", ""))
    context = str(entity.get("context", "")).casefold()
    if entity_type == "formation":
        return "formation.name"
    if entity_type != "date":
        return ""
    if re.search(r"\b(nato|nata)\s+il\b", context):
        return "birth.date"
    if re.search(r"\b(morto|morta|deceduto|deceduta|caduto|caduta)\s+il\b", context):
        return "death.date"
    if re.search(r"\bcadde\b(?:\W+\w+){0,8}\W+il\b", context):
        return "death.date"
    return ""


def _skip_reason(*, entity: dict[str, Any], quality: dict[str, Any], links: list[dict[str, Any]]) -> str:
    if not quality:
        return "quality_missing"
    if str(quality.get("document_class", "")) in SKIPPED_DOCUMENT_CLASSES:
        return f"skipped_{quality.get('document_class')}"
    if str(quality.get("quality_status", "")) != "ready_for_manual_review":
        return "quality_not_ready_for_manual_review"
    if not links:
        return "ambiguous_or_missing_document_person_link"
    if str(entity.get("review_status", "")) != "unreviewed":
        return "entity_review_status_not_unreviewed"
    return ""


def _link_for_entity(*, entity: dict[str, Any], links: list[dict[str, Any]]) -> dict[str, Any]:
    if len(links) == 1:
        return links[0]

    profile_ids = {str(link.get("profile_id", "")).strip() for link in links if str(link.get("profile_id", "")).strip()}
    if len(profile_ids) == 1:
        return sorted(links, key=lambda link: float(link.get("score", 0.0) or 0.0), reverse=True)[0]

    weak_segment_id = str(entity.get("weak_segment_id", "")).strip()
    if weak_segment_id:
        segment_links = [link for link in links if str(link.get("weak_segment_id", "")).strip() == weak_segment_id]
        if len(segment_links) == 1:
            return segment_links[0]

    chunk_id = str(entity.get("chunk_id", "")).strip()
    if chunk_id:
        chunk_links = [link for link in links if str(link.get("chunk_id", "")).strip() == chunk_id]
        if len(chunk_links) == 1:
            return chunk_links[0]

    return {}


def _link_for_document(links: list[dict[str, Any]]) -> dict[str, Any]:
    if len(links) == 1:
        return links[0]
    profile_ids = {str(link.get("profile_id", "")).strip() for link in links if str(link.get("profile_id", "")).strip()}
    if len(profile_ids) == 1:
        return sorted(links, key=lambda link: float(link.get("score", 0.0) or 0.0), reverse=True)[0]
    return {}


def _quality_by_document(quality_dir: Path) -> dict[str, dict[str, Any]]:
    qualities: dict[str, dict[str, Any]] = {}
    for quality_path in sorted(quality_dir.rglob("*.quality.json")):
        quality = _load_json_object(quality_path)
        document_id = str(quality.get("source_document_id", "")).strip()
        if not document_id:
            continue
        quality["_quality_file"] = str(quality_path)
        qualities[document_id] = quality
    return qualities


def _metadata_by_document(qualities: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metadata_by_document: dict[str, dict[str, Any]] = {}
    for document_id, quality in qualities.items():
        metadata_file = str(quality.get("metadata_file", "")).strip()
        metadata = _load_json_object(Path(metadata_file)) if metadata_file else {}
        if not metadata:
            metadata = quality
        metadata_by_document[document_id] = metadata
    return metadata_by_document


def _detail_logic_by_source(*, sources_yaml: Path | None) -> dict[str, SourceDetailLogicDefinition]:
    search_roots = _detail_logic_search_roots(sources_yaml=sources_yaml)
    by_source: dict[str, SourceDetailLogicDefinition] = {}
    for root in search_roots:
        detail_dir = root / "source_detail_logic"
        if not detail_dir.exists():
            continue
        for path in sorted(detail_dir.glob("*.yaml")):
            try:
                definition = load_source_detail_logic(path)
            except (OSError, ValueError):
                continue
            if definition.source_id and definition.source_id not in by_source:
                by_source[definition.source_id] = definition
    return by_source


def _detail_logic_search_roots(*, sources_yaml: Path | None) -> list[Path]:
    roots: list[Path] = []
    if sources_yaml is not None:
        roots.append(resolve_source_catalog_root(registry_path=sources_yaml))
    roots.append(resolve_source_catalog_root(Path.cwd()))
    module_root = Path(__file__).resolve().parents[3]
    roots.append(resolve_source_catalog_root(module_root))
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _detail_extracted_fields(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        payload = value
    else:
        try:
            payload = json.loads(str(value or ""))
        except json.JSONDecodeError:
            return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(item).strip() for key, item in payload.items() if str(item).strip()}


def _links_by_document(links: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_document: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        document_id = str(link.get("source_document_id", "")).strip()
        if not document_id:
            continue
        by_document.setdefault(document_id, []).append(link)
    return by_document


def _deduplicate_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str, str]] = []
    for claim in claims:
        record = CandidateEvidenceClaimRecord.from_payload(claim)
        key = record.dedupe_key
        if key not in by_key:
            by_key[key] = claim
            order.append(key)
            continue
        if _claim_priority(record) > _claim_priority(CandidateEvidenceClaimRecord.from_payload(by_key[key])):
            by_key[key] = claim
    return [by_key[key] for key in order]


def _claim_priority(claim: CandidateEvidenceClaimRecord) -> int:
    return claim.priority(structured_extraction_method=STRUCTURED_EXTRACTION_METHOD)


def _claim_id(*, profile_id: str, source_document_id: str, field: str, normalized_value: str) -> str:
    digest = hashlib.sha256(f"{profile_id}|{source_document_id}|{field}|{normalized_value}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-evidence-claim:{digest}"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _has_value(value: Any) -> bool:
    return value not in (None, "")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "si", "sì", "sÃ¬"}


def _normalize_value(value: str) -> str:
    return " ".join(value.split()).casefold()


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera CandidateEvidenceClaim preview-only da analisi documentale.")
    parser.add_argument("--entities-json", default="risultati/document_analysis/extracted_entities.json")
    parser.add_argument("--links-json", default="risultati/document_analysis/candidate_document_person_links.json")
    parser.add_argument("--quality-dir", default="data/processed/documents")
    parser.add_argument("--sources-yaml", default="")
    parser.add_argument("--output-json", default="risultati/document_analysis/candidate_evidence_claims.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/candidate_evidence_claims.md")
    args = parser.parse_args()

    payload = build_candidate_document_claims(
        entities_json=Path(args.entities_json),
        links_json=Path(args.links_json),
        quality_dir=Path(args.quality_dir),
        sources_yaml=Path(args.sources_yaml) if args.sources_yaml else None,
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"CandidateEvidenceClaim JSON scritto in {args.output_json}")
    print(f"CandidateEvidenceClaim Markdown scritto in {args.output_md}")
    print(f"Claim candidati: {payload['claim_count']}")
    print(f"Entita saltate: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
