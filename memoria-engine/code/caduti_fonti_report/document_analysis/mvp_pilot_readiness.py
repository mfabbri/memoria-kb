from __future__ import annotations


def readiness_status_and_action(
    *, document_count: int, link_count: int, claim_count: int, signal_count: int
) -> tuple[str, str]:
    if document_count == 0:
        return "needs_documents", "Registrare o collegare almeno un documento revisionabile."
    if link_count == 0:
        return "needs_links", "Verificare il link candidato documento-persona."
    if claim_count == 0:
        if signal_count > 0:
            return "needs_signal_review", "Revisionare piste documentali e valutare segmentazione per produrre claim candidati."
        return "needs_claims", "Migliorare testo/OCR o regole per produrre claim candidati."
    return "ready_for_review", "Revisionare documenti, link e claim candidati."
