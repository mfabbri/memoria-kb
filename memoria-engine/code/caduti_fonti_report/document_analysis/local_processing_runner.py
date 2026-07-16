from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from ..knowledge_catalog import default_military_glossary_dir
from .candidate_person_profiles import build_candidate_person_profiles_from_documents
from .document_chunking import DEFAULT_MAX_CHARS, DEFAULT_OVERLAP_CHARS, chunk_document_texts
from .historical_map_catalog import build_historical_map_catalog
from .image_preprocessing_plan import build_image_preprocessing_plan
from .input_processing_plan import build_input_processing_plan
from .language_detection import MIN_TEXT_CHARS, detect_document_languages
from .language_routing import build_document_language_routing_plans
from .llm_chunk_classifier import classify_document_chunks, llm_chunk_defaults_from_env
from .local_processing_manifest import build_running_step_record, build_skipped_step_record
from .local_processing_manifest import duration_text as _duration_text
from .local_processing_manifest import render_run_summary as _render_run_summary
from .mention_extraction import extract_document_mentions
from .metadata_extraction import extract_document_metadata
from .military_glossary import extract_military_glossary_mentions
from .ocr_batch import run_document_ocr_batch, write_batch_report
from .research_feedback_actions import build_document_research_feedback_actions
from .text_extraction import extract_document_text
from .weak_document_segmentation import weak_segment_document_chunks

LOCAL_PROCESSING_VERSION = "local-document-processing-v1"
ENV_LLM_CHUNK_ENABLED = "CADUTI_LLM_CHUNK_ENABLED"


def run_local_document_processing(
    *,
    root_dir: Path,
    processed_dir: Path,
    results_dir: Path,
    run_id: str,
    research_dir: Path = Path("ricerche"),
    glossary_dir: Path | None = None,
    run_ocr: bool = False,
    force_derived: bool = False,
    force_ocr: bool = False,
    preprocess_before_ocr: bool = False,
    enable_region_ocr: bool = False,
    ocr_language: str = "ita",
    tesseract_path: str = "tesseract",
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    dpi: str = "",
    ocr_max_workers: int = 2,
    ocr_progress_every: int = 25,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    min_language_text_chars: int = MIN_TEXT_CHARS,
    enable_llm_chunk_classification: bool | None = None,
    llm_provider: str = "",
    llm_model_name: str = "",
    llm_prompt_version: str = "",
    llm_wsl_distribution: str = "",
    llm_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    resolved_glossary_dir = glossary_dir or default_military_glossary_dir(research_dir)
    llm_defaults = llm_chunk_defaults_from_env(Path.cwd())
    resolved_enable_llm_chunk_classification = (
        _env_bool(ENV_LLM_CHUNK_ENABLED, False)
        if enable_llm_chunk_classification is None
        else enable_llm_chunk_classification
    )
    resolved_llm_provider = llm_provider.strip() or str(llm_defaults["provider"])
    resolved_llm_model_name = llm_model_name.strip() or str(llm_defaults["model_name"])
    resolved_llm_prompt_version = llm_prompt_version.strip() or str(llm_defaults["prompt_version"])
    resolved_llm_wsl_distribution = llm_wsl_distribution.strip() or str(llm_defaults["wsl_distribution"])
    resolved_llm_timeout_seconds = llm_timeout_seconds or int(llm_defaults["timeout_seconds"])
    resolved_run_id = run_id.strip() or _default_run_id()
    run_dir = results_dir / "runs" / resolved_run_id
    document_dir = run_dir / "document_analysis"
    document_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "run.log"
    logger = _RunLogger(log_path)

    previous_manifest = _load_previous_manifest(run_dir / "manifest.json")
    started_at = _now()
    manifest: dict[str, Any] = {
        "@type": "LocalDocumentProcessingRunManifest",
        "run_id": resolved_run_id,
        "runner_version": LOCAL_PROCESSING_VERSION,
        "started_at": started_at,
        "finished_at": "",
        "status": "running",
        "inputs": {
            "root_dir": str(root_dir),
            "processed_dir": str(processed_dir),
            "research_dir": str(research_dir),
            "glossary_dir": str(resolved_glossary_dir),
            "run_ocr": run_ocr,
            "force_derived": force_derived,
            "force_ocr": force_ocr,
            "preprocess_before_ocr": preprocess_before_ocr,
            "enable_region_ocr": enable_region_ocr,
            "ocr_language": ocr_language,
            "tesseract_path": tesseract_path,
            "page_segmentation_mode": page_segmentation_mode,
            "engine_mode": engine_mode,
            "dpi": dpi,
            "ocr_max_workers": ocr_max_workers,
            "ocr_progress_every": ocr_progress_every,
            "max_chars": max_chars,
            "overlap_chars": overlap_chars,
            "min_language_text_chars": min_language_text_chars,
            "enable_llm_chunk_classification": resolved_enable_llm_chunk_classification,
            "llm_chunk_provider": resolved_llm_provider,
            "llm_chunk_model_name": resolved_llm_model_name,
            "llm_chunk_prompt_version": resolved_llm_prompt_version,
            "llm_chunk_wsl_distribution": resolved_llm_wsl_distribution,
            "llm_chunk_timeout_seconds": resolved_llm_timeout_seconds,
        },
        "outputs": {
            "run_dir": str(run_dir),
            "document_analysis_dir": str(document_dir),
            "run_log": str(log_path),
        },
        "steps": [],
    }
    logger.write(f"RUN START local_document_processing run_id={resolved_run_id}")
    logger.write(f"RootDir={root_dir}")
    logger.write(f"ProcessedDir={processed_dir}")
    logger.write(f"ResultsDir={results_dir}")

    ocr_log_path = document_dir / "ocr_batch.log"
    manifest["outputs"]["ocr_batch_log"] = str(ocr_log_path)
    ocr_output_paths = [document_dir / "ocr_batch_report.json", document_dir / "ocr_batch_report.md"]
    if run_ocr:
        _run_delta_step(
            manifest,
            previous_manifest=previous_manifest,
            name="ocr_batch",
            input_roots=[root_dir],
            input_patterns=["**/*.jpg", "**/*.jpeg", "**/*.png", "**/*.tif", "**/*.tiff"],
            params={
                "root_dir": str(root_dir),
                "processed_dir": str(processed_dir),
                "language": ocr_language,
                "tesseract_path": tesseract_path,
                "page_segmentation_mode": page_segmentation_mode,
                "engine_mode": engine_mode,
                "dpi": dpi,
                "preprocess_before_ocr": preprocess_before_ocr,
                "enable_region_ocr": enable_region_ocr,
                "overwrite": force_ocr,
                "max_workers": ocr_max_workers,
                "progress_every": ocr_progress_every,
            },
            output_paths=ocr_output_paths,
            force=force_ocr,
            logger=logger,
            body=lambda: _ocr_batch_step(
                root_dir=root_dir,
                processed_dir=processed_dir,
                output_json=ocr_output_paths[0],
                output_md=ocr_output_paths[1],
                language=ocr_language,
                tesseract_path=tesseract_path,
                page_segmentation_mode=page_segmentation_mode,
                engine_mode=engine_mode,
                dpi=dpi,
                preprocess_before_ocr=preprocess_before_ocr,
                enable_region_ocr=enable_region_ocr,
                overwrite=force_ocr,
                max_workers=ocr_max_workers,
                progress_callback=lambda message: logger.write(f"STEP PROGRESS ocr_batch {message}"),
                log_file=ocr_log_path,
                progress_every=ocr_progress_every,
            ),
        )
    else:
        reason = "force_ocr_requires_run_ocr" if force_ocr else "run_ocr_false"
        _append_skipped_step(
            manifest,
            name="ocr_batch",
            status="skipped_not_enabled",
            reason=reason,
            output_paths=ocr_output_paths,
            logger=logger,
        )

    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="input_processing_plan",
        input_roots=[root_dir],
        input_patterns=["**/*"],
        params={"root_dir": str(root_dir)},
        output_paths=[document_dir / "input_processing_plan.json", document_dir / "input_processing_plan.md"],
        force=force_derived,
        logger=logger,
        body=lambda: build_input_processing_plan(
            root_dir=root_dir,
            output_json=document_dir / "input_processing_plan.json",
            output_md=document_dir / "input_processing_plan.md",
            progress_callback=lambda message: logger.write(f"STEP PROGRESS input_processing_plan {message}"),
        ),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="image_preprocessing_plan",
        input_roots=[document_dir],
        input_patterns=["input_processing_plan.json"],
        params={"input_processing_plan": str(document_dir / "input_processing_plan.json")},
        output_paths=[document_dir / "image_preprocessing_plan.json", document_dir / "image_preprocessing_plan.md"],
        force=force_derived,
        logger=logger,
        body=lambda: build_image_preprocessing_plan(
            input_plan_json=document_dir / "input_processing_plan.json",
            output_json=document_dir / "image_preprocessing_plan.json",
            output_md=document_dir / "image_preprocessing_plan.md",
            progress_callback=lambda message: logger.write(f"STEP PROGRESS image_preprocessing_plan {message}"),
        ),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="historical_map_catalog",
        input_roots=[root_dir],
        input_patterns=["**/*"],
        params={"root_dir": str(root_dir)},
        output_paths=[document_dir / "historical_map_catalog.json", document_dir / "historical_map_catalog.md"],
        force=force_derived,
        logger=logger,
        body=lambda: build_historical_map_catalog(
            root_dir=root_dir,
            output_json=document_dir / "historical_map_catalog.json",
            output_md=document_dir / "historical_map_catalog.md",
        ),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="metadata_extraction",
        input_roots=[root_dir],
        input_patterns=["**/*"],
        params={"root_dir": str(root_dir), "processed_dir": str(processed_dir)},
        output_paths=[document_dir / "document_metadata_extraction.json"],
        force=force_derived,
        logger=logger,
        body=lambda: _metadata_step(root_dir=root_dir, processed_dir=processed_dir, output_json=document_dir / "document_metadata_extraction.json"),
    )
    run_metadata_paths = _paths_from_summary(
        document_dir / "document_metadata_extraction.json",
        path_key="metadata_path",
        require_step_output=_step_output_is_current(manifest, "metadata_extraction"),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="text_extraction",
        input_roots=[],
        input_patterns=[],
        input_files=run_metadata_paths,
        params={"processed_dir": str(processed_dir), "root_dir": str(root_dir)},
        output_paths=[document_dir / "document_text_extraction.json"],
        force=force_derived,
        run_when_no_inputs=True,
        logger=logger,
        body=lambda: _text_step(
            processed_dir=processed_dir,
            root_dir=root_dir,
            output_json=document_dir / "document_text_extraction.json",
            metadata_paths=run_metadata_paths,
        ),
    )
    run_text_paths = _paths_from_summary(
        document_dir / "document_text_extraction.json",
        path_key="text_path",
        status_key="text_status",
        status_value="extracted",
        require_step_output=_step_output_is_current(manifest, "text_extraction"),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="candidate_person_profiles_from_documents",
        input_roots=[],
        input_patterns=[],
        input_files=run_text_paths,
        params={"processed_dir": str(processed_dir)},
        output_paths=[
            document_dir / "candidate_person_profiles_from_documents.json",
            document_dir / "candidate_person_profiles_from_documents.md",
        ],
        force=force_derived,
        run_when_no_inputs=True,
        logger=logger,
        body=lambda: build_candidate_person_profiles_from_documents(
            text_dir=processed_dir,
            output_json=document_dir / "candidate_person_profiles_from_documents.json",
            output_md=document_dir / "candidate_person_profiles_from_documents.md",
            text_paths=run_text_paths,
        ),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="document_language_detection",
        input_roots=[],
        input_patterns=[],
        input_files=run_text_paths,
        params={"processed_dir": str(processed_dir), "min_text_chars": min_language_text_chars},
        output_paths=[
            document_dir / "document_language_assessments.json",
            document_dir / "document_language_assessments.md",
        ],
        force=force_derived,
        run_when_no_inputs=True,
        logger=logger,
        body=lambda: detect_document_languages(
            text_dir=processed_dir,
            output_dir=processed_dir,
            output_json=document_dir / "document_language_assessments.json",
            output_md=document_dir / "document_language_assessments.md",
            min_text_chars=min_language_text_chars,
            text_paths=run_text_paths,
        ),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="document_language_routing",
        input_roots=[],
        input_patterns=[],
        input_files=[document_dir / "document_language_assessments.json"],
        params={"processed_dir": str(processed_dir)},
        output_paths=[
            document_dir / "document_language_routing.json",
            document_dir / "document_language_routing.md",
        ],
        force=force_derived,
        run_when_no_inputs=True,
        logger=logger,
        body=lambda: build_document_language_routing_plans(
            language_dir=processed_dir,
            language_json=document_dir / "document_language_assessments.json",
            output_dir=processed_dir,
            output_json=document_dir / "document_language_routing.json",
            output_md=document_dir / "document_language_routing.md",
        ),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="military_glossary_mentions",
        input_roots=[],
        input_patterns=[],
        input_files=run_text_paths,
        params={"processed_dir": str(processed_dir), "glossary_dir": str(resolved_glossary_dir)},
        output_paths=[
            document_dir / "military_glossary_mentions.json",
            document_dir / "military_glossary_mentions.md",
        ],
        force=force_derived,
        run_when_no_inputs=True,
        logger=logger,
        body=lambda: extract_military_glossary_mentions(
            text_dir=processed_dir,
            glossary_dir=resolved_glossary_dir,
            output_json=document_dir / "military_glossary_mentions.json",
            output_md=document_dir / "military_glossary_mentions.md",
            text_paths=run_text_paths,
        ),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="document_chunking",
        input_roots=[],
        input_patterns=[],
        input_files=run_text_paths,
        params={"processed_dir": str(processed_dir), "max_chars": max_chars, "overlap_chars": overlap_chars},
        output_paths=[document_dir / "document_chunks.json", document_dir / "document_chunks.md"],
        force=force_derived,
        run_when_no_inputs=True,
        logger=logger,
        body=lambda: chunk_document_texts(
            text_dir=processed_dir,
            output_dir=processed_dir,
            output_json=document_dir / "document_chunks.json",
            output_md=document_dir / "document_chunks.md",
            max_chars=max_chars,
            overlap_chars=overlap_chars,
            text_paths=run_text_paths,
        ),
    )
    run_chunk_paths = _paths_from_summary(
        document_dir / "document_chunks.json",
        path_key="chunk_file",
        require_step_output=_step_output_is_current(manifest, "document_chunking"),
    )
    llm_chunk_output_paths = [
        document_dir / "llm_chunk_classifications.json",
        document_dir / "llm_chunk_classifications.md",
    ]
    if resolved_enable_llm_chunk_classification:
        _run_delta_step(
            manifest,
            previous_manifest=previous_manifest,
            name="llm_chunk_classification",
            input_roots=[],
            input_patterns=[],
            input_files=run_chunk_paths,
            params={
                "processed_dir": str(processed_dir),
                "provider": resolved_llm_provider,
                "model_name": resolved_llm_model_name,
                "prompt_version": resolved_llm_prompt_version,
                "wsl_distribution": resolved_llm_wsl_distribution,
                "timeout_seconds": resolved_llm_timeout_seconds,
            },
            output_paths=llm_chunk_output_paths,
            force=force_derived,
            run_when_no_inputs=True,
            logger=logger,
            body=lambda: classify_document_chunks(
                chunk_dir=processed_dir,
                output_dir=processed_dir,
                output_json=llm_chunk_output_paths[0],
                output_md=llm_chunk_output_paths[1],
                model_name=resolved_llm_model_name,
                prompt_version=resolved_llm_prompt_version,
                provider=resolved_llm_provider,
                wsl_distribution=resolved_llm_wsl_distribution,
                timeout_seconds=resolved_llm_timeout_seconds,
                chunk_paths=run_chunk_paths,
            ),
        )
    else:
        _append_skipped_step(
            manifest,
            name="llm_chunk_classification",
            status="skipped_not_enabled",
            reason="enable_llm_chunk_classification_false",
            output_paths=llm_chunk_output_paths,
            logger=logger,
        )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="weak_document_segmentation",
        input_roots=[],
        input_patterns=[],
        input_files=run_chunk_paths,
        params={"processed_dir": str(processed_dir)},
        output_paths=[document_dir / "weak_document_segments.json", document_dir / "weak_document_segments.md"],
        force=force_derived,
        run_when_no_inputs=True,
        logger=logger,
        body=lambda: weak_segment_document_chunks(
            chunk_dir=processed_dir,
            output_dir=processed_dir,
            output_json=document_dir / "weak_document_segments.json",
            output_md=document_dir / "weak_document_segments.md",
            chunk_paths=run_chunk_paths,
        ),
    )
    run_segment_paths = _paths_from_summary(
        document_dir / "weak_document_segments.json",
        path_key="segments_file",
        require_step_output=_step_output_is_current(manifest, "weak_document_segmentation"),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="document_mentions",
        input_roots=[],
        input_patterns=[],
        input_files=run_segment_paths,
        params={"processed_dir": str(processed_dir)},
        output_paths=[document_dir / "document_mentions.json", document_dir / "document_mentions.md"],
        force=force_derived,
        run_when_no_inputs=True,
        logger=logger,
        body=lambda: extract_document_mentions(
            segments_dir=processed_dir,
            output_dir=processed_dir,
            output_json=document_dir / "document_mentions.json",
            output_md=document_dir / "document_mentions.md",
            segment_paths=run_segment_paths,
        ),
    )
    run_mention_paths = _paths_from_summary(
        document_dir / "document_mentions.json",
        path_key="mentions_file",
        require_step_output=_step_output_is_current(manifest, "document_mentions"),
    )
    _run_delta_step(
        manifest,
        previous_manifest=previous_manifest,
        name="research_feedback_actions",
        input_roots=[],
        input_patterns=[],
        input_files=run_mention_paths,
        params={"processed_dir": str(processed_dir)},
        output_paths=[document_dir / "research_feedback_actions.json", document_dir / "research_feedback_actions.md"],
        force=force_derived,
        run_when_no_inputs=True,
        logger=logger,
        body=lambda: build_document_research_feedback_actions(
            mentions_dir=processed_dir,
            output_dir=None,
            output_json=document_dir / "research_feedback_actions.json",
            output_md=document_dir / "research_feedback_actions.md",
            mention_paths=run_mention_paths,
        ),
    )

    failed_steps = [step for step in manifest["steps"] if step.get("status") == "failed"]
    manifest["status"] = "failed" if failed_steps else "completed"
    manifest["finished_at"] = _now()
    manifest["outputs"]["manifest_json"] = str(run_dir / "manifest.json")
    manifest["outputs"]["run_summary_md"] = str(run_dir / "run_summary.md")
    logger.write(
        "RUN END local_document_processing "
        f"run_id={resolved_run_id} status={manifest['status']} duration={_duration_text(started_at, manifest['finished_at'])}"
    )
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "run_summary.md").write_text(_render_run_summary(manifest), encoding="utf-8")
    return manifest


def _metadata_step(*, root_dir: Path, processed_dir: Path, output_json: Path) -> dict[str, Any]:
    payload = extract_document_metadata(root_dir=root_dir, output_dir=processed_dir)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _ocr_batch_step(
    *,
    root_dir: Path,
    processed_dir: Path,
    output_json: Path,
    output_md: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str,
    engine_mode: str,
    dpi: str,
    preprocess_before_ocr: bool,
    enable_region_ocr: bool,
    overwrite: bool,
    max_workers: int,
    progress_callback: Callable[[str], None] | None = None,
    log_file: Path | None = None,
    progress_every: int = 25,
) -> dict[str, Any]:
    payload = run_document_ocr_batch(
        root_dir=root_dir,
        output_dir=processed_dir,
        language=language,
        tesseract_path=tesseract_path,
        page_segmentation_mode=page_segmentation_mode,
        engine_mode=engine_mode,
        dpi=dpi,
        preprocess_before_ocr=preprocess_before_ocr,
        enable_region_ocr=enable_region_ocr,
        overwrite=overwrite,
        max_workers=max_workers,
        progress_callback=progress_callback,
        log_file=log_file,
        progress_every=progress_every,
    )
    write_batch_report(report=payload, output_json=output_json, output_md=output_md)
    return payload


def _text_step(*, processed_dir: Path, root_dir: Path, output_json: Path, metadata_paths: list[Path]) -> dict[str, Any]:
    payload = extract_document_text(
        metadata_dir=processed_dir,
        output_dir=processed_dir,
        raw_root_dir=root_dir,
        metadata_paths=metadata_paths,
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _run_delta_step(
    manifest: dict[str, Any],
    *,
    previous_manifest: dict[str, Any],
    name: str,
    input_roots: list[Path],
    input_patterns: list[str],
    input_files: list[Path] | None = None,
    params: dict[str, Any],
    output_paths: list[Path],
    force: bool,
    run_when_no_inputs: bool = False,
    logger: "_RunLogger | None" = None,
    body: Callable[[], dict[str, Any]],
) -> None:
    input_snapshot = _collect_step_input_snapshot(
        name=name,
        input_roots=input_roots,
        input_patterns=input_patterns,
        input_files=input_files,
        logger=logger,
    )
    signature = _step_signature(name=name, input_snapshot=input_snapshot, params=params)
    input_delta = _input_delta(previous_manifest=previous_manifest, name=name, input_snapshot=input_snapshot)
    step = build_running_step_record(
        name=name,
        started_at=_now(),
        output_paths=output_paths,
        signature=signature,
        input_read_error_count=_input_read_error_count(input_snapshot),
        input_delta=input_delta,
        input_snapshot=input_snapshot,
    )
    if logger is not None:
        logger.write(
            "STEP START "
            f"{name} inputs={len(input_snapshot)} force={str(force).lower()} outputs={len(output_paths)}"
        )
    try:
        if not input_snapshot and not run_when_no_inputs:
            step["status"] = "skipped_missing_input"
            step["reason"] = "no_matching_input_files"
        elif not force and _is_cached(previous_manifest=previous_manifest, name=name, signature=signature, output_paths=output_paths):
            step["status"] = "skipped_cached"
            step["reason"] = "signature_and_outputs_unchanged"
        else:
            payload = body()
            step["status"] = _status_from_payload(payload)
            step["summary"] = _summary_from_payload(payload)
            step["error"] = str(payload.get("error", "")) if isinstance(payload, dict) else ""
    except Exception as exc:  # pragma: no cover - integration-level guard.
        step["status"] = "failed"
        step["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        step["finished_at"] = _now()
        if logger is not None:
            logger.write(
                "STEP END "
                f"{name} status={step.get('status', '')} "
                f"duration={_duration_text(step['started_at'], step['finished_at'])} "
                f"reason={step.get('reason', '')} error={step.get('error', '')}"
            )
        manifest["steps"].append(step)


def _collect_step_input_snapshot(
    *,
    name: str,
    input_roots: list[Path],
    input_patterns: list[str],
    input_files: list[Path] | None,
    logger: "_RunLogger | None" = None,
) -> list[dict[str, str]]:
    snapshot_progress = (
        (lambda message: logger.write(f"SNAPSHOT PROGRESS {name} {message}"))
        if logger is not None
        else None
    )
    if logger is not None:
        input_description = (
            f"files={len(input_files)}"
            if input_files is not None
            else f"roots={len(input_roots)} patterns={len(input_patterns)}"
        )
        logger.write(f"SNAPSHOT START {name} {input_description}")
    input_snapshot = (
        _input_files_snapshot(input_files, progress_callback=snapshot_progress)
        if input_files is not None
        else _input_snapshot(input_roots=input_roots, input_patterns=input_patterns, progress_callback=snapshot_progress)
    )
    if logger is not None:
        logger.write(f"SNAPSHOT END {name} inputs={len(input_snapshot)} read_errors={_input_read_error_count(input_snapshot)}")
    return input_snapshot


def _append_skipped_step(
    manifest: dict[str, Any],
    *,
    name: str,
    status: str,
    reason: str,
    output_paths: list[Path],
    logger: "_RunLogger | None" = None,
) -> None:
    started_at = _now()
    finished_at = _now()
    if logger is not None:
        logger.write(f"STEP START {name} inputs=0 force=false outputs={len(output_paths)}")
        logger.write(f"STEP END {name} status={status} duration={_duration_text(started_at, finished_at)} reason={reason} error=")
    manifest["steps"].append(
        build_skipped_step_record(
            name=name,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            reason=reason,
            output_paths=output_paths,
        )
    )


def _is_cached(*, previous_manifest: dict[str, Any], name: str, signature: str, output_paths: list[Path]) -> bool:
    if not previous_manifest:
        return False
    previous_steps = previous_manifest.get("steps", [])
    if not isinstance(previous_steps, list):
        return False
    for step in previous_steps:
        if not isinstance(step, dict):
            continue
        if step.get("name") != name:
            continue
        if step.get("status") not in {"completed", "skipped_cached"}:
            return False
        if str(step.get("signature", "")) != signature:
            return False
        return all(path.exists() for path in output_paths)
    return False


def _step_signature(*, name: str, input_snapshot: list[dict[str, str]], params: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(LOCAL_PROCESSING_VERSION.encode("utf-8"))
    digest.update(name.encode("utf-8"))
    digest.update(json.dumps(params, sort_keys=True, ensure_ascii=True).encode("utf-8"))
    for item in input_snapshot:
        digest.update(str(item.get("path", "")).encode("utf-8"))
        digest.update(str(item.get("sha256", "")).encode("utf-8"))
    return digest.hexdigest()


def _matching_files(
    *,
    input_roots: list[Path],
    input_patterns: list[str],
    progress_callback: Callable[[str], None] | None = None,
) -> list[Path]:
    files: set[Path] = set()
    progress = _ProgressReporter(progress_callback)
    for root in input_roots:
        if not root.exists():
            progress.report(f"matching root_missing root={root}", force=True)
            continue
        for pattern in input_patterns:
            progress.report(f"matching pattern_start root={root} pattern={pattern} matched={len(files)}", force=True)
            for path in root.rglob(pattern):
                if path.is_file():
                    files.add(path)
                    progress.report(f"matching matched={len(files)} root={root} pattern={pattern}")
            progress.report(f"matching pattern_done root={root} pattern={pattern} matched={len(files)}", force=True)
    return sorted(files)


def _input_snapshot(
    *,
    input_roots: list[Path],
    input_patterns: list[str],
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict[str, str]]:
    snapshot: list[dict[str, str]] = []
    paths = _matching_files(input_roots=input_roots, input_patterns=input_patterns, progress_callback=progress_callback)
    progress = _ProgressReporter(progress_callback)
    progress.report(f"hashing start count={len(paths)}", force=True)
    for index, path in enumerate(paths, start=1):
        snapshot.append(_input_snapshot_item(path))
        read_errors = _input_read_error_count(snapshot)
        progress.report(f"hashing {index}/{len(paths)} read_errors={read_errors}")
    progress.report(f"hashing done count={len(snapshot)} read_errors={_input_read_error_count(snapshot)}", force=True)
    return snapshot


def _input_files_snapshot(
    input_files: list[Path],
    *,
    progress_callback: Callable[[str], None] | None = None,
) -> list[dict[str, str]]:
    snapshot: list[dict[str, str]] = []
    paths = sorted({Path(item) for item in input_files})
    progress = _ProgressReporter(progress_callback)
    progress.report(f"hashing explicit start count={len(paths)}", force=True)
    for index, path in enumerate(paths, start=1):
        if path.exists() and path.is_file():
            snapshot.append(_input_snapshot_item(path))
        progress.report(f"hashing explicit {index}/{len(paths)} kept={len(snapshot)} read_errors={_input_read_error_count(snapshot)}")
    progress.report(f"hashing explicit done count={len(snapshot)} read_errors={_input_read_error_count(snapshot)}", force=True)
    return snapshot


def _input_snapshot_item(path: Path) -> dict[str, str]:
    item = {"path": str(path), "sha256": ""}
    try:
        item["sha256"] = _sha256_file(path)
    except OSError as exc:
        item["read_error"] = f"{type(exc).__name__}: {exc}"
    return item


def _input_read_error_count(input_snapshot: list[dict[str, str]]) -> int:
    return sum(1 for item in input_snapshot if item.get("read_error"))


class _ProgressReporter:
    def __init__(self, callback: Callable[[str], None] | None, *, item_interval: int = 500, seconds_interval: float = 30.0) -> None:
        self.callback = callback
        self.item_interval = item_interval
        self.seconds_interval = seconds_interval
        self.last_item = 0
        self.last_time = time.monotonic()

    def report(self, message: str, *, force: bool = False) -> None:
        if self.callback is None:
            return
        item = _progress_item(message)
        now = time.monotonic()
        if force or item - self.last_item >= self.item_interval or now - self.last_time >= self.seconds_interval:
            self.callback(message)
            self.last_item = item
            self.last_time = now


def _progress_item(message: str) -> int:
    for token in message.split():
        value = token
        if "=" in token:
            _name, _sep, value = token.partition("=")
        if "/" in value:
            current, _sep, _total = value.partition("/")
        else:
            current = value
        try:
            return int(current)
        except ValueError:
            continue
    return 0


def _input_delta(*, previous_manifest: dict[str, Any], name: str, input_snapshot: list[dict[str, str]]) -> dict[str, Any]:
    current = _snapshot_map(input_snapshot)
    previous = _previous_snapshot(previous_manifest=previous_manifest, name=name)
    if not previous:
        return {
            "status": "first_run",
            "added_count": len(current),
            "modified_count": 0,
            "removed_count": 0,
            "added": _sample_paths(sorted(current)),
            "modified": [],
            "removed": [],
        }
    added = sorted(path for path in current if path not in previous)
    removed = sorted(path for path in previous if path not in current)
    modified = sorted(path for path, digest in current.items() if path in previous and previous[path] != digest)
    status = "unchanged" if not added and not removed and not modified else "changed"
    return {
        "status": status,
        "added_count": len(added),
        "modified_count": len(modified),
        "removed_count": len(removed),
        "added": _sample_paths(added),
        "modified": _sample_paths(modified),
        "removed": _sample_paths(removed),
    }


def _snapshot_map(snapshot: list[dict[str, str]]) -> dict[str, str]:
    return {str(item.get("path", "")): str(item.get("sha256", "")) for item in snapshot if str(item.get("path", ""))}


def _previous_snapshot(*, previous_manifest: dict[str, Any], name: str) -> dict[str, str]:
    if not previous_manifest:
        return {}
    steps = previous_manifest.get("steps", [])
    if not isinstance(steps, list):
        return {}
    for step in steps:
        if not isinstance(step, dict) or step.get("name") != name:
            continue
        snapshot = step.get("input_snapshot", [])
        return _snapshot_map(snapshot if isinstance(snapshot, list) else [])
    return {}


def _step_output_is_current(manifest: dict[str, Any], name: str) -> bool:
    for step in reversed(manifest.get("steps", [])):
        if not isinstance(step, dict) or step.get("name") != name:
            continue
        return str(step.get("status", "")) in {"completed", "skipped_cached"}
    return False


def _paths_from_summary(
    summary_path: Path,
    *,
    path_key: str,
    status_key: str = "",
    status_value: str = "",
    require_step_output: bool = True,
) -> list[Path]:
    if not require_step_output or not summary_path.exists():
        return []
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []
    paths: list[Path] = []
    documents = payload.get("documents", [])
    if not isinstance(documents, list):
        return []
    for document in documents:
        if not isinstance(document, dict):
            continue
        if status_key and str(document.get(status_key, "")) != status_value:
            continue
        path = Path(str(document.get(path_key, "")).strip())
        if path:
            paths.append(path)
    return paths


def _sample_paths(paths: list[str], *, limit: int = 10) -> list[str]:
    return paths[:limit]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _status_from_payload(payload: dict[str, Any]) -> str:
    if int(payload.get("exit_code", 0) or 0) != 0:
        return "failed"
    return "completed"


def _summary_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested_summary = payload.get("summary")
    if isinstance(nested_summary, dict):
        return nested_summary
    keys = [
        "document_count",
        "asset_count",
        "error_count",
        "action_counts",
        "map_candidate_count",
        "total",
        "processed",
        "skipped_existing_text",
        "skipped_missing_sidecar",
        "skipped_unreadable_sidecar",
        "skipped_sidecar_mismatch",
        "skipped_duplicate_output",
        "error",
        "extracted_count",
        "extraction_status_counts",
        "document_class_counts",
        "assessment_count",
        "routing_count",
        "skipped_count",
        "chunk_count",
        "classification_count",
        "segment_count",
        "mention_count",
        "candidate_profile_count",
        "tabular_document_count",
        "action_count",
    ]
    return {key: payload[key] for key in keys if key in payload}


def _load_previous_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    if payload.get("@type") != "LocalDocumentProcessingRunManifest":
        return {}
    return payload


def _default_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class _RunLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, message: str) -> None:
        line = f"[{_now()}] {message}"
        print(line, flush=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "y", "on"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue processing documentale locale con manifest delta.")
    parser.add_argument("--root-dir", default="data/raw")
    parser.add_argument("--processed-dir", default="data/processed/documents")
    parser.add_argument("--results-dir", "--remote-results-dir", dest="results_dir", default="risultati")
    parser.add_argument("--research-dir", default="ricerche")
    parser.add_argument("--glossary-dir", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-ocr", action="store_true")
    parser.add_argument("--force-derived", action="store_true")
    parser.add_argument("--force-ocr", action="store_true")
    parser.add_argument("--preprocess-before-ocr", action="store_true")
    parser.add_argument("--enable-region-ocr", action="store_true")
    parser.add_argument("--ocr-language", default="ita")
    parser.add_argument("--tesseract-path", default="tesseract")
    parser.add_argument("--psm", default="")
    parser.add_argument("--oem", default="")
    parser.add_argument("--dpi", default="")
    parser.add_argument("--ocr-max-workers", type=int, default=2)
    parser.add_argument("--ocr-progress-every", type=int, default=25)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--overlap-chars", type=int, default=DEFAULT_OVERLAP_CHARS)
    parser.add_argument("--min-language-text-chars", type=int, default=MIN_TEXT_CHARS)
    parser.add_argument("--enable-llm-chunk-classification", action="store_true", default=None)
    parser.add_argument("--llm-chunk-provider", default="")
    parser.add_argument("--llm-chunk-model-name", default="")
    parser.add_argument("--llm-chunk-prompt-version", default="")
    parser.add_argument("--llm-chunk-wsl-distribution", default="")
    parser.add_argument("--llm-chunk-timeout-seconds", type=int, default=0)
    args = parser.parse_args()

    manifest = run_local_document_processing(
        root_dir=Path(args.root_dir),
        processed_dir=Path(args.processed_dir),
        results_dir=Path(args.results_dir),
        research_dir=Path(args.research_dir),
        glossary_dir=Path(args.glossary_dir) if args.glossary_dir else None,
        run_id=args.run_id,
        run_ocr=args.run_ocr,
        force_derived=args.force_derived,
        force_ocr=args.force_ocr,
        preprocess_before_ocr=args.preprocess_before_ocr,
        enable_region_ocr=args.enable_region_ocr,
        ocr_language=args.ocr_language,
        tesseract_path=args.tesseract_path,
        page_segmentation_mode=args.psm,
        engine_mode=args.oem,
        dpi=args.dpi,
        ocr_max_workers=args.ocr_max_workers,
        ocr_progress_every=args.ocr_progress_every,
        max_chars=args.max_chars,
        overlap_chars=args.overlap_chars,
        min_language_text_chars=args.min_language_text_chars,
        enable_llm_chunk_classification=args.enable_llm_chunk_classification,
        llm_provider=args.llm_chunk_provider,
        llm_model_name=args.llm_chunk_model_name,
        llm_prompt_version=args.llm_chunk_prompt_version,
        llm_wsl_distribution=args.llm_chunk_wsl_distribution,
        llm_timeout_seconds=args.llm_chunk_timeout_seconds or None,
    )
    print(f"Run locale documentale: {manifest['run_id']}")
    print(f"Stato: {manifest['status']}")
    print(f"Manifest: {manifest['outputs']['manifest_json']}")
    print(f"Summary: {manifest['outputs']['run_summary_md']}")
    return 0 if manifest["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
