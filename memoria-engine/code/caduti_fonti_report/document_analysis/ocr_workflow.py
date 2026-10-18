"""Explicit T36 -> T37 workflow, optionally with diagnostic Tesseract.

OcrWorkflow v1 declares t36.input_manifest {path, sha256}, language, model
(ocr_version, detection/recognition names and local directories), runtime
(device, enable_mkldnn, text_det_limit_side_len/type, tile_width/height/overlap,
retry_limit), and t37 {variant_id, page_profiles}. Paths resolve at the manifest.
OcrWorkflow v1.1 additionally requires tesseract {root_dir, language,
tesseract_path, page_segmentation_mode, engine_mode, dpi, preprocess_before_ocr,
enable_region_ocr, pages}. Each page binds page_id/source_id/source_document_id
and sidecar/metadata {path, sha256}; the TIFF binding derives from T36 inputs.
OcrWorkflow v1.2 adds review {lexicons, glossaries?}, each an exact page_id map
of {path, sha256}. It requires raw single-frame inputs and original-pixel
Tesseract in the same language. The package builder derives its own T37 copy
without inference; this is separate from the immutable workflow t37 stage.
T37 always consumes only T36 evidence. Tesseract stages are diagnostic_only and
unreviewed, including partial runtime results, and are immutable on resume.
The wrapper owns workflow-request.json, workflow-state.json and the derived
tesseract/page-batch-manifest.json; stage owners publish other artifacts.
"""
from __future__ import annotations

from collections.abc import Callable
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
from .ocr_tesseract import CommandRunner


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
    if payload.get("@type") != "OcrWorkflow" or version not in {"1.0", "1.1", "1.2"}:
        raise ValueError("E' richiesto OcrWorkflow v1.0, v1.1 o v1.2.")
    _keys(payload, {"@type", "schema_version", "t36", "t37"}
          | ({"tesseract"} if version != "1.0" else set())
          | ({"review"} if version == "1.2" else set()), "workflow")
    t36, t37 = payload["t36"], payload["t37"]
    _keys(t36, {"input_manifest", "language", "model", "runtime"}, "t36")
    _keys(t36["input_manifest"], {"path", "sha256"}, "t36.input_manifest")
    inputs = _path(source.parent, t36["input_manifest"]["path"])
    if pilot._sha256_file(inputs) != structure._required_sha256(t36["input_manifest"]["sha256"], "input_manifest.sha256"):
        raise ValueError("SHA-256 manifest input T36 divergente.")
    if version != "1.0":
        _read(inputs)  # The v1.1 input boundary also rejects duplicate JSON keys.
    pages = batch._inputs(inputs)
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
            bound.append(page | references | {"raw_tiff": {"path": raw["path"], "sha256": raw["sha256"]}})
        request["tesseract"] = {"root_dir": str(_path(source.parent, section["root_dir"])),
                                "configuration": {key: section[key] for key in sorted(configuration)}, "pages": bound}
    if version == "1.2":
        section = payload["review"]
        if not isinstance(section, dict) or set(section) not in ({"lexicons"}, {"lexicons", "glossaries"}):
            raise ValueError("review richiede lexicons e, opzionalmente, glossaries.")
        aliases = {"deu": "de", "ger": "de", "ita": "it", "eng": "en", "fra": "fr", "fre": "fr"}
        if (t37["variant_id"] != "raw" or payload["tesseract"]["preprocess_before_ocr"]
                or payload["tesseract"]["enable_region_ocr"]
                or aliases.get(payload["tesseract"]["language"], payload["tesseract"]["language"])
                != aliases.get(t36["language"], t36["language"])):
            raise ValueError("Review richiede raw full-page, senza preprocessing/region OCR, e lingua Tesseract uguale a T36.")
        request["review"] = {}
        for role, resource_type in (("lexicons", "OcrLanguageLexicon"), ("glossaries", "MilitaryGlossary")):
            if role not in section:
                continue
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
    return {"@type": "TesseractPageBatchManifest", "schema_version": "1.0",
            "root_dir": section["root_dir"], "t36_manifest": {"path": str(t36),
            "sha256": pilot._sha256_file(t36) if t36.is_file() else "0" * 64}, "pages": section["pages"]}


def _tesseract_preflight(request: dict[str, Any], destination: Path, existing: bool) -> dict[str, Any]:
    manifest = _tesseract_manifest(request, destination / "t36" / "pilot-manifest.json")
    provisional_t36 = {"@type": "OcrTransformPilot", "schema_version": "1.0", "review_status": "unreviewed",
                       "accuracy_claim": "none_without_human_reference", "pages": [
                           {"page_id": page["page_id"], "status": "completed",
                            "source": {"path": page["path"], "sha256": page["sha256"]}}
                           for page in request["t36"]["inputs"]]}
    # All external bindings are checked before Paddle; prospective T36 pages
    # supply only raw paths/hashes, never OCR evidence or T37 inputs.
    paths = [Path(request["workflow_manifest"]["path"]), Path(request["t36"]["input_manifest"]["path"])]
    paths.extend(Path(page[role]["path"]) for page in manifest["pages"] for role in ("raw_tiff", "sidecar", "metadata"))
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
    t36, t37, diagnostic = destination / "t36", destination / "t37", destination / "tesseract"
    stages = {"t36", "t37"} | ({"tesseract"} if "tesseract" in request else set())
    if "review" in request:
        stages |= {"tesseract-evidence", "review"}
        _review_preflight(request, destination)
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
    if "review" in request:
        _review_preflight(request, destination)
        evidence_root = destination / "tesseract-evidence"
        if "tesseract-evidence" not in state["stages"]:
            tesseract_evidence.export_tesseract_from_t36(
                manifest_path=t36 / "pilot-manifest.json", output_dir=evidence_root, apply=True,
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
                glossaries=({page_id: Path(ref["path"]) for page_id, ref in request["review"]["glossaries"].items()}
                            if "glossaries" in request["review"] else None),
                output_dir=destination / "review", apply=True)
            _review_preflight(request, destination)
            state["stages"]["review"] = _checkpoint(destination / "review", request, "completed",
                source_bindings=_review_bindings(destination, package=True))
            batch._write(destination / "workflow-state.json", state)
        report["review"].update(status="template_incomplete", awaiting="visual_and_lexical_review")
        report.update(status="awaiting_review", state_path=str(destination / "workflow-state.json"))
        return report
    report.update(status="completed_unreviewed", state_path=str(destination / "workflow-state.json"))
    return report
