"""Preview-only contract for an injected visual ambiguity resolver.

The module does not call a model or a network service.  A caller may inject a
resolver for an offline experiment, while the original OCR and provenance stay
unchanged and the result cannot be treated as an approved transcription.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


_ALLOWED_TEXT = "[illeggibile]"


def build_visual_resolver_preview(
    *,
    page_id: str,
    source_image_hash: str,
    variant_id: str,
    source_bbox: Sequence[int],
    crop_artifact: str,
    candidate_ocr: str,
    resolver: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    resolver_id: str = "injected-offline",
) -> dict[str, Any]:
    """Run an injected resolver and return a provenance-safe preview result."""
    _required_text(page_id, "page_id")
    _required_text(source_image_hash, "source_image_hash")
    _required_text(variant_id, "variant_id")
    _required_text(crop_artifact, "crop_artifact")
    if not isinstance(candidate_ocr, str):
        raise TypeError("candidate_ocr deve essere una stringa.")
    bbox = _validated_bbox(source_bbox)
    if not callable(resolver):
        raise TypeError("resolver deve essere una funzione iniettata.")
    _required_text(resolver_id, "resolver_id")

    request = {
        "page_id": page_id,
        "source_image_hash": source_image_hash,
        "variant_id": variant_id,
        "source_bbox": bbox,
        "crop_artifact": crop_artifact,
        "candidate_ocr": candidate_ocr,
        "temperature": 0.0,
        "output_schema": {"text": "visible text or [illeggibile]"},
    }
    response = resolver(request)
    if not isinstance(response, Mapping):
        raise ValueError("Il resolver deve restituire una mappatura con il solo campo text.")
    if set(response) != {"text"} or not isinstance(response.get("text"), str):
        raise ValueError("L'output del resolver deve contenere esclusivamente text.")
    resolved_text = response["text"].strip()
    if not resolved_text:
        raise ValueError("text del resolver non puo' essere vuoto.")

    return {
        "@type": "OcrVisualAmbiguityResolverPreview",
        "schema_version": "1.0",
        "review_status": "preview-only",
        "accuracy_claim": "none",
        "resolver_id": resolver_id,
        "temperature": 0.0,
        "source_page": {
            "page_id": page_id,
            "source_image_hash": source_image_hash,
            "variant_id": variant_id,
            "source_bbox": bbox,
            "crop_artifact": crop_artifact,
        },
        "candidate_ocr": candidate_ocr,
        "resolver_output": {"text": resolved_text},
        "promotion_status": "unreviewed",
    }


def _required_text(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} deve essere testo non vuoto.")


def _validated_bbox(value: Sequence[int]) -> list[int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 4:
        raise ValueError("source_bbox deve contenere quattro interi.")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise ValueError("source_bbox deve contenere quattro interi.")
    left, top, right, bottom = value
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise ValueError("source_bbox deve essere un rettangolo non vuoto.")
    return [left, top, right, bottom]
