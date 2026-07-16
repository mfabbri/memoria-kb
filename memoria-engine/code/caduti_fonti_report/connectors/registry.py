from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..models import Caduto, Source, SourceResult
from ..source_definitions import has_source_definition, load_source_definition
from .interface import SourceConnector
from .legacy_adapter import LegacyConnectorAdapter
from .local_excel_connector import LocalExcelSourceConnector
from .uniform_source_connector import AuthenticatedSessionFactory, UniformSourceConnector


@dataclass(frozen=True)
class ConnectorRegistration:
    source_id: str
    connector_type: str
    evidence_aware: bool
    detail_fetch: str
    claim_extraction: str


def create_source_connector(
    source: Source,
    *,
    run_id: str = "",
    repo_root: Path | None = None,
    run_source_func: Callable[[Source, Caduto], SourceResult] | None = None,
    max_search_attempts: int = 0,
    authenticated_session_factory: AuthenticatedSessionFactory | None = None,
) -> SourceConnector:
    connector_run_id = run_id or "evidence-aware-connector"

    if source.kind == "local_excel":
        return LocalExcelSourceConnector(source, run_id=connector_run_id)

    if has_source_definition(source, repo_root=repo_root):
        return UniformSourceConnector(
            source,
            run_id=connector_run_id,
            repo_root=repo_root,
            max_search_attempts=max_search_attempts,
            authenticated_session_factory=authenticated_session_factory,
        )

    if run_source_func is None:
        return LegacyConnectorAdapter(source)
    return LegacyConnectorAdapter(source, run_source_func=run_source_func)


def describe_source_connector(source: Source) -> ConnectorRegistration:
    if source.kind == "local_excel":
        return ConnectorRegistration(
            source_id=source.source_id,
            connector_type="LocalExcelSourceConnector",
            evidence_aware=True,
            detail_fetch="local_table_row",
            claim_extraction="local_table_claims",
        )

    if has_source_definition(source):
        definition = load_source_definition(source)
        return ConnectorRegistration(
            source_id=source.source_id,
            connector_type="UniformSourceConnector",
            evidence_aware=True,
            detail_fetch=definition.detail_fetch_mode,
            claim_extraction=definition.claim_extraction_mode,
        )

    return ConnectorRegistration(
        source_id=source.source_id,
        connector_type="LegacyConnectorAdapter",
        evidence_aware=False,
        detail_fetch="none",
        claim_extraction="none",
    )
