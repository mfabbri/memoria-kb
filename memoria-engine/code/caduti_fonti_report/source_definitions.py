from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .detail_page_logic import SourceDetailLogicDefinition, load_source_detail_logic
from .models import Source
from .search_result_logic import SourceResultLogicDefinition, load_source_result_logic
from .source_catalog import resolve_source_catalog_root, source_catalog_relative_path, source_level_path
from .source_profiles import SourceSearchProfile, load_source_search_profile
from .source_strategies import SourceSearchStrategyDefinition, load_source_search_strategy


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    profile_path: str
    strategy_path: str
    result_logic_path: str
    executor_id: str
    result_parser_id: str
    detail_fetch_mode: str = "reference_only"
    claim_extraction_mode: str = "none"
    detail_logic_path: str = ""
    profile: SourceSearchProfile | None = None
    strategy_definition: SourceSearchStrategyDefinition | None = None
    result_logic: SourceResultLogicDefinition | None = None
    detail_logic: SourceDetailLogicDefinition | None = None


def load_source_definition(source: Source, *, repo_root: Path | None = None) -> SourceDefinition:
    repo_root = repo_root or Path.cwd()
    catalog_root = resolve_source_catalog_root(repo_root)
    source_id = source.source_id

    profile_path = source_level_path(catalog_root, "source_profiles", source_id)
    strategy_path = source_level_path(catalog_root, "source_strategies", source_id)
    result_logic_path = source_level_path(catalog_root, "source_result_logic", source_id)
    detail_logic_path = source_level_path(catalog_root, "source_detail_logic", source_id)

    missing = [source_catalog_relative_path(repo_root, path) for path in [profile_path, strategy_path, result_logic_path] if not path.exists()]
    if missing:
        joined = ", ".join(missing)
        raise FileNotFoundError(f"Definizione fonte incompleta per {source_id}: mancano {joined}.")

    executor_id, result_parser_id = _technical_components_for_source(source)
    return SourceDefinition(
        source_id=source_id,
        profile_path=source_catalog_relative_path(repo_root, profile_path),
        strategy_path=source_catalog_relative_path(repo_root, strategy_path),
        result_logic_path=source_catalog_relative_path(repo_root, result_logic_path),
        executor_id=executor_id,
        result_parser_id=result_parser_id,
        detail_fetch_mode="detail_page" if detail_logic_path.exists() else "reference_only",
        claim_extraction_mode="detail_logic" if detail_logic_path.exists() else "none",
        detail_logic_path=source_catalog_relative_path(repo_root, detail_logic_path) if detail_logic_path.exists() else "",
        profile=load_source_search_profile(profile_path),
        strategy_definition=load_source_search_strategy(strategy_path),
        result_logic=load_source_result_logic(result_logic_path),
        detail_logic=load_source_detail_logic(detail_logic_path) if detail_logic_path.exists() else None,
    )


def _technical_components_for_source(source: Source) -> tuple[str, str]:
    if source.source_id == "atlante_stragi":
        return "post_form_executor", "generic_result_page_parser"
    if source.source_id == "bundesarchiv_invenio":
        return "bundesarchiv_invenio_playwright_executor", "generic_result_page_parser"
    if source.source_id == "german_docs_in_russia_wwii":
        return "german_docs_in_russia_executor", "generic_result_page_parser"
    if source.source_id == "fondazione_fossoli":
        return "playwright_form_executor", "generic_result_page_parser"
    if source.kind == "cwgc" or source.source_id == "cwgc":
        return "url_only_executor", "cwgc_result_parser"
    if source.source_id in {"tna_wo417", "tna_hs9"}:
        return "playwright_form_executor", "generic_result_page_parser"
    if source.kind == "storia_memoria_bo" or source.source_id == "storia_memoria_bo":
        return "storia_memoria_bo_executor", "generic_result_page_parser"
    if source.kind == "search_form_get_name":
        return "http_get_form_executor", "generic_result_page_parser"
    if source.kind == "search_page":
        return "url_template_fetch_executor", "generic_result_page_parser"
    if source.kind in {"search_form_post", "search_form_aspnet", "obd_memorial", "pamyat_naroda", "credentialed"}:
        return "reference_only_executor", "generic_result_page_parser"
    return "reference_only_executor", "generic_result_page_parser"


def has_source_definition(source: Source, *, repo_root: Path | None = None) -> bool:
    repo_root = repo_root or Path.cwd()
    catalog_root = resolve_source_catalog_root(repo_root)
    source_id = source.source_id
    required = [
        source_level_path(catalog_root, "source_profiles", source_id),
        source_level_path(catalog_root, "source_strategies", source_id),
        source_level_path(catalog_root, "source_result_logic", source_id),
    ]
    return all(path.exists() for path in required)
