from __future__ import annotations

import argparse
from pathlib import Path

from .import_report_to_db import import_report_to_db
from .runner import run_report


def run_meta_search(
    *,
    csv_path: Path,
    sources_yaml: Path,
    output_md: Path,
    output_json: Path,
    output_dir: Path,
    db_path: Path,
    delay: float = 0.0,
    limit: int = 0,
    source_id: str = "",
    name_filter: str = "",
    run_id: str = "",
) -> dict[str, object]:
    report_result = run_report(
        csv_path=csv_path,
        sources_yaml=sources_yaml,
        output_md=output_md,
        output_json=output_json,
        output_dir=output_dir,
        delay=delay,
        limit=limit,
        source_id=source_id,
        name_filter=name_filter,
    )
    if report_result["exit_code"] != 0:
        return {
            "exit_code": report_result["exit_code"],
            "report": report_result,
            "db_import": None,
        }

    import_result = import_report_to_db(
        input_json_path=Path(report_result["output_json"]),
        db_path=db_path,
        run_id=run_id,
    )
    print("Import database completato")
    print(f"Run DB: {import_result['run_id']}")
    print(f"PersonQuery importate: {import_result['person_queries']}")
    print(f"SourceResult importati: {import_result['source_results']}")
    print(f"SourceDocument importati: {import_result['source_documents']}")
    print(f"Database: {import_result['db']}")

    return {
        "exit_code": 0,
        "report": report_result,
        "db_import": import_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue ricerca, report e import nel database SQLite.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml")
    parser.add_argument("--output-md", default="risultati/caduti_purocielo_fonti_report.md")
    parser.add_argument("--output-json", default="risultati/caduti_purocielo_fonti_report.json")
    parser.add_argument("--output-dir", default="risultati/caduti_purocielo_schede")
    parser.add_argument("--delay", type=float, default=0.0, help="Pausa tra le richieste HTTP.")
    parser.add_argument("--limit", type=int, default=0, help="Numero massimo di caduti da processare; 0 = tutti.")
    parser.add_argument("--source", default="", help="ID di una singola fonte da provare.")
    parser.add_argument("--name", default="", help="Filtra un caduto per nome/intestazione PDF.")
    parser.add_argument("--db", default="data/evidence.sqlite", help="Percorso del database SQLite.")
    parser.add_argument("--run-id", default="", help="Identificativo run opzionale per il DB.")
    args = parser.parse_args()

    result = run_meta_search(
        csv_path=Path(args.csv),
        sources_yaml=Path(args.sources_yaml),
        output_md=Path(args.output_md),
        output_json=Path(args.output_json),
        output_dir=Path(args.output_dir),
        db_path=Path(args.db),
        delay=args.delay,
        limit=args.limit,
        source_id=args.source,
        name_filter=args.name,
        run_id=args.run_id,
    )
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
