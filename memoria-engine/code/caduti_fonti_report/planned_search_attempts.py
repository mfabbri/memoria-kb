from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import to_json_safe


@dataclass(frozen=True)
class PlannedSearchAttempt:
    source_id: str
    attempt_id: str
    priority: int
    query_text: str = ""
    query_fields: dict[str, str] = field(default_factory=dict)
    identity_basis: str = ""
    used_profile_fields: list[str] = field(default_factory=list)
    used_search_hints: list[str] = field(default_factory=list)
    expected_result_level: str = "candidate_results"
    risk_level: str = "medium"
    manual_review_required: bool = True
    skip_reason: str = ""
    reason: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


def planned_search_attempt_to_dict(attempt: PlannedSearchAttempt) -> dict[str, Any]:
    return to_json_safe(attempt)


def planned_search_attempts_to_dict(attempts: list[PlannedSearchAttempt]) -> list[dict[str, Any]]:
    return [planned_search_attempt_to_dict(attempt) for attempt in attempts]
