from __future__ import annotations

from ..models import Caduto, Source, SourceResult
from .cwgc import run_cwgc_source
from .http_sources import run_http_source
from .local_excel import run_local_excel_source
from .obd_memorial import run_obd_memorial_source
from .pamyat_naroda import run_pamyat_naroda_source
from .storia_memoria_bo import run_storia_memoria_bo_source
from .tna import run_tna_advanced_search


def run_source(source: Source, caduto: Caduto) -> SourceResult:
    query = source.build_query(caduto)
    search_url = source.search_url_builder(query)

    if source.kind == "credentialed":
        missing = [key for key, value in source.credentials.items() if not str(value).strip()]
        if missing:
            return SourceResult(
                source_id=source.source_id,
                source_name=source.source_name,
                status="needs_credentials",
                note=f"{source.note} Credenziali mancanti nel file YAML: {', '.join(missing)}.",
                query=query,
                search_url=search_url,
            )
        if source.source_id in {"tna_wo417", "tna_hs9"}:
            return run_tna_advanced_search(source, caduto)

    if source.kind == "local_excel":
        return run_local_excel_source(source, caduto, query, search_url)

    if source.kind == "storia_memoria_bo":
        return run_storia_memoria_bo_source(source, caduto, query, search_url)

    if source.kind == "obd_memorial":
        return run_obd_memorial_source(source, caduto, query, search_url)

    if source.kind == "pamyat_naroda":
        return run_pamyat_naroda_source(source, caduto, query, search_url)

    if source.kind == "cwgc":
        return run_cwgc_source(source, caduto, query, search_url)

    return run_http_source(source, caduto, query, search_url)
