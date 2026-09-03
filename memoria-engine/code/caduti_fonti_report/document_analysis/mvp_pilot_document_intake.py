from __future__ import annotations

from typing import Any


def build_document_intake_blockers(
    *,
    input_summary: dict[str, Any],
    ocr_summary: dict[str, Any],
    text_summary: dict[str, Any],
    metadata_summary: dict[str, Any],
    image_ocr_readiness: dict[str, Any],
    mvp_document_count: int,
) -> list[str]:
    blockers: list[str] = []
    action_counts = input_summary.get("action_counts", {})
    ocr_required = _int_value(action_counts.get("image_ocr_required") if isinstance(action_counts, dict) else 0)
    pdf_required = _int_value(action_counts.get("pdf_text_extraction_required") if isinstance(action_counts, dict) else 0)
    manual_review = _int_value(action_counts.get("manual_review_required") if isinstance(action_counts, dict) else 0)
    if input_summary.get("available") and input_summary.get("asset_count", 0) == 0:
        blockers.append("Nessun asset raw rilevato nella run locale.")
    if ocr_required > 0 and not ocr_summary.get("available"):
        blocking_images = _int_value(image_ocr_readiness.get("blocking_image_count"))
        unknown_images = _int_value(image_ocr_readiness.get("unknown_image_count"))
        priority_images = blocking_images + unknown_images
        if priority_images > 0:
            blockers.append(
                f"{priority_images} immagini richiedono OCR prioritario, ma non esiste un report OCR batch collegato."
            )
    if pdf_required > 0:
        blockers.append(f"{pdf_required} PDF richiedono estrazione testo o revisione manuale.")
    if manual_review > 0:
        blockers.append(f"{manual_review} asset richiedono revisione manuale prima di produrre evidenze.")
    ocr_counts = ocr_summary.get("summary", {})
    if isinstance(ocr_counts, dict) and _int_value(ocr_counts.get("error")) > 0:
        blockers.append(f"{_int_value(ocr_counts.get('error'))} documenti OCR sono in errore.")
    if text_summary.get("available") and text_summary.get("extracted_count", 0) == 0 and metadata_summary.get("document_count", 0) > 0:
        blockers.append("Nessun testo estratto dai documenti metadatati: servono OCR, trascrizione o text extraction.")
    if mvp_document_count == 0:
        blockers.append("Nessun documento raggiunge il riepilogo MVP come base per link o claim candidati.")
    return blockers


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
