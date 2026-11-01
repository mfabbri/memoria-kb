"""Explicit T36 -> T37 workflow, optionally with diagnostic Tesseract.

OcrWorkflow v1 declares t36.input_manifest {path, sha256}, language, model
(ocr_version, detection/recognition names and local directories), runtime
(device, enable_mkldnn, text_det_limit_side_len/type, tile_width/height/overlap,
retry_limit), and t37 {variant_id, page_profiles}. Paths resolve at the manifest.
OcrWorkflow v1.1 additionally requires tesseract {root_dir, language,
tesseract_path, page_segmentation_mode, engine_mode, dpi, preprocess_before_ocr,
enable_region_ocr, pages}. Each page binds page_id/source_id/source_document_id
and sidecar/metadata {path, sha256}; the TIFF binding derives from T36 inputs.
OcrWorkflow v1.2 adds review {lexicons, glossaries}, each an exact page_id map
of {path, sha256}. It requires raw single-frame inputs and original-pixel
Tesseract in the same language. The package builder derives its own T37 copy
without inference; this is separate from the immutable workflow t37 stage.
OcrWorkflow v1.3 keeps the v1.2 sections and accepts native TIFF/JPEG with
TesseractPageBatchManifest v1.1/raw_image and raw-pixel-only PSM retries.
OcrWorkflow v1.4 additionally consumes a hash-bound provisional threshold
after evidence, structure, comparison and review-package preparation. It emits
page-scoped score/decision sidecars and routes unaccepted pages to manual review.
Non-comparable diagnostic text blocks the evidence and review stages.
T37 always consumes only T36 evidence. Tesseract stages are diagnostic_only and
unreviewed, including partial runtime results, and are immutable on resume.
The wrapper owns workflow-request.json, workflow-state.json and the derived
tesseract/page-batch-manifest.json; stage owners publish other artifacts.
"""
from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
from pathlib import Path
from typing import Any

from . import ocr_transform_batch as batch
from . import ocr_transform_pilot as pilot
from . import ocr_transform_structure as structure
from . import ocr_tesseract_page_batch as tesseract_batch
from . import ocr_tesseract_from_t36 as tesseract_evidence
from . import ocr_review_package as review_package
from . import ocr_lexicon_candidates as lexical
from . import ocr_candidate_assessment as candidate_assessment
from . import ocr_risk_features as risk_features
from . import ocr_risk_score as risk_score
from . import ocr_provisional_threshold as provisional_threshold
from .ocr_tesseract import CommandRunner

MAX_MANUAL_REVIEW_RATE = 0.03


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=structure._unique_object,
                       parse_constant=structure._reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f"Oggetto JSON richiesto: {path}")
    return value


def _keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"Campi {label} richiesti: {', '.join(sorted(expected))}.")


def _path(root: Path, value: Any) -> Path:
    path = Path(pilot._required_text(value, "path"))
    return (path if path.is_absolute() else root / path).resolve(strict=True)


def _prepare(manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = manifest_path.resolve(strict=True)
    payload = _read(source)
    version = payload.get("schema_version")
    if payload.get("@type") != "OcrWorkflow" or version not in {"1.0", "1.1", "1.2", "1.3", "1.4"}:
        raise ValueError("E' richiesto OcrWorkflow v1.0-v1.4.")
    _keys(payload, {"@type", "schema_version", "t36", "t37"}
          | ({"tesseract"} if version != "1.0" else set())
          | ({"review"} if version in {"1.2", "1.3", "1.4"} else set())
          | ({"provisional_threshold"} if version == "1.4" else set()), "workflow")
    t36, t37 = payload["t36"], payload["t37"]
    _keys(t36, {"input_manifest", "language", "model", "runtime"}, "t36")
    _keys(t36["input_manifest"], {"path", "sha256"}, "t36.input_manifest")
    inputs = _path(source.parent, t36["input_manifest"]["path"])
    if pilot._sha256_file(inputs) != structure._required_sha256(t36["input_manifest"]["sha256"], "input_manifest.sha256"):
        raise ValueError("SHA-256 manifest input T36 divergente.")
    if version != "1.0":
        _read(inputs)  # The v1.1 input boundary also rejects duplicate JSON keys.
    pages = batch._inputs(inputs)
    if version in {"1.1", "1.2"} and any(Path(page["path"]).suffix.lower() not in {".tif", ".tiff"} for page in pages):
        raise ValueError("OcrWorkflow v1.1/v1.2 con Tesseract/review richiede input TIFF; JPEG richiede v1.0 o v1.3.")
    model = t36["model"]
    model_fields = {"ocr_version", "text_detection_model_name", "text_recognition_model_name"}
    _keys(model, model_fields | {"text_detection_model_dir", "text_recognition_model_dir"}, "t36.model")
    directories = {key: _path(source.parent, model[key]) for key in ("text_detection_model_dir", "text_recognition_model_dir")}
    identity = pilot.local_paddle_checkpoint_identity(**directories)
    runtime = t36["runtime"]
    _keys(runtime, {"device", "enable_mkldnn", "text_det_limit_side_len", "text_det_limit_type",
                    "tile_width", "tile_height", "tile_overlap", "retry_limit"}, "t36.runtime")
    _keys(t37, {"variant_id", "page_profiles"}, "t37")
    if not isinstance(t37["variant_id"], str) or t37["variant_id"] not in structure._VARIANTS:
        raise ValueError("Variante T37 non supportata.")
    profiles = t37["page_profiles"]
    if (not isinstance(profiles, dict) or set(profiles) != {p["page_id"] for p in pages}
            or any(not isinstance(v, str) or v not in structure._PROFILES for v in profiles.values())):
        raise ValueError("page_profiles deve dichiarare esattamente ogni page_id con profilo supportato.")
    options = dict(manifest_path=inputs, language=t36["language"],
                   model={key: model[key] for key in model_fields}, runtime_identity=identity, **runtime)
    factory_options = {key: value for key, value in runtime.items()
                       if key in {"device", "enable_mkldnn", "text_det_limit_side_len", "text_det_limit_type"}}
    factory_options.update(language=t36["language"], **directories,
                           text_detection_model_name=model["text_detection_model_name"],
                           text_recognition_model_name=model["text_recognition_model_name"])
    request = {"@type": "OcrWorkflowRequest", "schema_version": version,
               "workflow_manifest": {"path": str(source), "sha256": pilot._sha256_file(source)},
               "t36": {"input_manifest": {"path": str(inputs), "sha256": pilot._sha256_file(inputs)},
                       "inputs": pages, "language": t36["language"], "model": model | {k: str(v) for k, v in directories.items()},
                       "runtime": runtime, "runtime_identity": identity}, "t37": t37}
    if version != "1.0":
        section = payload["tesseract"]
        configuration = {"language", "tesseract_path", "page_segmentation_mode", "engine_mode", "dpi",
                         "preprocess_before_ocr", "enable_region_ocr"}
        _keys(section, configuration | {"root_dir", "pages"}, "tesseract")
        for name in ("language", "tesseract_path"):
            pilot._required_text(section[name], name)
        for name in ("preprocess_before_ocr", "enable_region_ocr"):
            if type(section[name]) is not bool:
                raise ValueError(f"{name} deve essere booleano.")
        for name, maximum in (("page_segmentation_mode", 13), ("engine_mode", 3), ("dpi", None)):
            value = section[name]
            if (not isinstance(value, str) or (value != "" and
                    (not value.isascii() or not value.isdigit() or
                     (maximum is not None and int(value) > maximum) or (name == "dpi" and int(value) == 0)))):
                raise ValueError(f"Configurazione Tesseract non valida: {name}.")
        if not isinstance(section["pages"], list) or not section["pages"]:
            raise ValueError("Pagine Tesseract richieste.")
        bound = []
        by_id = {page["page_id"]: page for page in pages}
        for page in section["pages"]:
            _keys(page, {"page_id", "source_id", "source_document_id", "sidecar", "metadata"}, "pagina tesseract")
            if not isinstance(page["page_id"], str) or page["page_id"] not in by_id:
                raise ValueError("page_id Tesseract sconosciuto.")
            references = {}
            for role in ("sidecar", "metadata"):
                _keys(page[role], {"path", "sha256"}, role)
                references[role] = {"path": str(_path(source.parent, page[role]["path"])),
                                    "sha256": structure._required_sha256(page[role]["sha256"], role)}
            raw = by_id[page["page_id"]]
            raw_role = "raw_image" if version == "1.3" else "raw_tiff"
            bound.append(page | references | {raw_role: {"path": raw["path"], "sha256": raw["sha256"]}})
        request["tesseract"] = {"root_dir": str(_path(source.parent, section["root_dir"])),
                                "configuration": {key: section[key] for key in sorted(configuration)}, "pages": bound}
    if version in {"1.2", "1.3", "1.4"}:
        section = payload["review"]
        if not isinstance(section, dict) or set(section) != {"lexicons", "glossaries"}:
            raise ValueError("review richiede lexicons e glossaries espliciti per ogni pagina.")
        aliases = {"deu": "de", "ger": "de", "ita": "it", "eng": "en", "fra": "fr", "fre": "fr"}
        if (t37["variant_id"] != "raw" or payload["tesseract"]["preprocess_before_ocr"]
                or payload["tesseract"]["enable_region_ocr"]
                or aliases.get(payload["tesseract"]["language"], payload["tesseract"]["language"])
                != aliases.get(t36["language"], t36["language"])):
            raise ValueError("Review richiede raw full-page, senza preprocessing/region OCR, e lingua Tesseract uguale a T36.")
        request["review"] = {}
        for role, resource_type in (("lexicons", "OcrLanguageLexicon"), ("glossaries", "MilitaryGlossary")):
            mapping = section[role]
            if not isinstance(mapping, dict) or set(mapping) != set(profiles):
                raise ValueError(f"review.{role} deve dichiarare esattamente ogni page_id.")
            request["review"][role] = {}
            for page_id, reference in mapping.items():
                _keys(reference, {"path", "sha256"}, role)
                path = _path(source.parent, reference["path"])
                digest = structure._required_sha256(reference["sha256"], role)
                if pilot._sha256_file(path) != digest:
                    raise ValueError(f"SHA-256 review.{role} divergente: {page_id}.")
                resource = _read(path)
                if resource.get("@type") != resource_type:
                    raise ValueError(f"Risorsa {resource_type} richiesta: {path}")
                lexical._review_entries(resource, glossary=role == "glossaries")
                if role == "lexicons" and aliases.get(resource["language"], resource["language"]) != aliases.get(t36["language"], t36["language"]):
                    raise ValueError("Lingua del lessico diversa dalla lingua T36.")
                request["review"][role][page_id] = {"path": str(path), "sha256": digest}
    if version == "1.4":
        reference = payload["provisional_threshold"]
        _keys(reference, {"path", "sha256"}, "provisional_threshold")
        threshold_path = _path(source.parent, reference["path"])
        threshold_digest = structure._required_sha256(reference["sha256"], "provisional_threshold.sha256")
        if pilot._sha256_file(threshold_path) != threshold_digest:
            raise ValueError("SHA-256 artifact threshold provisional divergente.")
        provisional_threshold._validate_threshold_artifact(_read(threshold_path))
        request["provisional_threshold"] = {"path": str(threshold_path), "sha256": threshold_digest}
    return request, options, factory_options


def _review_bindings(destination: Path, *, package: bool) -> dict[str, str]:
    paths = ["t36/pilot-manifest.json", "t37/run-manifest.json", "tesseract/report.json"]
    if package:
        paths.append("tesseract-evidence/run-manifest.json")
    return {relative: pilot._sha256_file(destination / relative) for relative in paths}


def _review_preflight(request: dict[str, Any], destination: Path) -> None:
    for mapping in request["review"].values():
        for reference in mapping.values():
            path = Path(reference["path"])
            if path == destination or destination in path.parents:
                raise ValueError("Input lessicale sovrapposto alla directory output.")
            if pilot._sha256_file(path) != reference["sha256"]:
                raise ValueError(f"Input lessicale modificato dopo preflight: {path}")


def _tesseract_manifest(request: dict[str, Any], t36: Path) -> dict[str, Any]:
    section = request["tesseract"]
    return {"@type": "TesseractPageBatchManifest", "schema_version": "1.1" if request["schema_version"] in {"1.3", "1.4"} else "1.0",
            "root_dir": section["root_dir"], "t36_manifest": {"path": str(t36),
            "sha256": pilot._sha256_file(t36) if t36.is_file() else "0" * 64}, "pages": section["pages"]}


def _tesseract_preflight(request: dict[str, Any], destination: Path, existing: bool) -> dict[str, Any]:
    manifest = _tesseract_manifest(request, destination / "t36" / "pilot-manifest.json")
    provisional_t36 = {"@type": "OcrTransformPilot", "schema_version": "1.0", "review_status": "unreviewed",
                       "accuracy_claim": "none_without_human_reference", "pages": [
                           {"page_id": page["page_id"], "status": "completed",
                            "source": {"path": page["path"], "sha256": page["sha256"]}}
                           for page in request["t36"]["inputs"]]}
    if request["schema_version"] in {"1.3", "1.4"}:
        from PIL import Image
        for page in provisional_t36["pages"]:
            with Image.open(page["source"]["path"]) as image:
                width, height = image.size
                page["source"]["image_dimensions"] = {"width": width, "height": height}
    # All external bindings are checked before Paddle; prospective T36 pages
    # supply only raw paths/hashes, never OCR evidence or T37 inputs.
    paths = [Path(request["workflow_manifest"]["path"]), Path(request["t36"]["input_manifest"]["path"])]
    raw_role = "raw_image" if request["schema_version"] in {"1.3", "1.4"} else "raw_tiff"
    paths.extend(Path(page[role]["path"]) for page in manifest["pages"] for role in (raw_role, "sidecar", "metadata"))
    for path in paths:
        if tesseract_batch._key(path).startswith(tesseract_batch._key(destination) + "\\") or tesseract_batch._key(path) == tesseract_batch._key(destination):
            raise ValueError("Input workflow sovrapposto alla directory output.")
    stage = destination / "tesseract"
    return tesseract_batch.run_tesseract_page_batch(
        manifest_path=stage / "page-batch-manifest.json", output_dir=stage / "texts", report_path=stage / "report.json",
        **request["tesseract"]["configuration"], _preflight_payloads=(manifest, provisional_t36), _existing_stage=existing)


def _verify_stage(root: Path, checkpoint: Any, request: dict[str, Any]) -> None:
    if (not isinstance(checkpoint, dict) or checkpoint.get("status") not in {"completed", "partial"}
            or checkpoint.get("request_fingerprint") != pilot._request_fingerprint(request)
            or not root.is_dir() or not checkpoint.get("artifacts")
            or checkpoint["artifacts"] != batch._inventory(root)):
        raise ValueError(f"Checkpoint/inventario stage non valido: {root.name}")


def _checkpoint(root: Path, request: dict[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "request_fingerprint": pilot._request_fingerprint(request),
            "artifacts": batch._inventory(root), **extra}


def _provisional_validation_stage(*, request: dict[str, Any], package_manifest_path: Path,
                                 output_dir: Path) -> dict[str, Any]:
    """Score every packaged page and bind a provisional routing decision to it."""
    threshold_ref = request["provisional_threshold"]
    threshold_path = Path(threshold_ref["path"])
    if pilot._sha256_file(threshold_path) != threshold_ref["sha256"]:
        raise ValueError("Artifact threshold provisional cambiato dopo il preflight.")
    threshold_payload = _read(threshold_path)
    provisional_threshold._validate_threshold_artifact(threshold_payload)
    package = _read(package_manifest_path)
    if package.get("@type") != "OcrReviewPackage" or not isinstance(package.get("pages"), list):
        raise ValueError("Package review non valido per il consumo provisional.")
    expected_page_ids = set(request["t37"]["page_profiles"])
    package_page_ids = [page.get("page_id") for page in package["pages"] if isinstance(page, dict)]
    if len(package_page_ids) != len(package["pages"]) or len(set(package_page_ids)) != len(package_page_ids) \
            or set(package_page_ids) != expected_page_ids:
        raise ValueError("Pagine package non corrispondono esattamente al workflow manifest.")
    package_digest = pilot._sha256_file(package_manifest_path)
    target = Path(output_dir)
    if target.exists():
        raise FileExistsError(f"Stage provisional-validation gia' esistente: {target}")
    target.mkdir(parents=True, exist_ok=False)
    page_results = []
    for page in package["pages"]:
        page_id = page.get("page_id")
        refs = page.get("review_inputs")
        if not isinstance(page_id, str) or not isinstance(refs, dict):
            raise ValueError("Pagina package priva di page_id o review_inputs.")
        evidence = Path(refs["evidence"]["path"])
        structure_path = Path(refs["structure"]["path"])
        markdown = Path(refs["markdown"]["path"])
        lexicon = Path(refs["lexicon_review"]["path"])
        comparison_path = Path(refs["comparison"]["path"])
        image = Path(refs["image"]["path"])
        comparison = _read(comparison_path)
        comparison_inputs = comparison.get("inputs")
        if not isinstance(comparison_inputs, dict):
            raise ValueError(f"{page_id}: comparison privo di evidence hash-bound.")
        left_ref, right_ref = comparison_inputs.get("left"), comparison_inputs.get("right")
        if not isinstance(left_ref, dict) or not isinstance(right_ref, dict):
            raise ValueError(f"{page_id}: comparison privo di input left/right.")
        page_dir = target / hashlib.sha256(page_id.encode("utf-8")).hexdigest()[:24]
        page_dir.mkdir()
        assessment_path = page_dir / "candidate-assessment.json"
        candidate_assessment.build_ocr_candidate_assessment(
            structure_path=structure_path, markdown_path=markdown, evidence_path=evidence,
            lexicon_review_path=lexicon, output_path=assessment_path, apply=True)
        features_path = page_dir / "risk-features.json"
        risk_features.build_ocr_risk_features(
            assessment_path=assessment_path, structure_path=structure_path, markdown_path=markdown,
            evidence_path=evidence, lexicon_review_path=lexicon, comparison_path=comparison_path,
            left_path=Path(left_ref["path"]), right_path=Path(right_ref["path"]),
            image_path=image, output_path=features_path, apply=True)
        score_path = page_dir / "risk-score.json"
        score = risk_score.build_ocr_risk_score(bundle_path=features_path, output_path=score_path, apply=True)
        decision_path = page_dir / "decision.json"
        if score.get("score_status") == "diagnostic_only":
            decision = provisional_threshold.evaluate_provisional_ocr_threshold(
                threshold_path=threshold_path, score_path=score_path,
                output_path=decision_path, apply=True)
        else:
            score_payload = _read(score_path)
            decision = {
                "@type": "OcrProvisionalThresholdDecision", "schema_version": "1.0",
                "inputs": {"threshold": {"path": str(threshold_path), "sha256": threshold_ref["sha256"]},
                           "score": {"path": str(score_path), "sha256": pilot._sha256_file(score_path)},
                           "score_source_bundle_sha256": score_payload["inputs"]["bundle"]["sha256"]},
                "candidate_identity": score_payload["candidate_identity"], "score": None,
                "cutoff": threshold_payload["threshold"].get("cutoff"),
                "scope_match": provisional_threshold._scope(
                    score_payload["candidate_identity"], score_payload["candidate_identity"]["profile"]
                ) in threshold_payload["threshold"]["scope"],
                "operational_disposition": "manual_review_required", "reason": "score_not_scorable",
                "provisional_auto_acceptance": False,
                "transcription_validation_status": "manual_review_required",
                "auto_validation_scope": None, "machine_pass": False,
                "auto_validation_enabled": False, "auto_validation_mode": None,
                "human_verified": False, "review_status": "unreviewed",
                "semantic_accuracy_status": "not_attested", "claim_extraction_allowed": False,
            }
            canonical = json.dumps(decision, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":"), allow_nan=False)
            decision["decision_payload_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                                     encoding="utf-8", newline="\n")
        decision_payload = _read(decision_path)
        accepted = decision_payload.get("operational_disposition") == "provisional_auto_accept"
        page_results.append({
            "page_id": page_id, "profile": page["profile"],
            "candidate_markdown": refs["markdown"],
            "score": {"path": str(score_path), "sha256": pilot._sha256_file(score_path),
                      "status": score.get("score_status"), "value": score.get("risk_score")},
            "decision": {"path": str(decision_path), "sha256": pilot._sha256_file(decision_path),
                         "disposition": decision_payload["operational_disposition"],
                         "reason": decision_payload["reason"]},
            "transcription_validation_status": decision_payload["transcription_validation_status"],
            "auto_validation_enabled": accepted, "machine_pass": False,
            "human_verified": False, "claim_extraction_allowed": False,
            "review_required": not accepted,
        })
    accepted = sum(page["auto_validation_enabled"] for page in page_results)
    manual_count = len(page_results) - accepted
    manual_rate = manual_count / len(page_results) if page_results else 0.0
    manual_cap_exceeded = manual_rate > MAX_MANUAL_REVIEW_RATE
    report = {
        "@type": "OcrWorkflowProvisionalValidation", "schema_version": "1.0",
        "threshold": {"path": str(threshold_path), "sha256": threshold_ref["sha256"]},
        "review_package": {"path": str(package_manifest_path), "sha256": package_digest},
        "page_count": len(page_results), "auto_validated_page_count": accepted,
        "manual_review_page_count": manual_count, "manual_review_rate": manual_rate,
        "manual_review_rate_limit": MAX_MANUAL_REVIEW_RATE,
        "manual_review_cap_exceeded": manual_cap_exceeded,
        "manual_review_page_ids": [page["page_id"] for page in page_results if page["review_required"]],
        "pages": page_results, "auto_validation_enabled": accepted > 0,
        "manual_review_request_allowed": bool(manual_count) and not manual_cap_exceeded,
        "auto_validation_mode": "provisional_empirical_scoped",
        "machine_pass": False, "human_verified": False,
        "semantic_accuracy_status": "not_attested", "claim_extraction_allowed": False,
    }
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    report["report_payload_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    report_path = target / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8", newline="\n")
    return report


def run_ocr_workflow(*, manifest_path: Path, output_dir: Path, apply: bool = False,
                     resume: bool = False, runner_factory: Callable[[], Any] | None = None,
                     command_runner: CommandRunner | None = None) -> dict[str, Any]:
    """Preflight without side effects; publish only through the stage owners.

    Complete stages are immutable. A stage published before its workflow
    checkpoint is a crash gap and requires inspection rather than overwrite.
    An interrupted T36 without a published aggregate can use its page resume.
    """
    request, options, factory_options = _prepare(Path(manifest_path))
    raw_destination = Path(output_dir).absolute()
    if raw_destination.is_symlink() or getattr(raw_destination, "is_junction", lambda: False)():
        raise ValueError("Link output workflow non consentito.")
    destination = raw_destination.resolve()
    repo = Path(__file__).resolve().parents[4]
    if destination == repo or repo in destination.parents:
        raise ValueError("La directory output deve restare esterna al repository.")
    if "provisional_threshold" in request:
        threshold_path = Path(request["provisional_threshold"]["path"])
        if threshold_path == destination or destination in threshold_path.parents:
            raise ValueError("L'artifact threshold deve restare esterno alla directory output.")
    t36, t37, diagnostic = destination / "t36", destination / "t37", destination / "tesseract"
    stages = {"t36", "t37"} | ({"tesseract"} if "tesseract" in request else set())
    if "review" in request:
        stages |= {"tesseract-evidence", "review"}
        _review_preflight(request, destination)
    if "provisional_threshold" in request:
        stages.add("provisional-validation")
    version = request["schema_version"]
    state = {"@type": "OcrWorkflowState", "schema_version": version,
             "request_fingerprint": pilot._request_fingerprint(request), "stages": {}}
    if resume:
        if not destination.is_dir() or _read(destination / "workflow-request.json") != request:
            raise ValueError("Richiesta workflow resume non coincide con il run originale.")
        batch._inventory(destination)  # Reject links before any writer is called.
        if any(p.name not in {"workflow-request.json", "workflow-state.json"} | stages for p in destination.iterdir()):
            raise ValueError("Artifact workflow inatteso.")
        state = _read(destination / "workflow-state.json")
        if (state.get("@type") != "OcrWorkflowState" or state.get("schema_version") != version
                or state.get("request_fingerprint") != pilot._request_fingerprint(request)
                or not isinstance(state.get("stages"), dict) or set(state["stages"]) - stages):
            raise ValueError("Stato workflow non valido.")
        for name in sorted(stages):
            root = destination / name
            checkpoint = state["stages"].get(name)
            if checkpoint is not None:
                _verify_stage(root, checkpoint, request)
            elif root.exists():
                # T36 can recover an interrupted page run, but never a published
                # aggregate whose wrapper checkpoint was not committed.
                if name != "t36" or (root / "pilot-manifest.json").exists():
                    raise ValueError(f"Crash gap stage {name}: artifact senza checkpoint workflow.")
        if "t37" in state["stages"]:
            if (state["stages"].get("t36", {}).get("status") != "completed"
                    or state["stages"]["t37"].get("source_manifest_sha256") != pilot._sha256_file(t36 / "pilot-manifest.json")
                    or state["stages"]["t37"].get("status") != "completed"):
                raise ValueError("Binding T36-T37 del checkpoint divergente.")
        if "tesseract" in state["stages"]:
            checkpoint = state["stages"]["tesseract"]
            diagnostic_report = _read(diagnostic / "report.json")
            diagnostic_manifest = _read(diagnostic / "page-batch-manifest.json")
            expected_status = "partial" if diagnostic_report.get("summary", {}).get("error", 0) else "completed"
            if (state["stages"].get("t36", {}).get("status") != "completed"
                    or checkpoint.get("source_manifest_sha256") != pilot._sha256_file(t36 / "pilot-manifest.json")
                    or diagnostic_manifest != _tesseract_manifest(request, t36 / "pilot-manifest.json")
                    or checkpoint["status"] != expected_status
                    or diagnostic_report.get("diagnostic_only") is not True
                    or diagnostic_report.get("review_status") != "unreviewed"):
                raise ValueError("Binding checkpoint Tesseract divergente.")
        for name in ("tesseract-evidence", "review"):
            if name in state["stages"]:
                checkpoint = state["stages"][name]
                if (any(state["stages"].get(required, {}).get("status") != "completed"
                        for required in ("t36", "t37", "tesseract"))
                        or (name == "review" and state["stages"].get("tesseract-evidence", {}).get("status") != "completed")
                        or checkpoint.get("source_bindings") != _review_bindings(destination, package=name == "review")
                        or checkpoint.get("status") != "completed"):
                    raise ValueError(f"Binding checkpoint {name} divergente.")
        if "provisional-validation" in state["stages"]:
            checkpoint = state["stages"]["provisional-validation"]
            expected_bindings = {
                "review_package_sha256": pilot._sha256_file(destination / "review" / "package-manifest.json"),
                "threshold_sha256": request["provisional_threshold"]["sha256"],
            }
            if (any(state["stages"].get(required, {}).get("status") != "completed"
                    for required in ("review", "tesseract-evidence"))
                    or checkpoint.get("source_bindings") != expected_bindings):
                raise ValueError("Binding checkpoint provisional-validation divergente.")
    else:
        pilot._validate_new_output_directory(destination)
        if not destination.parent.is_dir():
            raise ValueError("La directory padre dell'output deve esistere.")

    completed_t36 = state["stages"].get("t36", {}).get("status") == "completed"
    # A new workflow root does not yet exist. Batch preview can validate its
    # request against the proposed root itself; output path is not fingerprinted.
    if completed_t36:
        preflight = batch.run_ocr_transform_batch(**options, output_dir=t36, resume=True, apply=False)
    else:
        preflight = batch.run_ocr_transform_batch(**options, output_dir=t36 if destination.exists() else destination,
                                                resume=t36.exists(), apply=False)
    diagnostic_preflight = (_tesseract_preflight(request, destination, "tesseract" in state["stages"])
                            if "tesseract" in request else None)
    report = {"@type": "OcrWorkflowRun", "schema_version": version, "status": "preview",
              "output_dir": str(destination), "request_fingerprint": pilot._request_fingerprint(request),
              "page_count": len(request["t36"]["inputs"]), "t36": preflight,
              "t37": {"variant_id": request["t37"]["variant_id"], "page_profiles": request["t37"]["page_profiles"],
                      "reused": "t37" in state["stages"]},
              "review_status": "unreviewed", "semantic_accuracy_status": "not_attested",
              "machine_pass": False, "auto_validation_enabled": False, "gold_promotion_allowed": False}
    if diagnostic_preflight is not None:
        report["tesseract"] = {"status": "preview", "diagnostic_only": True, "review_status": "unreviewed",
                               "reused": "tesseract" in state["stages"], "preflight": diagnostic_preflight}
    if "review" in request:
        report["tesseract_evidence"] = {"status": "preview", "diagnostic_only": True,
            "review_status": "unreviewed", "reused": "tesseract-evidence" in state["stages"],
            "report_path": str(destination / "tesseract-evidence/run-manifest.json")}
        report["review"] = {"status": "preview", "review_status": "unreviewed",
                            "reused": "review" in state["stages"],
                            "output_dir": str(destination / "review"),
                            "package_manifest_path": str(destination / "review/package-manifest.json"),
                            "embedded_t37_manifest_path": str(destination / "review/t37/run-manifest.json"),
                            "workflow_t37_manifest_path": str(t37 / "run-manifest.json")}
    if not apply:
        report.update(writes_performed=False, inference_performed=False)
        if "provisional_threshold" in request:
            report["provisional_validation"] = {
                "status": "planned_after_ocr_and_review_package",
                "threshold": request["provisional_threshold"],
                "machine_pass": False, "human_verified": False,
                "claim_extraction_allowed": False,
            }
        return report
    if not resume:
        destination.mkdir(exist_ok=False)
        batch._write(destination / "workflow-request.json", request)
        batch._write(destination / "workflow-state.json", state)
    if not completed_t36:
        result = batch.run_ocr_transform_batch(**options, output_dir=t36, resume=t36.exists(), apply=True,
                                               runner_factory=runner_factory or (lambda: pilot.create_local_paddle_ocr_v5_runner(**factory_options)))
        status = result["manifest"]["status"]
        state["stages"]["t36"] = _checkpoint(t36, request, status)
        batch._write(destination / "workflow-state.json", state)
        report["t36"] = {"status": status, "metrics": result["manifest"]["metrics"], "reused": result["reused"]}
        if status != "completed":
            report.update(status="partial_unreviewed", blocked_stage="t37")
            if "tesseract" in request:
                report["blocked_stages"] = ["t37", "tesseract"]
                if "review" in request:
                    report["blocked_stages"] += ["tesseract-evidence", "review"]
            return report
    if "t37" not in state["stages"]:
        structure.export_ocr_transform_structure(manifest_path=t36 / "pilot-manifest.json", output_dir=t37,
                                                 variant_id=request["t37"]["variant_id"],
                                                 page_profiles=request["t37"]["page_profiles"], apply=True)
        state["stages"]["t37"] = _checkpoint(t37, request, "completed",
                                             source_manifest_sha256=pilot._sha256_file(t36 / "pilot-manifest.json"))
        batch._write(destination / "workflow-state.json", state)
    if "tesseract" in request:
        reused = "tesseract" in state["stages"]
        if not reused:
            diagnostic.mkdir(exist_ok=False)
            diagnostic_manifest_path = diagnostic / "page-batch-manifest.json"
            tesseract_batch._write_new(diagnostic_manifest_path, (json.dumps(
                _tesseract_manifest(request, t36 / "pilot-manifest.json"), ensure_ascii=False, indent=2,
                allow_nan=False) + "\n").encode("utf-8"))
            result = tesseract_batch.run_tesseract_page_batch(
                manifest_path=diagnostic_manifest_path, output_dir=diagnostic / "texts", report_path=diagnostic / "report.json",
                apply=True, command_runner=command_runner, **request["tesseract"]["configuration"])
            status = "partial" if result["summary"]["error"] else "completed"
            state["stages"]["tesseract"] = _checkpoint(diagnostic, request, status,
                source_manifest_sha256=pilot._sha256_file(t36 / "pilot-manifest.json"))
            batch._write(destination / "workflow-state.json", state)
        else:
            result = _read(diagnostic / "report.json")
        report["tesseract"] = {"status": state["stages"]["tesseract"]["status"], "reused": reused,
                               "diagnostic_only": True, "review_status": "unreviewed",
                               "summary": result["summary"], "report_path": str(diagnostic / "report.json")}
        if state["stages"]["tesseract"]["status"] == "partial":
            report.update(status="partial_unreviewed", state_path=str(destination / "workflow-state.json"))
            if "review" in request:
                report.update(blocked_stage="tesseract-evidence", blocked_stages=["tesseract-evidence", "review"])
            return report
        if version == "1.3":
            non_comparable = []
            for page in result["pages"]:
                text = _read(Path(page["output_path"]))
                if (text.get("ocr_quality_gate_status") != "accepted"
                        or text.get("ocr_run_provenance", {}).get("adapter_ready") is not True):
                    non_comparable.append(page["page_id"])
            if non_comparable:
                report["tesseract_evidence"]["status"] = report["review"]["status"] = "blocked_non_comparable"
                report.update(status="partial_unreviewed", blocked_stage="tesseract-evidence",
                    blocked_stages=["tesseract-evidence", "review"], blocked_page_ids=non_comparable,
                    block_reason="tesseract_diagnostic_not_comparable",
                    state_path=str(destination / "workflow-state.json"))
                return report
    if "review" in request:
        _review_preflight(request, destination)
        evidence_root = destination / "tesseract-evidence"
        if "tesseract-evidence" not in state["stages"]:
            tesseract_evidence.export_tesseract_from_t36(
                manifest_path=t36 / "pilot-manifest.json", output_dir=evidence_root, apply=True,
                source_document_ids={page["page_id"]: page["source_document_id"]
                                     for page in request["tesseract"]["pages"]},
                processed_text={page["page_id"]: Path(page["output_path"])
                                for page in _read(diagnostic / "report.json")["pages"]})
            state["stages"]["tesseract-evidence"] = _checkpoint(evidence_root, request, "completed",
                source_bindings=_review_bindings(destination, package=False))
            batch._write(destination / "workflow-state.json", state)
        evidence_report = _read(evidence_root / "run-manifest.json")
        report["tesseract_evidence"]["status"] = "diagnostic_evidence_ready"
        if "review" not in state["stages"]:
            review_package.build_ocr_review_package(
                manifest_path=t36 / "pilot-manifest.json", variant_id=request["t37"]["variant_id"],
                page_profiles=request["t37"]["page_profiles"],
                tesseract_evidence={page["page_id"]: Path(page["evidence"]["path"]) for page in evidence_report["pages"]},
                lexicons={page_id: Path(ref["path"]) for page_id, ref in request["review"]["lexicons"].items()},
                glossaries={page_id: Path(ref["path"]) for page_id, ref in request["review"]["glossaries"].items()},
                output_dir=destination / "review", apply=True)
            _review_preflight(request, destination)
            state["stages"]["review"] = _checkpoint(destination / "review", request, "completed",
                source_bindings=_review_bindings(destination, package=True))
            batch._write(destination / "workflow-state.json", state)
        report["review"].update(status="template_incomplete")
        if "provisional_threshold" in request:
            validation_root = destination / "provisional-validation"
            package_manifest_path = destination / "review" / "package-manifest.json"
            if "provisional-validation" in state["stages"]:
                validation = _read(validation_root / "report.json")
            else:
                validation = _provisional_validation_stage(
                    request=request, package_manifest_path=package_manifest_path,
                    output_dir=validation_root)
                bindings = {
                    "review_package_sha256": pilot._sha256_file(package_manifest_path),
                    "threshold_sha256": request["provisional_threshold"]["sha256"],
                }
                state["stages"]["provisional-validation"] = _checkpoint(
                    validation_root, request, "completed", source_bindings=bindings)
                batch._write(destination / "workflow-state.json", state)
            accepted = validation["auto_validated_page_count"]
            manual = validation["manual_review_page_ids"]
            report["provisional_validation"] = {
                "status": "completed", "report_path": str(validation_root / "report.json"),
                "page_count": validation["page_count"],
                "auto_validated_page_count": accepted,
                "manual_review_page_ids": manual,
                "manual_review_page_count": validation["manual_review_page_count"],
                "manual_review_rate": validation["manual_review_rate"],
                "manual_review_rate_limit": validation["manual_review_rate_limit"],
                "manual_review_cap_exceeded": validation["manual_review_cap_exceeded"],
                "pages": validation["pages"],
                "auto_validation_enabled": validation["auto_validation_enabled"],
                "auto_validation_mode": validation["auto_validation_mode"],
                "manual_review_request_allowed": validation["manual_review_request_allowed"],
            }
            report.update(auto_validation_enabled=validation["auto_validation_enabled"],
                          auto_validation_mode=validation["auto_validation_mode"])
            if not manual:
                report["review"].update(status="not_required_for_provisionally_accepted_pages")
                report.update(status="completed_provisional_auto_validated",
                              review_status="unreviewed",
                              state_path=str(destination / "workflow-state.json"))
                return report
            if validation["manual_review_cap_exceeded"]:
                report["review"].update(status="manual_review_cap_exceeded",
                                        manual_review_page_ids=manual,
                                        manual_review_request_allowed=False)
                report.update(status="manual_review_cap_exceeded",
                              manual_review_request_allowed=False,
                              state_path=str(destination / "workflow-state.json"))
                return report
            report["review"].update(awaiting="manual_review_for_nonaccepted_pages",
                                    manual_review_page_ids=manual,
                                    manual_review_request_allowed=True)
        else:
            report["review"]["awaiting"] = "visual_and_lexical_review"
        report.update(status="awaiting_review", state_path=str(destination / "workflow-state.json"))
        return report
    report.update(status="completed_unreviewed", state_path=str(destination / "workflow-state.json"))
    return report
