from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .sqlite_store import SQLiteEvidenceStore


MANUAL_REVIEW_STATUSES = {"search_url_ready", "manual_request", "needs_credentials"}


def build_audit_report(*, db_path: Path, run_id: str) -> str:
    store = SQLiteEvidenceStore(db_path)
    run = _fetch_one(
        store,
        """
        SELECT run_id, timestamp, input_file, source_ids_json
        FROM search_runs
        WHERE run_id = ?
        """,
        (run_id,),
    )
    if run is None:
        raise ValueError(f"Run non trovata: {run_id}")

    people = _fetch_all(
        store,
        """
        SELECT full_name, given_name, family_name
        FROM person_queries
        WHERE run_id = ?
        ORDER BY full_name ASC
        """,
        (run_id,),
    )
    results = _fetch_all(
        store,
        """
        SELECT id, source_id, source_name, status, query, search_url
        FROM source_results
        WHERE run_id = ?
        ORDER BY source_id ASC, id ASC
        """,
        (run_id,),
    )
    documents = _fetch_all(
        store,
        """
        SELECT document_id, source_id, title, url, local_path, content_hash, payload_json
        FROM source_documents
        WHERE run_id = ?
        ORDER BY source_id ASC, title ASC, document_id ASC
        """,
        (run_id,),
    )
    claims = _fetch_all(
        store,
        """
        SELECT claim_id, subject_id, field, value, source_document_id, review_status
        FROM evidence_claims
        WHERE run_id = ?
        ORDER BY subject_id ASC, field ASC, claim_id ASC
        """,
        (run_id,),
    )

    lines = [
        f"# Audit run {run['run_id']}",
        "",
        "## Riepilogo",
        "",
        f"- Timestamp: {run['timestamp']}",
        f"- Input file: {run['input_file']}",
        f"- Fonti selezionate: {', '.join(_json_list(run['source_ids_json']))}",
        f"- Persone cercate: {len(people)}",
        f"- Fonti interrogate: {len(results)}",
        f"- Documenti registrati: {len(documents)}",
        f"- Evidenze estratte: {len(claims)}",
        "",
        "## Persone cercate",
        "",
    ]
    if people:
        for person in people:
            lines.append(f"- {person['full_name']}")
    else:
        lines.append("- Nessuna persona registrata.")

    lines.extend(["", "## Risultati per fonte", ""])
    if results:
        for result in results:
            lines.extend(
                [
                    f"### {result['source_id']}",
                    "",
                    f"- Nome fonte: {result['source_name']}",
                    f"- Stato: `{result['status']}`",
                    f"- Query: `{result['query']}`",
                    f"- URL ricerca: {result['search_url']}",
                    "",
                ]
            )
    else:
        lines.append("Nessun risultato fonte registrato.")

    lines.extend(["", "## Documenti registrati", ""])
    if documents:
        for document in documents:
            access_mode = _document_access_mode(document["payload_json"])
            lines.extend(
                [
                    f"### {document['document_id']}",
                    "",
                    f"- Fonte: {document['source_id']}",
                    f"- Titolo: {document['title']}",
                    f"- URL: {document['url']}",
                    f"- Access mode: {access_mode}",
                    f"- Path locale: {document['local_path'] or '(nessun file locale)'}",
                    f"- Hash contenuto: {document['content_hash'] or '(non disponibile)'}",
                    "",
                ]
            )
    else:
        lines.append("Nessun documento registrato.")

    lines.extend(["", "## Evidenze", ""])
    if claims:
        for claim in claims:
            lines.append(
                "- "
                f"{claim['subject_id']} | {claim['field']} = {claim['value']} | "
                f"documento={claim['source_document_id']} | stato={claim['review_status']}"
            )
    else:
        lines.append("Nessuna EvidenceClaim estratta per questa run.")

    lines.extend(["", "## Verifiche manuali", ""])
    manual_items = _manual_review_items(results=results, documents=documents)
    if manual_items:
        lines.extend(manual_items)
    else:
        lines.append("Nessuna verifica manuale evidenziata dal report audit.")

    return "\n".join(lines).rstrip() + "\n"


def write_audit_report(*, db_path: Path, run_id: str, output_md_path: Path) -> str:
    markdown = build_audit_report(db_path=db_path, run_id=run_id)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text(markdown, encoding="utf-8")
    return markdown


def _manual_review_items(*, results: list[sqlite3.Row], documents: list[sqlite3.Row]) -> list[str]:
    document_counts_by_source: dict[str, int] = {}
    for document in documents:
        source_id = str(document["source_id"])
        document_counts_by_source[source_id] = document_counts_by_source.get(source_id, 0) + 1

    lines: list[str] = []
    for result in results:
        source_id = str(result["source_id"])
        status = str(result["status"])
        document_count = document_counts_by_source.get(source_id, 0)
        if status in MANUAL_REVIEW_STATUSES:
            lines.append(
                f"- `{source_id}` ha stato `{status}`: verificare manualmente gli URL o le credenziali della fonte."
            )
        elif document_count == 0:
            lines.append(f"- `{source_id}` non ha documenti registrati: verificare se il risultato richiede follow-up.")
    return lines


def _document_access_mode(payload_json: str) -> str:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return ""
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("access_mode", ""))


def _fetch_one(store: SQLiteEvidenceStore, sql: str, parameters: tuple[object, ...]) -> sqlite3.Row | None:
    with closing(store.connect()) as connection:
        return connection.execute(sql, parameters).fetchone()


def _fetch_all(store: SQLiteEvidenceStore, sql: str, parameters: tuple[object, ...]) -> list[sqlite3.Row]:
    with closing(store.connect()) as connection:
        return list(connection.execute(sql, parameters))


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def main() -> int:
    parser = argparse.ArgumentParser(description="Esporta un report audit Markdown da una run nel database SQLite.")
    parser.add_argument("--db", default="data/evidence.sqlite", help="Percorso del database SQLite.")
    parser.add_argument("--run-id", required=True, help="Identificativo della run da esportare.")
    parser.add_argument("--output-md", required=True, help="File Markdown di output.")
    args = parser.parse_args()

    try:
        write_audit_report(
            db_path=Path(args.db),
            run_id=args.run_id,
            output_md_path=Path(args.output_md),
        )
    except ValueError as error:
        print(str(error))
        return 2

    print(f"Report audit scritto in {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
