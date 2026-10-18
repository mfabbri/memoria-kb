"""Opt-in T36 OCR transform and tiling pilot for exactly two TIFF pages.

The module only creates derived artefacts in a caller-supplied new directory.
It never changes source scans and does not make any claim about transcription
accuracy.  The default PP-OCRv5 adapter requires explicit local model paths,
so it cannot download model data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .ocr_benchmark import paddle_ocr_v5_structured_evidence


PaddlePredictionRunner = Callable[[Path, str], Any]
_REQUIRED_MODEL_FIELDS = ("ocr_version", "text_detection_model_name", "text_recognition_model_name")
_TRANSFORM_VERSION = "t36-transform-tiling-pilot-v1"
_RAW_PADDLE_FIELDS = (
    "input_path", "page_index", "dt_polys", "rec_texts", "rec_scores", "rec_polys", "rec_boxes",
    "textline_orientation_angles", "text_det_params", "model_settings", "text_type", "text_rec_score_thresh",
    "return_word_box",
)
_EXCLUDED_PADDLE_FIELDS = ("doc_preprocessor_res.output_img", "vis_fonts")


def run_ocr_transform_pilot(
    *,
    input_tiffs: Sequence[Path],
    output_dir: Path,
    language: str,
    model: Mapping[str, str],
    prediction_runner: PaddlePredictionRunner | None,
    tile_width: int = 1800,
    tile_height: int = 1800,
    tile_overlap: int = 200,
    enable_mkldnn: bool = False,
    text_det_limit_side_len: int = 8192,
    text_det_limit_type: str = "max",
    device: str = "cpu",
    runtime_identity: Mapping[str, Any] | None = None,
    resume: bool = False,
    retry_limit: int = 1,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Create transform/tile OCR artefacts for exactly two explicit TIFFs.

    ``prediction_runner`` is deliberately injectable: unit tests need no OCR
    runtime, while the CLI supplies a PP-OCRv5 runner configured with local
    weights. ``resume`` only reuses a completed, fully verified checkpoint.
    ``retry_limit`` bounds retries of runner calls and lazy materialization for
    each target. Failed pages retain audit only; their partial artifacts are removed.
    """
    sources = _validate_sources(input_tiffs)
    if type(retry_limit) is not int or retry_limit not in (0, 1):
        raise ValueError("retry_limit deve essere 0 oppure 1.")
    destination = Path(output_dir)
    language_key = _required_text(language, "language")
    model_payload = _validate_model(model)
    _validate_tiling(tile_width, tile_height, tile_overlap)
    runtime = _validate_runtime_options(enable_mkldnn, text_det_limit_side_len, text_det_limit_type)
    runtime["device"] = _required_text(device, "device")
    runner_provenance = getattr(prediction_runner, "runtime_provenance", None)
    if isinstance(runner_provenance, Mapping) and "models" in runner_provenance:
        model_identity = _json_value(runner_provenance["models"])
        if runtime_identity is None:
            runtime_identity = model_identity
        elif _json_value(runtime_identity) != model_identity:
            raise ValueError("Identita' dei pesi runtime diversa dalla fingerprint richiesta.")
    source_hashes = [{"path": str(source), "sha256": _sha256_file(source)} for source in sources]
    request = {"pilot_id": _TRANSFORM_VERSION, "inputs": source_hashes, "language": language_key,
               "model": model_payload, "runtime_options": dict(runtime), "retry_limit": retry_limit,
               "runtime_identity": _json_value(runtime_identity or {}),
               "tiling": {"width": tile_width, "height": tile_height, "overlap": tile_overlap}}
    fingerprint = _request_fingerprint(request)
    if resume:
        return _reuse_completed_checkpoint(destination, request, fingerprint)
    _validate_new_output_directory(destination)
    if prediction_runner is None:
        raise ValueError("prediction_runner richiesto per un nuovo run T36.")
    runtime["paddle_excluded_prediction_fields"] = list(_EXCLUDED_PADDLE_FIELDS)
    runtime["full_page_caveat"] = (
        "PaddleOCR può riportare max_side_limit=4000 e downscalare le inferenze full-page; "
        "i tile raw nativi sono la verifica ad alta risoluzione del pilot."
    )
    if runner_provenance is not None:
        runtime["paddle"] = _json_value(runner_provenance)

    try:
        from PIL import Image, ImageEnhance
    except ImportError as exc:  # pragma: no cover - machine configuration
        raise RuntimeError("Pillow non disponibile: impossibile creare il pilot T36.") from exc

    started = clock()
    destination.mkdir(parents=True, exist_ok=False)
    pages: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for source in sources:
        page_id = source.stem
        page_dir = destination / "pages" / page_id
        page = {"page_id": page_id, "source": {"path": str(source), "sha256": _sha256_file(source)},
                "variants": [], "status": "completed"}
        try:
            _process_page(source=source, page_dir=page_dir, page=page, destination=destination,
                          language=language_key, model=model_payload, runner=prediction_runner,
                          tile_width=tile_width, tile_height=tile_height, tile_overlap=tile_overlap,
                          image_class=Image, enhance_class=ImageEnhance, clock=clock,
                          retry_limit=retry_limit, attempts=attempts)
        except Exception as exc:
            # Only this newly created page directory is owned by the pilot.
            if page_dir.exists():
                if page_dir.is_symlink() or destination.resolve() not in page_dir.resolve().parents:
                    raise ValueError("Cleanup pagina T36 fuori dalla directory output consentita.") from exc
                shutil.rmtree(page_dir)
            page.update(status="failed", variants=[], error={"type": type(exc).__name__, "message": str(exc)})
        page["ocr_attempt_count"] = sum(item["page_id"] == page_id for item in attempts)
        pages.append(page)

    if any(_sha256_file(Path(item["path"])) != item["sha256"] for item in source_hashes):
        raise ValueError("Input T36 modificato durante il run; checkpoint non pubblicato.")
    duration = clock() - started
    latencies = [output["latency_ms"] for page in pages for variant in page["variants"] for output in variant["ocr_outputs"]]
    completed_pages = sum(page["status"] == "completed" for page in pages)
    status = "completed" if completed_pages == len(pages) else "partial"
    manifest = _build_manifest(pages=pages, request=request, fingerprint=fingerprint, duration=duration,
                               latencies=latencies, language=language_key, model=model_payload, runtime=runtime,
                               tile_width=tile_width, tile_height=tile_height, tile_overlap=tile_overlap)
    manifest["status"] = status
    manifest["ocr_attempts"] = attempts
    manifest["metrics"].update(completed_page_count=completed_pages, failed_page_count=len(pages) - completed_pages,
                               ocr_attempt_count=len(attempts),
                               failed_ocr_attempt_count=sum(item["status"] == "failed" for item in attempts))
    manifest_path = destination / "pilot-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = destination / "review.md"
    report_path.write_text(_markdown_report(manifest, destination), encoding="utf-8")
    checkpoint = {"@type": "OcrTransformPilotCheckpoint", "schema_version": "1.0", "status": status,
                  "request_fingerprint": fingerprint, "artifacts": _checkpoint_artifacts(destination)}
    (destination / "checkpoint.json").write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest_path": str(manifest_path), "report_path": str(report_path), "manifest": manifest, "reused": False}


def _process_page(*, source: Path, page_dir: Path, page: dict[str, Any], destination: Path,
                  language: str, model: Mapping[str, str], runner: PaddlePredictionRunner,
                  tile_width: int, tile_height: int, tile_overlap: int, image_class: Any,
                  enhance_class: Any, clock: Callable[[], float], retry_limit: int,
                  attempts: list[dict[str, Any]]) -> None:
    page_id = page["page_id"]
    variants = _write_variants(source=source, page_dir=page_dir, image_class=image_class, enhance_class=enhance_class)
    source_dimensions = variants[0]["image_dimensions"]
    page["source"]["image_dimensions"] = source_dimensions
    for variant in variants:
        tile_entries = (
            _write_tiles(
                image_path=Path(variant["absolute_path"]),
                page_dir=page_dir,
                variant_id=variant["variant_id"],
                tile_width=tile_width,
                tile_height=tile_height,
                tile_overlap=tile_overlap,
                image_class=image_class,
            )
            if variant["variant_id"] == "raw"
            else []
        )
        targets = [{"kind": "full_page", "path": Path(variant["absolute_path"]), "source_bbox": [0, 0, source_dimensions["width"], source_dimensions["height"]]}]
        targets.extend({"kind": "tile", "path": Path(tile["absolute_path"]), "source_bbox": tile["source_bbox"], "tile_id": tile["tile_id"]} for tile in tile_entries)
        ocr_outputs = [
            _run_target_ocr(
                target=target,
                page_id=page_id,
                source=source,
                source_dimensions=source_dimensions,
                variant=variant,
                language=language,
                model=model,
                runner=runner,
                output_dir=destination,
                clock=clock,
                retry_limit=retry_limit,
                attempts=attempts,
            )
            for target in targets
        ]
        page["variants"].append(
            {
                **_public_artifact_entry(variant, destination),
                "tiles": [_public_artifact_entry(tile, destination) for tile in tile_entries],
                "ocr_outputs": ocr_outputs,
            }
        )


def _build_manifest(*, pages: list[dict[str, Any]], request: Mapping[str, Any], fingerprint: str,
                    duration: float, latencies: list[float], language: str, model: Mapping[str, str],
                    runtime: Mapping[str, Any], tile_width: int, tile_height: int, tile_overlap: int) -> dict[str, Any]:
    return {
        "@type": "OcrTransformPilot",
        "schema_version": "1.0",
        "pilot_id": _TRANSFORM_VERSION,
        "checkpoint_request": request,
        "request_fingerprint": fingerprint,
        "metrics": {
            "duration_seconds": duration,
            "duration_scope": "from_before_output_directory_creation_through_artifacts_and_ocr_excludes_manifest_report_checkpoint_serialization_and_runtime_initialization",
            "page_count": len(pages),
            "ocr_target_count": len(latencies),
            "ocr_target_count_scope": "retained_outputs_from_completed_pages",
            "throughput_pages_per_second": sum(page["status"] == "completed" for page in pages) / duration if duration > 0 else None,
            "throughput_ocr_targets_per_second": len(latencies) / duration if duration > 0 else None,
            "p95_target_latency_ms": sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
            "latency_scope": "runner_call_and_prediction_iterator_materialization_per_full_page_or_tile",
            "target_latency_retry_policy": "sum_of_attempt_latencies_for_retained_target",
            "p95_method": "nearest_rank_ceil_0.95_times_ocr_target_count",
            "cost": None,
            "human_review_seconds": None,
        },
        "review_status": "unreviewed",
        "accuracy_claim": "none_without_human_reference",
        "language": language,
        "model": model,
        "runtime": runtime,
        "tiling": {"tile_width": tile_width, "tile_height": tile_height, "overlap": tile_overlap, "variant_id": "raw", "coordinate_convention": "left_top_inclusive_right_bottom_exclusive"},
        "pages": pages,
        "notes": [
            "Gli originali TIFF non sono modificati.",
            "Le coordinate source_page_* riportano tutte le geometrie nello spazio della pagina sorgente.",
            "Le varianti ricevono OCR a pagina intera; crop, tile e OCR dei tile sono limitati a raw per il budget CPU del pilot.",
            "Le inferenze full-page possono essere downscalate dal max_side_limit Paddle; i tile raw restano nativi.",
            "Le trascrizioni sono output OCR grezzi da revisionare, non fatti storici.",
        ],
    }


def _request_fingerprint(request: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _checkpoint_artifacts(destination: Path) -> list[dict[str, str]]:
    artifacts = []
    for path in sorted(destination.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink non consentito nel checkpoint T36.")
        if path.is_file() and path != destination / "checkpoint.json":
            artifacts.append({"path": path.relative_to(destination).as_posix(), "sha256": _sha256_file(path)})
    return artifacts


def _reuse_completed_checkpoint(destination: Path, request: Mapping[str, Any], fingerprint: str) -> dict[str, Any]:
    if destination.is_symlink():
        raise ValueError("Symlink output non consentito per resume T36.")
    checkpoint = json.loads((destination / "checkpoint.json").read_text(encoding="utf-8"))
    manifest_path = destination / "pilot-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (not isinstance(checkpoint, dict) or not isinstance(manifest, dict)
        or checkpoint.get("@type") != "OcrTransformPilotCheckpoint" or checkpoint.get("schema_version") != "1.0"
        or checkpoint.get("status") != "completed" or checkpoint.get("request_fingerprint") != fingerprint
        or manifest.get("@type") != "OcrTransformPilot" or manifest.get("schema_version") != "1.0"
        or manifest.get("checkpoint_request") != request or manifest.get("request_fingerprint") != fingerprint
        or checkpoint.get("artifacts") != _checkpoint_artifacts(destination)
        or not (destination / "review.md").is_file()):
        raise ValueError("Checkpoint T36 non valido: fingerprint, manifest o hash artifact non coincidono.")
    return {"manifest_path": str(manifest_path), "report_path": str(destination / "review.md"), "manifest": manifest, "reused": True}


def local_paddle_checkpoint_identity(*, text_detection_model_dir: Path, text_recognition_model_dir: Path) -> dict[str, Any]:
    """Hash declared local weights without importing or initializing Paddle."""
    return {field: {"directory": str(path), "files": _model_file_manifest(path)} for field, path in (
        ("text_detection", _validated_model_dir(text_detection_model_dir, "text_detection_model_dir")),
        ("text_recognition", _validated_model_dir(text_recognition_model_dir, "text_recognition_model_dir")),
    )}


def create_local_paddle_ocr_v5_runner(
    *,
    language: str,
    text_detection_model_dir: Path,
    text_detection_model_name: str,
    text_recognition_model_dir: Path,
    text_recognition_model_name: str,
    device: str = "cpu",
    enable_mkldnn: bool = False,
    text_det_limit_side_len: int = 8192,
    text_det_limit_type: str = "max",
    paddle_ocr_factory: Callable[..., Any] | None = None,
    paddle_version: str = "injected-unknown",
    paddleocr_version: str = "injected-unknown",
) -> PaddlePredictionRunner:
    """Build a PP-OCRv5 runner from explicit local model directories only."""
    detection_dir = _validated_model_dir(text_detection_model_dir, "text_detection_model_dir")
    recognition_dir = _validated_model_dir(text_recognition_model_dir, "text_recognition_model_dir")
    if "PP-OCRv5" not in _required_text(text_detection_model_name, "text_detection_model_name"):
        raise ValueError("text_detection_model_name deve indicare PP-OCRv5.")
    if "PP-OCRv5" not in _required_text(text_recognition_model_name, "text_recognition_model_name"):
        raise ValueError("text_recognition_model_name deve indicare PP-OCRv5.")
    runtime = _validate_runtime_options(enable_mkldnn, text_det_limit_side_len, text_det_limit_type)
    if paddle_ocr_factory is None:
        try:
            import paddle
            import paddleocr
            from paddleocr import PaddleOCR
        except ModuleNotFoundError as exc:  # pragma: no cover - machine configuration
            raise RuntimeError("PaddleOCR non è installato localmente.") from exc
        paddle_ocr_factory = PaddleOCR
        paddle_version = str(getattr(paddle, "__version__", "unknown"))
        paddleocr_version = str(getattr(paddleocr, "__version__", "unknown"))
    engine = paddle_ocr_factory(
        lang=_paddle_language(language),
        device=_required_text(device, "device"),
        text_detection_model_dir=str(detection_dir),
        text_detection_model_name=text_detection_model_name,
        text_recognition_model_dir=str(recognition_dir),
        text_recognition_model_name=text_recognition_model_name,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        **runtime,
    )
    def run(image_path: Path, _: str) -> Any:
        return engine.predict(str(image_path))

    run.runtime_provenance = {  # type: ignore[attr-defined]
        "paddle_version": _required_text(paddle_version, "paddle_version"),
        "paddleocr_version": _required_text(paddleocr_version, "paddleocr_version"),
        "models": {
            "text_detection": {"directory": str(detection_dir), "files": _model_file_manifest(detection_dir)},
            "text_recognition": {"directory": str(recognition_dir), "files": _model_file_manifest(recognition_dir)},
        },
    }
    return run


def _validate_sources(input_tiffs: Sequence[Path]) -> list[Path]:
    if len(input_tiffs) != 2:
        raise ValueError("Il pilot T36 richiede esattamente due TIFF espliciti.")
    sources = [Path(item).resolve(strict=True) for item in input_tiffs]
    if len(set(sources)) != 2:
        raise ValueError("I due input TIFF del pilot devono essere distinti.")
    if len({source.stem.casefold() for source in sources}) != 2:
        raise ValueError("Gli input T36 devono avere page_id (stem) distinti.")
    for source in sources:
        if not source.is_file() or source.suffix.lower() not in {".tif", ".tiff"}:
            raise ValueError(f"Input non TIFF valido per il pilot T36: {source}")
    return sources


def _validate_new_output_directory(output_dir: Path) -> None:
    if not str(output_dir).strip() or output_dir.exists():
        raise FileExistsError(f"La directory output del pilot deve essere nuova: {output_dir}")


def _validate_model(model: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(model, Mapping):
        raise ValueError("model deve essere un oggetto con identificativi PP-OCRv5 espliciti.")
    return {field: _required_text(model.get(field), field) for field in _REQUIRED_MODEL_FIELDS}


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} deve essere testo non vuoto.")
    return value.strip()


def _validate_tiling(width: int, height: int, overlap: int) -> None:
    if min(width, height) <= 0 or overlap < 0 or overlap >= min(width, height):
        raise ValueError("tile_width/tile_height devono essere positivi e overlap inferiore al lato minore.")


def _validate_runtime_options(enable_mkldnn: bool, text_det_limit_side_len: int, text_det_limit_type: str) -> dict[str, Any]:
    if not isinstance(enable_mkldnn, bool):
        raise ValueError("enable_mkldnn deve essere booleano.")
    if text_det_limit_side_len < 1:
        raise ValueError("text_det_limit_side_len deve essere positivo.")
    if text_det_limit_type not in {"min", "max"}:
        raise ValueError("text_det_limit_type deve essere min oppure max.")
    return {"enable_mkldnn": enable_mkldnn, "text_det_limit_side_len": text_det_limit_side_len, "text_det_limit_type": text_det_limit_type}


def _write_variants(*, source: Path, page_dir: Path, image_class: Any, enhance_class: Any) -> list[dict[str, Any]]:
    variants_dir = page_dir / "variants"
    variants_dir.mkdir(parents=True, exist_ok=False)
    raw_path = variants_dir / "raw.tif"
    shutil.copyfile(source, raw_path)
    entries: list[dict[str, Any]] = []
    with image_class.open(source) as image:
        width, height = image.size
        raw_mode = image.mode
        grayscale = image.convert("L")
        rendered = [
            ("raw", raw_path, {"operation": "byte_copy", "source_mode": raw_mode}),
            ("grayscale", variants_dir / "grayscale.png", {"operation": "convert", "mode": "L"}),
            ("contrast", variants_dir / "contrast-x1.8.png", {"operation": "contrast", "mode": "L", "factor": 1.8}),
            ("threshold", variants_dir / "threshold-160.png", {"operation": "threshold", "mode": "L", "threshold": 160}),
        ]
        grayscale.save(rendered[1][1])
        enhance_class.Contrast(grayscale).enhance(1.8).save(rendered[2][1])
        grayscale.point(lambda value: 0 if value < 160 else 255).save(rendered[3][1])
    for variant_id, variant_path, parameters in rendered:
        entries.append({
            "variant_id": variant_id,
            "absolute_path": str(variant_path),
            "sha256": _sha256_file(variant_path),
            "image_dimensions": {"width": width, "height": height},
            "transform": {"id": f"{_TRANSFORM_VERSION}:{variant_id}", "parameters": parameters},
        })
    return entries


def _write_tiles(*, image_path: Path, page_dir: Path, variant_id: str, tile_width: int, tile_height: int, tile_overlap: int, image_class: Any) -> list[dict[str, Any]]:
    tile_dir = page_dir / "tiles" / variant_id
    tile_dir.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    with image_class.open(image_path) as image:
        width, height = image.size
        for row, top in enumerate(_tile_starts(height, tile_height, tile_overlap)):
            for column, left in enumerate(_tile_starts(width, tile_width, tile_overlap)):
                right, bottom = min(left + tile_width, width), min(top + tile_height, height)
                path = tile_dir / f"tile-r{row:03d}-c{column:03d}.png"
                image.crop((left, top, right, bottom)).save(path)
                entries.append({
                    "tile_id": f"tile-r{row:03d}-c{column:03d}", "absolute_path": str(path), "sha256": _sha256_file(path),
                    "source_bbox": [left, top, right, bottom], "image_dimensions": {"width": right - left, "height": bottom - top},
                })
    return entries


def _tile_starts(length: int, tile_length: int, overlap: int) -> list[int]:
    if length <= tile_length:
        return [0]
    step, last = tile_length - overlap, length - tile_length
    starts = list(range(0, last + 1, step))
    return starts if starts[-1] == last else [*starts, last]


def _run_target_ocr(*, target: Mapping[str, Any], page_id: str, source: Path, source_dimensions: Mapping[str, int], variant: Mapping[str, Any], language: str, model: Mapping[str, str], runner: PaddlePredictionRunner, output_dir: Path, retry_limit: int, attempts: list[dict[str, Any]], clock: Callable[[], float] = time.perf_counter) -> dict[str, Any]:
    image_path = Path(target["path"])
    target_attempts = []
    for attempt_number in range(1, retry_limit + 2):
        attempt = {"page_id": page_id, "variant_id": variant["variant_id"], "target": target["kind"],
                   "tile_id": target.get("tile_id"), "attempt": attempt_number}
        started = clock()
        try:
            prediction = runner(image_path, language)
            stable_prediction = prediction if isinstance(prediction, str) else list(prediction)
        except Exception as exc:
            attempt.update(status="failed", latency_ms=round((clock() - started) * 1000, 3),
                           error={"type": type(exc).__name__, "message": str(exc)})
            attempts.append(attempt)
            target_attempts.append(attempt)
            if attempt_number > retry_limit:
                raise
        else:
            attempt.update(status="completed", latency_ms=round((clock() - started) * 1000, 3))
            attempts.append(attempt)
            target_attempts.append(attempt)
            break
    latency_ms = round(sum(item["latency_ms"] for item in target_attempts), 3)
    normalized_prediction = _json_prediction(stable_prediction)
    source_hash = _sha256_file(source)
    evidence = paddle_ocr_v5_structured_evidence(
        normalized_prediction, page_id=page_id, source_image_hash=source_hash,
        transform_id=variant["transform"]["id"], engine="paddle-ocr-v5", language=language,
        source_page={
            "original_page": {"page_id": page_id, "source_file": str(source),
                              "source_dimensions": dict(source_dimensions), "source_image_hash": source_hash},
            "variant_id": variant["variant_id"], "target": target["kind"], "tile_id": target.get("tile_id"),
        },
        model=model, image_transform=variant["transform"],
    )
    left, top, _, _ = target["source_bbox"]
    for region in evidence["regions"]:
        geometry = region["geometry"]
        geometry["source_page_polygon"] = _offset_polygon(geometry.get("polygon"), left, top)
        geometry["source_page_bbox"] = _offset_bbox(geometry.get("bbox"), left, top)
    return {
        "target": target["kind"], "tile_id": target.get("tile_id"), "artifact": _relative_path(image_path, output_dir),
        "artifact_sha256": _sha256_file(image_path), "source_bbox": target["source_bbox"], "latency_ms": latency_ms,
        "attempt_count": len(target_attempts),
        "raw_prediction": normalized_prediction, "structured_evidence": evidence,
    }


def _offset_polygon(polygon: Any, left: int, top: int) -> Any:
    if polygon is None:
        return None
    if not isinstance(polygon, list) or not all(isinstance(point, list) and len(point) == 2 for point in polygon):
        raise ValueError("rec_polys PaddleOCR deve essere una lista di punti [x, y].")
    return [[point[0] + left, point[1] + top] for point in polygon]


def _offset_bbox(bbox: Any, left: int, top: int) -> Any:
    if bbox is None:
        return None
    if isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(value, (int, float)) for value in bbox):
        return [bbox[0] + left, bbox[1] + top, bbox[2] + left, bbox[3] + top]
    if isinstance(bbox, list) and len(bbox) == 2 and all(isinstance(point, list) and len(point) == 2 for point in bbox):
        return [[point[0] + left, point[1] + top] for point in bbox]
    raise ValueError("rec_boxes PaddleOCR deve essere [x1, y1, x2, y2] oppure due punti.")


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _json_value(tolist())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError("Predizione PaddleOCR non serializzabile nel manifest T36.")


def _json_prediction(prediction: Any) -> Any:
    """Keep OCR payload fields while excluding Paddle intermediate image objects."""
    if isinstance(prediction, str):
        return prediction
    raw_results: list[Any] = []
    for result in prediction:
        payload = result if isinstance(result, Mapping) else getattr(result, "json", None)
        if not isinstance(payload, Mapping):
            raise ValueError("Risposta PaddleOCR senza payload JSON per il manifest T36.")
        raw_results.append(_normalized_paddle_payload(payload))
    return raw_results


def _normalized_paddle_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = payload.get("res", payload)
    if not isinstance(result, Mapping):
        raise ValueError("Risposta PaddleOCR con res non valido per il manifest T36.")
    retained: dict[str, Any] = {}
    for field in _RAW_PADDLE_FIELDS:
        value = result.get(field, payload.get(field))
        if value is not None:
            retained[field] = _json_value(value)
    return {"res": retained}


def _public_artifact_entry(entry: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    return {key: (_relative_path(Path(value), output_dir) if key == "absolute_path" else value) for key, value in entry.items() if key != "absolute_path"} | {"path": _relative_path(Path(entry["absolute_path"]), output_dir)}


def _relative_path(path: Path, base: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_file_manifest(model_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for candidate in sorted(model_dir.rglob("*"), key=lambda item: item.as_posix()):
        if not candidate.is_file() or ".cache" in candidate.relative_to(model_dir).parts:
            continue
        files.append({"path": candidate.relative_to(model_dir).as_posix(), "size_bytes": candidate.stat().st_size, "sha256": _sha256_file(candidate)})
    return files


def _markdown_report(manifest: Mapping[str, Any], output_dir: Path) -> str:
    lines = ["# Pilot T36 — review OCR trasformazioni e tile", "", "Stato: **unreviewed**. Le trascrizioni sono OCR grezzo e non attestano accuratezza o fatti storici.", "", "Budget pilot: ogni variante ha OCR a pagina intera; tile e OCR dei tile sono eseguiti soltanto su `raw` alla risoluzione nativa.", ""]
    for page in manifest["pages"]:
        lines.extend([f"## {page['page_id']}", "", f"TIFF originale (riferimento esterno): `{page['source']['path']}`  ", f"SHA-256: `{page['source']['sha256']}`", ""])
        lines.extend([f"Esito: **{page['status']}**; tentativi OCR: {page['ocr_attempt_count']}.", ""])
        for attempt in manifest["ocr_attempts"]:
            if attempt["page_id"] == page["page_id"] and attempt["status"] == "failed":
                lines.extend([f"Tentativo {attempt['attempt']} {attempt['variant_id']}/{attempt['tile_id'] or 'full_page'}: "
                              f"`{attempt['error']['type']}`: {attempt['error']['message']}", ""])
        if page["status"] == "failed":
            lines.extend([f"Errore: `{page['error']['type']}`: {page['error']['message']}",
                          "Artifact parziali della pagina rimossi.", ""])
        for variant in page["variants"]:
            lines.extend([f"### Variante `{variant['variant_id']}`", "", f"[Immagine derivata]({variant['path']}) · SHA-256 `{variant['sha256']}`", ""])
            for output in variant["ocr_outputs"]:
                label = output["tile_id"] or "pagina intera"
                overlap_note = " (tile sovrapposto: non sommare le trascrizioni)" if output["tile_id"] else ""
                lines.extend([f"#### {label}", "", f"[Crop o immagine OCR]({output['artifact']}) · bbox sorgente `{output['source_bbox']}` · {output['latency_ms']} ms{overlap_note}", "", "```text"])
                lines.extend(region["text"] for region in output["structured_evidence"]["regions"])
                lines.extend(["```", ""])
    lines.extend(["## Provenance", "", "Il dettaglio completo, inclusi output grezzi e geometrie rimappate alla pagina sorgente, è in [pilot-manifest.json](pilot-manifest.json).", ""])
    return "\n".join(lines)


def _validated_model_dir(value: Path, field: str) -> Path:
    path = Path(value).resolve(strict=True)
    required = ("inference.json", "inference.pdiparams", "inference.yml")
    missing = [name for name in required if not (path / name).is_file()]
    if not path.is_dir() or missing:
        raise ValueError(f"{field} deve essere una directory locale PP-OCRv5 completa; mancanti: {', '.join(missing)}")
    return path


def _paddle_language(language: str) -> str:
    return {"ita": "it", "deu": "de", "eng": "en", "rus": "ru"}.get(language, language)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pilot T36: trasformazioni e tile PP-OCRv5 per esattamente due TIFF.")
    parser.add_argument("--input-tiff", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--text-detection-model-dir", required=True)
    parser.add_argument("--text-detection-model-name", required=True)
    parser.add_argument("--text-recognition-model-dir", required=True)
    parser.add_argument("--text-recognition-model-name", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--resume", action="store_true", help="Riusa un checkpoint completato senza inizializzare Paddle.")
    parser.add_argument("--retry-limit", type=int, choices=(0, 1), default=1)
    parser.add_argument("--enable-mkldnn", action="store_true")
    parser.add_argument("--text-det-limit-side-len", type=int, default=8192)
    parser.add_argument("--text-det-limit-type", choices=("min", "max"), default="max")
    parser.add_argument("--tile-width", type=int, default=1800)
    parser.add_argument("--tile-height", type=int, default=1800)
    parser.add_argument("--tile-overlap", type=int, default=200)
    args = parser.parse_args(argv)
    try:
        runtime_identity = local_paddle_checkpoint_identity(
            text_detection_model_dir=Path(args.text_detection_model_dir),
            text_recognition_model_dir=Path(args.text_recognition_model_dir),
        )
        runner = None if args.resume else create_local_paddle_ocr_v5_runner(
            language=args.language, text_detection_model_dir=Path(args.text_detection_model_dir), text_detection_model_name=args.text_detection_model_name,
            text_recognition_model_dir=Path(args.text_recognition_model_dir), text_recognition_model_name=args.text_recognition_model_name, device=args.device,
            enable_mkldnn=args.enable_mkldnn, text_det_limit_side_len=args.text_det_limit_side_len, text_det_limit_type=args.text_det_limit_type,
        )
        result = run_ocr_transform_pilot(
            input_tiffs=[Path(path) for path in args.input_tiff], output_dir=Path(args.output_dir), language=args.language,
            model={"ocr_version": "PP-OCRv5", "text_detection_model_name": args.text_detection_model_name, "text_recognition_model_name": args.text_recognition_model_name}, prediction_runner=runner,
            tile_width=args.tile_width, tile_height=args.tile_height, tile_overlap=args.tile_overlap,
            device=args.device, runtime_identity=runtime_identity, resume=args.resume, retry_limit=args.retry_limit,
            enable_mkldnn=args.enable_mkldnn, text_det_limit_side_len=args.text_det_limit_side_len, text_det_limit_type=args.text_det_limit_type,
        )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"manifest_path": result["manifest_path"], "report_path": result["report_path"]}, ensure_ascii=False, indent=2))
    return 1 if result["manifest"]["status"] == "partial" else 0


if __name__ == "__main__":
    sys.exit(main())
