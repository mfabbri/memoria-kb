from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .manual_registration import register_manual_document

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def preview_manual_documents_batch(
    *,
    root_dir: Path,
    source_id: str,
    archival_reference: str,
    access_date: str = "",
    title_template: str = "{filename}",
    review_status: str = "unreviewed",
) -> dict[str, Any]:
    """Discover the batch without creating or changing sidecars."""
    root = _validate_batch_inputs(
        root_dir=root_dir,
        source_id=source_id,
        archival_reference=archival_reference,
    )
    documents: list[dict[str, Any]] = []
    for image_path in _image_paths(root):
        sidecar = _sidecar_path_for_image(image_path)
        if sidecar.exists():
            documents.append(
                {
                    "status": "skipped_existing_sidecar",
                    "file": str(image_path),
                    "sidecar_path": str(sidecar),
                    "reason": "document.yaml gia' presente",
                }
            )
            continue
        documents.append(
            {
                "status": "would_register",
                "file": str(image_path),
                "sidecar_path": str(sidecar),
                "title": _title_from_template(template=title_template, image_path=image_path, root=root),
                "review_status": review_status.strip() or "unreviewed",
            }
        )
    return _batch_report(
        root=root,
        source_id=source_id,
        archival_reference=archival_reference,
        access_date=access_date,
        title_template=title_template,
        documents=documents,
        preview_only=True,
    )


def register_manual_documents_batch(
    *,
    root_dir: Path,
    source_id: str,
    archival_reference: str,
    access_date: str = "",
    title_template: str = "{filename}",
    review_status: str = "unreviewed",
    overwrite: bool = False,
) -> dict[str, Any]:
    root = _validate_batch_inputs(
        root_dir=root_dir,
        source_id=source_id,
        archival_reference=archival_reference,
    )

    documents: list[dict[str, Any]] = []
    for image_path in _image_paths(root):
        sidecar = _sidecar_path_for_image(image_path)
        if sidecar.exists() and not overwrite:
            documents.append(
                {
                    "status": "skipped_existing_sidecar",
                    "file": str(image_path),
                    "sidecar_path": str(sidecar),
                    "reason": "document.yaml gia' presente",
                }
            )
            continue
        title = _title_from_template(template=title_template, image_path=image_path, root=root)
        try:
            result = register_manual_document(
                file_path=image_path,
                source_id=source_id,
                title=title,
                archival_reference=archival_reference,
                access_date=access_date,
                review_status=review_status,
                overwrite=overwrite,
                sidecar_path=sidecar,
            )
        except (FileExistsError, FileNotFoundError, ValueError) as exc:
            documents.append({"status": "error", "file": str(image_path), "sidecar_path": str(sidecar), "error": str(exc)})
            continue
        documents.append(
            {
                "status": "registered",
                "file": str(image_path),
                "sidecar_path": result["sidecar_path"],
                "source_document_id": result["document"]["document_id"],
                "title": result["document"]["title"],
                "review_status": result["document"]["metadata"]["review_status"],
            }
        )

    return _batch_report(
        root=root,
        source_id=source_id,
        archival_reference=archival_reference,
        access_date=access_date,
        title_template=title_template,
        documents=documents,
        preview_only=False,
        overwrite=overwrite,
    )


def _batch_report(
    *,
    root: Path,
    source_id: str,
    archival_reference: str,
    access_date: str,
    title_template: str,
    documents: list[dict[str, Any]],
    preview_only: bool,
    overwrite: bool = False,
) -> dict[str, Any]:
    return {
        "@type": "ManualDocumentBatchRegistration",
        "root_dir": str(root),
        "source_id": source_id.strip(),
        "archival_reference": archival_reference.strip(),
        "access_date": access_date,
        "title_template": title_template,
        "overwrite": overwrite,
        "preview_only": preview_only,
        "summary": _summary(documents),
        "documents": documents,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Registrazione batch documenti manuali",
        "",
        f"Root: `{report.get('root_dir', '')}`",
        f"Source ID: `{report.get('source_id', '')}`",
        f"Riferimento archivistico: {report.get('archival_reference', '')}",
        "",
        "## Sintesi",
        "",
        f"- Totale immagini: {summary.get('total', 0)}",
        f"- Registrate: {summary.get('registered', 0)}",
        f"- Gia' registrate: {summary.get('skipped_existing_sidecar', 0)}",
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
                f"- Sidecar: `{item.get('sidecar_path', '')}`",
                f"- Titolo: {item.get('title', '')}",
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


def _summary(documents: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(documents), "would_register": 0, "registered": 0, "skipped_existing_sidecar": 0, "error": 0}
    for item in documents:
        status = str(item.get("status", ""))
        if status in summary:
            summary[status] += 1
    return summary


def _validate_batch_inputs(*, root_dir: Path, source_id: str, archival_reference: str) -> Path:
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Root registrazione batch non trovata: {root}")
    if not source_id.strip():
        raise ValueError("source_id obbligatorio per registrazione batch prudente.")
    if not archival_reference.strip():
        raise ValueError("archival_reference obbligatorio per registrazione batch prudente.")
    return root


def _image_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def _title_from_template(*, template: str, image_path: Path, root: Path) -> str:
    relative = image_path.relative_to(root)
    return template.format(
        filename=image_path.name,
        stem=image_path.stem,
        relative_path=str(relative),
        parent=image_path.parent.name,
    ).strip() or image_path.name


def _sidecar_path_for_image(image_path: Path) -> Path:
    return image_path.with_name(f"{image_path.name}.document.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra ricorsivamente immagini manuali creando document.yaml.")
    parser.add_argument("--root-dir", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--archival-reference", required=True)
    parser.add_argument("--access-date", default="")
    parser.add_argument("--title-template", default="{filename}")
    parser.add_argument("--review-status", default="unreviewed")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    try:
        report = register_manual_documents_batch(
            root_dir=Path(args.root_dir),
            source_id=args.source_id,
            archival_reference=args.archival_reference,
            access_date=args.access_date,
            title_template=args.title_template,
            review_status=args.review_status,
            overwrite=args.overwrite,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    write_batch_report(
        report=report,
        output_json=Path(args.output_json),
        output_md=Path(args.output_md) if args.output_md.strip() else None,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
