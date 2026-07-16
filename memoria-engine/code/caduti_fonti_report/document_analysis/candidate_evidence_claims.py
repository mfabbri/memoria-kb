from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .preview_payloads import list_strings


@dataclass(frozen=True)
class CandidateEvidenceClaimRecord:
    claim_id: str
    profile_id: str
    person_candidate_id: str
    source_document_id: str
    source_id: str
    field: str
    value: str
    normalized_value: str
    review_status: str
    extraction_method: str
    confidence: Any
    reasons: tuple[str, ...]
    weak_segment_id: str
    chunk_id: str
    evidence_span: str
    context: str
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> CandidateEvidenceClaimRecord:
        reasons = list_strings(payload.get("reasons")) if isinstance(payload.get("reasons"), list) else []
        return cls(
            claim_id=_text(payload.get("@id") or payload.get("claim_id")),
            profile_id=_text(payload.get("profile_id")),
            person_candidate_id=_text(payload.get("person_candidate_id")),
            source_document_id=_text(payload.get("source_document_id")),
            source_id=_text(payload.get("source_id")),
            field=_text(payload.get("field")),
            value=_text(payload.get("value")),
            normalized_value=_text(payload.get("normalized_value")),
            review_status=_text(payload.get("review_status")),
            extraction_method=_text(payload.get("extraction_method")),
            confidence=payload.get("confidence", ""),
            reasons=tuple(reasons),
            weak_segment_id=_text(payload.get("weak_segment_id")),
            chunk_id=_text(payload.get("chunk_id")),
            evidence_span=_text(payload.get("evidence_span")),
            context=_text(payload.get("context")),
            payload=payload,
        )

    @property
    def effective_profile_id(self) -> str:
        return self.profile_id or self.person_candidate_id

    @property
    def dedupe_key(self) -> tuple[str, str, str, str]:
        return (self.effective_profile_id, self.source_document_id, self.field, self.normalized_value)

    @property
    def reasons_text(self) -> str:
        return ", ".join(self.reasons)

    def priority(self, *, structured_extraction_method: str) -> int:
        if self.extraction_method == structured_extraction_method:
            return 2
        return 1


def _text(value: Any) -> str:
    return str(value or "").strip()
