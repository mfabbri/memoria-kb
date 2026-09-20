"""Deterministic, provenance-safe document structure reconstruction.

This module deliberately consumes ``OcrPageEvidence`` regions rather than a
normalised page string.  Its two initial profiles are narrow, synthetic-fixture
tested heuristics; they produce reviewable structure, never corrected OCR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any, Iterable, Mapping


_BLOCK_KINDS = {"heading", "paragraph", "key_value", "list", "table", "unknown"}
_PROFILES = {"leader_list_report", "numbered_report"}
_NUMBERED = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+.+")
_LEADER = re.compile(r"^(?P<label>.+?)(?:\s*[.·•]{2,}\s*|\s{3,})(?P<value>\S.+)$")


@dataclass(frozen=True)
class EvidenceReference:
    """Immutable identity and provenance of the exact OCR evidence variant."""

    page_id: str
    source_image_hash: str
    transform_id: str
    engine: str
    language: str
    source_page_json: str
    model_json: str
    image_transform_json: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"page_id": self.page_id, "source_image_hash": self.source_image_hash,
                "transform_id": self.transform_id, "engine": self.engine, "language": self.language,
                "source_page": json.loads(self.source_page_json), "model": json.loads(self.model_json),
                "image_transform": json.loads(self.image_transform_json) if self.image_transform_json else None}


@dataclass(frozen=True)
class DocumentBlock:
    """A derived block whose text is supported by the listed OCR regions."""

    block_id: str
    kind: str
    source_region_ids: tuple[str, ...]
    text: str
    status: str
    structure_confidence: float
    value: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _BLOCK_KINDS:
            raise ValueError(f"Tipo blocco non supportato: {self.kind}.")
        if not self.source_region_ids:
            raise ValueError("Ogni blocco strutturale richiede source_region_ids.")
        if not 0.0 <= self.structure_confidence <= 1.0:
            raise ValueError("structure_confidence deve essere compresa tra 0 e 1.")


@dataclass(frozen=True)
class DocumentStructure:
    """A page-scoped, derived structure distinct from OCR evidence confidence."""

    page_id: str
    profile: str
    blocks: tuple[DocumentBlock, ...]
    source_evidence: EvidenceReference
    source_evidence_type: str = "OcrPageEvidence"
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {"@type": "DocumentStructure", "schema_version": self.schema_version,
                "page_id": self.page_id, "profile": self.profile,
                "source_evidence_type": self.source_evidence_type,
                "source_evidence": self.source_evidence.to_dict(),
                "blocks": [asdict(block) | {"source_region_ids": list(block.source_region_ids)} for block in self.blocks]}


@dataclass(frozen=True)
class _Region:
    region_id: str
    text: str
    left: float | None
    top: float | None
    bottom: float | None


def reconstruct_document_structure(*, evidence: Mapping[str, Any], profile: str) -> DocumentStructure:
    """Build one explicit profile from geometry-first OCR page evidence.

    OCR confidence is intentionally not read: ``structure_confidence`` records
    how unambiguous the layout rule was, and must not be interpreted as OCR
    accuracy.
    """
    if profile not in _PROFILES:
        raise ValueError(f"Profilo strutturale non supportato: {profile}.")
    if evidence.get("@type") != "OcrPageEvidence":
        raise ValueError("Il parser richiede un OcrPageEvidence.")
    evidence_reference = _evidence_reference(evidence)
    regions = _regions(evidence.get("regions"))
    blocks = _leader_list_blocks(regions) if profile == "leader_list_report" else _numbered_blocks(regions)
    return DocumentStructure(page_id=evidence_reference.page_id, profile=profile, blocks=tuple(blocks),
                             source_evidence=evidence_reference)


def render_document_structure_markdown(structure: DocumentStructure) -> str:
    """Render only derived structure; every content block keeps provenance."""
    if not isinstance(structure, DocumentStructure):
        raise TypeError("Il renderer Markdown richiede DocumentStructure.")
    lines = ["# Document structure (unreviewed)", "", f"- Page ID: `{_inline(structure.page_id)}`",
             f"- Profile: `{_inline(structure.profile)}`",
             f"- Evidence source image hash: `{_inline(structure.source_evidence.source_image_hash)}`",
             f"- Evidence transform ID: `{_inline(structure.source_evidence.transform_id)}`",
             f"- OCR engine/language: `{_inline(structure.source_evidence.engine)}` / `{_inline(structure.source_evidence.language)}`",
             f"<!-- evidence_reference: {_canonical_json(structure.source_evidence.to_dict())} -->",
             "- Structure is derived from OCR regions and is not an accuracy claim.", ""]
    for block in structure.blocks:
        provenance = ", ".join(block.source_region_ids)
        lines.append(f"<!-- source_region_ids: {provenance}; status: {block.status}; structure_confidence: {block.structure_confidence:.2f} -->")
        if block.kind == "heading":
            lines.extend([f"## {_inline(block.text)}", ""])
        elif block.kind == "key_value":
            lines.extend([f"- **{_inline(block.text)}:** {_inline(block.value or '[illeggibile]')}", ""])
        elif block.kind == "list":
            lines.extend([f"- {_inline(block.text)}", ""])
        elif block.kind == "table":
            lines.extend([f"| {_inline(block.text)} |", "| --- |", ""])
        elif block.kind == "unknown":
            lines.extend([f"[illeggibile] — {_inline(block.text) if block.text else 'OCR text unavailable'}", ""])
        else:
            lines.extend([_inline(block.text), ""])
    return "\n".join(lines).rstrip() + "\n"


def _evidence_reference(evidence: Mapping[str, Any]) -> EvidenceReference:
    values: dict[str, str] = {}
    for field in ("page_id", "source_image_hash", "transform_id", "engine", "language"):
        value = evidence.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"OcrPageEvidence senza {field} valido.")
        values[field] = value.strip()
    source_page, model, image_transform = evidence.get("source_page"), evidence.get("model"), evidence.get("image_transform")
    if not isinstance(source_page, Mapping) or not isinstance(model, Mapping):
        raise ValueError("OcrPageEvidence senza source_page o model validi.")
    if image_transform is not None and not isinstance(image_transform, Mapping):
        raise ValueError("OcrPageEvidence con image_transform non valida.")
    return EvidenceReference(**values, source_page_json=_canonical_json(source_page), model_json=_canonical_json(model),
                             image_transform_json=_canonical_json(image_transform) if image_transform is not None else None)


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Provenance OcrPageEvidence non serializzabile.") from exc


def _regions(value: object) -> list[_Region]:
    if not isinstance(value, list):
        raise ValueError("OcrPageEvidence senza lista regions valida.")
    result: list[_Region] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError("Ogni regione OCR deve essere un oggetto.")
        region_id = item.get("region_id")
        if not isinstance(region_id, str) or not region_id.strip():
            raise ValueError(f"Regione OCR {index} senza region_id valido.")
        if region_id.strip() in seen_ids:
            raise ValueError(f"region_id OCR duplicato: {region_id.strip()}.")
        seen_ids.add(region_id.strip())
        text = item.get("text")
        if not isinstance(text, str):
            raise ValueError(f"Regione OCR {region_id} senza testo valido.")
        left, top, bottom = _geometry(item.get("geometry"), index)
        result.append(_Region(region_id.strip(), text, left, top, bottom))
    return sorted(result, key=lambda region: (region.top is None, region.top or 0, region.left or 0, region.region_id))


def _geometry(value: object, index: int) -> tuple[float | None, float | None, float | None]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Regione OCR {index} senza geometry valida.")
    bbox = value.get("bbox")
    if bbox is None:
        return None, None, None
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or not all(isinstance(item, (int, float)) for item in bbox):
        raise ValueError(f"Regione OCR {index} senza bbox [left, top, right, bottom] valida.")
    left, top, right, bottom = (float(item) for item in bbox)
    if right < left or bottom < top:
        raise ValueError(f"Regione OCR {index} con bbox non ordinata.")
    return left, top, bottom


def _leader_list_blocks(regions: Iterable[_Region]) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    ordered = list(regions)
    consumed: set[str] = set()
    for position, region in enumerate(ordered):
        if region.region_id in consumed:
            continue
        text = region.text.strip()
        if region.top is None:
            blocks.append(_block("unknown", (region,), text, "uncertain", 0.0))
            continue
        if not _has_text(text):
            blocks.append(_block("unknown", (region,), "", "uncertain", 0.0))
            continue
        matched = _LEADER.match(text)
        if matched:
            blocks.append(_block("key_value", (region,), matched.group("label").strip(), "inferred", 0.95,
                                 matched.group("value").strip()))
        elif _is_heading(text):
            blocks.append(_block("heading", (region,), text, "inferred", 0.75))
        else:
            value_region = _aligned_value(region, ordered[position + 1:], consumed)
            if value_region is None:
                blocks.append(_block("unknown", (region,), text, "unrecognized", 0.25))
            else:
                consumed.add(value_region.region_id)
                blocks.append(_block("key_value", (region, value_region), text, "inferred", 0.85,
                                     value_region.text.strip()))
    return blocks


def _aligned_value(label: _Region, following: Iterable[_Region], consumed: set[str]) -> _Region | None:
    """Find a same-row, right-aligned value without using OCR confidence."""
    for candidate in following:
        if candidate.region_id in consumed:
            continue
        if candidate.top is None or label.top is None or label.bottom is None:
            continue
        if candidate.top - label.bottom > 24:
            return None
        if abs(candidate.top - label.top) <= 18 and candidate.left >= label.left + 40 and _has_text(candidate.text.strip()):
            return candidate
    return None


def _numbered_blocks(regions: list[_Region]) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    previous: _Region | None = None
    for region in regions:
        text = region.text.strip()
        if region.top is None:
            blocks.append(_block("unknown", (region,), text, "uncertain", 0.0))
        elif not _has_text(text):
            blocks.append(_block("unknown", (region,), "", "uncertain", 0.0))
        elif _NUMBERED.match(text) or _is_heading(text):
            blocks.append(_block("heading", (region,), text, "inferred", 0.90 if _NUMBERED.match(text) else 0.75))
        elif _is_continuation(region, previous, blocks):
            prior = blocks[-1]
            blocks[-1] = DocumentBlock(prior.block_id, "paragraph", prior.source_region_ids + (region.region_id,),
                                       f"{prior.text} {text}", "inferred", 0.80)
        else:
            blocks.append(_block("paragraph", (region,), text, "inferred", 0.60))
        previous = region
    return blocks


def _is_continuation(region: _Region, previous: _Region | None, blocks: list[DocumentBlock]) -> bool:
    if previous is None or previous.top is None or region.top is None or not blocks or blocks[-1].kind != "paragraph":
        return False
    vertical_gap = region.top - (previous.bottom or previous.top)
    return 0 <= vertical_gap <= 36 and region.left >= previous.left + 12


def _is_heading(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    return bool(letters) and len(text) <= 90 and all(character.isupper() for character in letters)


def _has_text(text: str) -> bool:
    return any(character.isalnum() for character in text)


def _block(kind: str, regions: tuple[_Region, ...], text: str, status: str, confidence: float,
           value: str | None = None) -> DocumentBlock:
    return DocumentBlock(block_id=f"block-{len(regions)}-{regions[0].region_id}", kind=kind,
                         source_region_ids=tuple(region.region_id for region in regions), text=text,
                         status=status, structure_confidence=confidence, value=value)


def _inline(value: str) -> str:
    return " ".join(value.replace("\n", " ").split())
