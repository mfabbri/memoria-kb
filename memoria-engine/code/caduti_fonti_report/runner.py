from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .authenticated_session import source_uses_manual_authenticated_session
from .config import load_caduti, load_source_registry, load_sources_from_yaml
from .connectors.registry import create_source_connector
from .models import person_query_from_caduto
from .renderers import render_markdown, render_single_caduto_markdown, slugify
from .validate_sources_registry import validate_sources_registry_file


REPORT_SOURCE_KINDS_WITH_DELAY = {
    "search_page",
    "wp_json",
    "search_form_post",
    "search_form_aspnet",
    "search_form_get_name",
    "storia_memoria_bo",
    "obd_memorial",
    "pamyat_naroda",
    "cwgc",
}


def log_progress(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def _warn_manual_authenticated_sources(sources) -> None:
    authenticated_source_ids = [
        source.source_id for source in sources if source_uses_manual_authenticated_session(source)
    ]
    if not authenticated_source_ids:
        return

    joined_ids = ", ".join(authenticated_source_ids)
    print(
        "Avviso: la run include fonti con sessione autenticata manuale "
        f"({joined_ids}). Se la cache locale non basta, il fetch di dettaglio puo' aprire SPID/CIE."
    )


def _repo_root_from_sources_yaml(sources_yaml: Path) -> Path:
    resolved = sources_yaml.resolve()
    if resolved.parent.name == "ricerche":
        return resolved.parent.parent
    return resolved.parent


def _matches_name_filter(filter_text: str, *candidate_values: str) -> bool:
    filter_tokens = [token for token in filter_text.casefold().split() if token]
    if not filter_tokens:
        return True

    for candidate in candidate_values:
        candidate_tokens = candidate.casefold().split()
        if all(token in candidate_tokens for token in filter_tokens):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Interroga fonti sui caduti di Purocielo e genera un report markdown.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml")
    parser.add_argument("--output-md", default="risultati/caduti_purocielo_fonti_report.md")
    parser.add_argument("--output-json", default="risultati/caduti_purocielo_fonti_report.json")
    parser.add_argument("--output-dir", default="risultati/caduti_purocielo_schede")
    parser.add_argument("--delay", type=float, default=0.0, help="Pausa tra le richieste HTTP.")
    parser.add_argument("--limit", type=int, default=0, help="Numero massimo di caduti da processare; 0 = tutti.")
    parser.add_argument(
        "--source",
        default="",
        help="ID di una singola fonte da provare, letta dal file YAML delle fonti.",
    )
    parser.add_argument(
        "--name",
        default="",
        help="Filtra un solo caduto per nome/intestazione PDF, con confronto case-insensitive.",
    )
    args = parser.parse_args()

    result = run_report(
        csv_path=Path(args.csv),
        sources_yaml=Path(args.sources_yaml),
        output_md=Path(args.output_md),
        output_json=Path(args.output_json),
        output_dir=Path(args.output_dir),
        delay=args.delay,
        limit=args.limit,
        source_id=args.source,
        name_filter=args.name,
    )
    return result["exit_code"]


def run_report(
    *,
    csv_path: Path,
    sources_yaml: Path,
    output_md: Path,
    output_json: Path,
    output_dir: Path,
    delay: float = 0.0,
    limit: int = 0,
    source_id: str = "",
    name_filter: str = "",
) -> dict[str, object]:
    csv_path = Path(csv_path)
    sources_yaml = Path(sources_yaml)
    output_md = Path(output_md)
    output_json = Path(output_json)
    output_dir = Path(output_dir)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    caduti = load_caduti(csv_path)
    if name_filter.strip():
        requested_name = name_filter.strip()
        caduti = [
            caduto
            for caduto in caduti
            if _matches_name_filter(requested_name, caduto.nome, caduto.intestazione_pdf)
        ]
        if not caduti:
            print(f"Nessun caduto trovato per il filtro nome: {name_filter.strip()}")
            return {
                "exit_code": 2,
                "output_json": str(output_json),
                "output_md": str(output_md),
                "output_dir": str(output_dir),
                "caduti_count": 0,
                "sources_count": 0,
                "error": "name_not_found",
            }
    if limit > 0:
        caduti = caduti[:limit]

    source_registry = load_source_registry(sources_yaml)
    source_selection = load_sources_from_yaml(sources_yaml, source_registry, only_source_id=source_id.strip())
    if not source_selection.selected_sources:
        available_source_ids = ", ".join(source_registry.keys())
        requested_source = source_id.strip() or "(vuoto)"
        print(f"Fonte richiesta non trovata nel file YAML: {requested_source}")
        print(f"Fonti disponibili: {available_source_ids}")
        return {
            "exit_code": 2,
            "output_json": str(output_json),
            "output_md": str(output_md),
            "output_dir": str(output_dir),
            "caduti_count": len(caduti),
            "sources_count": 0,
            "error": "source_not_found",
        }
    sources = source_selection.selected_sources
    selected_source_ids = {source.source_id for source in sources}
    validation = validate_sources_registry_file(
        sources_yaml,
        only_source_ids=selected_source_ids,
    )
    if not validation.valid:
        print("Registry fonti non valido; esecuzione interrotta.")
        for error in validation.errors:
            print(f"- {error}")
        return {
            "exit_code": 2,
            "output_json": str(output_json),
            "output_md": str(output_md),
            "output_dir": str(output_dir),
            "caduti_count": len(caduti),
            "sources_count": len(sources),
            "error": "invalid_sources_registry",
        }

    repo_root = _repo_root_from_sources_yaml(sources_yaml)
    connectors = {
        source.source_id: create_source_connector(
            source,
            run_id=f"caduti-fonti-report:{source.source_id}",
            repo_root=repo_root,
        )
        for source in sources
    }
    aggregated: dict[str, list] = {}
    aggregated_details: dict[str, list[dict[str, object]]] = {}

    log_progress(
        f"Avvio report: {len(caduti)} caduti, {len(sources)} fonti, CSV={csv_path}, YAML={sources_yaml}"
    )
    _warn_manual_authenticated_sources(sources)

    try:
        for caduto_index, caduto in enumerate(caduti, start=1):
            log_progress(f"[{caduto_index}/{len(caduti)}] Caduto: {caduto.intestazione_pdf}")
            source_results = []
            source_result_entries: list[dict[str, object]] = []
            query = person_query_from_caduto(caduto)
            for source_index, source in enumerate(sources, start=1):
                log_progress(f"  [{source_index}/{len(sources)}] Fonte: {source.source_name}")
                source_started_at = time.perf_counter()
                connector = connectors[source.source_id]
                results = connector.search_person(query)
                elapsed = time.perf_counter() - source_started_at
                for result in results:
                    documents = connector.fetch_detail(result)
                    claims = []
                    for document in documents:
                        claims.extend(connector.extract_evidence(document))
                    source_results.append(result)
                    source_result_entries.append(
                        {
                            "result": asdict(result),
                            "documents": [asdict(document) for document in documents],
                            "claims": [asdict(claim) for claim in claims],
                        }
                    )
                    log_progress(
                        f"  [{source_index}/{len(sources)}] Esito {source.source_id}: "
                        f"{result.status} in {elapsed:.1f}s"
                    )
                if not results:
                    log_progress(
                        f"  [{source_index}/{len(sources)}] Esito {source.source_id}: "
                        "nessun risultato prodotto dal connettore"
                    )
                if source.kind in REPORT_SOURCE_KINDS_WITH_DELAY and delay > 0:
                    time.sleep(delay)
            aggregated[caduto.intestazione_pdf] = source_results
            aggregated_details[caduto.intestazione_pdf] = source_result_entries
            log_progress(f"[{caduto_index}/{len(caduti)}] Completato: {caduto.intestazione_pdf}")
    finally:
        for connector in connectors.values():
            close_connector = getattr(connector, "close", None)
            if callable(close_connector):
                close_connector()

    markdown = render_markdown(caduti, aggregated, source_selection, aggregated_details)
    output_md.write_text(markdown, encoding="utf-8")

    for caduto in caduti:
        filename = f"{slugify(caduto.intestazione_pdf)}.md"
        single_markdown = render_single_caduto_markdown(
            caduto,
            aggregated[caduto.intestazione_pdf],
            aggregated_details[caduto.intestazione_pdf],
        )
        (output_dir / filename).write_text(single_markdown, encoding="utf-8")

    serializable = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_selection": {
            "source_file": source_selection.source_file,
            "selected_source_ids": source_selection.selected_source_ids,
            "unresolved_source_ids": source_selection.unresolved_source_ids,
            "used_fallback": source_selection.used_fallback,
        },
        "caduti": [
            {
                "caduto": asdict(caduto),
                "results": aggregated_details[caduto.intestazione_pdf],
            }
            for caduto in caduti
        ],
    }
    output_json.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")

    log_progress("Scrittura output completata")
    print(f"Report markdown scritto in {output_md}")
    print(f"Report json scritto in {output_json}")
    print(f"Schede singole scritte in {output_dir}")
    print(f"File fonti usato: {sources_yaml}")
    print(f"Fonti selezionate: {len(sources)}")
    if source_selection.unresolved_source_ids:
        print(f"ID fonti non risolti: {len(source_selection.unresolved_source_ids)}")
    print(f"Caduti processati: {len(caduti)}")
    return {
        "exit_code": 0,
        "output_json": str(output_json),
        "output_md": str(output_md),
        "output_dir": str(output_dir),
        "caduti_count": len(caduti),
        "sources_count": len(sources),
        "error": "",
    }
