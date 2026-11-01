"""User-authorized ten-page empirical OCR cutoff and its scoped consumer.

This pilot is deliberately separate from the formal 5%/95% calibration and
holdout audit. It preserves human review status and never promotes archival
facts; it only emits an operational provisional disposition.
"""

from __future__ import annotations

from datetime import datetime, timezone
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


def build_provisional_threshold_dataset(*, confirmations_path: Path,
                                        sample_manifest_path: Path) -> dict[str, Any]:
    """Join ten completed human confirmations to their frozen package inputs."""
    form_path = Path(confirmations_path).resolve(strict=True)
    sample_path = Path(sample_manifest_path).resolve(strict=True)
    form, form_raw = _read_object(form_path, "Modulo conferme")
    sample, sample_raw = _read_object(sample_path, "Manifest sample pilot")
    if form.get("@type") != "OcrProvisionalThresholdConfirmationForm" or form.get("schema_version") != "1.0":
        raise ValueError("Richiesto OcrProvisionalThresholdConfirmationForm v1.0.")
    if Path(form.get("sample_manifest", "")).resolve() != sample_path:
        raise ValueError("Il modulo deve riferirsi al sample manifest esplicito.")
    if form.get("sample_manifest_sha256") != hashlib.sha256(sample_raw).hexdigest():
        raise ValueError("SHA-256 del sample manifest divergente dal modulo.")
    package_path = Path(form.get("review_package", "")).resolve(strict=True)
    package, package_raw = _read_object(package_path, "Package review")
    if package.get("@type") != "OcrReviewPackage" or package.get("schema_version") != "1.0":
        raise ValueError("Il package review deve essere OcrReviewPackage v1.0.")
    sample_ids = sample.get("page_ids")
    sample_hashes = sample.get("source_image_sha256")
    form_pages = form.get("pages")
    package_pages = package.get("pages")
    if (sample.get("@type") != "OcrProvisionalThresholdSample" or sample.get("schema_version") != "1.0"
            or sample.get("policy") != "operational_pilot" or sample.get("frozen_before_review") is not True
            or not isinstance(sample.get("pilot_id"), str) or not sample["pilot_id"].strip()
            or not isinstance(sample_ids, list) or len(sample_ids) != CONFIRMATION_COUNT
            or len(set(sample_ids)) != CONFIRMATION_COUNT or not isinstance(form_pages, list)
            or not isinstance(sample_hashes, dict) or set(sample_hashes) != set(sample_ids)
            or any(not _is_sha256(value) for value in sample_hashes.values())
            or len(form_pages) != CONFIRMATION_COUNT or not isinstance(package_pages, list)
            or len(package_pages) != CONFIRMATION_COUNT):
        raise ValueError("Sample, modulo e package devono contenere le stesse dieci pagine congelate.")
    package_by_id = {page.get("page_id"): page for page in package_pages if isinstance(page, dict)}
    form_by_id = {page.get("page_id"): page for page in form_pages if isinstance(page, dict)}
    if (set(package_by_id) != set(sample_ids) or set(form_by_id) != set(sample_ids)
            or len(package_by_id) != CONFIRMATION_COUNT or len(form_by_id) != CONFIRMATION_COUNT):
        raise ValueError("Package e modulo non corrispondono esattamente alle dieci page_id congelate.")
    form_digest = hashlib.sha256(form_raw).hexdigest()
    package_digest = hashlib.sha256(package_raw).hexdigest()
    if form.get("review_package_sha256") != package_digest:
        raise ValueError("SHA-256 del package review divergente dal modulo.")
    sample_digest = hashlib.sha256(sample_raw).hexdigest()
    submitted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if _timestamp(submitted_at, "dataset.reviewed_at") <= _timestamp(sample.get("frozen_at"), "sample.frozen_at"):
        raise ValueError("Il sample manifest deve essere congelato prima della compilazione delle conferme.")
    cases = []
    for page_id in sample_ids:
        item, packaged = form_by_id[page_id], package_by_id[page_id]
        if item.get("human_verified") is not True or type(item.get("accuracy_eligible")) is not bool:
            raise ValueError(f"{page_id}: la pagina deve essere verificata e avere accuracy_eligible booleano.")
        reviewer = item.get("reviewer_id")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError(f"{page_id}: reviewer_id mancante.")
        roles = packaged.get("review_inputs")
        if not isinstance(roles, dict) or any(role not in roles for role in ("image", "structure", "markdown")):
            raise ValueError(f"{page_id}: package privo di image/structure/markdown hash-bound.")
        image_path = Path(roles["image"]["path"]).resolve(strict=True)
        structure_path = Path(roles["structure"]["path"]).resolve(strict=True)
        markdown_path = Path(roles["markdown"]["path"]).resolve(strict=True)
        score_path = Path(item.get("score_path", "")).resolve(strict=True)
        feature_path = Path(item.get("features_path", "")).resolve(strict=True)
        hashes = {"image": _sha256_file(image_path), "structure": _sha256_file(structure_path),
                  "markdown": _sha256_file(markdown_path), "features": _sha256_file(feature_path),
                  "score": _sha256_file(score_path)}
        if (hashes["image"] != roles["image"].get("sha256") or hashes["image"] != item.get("image_sha256")
                or hashes["image"] != sample_hashes[page_id]
                or hashes["structure"] != item.get("candidate_structure_sha256")
                or hashes["markdown"] != item.get("candidate_markdown_sha256")
                or hashes["score"] != item.get("score_source_sha256")):
            raise ValueError(f"{page_id}: hash immagine/candidata/score divergente dal modulo o package.")
        score, _ = _read_object(score_path, f"Score {page_id}")
        features, _ = _read_object(feature_path, f"Risk features {page_id}")
        feature_inputs = features.get("inputs")
        if not isinstance(feature_inputs, dict):
            raise ValueError(f"{page_id}: feature bundle privo di input hash-bound.")
        score_inputs = score.get("inputs")
        score_bundle = score_inputs.get("bundle") if isinstance(score_inputs, dict) else None
        if not isinstance(score_bundle, dict):
            raise ValueError(f"{page_id}: score privo del binding al feature bundle.")
        for role in ("image", "structure", "markdown", "evidence", "lexicon_review", "comparison"):
            package_ref, feature_ref = roles.get(role), feature_inputs.get(role)
            if (not isinstance(package_ref, dict) or not isinstance(feature_ref, dict)
                    or Path(package_ref.get("path", "")).resolve() != Path(feature_ref.get("path", "")).resolve()
                    or package_ref.get("sha256") != feature_ref.get("sha256")
                    or _sha256_file(Path(package_ref["path"])) != package_ref.get("sha256")):
                raise ValueError(f"{page_id}: feature input {role} diverge dal package o dal suo hash.")
        comparison, _ = _read_object(Path(roles["comparison"]["path"]), f"Comparison {page_id}")
        for side in ("left", "right"):
            comparison_ref = comparison.get("inputs", {}).get(side, {})
            feature_ref = feature_inputs.get(side, {})
            if (not isinstance(comparison_ref, dict) or not isinstance(feature_ref, dict)
                    or Path(comparison_ref.get("path", "")).resolve() != Path(feature_ref.get("path", "")).resolve()
                    or comparison_ref.get("sha256") != feature_ref.get("sha256")
                    or _sha256_file(Path(comparison_ref["path"])) != comparison_ref.get("sha256")):
                raise ValueError(f"{page_id}: evidence {side} diverge dal confronto hash-bound.")
        identity = score.get("candidate_identity")
        _validate_score_identity(identity)
        if (score.get("@type") != "OcrRiskScore" or score.get("score_status") != "diagnostic_only"
                or Path(score_bundle.get("path", "")).resolve() != feature_path
                or score_bundle.get("sha256") != hashes["features"]
                or features.get("@type") != "OcrRiskFeatureBundle"
                or features.get("candidate_identity") != identity
                or identity.get("page_id") != page_id or identity.get("source_image_hash") != hashes["image"]
                or identity.get("profile") != item.get("profile") or packaged.get("profile") != item.get("profile")
                or (item.get("candidate_identity") is not None and item["candidate_identity"] != identity)
                or item.get("score") != score.get("risk_score")):
            raise ValueError(f"{page_id}: score diagnostico non concorda con identita' o modulo.")
        source_binding = features.get("source_document_binding")
        right_ref = features.get("inputs", {}).get("right", {})
        if (not isinstance(source_binding, dict) or not isinstance(right_ref, dict)
                or source_binding.get("source_document_id") != identity.get("source_document_id")
                or source_binding.get("page_id") != page_id
                or source_binding.get("source_image_hash") != hashes["image"]
                or source_binding.get("evidence_sha256") != right_ref.get("sha256")):
            raise ValueError(f"{page_id}: binding archivistico delle risk features non valido.")
        right_path = Path(right_ref.get("path", "")).resolve(strict=True)
        if _sha256_file(right_path) != right_ref.get("sha256"):
            raise ValueError(f"{page_id}: evidence Tesseract modificata dopo il calcolo dello score.")
        right_evidence, _ = _read_object(right_path, f"Evidence Tesseract {page_id}")
        if (right_evidence.get("source_document_id") != identity.get("source_document_id")
                or right_evidence.get("page_id") != page_id
                or right_evidence.get("source_image_hash") != hashes["image"]):
            raise ValueError(f"{page_id}: evidence Tesseract non concorda con il legame candidato.")
        if item["accuracy_eligible"]:
            words, errors, categories = (item.get("reference_word_count"),
                                         item.get("material_word_error_count"),
                                         item.get("material_error_categories"))
            if (type(words) is not int or words < 1 or type(errors) is not int or errors < 0 or errors > words
                    or not isinstance(categories, list)
                    or any(category not in MATERIAL_ERROR_CATEGORIES for category in categories)
                    or len(set(categories)) != len(categories) or bool(categories) != (errors > 0)):
                raise ValueError(f"{page_id}: conteggi reference/errori o categorie non validi.")
        else:
            if any(item.get(field) is not None for field in (
                    "reference_word_count", "material_word_error_count", "material_error_categories")):
                raise ValueError(f"{page_id}: metriche reference devono restare null se non accuracy-eligible.")
            words = errors = categories = None
            reason = item.get("accuracy_ineligibility_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"{page_id}: spiegare perche' la pagina non e' accuracy-eligible.")
        cases.append({
            "page_id": page_id, "partition": "operational_pilot",
            "review_status": "human_verified", "accuracy_eligible": item["accuracy_eligible"],
            "confirmed_at": submitted_at, "reviewer_id": reviewer,
            "source_document_id": identity["source_document_id"],
            "reference_id": f"manual-count:{form_digest}:{page_id}",
            "source_image_sha256": hashes["image"],
            "candidate_structure_sha256": hashes["structure"],
            "candidate_markdown_sha256": hashes["markdown"],
            "reference_evaluation_sha256": form_digest,
            "score_source_sha256": hashes["score"], "candidate_identity": identity,
            "profile": item["profile"], "score": score["risk_score"],
            "reference_word_count": words, "material_word_error_count": errors,
            "material_error_categories": categories,
            "accuracy_ineligibility_reason": item.get("accuracy_ineligibility_reason") if not item["accuracy_eligible"] else None,
        })
    return {
        "@type": "OcrProvisionalThresholdDataset", "schema_version": "1.0",
        "pilot_id": sample["pilot_id"], "reviewed_at": submitted_at,
        "sample_manifest_sha256": sample_digest,
        "confirmation_form": {"path": str(form_path), "sha256": form_digest},
        "review_package": {"path": str(package_path), "sha256": package_digest},
        "score_name": "ocr-coverage-disagreement-max-v1", "score_spec": SCORE_SPEC,
        "cases": cases,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    eligible_cases = [case for case in cases if case["accuracy_eligible"] is True]
    bad_scores = sorted({case["score"] for case in eligible_cases
                         if case["material_word_error_count"] / case["reference_word_count"]
                         > MAX_PAGE_MATERIAL_WORD_ERROR_RATE})
    candidate_cutoffs = sorted({case["score"] for case in eligible_cases
                                if case["material_word_error_count"] / case["reference_word_count"]
                                <= MAX_PAGE_MATERIAL_WORD_ERROR_RATE})
    safe_cutoffs = [cutoff for cutoff in candidate_cutoffs
                    if not any(score <= cutoff for score in bad_scores)]
    discriminating_cutoffs = [value for value in safe_cutoffs if value < 1.0]
    cutoff = max(discriminating_cutoffs) if len(eligible_cases) == CONFIRMATION_COUNT and discriminating_cutoffs else None
    accepted = [case for case in eligible_cases if cutoff is not None and case["score"] <= cutoff]
    breaches = [case for case in accepted
                if case["material_word_error_count"] / case["reference_word_count"]
                > MAX_PAGE_MATERIAL_WORD_ERROR_RATE]
    scopes_by_key = {_canonical(scope): scope for scope in
                     (_scope(case["candidate_identity"], case["profile"]) for case in cases)}
    scopes = sorted(scopes_by_key.values(), key=lambda value: (
        value["language"], value["engine"], _canonical(value["model"]), value["profile"]))
    no_go_reason = ("insufficient_accuracy_eligible_confirmations"
                    if len(eligible_cases) != CONFIRMATION_COUNT else
                    ("no_discriminating_cutoff_below_max_score" if cutoff is None and safe_cutoffs
                     and all(value >= 1.0 for value in safe_cutoffs) else
                     ("no_cutoff_separates_page_limit_breaches" if cutoff is None else None)))
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
                     "accuracy_eligible_case_count": len(eligible_cases),
                     "accuracy_ineligible_page_ids": [case["page_id"] for case in cases
                                                      if case["accuracy_eligible"] is not True],
                     "page_limit_breach_count": sum(
                         case["material_word_error_count"] / case["reference_word_count"]
                         > MAX_PAGE_MATERIAL_WORD_ERROR_RATE for case in eligible_cases),
                     "accepted_page_limit_breach_count": len(breaches),
                     "cutoff_selection": "largest_safe_observed_score_below_1.0; score_1.0_always_requires_manual_review"},
        "no_go_reason": no_go_reason,
        "status": "provisional_cutoff_frozen" if cutoff is not None else "no_go_no_supported_provisional_cutoff",
        "provisional_auto_acceptance_enabled": cutoff is not None,
        "machine_pass": False, "auto_validation_enabled": cutoff is not None,
        "auto_validation_mode": "provisional_empirical_scoped" if cutoff is not None else None,
        "human_verified": False, "review_status": "unreviewed",
        "semantic_accuracy_status": "not_attested", "claim_extraction_allowed": False,
        "limitations": [
            "Empirical cutoff selected on ten tuning cases; no formal false-acceptance rate or 5%/95% guarantee is established.",
            "The maximum diagnostic score 1.0 is never auto-accepted because it cannot define a discriminating cutoff.",
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
    accepted = (threshold["status"] == "provisional_cutoff_frozen" and in_scope
                and score_value <= cutoff)
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
        "reason": ("within_provisional_cutoff" if accepted else
                   ("no_supported_provisional_cutoff" if threshold["status"] != "provisional_cutoff_frozen" else
                    ("outside_supported_scope" if not in_scope else "score_above_cutoff"))),
        "provisional_auto_acceptance": accepted,
        "transcription_validation_status": "provisional_auto_validated" if accepted else "manual_review_required",
        "auto_validation_scope": scope if accepted else None,
        "machine_pass": False, "auto_validation_enabled": accepted,
        "auto_validation_mode": "provisional_empirical_scoped" if accepted else None,
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
    if dataset.get("pilot_id") != sample.get("pilot_id"):
        raise ValueError("pilot_id divergente dal sample manifest congelato.")
    ids = sample.get("page_ids")
    cases = dataset.get("cases")
    if (not isinstance(ids, list) or len(ids) != CONFIRMATION_COUNT
            or any(not isinstance(item, str) or not item.strip() for item in ids)
            or len(set(ids)) != CONFIRMATION_COUNT):
        raise ValueError("Il sample manifest deve contenere esattamente dieci page_id unici.")
    if not isinstance(cases, list) or len(cases) != CONFIRMATION_COUNT:
        raise ValueError("Il dataset deve contenere esattamente dieci conferme reali.")
    sample_hashes = sample.get("source_image_sha256")
    if (not isinstance(sample_hashes, dict) or set(sample_hashes) != set(ids)
            or any(not _is_sha256(value) for value in sample_hashes.values())):
        raise ValueError("Il sample manifest deve legare uno SHA-256 immagine a ogni pagina.")
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
                or type(case.get("accuracy_eligible")) is not bool):
            raise ValueError("Ogni conferma deve essere human_verified e dichiarare accuracy_eligible.")
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
        if sample_hashes.get(page_id) != image_hash:
            raise ValueError("source_image_sha256 divergente dal sample manifest congelato.")
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
        if case["accuracy_eligible"]:
            word_count = case.get("reference_word_count")
            error_count = case.get("material_word_error_count")
            for field, minimum in (("material_word_error_count", 0), ("reference_word_count", 1)):
                value = case.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                    raise ValueError(f"{field} non valido.")
            if error_count > word_count:
                raise ValueError("material_word_error_count non puo' superare reference_word_count.")
            categories = case.get("material_error_categories")
            if (not isinstance(categories, list)
                    or any(item not in MATERIAL_ERROR_CATEGORIES for item in categories)
                    or len(set(categories)) != len(categories)
                    or bool(categories) != (error_count > 0)):
                raise ValueError("material_error_categories incomplete o non valide.")
        elif any(case.get(field) is not None for field in (
                "material_word_error_count", "reference_word_count", "material_error_categories")):
            raise ValueError("Pagina non accuracy-eligible: metriche reference devono essere null.")
        elif not isinstance(case.get("accuracy_ineligibility_reason"), str) \
                or not case["accuracy_ineligibility_reason"].strip():
            raise ValueError("Pagina non accuracy-eligible: motivazione richiesta.")
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
    if not isinstance(threshold, dict):
        raise ValueError("Artifact cutoff provisional senza threshold.")
    status = payload.get("status")
    cutoff = threshold.get("cutoff")
    frozen = status == "provisional_cutoff_frozen"
    no_go = status == "no_go_no_supported_provisional_cutoff"
    if ((frozen and (payload.get("provisional_auto_acceptance_enabled") is not True
                     or payload.get("auto_validation_enabled") is not True
                     or payload.get("auto_validation_mode") != "provisional_empirical_scoped"
                     or isinstance(cutoff, bool) or not isinstance(cutoff, (int, float))
                     or payload.get("no_go_reason") is not None))
            or (no_go and (payload.get("provisional_auto_acceptance_enabled") is not False
                           or payload.get("auto_validation_enabled") is not False
                           or payload.get("auto_validation_mode") is not None or cutoff is not None))
            or (no_go and (not isinstance(payload.get("no_go_reason"), str)
                           or not payload["no_go_reason"].strip()))
            or not (frozen or no_go)):
        raise ValueError("Artifact cutoff provisional senza decisione valida.")
    if ((frozen and (not math.isfinite(cutoff) or cutoff < 0 or cutoff >= 1.0))
            or threshold.get("direction") != "lower_is_safer"
            or threshold.get("max_page_material_word_error_rate") != MAX_PAGE_MATERIAL_WORD_ERROR_RATE
            or threshold.get("score_spec") != SCORE_SPEC):
        raise ValueError("Campi cutoff non validi.")
    scopes = threshold.get("scope")
    if not isinstance(scopes, list) or not scopes:
        raise ValueError("Scope threshold mancante.")
