from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .adapters import matches_name_filter, person_queries_from_caduti
from .config import load_caduti
from .models import to_json_safe


def build_person_queries_export(
    *,
    csv_path: Path,
    limit: int = 0,
    name_filter: str = "",
) -> dict[str, object]:
    caduti = load_caduti(csv_path)
    if name_filter.strip():
        requested_name = name_filter.strip()
        caduti = [
            caduto
            for caduto in caduti
            if matches_name_filter(requested_name, caduto.nome, caduto.intestazione_pdf)
        ]
    if limit > 0:
        caduti = caduti[:limit]

    person_queries = person_queries_from_caduti(caduti)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_file": str(csv_path),
        "count": len(person_queries),
        "person_queries": [to_json_safe(person_query) for person_query in person_queries],
    }


def write_person_queries_export(
    *,
    csv_path: Path,
    output_json_path: Path,
    limit: int = 0,
    name_filter: str = "",
) -> dict[str, object]:
    payload = build_person_queries_export(csv_path=csv_path, limit=limit, name_filter=name_filter)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Esporta PersonQuery canoniche dal CSV dei caduti.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output-json", default="risultati/person_queries_purocielo.json")
    parser.add_argument("--limit", type=int, default=0, help="Numero massimo di caduti da esportare; 0 = tutti.")
    parser.add_argument(
        "--name",
        default="",
        help="Filtra un caduto per nome/intestazione PDF, con confronto case-insensitive.",
    )
    args = parser.parse_args()

    payload = write_person_queries_export(
        csv_path=Path(args.csv),
        output_json_path=Path(args.output_json),
        limit=args.limit,
        name_filter=args.name,
    )
    print(f"PersonQuery esportate: {payload['count']}")
    print(f"File CSV usato: {payload['input_file']}")
    print(f"Output JSON scritto in {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
