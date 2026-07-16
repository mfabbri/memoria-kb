from __future__ import annotations

import argparse
import json
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Callable

import yaml

from .metadata_extraction import extract_document_metadata
from .ocr_tesseract import CommandRunner, run_document_ocr

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def run_document_ocr_batch(
    *,
    root_dir: Path,
    output_dir: Path = Path("data/processed/documents"),
    language: str = "ita",
    tesseract_path: str = "tesseract",
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    dpi: str = "",
    preprocess_before_ocr: bool = False,
    enable_region_ocr: bool = False,
    review_status: str = "unreviewed",
    overwrite: bool = False,
    max_workers: int = 2,
    command_runner: CommandRunner | None = None,
    progress_callback: Callable[[str], None] | None = None,
    log_file: Path | None = None,
    progress_every: int = 25,
) -> dict[str, Any]:
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Root OCR batch non trovata: {root}")
    workers = max(1, int(max_workers))
    progress_interval = max(1, int(progress_every))
    log_path = Path(log_file) if log_file is not None else None
    started_at = perf_counter()
    _progress(
        "RUN START ocr_batch "
        f"root={root} output_dir={output_dir} language={language} workers={workers} "
        f"overwrite={overwrite} preprocess_before_ocr={preprocess_before_ocr} "
        f"enable_region_ocr={enable_region_ocr} psm={page_segmentation_mode or '-'} "
        f"oem={engine_mode or '-'} dpi={dpi or '-'}",
        progress_callback=progress_callback,
        log_file=log_path,
    )
    _progress(
        "COLLECT START image_candidates",
        progress_callback=progress_callback,
        log_file=log_path,
    )
    candidates = _collect_candidates(root=root, output_dir=Path(output_dir), overwrite=overwrite)
    candidate_counts = _status_counts(candidates)
    pending_count = candidate_counts.get("pending", 0)
    _progress(
        "COLLECT END image_candidates "
        f"total={len(candidates)} pending={pending_count} "
        f"skipped_existing_text={candidate_counts.get('skipped_existing_text', 0)} "
        f"skipped_missing_sidecar={candidate_counts.get('skipped_missing_sidecar', 0)} "
        f"skipped_unreadable_sidecar={candidate_counts.get('skipped_unreadable_sidecar', 0)} "
        f"skipped_sidecar_mismatch={candidate_counts.get('skipped_sidecar_mismatch', 0)} "
        f"skipped_duplicate_output={candidate_counts.get('skipped_duplicate_output', 0)}",
        progress_callback=progress_callback,
        log_file=log_path,
    )

    if any(item["status"] == "pending" for item in candidates):
        metadata_progress = None
        if progress_callback is not None or log_path is not None:
            def metadata_progress(message: str) -> None:
                _progress(
                    f"METADATA PROGRESS {message}",
                    progress_callback=progress_callback,
                    log_file=log_path,
                )

        _progress(
            f"METADATA START pending={pending_count}",
            progress_callback=progress_callback,
            log_file=log_path,
        )
        extract_document_metadata(
            root_dir=root,
            output_dir=output_dir,
            progress_callback=metadata_progress,
            progress_every=progress_interval,
        )
        _progress(
            f"METADATA END pending={pending_count}",
            progress_callback=progress_callback,
            log_file=log_path,
        )

    results: list[dict[str, Any]] = [item for item in candidates if item["status"] != "pending"]
    pending = [item for item in candidates if item["status"] == "pending"]
    _progress(
        f"OCR START pending={len(pending)} workers={workers}",
        progress_callback=progress_callback,
        log_file=log_path,
    )
    completed = 0
    active_ocr: dict[int, str] = {}
    active_ocr_lock = Lock()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _run_single_with_progress,
                item=item,
                item_index=index,
                item_count=len(pending),
                root_dir=root,
                output_dir=output_dir,
                language=language,
                tesseract_path=tesseract_path,
                page_segmentation_mode=page_segmentation_mode,
                engine_mode=engine_mode,
                dpi=dpi,
                preprocess_before_ocr=preprocess_before_ocr,
                enable_region_ocr=enable_region_ocr,
                review_status=review_status,
                overwrite=overwrite,
                command_runner=command_runner,
                progress_callback=progress_callback,
                log_file=log_path,
                active_ocr=active_ocr,
                active_ocr_lock=active_ocr_lock,
            ): item
            for index, item in enumerate(pending, start=1)
        }
        pending_futures = set(futures)
        ocr_wait_started_at = perf_counter()
        while pending_futures:
            done_futures, pending_futures = wait(
                pending_futures,
                timeout=30.0,
                return_when=FIRST_COMPLETED,
            )
            if not done_futures:
                with active_ocr_lock:
                    active_files = [active_ocr[index] for index in sorted(active_ocr)]
                _progress(
                    "OCR HEARTBEAT "
                    f"completed={completed}/{len(pending)} "
                    f"active={len(active_files)} queued_or_running={len(pending_futures)} "
                    f"elapsed_seconds={perf_counter()-ocr_wait_started_at:.1f}s "
                    f"active_files={_short_file_list(active_files)}",
                    progress_callback=progress_callback,
                    log_file=log_path,
                )
                continue
            for future in done_futures:
                result = future.result()
                results.append(result)
                completed += 1
                if completed == 1 or completed == len(pending) or completed % progress_interval == 0:
                    _progress(
                        "OCR PROGRESS "
                        f"completed={completed}/{len(pending)} status={result.get('status', '')} "
                        f"file={result.get('file', '')}",
                        progress_callback=progress_callback,
                        log_file=log_path,
                    )
    _progress(
        f"OCR END pending={len(pending)} completed={completed}",
        progress_callback=progress_callback,
        log_file=log_path,
    )

    ordered_results = sorted(results, key=lambda item: item.get("file", ""))
    summary = _summary(ordered_results)
    elapsed_seconds = perf_counter() - started_at
    _progress(
        "RUN END ocr_batch "
        f"status=completed duration_seconds={elapsed_seconds:.1f} "
        f"processed={summary.get('processed', 0)} skipped_existing_text={summary.get('skipped_existing_text', 0)} "
        f"error={summary.get('error', 0)}",
        progress_callback=progress_callback,
        log_file=log_path,
    )
    return {
        "@type": "DocumentOcrBatchReport",
        "root_dir": str(root),
        "output_dir": str(output_dir),
        "max_workers": workers,
        "progress_every": progress_interval,
        "log_file": str(log_path) if log_path is not None else "",
        "language": language,
        "tesseract_path": tesseract_path,
        "page_segmentation_mode": page_segmentation_mode,
        "engine_mode": engine_mode,
        "dpi": dpi,
        "preprocess_before_ocr": preprocess_before_ocr,
        "enable_region_ocr": enable_region_ocr,
        "overwrite": overwrite,
        "summary": summary,
        "documents": ordered_results,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# OCR batch preview",
        "",
        f"Root: `{report.get('root_dir', '')}`",
        f"Output: `{report.get('output_dir', '')}`",
        f"Max workers: `{report.get('max_workers', '')}`",
        "",
        "## Sintesi",
        "",
        f"- Totale immagini: {summary.get('total', 0)}",
        f"- Processate: {summary.get('processed', 0)}",
        f"- Gia' presenti: {summary.get('skipped_existing_text', 0)}",
        f"- Senza sidecar: {summary.get('skipped_missing_sidecar', 0)}",
        f"- Sidecar illeggibili: {summary.get('skipped_unreadable_sidecar', 0)}",
        f"- Sidecar non corrispondenti: {summary.get('skipped_sidecar_mismatch', 0)}",
        f"- Output duplicati nella run: {summary.get('skipped_duplicate_output', 0)}",
        f"- Errori: {summary.get('error', 0)}",
        "",
        "## Documenti",
        "",
    ]
    for item in report.get("documents", []):
        lines.extend(
            [
                f"### {item.get('status', '')}: {item.get('file', '')}",
                "",
                f"- Sidecar: `{item.get('sidecar', '')}`",
                f"- Text: `{item.get('text_path', '')}`",
                f"- Motivo/errore: {item.get('reason', item.get('error', ''))}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_batch_report(*, report: dict[str, Any], output_json: Path, output_md: Path | None = None) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown_report(report), encoding="utf-8")


def _progress(
    message: str,
    *,
    progress_callback: Callable[[str], None] | None,
    log_file: Path | None,
) -> None:
    if progress_callback is None and log_file is None:
        return
    line = f"{datetime.now(UTC).isoformat()} {message}"
    if progress_callback is not None:
        progress_callback(line)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _short_file_list(files: list[str], *, limit: int = 4) -> str:
    if not files:
        return "-"
    visible = files[:limit]
    suffix = f"; +{len(files) - limit} more" if len(files) > limit else ""
    return "; ".join(visible) + suffix


def _collect_candidates(*, root: Path, output_dir: Path, overwrite: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    pending_text_paths: set[str] = set()
    for image_path in sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS):
        sidecar = _sidecar_path_for_image(image_path)
        if not sidecar.exists():
            legacy_sidecar = image_path.with_name("document.yaml")
            if legacy_sidecar.exists():
                sidecar = legacy_sidecar
            else:
                items.append({"status": "skipped_missing_sidecar", "file": str(image_path), "sidecar": str(sidecar), "reason": "document.yaml assente"})
                continue
        try:
            sidecar_payload = _load_sidecar(sidecar)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            items.append(
                {
                    "status": "skipped_unreadable_sidecar",
                    "file": str(image_path),
                    "sidecar": str(sidecar),
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        if not _sidecar_matches_file(sidecar=sidecar_payload, image_path=image_path):
            items.append({"status": "skipped_sidecar_mismatch", "file": str(image_path), "sidecar": str(sidecar), "reason": "document.yaml non riferito a questa immagine"})
            continue
        text_path = _expected_text_path(output_dir=output_dir, sidecar=sidecar_payload)
        if text_path.exists() and not overwrite:
            items.append({"status": "skipped_existing_text", "file": str(image_path), "sidecar": str(sidecar), "text_path": str(text_path), "reason": "text json gia' presente"})
            continue
        normalized_text_path = str(text_path.resolve())
        if normalized_text_path in pending_text_paths and not overwrite:
            items.append({"status": "skipped_duplicate_output", "file": str(image_path), "sidecar": str(sidecar), "text_path": str(text_path), "reason": "output text duplicato nella stessa run"})
            continue
        pending_text_paths.add(normalized_text_path)
        items.append({"status": "pending", "file": str(image_path), "sidecar": str(sidecar), "text_path": str(text_path)})
    return items


def _run_single_with_progress(
    *,
    item: dict[str, Any],
    item_index: int,
    item_count: int,
    root_dir: Path,
    output_dir: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str,
    engine_mode: str,
    dpi: str,
    preprocess_before_ocr: bool,
    enable_region_ocr: bool,
    review_status: str,
    overwrite: bool,
    command_runner: CommandRunner | None,
    progress_callback: Callable[[str], None] | None,
    log_file: Path | None,
    active_ocr: dict[int, str],
    active_ocr_lock: Lock,
) -> dict[str, Any]:
    file_path = str(item.get("file", ""))
    with active_ocr_lock:
        active_ocr[item_index] = file_path
    item_started_at = perf_counter()
    _progress(
        f"OCR ITEM START index={item_index}/{item_count} file={file_path}",
        progress_callback=progress_callback,
        log_file=log_file,
    )
    status = "unknown"
    try:
        result = _run_single(
            item=item,
            root_dir=root_dir,
            output_dir=output_dir,
            language=language,
            tesseract_path=tesseract_path,
            page_segmentation_mode=page_segmentation_mode,
            engine_mode=engine_mode,
            dpi=dpi,
            preprocess_before_ocr=preprocess_before_ocr,
            enable_region_ocr=enable_region_ocr,
            review_status=review_status,
            overwrite=overwrite,
            command_runner=command_runner,
        )
        status = str(result.get("status", ""))
        return result
    except BaseException as exc:
        status = f"exception:{type(exc).__name__}"
        raise
    finally:
        with active_ocr_lock:
            active_ocr.pop(item_index, None)
        _progress(
            "OCR ITEM END "
            f"index={item_index}/{item_count} status={status} "
            f"duration_seconds={perf_counter()-item_started_at:.1f} file={file_path}",
            progress_callback=progress_callback,
            log_file=log_file,
        )


def _run_single(
    *,
    item: dict[str, Any],
    root_dir: Path,
    output_dir: Path,
    language: str,
    tesseract_path: str,
    page_segmentation_mode: str,
    engine_mode: str,
    dpi: str,
    preprocess_before_ocr: bool,
    enable_region_ocr: bool,
    review_status: str,
    overwrite: bool,
    command_runner: CommandRunner | None,
) -> dict[str, Any]:
    try:
        result = run_document_ocr(
            file_path=Path(item["file"]),
            sidecar_path=Path(item["sidecar"]),
            root_dir=root_dir,
            output_dir=output_dir,
            language=language,
            tesseract_path=tesseract_path,
            page_segmentation_mode=page_segmentation_mode,
            engine_mode=engine_mode,
            dpi=dpi,
            preprocess_before_ocr=preprocess_before_ocr,
            enable_region_ocr=enable_region_ocr,
            review_status=review_status,
            overwrite=overwrite,
            command_runner=command_runner,
        )
    except FileExistsError as exc:
        return {
            **item,
            "status": "skipped_existing_text",
            "reason": str(exc),
            "existing_text_path": _existing_text_path_from_error(str(exc)),
        }
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return {**item, "status": "error", "error": str(exc)}
    return {
        **item,
        "status": "processed",
        "text_path": result.get("text_path", item.get("text_path", "")),
        "source_document_id": result.get("source_document_id", ""),
        "ocr_quality_status": result.get("ocr_quality_status", ""),
        "ocr_preprocessing_status": result.get("ocr_preprocessing_status", ""),
        "ocr_region_status": result.get("ocr_region_status", ""),
        "ocr_effective_page_segmentation_mode": result.get("ocr_effective_page_segmentation_mode", ""),
    }


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "total": len(items),
        "processed": 0,
        "skipped_existing_text": 0,
        "skipped_missing_sidecar": 0,
        "skipped_unreadable_sidecar": 0,
        "skipped_sidecar_mismatch": 0,
        "skipped_duplicate_output": 0,
        "error": 0,
    }
    for item in items:
        status = str(item.get("status", ""))
        if status in summary:
            summary[status] += 1
    return summary


def _status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status", ""))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _load_sidecar(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _existing_text_path_from_error(message: str) -> str:
    prefix = "Testo processato gia' presente:"
    if prefix not in message:
        return ""
    return message.split(prefix, 1)[1].strip()


def _sidecar_matches_file(*, sidecar: dict[str, Any], image_path: Path) -> bool:
    local_path = str(sidecar.get("local_path", "")).strip()
    if not local_path:
        return True
    try:
        return Path(local_path).resolve() == image_path.resolve()
    except OSError:
        return False


def _expected_text_path(*, output_dir: Path, sidecar: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(sidecar.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(sidecar.get("document_id", "")) or "unknown")
    return output_dir / source_id / f"{document_id}.text.json"


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def _sidecar_path_for_image(image_path: Path) -> Path:
    return image_path.with_name(f"{image_path.name}.document.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue OCR Tesseract batch su immagini registrate con document.yaml.")
    parser.add_argument("--root-dir", required=True)
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--language", default="ita")
    parser.add_argument("--tesseract-path", default="tesseract")
    parser.add_argument("--psm", default="")
    parser.add_argument("--oem", default="")
    parser.add_argument("--dpi", default="")
    parser.add_argument("--preprocess-before-ocr", action="store_true")
    parser.add_argument("--enable-region-ocr", action="store_true")
    parser.add_argument("--review-status", default="unreviewed")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--log-file", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    try:
        report = run_document_ocr_batch(
            root_dir=Path(args.root_dir),
            output_dir=Path(args.output_dir),
            language=args.language,
            tesseract_path=args.tesseract_path,
            page_segmentation_mode=args.psm,
            engine_mode=args.oem,
            dpi=args.dpi,
            preprocess_before_ocr=args.preprocess_before_ocr,
            enable_region_ocr=args.enable_region_ocr,
            review_status=args.review_status,
            overwrite=args.overwrite,
            max_workers=args.max_workers,
            progress_callback=print,
            log_file=Path(args.log_file) if args.log_file.strip() else None,
            progress_every=args.progress_every,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    write_batch_report(
        report=report,
        output_json=Path(args.output_json),
        output_md=Path(args.output_md) if args.output_md.strip() else None,
    )
    _progress(
        f"REPORT WRITTEN json={args.output_json} md={args.output_md or '-'}",
        progress_callback=print,
        log_file=Path(args.log_file) if args.log_file.strip() else None,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
