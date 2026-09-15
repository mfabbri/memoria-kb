from __future__ import annotations


def build_signal_blockers(
    *,
    document_count: int,
    unique_document_count: int,
    duplicate_groups: list[dict],
    weak_nominal_link_count: int,
    link_count: int,
    claim_count: int,
    profiles_with_links_no_claims: list[dict],
) -> list[str]:
    blockers: list[str] = []
    if document_count == 0:
        blockers.append("Nessun documento collegato al pacchetto MVP.")
    elif duplicate_groups:
        blockers.append(
            f"{document_count - unique_document_count} documenti sembrano duplicati o copie dello stesso contenuto."
        )
    if link_count > 0 and weak_nominal_link_count == link_count:
        blockers.append("Tutti i link persona-documento sono match nominali deboli: serve conferma contestuale.")
    elif weak_nominal_link_count > 0:
        blockers.append(f"{weak_nominal_link_count} link persona-documento sono match nominali deboli.")
    if profiles_with_links_no_claims:
        blockers.append(f"{len(profiles_with_links_no_claims)} profili hanno link candidati ma zero claim.")
    if claim_count == 0 and link_count > 0:
        blockers.append("Nessun claim candidato prodotto nonostante i link documento-persona.")
    if not blockers:
        blockers.append("Segnale MVP leggibile: passare a review queue e decisioni umane.")
    return blockers
