from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .export_audit_report import MANUAL_REVIEW_STATUSES
from .export_obsidian_vault_markdown import (
    _mvp_curatorial_brief_markdown,
    _mvp_dashboard_markdown,
    _mvp_document_markdown,
    _mvp_evidence_markdown,
    _mvp_person_markdown,
    _mvp_publication_candidate_markdown,
)
from .profile_repository import ProfileRepository
from .raw_store import slugify_identifier
from .sqlite_store import SQLiteEvidenceStore


AUTO_BEGIN = "<!-- BEGIN AUTO-GENERATED -->"
AUTO_END = "<!-- END AUTO-GENERATED -->"
EDITORIAL_BEGIN = "<!-- BEGIN EDITORIAL NOTES -->"
EDITORIAL_END = "<!-- END EDITORIAL NOTES -->"


def export_obsidian_vault(*, db_path: Path, run_id: str, output_dir: Path) -> dict[str, object]:
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
        SELECT source_id, source_name, status, query, search_url
        FROM source_results
        WHERE run_id = ?
        ORDER BY source_id ASC, id ASC
        """,
        (run_id,),
    )
    documents = _fetch_all(
        store,
        """
        SELECT document_id, source_id, title, url, access_date, local_path, content_hash, payload_json
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
    events = store.fetch_events()
    places = store.fetch_places()

    people_dir = output_dir / "01_Persone"
    documents_dir = output_dir / "02_Documenti"
    events_dir = output_dir / "03_Eventi"
    places_dir = output_dir / "04_Luoghi"
    evidence_dir = output_dir / "07_Evidenze"
    logs_dir = output_dir / "09_Log_ricerca"
    for directory in [people_dir, documents_dir, events_dir, places_dir, evidence_dir, logs_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    document_links = [_obsidian_link("02_Documenti", document["document_id"]) for document in documents]

    for person in people:
        person_path = people_dir / f"{slugify_identifier(person['full_name'])}.md"
        markdown = _person_markdown(person=person, run=run, results=results, document_links=document_links)
        _write_preserving_editorial(person_path, markdown)
        written.append(str(person_path))

    for document in documents:
        document_path = documents_dir / f"{slugify_identifier(document['document_id'])}.md"
        markdown = _document_markdown(document=document, run=run)
        _write_preserving_editorial(document_path, markdown)
        written.append(str(document_path))

    documents_by_id = {str(document["document_id"]): document for document in documents}
    claims_by_id = {str(claim["claim_id"]): claim for claim in claims}
    for event in events:
        event_path = events_dir / f"{slugify_identifier(event['event_id'])}.md"
        markdown = _event_markdown(
            event=event,
            run=run,
            documents_by_id=documents_by_id,
            claims_by_id=claims_by_id,
        )
        _write_preserving_editorial(event_path, markdown)
        written.append(str(event_path))

    for place in places:
        place_path = places_dir / f"{slugify_identifier(place['place_id'])}.md"
        markdown = _place_markdown(
            place=place,
            run=run,
            documents_by_id=documents_by_id,
            claims_by_id=claims_by_id,
        )
        _write_preserving_editorial(place_path, markdown)
        written.append(str(place_path))

    evidence_path = evidence_dir / "README.md"
    _write_preserving_editorial(evidence_path, _evidence_markdown(run=run, claims=claims))
    written.append(str(evidence_path))

    log_path = logs_dir / f"{slugify_identifier(run_id)}.md"
    _write_preserving_editorial(
        log_path,
        _log_markdown(run=run, people=people, results=results, documents=documents, claims=claims),
    )
    written.append(str(log_path))

    return {
        "run_id": run_id,
        "output_dir": str(output_dir),
        "files": written,
    }


def export_profile_obsidian_vault(
    *,
    profiles_index: Path,
    output_dir: Path,
    profile_id: str = "",
    limit: int = 0,
) -> dict[str, object]:
    repository = ProfileRepository(profiles_index)
    entries = repository.list_entries()
    if profile_id.strip():
        profiles = repository.load_profiles(profile_id=profile_id)
    else:
        profiles = repository.load_profiles(limit=limit)
    if limit > 0 and profile_id.strip():
        profiles = profiles[:limit]

    people_dir = output_dir / "01_Persone"
    people_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for profile in profiles:
        source_file = Path(str(profile.metadata.get("profile_source_file", "")))
        payload = _json_object(source_file.read_text(encoding="utf-8")) if source_file.exists() else {}
        person_path = people_dir / f"{slugify_identifier(profile.identity.canonical_name or profile.profile_id)}.md"
        markdown = _profile_person_markdown(profile_payload=payload, profiles_index=profiles_index)
        _write_preserving_editorial(person_path, markdown)
        written.append(str(person_path))

    return {
        "profiles_index": str(profiles_index),
        "profiles_available": len(entries),
        "profiles_exported": len(profiles),
        "output_dir": str(output_dir),
        "files": written,
    }


def export_mvp_pilot_obsidian_vault(
    *,
    summary_json: Path,
    output_dir: Path,
    limit: int = 10,
    review_queue_md: Path | None = None,
    review_decisions_summary: Path | None = None,
) -> dict[str, object]:
    payload = _json_object(summary_json.read_text(encoding="utf-8"))
    review_decisions_payload = _load_optional_json_object(review_decisions_summary)
    review_session = _dict_object(review_decisions_payload.get("review_session"))
    review_profiles = _review_session_profiles_by_id(review_session)
    profiles = _select_mvp_profiles(payload=payload, limit=limit)
    links = _json_object_list(payload.get("candidate_document_person_links"))
    claims = _json_object_list(payload.get("candidate_evidence_claims"))
    signal_groups = _json_object_list(payload.get("reviewable_document_signals"))
    documents = _json_object_list(payload.get("documents"))
    readiness = _mvp_profile_readiness(
        payload=payload,
        profiles=profiles,
        links=links,
        claims=claims,
        signal_groups=signal_groups,
        documents=documents,
    )

    people_dir = output_dir / "01_Persone"
    documents_dir = output_dir / "02_Documenti"
    evidence_dir = output_dir / "07_Evidenze"
    output_report_dir = output_dir / "10_Output"
    publication_candidates_dir = output_dir / "40_Publication_Candidates"
    for directory in [people_dir, documents_dir, evidence_dir, output_report_dir, publication_candidates_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    publication_candidates: list[dict[str, object]] = []
    for profile in profiles:
        profile_id = str(profile.get("profile_id", ""))
        name = str(profile.get("canonical_name") or profile_id)
        profile_payload = _load_mvp_profile_payload(profile)
        profile_links = [link for link in links if _profile_id_from_item(link) == profile_id]
        profile_claims = [claim for claim in claims if _profile_id_from_item(claim) == profile_id]
        profile_signals = _mvp_signals_for_profile(signal_groups, profile_id)
        profile_readiness = readiness.get(profile_id, {})
        profile_review_session = review_profiles.get(profile_id, {})
        person_path = people_dir / f"{slugify_identifier(name or profile_id)}.md"
        person_markdown = _mvp_person_markdown(
            profile=profile,
            profile_payload=profile_payload,
            payload=payload,
            links=profile_links,
            claims=profile_claims,
            signals=profile_signals,
            readiness=profile_readiness,
            review_session=profile_review_session,
        )
        _write_preserving_editorial(person_path, person_markdown)
        written.append(str(person_path))
        candidate_status = _mvp_publication_candidate_status(
            readiness=profile_readiness,
            review_session=profile_review_session,
        )
        candidate_path = publication_candidates_dir / f"{slugify_identifier(name or profile_id)}.md"
        _write_preserving_editorial(
            candidate_path,
            _mvp_publication_candidate_markdown(
                profile=profile,
                profile_payload=profile_payload,
                links=profile_links,
                claims=profile_claims,
                signals=profile_signals,
                readiness=profile_readiness,
                review_session=profile_review_session,
                candidate_status=candidate_status,
            ),
        )
        written.append(str(candidate_path))
        publication_candidates.append(
            {
                "profile_id": profile_id,
                "canonical_name": name,
                "candidate_status": candidate_status,
                "path": str(candidate_path),
            }
        )

    for document in _documents_for_profiles(documents=documents, links=links, claims=claims, signal_groups=signal_groups, profiles=profiles):
        document_id = str(document.get("source_document_id", ""))
        if not document_id:
            continue
        document_path = documents_dir / f"{slugify_identifier(document_id)}.md"
        _write_preserving_editorial(document_path, _mvp_document_markdown(document=document, payload=payload))
        written.append(str(document_path))

    evidence_path = evidence_dir / "README.md"
    _write_preserving_editorial(evidence_path, _mvp_evidence_markdown(payload=payload, claims=claims, profiles=profiles))
    written.append(str(evidence_path))

    dashboard_path = output_report_dir / "MVP_Pilot_Review.md"
    _write_preserving_editorial(
        dashboard_path,
        _mvp_dashboard_markdown(
            payload=payload,
            profiles=profiles,
            readiness=readiness,
            review_queue_md=review_queue_md,
            review_decisions_summary=review_decisions_summary,
            review_session=review_session,
            publication_candidates=publication_candidates,
        ),
    )
    written.append(str(dashboard_path))

    curatorial_brief_path = output_report_dir / "mvp_curatorial_brief.md"
    _write_preserving_editorial(
        curatorial_brief_path,
        _mvp_curatorial_brief_markdown(
            payload=payload,
            profiles=profiles,
            readiness=readiness,
            review_session=review_session,
            publication_candidates=publication_candidates,
        ),
    )
    written.append(str(curatorial_brief_path))

    return {
        "summary_json": str(summary_json),
        "output_dir": str(output_dir),
        "profiles_exported": len(profiles),
        "files": written,
    }


def _person_markdown(*, person: sqlite3.Row, run: sqlite3.Row, results: list[sqlite3.Row], document_links: list[str]) -> str:
    lines = [
        "---",
        "type: person",
        f"name: {_yaml_value(person['full_name'])}",
        f"run_id: {_yaml_value(run['run_id'])}",
        "---",
        "",
        f"# {person['full_name']}",
        "",
        AUTO_BEGIN,
        "",
        "## Identita",
        "",
        f"- Nome completo: {person['full_name']}",
        f"- Nome: {person['given_name']}",
        f"- Cognome: {person['family_name']}",
        "",
        "## Run di ricerca",
        "",
        f"- Run: {_obsidian_link('09_Log_ricerca', run['run_id'])}",
        f"- Timestamp: {run['timestamp']}",
        "",
        "## Fonti interrogate",
        "",
    ]
    if results:
        for result in results:
            lines.append(f"- `{result['source_id']}`: `{result['status']}`")
    else:
        lines.append("- Nessuna fonte interrogata.")

    lines.extend(["", "## Documenti collegati", ""])
    if document_links:
        lines.extend(f"- {link}" for link in document_links)
    else:
        lines.append("- Nessun documento collegato.")

    lines.extend(["", AUTO_END])
    return "\n".join(lines)


def _profile_person_markdown(*, profile_payload: dict[str, object], profiles_index: Path) -> str:
    identity = _dict_object(profile_payload.get("identity"))
    seed = _dict_object(profile_payload.get("seed"))
    metadata = _dict_object(profile_payload.get("metadata"))
    canonical_name = str(identity.get("canonical_name") or profile_payload.get("profile_id") or profile_payload.get("@id") or "")
    profile_id = str(profile_payload.get("profile_id") or profile_payload.get("@id") or "")
    verified_facts = _dict_object(profile_payload.get("verified_facts"))
    conflicts = _json_object_list(profile_payload.get("conflicts"))
    search_hints = _json_object_list(profile_payload.get("search_hints"))
    evidence_claim_ids = _json_string_list(profile_payload.get("evidence_claim_ids"))
    next_research = _json_string_list(profile_payload.get("next_research"))
    searched_sources = _json_string_list(profile_payload.get("searched_sources"))
    lines = [
        "---",
        "type: person_research_profile",
        f"profile_id: {_yaml_value(profile_id)}",
        f"name: {_yaml_value(canonical_name)}",
        f"model_version: {_yaml_value(metadata.get('model_version', ''))}",
        f"profiles_index: {_yaml_value(profiles_index)}",
        "---",
        "",
        f"# {canonical_name}",
        "",
        AUTO_BEGIN,
        "",
        "## Identita",
        "",
        f"- Profile ID: `{profile_id}`",
        f"- Nome canonico: {canonical_name or '(non indicato)'}",
        f"- Nome: {identity.get('given_name') or '(non indicato)'}",
        f"- Cognome: {identity.get('family_name') or '(non indicato)'}",
        f"- Alias: {_format_list(_json_string_list(identity.get('aliases')))}",
        f"- Forme nome: {_format_list(_json_string_list(identity.get('name_forms')))}",
        "",
        "## Fatti revisionati",
        "",
    ]
    if verified_facts:
        for field, fact in sorted(verified_facts.items()):
            lines.append(f"- `{field}`: {_format_verified_fact(fact)}")
    else:
        lines.append("- Nessun fatto revisionato.")

    lines.extend(["", "## Evidenze collegate", ""])
    if evidence_claim_ids:
        lines.extend(f"- `{claim_id}`" for claim_id in evidence_claim_ids)
    else:
        lines.append("- Nessuna EvidenceClaim collegata.")

    lines.extend(["", "## Conflitti aperti", ""])
    if conflicts:
        for conflict in conflicts:
            field = str(conflict.get("field", "(campo non indicato)"))
            current = str(conflict.get("current_value", "(non indicato)"))
            candidate = str(conflict.get("candidate_value", "(non indicato)"))
            status = str(conflict.get("review_status", "needs_review"))
            lines.append(f"- `{field}`: attuale `{current}`, candidato `{candidate}` | stato={status}")
    else:
        lines.append("- Nessun conflitto registrato.")

    lines.extend(["", "## Indizi operativi non pubblicabili", ""])
    if search_hints:
        for hint in search_hints:
            field = str(hint.get("field", ""))
            value = str(hint.get("value", ""))
            provenance = str(hint.get("provenance", ""))
            status = str(hint.get("review_status", "unreviewed"))
            lines.append(f"- `{field}`: {value} | provenance={provenance or '(non dichiarata)'} | stato={status}")
    else:
        lines.append("- Nessun search hint.")

    lines.extend(["", "## Prossime ricerche", ""])
    if next_research:
        lines.extend(f"- {item}" for item in next_research)
    else:
        lines.append("- Nessuna prossima ricerca registrata.")

    lines.extend(
        [
            "",
            "## Stato ricerca",
            "",
            f"- Fonti gia' cercate: {_format_list(searched_sources)}",
            f"- Seed source: {seed.get('source') or '(non indicata)'}",
            "- Nota: il seed resta un indizio operativo e non viene esportato come fatto verificato.",
            "",
            AUTO_END,
        ]
    )
    return "\n".join(lines)


def _load_mvp_profile_payload(profile: dict[str, object]) -> dict[str, object]:
    source_file = str(profile.get("profile_source_file", "")).strip()
    if not source_file:
        return {}
    try:
        path = Path(source_file)
        if not path.exists() or not path.is_file():
            return {}
        return _json_object(path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _mvp_publication_candidate_status(*, readiness: dict[str, object], review_session: dict[str, object]) -> str:
    if not review_session:
        return "draft"
    if int(_number_or_zero(review_session.get("invalid_count"))) > 0:
        return "publication_candidate_blocked"
    readiness_status = str(readiness.get("readiness_status", "needs_documents"))
    if readiness_status in {"needs_documents", "needs_claims", "needs_signal_review", "blocked"}:
        return "publication_candidate_blocked"
    if int(_number_or_zero(review_session.get("pending_count"))) > 0:
        return "needs_review"
    if str(review_session.get("session_status", "")) == "ready_for_curator_review":
        return "publication_candidate"
    return "draft"


def _number_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _document_markdown(*, document: sqlite3.Row, run: sqlite3.Row) -> str:
    access_mode = _document_access_mode(document["payload_json"])
    lines = [
        "---",
        "type: source_document",
        f"document_id: {_yaml_value(document['document_id'])}",
        f"source_id: {_yaml_value(document['source_id'])}",
        f"run_id: {_yaml_value(run['run_id'])}",
        "---",
        "",
        f"# {document['title']}",
        "",
        AUTO_BEGIN,
        "",
        f"- Document ID: `{document['document_id']}`",
        f"- Fonte: `{document['source_id']}`",
        f"- URL: {document['url']}",
        f"- Access date: {document['access_date']}",
        f"- Access mode: {access_mode}",
        f"- Path locale: {document['local_path'] or '(nessun file locale)'}",
        f"- Hash contenuto: {document['content_hash'] or '(non disponibile)'}",
        "",
        AUTO_END,
    ]
    return "\n".join(lines)


def _event_markdown(
    *,
    event: sqlite3.Row,
    run: sqlite3.Row,
    documents_by_id: dict[str, sqlite3.Row],
    claims_by_id: dict[str, sqlite3.Row],
) -> str:
    payload = _json_object(event["payload_json"])
    place_labels = _json_string_list(payload.get("place_labels"))
    place_ids = _json_string_list(payload.get("place_ids"))
    source_document_ids = _json_string_list(payload.get("source_document_ids"))
    evidence_claim_ids = _json_string_list(payload.get("evidence_claim_ids"))
    provenance = str(payload.get("provenance", ""))
    description = str(payload.get("description", ""))
    lines = [
        "---",
        "type: historical_event",
        f"event_id: {_yaml_value(event['event_id'])}",
        f"event_type: {_yaml_value(event['event_type'])}",
        f"review_status: {_yaml_value(event['review_status'])}",
        f"run_id: {_yaml_value(run['run_id'])}",
        "---",
        "",
        f"# {event['label']}",
        "",
        AUTO_BEGIN,
        "",
        "## Stato",
        "",
        f"- Event ID: `{event['event_id']}`",
        f"- Tipo: `{event['event_type']}`",
        f"- Stato revisione: `{event['review_status']}`",
        f"- Confidenza: `{payload.get('confidence', '')}`",
        f"- Provenance: {provenance or '(non dichiarata)'}",
        "",
        "## Descrizione",
        "",
        description or "Descrizione non ancora revisionata.",
        "",
        "## Date e luoghi",
        "",
        f"- Inizio: {event['date_start'] or '(non indicato)'}",
        f"- Fine: {event['date_end'] or '(non indicato)'}",
    ]
    if place_labels:
        lines.extend(f"- Luogo candidato: {place_label}" for place_label in place_labels)
    else:
        lines.append("- Luogo candidato: (non indicato)")
    if place_ids:
        lines.extend(f"- Place normalizzato candidato: {_obsidian_link('04_Luoghi', place_id)}" for place_id in place_ids)

    lines.extend(["", "## Documenti collegati", ""])
    if source_document_ids:
        for document_id in source_document_ids:
            if document_id in documents_by_id:
                lines.append(f"- {_obsidian_link('02_Documenti', document_id)}")
            else:
                lines.append(f"- `{document_id}` (non presente nella run esportata)")
    else:
        lines.append("- Nessun SourceDocument collegato.")

    lines.extend(["", "## EvidenceClaim collegate", ""])
    if evidence_claim_ids:
        for claim_id in evidence_claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is None:
                lines.append(f"- `{claim_id}` (non presente nella run esportata)")
                continue
            lines.append(
                "- "
                f"`{claim_id}`: {claim['field']} = {claim['value']} "
                f"| stato={claim['review_status']}"
            )
    else:
        lines.append("- Nessuna EvidenceClaim collegata.")

    lines.extend(
        [
            "",
            "## Partecipazioni",
            "",
            "Nessuna Participation creata da questo export.",
            "",
            AUTO_END,
        ]
    )
    return "\n".join(lines)


def _place_markdown(
    *,
    place: sqlite3.Row,
    run: sqlite3.Row,
    documents_by_id: dict[str, sqlite3.Row],
    claims_by_id: dict[str, sqlite3.Row],
) -> str:
    payload = _json_object(place["payload_json"])
    alternate_labels = _json_string_list(payload.get("alternate_labels"))
    admin_hierarchy = _json_string_list(payload.get("admin_hierarchy"))
    same_as = _json_string_list(payload.get("same_as"))
    source_document_ids = _json_string_list(payload.get("source_document_ids"))
    evidence_claim_ids = _json_string_list(payload.get("evidence_claim_ids"))
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    provenance = str(payload.get("provenance", ""))
    description = str(payload.get("description", ""))
    lines = [
        "---",
        "type: place",
        f"place_id: {_yaml_value(place['place_id'])}",
        f"place_type: {_yaml_value(place['place_type'])}",
        f"review_status: {_yaml_value(place['review_status'])}",
        f"run_id: {_yaml_value(run['run_id'])}",
        "---",
        "",
        f"# {place['preferred_label']}",
        "",
        AUTO_BEGIN,
        "",
        "## Stato",
        "",
        f"- Place ID: `{place['place_id']}`",
        f"- Tipo: `{place['place_type']}`",
        f"- Stato revisione: `{place['review_status']}`",
        f"- Confidenza: `{payload.get('confidence', '')}`",
        f"- Provenance: {provenance or '(non dichiarata)'}",
        "",
        "## Descrizione",
        "",
        description or "Descrizione non ancora revisionata.",
        "",
        "## Varianti e contesto",
        "",
    ]
    if alternate_labels:
        lines.extend(f"- Variante: {label}" for label in alternate_labels)
    else:
        lines.append("- Variante: (nessuna)")
    if admin_hierarchy:
        lines.extend(f"- Gerarchia amministrativa: {label}" for label in admin_hierarchy)
    else:
        lines.append("- Gerarchia amministrativa: (non indicata)")
    if latitude is not None and longitude is not None:
        lines.append(f"- Coordinate: {latitude}, {longitude}")
    else:
        lines.append("- Coordinate: (non attestate)")
    if same_as:
        lines.extend(f"- Same as candidato: {identifier}" for identifier in same_as)
    else:
        lines.append("- Same as candidato: (nessuno)")

    lines.extend(["", "## Documenti collegati", ""])
    if source_document_ids:
        for document_id in source_document_ids:
            if document_id in documents_by_id:
                lines.append(f"- {_obsidian_link('02_Documenti', document_id)}")
            else:
                lines.append(f"- `{document_id}` (non presente nella run esportata)")
    else:
        lines.append("- Nessun SourceDocument collegato.")

    lines.extend(["", "## EvidenceClaim collegate", ""])
    if evidence_claim_ids:
        for claim_id in evidence_claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is None:
                lines.append(f"- `{claim_id}` (non presente nella run esportata)")
                continue
            lines.append(
                "- "
                f"`{claim_id}`: {claim['field']} = {claim['value']} "
                f"| stato={claim['review_status']}"
            )
    else:
        lines.append("- Nessuna EvidenceClaim collegata.")

    lines.extend(
        [
            "",
            "## Relazioni storiche",
            "",
            "Nessuna relazione persona-luogo, evento-luogo forte, Membership o Participation creata da questo export.",
            "",
            AUTO_END,
        ]
    )
    return "\n".join(lines)


def _evidence_markdown(*, run: sqlite3.Row, claims: list[sqlite3.Row]) -> str:
    lines = [
        "---",
        "type: evidence_index",
        f"run_id: {_yaml_value(run['run_id'])}",
        "---",
        "",
        "# Evidenze",
        "",
        AUTO_BEGIN,
        "",
    ]
    if claims:
        for claim in claims:
            lines.append(
                "- "
                f"`{claim['claim_id']}`: {claim['subject_id']} | {claim['field']} = {claim['value']} "
                f"| stato={claim['review_status']}"
            )
    else:
        lines.append("Nessuna EvidenceClaim estratta per questa run.")
    lines.extend(["", AUTO_END])
    return "\n".join(lines)


def _log_markdown(
    *,
    run: sqlite3.Row,
    people: list[sqlite3.Row],
    results: list[sqlite3.Row],
    documents: list[sqlite3.Row],
    claims: list[sqlite3.Row],
) -> str:
    lines = [
        "---",
        "type: search_run",
        f"run_id: {_yaml_value(run['run_id'])}",
        "---",
        "",
        f"# Log ricerca {run['run_id']}",
        "",
        AUTO_BEGIN,
        "",
        "## Riepilogo",
        "",
        f"- Timestamp: {run['timestamp']}",
        f"- Input file: {run['input_file']}",
        f"- Fonti selezionate: {', '.join(_json_list(run['source_ids_json']))}",
        f"- Persone cercate: {len(people)}",
        f"- Risultati fonte: {len(results)}",
        f"- Documenti: {len(documents)}",
        f"- Evidenze: {len(claims)}",
        "",
        "## Persone",
        "",
    ]
    if people:
        for person in people:
            lines.append(f"- {_obsidian_link('01_Persone', person['full_name'])}")
    else:
        lines.append("- Nessuna persona registrata.")

    lines.extend(["", "## Risultati per fonte", ""])
    manual_lines: list[str] = []
    document_counts = _document_counts_by_source(documents)
    for result in results:
        lines.append(f"- `{result['source_id']}`: `{result['status']}` - {result['search_url']}")
        status = str(result["status"])
        source_id = str(result["source_id"])
        if status in MANUAL_REVIEW_STATUSES:
            manual_lines.append(f"- `{source_id}` ha stato `{status}`: verifica manuale richiesta.")
        elif document_counts.get(source_id, 0) == 0:
            manual_lines.append(f"- `{source_id}` non ha documenti registrati: verificare follow-up.")

    lines.extend(["", "## Verifiche manuali", ""])
    lines.extend(manual_lines or ["- Nessuna verifica manuale evidenziata."])
    lines.extend(["", AUTO_END])
    return "\n".join(lines)


def _write_preserving_editorial(path: Path, auto_markdown: str) -> None:
    editorial = _extract_editorial(path.read_text(encoding="utf-8") if path.exists() else "")
    final_text = "\n\n".join(
        [
            auto_markdown.rstrip(),
            editorial.rstrip(),
        ]
    ).rstrip() + "\n"
    path.write_text(final_text, encoding="utf-8")


def _extract_editorial(existing_text: str) -> str:
    if EDITORIAL_BEGIN in existing_text and EDITORIAL_END in existing_text:
        start = existing_text.index(EDITORIAL_BEGIN)
        end = existing_text.index(EDITORIAL_END) + len(EDITORIAL_END)
        return existing_text[start:end]
    return "\n".join([EDITORIAL_BEGIN, "", EDITORIAL_END])


def _obsidian_link(folder: str, identifier: str) -> str:
    return f"[[../{folder}/{slugify_identifier(identifier)}]]"


def _document_counts_by_source(documents: list[sqlite3.Row]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for document in documents:
        source_id = str(document["source_id"])
        counts[source_id] = counts.get(source_id, 0) + 1
    return counts


def _select_mvp_profiles(*, payload: dict[str, object], limit: int) -> list[dict[str, object]]:
    profiles = _json_object_list(payload.get("profiles"))
    links = _json_object_list(payload.get("candidate_document_person_links"))
    claims = _json_object_list(payload.get("candidate_evidence_claims"))
    signal_groups = _json_object_list(payload.get("reviewable_document_signals"))
    score_by_profile: dict[str, int] = {}
    for link in links:
        profile_id = _profile_id_from_item(link)
        score_by_profile[profile_id] = score_by_profile.get(profile_id, 0) + 1
    for claim in claims:
        profile_id = _profile_id_from_item(claim)
        score_by_profile[profile_id] = score_by_profile.get(profile_id, 0) + 100
    for group in signal_groups:
        profile_id = str(group.get("profile_id", ""))
        score_by_profile[profile_id] = score_by_profile.get(profile_id, 0) + len(_json_object_list(group.get("signals")))
    ordered = sorted(
        profiles,
        key=lambda profile: (-score_by_profile.get(str(profile.get("profile_id", "")), 0), str(profile.get("canonical_name", ""))),
    )
    effective_limit = 10 if limit <= 0 else min(limit, 10)
    return ordered[:effective_limit]


def _documents_for_profiles(
    *,
    documents: list[dict[str, object]],
    links: list[dict[str, object]],
    claims: list[dict[str, object]],
    signal_groups: list[dict[str, object]],
    profiles: list[dict[str, object]],
) -> list[dict[str, object]]:
    selected = {str(profile.get("profile_id", "")) for profile in profiles}
    signals = [
        signal
        for group in signal_groups
        if str(group.get("profile_id", "")) in selected
        for signal in _json_object_list(group.get("signals"))
    ]
    document_ids = {
        str(item.get("source_document_id", ""))
        for item in [*links, *claims]
        if _profile_id_from_item(item) in selected and str(item.get("source_document_id", ""))
    }
    document_ids.update(str(signal.get("source_document_id", "")) for signal in signals if str(signal.get("source_document_id", "")))
    by_id = {str(document.get("source_document_id", "")): document for document in documents}
    return [by_id.get(document_id, {"source_document_id": document_id, "review_status": "unreviewed"}) for document_id in sorted(document_ids)]


def _mvp_profile_readiness(
    *,
    payload: dict[str, object],
    profiles: list[dict[str, object]],
    links: list[dict[str, object]],
    claims: list[dict[str, object]],
    signal_groups: list[dict[str, object]],
    documents: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    from_payload = {
        str(item.get("profile_id", "")): item
        for item in _json_object_list(payload.get("profile_readiness"))
        if str(item.get("profile_id", ""))
    }
    if from_payload:
        return from_payload

    document_ids = {str(document.get("source_document_id", "")) for document in documents if str(document.get("source_document_id", ""))}
    signals_by_profile = {
        str(group.get("profile_id", "")): _json_object_list(group.get("signals"))
        for group in signal_groups
        if str(group.get("profile_id", ""))
    }
    readiness: dict[str, dict[str, object]] = {}
    for profile in profiles:
        profile_id = str(profile.get("profile_id", ""))
        profile_links = [link for link in links if _profile_id_from_item(link) == profile_id]
        profile_claims = [claim for claim in claims if _profile_id_from_item(claim) == profile_id]
        profile_signals = signals_by_profile.get(profile_id, [])
        profile_document_ids = {
            str(item.get("source_document_id", ""))
            for item in [*profile_links, *profile_claims, *profile_signals]
            if str(item.get("source_document_id", ""))
        }
        if document_ids:
            profile_document_ids &= document_ids
        status, next_action = _mvp_readiness_status_and_action(
            document_count=len(profile_document_ids),
            link_count=len(profile_links),
            claim_count=len(profile_claims),
            signal_count=len(profile_signals),
        )
        readiness[profile_id] = {
            "profile_id": profile_id,
            "canonical_name": profile.get("canonical_name", ""),
            "document_count": len(profile_document_ids),
            "candidate_document_person_link_count": len(profile_links),
            "candidate_evidence_claim_count": len(profile_claims),
            "reviewable_document_signal_count": len(profile_signals),
            "readiness_status": status,
            "next_action": next_action,
            "review_status": "unreviewed",
            "publication_status": "not_publishable_without_human_review",
        }
    return readiness


def _mvp_readiness_status_and_action(*, document_count: int, link_count: int, claim_count: int, signal_count: int) -> tuple[str, str]:
    if document_count == 0:
        return "needs_documents", "Registrare o collegare almeno un documento revisionabile."
    if link_count == 0:
        return "needs_links", "Verificare il link candidato documento-persona."
    if claim_count == 0:
        if signal_count > 0:
            return "needs_signal_review", "Revisionare piste documentali e valutare segmentazione per produrre claim candidati."
        return "needs_claims", "Migliorare testo/OCR o regole per produrre claim candidati."
    return "ready_for_review", "Revisionare documenti, link e claim candidati."


def _mvp_signals_for_profile(signal_groups: list[dict[str, object]], profile_id: str) -> list[dict[str, object]]:
    for group in signal_groups:
        if str(group.get("profile_id", "")) == profile_id:
            return _json_object_list(group.get("signals"))
    return []


def _profile_id_from_item(item: dict[str, object]) -> str:
    return str(item.get("profile_id") or item.get("person_candidate_id") or item.get("person_id") or "")


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


def _json_object(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _load_optional_json_object(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    try:
        if not path.exists() or not path.is_file():
            return {}
        return _json_object(path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _review_session_profiles_by_id(review_session: dict[str, object]) -> dict[str, dict[str, object]]:
    profiles_by_id: dict[str, dict[str, object]] = {}
    for item in _json_object_list(review_session.get("profiles")):
        profile_id = str(item.get("profile_id", "")).strip()
        if profile_id:
            profiles_by_id[profile_id] = item
    return profiles_by_id


def _profile_name_for_id(profiles: list[dict[str, object]], profile_id: str) -> str:
    for profile in profiles:
        if str(profile.get("profile_id", "")) == profile_id:
            return str(profile.get("canonical_name") or profile_id)
    return ""


def _dict_object(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _dict_get(value: object, key: str, default: object = "") -> object:
    return value.get(key, default) if isinstance(value, dict) else default


def _json_object_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _json_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _format_verified_fact(value: object) -> str:
    if isinstance(value, dict):
        fact_value = str(value.get("value", ""))
        review_status = str(value.get("review_status", ""))
        provenance = str(value.get("provenance", ""))
        claims = _json_string_list(value.get("source_claim_ids"))
        documents = _json_string_list(value.get("source_document_ids"))
        parts = [fact_value or "(valore non indicato)"]
        if review_status:
            parts.append(f"stato={review_status}")
        if provenance:
            parts.append(f"provenance={provenance}")
        if claims:
            parts.append("claim=" + ", ".join(f"`{claim_id}`" for claim_id in claims))
        if documents:
            parts.append("documenti=" + ", ".join(f"`{document_id}`" for document_id in documents))
        return " | ".join(parts)
    return str(value)


def _format_list(values: list[str]) -> str:
    if not values:
        return "(nessuno)"
    return ", ".join(values)


def _yaml_value(value: object) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def main() -> int:
    parser = argparse.ArgumentParser(description="Esporta un vault Obsidian dal database SQLite o dai profili JSON-LD.")
    parser.add_argument("--db", default="data/evidence.sqlite", help="Percorso del database SQLite.")
    parser.add_argument("--output-dir", required=True, help="Cartella root del vault Obsidian.")
    parser.add_argument("--run-id", default="", help="Identificativo della run SQLite da esportare.")
    parser.add_argument("--profiles-index", default="", help="Indice PersonResearchProfile JSON-LD da esportare.")
    parser.add_argument("--profile-id", default="", help="Filtra un singolo profilo JSON-LD.")
    parser.add_argument("--limit", type=int, default=0, help="Numero massimo di profili JSON-LD da esportare; 0 = tutti.")
    parser.add_argument("--mvp-pilot-summary", default="", help="Summary JSON MvpPilotSummary da esportare come pacchetto di revisione.")
    parser.add_argument("--mvp-review-queue", default="", help="Review queue Markdown MVP da linkare nella dashboard.")
    parser.add_argument("--mvp-review-decisions-summary", default="", help="Riepilogo decisioni MVP JSON da linkare e visualizzare nel vault.")
    args = parser.parse_args()

    try:
        if args.mvp_pilot_summary.strip():
            result = export_mvp_pilot_obsidian_vault(
                summary_json=Path(args.mvp_pilot_summary),
                output_dir=Path(args.output_dir),
                limit=args.limit or 10,
                review_queue_md=Path(args.mvp_review_queue) if args.mvp_review_queue.strip() else None,
                review_decisions_summary=(
                    Path(args.mvp_review_decisions_summary) if args.mvp_review_decisions_summary.strip() else None
                ),
            )
            print(f"Vault Obsidian MVP pilota esportato in {result['output_dir']}")
            print(f"Profili esportati: {result['profiles_exported']}")
            print(f"File scritti: {len(result['files'])}")
            return 0
        if args.profiles_index.strip():
            result = export_profile_obsidian_vault(
                profiles_index=Path(args.profiles_index),
                output_dir=Path(args.output_dir),
                profile_id=args.profile_id,
                limit=args.limit,
            )
            print(f"Vault Obsidian profili esportato in {result['output_dir']}")
            print(f"Profili esportati: {result['profiles_exported']}")
            print(f"File scritti: {len(result['files'])}")
            return 0
        if not args.run_id.strip():
            print("Specificare --run-id, --profiles-index oppure --mvp-pilot-summary.")
            return 2
        result = export_obsidian_vault(db_path=Path(args.db), run_id=args.run_id, output_dir=Path(args.output_dir))
    except ValueError as error:
        print(str(error))
        return 2

    print(f"Vault Obsidian esportato in {result['output_dir']}")
    print(f"File scritti: {len(result['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

