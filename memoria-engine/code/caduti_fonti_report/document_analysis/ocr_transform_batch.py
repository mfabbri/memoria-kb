"""Manifest-driven T36 orchestration with isolated, hash-bound page checkpoints.

Input v1: {"schema_version": "1.0", "pages": [{"page_id": "p1",
"path": "scan.tif", "sha256": "<64 lowercase hex characters>"}]}.
Relative TIFF paths resolve against the input manifest, never the working directory.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from pathlib import Path
import re
import shutil
import time
from typing import Any

from . import ocr_transform_pilot as pilot


_BATCH_VERSION = "t36-manifest-batch-v1"
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Oggetto JSON richiesto: {path}")
    return payload


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    # Publish checkpoints atomically; an interrupted serialization is never reusable.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _inputs(manifest_path: Path) -> list[dict[str, str]]:
    manifest_path = manifest_path.resolve(strict=True)
    payload = _read(manifest_path)
    if set(payload) != {"schema_version", "pages"} or payload["schema_version"] != "1.0":
        raise ValueError("Manifest batch T36: schema_version 1.0 e pages richiesti.")
    if not isinstance(payload["pages"], list) or not payload["pages"]:
        raise ValueError("Il manifest batch T36 deve dichiarare almeno una pagina.")
    pages, ids, sources = [], set(), set()
    for item in payload["pages"]:
        if not isinstance(item, dict) or set(item) != {"page_id", "path", "sha256"}:
            raise ValueError("Ogni pagina richiede page_id, path e sha256 espliciti.")
        page_id = item["page_id"]
        if (not isinstance(page_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", page_id)
                or page_id.endswith(".") or page_id.split(".")[0].casefold() in _RESERVED):
            raise ValueError("page_id non valido come identita' e directory Windows.")
        if page_id.casefold() in ids:
            raise ValueError("page_id duplicato (confronto Windows case-insensitive).")
        ids.add(page_id.casefold())
        path_text = pilot._required_text(item["path"], "path")
        source = Path(path_text)
        source = (source if source.is_absolute() else manifest_path.parent / source).resolve(strict=True)
        if not source.is_file() or source.suffix.lower() not in {".tif", ".tiff"}:
            raise ValueError(f"Input TIFF non valido: {source}")
        if str(source).casefold() in sources:
            raise ValueError("TIFF duplicato nel manifest batch.")
        sources.add(str(source).casefold())
        digest = item["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or pilot._sha256_file(source) != digest:
            raise ValueError(f"SHA-256 input non valido: {page_id}")
        pages.append({"page_id": page_id, "path": str(source), "sha256": digest})
    return pages


def _inventory(directory: Path) -> list[dict[str, str]]:
    entries = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError("Link non consentiti negli artifact batch T36.")
        if path.is_file():
            entries.append({"path": path.relative_to(directory).as_posix(), "sha256": pilot._sha256_file(path)})
    return entries


def _completed_checkpoint(destination: Path, item: Mapping[str, str], request: Mapping[str, Any]) -> dict[str, Any] | None:
    checkpoint_path = destination / "checkpoints" / f"{item['page_id']}.json"
    if not checkpoint_path.exists():
        return None
    checkpoint = _read(checkpoint_path)
    audit = {field: checkpoint.get(field) for field in ("page", "ocr_attempts", "prior_runs", "runtime_provenance")}
    if (checkpoint.get("@type") != "OcrTransformBatchPageCheckpoint" or checkpoint.get("schema_version") != "1.0"
            or checkpoint.get("request") != request or checkpoint.get("request_fingerprint") != pilot._request_fingerprint(request)
            or not isinstance(checkpoint.get("page"), dict) or not isinstance(checkpoint.get("ocr_attempts"), list)
            or not isinstance(checkpoint.get("prior_runs"), list)
            or checkpoint.get("audit_fingerprint") != pilot._request_fingerprint(audit)):
        raise ValueError(f"Checkpoint pagina non valido: {item['page_id']}")
    if checkpoint.get("status") == "failed":
        if checkpoint.get("artifacts") != [] or (destination / "pages" / item["page_id"]).exists():
            raise ValueError("Checkpoint failed con artifact inattesi.")
        return None
    page = checkpoint.get("page", {})
    inventory = _inventory(destination / "pages" / item["page_id"])
    if (checkpoint.get("status") != "completed" or not inventory or checkpoint.get("artifacts") != inventory
            or page.get("status") != "completed" or page.get("page_id") != item["page_id"]
            or page.get("source", {}).get("path") != item["path"] or page.get("source", {}).get("sha256") != item["sha256"]
            or checkpoint.get("page_fingerprint") != pilot._request_fingerprint(page)
            or [variant.get("variant_id") for variant in page.get("variants", [])] != ["raw", "grayscale", "contrast", "threshold"]):
        raise ValueError(f"Checkpoint pagina completo non verificabile: {item['page_id']}")
    return checkpoint


def run_ocr_transform_batch(
    *, manifest_path: Path, output_dir: Path, language: str, model: Mapping[str, str],
    prediction_runner: pilot.PaddlePredictionRunner | None = None,
    runner_factory: Callable[[], pilot.PaddlePredictionRunner] | None = None,
    runtime_identity: Mapping[str, Any] | None = None,
    tile_width: int = 2400, tile_height: int = 2400, tile_overlap: int = 200,
    enable_mkldnn: bool = False, text_det_limit_side_len: int = 8192,
    text_det_limit_type: str = "max", device: str = "cpu", retry_limit: int = 1,
    resume: bool = False, apply: bool = True, clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Validate everything before constructing a runtime; resume only verified pages.

    An invalid completed checkpoint fails closed. Missing/interrupted pages and
    audited failed pages can run again, while completed pages retain their audit.
    ``apply=False`` performs the same preflight without initializing OCR or writing.
    """
    inputs = _inputs(Path(manifest_path))
    language = pilot._required_text(language, "language")
    model_payload = pilot._validate_model(model)
    for field in ("text_detection_model_name", "text_recognition_model_name"):
        if "PP-OCRv5" not in model_payload[field]:
            raise ValueError("I nomi modelli devono identificare PP-OCRv5.")
    if any(type(value) is not int for value in (tile_width, tile_height, tile_overlap, text_det_limit_side_len)):
        raise ValueError("Dimensioni tile e limite detection devono essere interi.")
    pilot._validate_tiling(tile_width, tile_height, tile_overlap)
    if type(retry_limit) is not int or retry_limit not in (0, 1):
        raise ValueError("retry_limit deve essere 0 oppure 1.")
    runtime = pilot._validate_runtime_options(enable_mkldnn, text_det_limit_side_len, text_det_limit_type)
    runtime["device"] = pilot._required_text(device, "device")
    identity = pilot._json_value(runtime_identity or {})
    provenance = getattr(prediction_runner, "runtime_provenance", None)
    if isinstance(provenance, Mapping) and "models" in provenance:
        if runtime_identity is None:
            identity = pilot._json_value(provenance["models"])
        elif identity != pilot._json_value(provenance["models"]):
            raise ValueError("Identita' dei pesi runtime diversa dalla fingerprint richiesta.")
    request = {"batch_id": _BATCH_VERSION, "inputs": inputs, "language": language,
               "model": model_payload, "runtime_options": runtime, "runtime_identity": identity,
               "retry_limit": retry_limit, "tiling": {"width": tile_width, "height": tile_height, "overlap": tile_overlap}}
    fingerprint = pilot._request_fingerprint(request)
    raw_destination = Path(output_dir).absolute()
    if raw_destination.is_symlink() or getattr(raw_destination, "is_junction", lambda: False)():
        raise ValueError("Link output non consentito.")
    destination = raw_destination.resolve()
    repository_root = Path(__file__).resolve().parents[4]
    if destination == repository_root or repository_root in destination.parents:
        raise ValueError("La directory output deve restare esterna al repository.")
    page_requests = {item["page_id"]: {key: value for key, value in request.items() if key != "inputs"} | {"input": item} for item in inputs}
    cached = {}
    if resume:
        if not destination.is_dir() or _read(destination / "batch-request.json") != request:
            raise ValueError("Richiesta batch resume non coincide con il run originale.")
        _inventory(destination)  # Reject links before inspecting or removing page content.
        expected_ids = {item["page_id"] for item in inputs}
        checkpoint_names = {f"{page_id}{suffix}" for page_id in expected_ids for suffix in (".json", ".json.tmp")}
        allowed_root_names = {"batch-request.json", "checkpoints", "pages", "pilot-manifest.json", "pilot-manifest.json.tmp", "review.md"}
        if any(child.name not in allowed_root_names for child in destination.iterdir()):
            raise ValueError("Artifact batch inatteso nella directory output.")
        for directory in (destination / "pages", destination / "checkpoints"):
            if directory.exists():
                if not directory.is_dir():
                    raise ValueError("Directory artifact batch non valida.")
                for child in directory.iterdir():
                    valid_page = directory.name == "pages" and child.name in expected_ids and child.is_dir()
                    valid_checkpoint = (directory.name == "checkpoints" and child.is_file()
                                        and child.name in checkpoint_names)
                    if not (valid_page or valid_checkpoint):
                        raise ValueError("Artifact batch inatteso; resume interrotto.")
        for item in inputs:
            checkpoint = _completed_checkpoint(destination, item, page_requests[item["page_id"]])
            if checkpoint is not None:
                cached[item["page_id"]] = checkpoint
    else:
        pilot._validate_new_output_directory(destination)
        if not destination.parent.is_dir():
            raise ValueError("La directory padre dell'output deve esistere.")
    pending = [item for item in inputs if item["page_id"] not in cached]
    if not apply:
        return {"status": "preview", "page_count": len(inputs), "reused_page_count": len(cached),
                "pending_page_count": len(pending), "inference_performed": False, "writes_performed": False,
                "request_fingerprint": fingerprint}
    if pending and prediction_runner is None:
        if runner_factory is None:
            raise ValueError("prediction_runner o runner_factory richiesto per pagine da processare.")
        prediction_runner = runner_factory()
        actual = getattr(prediction_runner, "runtime_provenance", None)
        if isinstance(actual, Mapping) and "models" in actual and pilot._json_value(actual["models"]) != identity:
            raise ValueError("Identita' dei pesi runtime diversa dalla fingerprint richiesta.")
    from PIL import Image, ImageEnhance
    started = clock()
    if not resume:
        destination.mkdir(exist_ok=False)
        (destination / "checkpoints").mkdir()
        _write(destination / "batch-request.json", request)
    pages, attempts = [], []
    page_runtime_provenance = {}
    for item in inputs:
        page_id = item["page_id"]
        if page_id in cached:
            pages.append(cached[page_id]["page"])
            attempts.extend(cached[page_id]["ocr_attempts"])
            page_runtime_provenance[page_id] = cached[page_id].get("runtime_provenance")
            continue
        page_dir = destination / "pages" / page_id
        previous_runs = []
        previous_checkpoint_path = destination / "checkpoints" / f"{page_id}.json"
        if previous_checkpoint_path.exists():
            previous = _read(previous_checkpoint_path)
            previous_runs = [*previous.get("prior_runs", []),
                             {"status": previous["status"], "page": previous["page"], "ocr_attempts": previous["ocr_attempts"]}]
        # Only declared page directories inside this matching batch are owned.
        if page_dir.exists():
            shutil.rmtree(page_dir)
        page = {"page_id": page_id, "source": {"path": item["path"], "sha256": item["sha256"]}, "status": "completed", "variants": []}
        page_attempts: list[dict[str, Any]] = []
        try:
            pilot._process_page(source=Path(item["path"]), page_dir=page_dir, page=page, destination=destination,
                                language=language, model=model_payload, runner=prediction_runner,
                                tile_width=tile_width, tile_height=tile_height, tile_overlap=tile_overlap,
                                image_class=Image, enhance_class=ImageEnhance, clock=clock,
                                retry_limit=retry_limit, attempts=page_attempts)
            if pilot._sha256_file(Path(item["path"])) != item["sha256"]:
                raise ValueError("Input modificato durante l'elaborazione pagina.")
        except Exception as exc:
            if page_dir.exists():
                _inventory(page_dir)
                shutil.rmtree(page_dir)
            page.update(status="failed", variants=[], error={"type": type(exc).__name__, "message": str(exc)})
        page["ocr_attempt_count"] = len(page_attempts)
        checkpoint = {"@type": "OcrTransformBatchPageCheckpoint", "schema_version": "1.0", "status": page["status"],
                      "request": page_requests[page_id], "request_fingerprint": pilot._request_fingerprint(page_requests[page_id]),
                      "page": page, "page_fingerprint": pilot._request_fingerprint(page), "ocr_attempts": page_attempts,
                      "prior_runs": previous_runs,
                      "runtime_provenance": pilot._json_value(getattr(prediction_runner, "runtime_provenance", None)),
                      "artifacts": _inventory(page_dir) if page["status"] == "completed" else []}
        checkpoint["audit_fingerprint"] = pilot._request_fingerprint({field: checkpoint[field] for field in ("page", "ocr_attempts", "prior_runs", "runtime_provenance")})
        _write(destination / "checkpoints" / f"{page_id}.json", checkpoint)
        page_runtime_provenance[page_id] = checkpoint["runtime_provenance"]
        pages.append(page)
        attempts.extend(page_attempts)
    if any(pilot._sha256_file(Path(item["path"])) != item["sha256"] for item in inputs):
        raise ValueError("Input batch modificato durante il run; manifest non pubblicato.")
    latencies = [output["latency_ms"] for page in pages for variant in page["variants"] for output in variant["ocr_outputs"]]
    duration = clock() - started
    manifest = pilot._build_manifest(pages=pages, request=request, fingerprint=fingerprint,
                                    duration=duration, latencies=latencies, language=language,
                                    model=model_payload, runtime=dict(runtime) | {"page_runtime_provenance": page_runtime_provenance}, tile_width=tile_width,
                                    tile_height=tile_height, tile_overlap=tile_overlap)
    completed = sum(page["status"] == "completed" for page in pages)
    manifest.update(batch_id=_BATCH_VERSION, status="completed" if completed == len(pages) else "partial", ocr_attempts=attempts)
    manifest["metrics"].update(completed_page_count=completed, failed_page_count=len(pages) - completed,
                               reused_page_count=len(cached), processed_page_count=len(pending),
                               ocr_attempt_count=len(attempts),
                               failed_ocr_attempt_count=sum(attempt["status"] == "failed" for attempt in attempts),
                               ocr_attempt_count_scope="current_page_checkpoints_including_reused_pages_excluding_prior_failed_runs",
                               p95_scope="retained_target_audit_including_reused_pages")
    # Aggregate target/attempt metrics describe retained page audit, including reused pages.
    manifest["metrics"]["current_run_ocr_attempt_count"] = sum(page["ocr_attempt_count"] for page in pages if page["page_id"] not in cached)
    current_pages = [page for page in pages if page["page_id"] not in cached]
    manifest["metrics"]["throughput_pages_per_second"] = sum(page["status"] == "completed" for page in current_pages) / duration if duration > 0 else None
    current_targets = sum(len(variant["ocr_outputs"]) for page in current_pages for variant in page["variants"])
    manifest["metrics"]["throughput_ocr_targets_per_second"] = current_targets / duration if duration > 0 else None
    manifest["metrics"]["duration_scope"] = "current_invocation_processing_excludes_runtime_initialization_and_aggregate_serialization"
    _write(destination / "pilot-manifest.json", manifest)
    (destination / "review.md").write_text(pilot._markdown_report(manifest, destination), encoding="utf-8")
    return {"manifest": manifest, "manifest_path": str(destination / "pilot-manifest.json"),
            "report_path": str(destination / "review.md"), "reused": not pending}
