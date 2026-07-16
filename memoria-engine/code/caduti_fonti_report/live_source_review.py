from __future__ import annotations

import argparse
import json
import time
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .config import load_caduti, load_source_registry
from .connectors.registry import create_source_connector
from .connectors.base import run_source
from .connectors.search_executor import SearchExecutionResult
from .connectors.uniform_source_connector import UniformSourceConnector
from .models import Caduto, PersonQuery, SearchHit, Source, SourceResult, person_query_from_caduto
from .renderers import slugify


LIVE_SOURCE_IDS = {"cwgc", "partigiani_italia", "storia_memoria_bo"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue una review live controllata su fonti selezionate.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml")
    parser.add_argument("--source", action="append", default=[], help="Fonte da eseguire. Ripetibile.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--name", default="")
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output-md", default="risultati/live_source_review.md")
    parser.add_argument("--output-json", default="risultati/live_source_review.json")
    args = parser.parse_args()

    source_ids = args.source or ["cwgc", "storia_memoria_bo"]
    result = run_live_source_review(
        csv_path=Path(args.csv),
        sources_yaml=Path(args.sources_yaml),
        source_ids=source_ids,
        output_md=Path(args.output_md),
        output_json=Path(args.output_json),
        limit=args.limit,
        name_filter=args.name,
        delay=args.delay,
        timeout=args.timeout,
    )
    return int(result["exit_code"])


def run_live_source_review(
    *,
    csv_path: Path,
    sources_yaml: Path,
    source_ids: list[str],
    output_md: Path,
    output_json: Path,
    limit: int = 5,
    name_filter: str = "",
    delay: float = 0.0,
    timeout: int = 30,
) -> dict[str, object]:
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    caduti = _select_caduti(load_caduti(csv_path), limit=limit, name_filter=name_filter)
    registry = load_source_registry(sources_yaml)
    selected_sources = [_resolve_source(registry, source_id) for source_id in source_ids]

    started_at = datetime.now(UTC)
    aggregated: dict[str, list[SourceResult]] = {}
    for caduto in caduti:
        print(f"[live-review] {caduto.intestazione_pdf}", flush=True)
        source_results: list[SourceResult] = []
        for source in selected_sources:
            print(f"[live-review]   fonte {source.source_id}", flush=True)
            source_started = time.perf_counter()
            if source.source_id in {"cwgc", "partigiani_italia", "storia_memoria_bo"}:
                source_results.extend(_run_live_uniform(source=source, caduto=caduto, timeout=timeout))
            else:
                raise ValueError(f"Fonte live non supportata: {source.source_id}")
            elapsed = time.perf_counter() - source_started
            print(f"[live-review]   completata {source.source_id} in {elapsed:.1f}s", flush=True)
            if delay > 0:
                time.sleep(delay)
        aggregated[caduto.intestazione_pdf] = source_results

    output_md.write_text(
        render_live_review_markdown(
            generated_at=started_at,
            caduti=caduti,
            source_ids=[source.source_id for source in selected_sources],
            aggregated=aggregated,
        ),
        encoding="utf-8",
    )
    output_json.write_text(
        json.dumps(
            {
                "generated_at": started_at.isoformat(),
                "source_ids": [source.source_id for source in selected_sources],
                "caduti": [
                    {
                        "caduto": asdict(caduto),
                        "results": [asdict(result) for result in aggregated[caduto.intestazione_pdf]],
                    }
                    for caduto in caduti
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Report markdown scritto in {output_md}")
    print(f"Report json scritto in {output_json}")
    return {"exit_code": 0, "output_md": str(output_md), "output_json": str(output_json)}


def render_live_review_markdown(
    *,
    generated_at: datetime,
    caduti: list[Caduto],
    source_ids: list[str],
    aggregated: dict[str, list[SourceResult]],
) -> str:
    lines = [
        "# Live source review",
        "",
        f"- Generato: {generated_at.isoformat()}",
        f"- Fonti: {', '.join(source_ids)}",
        "",
    ]
    for caduto in caduti:
        lines.extend([f"## {caduto.intestazione_pdf}", "", f"- Nome CSV: {caduto.nome}", ""])
        for result in aggregated.get(caduto.intestazione_pdf, []):
            lines.extend(
                [
                    f"### {result.source_name}",
                    "",
                    f"- Stato: `{result.status}`",
                    f"- Query: `{result.query}`",
                    f"- URL ricerca: {result.search_url}",
                    f"- Nota: {result.note}",
                    "",
                ]
            )
            if result.hits:
                lines.append("Risultati/candidati:")
                lines.append("")
                for index, hit in enumerate(result.hits, start=1):
                    lines.append(f"{index}. [{hit.title}]({hit.url})")
                    if hit.snippet:
                        lines.append(f"   {hit.snippet}")
                lines.append("")
            else:
                lines.append("Nessun candidato riportato.")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _run_live_uniform(*, source: Source, caduto: Caduto, timeout: int) -> list[SourceResult]:
    connector = create_source_connector(
        source,
        run_id=f"live-{source.source_id}-{slugify(caduto.intestazione_pdf)}",
        repo_root=Path.cwd(),
    )
    if not isinstance(connector, UniformSourceConnector):
        raise ValueError(f"Fonte live non uniforme: {source.source_id}")
    connector.html_provider = _live_html_provider(timeout=timeout)
    return connector.search_person(person_query_from_caduto(caduto))


def _live_html_provider(*, timeout: int):
    def provider(execution_result: SearchExecutionResult) -> str:
        request = urllib.request.Request(
            execution_result.url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw_content = response.read()
        return raw_content.decode("utf-8", errors="replace")

    return provider


def _select_caduti(caduti: list[Caduto], *, limit: int, name_filter: str) -> list[Caduto]:
    if name_filter.strip():
        needle = name_filter.strip().casefold()
        caduti = [
            caduto
            for caduto in caduti
            if needle in caduto.nome.casefold() or needle in caduto.intestazione_pdf.casefold()
        ]
    if limit > 0:
        caduti = caduti[:limit]
    return caduti


def _resolve_source(registry: dict[str, Source], source_id: str) -> Source:
    normalized = source_id.strip()
    if normalized not in LIVE_SOURCE_IDS:
        raise ValueError(f"Fonte live non supportata: {normalized}")
    if normalized not in registry:
        raise ValueError(f"Fonte non trovata nel registry: {normalized}")
    return registry[normalized]


if __name__ == "__main__":
    raise SystemExit(main())
