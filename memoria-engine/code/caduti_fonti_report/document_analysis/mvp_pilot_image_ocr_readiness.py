from __future__ import annotations

from typing import Any


def build_image_ocr_readiness(*, input_plan: dict[str, Any], metadata_report: dict[str, Any]) -> dict[str, Any]:
    assets = [
        asset
        for asset in _list_items(input_plan.get("assets"))
        if str(asset.get("recommended_action", "")) == "image_ocr_required"
    ]
    metadata_by_document_id: dict[str, dict[str, Any]] = {}
    metadata_by_raw_file: dict[str, dict[str, Any]] = {}
    for item in _list_items(metadata_report.get("documents")):
        document_id = str(item.get("source_document_id", "")).strip()
        raw_file = _normalized_path_key(item.get("raw_file"))
        if document_id:
            metadata_by_document_id[document_id] = item
        if raw_file:
            metadata_by_raw_file[raw_file] = item

    support_images: list[dict[str, str]] = []
    blocking_images: list[dict[str, str]] = []
    unknown_images: list[dict[str, str]] = []
    for asset in assets:
        metadata = _metadata_for_asset(asset, metadata_by_document_id, metadata_by_raw_file)
        item = {
            "source_document_id": str(asset.get("source_document_id", "")),
            "raw_file": str(asset.get("raw_file", "")),
        }
        if not metadata:
            unknown_images.append(item)
            continue
        if _is_false_like(metadata.get("claim_eligible")):
            support_images.append(item)
        else:
            blocking_images.append(item)

    warnings: list[str] = []
    if support_images:
        warnings.append(
            f"{len(support_images)} immagini di supporto claim_eligible=false non bloccano il pacchetto; restano da revisione/OCR se necessario."
        )
    if unknown_images:
        warnings.append(
            f"{len(unknown_images)} immagini richiedono metadata o sidecar piu' chiari prima di degradarle a warning."
        )

    return {
        "@type": "MvpImageOcrReadiness",
        "image_ocr_required_count": len(assets),
        "blocking_image_count": len(blocking_images),
        "support_image_count": len(support_images),
        "unknown_image_count": len(unknown_images),
        "blocking_images": blocking_images[:20],
        "support_images": support_images[:20],
        "unknown_images": unknown_images[:20],
        "warnings": warnings,
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
    }


def _metadata_for_asset(
    asset: dict[str, Any],
    metadata_by_document_id: dict[str, dict[str, Any]],
    metadata_by_raw_file: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    document_id = str(asset.get("source_document_id", "")).strip()
    if document_id and document_id in metadata_by_document_id:
        return metadata_by_document_id[document_id]
    raw_file = _normalized_path_key(asset.get("raw_file"))
    if raw_file and raw_file in metadata_by_raw_file:
        return metadata_by_raw_file[raw_file]
    return {}


def _normalized_path_key(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip().casefold()


def _is_false_like(value: Any) -> bool:
    if isinstance(value, bool):
        return value is False
    return str(value).strip().casefold() in {"0", "false", "no", "not_claim_eligible"}


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
