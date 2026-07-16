from __future__ import annotations

from collections.abc import Callable

from ..models import Caduto, EvidenceClaim, PersonQuery, Source, SourceDocument, SourceResult
from .base import run_source


class LegacyConnectorAdapter:
    def __init__(
        self,
        source: Source,
        run_source_func: Callable[[Source, Caduto], SourceResult] = run_source,
    ) -> None:
        self.source = source
        self.source_id = source.source_id
        self.run_source_func = run_source_func

    def search_person(self, query: PersonQuery) -> list[SourceResult]:
        caduto = caduto_from_person_query(query)
        return [self.run_source_func(self.source, caduto)]

    def fetch_detail(self, result: SourceResult) -> list[SourceDocument]:
        return []

    def extract_evidence(self, document: SourceDocument) -> list[EvidenceClaim]:
        return []


def caduto_from_person_query(query: PersonQuery) -> Caduto:
    metadata = query.metadata
    return Caduto(
        intestazione_pdf=metadata.get("intestazione_pdf") or query.full_name,
        nome=metadata.get("nome") or query.full_name,
        origine_sulla_lapide=metadata.get("origine_sulla_lapide") or query.place_hint,
        nascita=metadata.get("nascita") or query.birth_date,
        morte=metadata.get("morte") or query.death_date,
        ruolo_affiliazione=metadata.get("ruolo_affiliazione") or query.formation,
        fonti_richiamate=metadata.get("fonti_richiamate", ""),
        profilo_biografico=metadata.get("profilo_biografico", ""),
        episodio_documentato=metadata.get("episodio_documentato") or query.event_hint,
    )
