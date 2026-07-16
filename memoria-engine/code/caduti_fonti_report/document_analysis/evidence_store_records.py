from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceStoreRecord:
    record_id: str
    source_run_id: str
    record_kind: str
    subject_id: str
    source_document_id: str
    review_status: str
    payload_hash: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "EvidenceStoreRecord":
        return cls(
            record_id=str(row.get("record_id", "")),
            source_run_id=str(row.get("source_run_id", "")),
            record_kind=str(row.get("record_kind", "")),
            subject_id=str(row.get("subject_id", "")).strip(),
            source_document_id=str(row.get("source_document_id", "")).strip(),
            review_status=str(row.get("review_status", "")),
            payload_hash=str(row.get("payload_hash", "")),
            payload=_payload_from_json(str(row.get("payload_json", ""))),
        )

    @property
    def effective_source_document_id(self) -> str:
        return self.source_document_id or str(self.payload.get("source_document_id", "")).strip()

    @property
    def subject_kind(self) -> str:
        return str(self.payload.get("subject_kind", "")).strip()

    @property
    def item_id(self) -> str:
        return str(self.payload.get("item_id", "")).strip()

    def profile_ids(self) -> list[str]:
        values = [
            self.subject_id,
            str(self.payload.get("profile_id", "")).strip(),
            str(self.payload.get("person_id", "")).strip(),
            str(self.payload.get("person_candidate_id", "")).strip(),
            str(self.payload.get("subject_id", "")).strip(),
            str(self.payload.get("candidate_profile_id", "")).strip(),
        ]
        for key in ("candidate_profile_ids", "profile_ids", "person_ids", "subject_ids"):
            value = self.payload.get(key)
            if isinstance(value, list):
                values.extend(str(item).strip() for item in value)
        result = []
        for value in values:
            if value and value not in result:
                result.append(value)
        return result

    def primary_profile_id(self) -> str:
        ids = self.profile_ids()
        return ids[0] if ids else ""

    def scoped_payload(self, *, profile_id: str = "") -> dict[str, Any]:
        payload = dict(self.payload)
        if profile_id:
            payload.setdefault("profile_id", profile_id)
        payload.setdefault("source_document_id", self.effective_source_document_id)
        payload.setdefault("review_status", self.review_status or "unreviewed")
        return payload

    def store_key(self, *parts: Any) -> str:
        logical = "|".join(str(part) for part in parts if str(part))
        return logical or self.record_id


def _payload_from_json(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("payload")
    return nested if isinstance(nested, dict) else payload
