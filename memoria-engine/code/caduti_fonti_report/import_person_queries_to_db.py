from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import PersonQuery, SearchRun
from .sqlite_store import SQLiteEvidenceStore


def import_person_queries_export(
    *,
    input_json_path: Path,
    db_path: Path,
    run_id: str = "",
) -> dict[str, object]:
    payload = json.loads(input_json_path.read_text(encoding="utf-8"))
    generated_at = str(payload.get("generated_at") or datetime.now(UTC).isoformat())
    effective_run_id = run_id or f"person_queries:{input_json_path.stem}:{generated_at}"
    person_queries = [_person_query_from_payload(item) for item in payload.get("person_queries", [])]

    run = SearchRun(
        run_id=effective_run_id,
        timestamp=generated_at,
        input_file=str(payload.get("input_file", "")),
        source_ids=[],
        parameters={"import_file": str(input_json_path)},
        metadata={"import_type": "person_queries_export"},
    )

    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    store.delete_run(effective_run_id)
    store.insert_search_run(run)
    for person_query in person_queries:
        store.insert_person_query(effective_run_id, person_query)

    return {
        "run_id": effective_run_id,
        "person_queries": len(person_queries),
        "db": str(db_path),
    }


def _person_query_from_payload(payload: dict[str, Any]) -> PersonQuery:
    return PersonQuery(
        full_name=str(payload.get("full_name", "")),
        given_name=str(payload.get("given_name", "")),
        family_name=str(payload.get("family_name", "")),
        aliases=_string_list(payload.get("aliases", [])),
        birth_date=str(payload.get("birth_date", "")),
        birth_place=str(payload.get("birth_place", "")),
        death_date=str(payload.get("death_date", "")),
        death_place=str(payload.get("death_place", "")),
        formation=str(payload.get("formation", "")),
        event_hint=str(payload.get("event_hint", "")),
        place_hint=str(payload.get("place_hint", "")),
        source_hints=_string_dict(payload.get("source_hints", {})),
        metadata=_string_dict(payload.get("metadata", {})),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa un export PersonQuery nel database SQLite.")
    parser.add_argument("--input-json", required=True, help="File JSON creato da export_person_queries.ps1.")
    parser.add_argument("--db", default="data/evidence.sqlite", help="Percorso del database SQLite.")
    parser.add_argument("--run-id", default="", help="Identificativo run opzionale.")
    args = parser.parse_args()

    result = import_person_queries_export(
        input_json_path=Path(args.input_json),
        db_path=Path(args.db),
        run_id=args.run_id,
    )
    print(f"Run importato: {result['run_id']}")
    print(f"PersonQuery importate: {result['person_queries']}")
    print(f"Database: {result['db']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
