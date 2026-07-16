from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import yaml

from caduti_fonti_report.document_analysis.mvp_demo_descriptor import build_mvp_demo_aligned_ledger, build_mvp_demo_descriptor
from caduti_fonti_report.workspace_storage import LocalWorkspaceStorage, WorkspaceStorage
from caduti_fonti_report.workspace_resolver import DataRootResolution, DataRootResolutionError, resolve_data_root


REQUIRED_DATA_ROOT_DIRS = (
    "risultati",
    "documenti_da_processare",
    "documenti_processati",
    "docs",
    "logs",
    "ricerche",
    "archivi",
    "secure",
    "database",
)

SIBLING_REPOSITORIES = (
    "memoria-bootstrap",
    "memoria-engine",
    "memoria-knowledge",
    "memoria-rules",
    "memoria-sources",
    "memoria-workspace",
)

INVENTORY_SECTIONS = (
    "risultati",
    "documenti_processati",
    "documenti_da_processare",
)

MAX_INVENTORY_NAMES = 20
DEFAULT_PROFILES_INDEX = Path("ricerche") / "person_profiles" / "purocielo.index.jsonld"
DEFAULT_SOURCES_REGISTRY = Path("ricerche") / "camalanca_fonti.yaml"
DEFAULT_MVP_DEMO_DESCRIPTOR = Path("database") / "memoria_mvp_demo.active.json"


@dataclass(frozen=True)
class SectionInventory:
    name: str
    path: Path
    exists: bool
    top_level_files: int
    top_level_dirs: int
    names: tuple[str, ...]


@dataclass(frozen=True)
class ProfilesStatus:
    data_root: Path
    index_path: Path
    index_exists: bool
    index_count: int
    loaded_profiles: int
    missing_profile_files: tuple[str, ...]
    profile_statuses: tuple[tuple[str, int], ...]
    review_statuses: tuple[tuple[str, int], ...]
    publication_statuses: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ReviewRunCandidate:
    run_id: str
    run_dir: Path
    score: int
    profile_count: int
    review_queue_count: int
    decision_count: int
    historical_decision_count: int
    session_item_count: int
    reason: str
    review_session_path: Path
    review_queue_path: Path
    review_decisions_path: Path
    ledger_path: Path


@dataclass(frozen=True)
class ReviewDecisionsStatus:
    data_root: Path
    source: str
    run_id: str
    decisions_path: Path | None
    decisions_available: bool
    decision_count: int
    historical_decision_count: int
    selected_actions: tuple[tuple[str, int], ...]
    decision_statuses: tuple[tuple[str, int], ...]
    subject_kinds: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ConsolidateRunCandidate:
    run_id: str
    run_dir: Path
    score: int
    ledger_available: bool
    review_queue_available: bool
    review_session_available: bool
    decision_summary_available: bool
    profile_count: int
    decision_count: int
    reason: str
    ledger_path: Path
    review_queue_path: Path
    review_session_path: Path
    review_decisions_path: Path


@dataclass(frozen=True)
class SourcesOnlineDiscovery:
    data_root: Path
    registry_path: Path
    registry_exists: bool
    enabled_source_count: int
    source_definition_count: int
    candidate_source_ids: tuple[str, ...]
    profiles_index_path: Path
    profiles_index_exists: bool
    profile_count: int


@dataclass(frozen=True)
class MvpDemoStatus:
    data_root: Path
    descriptor_status: MvpDemoDescriptorStatus
    profiles_status: ProfilesStatus
    review_candidates: tuple[ReviewRunCandidate, ...]
    review_session_available: bool
    review_decisions_status: ReviewDecisionsStatus
    consolidate_candidates: tuple[ConsolidateRunCandidate, ...]
    consolidate_session_available: bool
    sources_online: SourcesOnlineDiscovery
    offline_intake: SectionInventory
    offline_processed: SectionInventory


@dataclass(frozen=True)
class MvpDemoDescriptorStatus:
    data_root: Path
    descriptor_path: Path
    exists: bool
    valid_json: bool
    contract_version: str
    status: str
    preview_only: bool | None
    publication_status: str
    run_id: str
    run_dir: Path | None
    run_dir_exists: bool
    primary_profile_ids: tuple[str, ...]
    contrast_profile_ids: tuple[str, ...]
    source_document_ids: tuple[str, ...]
    source_families: tuple[str, ...]
    artifact_paths: tuple[tuple[str, str, bool], ...]
    safety_flags: tuple[tuple[str, bool], ...]


def inspect_required_dirs(data_root: Path, storage: WorkspaceStorage | None = None) -> list[tuple[str, bool]]:
    workspace = storage or LocalWorkspaceStorage(data_root)
    return [(name, workspace.stat(name).is_dir) for name in REQUIRED_DATA_ROOT_DIRS]


def inspect_sibling_repositories(project_root: Path, storage: WorkspaceStorage | None = None) -> list[tuple[str, bool]]:
    workspace = storage or LocalWorkspaceStorage(project_root)
    return [(name, workspace.stat(name).is_dir) for name in SIBLING_REPOSITORIES]


def inspect_inventory_section(data_root: Path, section: str) -> SectionInventory:
    section_path = data_root / section
    if not section_path.is_dir():
        return SectionInventory(
            name=section,
            path=section_path,
            exists=False,
            top_level_files=0,
            top_level_dirs=0,
            names=(),
        )

    entries = sorted(section_path.iterdir(), key=lambda item: item.name.lower())
    file_count = sum(1 for entry in entries if entry.is_file())
    dir_count = sum(1 for entry in entries if entry.is_dir())
    preview_names = tuple(entry.name + ("/" if entry.is_dir() else "") for entry in entries[:MAX_INVENTORY_NAMES])
    return SectionInventory(
        name=section,
        path=section_path,
        exists=True,
        top_level_files=file_count,
        top_level_dirs=dir_count,
        names=preview_names,
    )


def inspect_profiles_status(data_root: Path, profiles_index: Path | None = None) -> ProfilesStatus:
    index_path = profiles_index or data_root / DEFAULT_PROFILES_INDEX
    if not index_path.is_file():
        return ProfilesStatus(
            data_root=data_root,
            index_path=index_path,
            index_exists=False,
            index_count=0,
            loaded_profiles=0,
            missing_profile_files=(),
            profile_statuses=(),
            review_statuses=(),
            publication_statuses=(),
        )

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    profile_entries = [item for item in payload.get("profiles", []) if isinstance(item, dict)]
    profile_statuses: Counter[str] = Counter()
    review_statuses: Counter[str] = Counter()
    publication_statuses: Counter[str] = Counter()
    missing_profile_files: list[str] = []
    loaded_profiles = 0

    for entry in profile_entries:
        file_name = str(entry.get("file", "")).strip()
        if not file_name:
            missing_profile_files.append("<missing file field>")
            continue
        profile_path = index_path.parent / file_name
        if not profile_path.is_file():
            missing_profile_files.append(file_name)
            continue

        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        metadata = profile.get("metadata", {}) if isinstance(profile.get("metadata"), dict) else {}
        profile_statuses[_status_value(metadata.get("profile_status"))] += 1
        review_statuses[_status_value(profile.get("review_status") or metadata.get("review_status"))] += 1
        publication_statuses[_status_value(profile.get("publication_status") or metadata.get("publication_status"))] += 1
        loaded_profiles += 1

    return ProfilesStatus(
        data_root=data_root,
        index_path=index_path,
        index_exists=True,
        index_count=len(profile_entries),
        loaded_profiles=loaded_profiles,
        missing_profile_files=tuple(missing_profile_files),
        profile_statuses=_sorted_counts(profile_statuses),
        review_statuses=_sorted_counts(review_statuses),
        publication_statuses=_sorted_counts(publication_statuses),
    )


def inspect_review_run_candidates(data_root: Path) -> tuple[ReviewRunCandidate, ...]:
    runs_root = data_root / "risultati" / "runs"
    if not runs_root.is_dir():
        return ()
    candidates = [
        candidate
        for run_dir in sorted((item for item in runs_root.iterdir() if item.is_dir()), key=lambda item: item.name.lower())
        if (candidate := _inspect_review_run_candidate(run_dir)) is not None
    ]
    return tuple(sorted(candidates, key=lambda item: (-item.score, item.run_id)))


def inspect_review_decisions_status(data_root: Path) -> ReviewDecisionsStatus:
    source = "nessuna run"
    run_id = ""
    decisions_path: Path | None = None
    session = _load_json_object(_active_review_session_path(data_root))
    if session is not None:
        source = "sessione attiva"
        run_id = str(session.get("selected_run_id", "")).strip()
        decisions_path = _review_decisions_path_from_session(data_root, session)
    else:
        candidates = inspect_review_run_candidates(data_root)
        if candidates:
            recommended = candidates[0]
            source = "run consigliata"
            run_id = recommended.run_id
            decisions_path = recommended.review_decisions_path

    decisions = _load_json_object(decisions_path) if decisions_path is not None else None
    decision_items = _decision_items(decisions)
    selected_actions: Counter[str] = Counter()
    decision_statuses: Counter[str] = Counter()
    subject_kinds: Counter[str] = Counter()
    for decision in decision_items:
        selected_actions[_status_value(decision.get("selected_action"))] += 1
        decision_statuses[_status_value(decision.get("decision_status"))] += 1
        subject_kinds[_status_value(decision.get("subject_kind"))] += 1

    return ReviewDecisionsStatus(
        data_root=data_root,
        source=source,
        run_id=run_id,
        decisions_path=decisions_path,
        decisions_available=decisions is not None,
        decision_count=len(decision_items),
        historical_decision_count=sum(1 for decision in decision_items if _is_substantive_decision(decision)),
        selected_actions=_sorted_counts(selected_actions),
        decision_statuses=_sorted_counts(decision_statuses),
        subject_kinds=_sorted_counts(subject_kinds),
    )


def inspect_consolidate_run_candidates(data_root: Path) -> tuple[ConsolidateRunCandidate, ...]:
    runs_root = data_root / "risultati" / "runs"
    if not runs_root.is_dir():
        return ()
    candidates = [
        candidate
        for run_dir in sorted((item for item in runs_root.iterdir() if item.is_dir()), key=lambda item: item.name.lower())
        if (candidate := _inspect_consolidate_run_candidate(run_dir)) is not None
    ]
    return tuple(sorted(candidates, key=lambda item: (-item.score, item.run_id)))


def inspect_sources_online(data_root: Path, *, limit: int) -> SourcesOnlineDiscovery:
    registry_path = _sources_registry_path(data_root)
    registry = _load_yaml_object(registry_path)
    enabled_sources = _string_list(registry.get("enabled_sources") if registry else None)
    sources = registry.get("sources") if registry else None
    source_ids = _source_ids(sources)
    candidate_source_ids = enabled_sources or source_ids
    profiles_index_path = data_root / DEFAULT_PROFILES_INDEX
    profile_count = _profile_index_count(profiles_index_path)
    return SourcesOnlineDiscovery(
        data_root=data_root,
        registry_path=registry_path,
        registry_exists=registry is not None,
        enabled_source_count=len(enabled_sources),
        source_definition_count=len(source_ids),
        candidate_source_ids=tuple(candidate_source_ids[:limit]),
        profiles_index_path=profiles_index_path,
        profiles_index_exists=profiles_index_path.is_file(),
        profile_count=profile_count,
    )


def inspect_mvp_demo_status(data_root: Path) -> MvpDemoStatus:
    return MvpDemoStatus(
        data_root=data_root,
        descriptor_status=inspect_mvp_demo_descriptor(data_root),
        profiles_status=inspect_profiles_status(data_root),
        review_candidates=inspect_review_run_candidates(data_root),
        review_session_available=_active_review_session_path(data_root).is_file(),
        review_decisions_status=inspect_review_decisions_status(data_root),
        consolidate_candidates=inspect_consolidate_run_candidates(data_root),
        consolidate_session_available=_active_consolidate_session_path(data_root).is_file(),
        sources_online=inspect_sources_online(data_root, limit=3),
        offline_intake=inspect_inventory_section(data_root, "documenti_da_processare"),
        offline_processed=inspect_inventory_section(data_root, "documenti_processati"),
    )


def inspect_mvp_demo_descriptor(data_root: Path, descriptor_path: Path | None = None) -> MvpDemoDescriptorStatus:
    path = descriptor_path or data_root / DEFAULT_MVP_DEMO_DESCRIPTOR
    payload = _load_json_object(path)
    run_dir = _descriptor_run_dir(data_root, payload)
    artifacts = _descriptor_artifacts(payload)
    return MvpDemoDescriptorStatus(
        data_root=data_root,
        descriptor_path=path,
        exists=path.is_file(),
        valid_json=payload is not None,
        contract_version=str(payload.get("contract_version", "")).strip() if payload else "",
        status=str(payload.get("status", "")).strip() if payload else "",
        preview_only=_bool_or_none(payload.get("preview_only")) if payload else None,
        publication_status=str(payload.get("publication_status", "")).strip() if payload else "",
        run_id=str(payload.get("run_id", "")).strip() if payload else "",
        run_dir=run_dir,
        run_dir_exists=run_dir.is_dir() if run_dir is not None else False,
        primary_profile_ids=tuple(_string_list(payload.get("primary_profile_ids") if payload else None)),
        contrast_profile_ids=tuple(_string_list(payload.get("contrast_profile_ids") if payload else None)),
        source_document_ids=tuple(_string_list(payload.get("source_document_ids") if payload else None)),
        source_families=tuple(_string_list(payload.get("source_families") if payload else None)),
        artifact_paths=artifacts,
        safety_flags=_descriptor_safety_flags(payload),
    )


def _inspect_review_run_candidate(run_dir: Path) -> ReviewRunCandidate | None:
    review_dir = run_dir / "historian_review"
    session_path = review_dir / "review_session.json"
    queue_path = review_dir / "review_queue.json"
    decisions_path = review_dir / "review_decisions_summary.json"
    ledger_path = run_dir / "mvp_consolidated_review_ledger.json"

    if not any(path.is_file() for path in (session_path, queue_path, decisions_path, ledger_path)):
        return None

    session = _load_json_object(session_path)
    queue = _load_json_object(queue_path)
    decisions = _load_json_object(decisions_path)
    ledger = _load_json_object(ledger_path)

    queue_count = _list_count(queue, ("items", "review_items"))
    decision_items = _decision_items(decisions)
    decision_count = len(decision_items)
    historical_decision_count = sum(1 for decision in decision_items if _is_substantive_decision(decision))
    profile_count = _list_count(ledger, ("profiles", "profile_records", "records"))
    session_item_count = _list_count(session, ("items", "worklist", "focus_items"))

    score = 0
    if session is not None:
        score += 30
    if queue is not None:
        score += 20
    if decisions is not None:
        score += 20
    if ledger is not None:
        score += 15
    score += min(queue_count, 20)
    score += min(historical_decision_count, 10) * 2
    score += min(profile_count, 10)
    score += min(session_item_count, 10)

    reasons = []
    if session is not None:
        reasons.append("review_session")
    if queue is not None:
        reasons.append("review_queue")
    if decisions is not None:
        reasons.append("decisioni")
    if ledger is not None:
        reasons.append("ledger")

    return ReviewRunCandidate(
        run_id=run_dir.name,
        run_dir=run_dir,
        score=score,
        profile_count=profile_count,
        review_queue_count=queue_count,
        decision_count=decision_count,
        historical_decision_count=historical_decision_count,
        session_item_count=session_item_count,
        reason=" + ".join(reasons) if reasons else "artefatti review parziali",
        review_session_path=session_path,
        review_queue_path=queue_path,
        review_decisions_path=decisions_path,
        ledger_path=ledger_path,
    )


def _inspect_consolidate_run_candidate(run_dir: Path) -> ConsolidateRunCandidate | None:
    review_dir = run_dir / "historian_review"
    ledger_path = run_dir / "mvp_consolidated_review_ledger.json"
    queue_path = review_dir / "review_queue.json"
    session_path = review_dir / "review_session.json"
    decisions_path = review_dir / "review_decisions_summary.json"

    if not any(path.is_file() for path in (ledger_path, queue_path, session_path, decisions_path)):
        return None

    ledger = _load_json_object(ledger_path)
    decisions = _load_json_object(decisions_path)
    profile_count = _list_count(ledger, ("profiles", "profile_records", "records"))
    decision_count = len(_decision_items(decisions))

    score = 0
    if ledger is not None:
        score += 40 + min(profile_count, 20)
    if decisions is not None:
        score += 20 + min(decision_count, 20)
    if session_path.is_file():
        score += 15
    if queue_path.is_file():
        score += 10

    reasons = []
    if ledger is not None:
        reasons.append("ledger_json_available")
    if decisions is not None:
        reasons.append("decisioni")
    if session_path.is_file():
        reasons.append("review_session")
    if queue_path.is_file():
        reasons.append("review_queue")

    return ConsolidateRunCandidate(
        run_id=run_dir.name,
        run_dir=run_dir,
        score=score,
        ledger_available=ledger is not None,
        review_queue_available=queue_path.is_file(),
        review_session_available=session_path.is_file(),
        decision_summary_available=decisions is not None,
        profile_count=profile_count,
        decision_count=decision_count,
        reason=" + ".join(reasons) if reasons else "artefatti consolidate parziali",
        ledger_path=ledger_path,
        review_queue_path=queue_path,
        review_session_path=session_path,
        review_decisions_path=decisions_path,
    )


def _project_root(start_dir: Path) -> Path:
    start_dir = start_dir.resolve()
    return start_dir.parent if start_dir.name == "memoria-engine" else start_dir


def _print_status_line(label: str, ok: bool) -> None:
    status = "OK" if ok else "MISSING"
    print(f"{status} {label}")


def _inventory_sections(section: str) -> tuple[str, ...]:
    if section == "all":
        return INVENTORY_SECTIONS
    return (section,)


def _print_inventory_text(resolution: DataRootResolution, inventories: list[SectionInventory]) -> None:
    print(f"Data root: {resolution.path}")
    print(f"Source: {resolution.source}")
    for inventory in inventories:
        print("")
        print(f"Section: {inventory.name}")
        print(f"Path: {inventory.path}")
        print(f"exists: {str(inventory.exists).lower()}")
        print(f"top_level_files: {inventory.top_level_files}")
        print(f"top_level_dirs: {inventory.top_level_dirs}")
        print("entries:")
        if inventory.names:
            for name in inventory.names:
                print(f"- {name}")
        else:
            print("- none")


def _print_inventory_markdown(resolution: DataRootResolution, inventories: list[SectionInventory]) -> None:
    print("# Memoria inventory")
    print("")
    print(f"- Data root: `{resolution.path}`")
    print(f"- Source: `{resolution.source}`")
    for inventory in inventories:
        print("")
        print(f"## {inventory.name}")
        print("")
        print(f"- Path: `{inventory.path}`")
        print(f"- Exists: {'yes' if inventory.exists else 'no'}")
        print(f"- Top-level files: {inventory.top_level_files}")
        print(f"- Top-level directories: {inventory.top_level_dirs}")
        print("")
        print("### Entries")
        print("")
        if inventory.names:
            for name in inventory.names:
                print(f"- `{name}`")
        else:
            print("- none")


def _print_profiles_status_text(resolution: DataRootResolution, status: ProfilesStatus) -> None:
    print(f"Data root: {resolution.path}")
    print(f"Source: {resolution.source}")
    print(f"Profiles index: {status.index_path}")
    print(f"exists: {str(status.index_exists).lower()}")
    print(f"index_profiles: {status.index_count}")
    print(f"loaded_profiles: {status.loaded_profiles}")
    print(f"missing_profile_files: {len(status.missing_profile_files)}")
    _print_count_block("profile_status", status.profile_statuses)
    _print_count_block("review_status", status.review_statuses)
    _print_count_block("publication_status", status.publication_statuses)
    if status.missing_profile_files:
        print("missing_files:")
        for file_name in status.missing_profile_files:
            print(f"- {file_name}")


def _print_profiles_status_markdown(resolution: DataRootResolution, status: ProfilesStatus) -> None:
    print("# Memoria profiles status")
    print("")
    print(f"- Data root: `{resolution.path}`")
    print(f"- Source: `{resolution.source}`")
    print(f"- Profiles index: `{status.index_path}`")
    print(f"- Exists: {'yes' if status.index_exists else 'no'}")
    print(f"- Index profiles: {status.index_count}")
    print(f"- Loaded profiles: {status.loaded_profiles}")
    print(f"- Missing profile files: {len(status.missing_profile_files)}")
    print("")
    _print_count_markdown("Profile status", status.profile_statuses)
    _print_count_markdown("Review status", status.review_statuses)
    _print_count_markdown("Publication status", status.publication_statuses)
    if status.missing_profile_files:
        print("## Missing files")
        print("")
        for file_name in status.missing_profile_files:
            print(f"- `{file_name}`")


def _print_required_dirs_markdown(resolution: DataRootResolution, checks: list[tuple[str, bool]]) -> None:
    print("# Memoria inventory")
    print("")
    print(f"- Data root: `{resolution.path}`")
    print(f"- Source: `{resolution.source}`")
    print("")
    print("## Required folders")
    print("")
    for name, ok in checks:
        print(f"- [{'x' if ok else ' '}] `{name}`")


def _command_data_root(args: argparse.Namespace) -> int:
    try:
        resolution = resolve_data_root(explicit_data_root=args.data_root)
    except DataRootResolutionError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    exists = resolution.path.is_dir()
    print(str(resolution.path))
    print(f"source: {resolution.source}")
    print(f"exists: {str(exists).lower()}")
    if not exists:
        print(f"ERROR Data root non trovato: {resolution.path}", file=sys.stderr)
        return 1
    return 0


def _command_inventory(args: argparse.Namespace) -> int:
    try:
        resolution = resolve_data_root(explicit_data_root=args.data_root)
    except DataRootResolutionError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    if not resolution.path.is_dir():
        print(f"Data root: {resolution.path}")
        print(f"Source: {resolution.source}")
        print(f"ERROR Data root non trovato: {resolution.path}", file=sys.stderr)
        return 1

    if args.section:
        inventories = [inspect_inventory_section(resolution.path, section) for section in _inventory_sections(args.section)]
        if args.output == "markdown":
            _print_inventory_markdown(resolution, inventories)
        else:
            _print_inventory_text(resolution, inventories)
        return 0 if all(inventory.exists for inventory in inventories) else 1

    print(f"Data root: {resolution.path}")
    print(f"Source: {resolution.source}")
    checks = inspect_required_dirs(resolution.path)
    if args.output == "markdown":
        _print_required_dirs_markdown(resolution, checks)
        return 0 if all(ok for _, ok in checks) else 1

    for name, ok in checks:
        _print_status_line(name, ok)
    return 0 if all(ok for _, ok in checks) else 1


def _command_doctor(args: argparse.Namespace) -> int:
    try:
        resolution = resolve_data_root(explicit_data_root=args.data_root)
    except DataRootResolutionError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    print("Me.Mo.Ri.A doctor")
    print(f"Data root: {resolution.path}")
    print(f"Data root source: {resolution.source}")
    data_root_storage = LocalWorkspaceStorage(resolution.path)
    data_root_ok = data_root_storage.stat(".").is_dir
    _print_status_line("data-root", data_root_ok)

    print("")
    print("Data root folders:")
    dir_checks = (
        inspect_required_dirs(resolution.path, data_root_storage)
        if data_root_ok
        else [(name, False) for name in REQUIRED_DATA_ROOT_DIRS]
    )
    for name, ok in dir_checks:
        _print_status_line(name, ok)

    project_root = _project_root(Path.cwd())
    print("")
    print(f"Sibling repositories: {project_root}")
    sibling_checks = inspect_sibling_repositories(project_root, LocalWorkspaceStorage(project_root))
    for name, ok in sibling_checks:
        _print_status_line(name, ok)

    return 0 if data_root_ok and all(ok for _, ok in dir_checks) and all(ok for _, ok in sibling_checks) else 1


def _command_profiles_status(args: argparse.Namespace) -> int:
    try:
        resolution = resolve_data_root(explicit_data_root=args.data_root)
    except DataRootResolutionError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    if not resolution.path.is_dir():
        print(f"Data root: {resolution.path}")
        print(f"Source: {resolution.source}")
        print(f"ERROR Data root non trovato: {resolution.path}", file=sys.stderr)
        return 1

    explicit_index = Path(args.profiles_index).expanduser().resolve() if args.profiles_index.strip() else None
    status = inspect_profiles_status(resolution.path, explicit_index)
    if args.output == "markdown":
        _print_profiles_status_markdown(resolution, status)
    else:
        _print_profiles_status_text(resolution, status)

    if not status.index_exists:
        print(f"ERROR Indice profili non trovato: {status.index_path}", file=sys.stderr)
        return 1
    if status.missing_profile_files:
        return 1
    return 0


def _command_review_discover(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    _print_review_discovery(resolution, limit=args.limit)
    return 0


def _command_review_status(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    session_path = _active_review_session_path(resolution.path)
    session = _load_json_object(session_path)
    if session is None:
        _print_review_discovery(resolution, limit=args.limit)
        return 0

    print("Me.Mo.Ria review status")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    print(f"Run attiva: {session.get('selected_run_id', '')}")
    worklist = _list_items(session.get("worklist"))
    total_count = _int_value(session.get("worklist_item_count"), len(worklist))
    decided_count = sum(1 for item in worklist if _is_decided_work_item(item))
    pending_count = max(total_count - decided_count, 0)
    print(f"Worklist item: {total_count}")
    print(f"Decisioni sessione: {decided_count}/{total_count}")
    print(f"Pendenti: {pending_count}")
    last_item_id = str(session.get("last_decision_item_id", "")).strip()
    if last_item_id:
        print(
            "Ultima decisione: "
            f"[{session.get('last_decision_item_number', '')}] {last_item_id} -> {session.get('last_selected_action', '')}"
        )
    print(f"Sessione: {session_path}")
    print(f"Review session JSON: {session.get('review_session_json', '')}")
    dashboard = _review_dashboard_paths(session)
    if dashboard is None:
        print("Dashboard: non verificabile dalla sessione attiva")
    elif dashboard["json"].is_file() or dashboard["markdown"].is_file():
        print("Dashboard: disponibile")
        print(f"  JSON: {dashboard['json']}")
        print(f"  Markdown: {dashboard['markdown']}")
    else:
        print("Dashboard: non generata")
    print("")
    print("Prossimo comando:")
    print(f'  memoria review work --data-root "{resolution.path}"')
    return 0


def _command_review_work(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    session_path = _active_review_session_path(resolution.path)
    session = _load_json_object(session_path)
    if session is None:
        print("Nessuna sessione review attiva.")
        print("Avviare prima con PowerShell:")
        print(f'  .\\scripts\\memoria.ps1 review start --auto -WorkspaceRoot "{resolution.path}"')
        return 0

    print("Me.Mo.Ria review work")
    print(f"Run attiva: {session.get('selected_run_id', '')}")
    print("Modalita: preview-only/read-only")
    print("")
    worklist = _list_items(session.get("worklist"))
    if not worklist:
        print("La sessione attiva non contiene item numerabili.")
        print(f"Aprire: {session.get('review_session_json', '')}")
        return 0
    for item in worklist[: args.limit]:
        display_number = item.get("display_number", "")
        print(
            f"[{display_number}] {item.get('profile_label', '')} | "
            f"{item.get('subject_kind', '')} | {item.get('decision_status', '')}"
        )
        print(f"    Item: {item.get('item_id', '')}")
        print(f"    Documento: {item.get('source_document_id', '')}")
        raw_file = str(item.get("raw_file", "")).strip()
        metadata_file = str(item.get("metadata_file", "")).strip()
        if raw_file:
            print(f"    File sorgente: {raw_file}")
        if metadata_file:
            print(f"    Metadata: {metadata_file}")
        print(f"    Domanda: {item.get('question', '')}")
        print(f"    Comando decisionale PowerShell: .\\scripts\\memoria.ps1 review accept {display_number}")
        print(f"    Alternative: review reject {display_number} | review uncertain {display_number}")
    print("")
    print("Nota: comando Python read-only; non applica decisioni.")
    return 0


def _command_review_decisions(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    status = inspect_review_decisions_status(resolution.path)
    print("Me.Mo.Ria review decisions")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    print(f"Origine: {status.source}")
    print(f"Run: {status.run_id or 'non selezionata'}")
    print(f"Decision summary: {status.decisions_path if status.decisions_path is not None else 'non disponibile'}")
    print(f"Presente: {str(status.decisions_available).lower()}")
    print(f"Decisioni totali: {status.decision_count}")
    print(f"Decisioni storiche sostanziali: {status.historical_decision_count}")
    _print_count_block("selected_action", status.selected_actions)
    _print_count_block("decision_status", status.decision_statuses)
    _print_count_block("subject_kind", status.subject_kinds)
    print("")
    print("Nota: comando Python read-only; non registra decisioni e non modifica profili o store.")
    return 0


def _command_mvp_status(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    status = inspect_mvp_demo_status(resolution.path)
    print("Me.Mo.Ria MVP demo status")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    print("Golden run:")
    print(f"  Descriptor presente: {str(status.descriptor_status.exists).lower()}")
    print(f"  Descriptor JSON valido: {str(status.descriptor_status.valid_json).lower()}")
    print(f"  Status: {status.descriptor_status.status or 'missing'}")
    print(f"  Run canonica: {status.descriptor_status.run_id or 'missing'}")
    print(f"  Run dir presente: {str(status.descriptor_status.run_dir_exists).lower()}")
    print(f"  Artefatti dichiarati: {len(status.descriptor_status.artifact_paths)}")
    print(f"  Artefatti presenti: {sum(1 for _, _, exists in status.descriptor_status.artifact_paths if exists)}")
    preview_only = status.descriptor_status.preview_only
    print(f"  Preview-only: {_format_optional_bool(preview_only)}")
    publication_ready = dict(status.descriptor_status.safety_flags).get("publication_ready")
    if publication_ready is not None:
        print(f"  Publication ready: {str(publication_ready).lower()}")
    print(f"  Publication status: {status.descriptor_status.publication_status or 'missing'}")
    print("Profili:")
    print(f"  Indice presente: {str(status.profiles_status.index_exists).lower()}")
    print(f"  Profili caricati: {status.profiles_status.loaded_profiles}/{status.profiles_status.index_count}")
    print(f"  File profilo mancanti: {len(status.profiles_status.missing_profile_files)}")
    print("Review:")
    print(f"  Run candidate: {len(status.review_candidates)}")
    print(f"  Sessione attiva: {str(status.review_session_available).lower()}")
    print(f"  Decisioni: {status.review_decisions_status.decision_count}")
    print(f"  Decisioni storiche sostanziali: {status.review_decisions_status.historical_decision_count}")
    print("Consolidamento:")
    print(f"  Run candidate: {len(status.consolidate_candidates)}")
    print(f"  Sessione attiva: {str(status.consolidate_session_available).lower()}")
    active_consolidate_profiles = _active_consolidate_profile_count(resolution.path)
    if active_consolidate_profiles is not None:
        print(f"  Profili ledger attivo: {active_consolidate_profiles}")
    elif status.consolidate_candidates:
        print(f"  Profili ledger consigliato: {status.consolidate_candidates[0].profile_count}")
    else:
        print("  Profili ledger consigliato: 0")
    print("Fonti:")
    print(f"  Registry online presente: {str(status.sources_online.registry_exists).lower()}")
    print(f"  Fonti online abilitate: {status.sources_online.enabled_source_count}")
    print(f"  Profili candidati fonti: {status.sources_online.profile_count}")
    print(
        "  Offline intake: "
        f"{status.offline_intake.top_level_dirs} cartelle, {status.offline_intake.top_level_files} file"
    )
    print(
        "  Offline processati: "
        f"{status.offline_processed.top_level_dirs} cartelle, {status.offline_processed.top_level_files} file"
    )
    print("")
    print("Walkthrough read-only:")
    print(f'  memoria mvp demo --data-root "{resolution.path}"')
    print(f'  memoria mvp demo-build --data-root "{resolution.path}" --run-id <canonical-run-id>')
    print(f'  memoria profiles status --data-root "{resolution.path}"')
    print(f'  memoria review discover --data-root "{resolution.path}"')
    print(f'  memoria review status --data-root "{resolution.path}"')
    print(f'  memoria review work --data-root "{resolution.path}"')
    print(f'  memoria review decisions --data-root "{resolution.path}"')
    print(f'  memoria consolidate status --data-root "{resolution.path}"')
    print(f'  memoria sources online status --data-root "{resolution.path}"')
    print(f'  memoria sources offline status --data-root "{resolution.path}"')
    print("")
    print("Nota: comando Python read-only; non genera report, non crea run e non modifica il data root.")
    return 0


def _command_mvp_demo(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    explicit_descriptor = Path(args.descriptor).expanduser().resolve() if args.descriptor.strip() else None
    status = inspect_mvp_demo_descriptor(resolution.path, explicit_descriptor)
    print("Me.Mo.Ria MVP demo descriptor")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    print(f"Descriptor: {status.descriptor_path}")
    print(f"Presente: {str(status.exists).lower()}")
    print(f"JSON valido: {str(status.valid_json).lower()}")
    if not status.exists:
        print("")
        print("Descriptor non ancora creato.")
        print("Path atteso T30:")
        print(f"  {resolution.path / DEFAULT_MVP_DEMO_DESCRIPTOR}")
        print("")
        print("Nota: comando Python read-only; non crea il descrittore e non modifica il data root.")
        return 1
    if not status.valid_json:
        print("ERROR Descriptor presente ma non leggibile come oggetto JSON.", file=sys.stderr)
        return 1

    print(f"Contract version: {status.contract_version or 'missing'}")
    print(f"Status: {status.status or 'missing'}")
    print(f"Preview-only: {_format_optional_bool(status.preview_only)}")
    print(f"Publication status: {status.publication_status or 'missing'}")
    print(f"Run: {status.run_id or 'missing'}")
    print(f"Run dir: {status.run_dir if status.run_dir is not None else 'missing'}")
    print(f"Run dir presente: {str(status.run_dir_exists).lower()}")
    print(f"Profili principali: {len(status.primary_profile_ids)}")
    for profile_id in status.primary_profile_ids:
        print(f"- {profile_id}")
    print(f"Profili contrasto: {len(status.contrast_profile_ids)}")
    for profile_id in status.contrast_profile_ids:
        print(f"- {profile_id}")
    print(f"Documenti sorgente: {len(status.source_document_ids)}")
    for document_id in status.source_document_ids:
        print(f"- {document_id}")
    print(f"Famiglie fonte: {', '.join(status.source_families) if status.source_families else 'none'}")
    print("Artefatti:")
    if status.artifact_paths:
        for name, path_text, exists in status.artifact_paths:
            print(f"- {name}: {path_text or 'missing'} | presente={str(exists).lower()}")
    else:
        print("- none")
    print("Safety:")
    if status.safety_flags:
        for name, value in status.safety_flags:
            print(f"- {name}: {str(value).lower()}")
    else:
        print("- none")
    print("")
    print("Nota: comando Python read-only; non crea run, non rigenera artefatti e non modifica il data root.")
    return 0


def _command_mvp_demo_build(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    output_descriptor = Path(args.output_descriptor).expanduser().resolve() if args.output_descriptor.strip() else None
    output_reconciliation = (
        Path(args.output_reconciliation).expanduser().resolve() if args.output_reconciliation.strip() else None
    )
    output_aligned_ledger = Path(args.output_aligned_ledger).expanduser().resolve() if args.output_aligned_ledger.strip() else None
    build_kwargs = {
        "data_root": resolution.path,
        "run_id": args.run_id,
        "primary_profile_id": args.primary_profile_id,
        "contrast_profile_id": args.contrast_profile_id,
        "source_document_id": args.source_document_id,
        "ledger_json": Path(args.ledger).expanduser().resolve() if args.ledger.strip() else None,
        "review_queue_json": Path(args.review_queue).expanduser().resolve() if args.review_queue.strip() else None,
        "review_decisions_summary_json": (
            Path(args.review_decisions_summary).expanduser().resolve() if args.review_decisions_summary.strip() else None
        ),
        "verified_facts_preview_json": (
            Path(args.verified_facts_preview).expanduser().resolve() if args.verified_facts_preview.strip() else None
        ),
        "profile_patch_preview_json": (
            Path(args.profile_patch_preview).expanduser().resolve() if args.profile_patch_preview.strip() else None
        ),
        "readiness_report_json": (
            Path(args.readiness_report).expanduser().resolve() if args.readiness_report.strip() else None
        ),
    }
    aligned_ledger_label = output_aligned_ledger if output_aligned_ledger is not None else "skipped"
    if output_aligned_ledger is not None:
        try:
            build_mvp_demo_aligned_ledger(
                data_root=resolution.path,
                run_id=args.run_id,
                primary_profile_id=args.primary_profile_id,
                contrast_profile_id=args.contrast_profile_id,
                source_document_id=args.source_document_id,
                ledger_json=build_kwargs["ledger_json"],
                output_json=output_aligned_ledger,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR {exc}", file=sys.stderr)
            return 1
        build_kwargs["ledger_json"] = output_aligned_ledger
    try:
        descriptor = build_mvp_demo_descriptor(**build_kwargs)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1

    reconciliation = descriptor.get("reconciliation", {}) if isinstance(descriptor.get("reconciliation"), dict) else {}
    review = descriptor.get("review", {}) if isinstance(descriptor.get("review"), dict) else {}
    readiness = descriptor.get("readiness", {}) if isinstance(descriptor.get("readiness"), dict) else {}
    readiness_status = str(readiness.get("status", "unknown"))
    is_ready = readiness_status == "ready_for_internal_demo"
    if is_ready and (output_descriptor is not None or output_reconciliation is not None):
        descriptor = build_mvp_demo_descriptor(
            **build_kwargs,
            output_json=output_descriptor,
            output_reconciliation_md=output_reconciliation,
        )
        reconciliation = descriptor.get("reconciliation", {}) if isinstance(descriptor.get("reconciliation"), dict) else {}
        review = descriptor.get("review", {}) if isinstance(descriptor.get("review"), dict) else {}
        readiness = descriptor.get("readiness", {}) if isinstance(descriptor.get("readiness"), dict) else {}
    descriptor_output_label = output_descriptor if output_descriptor is not None else "skipped"
    reconciliation_output_label = output_reconciliation if output_reconciliation is not None else "skipped"
    if not is_ready:
        if output_descriptor is not None:
            descriptor_output_label = f"{output_descriptor} (blocked, not written)"
        if output_reconciliation is not None:
            reconciliation_output_label = f"{output_reconciliation} (blocked, not written)"
    compatibility_counts = reconciliation.get("compatibility_counts", {})
    print("Me.Mo.Ria MVP demo descriptor build")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only")
    print("")
    print(f"Run: {descriptor.get('run_id', '')}")
    print(f"Run dir: {descriptor.get('run_dir', '')}")
    print(f"Aligned ledger output: {aligned_ledger_label}")
    print(f"Descriptor output: {descriptor_output_label}")
    print(f"Reconciliation output: {reconciliation_output_label}")
    print(f"Profili principali: {len(descriptor.get('primary_profile_ids', []))}")
    print(f"Profili contrasto: {len(descriptor.get('contrast_profile_ids', []))}")
    print(f"Documenti sorgente: {len(descriptor.get('source_document_ids', []))}")
    print(f"Famiglie coperte nel descriptor: {', '.join(descriptor.get('source_families', [])) or 'none'}")
    print(f"Readiness: {readiness_status}")
    print(f"Readiness errors: {readiness.get('error_count', 0)}")
    for error in readiness.get("errors", []):
        print(f"- ERROR {error}")
    print(f"Readiness warnings: {readiness.get('warning_count', 0)}")
    for warning in readiness.get("warnings", []):
        print(f"- WARNING {warning}")
    print("Azioni successive:")
    for action in readiness.get("next_actions", []):
        print(f"- {action}")
    print(f"Famiglie selezionate: {', '.join(readiness.get('selected_source_families', [])) or 'none'}")
    print(f"Famiglie coperte: {', '.join(readiness.get('covered_source_families', [])) or 'none'}")
    print(f"Famiglie mancanti: {', '.join(readiness.get('missing_source_families', [])) or 'none'}")
    print(f"Documenti coperti: {readiness.get('covered_document_count', 0)}/{readiness.get('selected_document_count', 0)}")
    print("Diagnostica famiglie:")
    for item in readiness.get("source_family_diagnostics", []):
        if not isinstance(item, dict):
            continue
        print(
            "- FAMILY_STATUS "
            f"{item.get('source_family', '')} | "
            f"coverage={item.get('coverage_status', '')} | "
            f"blocked_by={item.get('blocking_reason', '')} | "
            f"selected_documents={item.get('selected_document_count', 0)} | "
            f"covered_documents={item.get('covered_document_count', 0)} | "
            f"missing_documents={item.get('missing_document_count', 0)}"
        )
    print("Diagnostica documenti:")
    for item in readiness.get("document_diagnostics", []):
        if not isinstance(item, dict):
            continue
        print(
            "- DOCUMENT_STATUS "
            f"{item.get('source_document_id', '')} | "
            f"family={item.get('source_family', '')} | "
            f"reconciliation={item.get('reconciliation_status', '')} | "
            f"profile_scope={item.get('profile_scope_status', '')} | "
            f"claims={item.get('candidate_claim_status', '')} | "
            f"blocked_by={item.get('blocking_reason', '')}"
        )
    print("Piano riallineamento preview:")
    alignment_plan = readiness.get("alignment_plan", [])
    if isinstance(alignment_plan, list) and alignment_plan:
        for item in alignment_plan:
            if not isinstance(item, dict):
                continue
            print(
                "- ALIGNMENT_STEP "
                f"{item.get('step', '')} | "
                f"action={item.get('action', '')} | "
                f"document={item.get('source_document_id', '')} | "
                f"family={item.get('source_family', '')} | "
                f"reason={item.get('reason', '')}"
            )
    else:
        print("- none")
    for document_id in readiness.get("covered_source_document_ids", []):
        print(f"- COVERED_DOCUMENT {document_id}")
    for document_id in readiness.get("missing_source_document_ids", []):
        print(f"- MISSING_DOCUMENT {document_id}")
    for document_id in readiness.get("missing_documents_present_in_selected_profiles", []):
        print(f"- MISSING_DOCUMENT_PRESENT_IN_SELECTED_PROFILES {document_id}")
    for document_id in readiness.get("missing_documents_absent_from_selected_profiles", []):
        print(f"- MISSING_DOCUMENT_ABSENT_FROM_SELECTED_PROFILES {document_id}")
    for document_id in readiness.get("missing_documents_without_candidate_claims", []):
        print(f"- MISSING_DOCUMENT_WITHOUT_CANDIDATE_CLAIMS {document_id}")
    for document_id in readiness.get("missing_documents_with_claims_outside_selected_profiles", []):
        print(f"- MISSING_DOCUMENT_WITH_CLAIMS_OUTSIDE_SELECTED_PROFILES {document_id}")
    print(f"Righe riconciliazione: {reconciliation.get('row_count', 0)}")
    print("Compatibilita:")
    if isinstance(compatibility_counts, dict) and compatibility_counts:
        for name in sorted(str(key) for key in compatibility_counts):
            print(f"- {name}: {compatibility_counts.get(name)}")
    else:
        print("- none: 0")
    print(f"Decisioni sostanziali: {review.get('substantive_decision_count', 0)}")
    print(f"Verified facts preview: {review.get('verified_fact_preview_count', 0)}")
    print(f"ProfilePatch preview: {review.get('profile_patch_preview_count', 0)}")
    print("")
    if not is_ready:
        print("Nota: readiness bloccata; nessun output e' stato scritto, anche se richiesto.")
        return 1
    print("Nota: non crea run, non applica decisioni, non applica ProfilePatch e scrive solo sugli output espliciti.")
    return 0


def _command_consolidate_discover(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    _print_consolidate_discovery(resolution, limit=args.limit)
    return 0


def _command_consolidate_status(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    session_path = _active_consolidate_session_path(resolution.path)
    session = _load_json_object(session_path)
    if session is None:
        _print_consolidate_discovery(resolution, limit=args.limit)
        return 0
    descriptor_status = inspect_mvp_demo_descriptor(resolution.path)
    active_run_id = str(session.get("selected_run_id", "")).strip()

    print("Me.Mo.Ria consolidate status")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    print(f"Run attiva: {active_run_id}")
    print(f"Score: {session.get('discovery_score', '')}")
    print(f"Motivo: {session.get('discovery_reason', '')}")
    print(f"Sessione: {session_path}")
    print(f"Run dir: {session.get('selected_run_dir', '')}")
    print(f"Ledger: {session.get('selected_ledger_json', '')}")
    if descriptor_status.exists and descriptor_status.valid_json:
        print("Demo golden run:")
        print(f"  Run canonica: {descriptor_status.run_id or 'missing'}")
        print(f"  Status: {descriptor_status.status or 'missing'}")
        print(f"  Artefatti presenti: {sum(1 for _, _, exists in descriptor_status.artifact_paths if exists)}")
        if descriptor_status.run_id and descriptor_status.run_id != active_run_id:
            print("  Nota: la sessione consolidate attiva non coincide con la golden run demo.")
    print("")
    print("Prossimi comandi PowerShell preview:")
    print(f'  .\\scripts\\memoria.ps1 consolidate dry-run -WorkspaceRoot "{resolution.path}"')
    print(f'  .\\scripts\\memoria.ps1 consolidate run --preview -WorkspaceRoot "{resolution.path}"')
    print("")
    print("Nota: comando Python read-only; non rigenera ledger e non scrive nello store.")
    return 0


def _command_sources_online_discover(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    _print_sources_online_discovery(
        resolution,
        limit=args.limit,
        subject_kind=args.subject_kind,
        subject_id=args.subject_id,
        subject_label=args.subject_label,
        profile_id=args.profile_id,
    )
    return 0


def _command_sources_online_status(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    session_path = _active_sources_online_session_path(resolution.path)
    session = _load_json_object(session_path)
    if session is None:
        _print_sources_online_discovery(
            resolution,
            limit=args.limit,
            subject_kind=args.subject_kind,
            subject_id=args.subject_id,
            subject_label=args.subject_label,
            profile_id=args.profile_id,
        )
        return 0

    print("Me.Mo.Ria sources online status")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    print("Sessione sources online attiva:")
    print(f"  Path: {session_path}")
    print("  Stato: presente")
    subject = session.get("subject") if isinstance(session.get("subject"), dict) else {}
    candidate_query = session.get("candidate_query") if isinstance(session.get("candidate_query"), dict) else {}
    print(f"  Soggetto: {subject.get('kind', '')} {subject.get('id', '')}")
    print(f"  Etichetta: {subject.get('label', '')}")
    print(f"  Query seed candidata: {candidate_query.get('seed', '')}")
    print(f"  Intake proposto: {session.get('proposed_intake_path', '')}")
    print(f"  Preview-only: {session.get('preview_only', '')}")
    candidate_sources = _list_items(session.get("candidate_sources"))
    if candidate_sources:
        print("")
        print("Fonti candidate sessione:")
        for source in candidate_sources[: args.limit]:
            print(f"- {source.get('source_id', '')} | {source.get('status', '')}")
    print("")
    print("Nota: comando Python read-only; non avvia rete, browser, download, pipeline o import.")
    return 0


def _command_sources_offline_discover(args: argparse.Namespace) -> int:
    resolution = _resolve_existing_data_root_for_command(args)
    if resolution is None:
        return 1
    _print_sources_offline_discovery(resolution, limit=args.limit)
    return 0


def _command_sources_offline_status(args: argparse.Namespace) -> int:
    return _command_sources_offline_discover(args)


def _resolve_existing_data_root_for_command(args: argparse.Namespace) -> DataRootResolution | None:
    try:
        resolution = resolve_data_root(explicit_data_root=args.data_root)
    except DataRootResolutionError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return None
    if not resolution.path.is_dir():
        print(f"Data root: {resolution.path}")
        print(f"Source: {resolution.source}")
        print(f"ERROR Data root non trovato: {resolution.path}", file=sys.stderr)
        return None
    return resolution


def _print_review_discovery(resolution: DataRootResolution, *, limit: int) -> None:
    candidates = inspect_review_run_candidates(resolution.path)
    print("Me.Mo.Ria review discovery")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    if not candidates:
        print("Nessuna run review trovata in risultati/runs.")
        return
    recommended = candidates[0]
    print("Run consigliata:")
    print(f"[1] {recommended.run_id}")
    print(f"    Score: {recommended.score}")
    print(f"    Motivo: {recommended.reason}")
    print(f"    Review queue: {recommended.review_queue_count}")
    print(f"    Decisioni: {recommended.decision_count}")
    print(f"    Decisioni storiche sostanziali: {recommended.historical_decision_count}")
    print(f"    Profili ledger: {recommended.profile_count}")
    print(f"    Path: {recommended.run_dir}")
    print("")
    print("Candidate:")
    for index, candidate in enumerate(candidates[:limit], start=1):
        print(
            f"[{index}] {candidate.run_id} | score={candidate.score} | "
            f"queue={candidate.review_queue_count} | decisioni={candidate.decision_count} | motivo={candidate.reason}"
        )
    print("")
    print("Prossimi comandi:")
    print(f'  memoria review status --data-root "{resolution.path}"')
    print(f'  .\\scripts\\memoria.ps1 review start --auto -WorkspaceRoot "{resolution.path}"')


def _print_consolidate_discovery(resolution: DataRootResolution, *, limit: int) -> None:
    candidates = inspect_consolidate_run_candidates(resolution.path)
    print("Me.Mo.Ria consolidate discovery")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    if not candidates:
        print("Nessuna run consolidabile trovata in risultati/runs.")
        return
    recommended = candidates[0]
    print("Run consigliata:")
    print(f"[1] {recommended.run_id}")
    print(f"    Score: {recommended.score}")
    print(f"    Motivo: {recommended.reason}")
    print(f"    Ledger disponibile: {recommended.ledger_available}")
    print(f"    Profili ledger: {recommended.profile_count}")
    print(f"    Decisioni: {recommended.decision_count}")
    print(f"    Path: {recommended.run_dir}")
    print("")
    print("Candidate:")
    for index, candidate in enumerate(candidates[:limit], start=1):
        print(
            f"[{index}] {candidate.run_id} | score={candidate.score} | "
            f"ledger={candidate.ledger_available} | profili={candidate.profile_count} | "
            f"decisioni={candidate.decision_count} | motivo={candidate.reason}"
        )
    print("")
    print("Prossimi comandi:")
    print(f'  memoria consolidate status --data-root "{resolution.path}"')
    print(f'  .\\scripts\\memoria.ps1 consolidate start --auto -WorkspaceRoot "{resolution.path}"')
    print("")
    print("Nota: discovery read-only; non crea sessioni e non rigenera ledger.")


def _print_sources_online_discovery(
    resolution: DataRootResolution,
    *,
    limit: int,
    subject_kind: str,
    subject_id: str,
    subject_label: str,
    profile_id: str,
) -> None:
    discovery = inspect_sources_online(resolution.path, limit=limit)
    print("Me.Mo.Ria sources online discovery")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    print(f"Registry fonti: {discovery.registry_path if discovery.registry_exists else 'non trovato'}")
    print(f"  Presente: {discovery.registry_exists}")
    print(f"  Fonti abilitate: {discovery.enabled_source_count}")
    print(f"  Definizioni fonte: {discovery.source_definition_count}")
    print(
        "Indice profili pilota: "
        f"{discovery.profiles_index_path if discovery.profiles_index_exists else 'non trovato'}"
    )
    print(f"  Presente: {discovery.profiles_index_exists}")
    print(f"  Profili candidati: {discovery.profile_count}")
    if discovery.candidate_source_ids:
        print("")
        print("Fonti candidate:")
        for source_id in discovery.candidate_source_ids:
            print(f"- {source_id}")

    subject = _sources_subject_context(
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_label=subject_label,
        profile_id=profile_id,
    )
    if subject is not None:
        intake_path = resolution.path / "documenti_da_processare" / "sources_online" / subject["kind"] / subject["safe_id"]
        print("")
        print("Soggetto storico richiesto:")
        print(f"  Tipo: {subject['kind']}")
        print(f"  ID: {subject['id']}")
        print(f"  Etichetta: {subject['label']}")
        print(f"  Intake proposto: {intake_path}")
        print(f"  Query seed candidata: {subject['label']}")
        print("  Stato: fonte/evidenza candidata, non dato canonico")
    print("")
    print("Prossimo comando:")
    print(f'  .\\scripts\\memoria.ps1 sources online start --auto -WorkspaceRoot "{resolution.path}"')
    print("Nota: discovery read-only; non crea sessioni, non avvia rete, non scarica dati e non modifica profili JSON-LD.")


def _print_sources_offline_discovery(resolution: DataRootResolution, *, limit: int) -> None:
    intake = inspect_inventory_section(resolution.path, "documenti_da_processare")
    processed = inspect_inventory_section(resolution.path, "documenti_processati")
    print("Me.Mo.Ria sources offline discovery")
    print(f"Workspace: {resolution.path}")
    print("Modalita: preview-only/read-only")
    print("")
    print(f"Documenti da processare: {intake.path}")
    print(f"  Presente: {intake.exists}")
    print(f"  Cartelle candidate: {intake.top_level_dirs}")
    print(f"  File candidati: {intake.top_level_files}")
    print(f"Documenti processati: {processed.path}")
    print(f"  Presente: {processed.exists}")
    print(f"  Cartelle processate: {processed.top_level_dirs}")
    print(f"  File processati: {processed.top_level_files}")
    directories = [name for name in intake.names if name.endswith("/")][:limit]
    files = [name for name in intake.names if not name.endswith("/")][:limit]
    if directories:
        print("")
        print("Cartelle candidate:")
        for name in directories:
            print(f"- {name.rstrip('/')}")
    if files:
        print("")
        print("File candidati:")
        for name in files:
            print(f"- {name}")
    print("")
    print("Prossimo comando:")
    print(f'  .\\scripts\\memoria.ps1 sources offline start --auto -WorkspaceRoot "{resolution.path}"')
    print("Nota: discovery read-only; non crea run, non avvia OCR, non scrive nello store e non modifica profili JSON-LD.")


def _load_json_object(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_yaml_object(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    return payload if isinstance(payload, dict) else None


def _descriptor_run_dir(data_root: Path, payload: dict[str, object] | None) -> Path | None:
    if payload is None:
        return None
    run_dir_text = str(payload.get("run_dir", "")).strip()
    if run_dir_text:
        return Path(run_dir_text)
    run_id = str(payload.get("run_id", "")).strip()
    if run_id:
        return data_root / "risultati" / "runs" / run_id
    return None


def _descriptor_artifacts(payload: dict[str, object] | None) -> tuple[tuple[str, str, bool], ...]:
    if payload is None:
        return ()
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        return ()
    result: list[tuple[str, str, bool]] = []
    for name in sorted(str(key) for key in artifacts):
        path_text = str(artifacts.get(name, "")).strip()
        result.append((name, path_text, Path(path_text).is_file() if path_text else False))
    return tuple(result)


def _descriptor_safety_flags(payload: dict[str, object] | None) -> tuple[tuple[str, bool], ...]:
    if payload is None:
        return ()
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return ()
    result: list[tuple[str, bool]] = []
    for name in sorted(str(key) for key in safety):
        value = safety.get(name)
        if isinstance(value, bool):
            result.append((name, value))
    return tuple(result)


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _format_optional_bool(value: bool | None) -> str:
    if value is None:
        return "missing"
    return str(value).lower()


def _profile_index_count(path: Path) -> int:
    payload = _load_json_object(path)
    if payload is None:
        return 0
    return _list_count(payload, ("profiles",))


def _sources_registry_path(data_root: Path) -> Path:
    engine_root = Path(__file__).resolve().parents[2]
    candidates = (
        engine_root.parent / "memoria-sources" / "registry" / "camalanca_fonti.yaml",
        data_root / DEFAULT_SOURCES_REGISTRY,
        engine_root / DEFAULT_SOURCES_REGISTRY,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := str(item).strip())]


def _source_ids(value: object) -> list[str]:
    if isinstance(value, dict):
        return [text for key in value if (text := str(key).strip())]
    if isinstance(value, list):
        ids: list[str] = []
        for item in value:
            if isinstance(item, dict):
                source_id = str(item.get("id") or item.get("source_id") or item.get("@id") or "").strip()
                if source_id:
                    ids.append(source_id)
            else:
                source_id = str(item).strip()
                if source_id:
                    ids.append(source_id)
        return ids
    return []


def _list_count(payload: dict[str, object] | None, names: tuple[str, ...]) -> int:
    if payload is None:
        return 0
    for name in names:
        value = payload.get(name)
        if isinstance(value, list):
            return len(value)
        if value is not None:
            return 1
    return 0


def _decision_items(payload: dict[str, object] | None) -> list[dict[str, object]]:
    if payload is None:
        return []
    for name in ("decisions", "provided_decisions"):
        items = _list_items(payload.get(name))
        if items:
            return items
    return []


def _list_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _is_substantive_decision(decision: dict[str, object]) -> bool:
    return (
        bool(str(decision.get("profile_id", "")).strip())
        and bool(str(decision.get("source_document_id", "")).strip())
        and str(decision.get("subject_kind", "")).strip() != "workflow"
        and bool(str(decision.get("selected_action", "")).strip())
        and str(decision.get("selected_action", "")).strip() != "pending"
        and str(decision.get("decision_status", "")).strip() in {"accepted", "reviewed", "approved"}
    )


def _active_review_session_path(data_root: Path) -> Path:
    return data_root / "database" / "memoria_review_session.active.json"


def _active_consolidate_session_path(data_root: Path) -> Path:
    return data_root / "database" / "memoria_consolidate_session.active.json"


def _active_consolidate_profile_count(data_root: Path) -> int | None:
    session = _load_json_object(_active_consolidate_session_path(data_root))
    if session is None:
        return None
    ledger_path_text = str(session.get("selected_ledger_json", "")).strip()
    if not ledger_path_text:
        return 0
    return _list_count(_load_json_object(Path(ledger_path_text)), ("profiles", "profile_records", "records"))


def _review_decisions_path_from_session(data_root: Path, session: dict[str, object]) -> Path | None:
    for field_name in ("review_decisions_json", "review_decisions_summary_json"):
        path_text = str(session.get(field_name, "")).strip()
        if path_text:
            return Path(path_text)
    review_session_json = str(session.get("review_session_json", "")).strip()
    if review_session_json:
        return Path(review_session_json).parent / "review_decisions_summary.json"
    selected_run_id = str(session.get("selected_run_id", "")).strip()
    if selected_run_id:
        return data_root / "risultati" / "runs" / selected_run_id / "historian_review" / "review_decisions_summary.json"
    return None


def _active_sources_online_session_path(data_root: Path) -> Path:
    return data_root / "database" / "memoria_sources_online_session.active.json"


def _sources_subject_context(
    *,
    subject_kind: str,
    subject_id: str,
    subject_label: str,
    profile_id: str,
) -> dict[str, str] | None:
    kind = subject_kind.strip()
    item_id = subject_id.strip()
    label = subject_label.strip()
    if profile_id.strip() and not kind and not item_id:
        kind = "person"
        item_id = profile_id.strip()
    if not kind and not item_id and not label:
        return None
    if not kind:
        kind = "subject"
    if not item_id:
        item_id = label or kind
    if not label:
        label = item_id
    safe_id = "".join(char if char.isalnum() or char in "._-" else "_" for char in item_id).strip("_")
    return {"kind": kind, "id": item_id, "label": label, "safe_id": safe_id or "subject"}


def _is_decided_work_item(item: dict[str, object]) -> bool:
    selected_action = str(item.get("selected_action", "")).strip()
    decision_status = str(item.get("decision_status", "")).strip()
    return bool(selected_action and selected_action != "pending") or bool(
        decision_status and decision_status not in {"pending", "unreviewed", "draft"}
    )


def _review_dashboard_paths(session: dict[str, object]) -> dict[str, Path] | None:
    review_session_json = str(session.get("review_session_json", "")).strip()
    if not review_session_json:
        return None
    review_dir = Path(review_session_json).parent
    if not str(review_dir):
        return None
    return {"json": review_dir / "review_dashboard.json", "markdown": review_dir / "review_dashboard.md"}


def _int_value(value: object, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _status_value(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "unknown"


def _sorted_counts(counter: Counter[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counter.items(), key=lambda item: item[0]))


def _print_count_block(label: str, counts: tuple[tuple[str, int], ...]) -> None:
    print(f"{label}:")
    if counts:
        for status, count in counts:
            print(f"- {status}: {count}")
    else:
        print("- none: 0")


def _print_count_markdown(title: str, counts: tuple[tuple[str, int], ...]) -> None:
    print(f"## {title}")
    print("")
    if counts:
        for status, count in counts:
            print(f"- `{status}`: {count}")
    else:
        print("- none")
    print("")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memoria", description="Me.Mo.Ri.A diagnostic CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name, command_help, handler in (
        ("data-root", "Stampa il data root risolto.", _command_data_root),
        ("inventory", "Verifica le cartelle principali del data root senza scansione ricorsiva.", _command_inventory),
        ("doctor", "Verifica data root, cartelle principali e repository sibling.", _command_doctor),
    ):
        command = subparsers.add_parser(command_name, help=command_help)
        command.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
        if command_name == "inventory":
            command.add_argument(
                "--section",
                choices=(*INVENTORY_SECTIONS, "all"),
                default="",
                help="Sezione del data root da inventariare superficialmente.",
            )
            command.add_argument(
                "--output",
                choices=("text", "markdown"),
                default="text",
                help="Formato di output.",
            )
        command.set_defaults(handler=handler)

    profiles = subparsers.add_parser("profiles", help="Diagnostica read-only dei profili persona.")
    profiles_subparsers = profiles.add_subparsers(dest="profiles_command", required=True)
    profiles_status = profiles_subparsers.add_parser(
        "status",
        help="Verifica stato profili/schede dal data root esterno.",
    )
    profiles_status.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
    profiles_status.add_argument(
        "--profiles-index",
        default="",
        help="Indice profili esplicito; di default usa ricerche/person_profiles/purocielo.index.jsonld nel data root.",
    )
    profiles_status.add_argument(
        "--output",
        choices=("text", "markdown"),
        default="text",
        help="Formato di output.",
    )
    profiles_status.set_defaults(handler=_command_profiles_status)

    mvp = subparsers.add_parser("mvp", help="Vista read-only del walkthrough MVP demo.")
    mvp_subparsers = mvp.add_subparsers(dest="mvp_command", required=True)
    mvp_status = mvp_subparsers.add_parser(
        "status",
        help="Compone lo stato read-only del walkthrough MVP demo.",
    )
    mvp_status.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
    mvp_status.set_defaults(handler=_command_mvp_status)
    mvp_demo = mvp_subparsers.add_parser(
        "demo",
        help="Legge il descrittore golden run MVP demo senza modificarlo.",
    )
    mvp_demo.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
    mvp_demo.add_argument(
        "--descriptor",
        default="",
        help="Path esplicito al descrittore; di default usa database/memoria_mvp_demo.active.json nel data root.",
    )
    mvp_demo.set_defaults(handler=_command_mvp_demo)
    mvp_demo_build = mvp_subparsers.add_parser(
        "demo-build",
        help="Prepara il descrittore golden run MVP demo da una run esistente; scrive solo su output espliciti.",
    )
    mvp_demo_build.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
    mvp_demo_build.add_argument("--run-id", required=True, help="Run canonica da leggere in risultati/runs/<run-id>.")
    mvp_demo_build.add_argument(
        "--primary-profile-id",
        action="append",
        default=None,
        help="Profilo principale da includere; ripetibile. Default: caso T30.",
    )
    mvp_demo_build.add_argument(
        "--contrast-profile-id",
        action="append",
        default=None,
        help="Profilo di contrasto da includere; ripetibile. Default: caso T30.",
    )
    mvp_demo_build.add_argument(
        "--source-document-id",
        action="append",
        default=None,
        help="Documento sorgente da includere; ripetibile. Default: documenti T30.",
    )
    mvp_demo_build.add_argument("--ledger", default="", help="Ledger consolidato esplicito.")
    mvp_demo_build.add_argument("--review-queue", default="", help="Review queue esplicita.")
    mvp_demo_build.add_argument("--review-decisions-summary", default="", help="Decision summary esplicito.")
    mvp_demo_build.add_argument("--verified-facts-preview", default="", help="Verified facts preview esplicito.")
    mvp_demo_build.add_argument("--profile-patch-preview", default="", help="ProfilePatch preview esplicito.")
    mvp_demo_build.add_argument("--readiness-report", default="", help="Readiness report esplicito.")
    mvp_demo_build.add_argument(
        "--output-aligned-ledger",
        default="",
        help="Path sidecar ledger preview riallineato al perimetro T30. Se omesso, non viene scritto.",
    )
    mvp_demo_build.add_argument(
        "--output-descriptor",
        default="",
        help="Path di output descriptor. Se omesso, non viene scritto alcun descriptor.",
    )
    mvp_demo_build.add_argument(
        "--output-reconciliation",
        default="",
        help="Path di output tabella markdown. Se omesso, non viene scritta alcuna tabella.",
    )
    mvp_demo_build.set_defaults(handler=_command_mvp_demo_build)

    review = subparsers.add_parser("review", help="Bridge read-only dei workflow review MVP.")
    review_subparsers = review.add_subparsers(dest="review_command", required=True)
    for command_name, command_help, handler in (
        ("discover", "Scopre run review candidate senza creare sessioni.", _command_review_discover),
        ("status", "Mostra stato review o discovery se non esiste una sessione attiva.", _command_review_status),
        ("work", "Mostra la worklist della sessione review attiva senza applicare decisioni.", _command_review_work),
        ("decisions", "Mostra il riepilogo decisioni review senza registrare nuove decisioni.", _command_review_decisions),
    ):
        command = review_subparsers.add_parser(command_name, help=command_help)
        command.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
        if command_name != "decisions":
            command.add_argument("--limit", type=int, default=5, help="Numero massimo di elementi da mostrare.")
        command.set_defaults(handler=handler)

    consolidate = subparsers.add_parser("consolidate", help="Bridge read-only dei workflow consolidate MVP.")
    consolidate_subparsers = consolidate.add_subparsers(dest="consolidate_command", required=True)
    for command_name, command_help, handler in (
        ("discover", "Scopre run consolidabili senza creare sessioni.", _command_consolidate_discover),
        ("status", "Mostra stato consolidate o discovery se non esiste una sessione attiva.", _command_consolidate_status),
    ):
        command = consolidate_subparsers.add_parser(command_name, help=command_help)
        command.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
        command.add_argument("--limit", type=int, default=5, help="Numero massimo di elementi da mostrare.")
        command.set_defaults(handler=handler)

    sources = subparsers.add_parser("sources", help="Bridge read-only dei workflow sources MVP.")
    sources_subparsers = sources.add_subparsers(dest="sources_kind", required=True)
    sources_online = sources_subparsers.add_parser("online", help="Orientamento read-only sulle fonti online.")
    sources_online_subparsers = sources_online.add_subparsers(dest="sources_online_command", required=True)
    for command_name, command_help, handler in (
        ("discover", "Mostra registry, profili e fonti candidate senza avviare rete.", _command_sources_online_discover),
        ("status", "Mostra sessione sources online attiva o discovery read-only.", _command_sources_online_status),
    ):
        command = sources_online_subparsers.add_parser(command_name, help=command_help)
        command.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
        command.add_argument("--limit", type=int, default=5, help="Numero massimo di elementi da mostrare.")
        command.add_argument("--profile-id", default="", help="Profilo persona candidato per il contesto sources online.")
        command.add_argument("--subject-kind", default="", help="Tipo soggetto candidato: person, place o event.")
        command.add_argument("--subject-id", default="", help="ID soggetto candidato.")
        command.add_argument("--subject-label", default="", help="Etichetta soggetto candidata.")
        command.set_defaults(handler=handler)

    sources_offline = sources_subparsers.add_parser("offline", help="Orientamento read-only sulle fonti offline.")
    sources_offline_subparsers = sources_offline.add_subparsers(dest="sources_offline_command", required=True)
    for command_name, command_help, handler in (
        ("discover", "Mostra documenti offline candidati senza creare run.", _command_sources_offline_discover),
        ("status", "Mostra stato offline read-only senza creare run.", _command_sources_offline_status),
    ):
        command = sources_offline_subparsers.add_parser(command_name, help=command_help)
        command.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
        command.add_argument("--limit", type=int, default=5, help="Numero massimo di elementi da mostrare.")
        command.set_defaults(handler=handler)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
