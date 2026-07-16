from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from typing import Any, Callable


@dataclass
class Caduto:
    intestazione_pdf: str
    nome: str
    origine_sulla_lapide: str
    nascita: str
    morte: str
    ruolo_affiliazione: str
    fonti_richiamate: str
    profilo_biografico: str
    episodio_documentato: str


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str = ""
    content: str = ""


@dataclass
class SourceResult:
    source_id: str
    source_name: str
    status: str
    note: str
    query: str
    search_url: str
    hits: list[SearchHit] = field(default_factory=list)


@dataclass
class Source:
    source_id: str
    source_name: str
    kind: str
    build_query: Callable[[Caduto], str]
    search_url_builder: Callable[[str], str]
    credentials: dict[str, str] = field(default_factory=dict)
    auth: dict[str, str] = field(default_factory=dict)
    form: dict[str, str] = field(default_factory=dict)
    local: dict[str, str] = field(default_factory=dict)
    extraction: dict[str, Any] = field(default_factory=dict)
    note: str = ""
    timeout: int = 20


@dataclass
class SourceQualityIssue:
    source_id: str
    severity: str
    code: str
    message: str


@dataclass
class SourceQualityAssessment:
    source_id: str
    source_name: str = ""
    candidate_quality: str = "unknown"
    detail_level: str = "detail_document_only"
    has_profile: bool = False
    has_strategy: bool = False
    has_result_logic: bool = False
    has_detail_logic: bool = False
    has_result_fixture: bool = False
    has_detail_fixture: bool = False
    has_result_logic_test: bool = False
    has_detail_logic_test: bool = False
    noise_indicators: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    issues: list[SourceQualityIssue] = field(default_factory=list)


@dataclass
class SourceQualityAudit:
    generated_at: str
    source_count: int
    assessments: list[SourceQualityAssessment] = field(default_factory=list)


@dataclass
class SourceSelection:
    source_file: str
    selected_sources: list[Source]
    selected_source_ids: list[str]
    unresolved_source_ids: list[str]
    used_fallback: bool = False


@dataclass
class PersonQuery:
    full_name: str
    given_name: str = ""
    family_name: str = ""
    aliases: list[str] = field(default_factory=list)
    birth_date: str = ""
    birth_place: str = ""
    death_date: str = ""
    death_place: str = ""
    formation: str = ""
    event_hint: str = ""
    place_hint: str = ""
    source_hints: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ProfileSeed:
    source: str
    source_id: str = ""
    imported_at: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfileIdentity:
    canonical_name: str
    given_name: str = ""
    family_name: str = ""
    aliases: list[str] = field(default_factory=list)
    name_forms: list[str] = field(default_factory=list)


@dataclass
class ProfileSearchHint:
    hint_id: str
    source_id: str
    field: str
    value: str
    confidence: float = 0.0
    provenance: str = ""
    review_status: str = "unreviewed"


@dataclass
class PersonResearchProfile:
    profile_id: str
    identity: ProfileIdentity
    seed: ProfileSeed
    birth: dict[str, str] = field(default_factory=dict)
    death: dict[str, str] = field(default_factory=dict)
    formations: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    search_hints: list[ProfileSearchHint] = field(default_factory=list)
    evidence_claim_ids: list[str] = field(default_factory=list)
    verified_facts: dict[str, str] = field(default_factory=dict)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    searched_sources: list[str] = field(default_factory=list)
    next_research: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class HistoricalEvent:
    event_id: str
    event_type: str
    label: str
    description: str = ""
    date_start: str = ""
    date_end: str = ""
    place_labels: list[str] = field(default_factory=list)
    place_ids: list[str] = field(default_factory=list)
    source_document_ids: list[str] = field(default_factory=list)
    evidence_claim_ids: list[str] = field(default_factory=list)
    review_status: str = "unreviewed"
    confidence: float = 0.0
    provenance: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Place:
    place_id: str
    preferred_label: str
    place_type: str
    alternate_labels: list[str] = field(default_factory=list)
    description: str = ""
    latitude: float | None = None
    longitude: float | None = None
    admin_hierarchy: list[str] = field(default_factory=list)
    same_as: list[str] = field(default_factory=list)
    source_document_ids: list[str] = field(default_factory=list)
    evidence_claim_ids: list[str] = field(default_factory=list)
    review_status: str = "unreviewed"
    confidence: float = 0.0
    provenance: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class SourceDocument:
    document_id: str
    source_id: str
    title: str = ""
    url: str = ""
    access_date: str = ""
    media_type: str = ""
    local_path: str = ""
    content_hash: str = ""
    raw_text: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class EvidenceClaim:
    claim_id: str
    subject_id: str
    field: str
    value: str
    normalized_value: str = ""
    source_document_id: str = ""
    source_url: str = ""
    quote: str = ""
    extraction_method: str = ""
    confidence: float = 0.0
    review_status: str = "unreviewed"
    created_at: str = ""


@dataclass
class SearchRun:
    run_id: str
    timestamp: str
    input_file: str = ""
    source_ids: list[str] = field(default_factory=list)
    parameters: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ResearchReport:
    run: SearchRun
    person_queries: list[PersonQuery] = field(default_factory=list)
    source_results: list[SourceResult] = field(default_factory=list)
    source_documents: list[SourceDocument] = field(default_factory=list)
    evidence_claims: list[EvidenceClaim] = field(default_factory=list)


HISTORICAL_EVENT_JSONLD_CONTEXT = {
    "crm": "http://www.cidoc-crm.org/cidoc-crm/",
    "schema": "https://schema.org/",
    "ca": "https://ca-di-malanca.local/ontology/",
    "HistoricalEvent": "ca:HistoricalEvent",
    "Place": "ca:Place",
    "EvidenceClaim": "ca:EvidenceClaim",
    "SourceDocument": "ca:SourceDocument",
}

PLACE_JSONLD_CONTEXT = {
    "crm": "http://www.cidoc-crm.org/cidoc-crm/",
    "schema": "https://schema.org/",
    "ca": "https://ca-di-malanca.local/ontology/",
    "Place": "ca:Place",
    "EvidenceClaim": "ca:EvidenceClaim",
    "SourceDocument": "ca:SourceDocument",
}


def to_json_safe(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: to_json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [to_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def historical_event_to_jsonld(event: HistoricalEvent) -> dict[str, Any]:
    payload = to_json_safe(event)
    payload["@context"] = HISTORICAL_EVENT_JSONLD_CONTEXT
    payload["@type"] = "HistoricalEvent"
    payload["@id"] = event.event_id
    return payload


def historical_event_from_jsonld(payload: dict[str, Any]) -> HistoricalEvent:
    return HistoricalEvent(
        event_id=str(payload.get("event_id") or payload.get("@id") or ""),
        event_type=str(payload.get("event_type", "")),
        label=str(payload.get("label", "")),
        description=str(payload.get("description", "")),
        date_start=str(payload.get("date_start", "")),
        date_end=str(payload.get("date_end", "")),
        place_labels=_string_list(payload.get("place_labels")),
        place_ids=_string_list(payload.get("place_ids")),
        source_document_ids=_string_list(payload.get("source_document_ids")),
        evidence_claim_ids=_string_list(payload.get("evidence_claim_ids")),
        review_status=str(payload.get("review_status", "unreviewed")),
        confidence=_float_or_default(payload.get("confidence"), 0.0),
        provenance=str(payload.get("provenance", "")),
        metadata=_string_dict(payload.get("metadata")),
    )


def place_to_jsonld(place: Place) -> dict[str, Any]:
    payload = to_json_safe(place)
    payload["@context"] = PLACE_JSONLD_CONTEXT
    payload["@type"] = "Place"
    payload["@id"] = place.place_id
    return payload


def place_from_jsonld(payload: dict[str, Any]) -> Place:
    return Place(
        place_id=str(payload.get("place_id") or payload.get("@id") or ""),
        preferred_label=str(payload.get("preferred_label", "")),
        place_type=str(payload.get("place_type", "unknown")),
        alternate_labels=_string_list(payload.get("alternate_labels")),
        description=str(payload.get("description", "")),
        latitude=_optional_float(payload.get("latitude")),
        longitude=_optional_float(payload.get("longitude")),
        admin_hierarchy=_string_list(payload.get("admin_hierarchy")),
        same_as=_string_list(payload.get("same_as")),
        source_document_ids=_string_list(payload.get("source_document_ids")),
        evidence_claim_ids=_string_list(payload.get("evidence_claim_ids")),
        review_status=str(payload.get("review_status", "unreviewed")),
        confidence=_float_or_default(payload.get("confidence"), 0.0),
        provenance=str(payload.get("provenance", "")),
        metadata=_string_dict(payload.get("metadata")),
    )


def person_query_from_caduto(caduto: Caduto) -> PersonQuery:
    name_parts = caduto.nome.split()
    family_name = name_parts[0] if len(name_parts) >= 2 else ""
    given_name = " ".join(name_parts[1:]) if len(name_parts) >= 2 else caduto.nome
    metadata = {
        "intestazione_pdf": caduto.intestazione_pdf,
        "nome": caduto.nome,
        "origine_sulla_lapide": caduto.origine_sulla_lapide,
        "nascita": caduto.nascita,
        "morte": caduto.morte,
        "ruolo_affiliazione": caduto.ruolo_affiliazione,
        "fonti_richiamate": caduto.fonti_richiamate,
        "profilo_biografico": caduto.profilo_biografico,
        "episodio_documentato": caduto.episodio_documentato,
    }
    return PersonQuery(
        full_name=caduto.nome,
        given_name=given_name,
        family_name=family_name,
        birth_date=caduto.nascita,
        death_date=caduto.morte,
        formation=caduto.ruolo_affiliazione,
        event_hint=caduto.episodio_documentato,
        place_hint=caduto.origine_sulla_lapide,
        metadata=metadata,
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
