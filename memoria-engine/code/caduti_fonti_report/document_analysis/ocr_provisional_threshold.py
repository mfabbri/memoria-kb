"""User-authorized ten-page empirical OCR cutoff and its scoped consumer.

This pilot is deliberately separate from the formal 5%/95% calibration and
holdout audit. It preserves human review status and never promotes archival
facts; it only emits an operational provisional disposition.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .ocr_risk_score import SCORE_SPEC
from .ocr_threshold_audit import MAX_PAGE_MATERIAL_WORD_ERROR_RATE, MATERIAL_ERROR_CATEGORIES, _is_sha256


CONFIRMATION_COUNT = 10


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _read_object(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = Path(path).read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: JSON non valido.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}: oggetto JSON richiesto.")
    _canonical(payload)
    return payload, raw


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} mancante.")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} non valido.") from exc
    if result.utcoffset() is None:
        raise ValueError(f"{field} richiede un fuso orario.")
    return result


def calibrate_provisional_ocr_threshold(*, dataset_path: Path,
                                        sample_manifest_path: Path) -> dict[str, Any]:
    """Freeze an empirical cutoff from exactly ten manually confirmed pages."""
    dataset, dataset_raw = _read_object(Path(dataset_path), "Dataset pilot")
    sample, sample_raw = _read_object(Path(sample_manifest_path), "Manifest sample pilot")
    _validate_sample(dataset, sample, sample_raw)
    cases = dataset["cases"]
    sample_digest = hashlib.sha256(sample_raw).hexdigest()
    dataset_digest = hashlib.sha256(dataset_raw).hexdigest()

    bad_scores = sorted({case["score"] for case in cases
                         if case["material_word_error_count"] / case["reference_word_count"]
                         > MAX_PAGE_MATERIAL_WORD_ERROR_RATE})
    candidate_cutoffs = sorted({case["score"] for case in cases
                                if case["material_word_error_count"] / case["reference_word_count"]
                                <= MAX_PAGE_MATERIAL_WORD_ERROR_RATE})
    safe_cutoffs = [cutoff for cutoff in candidate_cutoffs
                    if not any(score <= cutoff for score in bad_scores)]
    cutoff = max(safe_cutoffs) if safe_cutoffs else None
    accepted = [case for case in cases if cutoff is not None and case["score"] <= cutoff]
    breaches = [case for case in accepted
                if case["material_word_error_count"] / case["reference_word_count"]
                > MAX_PAGE_MATERIAL_WORD_ERROR_RATE]
    scopes_by_key = {_canonical(scope): scope for scope in
                     (_scope(case["candidate_identity"], case["profile"]) for case in cases)}
    scopes = sorted(scopes_by_key.values(), key=lambda value: (
        value["language"], value["engine"], _canonical(value["model"]), value["profile"]))
    report: dict[str, Any] = {
        "@type": "OcrProvisionalThresholdArtifact", "schema_version": "1.0",
        "policy": "user_authorized_ten_case_empirical_pilot",
        "dataset": {"path": str(Path(dataset_path).resolve()), "sha256": dataset_digest},
        "sample_manifest": {"path": str(Path(sample_manifest_path).resolve()), "sha256": sample_digest},
        "confirmation_count": len(cases), "required_confirmation_count": CONFIRMATION_COUNT,
        "threshold": {"score_name": dataset["score_name"], "score_spec": SCORE_SPEC,
                      "direction": "lower_is_safer", "cutoff": cutoff,
                      "max_page_material_word_error_rate": MAX_PAGE_MATERIAL_WORD_ERROR_RATE,
                      "scope": scopes},
        "observed": {"reviewed_case_count": len(cases), "accepted_case_count": len(accepted),
                     "page_limit_breach_count": sum(
                         case["material_word_error_count"] / case["reference_word_count"]
                         > MAX_PAGE_MATERIAL_WORD_ERROR_RATE for case in cases),
                     "accepted_page_limit_breach_count": len(breaches),
                     "cutoff_selection": "largest_observed_score_with_no_accepted_page_over_2_percent_including_ties"},
        "status": "provisional_cutoff_frozen" if cutoff is not None else "no_go_no_supported_provisional_cutoff",
        "provisional_auto_acceptance_enabled": cutoff is not None,
        "machine_pass": False, "auto_validation_enabled": False,
        "human_verified": False, "review_status": "unreviewed",
        "semantic_accuracy_status": "not_attested", "claim_extraction_allowed": False,
        "limitations": [
            "Empirical cutoff selected on ten tuning cases; no formal false-acceptance rate or 5%/95% guarantee is established.",
            "Scope is limited to the exact language, engine, model and structure profiles represented by the ten cases.",
            "This artifact never marks future pages human_verified and never promotes archival claims.",
        ],
    }
    report["artifact_payload_sha256"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def evaluate_provisional_ocr_threshold(*, threshold_path: Path, score_path: Path,
                                       output_path: Path, apply: bool = False) -> dict[str, Any]:
    """Apply a frozen provisional cutoff to one diagnostic score, fail-closed."""
    threshold, threshold_raw = _read_object(Path(threshold_path), "Artifact cutoff provisional")
    score, score_raw = _read_object(Path(score_path), "Score OCR")
    _validate_threshold_artifact(threshold)
    identity = score.get("candidate_identity")
    if (score.get("@type") != "OcrRiskScore" or score.get("schema_version") != "1.0"
            or score.get("score_status") != "diagnostic_only"
            or score.get("direction") != "lower_is_safer"
            or not isinstance(identity, dict)):
        raise ValueError("Serve OcrRiskScore diagnostico con identita' candidata.")
    _validate_score_identity(identity)
    score_value = score.get("risk_score")
    if (isinstance(score_value, bool) or not isinstance(score_value, (int, float))
            or not math.isfinite(score_value) or not 0 <= score_value <= 1):
        raise ValueError("Lo score candidato non e' finito o fuori dall'intervallo diagnostico [0, 1].")
    source_score = score.get("inputs", {}).get("bundle", {}).get("sha256") \
        if isinstance(score.get("inputs"), dict) else None
    if not _is_sha256(source_score):
        raise ValueError("Lo score non lega uno sha256 valido al feature bundle.")
    cutoff = threshold["threshold"]["cutoff"]
    scope = _scope(identity, identity["profile"])
    in_scope = scope in threshold["threshold"]["scope"]
    accepted = in_scope and score_value <= cutoff
    report = {
        "@type": "OcrProvisionalThresholdDecision", "schema_version": "1.0",
        "inputs": {"threshold": {"path": str(Path(threshold_path).resolve()),
                                  "sha256": hashlib.sha256(threshold_raw).hexdigest()},
                   "score": {"path": str(Path(score_path).resolve()),
                             "sha256": hashlib.sha256(score_raw).hexdigest()},
                   "score_source_bundle_sha256": source_score},
        "candidate_identity": identity, "score": score_value, "cutoff": cutoff,
        "scope_match": in_scope,
        "operational_disposition": "provisional_auto_accept" if accepted else "manual_review_required",
        "reason": "within_provisional_cutoff" if accepted else ("outside_supported_scope" if not in_scope else "score_above_cutoff"),
        "provisional_auto_acceptance": accepted,
        "machine_pass": False, "auto_validation_enabled": False,
        "human_verified": False, "review_status": "unreviewed",
        "semantic_accuracy_status": "not_attested", "claim_extraction_allowed": False,
    }
    report["decision_payload_sha256"] = hashlib.sha256(_canonical(report)).hexdigest()
    target = Path(output_path).resolve()
    inputs = {Path(threshold_path).resolve(), Path(score_path).resolve()}
    if target in inputs or target.exists():
        raise ValueError("Output decision deve essere un file nuovo e distinto dagli input.")
    if apply:
        if not target.parent.is_dir():
            raise ValueError("La directory output deve esistere.")
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    return report | {"operation_status": "written" if apply else "preview", "output_path": str(target)}


def _validate_sample(dataset: dict[str, Any], sample: dict[str, Any], sample_raw: bytes) -> None:
    if dataset.get("@type") != "OcrProvisionalThresholdDataset" or dataset.get("schema_version") != "1.0":
        raise ValueError("Richiesto OcrProvisionalThresholdDataset v1.0.")
    if sample.get("@type") != "OcrProvisionalThresholdSample" or sample.get("schema_version") != "1.0":
        raise ValueError("Richiesto OcrProvisionalThresholdSample v1.0.")
    if sample.get("policy") != "operational_pilot" or sample.get("frozen_before_review") is not True:
        raise ValueError("Il manifest deve essere il sample operativo congelato prima della review.")
    frozen_at = _timestamp(sample.get("frozen_at"), "sample.frozen_at")
    reviewed_at = _timestamp(dataset.get("reviewed_at"), "dataset.reviewed_at")
    if reviewed_at <= frozen_at:
        raise ValueError("Il campione deve essere congelato prima delle conferme.")
    ids = sample.get("page_ids")
    cases = dataset.get("cases")
    if (not isinstance(ids, list) or len(ids) != CONFIRMATION_COUNT
            or any(not isinstance(item, str) or not item.strip() for item in ids)
            or len(set(ids)) != CONFIRMATION_COUNT):
        raise ValueError("Il sample manifest deve contenere esattamente dieci page_id unici.")
    if not isinstance(cases, list) or len(cases) != CONFIRMATION_COUNT:
        raise ValueError("Il dataset deve contenere esattamente dieci conferme reali.")
    if dataset.get("score_name") != "ocr-coverage-disagreement-max-v1" \
            or dataset.get("score_spec") != SCORE_SPEC:
        raise ValueError("Il dataset deve usare lo score diagnostico versionato del CLI.")
    if not isinstance(dataset.get("pilot_id"), str) or not dataset["pilot_id"].strip():
        raise ValueError("pilot_id mancante.")
    if dataset.get("sample_manifest_sha256") != hashlib.sha256(sample_raw).hexdigest():
        raise ValueError("Il dataset deve dichiarare lo SHA-256 esatto del sample manifest.")
    seen_pages: set[str] = set()
    seen_images: set[str] = set()
    for case in cases:
        if (not isinstance(case, dict) or case.get("review_status") != "human_verified"
                or case.get("accuracy_eligible") is not True):
            raise ValueError("Ogni conferma deve essere human_verified e accuracy_eligible.")
        page_id = case.get("page_id")
        if page_id in seen_pages:
            raise ValueError("page_id duplicato nel campione.")
        seen_pages.add(page_id)
        if case.get("partition") != "operational_pilot" or page_id not in ids:
            raise ValueError("Ogni caso deve appartenere al sample operativo congelato.")
        if _timestamp(case.get("confirmed_at"), "case.confirmed_at") < frozen_at:
            raise ValueError("La conferma precede il freeze del campione.")
        for field in ("source_document_id", "reference_id"):
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} mancante.")
        document_id = case["source_document_id"]
        image_hash = case.get("source_image_sha256")
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("source_document_id mancante o non valido.")
        if not _is_sha256(image_hash) or image_hash in seen_images:
            raise ValueError("source_image_sha256 duplicato o non valido.")
        seen_images.add(image_hash)
        for field in ("candidate_structure_sha256", "candidate_markdown_sha256",
                      "reference_evaluation_sha256", "score_source_sha256"):
            if not _is_sha256(case.get(field)):
                raise ValueError(f"{field} non valido.")
        identity = case.get("candidate_identity")
        if not isinstance(identity, dict):
            raise ValueError("candidate_identity mancante.")
        _validate_score_identity(identity)
        if identity.get("source_document_id") != document_id or identity.get("page_id") != page_id \
                or identity.get("source_image_hash") != image_hash or identity.get("profile") != case.get("profile"):
            raise ValueError("Identita' candidata divergente dall'immagine/documento del caso.")
        score = case.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("score non valido.")
        for field, minimum in (("material_word_error_count", 0), ("reference_word_count", 1)):
            value = case.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{field} non valido.")
        categories = case.get("material_error_categories")
        if (not isinstance(categories, list)
                or any(item not in MATERIAL_ERROR_CATEGORIES for item in categories)
                or len(set(categories)) != len(categories)
                or bool(categories) != (case["material_word_error_count"] > 0)):
            raise ValueError("material_error_categories incomplete o non valide.")
    if seen_pages != set(ids):
        raise ValueError("Dataset e sample manifest non hanno le stesse dieci pagine.")


def _validate_score_identity(identity: Any) -> None:
    if not isinstance(identity, dict):
        raise ValueError("candidate_identity deve essere un oggetto.")
    for field in ("source_document_id", "page_id", "source_image_hash", "engine", "language", "profile"):
        value = identity.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"candidate_identity.{field} mancante.")
    for field in ("model", "image_transform", "source_page"):
        if not isinstance(identity.get(field), dict) or not identity[field]:
            raise ValueError(f"candidate_identity.{field} mancante.")
    if not _is_sha256(identity.get("source_image_hash")):
        raise ValueError("candidate_identity.source_image_hash non valido.")


def _scope(identity: dict[str, Any], profile: str) -> dict[str, Any]:
    return {"language": identity["language"], "engine": identity["engine"],
            "model": identity["model"], "profile": profile}


def _validate_threshold_artifact(payload: dict[str, Any]) -> None:
    digest = payload.get("artifact_payload_sha256")
    unsigned = {key: value for key, value in payload.items() if key != "artifact_payload_sha256"}
    if payload.get("@type") != "OcrProvisionalThresholdArtifact" or payload.get("schema_version") != "1.0":
        raise ValueError("Artifact cutoff provisional non supportato.")
    if not _is_sha256(digest) or hashlib.sha256(_canonical(unsigned)).hexdigest() != digest:
        raise ValueError("Digest artifact cutoff non corrispondente.")
    threshold = payload.get("threshold")
    if not isinstance(threshold, dict) or payload.get("status") != "provisional_cutoff_frozen" \
            or payload.get("provisional_auto_acceptance_enabled") is not True:
        raise ValueError("Artifact senza cutoff provisional utilizzabile.")
    cutoff = threshold.get("cutoff")
    if (isinstance(cutoff, bool) or not isinstance(cutoff, (int, float))
            or not math.isfinite(cutoff) or cutoff < 0
            or threshold.get("direction") != "lower_is_safer"
            or threshold.get("max_page_material_word_error_rate") != MAX_PAGE_MATERIAL_WORD_ERROR_RATE
            or threshold.get("score_spec") != SCORE_SPEC):
        raise ValueError("Campi cutoff non validi.")
    scopes = threshold.get("scope")
    if not isinstance(scopes, list) or not scopes:
        raise ValueError("Scope threshold mancante.")
