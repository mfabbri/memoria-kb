from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .preview_payloads import dict_object, list_strings


@dataclass(frozen=True)
class ReviewQueueItemRecord:
    item_id: str
    item_type: str
    subject_kind: str
    profile_id: str
    canonical_name: str
    source_document_id: str
    source_item_id: str
    priority: str
    risk: str
    question: str
    context: str
    raw_file: str
    metadata_file: str
    document_reference_note: str
    allowed_decisions: tuple[str, ...]
    candidate_field: str
    candidate_value: str
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ReviewQueueItemRecord:
        candidate = dict_object(payload.get("candidate"))
        allowed_decisions = list_strings(payload.get("allowed_decisions")) if isinstance(payload.get("allowed_decisions"), list) else []
        return cls(
            item_id=_text(payload.get("item_id")),
            item_type=_text(payload.get("item_type")),
            subject_kind=_text(payload.get("subject_kind")),
            profile_id=_text(payload.get("profile_id")),
            canonical_name=_text(payload.get("canonical_name")),
            source_document_id=_text(payload.get("source_document_id")),
            source_item_id=_text(payload.get("source_item_id")),
            priority=_text(payload.get("priority")),
            risk=_text(payload.get("risk")),
            question=_text(payload.get("question")),
            context=_text(payload.get("context")),
            raw_file=_text(payload.get("raw_file")),
            metadata_file=_text(payload.get("metadata_file")),
            document_reference_note=_text(payload.get("document_reference_note")),
            allowed_decisions=tuple(allowed_decisions),
            candidate_field=_text(candidate.get("field")),
            candidate_value=_text(candidate.get("value")),
            payload=payload,
        )

    @property
    def allowed_decisions_text(self) -> str:
        return ", ".join(self.allowed_decisions)


def _text(value: Any) -> str:
    return str(value or "").strip()
