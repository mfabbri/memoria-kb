from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
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


def build_source_report_candidate_claims(
    *, report_json: Path, profile_id: str, output_dir: Path, source_document_ids: list[str] | None = None,
) -> dict[str, Any]:
    selected_document_ids = _report_identifier_list({"source_document_ids": source_document_ids}, "source_document_ids")
    if not selected_document_ids:
        raise ValueError("At least one explicit source document ID is required.")
    selected_document_ids = sorted(selected_document_ids)
    selected_document_set = set(selected_document_ids)
    raw = report_json.read_bytes()
    report = json.loads(raw)
    if not isinstance(report, dict) or (
        report.get("@type") != "SourceResearchReport"
        and not ("@type" not in report and report.get("input_mode") == "person_profiles_jsonld")
    ):
        raise ValueError("Expected a SourceResearchReport or person_profiles_jsonld source report.")
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ValueError("An explicit profile ID is required.")
    source_selection = report.get("source_selection")
    if source_selection is None:
        if report.get("@type") != "SourceResearchReport":
            raise ValueError("A person_profiles_jsonld report requires explicit source_selection.")
        selected_sources = None
    else:
        if not isinstance(source_selection, dict):
            raise ValueError("Source selection must be an object.")
        selected_sources = _report_identifier_list(source_selection, "selected_source_ids")
    profiles = _report_list(report, "profiles")
    profile_ids = [_report_text(profile, "profile_id") for profile in profiles]
    if len(set(profile_ids)) != len(profile_ids):
        raise ValueError("Source report contains duplicate profile IDs.")
    if profile_ids.count(profile_id) != 1:
        raise ValueError("Source report must contain exactly one selected profile.")
    profile_index = profile_ids.index(profile_id)
    profile = profiles[profile_index]
    report_attempts = _report_attempt_ids(report)
    report_ref = {"path": str(report_json.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}
    candidates = []
    seen_claims: dict[str, dict[str, Any]] = {}
    profile_document_ids: set[str] = set()
    excluded_claim_ids: set[str] = set()
    for result_index, entry in enumerate(_report_list(profile, "results")):
        if _report_text(entry, "profile_id") != profile_id:
            raise ValueError("Result profile reference does not match the selected profile.")
        result = entry.get("result")
        declared_source_ids = []
        for source_reference in (entry, result if isinstance(result, dict) else {}):
            if "source_id" in source_reference:
                declared_source_ids.append(_report_text(source_reference, "source_id"))
        attempts = _report_attempt_ids(entry)
        if report_attempts and attempts and attempts != report_attempts:
            raise ValueError("Result selected attempt IDs disagree with the source report.")
        matched_attempt = _report_text(entry, "matched_planned_attempt_id", required=False)
        if matched_attempt and (attempts or report_attempts) and matched_attempt not in (attempts or report_attempts):
            raise ValueError("Matched attempt ID is not among the explicitly selected attempts.")
        documents = {}
        for document in _report_list(entry, "documents"):
            document_id = _report_text(document, "document_id")
            if document_id in documents:
                raise ValueError("Ambiguous duplicate document ID within a report result.")
            document_source_id = _report_text(document, "source_id")
            if any(source_id != document_source_id for source_id in declared_source_ids):
                raise ValueError("Document and result source IDs disagree.")
            if selected_sources is not None and document_source_id not in selected_sources:
                raise ValueError("Document source ID is outside the report's explicit source selection.")
            metadata = document.get("metadata", {})
            if (not isinstance(metadata, dict) or (metadata.get("profile_id") and metadata["profile_id"] != profile_id)
                    or (document.get("profile_id") and document["profile_id"] != profile_id)):
                raise ValueError("Document profile metadata does not match the selected profile.")
            documents[document_id] = document
            profile_document_ids.add(document_id)
        for claim in _report_list(entry, "claims"):
            claim_id = _report_text(claim, "claim_id")
            if (claim.get("@id") and claim["@id"] != claim_id) or (claim.get("profile_id") and claim["profile_id"] != profile_id):
                raise ValueError("Claim identifiers or profile references disagree.")
            if _report_text(claim, "subject_id") != profile_id:
                raise ValueError("Claim subject_id does not match the selected profile.")
            document_id = _report_text(claim, "source_document_id")
            if document_id not in documents:
                raise ValueError("Claim must reference exactly one document in the same result.")
            document = documents[document_id]
            source_id = document["source_id"]
            url = _report_text(document, "url")
            access_date = _report_text(document, "access_date")
            date.fromisoformat(access_date)
            if _report_text(claim, "source_url", required=False) not in {"", url}:
                raise ValueError("Claim source URL differs from its linked document.")
            if "source_id" in claim and _report_text(claim, "source_id") != source_id:
                raise ValueError("Claim source ID differs from its linked document.")
            if claim.get("review_status") != "unreviewed":
                raise ValueError("Only unreviewed source-report claims can become candidates.")
            confidence = claim.get("confidence")
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1 or not math.isfinite(confidence):
                raise ValueError("Claim confidence must be numeric and in [0, 1].")
            quote = _report_text(claim, "quote")
            document_ref = {key: value for key, value in document.items() if key != "raw_text"}
            candidate = {
                "@type": "CandidateEvidenceClaim", "@id": claim_id, "claim_id": claim_id,
                "profile_id": profile_id, "subject_id": claim["subject_id"],
                "source_document_id": document_id, "source_id": source_id, "source_url": url, "url": url,
                "access_date": access_date, "field": _report_text(claim, "field"), "value": _report_text(claim, "value"),
                "normalized_value": _report_text(claim, "normalized_value", required=False),
                "quote": quote, "evidence_span": quote, "confidence": confidence,
                "extraction_method": _report_text(claim, "extraction_method"), "review_status": "unreviewed",
                "selected_attempt_ids": attempts, "matched_planned_attempt_id": matched_attempt,
                "source_report_claim": claim,
                "provenance": {"source_report": report_ref, "profile_index": profile_index, "result_index": result_index,
                               "source_document": document_ref, "source_url": url, "access_date": access_date,
                               "report_selected_attempt_ids": report_attempts, "result_selected_attempt_ids": attempts,
                               "matched_planned_attempt_id": matched_attempt},
            }
            fingerprint = _claim_semantic_fingerprint(candidate)
            attempt_record = {
                "result_index": result_index,
                "report_selected_attempt_ids": report_attempts,
                "selected_attempt_ids": attempts,
                "matched_planned_attempt_id": matched_attempt,
                "source_report_claim": claim,
            }
            attempt_identity = (matched_attempt, tuple(attempts))
            existing = seen_claims.get(claim_id)
            if existing is not None:
                if existing["fingerprint"] != fingerprint:
                    raise ValueError(f"Source report contains conflicting duplicate claim ID: {claim_id}.")
                if attempt_identity in existing["attempt_identities"]:
                    raise ValueError(f"Source report repeats claim ID within the same attempt: {claim_id}.")
                existing["attempt_identities"].add(attempt_identity)
                existing["attempt_records"].append(attempt_record)
                candidate_index = existing.get("candidate_index")
                if candidate_index is not None:
                    _merge_attempt_provenance(candidates[candidate_index], existing["attempt_records"])
            else:
                seen_claims[claim_id] = {
                    "fingerprint": fingerprint,
                    "attempt_identities": {attempt_identity},
                    "attempt_records": [attempt_record],
                    "candidate_index": None,
                }
                if document_id in selected_document_set:
                    seen_claims[claim_id]["candidate_index"] = len(candidates)
                    _merge_attempt_provenance(candidate, [attempt_record])
                    candidates.append(candidate)
            if document_id not in selected_document_set:
                excluded_claim_ids.add(claim_id)
    if selected_document_set - profile_document_ids:
        raise ValueError("Selected source document IDs must belong to documents of the selected report profile.")
    selection = {"selected_source_document_ids": selected_document_ids,
                 "excluded_claim_ids": sorted(excluded_claim_ids), "excluded_claim_count": len(excluded_claim_ids)}
    flags = {"preview_only": True, "review_status": "unreviewed", "canonical_write_allowed": False,
             "claim_promotion_allowed": False, "profile_write_allowed": False, "source_document_existence_verified": False}
    payload = {"@type": "CandidateEvidenceClaimSet", "profile_id": profile_id, "source_report": report_ref,
               "candidate_evidence_claims": candidates, **selection, **flags}
    output_dir = output_dir.resolve()
    claims_path, md_path = output_dir / "candidate_evidence_claims.json", output_dir / "candidate_evidence_claims.md"
    claims_raw = _report_json_bytes(payload)
    lines = ["# Claim candidati dal report fonte", "", f"Profilo: `{profile_id}`", f"Report SHA-256: `{report_ref['sha256']}`", "",
             f"Documenti selezionati: {', '.join(selected_document_ids)}", f"Claim esclusi: {len(excluded_claim_ids)}", "",
             "Candidate unreviewed; nessuna verifica del catalogo, decisione o promozione.", ""]
    for candidate in candidates:
        lines.extend([f"## {candidate['field']}: {candidate['value']}", "", f"Claim: `{candidate['claim_id']}`",
                      f"Fonte: `{candidate['source_id']}`; documento: `{candidate['source_document_id']}`",
                      f"URL: {candidate['url']}", f"Accesso: {candidate['access_date']}", "", candidate["quote"], ""])
    md_raw = ("\n".join(lines) + "\n").encode("utf-8")
    manifest = {"@type": "SourceReportCandidateClaimsManifest", "source_report": report_ref, "profile_id": profile_id,
                "selected_source_ids": selected_sources if selected_sources is not None else [],
                "source_selection_declared": selected_sources is not None,
                "claim_count": len(candidates), "source_document_ids": sorted({item["source_document_id"] for item in candidates}),
                "artifacts": {"candidate_claims": {"path": str(claims_path), "sha256": hashlib.sha256(claims_raw).hexdigest()},
                              "markdown": {"path": str(md_path), "sha256": hashlib.sha256(md_raw).hexdigest()}}, **selection, **flags}
    files = {claims_path.name: claims_raw, md_path.name: md_raw, "candidate_evidence_claims_manifest.json": _report_json_bytes(manifest)}
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError("Claims output must be a directory.")
        entries = list(output_dir.iterdir())
        if entries and (set(path.name for path in entries) != set(files)
                        or any(not (output_dir / name).is_file() or (output_dir / name).read_bytes() != data
                               for name, data in files.items())):
            raise ValueError("Claims output must be new, empty, or an identical prior preview.")
        if entries:
            return manifest
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (output_dir / name).write_bytes(data)
    return manifest


def _report_text(payload: Any, key: str, *, required: bool = True) -> str:
    if not isinstance(payload, dict):
        raise ValueError("Source report entries must be objects.")
    value = payload.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"Source report requires text field {key}.")
    return value


def _report_list(payload: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list) or any(not isinstance(item, dict) for item in payload[key]):
        raise ValueError(f"Source report requires an object list: {key}.")
    return payload[key]


def _report_attempt_ids(payload: dict[str, Any]) -> list[str]:
    return _report_identifier_list(payload, "selected_attempt_ids", required=False)


def _claim_semantic_fingerprint(candidate: dict[str, Any]) -> str:
    semantic = {key: value for key, value in candidate.items()
                if key not in {"selected_attempt_ids", "matched_planned_attempt_id"}}
    provenance = dict(semantic["provenance"])
    for key in ("result_index", "report_selected_attempt_ids", "result_selected_attempt_ids", "matched_planned_attempt_id"):
        provenance.pop(key, None)
    semantic["provenance"] = provenance
    return json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _merge_attempt_provenance(candidate: dict[str, Any], records: list[dict[str, Any]]) -> None:
    ordered = sorted(records, key=lambda item: (
        item["matched_planned_attempt_id"], item["result_index"],
        json.dumps(item["source_report_claim"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    ))
    candidate["attempt_provenance"] = ordered
    candidate["selected_attempt_ids"] = sorted({
        attempt_id
        for record in ordered
        for attempt_id in record["report_selected_attempt_ids"] + record["selected_attempt_ids"]
    })
    matched_attempt_ids = sorted({record["matched_planned_attempt_id"] for record in ordered
                                  if record["matched_planned_attempt_id"]})
    candidate["matched_planned_attempt_ids"] = matched_attempt_ids
    candidate["matched_planned_attempt_id"] = matched_attempt_ids[0] if matched_attempt_ids else ""
    candidate["provenance"]["result_index"] = min(record["result_index"] for record in ordered)
    candidate["provenance"]["result_indexes"] = sorted({record["result_index"] for record in ordered})
    candidate["provenance"]["report_selected_attempt_ids"] = sorted({
        attempt_id for record in ordered for attempt_id in record["report_selected_attempt_ids"]
    })
    candidate["provenance"]["result_selected_attempt_ids"] = sorted({
        attempt_id for record in ordered for attempt_id in record["selected_attempt_ids"]
    })
    candidate["provenance"]["matched_planned_attempt_ids"] = matched_attempt_ids


def _report_identifier_list(payload: dict[str, Any], key: str, *, required: bool = True) -> list[str]:
    values = payload.get(key, None if required else [])
    if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values) or len(values) != len(set(values)):
        raise ValueError(f"{key} must contain unique non-empty identifier strings.")
    return values


def _report_json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
