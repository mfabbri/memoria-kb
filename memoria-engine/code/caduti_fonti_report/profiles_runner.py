from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .authenticated_session import ManualAuthenticatedPlaywrightSession, source_uses_manual_authenticated_session
from .config import load_source_registry, load_sources_from_yaml
from .connectors.registry import create_source_connector
from .document_analysis.online_source_acquisition import acquire_online_source_documents, acquisition_summary
from .models import Caduto, PersonResearchProfile, SourceSelection
from .person_profiles import person_query_from_profile
from .planned_search_attempts import planned_search_attempts_to_dict
from .profile_repository import ProfileRepository
from .renderers import render_markdown, render_single_caduto_markdown, slugify
from .runner import REPORT_SOURCE_KINDS_WITH_DELAY, log_progress
from .search_strategy_planner import plan_profile_search
from .source_definitions import has_source_definition, load_source_definition
from .validate_sources_registry import validate_sources_registry_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue il meta motore usando PersonResearchProfile JSON-LD.")
    parser.add_argument("--profiles-index", required=True)
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml")
    parser.add_argument("--output-md", default="risultati/profili_purocielo_fonti_report.md")
    parser.add_argument("--output-json", default="risultati/profili_purocielo_fonti_report.json")
    parser.add_argument("--output-dir", default="risultati/profili_purocielo_schede")
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--source", default="", help="ID di una singola fonte da provare.")
    parser.add_argument("--profile-id", default="", help="Filtra per profile_id, file o slug profilo.")
    parser.add_argument("--name", default="", help="Filtra per nome canonico del profilo.")
    parser.add_argument("--include-search-plan", action="store_true", help="Include nel JSON i tentativi pianificati senza cambiare l'esecuzione.")
    parser.add_argument("--execute-first-planned-attempt", action="store_true", help="Esegue solo il primo tentativo pianificato; richiede source e limit > 0.")
    parser.add_argument("--ensure-authenticated-session", action="store_true", help="Apre/riusa prima della ricerca le sessioni manual_persistent_context selezionate.")
    parser.add_argument("--refresh-authenticated-cache", action="store_true", help="Ignora la cache autenticata locale e rifetcha live le pagine manual_persistent_context.")
    parser.add_argument("--keep-authenticated-browser-open-seconds", type=int, default=0, help="Mantiene aperto il browser autenticato per N secondi prima della chiusura finale.")
    parser.add_argument("--acquire-documents-root", default="", help="Se impostato, acquisisce i SourceDocument di dettaglio come documenti offline processabili.")
    args = parser.parse_args()

    result = run_profiles_report(
        profiles_index=Path(args.profiles_index),
        sources_yaml=Path(args.sources_yaml),
        output_md=Path(args.output_md),
        output_json=Path(args.output_json),
        output_dir=Path(args.output_dir),
        delay=args.delay,
        limit=args.limit,
        source_id=args.source,
        profile_id=args.profile_id,
        name_filter=args.name,
        include_search_plan=args.include_search_plan,
        execute_first_planned_attempt=args.execute_first_planned_attempt,
        ensure_authenticated_session=args.ensure_authenticated_session,
        refresh_authenticated_cache=args.refresh_authenticated_cache,
        keep_authenticated_browser_open_seconds=args.keep_authenticated_browser_open_seconds,
        acquire_documents_root=Path(args.acquire_documents_root) if args.acquire_documents_root else None,
    )
    return int(result["exit_code"])


def run_profiles_report(
    *,
    profiles_index: Path,
    sources_yaml: Path,
    output_md: Path,
    output_json: Path,
    output_dir: Path,
    delay: float = 0.0,
    limit: int = 0,
    source_id: str = "",
    profile_id: str = "",
    name_filter: str = "",
    include_search_plan: bool = False,
    execute_first_planned_attempt: bool = False,
    ensure_authenticated_session: bool = False,
    refresh_authenticated_cache: bool = False,
    keep_authenticated_browser_open_seconds: int = 0,
    acquire_documents_root: Path | None = None,
) -> dict[str, object]:
    profiles_index = Path(profiles_index)
    sources_yaml = Path(sources_yaml)
    output_md = Path(output_md)
    output_json = Path(output_json)
    output_dir = Path(output_dir)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    if execute_first_planned_attempt and (not source_id.strip() or limit <= 0):
        print("La modalita' execute-first-planned-attempt richiede Source e Limit > 0.")
        return {
            "exit_code": 2,
            "output_json": str(output_json),
            "output_md": str(output_md),
            "output_dir": str(output_dir),
            "profiles_count": 0,
            "sources_count": 0,
            "error": "planned_execution_requires_source_limit",
        }

    include_search_plan = include_search_plan or execute_first_planned_attempt
    max_search_attempts = 1 if execute_first_planned_attempt else 0
    planned_execution_mode = "first_planned_attempt" if execute_first_planned_attempt else "standard"

    repository = ProfileRepository(profiles_index)
    profiles = repository.load_profiles(
        profile_id=profile_id,
        name_filter=name_filter,
        limit=limit,
        include_legacy_seed=bool(profile_id.strip()),
    )
    if not profiles:
        print("Nessun profilo trovato per i filtri richiesti.")
        return {
            "exit_code": 2,
            "output_json": str(output_json),
            "output_md": str(output_md),
            "output_dir": str(output_dir),
            "profiles_count": 0,
            "sources_count": 0,
            "error": "profile_not_found",
        }

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
            "profiles_count": len(profiles),
            "sources_count": 0,
            "error": "source_not_found",
        }

    sources = source_selection.selected_sources
    _apply_authenticated_runtime_options(
        sources=sources,
        refresh_authenticated_cache=refresh_authenticated_cache,
        keep_authenticated_browser_open_seconds=keep_authenticated_browser_open_seconds,
    )
    selected_source_ids = {source.source_id for source in sources}
    validation = validate_sources_registry_file(sources_yaml, only_source_ids=selected_source_ids)
    if not validation.valid:
        print("Registry fonti non valido; esecuzione interrotta.")
        for error in validation.errors:
            print(f"- {error}")
        return {
            "exit_code": 2,
            "output_json": str(output_json),
            "output_md": str(output_md),
            "output_dir": str(output_dir),
            "profiles_count": len(profiles),
            "sources_count": len(sources),
            "error": "invalid_sources_registry",
        }

    repo_root = _repo_root_from_sources_yaml(sources_yaml)
    prepared_authenticated_sessions: dict[str, tuple[ManualAuthenticatedPlaywrightSession, object]] = {}
    if ensure_authenticated_session:
        prepared_authenticated_sessions = _ensure_manual_authenticated_sessions(sources=sources, repo_root=repo_root)

    connectors = {
        source.source_id: create_source_connector(
            source,
            run_id=f"profiles-meta-search:{source.source_id}",
            repo_root=repo_root,
            max_search_attempts=max_search_attempts,
            authenticated_session_factory=(
                _prepared_authenticated_session_factory(prepared_authenticated_sessions)
                if prepared_authenticated_sessions
                else None
            ),
        )
        for source in sources
    }
    caduti = [_caduto_from_profile(profile) for profile in profiles]
    caduto_by_profile_id = {profile.profile_id: caduto for profile, caduto in zip(profiles, caduti, strict=True)}
    aggregated: dict[str, list] = {}
    aggregated_details: dict[str, list[dict[str, object]]] = {}
    acquired_documents: list[dict[str, object]] = []

    log_progress(
        f"Avvio report profili: {len(profiles)} profili, {len(sources)} fonti, INDEX={profiles_index}, YAML={sources_yaml}"
    )
    _warn_manual_authenticated_sources(sources)

    try:
        for profile_index, profile in enumerate(profiles, start=1):
            caduto = caduto_by_profile_id[profile.profile_id]
            key = caduto.intestazione_pdf
            log_progress(f"[{profile_index}/{len(profiles)}] Profilo: {profile.profile_id} ({profile.identity.canonical_name})")
            source_results = []
            source_result_entries: list[dict[str, object]] = []
            query = person_query_from_profile(profile)
            for source_index, source in enumerate(sources, start=1):
                log_progress(f"  [{source_index}/{len(sources)}] Fonte: {source.source_name}")
                source_started_at = time.perf_counter()
                connector = connectors[source.source_id]
                planned_attempts = (
                    _planned_attempts_for_profile_source(profile=profile, source=source, repo_root=repo_root)
                    if include_search_plan
                    else []
                )
                results = connector.search_person(query)
                elapsed = time.perf_counter() - source_started_at
                for result in results:
                    planned_attempt_match = (
                        _planned_attempt_match_metadata(planned_attempts=planned_attempts, result_query=result.query)
                        if include_search_plan
                        else {}
                    )
                    documents = connector.fetch_detail(result)
                    claims = []
                    for document in documents:
                        claims.extend(connector.extract_evidence(document))
                    acquisition_items: list[dict[str, object]] = []
                    if acquire_documents_root is not None:
                        acquisition_items = acquire_online_source_documents(
                            documents=documents,
                            root_dir=acquire_documents_root,
                            profile_slug=slugify(profile.identity.canonical_name or profile.profile_id),
                            profile_id=profile.profile_id,
                            profile_source_file=profile.metadata.get("profile_source_file", ""),
                        )
                        acquired_documents.extend(acquisition_items)
                    source_results.append(result)
                    source_result_entries.append(
                        {
                            "profile_id": profile.profile_id,
                            "profile_source_file": profile.metadata.get("profile_source_file", ""),
                            "person_query": asdict(query),
                            "result": asdict(result),
                            "documents": [asdict(document) for document in documents],
                            "claims": [asdict(claim) for claim in claims],
                            "acquired_documents": acquisition_items,
                            **(
                                {
                                    "planned_execution_mode": planned_execution_mode,
                                    "planned_attempt_execution_limit": max_search_attempts,
                                }
                                if include_search_plan
                                else {}
                            ),
                            **({"planned_attempts": planned_attempts} if include_search_plan else {}),
                            **planned_attempt_match,
                        }
                    )
                    log_progress(
                        f"  [{source_index}/{len(sources)}] Esito {source.source_id}: {result.status} in {elapsed:.1f}s"
                    )
                if not results:
                    log_progress(
                        f"  [{source_index}/{len(sources)}] Esito {source.source_id}: nessun risultato prodotto dal connettore"
                    )
                if source.kind in REPORT_SOURCE_KINDS_WITH_DELAY and delay > 0:
                    time.sleep(delay)
            aggregated[key] = source_results
            aggregated_details[key] = source_result_entries
            log_progress(f"[{profile_index}/{len(profiles)}] Completato: {profile.profile_id}")
    finally:
        for connector in connectors.values():
            close_connector = getattr(connector, "close", None)
            if callable(close_connector):
                close_connector()
        for session, _state in prepared_authenticated_sessions.values():
            session.close()

    profile_source_selection = SourceSelection(
        source_file=str(sources_yaml),
        selected_sources=source_selection.selected_sources,
        selected_source_ids=source_selection.selected_source_ids,
        unresolved_source_ids=source_selection.unresolved_source_ids,
        used_fallback=source_selection.used_fallback,
    )
    output_md.write_text(render_markdown(caduti, aggregated, profile_source_selection, aggregated_details), encoding="utf-8")

    for caduto in caduti:
        filename = f"{slugify(caduto.intestazione_pdf)}.md"
        (output_dir / filename).write_text(
            render_single_caduto_markdown(caduto, aggregated[caduto.intestazione_pdf], aggregated_details[caduto.intestazione_pdf]),
            encoding="utf-8",
        )

    serializable = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_mode": "person_profiles_jsonld",
        "profiles_index": str(profiles_index),
        "source_selection": {
            "source_file": source_selection.source_file,
            "selected_source_ids": source_selection.selected_source_ids,
            "unresolved_source_ids": source_selection.unresolved_source_ids,
            "used_fallback": source_selection.used_fallback,
        },
        "include_search_plan": include_search_plan,
        "planned_execution_mode": planned_execution_mode,
        "planned_attempt_execution_limit": max_search_attempts,
        "acquire_documents_root": str(acquire_documents_root) if acquire_documents_root is not None else "",
        "acquired_documents_summary": acquisition_summary(acquired_documents),
        "profiles": [
            {
                "profile_id": profile.profile_id,
                "profile_source_file": profile.metadata.get("profile_source_file", ""),
                "canonical_name": profile.identity.canonical_name,
                "person_query": asdict(person_query_from_profile(profile)),
                "results": aggregated_details[caduto_by_profile_id[profile.profile_id].intestazione_pdf],
            }
            for profile in profiles
        ],
    }
    output_json.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")

    log_progress("Scrittura output profili completata")
    print(f"Report markdown scritto in {output_md}")
    print(f"Report json scritto in {output_json}")
    print(f"Schede singole scritte in {output_dir}")
    print(f"Indice profili usato: {profiles_index}")
    print(f"File fonti usato: {sources_yaml}")
    print(f"Fonti selezionate: {len(sources)}")
    print(f"Profili processati: {len(profiles)}")
    if acquire_documents_root is not None:
        summary = acquisition_summary(acquired_documents)
        print(
            "Documenti online acquisiti: "
            f"{summary['acquired_count']} testuali, "
            f"{summary.get('related_acquired_count', 0)} correlati, "
            f"{summary.get('total_acquired_file_count', summary['acquired_count'])} file totali / {summary['count']} SourceDocument"
        )
    return {
        "exit_code": 0,
        "output_json": str(output_json),
        "output_md": str(output_md),
        "output_dir": str(output_dir),
        "profiles_count": len(profiles),
        "sources_count": len(sources),
        "acquired_documents_count": acquisition_summary(acquired_documents)["acquired_count"],
        "error": "",
    }


def _caduto_from_profile(profile: PersonResearchProfile) -> Caduto:
    payload = profile.seed.payload
    return Caduto(
        intestazione_pdf=str(payload.get("intestazione_pdf") or profile.profile_id),
        nome=profile.identity.canonical_name,
        origine_sulla_lapide=str(payload.get("origine_sulla_lapide") or (profile.places[0] if profile.places else "")),
        nascita=profile.birth.get("date", ""),
        morte=profile.death.get("date", ""),
        ruolo_affiliazione=profile.formations[0] if profile.formations else "",
        fonti_richiamate=str(payload.get("fonti_richiamate", "")),
        profilo_biografico=str(payload.get("profilo_biografico", "")),
        episodio_documentato=profile.events[0] if profile.events else "",
    )


def _repo_root_from_sources_yaml(sources_yaml: Path) -> Path:
    resolved = sources_yaml.resolve()
    if resolved.parent.name == "ricerche":
        return resolved.parent.parent
    return resolved.parent


def _planned_attempts_for_profile_source(*, profile: PersonResearchProfile, source, repo_root: Path) -> list[dict[str, object]]:
    if not has_source_definition(source, repo_root=repo_root):
        return []
    source_definition = load_source_definition(source, repo_root=repo_root)
    return planned_search_attempts_to_dict(
        plan_profile_search(profile=profile, source=source, source_definition=source_definition)
    )


def _planned_attempt_match_metadata(*, planned_attempts: list[dict[str, object]], result_query: str) -> dict[str, object]:
    for attempt in planned_attempts:
        if str(attempt.get("query_text", "")) == result_query:
            return {
                "matched_planned_attempt_id": str(attempt.get("attempt_id", "")),
                "matched_planned_attempt_priority": attempt.get("priority", 0),
                "matched_planned_attempt_status": "matched",
            }
    return {
        "matched_planned_attempt_id": "",
        "matched_planned_attempt_priority": 0,
        "matched_planned_attempt_status": "unmatched",
    }


def _warn_manual_authenticated_sources(sources) -> None:
    authenticated_source_ids = [source.source_id for source in sources if source_uses_manual_authenticated_session(source)]
    if not authenticated_source_ids:
        return
    joined_ids = ", ".join(authenticated_source_ids)
    print(
        "Avviso: la run include fonti con sessione autenticata manuale "
        f"({joined_ids}). Se la cache locale non basta, il fetch di dettaglio puo' aprire SPID/CIE."
    )


def _apply_authenticated_runtime_options(
    *,
    sources,
    refresh_authenticated_cache: bool,
    keep_authenticated_browser_open_seconds: int,
) -> None:
    keep_seconds = max(0, int(keep_authenticated_browser_open_seconds))
    for source in sources:
        if not source_uses_manual_authenticated_session(source):
            continue
        if refresh_authenticated_cache:
            source.auth["force_refresh_authenticated_cache"] = "true"
        if keep_seconds > 0:
            source.auth["keep_open_seconds"] = str(keep_seconds)


def _ensure_manual_authenticated_sessions(*, sources, repo_root: Path) -> dict[str, tuple[ManualAuthenticatedPlaywrightSession, object]]:
    authenticated_sources = [source for source in sources if source_uses_manual_authenticated_session(source)]
    if not authenticated_sources:
        return {}
    sessions: dict[str, tuple[ManualAuthenticatedPlaywrightSession, object]] = {}
    for source in authenticated_sources:
        print(f"Preparazione sessione autenticata manuale per {source.source_id}...")
        session = ManualAuthenticatedPlaywrightSession(source, repo_root=repo_root)
        try:
            session.__enter__()
            state = session.ensure_authenticated()
            print(
                "Sessione autenticata: "
                f"{source.source_id} state={state.state} note={state.note} checked_url={state.checked_url}"
            )
            sessions[source.source_id] = (session, state)
        except Exception:
            session.close()
            raise
    return sessions


def _prepared_authenticated_session_factory(sessions: dict[str, tuple[ManualAuthenticatedPlaywrightSession, object]]):
    def factory(source, repo_root: Path):
        prepared = sessions.get(source.source_id)
        if prepared is None:
            return ManualAuthenticatedPlaywrightSession(source, repo_root=repo_root)
        session, state = prepared
        return _PreparedAuthenticatedSession(session, state)

    return factory


class _PreparedAuthenticatedSession:
    def __init__(self, session: ManualAuthenticatedPlaywrightSession, authenticated_state: object) -> None:
        self._session = session
        self._authenticated_state = authenticated_state

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, name: str):
        return getattr(self._session, name)

    def ensure_authenticated(self):
        return self._authenticated_state

    def close(self) -> None:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
