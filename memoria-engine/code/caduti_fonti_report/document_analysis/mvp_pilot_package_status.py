from __future__ import annotations


def pilot_package_status_and_action(
    *,
    profile_count: int,
    document_count: int,
    link_count: int,
    claim_count: int,
    signal_count: int,
    ready_count: int,
    blockers: list[str],
) -> tuple[str, str]:
    """Return the package readiness status and the next human action."""
    if profile_count == 0:
        return "needs_profiles", "Selezionare 5-10 PersonResearchProfile pilota."
    if document_count == 0:
        return "needs_documents", "Registrare o collegare documenti revisionabili ai profili pilota."
    if link_count == 0:
        return "needs_document_person_links", "Generare o revisionare link documento-persona candidati."
    if claim_count == 0:
        if signal_count > 0:
            return "needs_document_signal_review", "Revisionare le piste documentali e segmentare i documenti multi-scheda prima dei claim."
        return "needs_candidate_claims", "Migliorare testi, qualita' documento o regole per produrre claim candidati."
    if ready_count == 0:
        return "needs_profile_readiness", "Risolvere i blocchi delle schede pilota prima della review storica."
    if blockers:
        return "ready_with_document_intake_warnings", "Revisionare le schede pronte e pianificare i blocchi documentali residui."
    return "ready_for_human_review", "Passare alla review queue e alle decisioni del revisore storico."
