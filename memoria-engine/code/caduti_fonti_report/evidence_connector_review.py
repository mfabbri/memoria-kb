from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .config import load_caduti, load_source_registry, load_sources_from_yaml
from .connectors.registry import create_source_connector, describe_source_connector
from .models import Caduto, Source, person_query_from_caduto, to_json_safe


def run_evidence_connector_review(
    *,
    csv_path: Path,
    sources_yaml: Path,
    output_md: Path,
    output_json: Path,
    source_ids: list[str] | None = None,
    limit: int = 0,
    name_filter: str = "",
    run_id: str = "",
    refresh_authenticated_cache: bool = False,
    repo_root: Path | None = None,
) -> dict[str, object]:
    csv_path = Path(csv_path)
    sources_yaml = Path(sources_yaml)
    output_md = Path(output_md)
    output_json = Path(output_json)
    repo_root = repo_root or Path.cwd()
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    caduti = _select_caduti(load_caduti(csv_path), limit=limit, name_filter=name_filter)
    source_registry = load_source_registry(sources_yaml)
    sources = _select_sources(sources_yaml=sources_yaml, source_registry=source_registry, source_ids=source_ids or [])
    effective_run_id = run_id or f"evidence-connectors:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"

    source_entries = []
    for source in sources:
        if refresh_authenticated_cache:
            source.auth["force_refresh_authenticated_cache"] = "true"
        registration = describe_source_connector(source)
        connector = create_source_connector(
            source,
            run_id=effective_run_id,
            repo_root=repo_root,
        )
        try:
            caduto_entries = []
            for caduto in caduti:
                query = person_query_from_caduto(caduto)
                results = connector.search_person(query)
                result_entries = []
                for result in results:
                    documents = connector.fetch_detail(result)
                    claims = []
                    for document in documents:
                        claims.extend(connector.extract_evidence(document))
                    result_entries.append(
                        {
                            "result": result,
                            "documents": documents,
                            "claims": claims,
                        }
                    )
                caduto_entries.append(
                    {
                        "caduto": caduto,
                        "query": query,
                        "results": result_entries,
                    }
                )
            source_entries.append(
                {
                    "source": _source_summary(source),
                    "registration": registration,
                    "caduti": caduto_entries,
                }
            )
        finally:
            close_connector = getattr(connector, "close", None)
            if callable(close_connector):
                close_connector()

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": effective_run_id,
        "source_file": str(sources_yaml),
        "csv": str(csv_path),
        "sources": source_entries,
    }
    output_json.write_text(json.dumps(to_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(_render_markdown(payload), encoding="utf-8")
    return {
        "exit_code": 0,
        "run_id": effective_run_id,
        "output_md": str(output_md),
        "output_json": str(output_json),
        "sources_count": len(sources),
        "caduti_count": len(caduti),
    }


def _select_caduti(caduti: list[Caduto], *, limit: int, name_filter: str) -> list[Caduto]:
    if name_filter.strip():
        wanted = name_filter.casefold().split()
        caduti = [
            caduto
            for caduto in caduti
            if all(token in f"{caduto.nome} {caduto.intestazione_pdf}".casefold().split() for token in wanted)
        ]
    if limit > 0:
        return caduti[:limit]
    return caduti


def _select_sources(
    *,
    sources_yaml: Path,
    source_registry: dict[str, Source],
    source_ids: list[str],
) -> list[Source]:
    if source_ids:
        return [source_registry[source_id] for source_id in source_ids if source_id in source_registry]
    return load_sources_from_yaml(sources_yaml, source_registry).selected_sources


def _source_summary(source: Source) -> dict[str, str]:
    return {
        "source_id": source.source_id,
        "source_name": source.source_name,
        "kind": source.kind,
        "note": source.note,
    }


def _render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Evidence-aware connector review",
        "",
        f"Run: `{payload['run_id']}`",
        f"Generato il: `{payload['generated_at']}`",
        f"Fonti YAML: `{payload['source_file']}`",
        "",
    ]

    for source_entry in payload["sources"]:
        source = source_entry["source"]
        registration = source_entry["registration"]
        lines.extend(
            [
                f"## {source['source_name']}",
                "",
                f"- Source ID: `{source['source_id']}`",
                f"- Connector: `{registration.connector_type}`",
                f"- Evidence-aware: `{str(registration.evidence_aware).lower()}`",
                f"- Detail fetch: `{registration.detail_fetch}`",
                f"- Claim extraction: `{registration.claim_extraction}`",
                "",
            ]
        )
        for caduto_entry in source_entry["caduti"]:
            caduto = caduto_entry["caduto"]
            result_entries = caduto_entry["results"]
            lines.append(f"### {caduto.intestazione_pdf}")
            if not result_entries:
                lines.append("- Nessun risultato prodotto dal connettore.")
                lines.append("")
                continue
            for result_entry in result_entries:
                result = result_entry["result"]
                documents = result_entry["documents"]
                claims = result_entry["claims"]
                lines.extend(
                    [
                        f"- Stato: `{result.status}`",
                        f"- Query: `{result.query}`",
                        f"- Hit: `{len(result.hits)}`",
                        f"- Documenti: `{len(documents)}`",
                        f"- Claim: `{len(claims)}`",
                    ]
                )
                if result.search_url:
                    lines.append(f"- Ricerca: {result.search_url}")
                for hit in result.hits[:10]:
                    lines.append(f"  - [{hit.title}]({hit.url})")
                lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prova i connettori evidence-aware o legacy-adapted.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml")
    parser.add_argument("--output-md", default="risultati/evidence_connector_review.md")
    parser.add_argument("--output-json", default="risultati/evidence_connector_review.json")
    parser.add_argument("--source", action="append", default=[], help="ID fonte da provare; ripetibile.")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--name", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--refresh-authenticated-cache", action="store_true")
    args = parser.parse_args()

    result = run_evidence_connector_review(
        csv_path=Path(args.csv),
        sources_yaml=Path(args.sources_yaml),
        output_md=Path(args.output_md),
        output_json=Path(args.output_json),
        source_ids=list(args.source),
        limit=args.limit,
        name_filter=args.name,
        run_id=args.run_id,
        refresh_authenticated_cache=args.refresh_authenticated_cache,
    )
    print(f"Run: {result['run_id']}")
    print(f"Report markdown scritto in {result['output_md']}")
    print(f"Report json scritto in {result['output_json']}")
    print(f"Fonti: {result['sources_count']}")
    print(f"Caduti: {result['caduti_count']}")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
