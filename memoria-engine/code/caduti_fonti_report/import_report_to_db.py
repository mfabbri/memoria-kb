from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Caduto, PersonQuery, SearchHit, SearchRun, SourceDocument, SourceResult, person_query_from_caduto
from .raw_store import slugify_identifier
from .sqlite_store import SQLiteEvidenceStore


def import_report_to_db(
    *,
    input_json_path: Path,
    db_path: Path,
    run_id: str = "",
) -> dict[str, object]:
    payload = json.loads(input_json_path.read_text(encoding="utf-8"))
    generated_at = str(payload.get("generated_at") or datetime.now(UTC).isoformat())
    source_selection = _dict(payload.get("source_selection", {}))
    effective_run_id = run_id or f"report:{input_json_path.stem}:{generated_at}"

    run = SearchRun(
        run_id=effective_run_id,
        timestamp=generated_at,
        input_file=str(input_json_path),
        source_ids=_string_list(source_selection.get("selected_source_ids", [])),
        parameters={"import_file": str(input_json_path)},
        metadata={
            "import_type": "caduti_fonti_report",
            "source_file": str(source_selection.get("source_file", "")),
            "used_fallback": str(source_selection.get("used_fallback", False)),
        },
    )

    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    store.delete_run(effective_run_id)
    store.insert_search_run(run)

    person_query_count = 0
    source_result_count = 0
    source_document_count = 0

    for caduto_entry in _list(payload.get("caduti", [])):
        caduto_payload = _dict(caduto_entry.get("caduto", {}))
        caduto = _caduto_from_payload(caduto_payload)
        person_query = person_query_from_caduto(caduto)
        store.insert_person_query(effective_run_id, person_query)
        person_query_count += 1

        for result_payload in _list(caduto_entry.get("results", [])):
            source_result = _source_result_from_payload(_dict(result_payload))
            store.insert_source_result(effective_run_id, source_result)
            source_result_count += 1

            for hit_index, hit in enumerate(source_result.hits, start=1):
                document = _source_document_from_hit(
                    run_id=effective_run_id,
                    source_result=source_result,
                    person_query=person_query,
                    hit=hit,
                    hit_index=hit_index,
                    generated_at=generated_at,
                )
                store.insert_source_document(effective_run_id, document)
                source_document_count += 1

    return {
        "run_id": effective_run_id,
        "person_queries": person_query_count,
        "source_results": source_result_count,
        "source_documents": source_document_count,
        "db": str(db_path),
    }


def _caduto_from_payload(payload: dict[str, Any]) -> Caduto:
    return Caduto(
        intestazione_pdf=str(payload.get("intestazione_pdf", "")),
        nome=str(payload.get("nome", "")),
        origine_sulla_lapide=str(payload.get("origine_sulla_lapide", "")),
        nascita=str(payload.get("nascita", "")),
        morte=str(payload.get("morte", "")),
        ruolo_affiliazione=str(payload.get("ruolo_affiliazione", "")),
        fonti_richiamate=str(payload.get("fonti_richiamate", "")),
        profilo_biografico=str(payload.get("profilo_biografico", "")),
        episodio_documentato=str(payload.get("episodio_documentato", "")),
    )


def _source_result_from_payload(payload: dict[str, Any]) -> SourceResult:
    return SourceResult(
        source_id=str(payload.get("source_id", "")),
        source_name=str(payload.get("source_name", "")),
        status=str(payload.get("status", "")),
        note=str(payload.get("note", "")),
        query=str(payload.get("query", "")),
        search_url=str(payload.get("search_url", "")),
        hits=[_search_hit_from_payload(_dict(item)) for item in _list(payload.get("hits", []))],
    )


def _search_hit_from_payload(payload: dict[str, Any]) -> SearchHit:
    return SearchHit(
        title=str(payload.get("title", "")),
        url=str(payload.get("url", "")),
        snippet=str(payload.get("snippet", "")),
        content=str(payload.get("content", "")),
    )


def _source_document_from_hit(
    *,
    run_id: str,
    source_result: SourceResult,
    person_query: PersonQuery,
    hit: SearchHit,
    hit_index: int,
    generated_at: str,
) -> SourceDocument:
    seed = "|".join([run_id, source_result.source_id, person_query.full_name, hit.url, hit.title, str(hit_index)])
    suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    title = hit.title or f"{source_result.source_name} hit {hit_index}"
    document_id = "-".join(
        [
            slugify_identifier(source_result.source_id),
            slugify_identifier(person_query.full_name),
            slugify_identifier(title),
            suffix,
        ]
    )
    return SourceDocument(
        document_id=document_id,
        source_id=source_result.source_id,
        title=title,
        url=hit.url,
        access_date=generated_at,
        media_type="text/uri-list",
        local_path="",
        content_hash="",
        raw_text="",
        metadata={
            "access_mode": "reference_only",
            "import_type": "report_hit",
            "person_full_name": person_query.full_name,
            "query": source_result.query,
            "search_url": source_result.search_url,
            "snippet": hit.snippet,
            "content": hit.content,
            "hit_index": str(hit_index),
        },
    )


def _dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _string_list(value: object) -> list[str]:
    return [str(item) for item in _list(value)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa un report JSON nel database SQLite delle evidenze.")
    parser.add_argument("--input-json", required=True, help="File JSON creato da run_caduti_fonti_report.ps1.")
    parser.add_argument("--db", default="data/evidence.sqlite", help="Percorso del database SQLite.")
    parser.add_argument("--run-id", default="", help="Identificativo run opzionale.")
    args = parser.parse_args()

    result = import_report_to_db(
        input_json_path=Path(args.input_json),
        db_path=Path(args.db),
        run_id=args.run_id,
    )
    print(f"Run importato: {result['run_id']}")
    print(f"PersonQuery importate: {result['person_queries']}")
    print(f"SourceResult importati: {result['source_results']}")
    print(f"SourceDocument importati: {result['source_documents']}")
    print(f"Database: {result['db']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
