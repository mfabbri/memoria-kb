"""Manual image transcription through a hash-bound, review-only CLI wizard."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .transcription_registration import build_bound_manual_transcription

_FLAGS = {"claim_eligible": False, "claim_promotion_allowed": False,
          "canonical_write_allowed": False, "profile_write_allowed": False,
          "person_identity_resolved": False, "machine_pass": False}


def _bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _path(value: Any, base: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing explicit local file path.")
    path = Path(value)
    return (path if path.is_absolute() else base / path).resolve(strict=True)


def _reference(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": _digest(path.read_bytes())}


def _load_images(report_path: Path, document_ids: list[str]) -> dict[str, Any]:
    if not document_ids or len(set(document_ids)) != len(document_ids):
        raise ValueError("Select distinct explicit image document IDs.")
    report_path = report_path.resolve(strict=True)
    raw = report_path.read_bytes()
    report = json.loads(raw)
    if not isinstance(report, dict):
        raise ValueError("Expected an acquisition report object.")
    summary = report.get("acquired_documents_summary")
    items = summary.get("items") if isinstance(summary, dict) else None
    if not isinstance(items, list):
        raise ValueError("Report has no acquired_documents_summary.items.")
    images = []
    paths_seen: set[Path] = set()
    for document_id in document_ids:
        if any(isinstance(parent, dict) and not isinstance(parent.get("related_documents", []), list)
               for parent in items):
            raise ValueError("related_documents must be a list.")
        matches = [(parent, item) for parent in items if isinstance(parent, dict)
                   for item in parent.get("related_documents", []) if isinstance(item, dict)
                   and item.get("source_document_id") == document_id]
        if len(matches) != 1:
            raise ValueError(f"Image ID must occur exactly once in the report: {document_id}")
        parent, item = matches[0]
        parent_id = parent.get("source_document_id")
        source_id = parent.get("source_id")
        if (parent.get("status") != "acquired" or item.get("status") != "acquired"
                or not isinstance(parent_id, str) or not parent_id or parent_id == document_id
                or not isinstance(source_id, str) or not source_id
                or item.get("source_id") != source_id
                or item.get("parent_source_document_id") != parent_id):
            raise ValueError("Inconsistent acquired image/parent/source binding.")
        image_path = _path(item.get("file"), report_path.parent)
        sidecar_path = _path(item.get("sidecar"), report_path.parent)
        if image_path in paths_seen:
            raise ValueError("Two image IDs refer to the same file.")
        paths_seen.add(image_path)
        sidecar_raw = sidecar_path.read_bytes()
        sidecar = yaml.safe_load(sidecar_raw)
        metadata = sidecar.get("metadata") if isinstance(sidecar, dict) else None
        if not isinstance(metadata, dict):
            raise ValueError("Expected an acquired online-image sidecar with metadata.")
        image_hash = _digest(image_path.read_bytes())
        if (item.get("content_hash") != image_hash or metadata.get("content_hash") != image_hash
                or sidecar.get("content_hash", image_hash) != image_hash):
            raise ValueError("Image SHA-256 differs from report or sidecar.")
        # Online acquisition uses document_id for the image and the nested
        # source_document_id for its parent; do not substitute the parent ID.
        if (sidecar.get("document_id") != document_id or metadata.get("document_id") != document_id
                or sidecar.get("source_id") != source_id or metadata.get("source_id") != source_id
                or metadata.get("source_document_id") != parent_id
                or _path(sidecar.get("file"), sidecar_path.parent) != image_path):
            raise ValueError("Sidecar image identity, parent or file mismatch.")
        media_type = metadata.get("media_type", "")
        if (metadata.get("document_class") != "image_scan" or not isinstance(media_type, str)
                or not media_type.startswith("image/")
                or image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}
                or item.get("claim_eligible") is not False or metadata.get("claim_eligible") is not False
                or not isinstance(item.get("review_status"), str)
                or metadata.get("review_status") != item.get("review_status")):
            raise ValueError("Expected a non-claim-eligible acquired image with consistent review status.")
        images.append({"source_id": source_id, "source_document_id": document_id,
                       "parent_source_document_id": parent_id,
                       "image": {"path": str(image_path), "sha256": image_hash},
                       "sidecar": {"path": str(sidecar_path), "sha256": _digest(sidecar_raw)},
                       "media_type": media_type, "source_review_status": item["review_status"],
                       "source_claim_eligible": False})
    return {"source_report": {"path": str(report_path), "sha256": _digest(raw)}, "images": images}


def _open_image(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))
    else:
        try:
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(path)], check=True)
        except subprocess.CalledProcessError as exc:
            raise ValueError("Local image viewer failed; no review can be saved.") from exc


def _timestamp(now_fn=None) -> str:
    value = now_fn() if now_fn else datetime.now().astimezone()
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Review requires a timezone-aware clock.")
    return value.isoformat()


class _Cancelled(Exception):
    pass


def run_document_transcription_wizard(
    *, source_report: Path, document_ids: list[str], output_dir: Path,
    open_images: bool = False, input_fn=None, output_fn=print, now_fn=None, open_image_fn=None,
) -> dict[str, Any] | None:
    """Collect manual text, then separate human decisions; publish only on confirmation."""
    output = output_dir.resolve()
    if output.exists():
        raise ValueError("output-dir must be new; existing artifacts cannot be overwritten.")
    binding = _load_images(source_report, document_ids)
    ask = input_fn or input

    def answer(prompt: str, *, required: bool = False) -> str:
        while True:
            value = ask(prompt).strip()
            if value.lower() == "q":
                raise _Cancelled
            if value or not required:
                return value
            output_fn("Valore obbligatorio; [q] annulla senza scritture.")

    output_fn("Trascrizione manuale; nessun OCR/VLM, claim o fatto verificato. [q] annulla.")
    output_fn(f"Report SHA-256: {binding['source_report']['sha256']}; immagini: {len(document_ids)}")
    drafts = []
    decisions = []
    try:
        transcriber = answer("Identificativo trascrittore: ", required=True)
        for image in binding["images"]:
            output_fn(f"\nImmagine {image['source_document_id']}: {image['image']['path']}")
            output_fn(f"SHA-256: {image['image']['sha256']}")
            if open_images:
                (open_image_fn or _open_image)(Path(image["image"]["path"]))
            scope = answer("Porzione/campo trascritto (non inferire campi assenti): ", required=True)
            while True:
                coverage = answer("Copertura [p] parziale / [f] intera immagine: ").lower()
                if coverage in {"p", "f"}:
                    break
            text = answer("Testo manuale su una riga ([i] illeggibile): ", required=True)
            illegible = text.lower() == "i"
            drafts.append({"source_document_id": image["source_document_id"],
                           "scope": scope, "coverage": "partial" if coverage == "p" else "full",
                           "text": "" if illegible else " ".join(text.split()),
                           "legibility": "illegible" if illegible else "transcribed",
                           "transcriber": transcriber, "transcribed_at": _timestamp(now_fn),
                           "review_status": "unreviewed", "transcription_method": "manual_transcription"})
        output_fn("\nREVIEW DELLA TRASCRIZIONE: confrontare ogni testo con la relativa immagine.")
        reviewer = answer("Identificativo reviewer (dichiarato, non autenticato): ", required=True)
        for image, draft in zip(binding["images"], drafts, strict=True):
            output_fn(f"\n{image['source_document_id']} | {image['image']['path']}")
            if open_images:
                (open_image_fn or _open_image)(Path(image["image"]["path"]))
            output_fn(f"{draft['scope']} ({draft['coverage']}): {draft['text'] or '[illeggibile]'}")
            while True:
                choice = answer("Lettura confrontata con l'immagine: [a] conferma / [r] respingi / [e] incerta: ").lower()
                if choice in {"a", "r", "e"} and not (choice == "a" and draft["legibility"] == "illegible"):
                    break
                output_fn("Scelta non valida; una porzione illeggibile non puo' essere confermata.")
            note = answer("Nota (obbligatoria se respinta/incerta): ", required=choice != "a")
            decisions.append({"source_document_id": image["source_document_id"], "scope": draft["scope"],
                              "coverage": draft["coverage"], "reviewer": reviewer,
                              "image_consultation_attested": True,
                              "reviewed_at": _timestamp(now_fn), "note": note,
                              "decision": {"a": "accept_transcription", "r": "reject_transcription",
                                           "e": "needs_more_evidence"}[choice]})
        output_fn("Riepilogo: " + str(dict(Counter(item["decision"] for item in decisions))))
        if answer("Confermare e salvare trascrizioni e receipt review-only? [s/N]: ").lower() not in {"s", "si", "y", "yes"}:
            return None
    except _Cancelled:
        return None
    if _load_images(source_report, document_ids) != binding:
        raise ValueError("Source inputs changed during transcription/review; no artifacts saved.")
    if output.exists():
        raise ValueError("output-dir appeared during review; no artifacts saved.")
    draft = {"@type": "ManualTranscriptionDraftSet", "schema_version": "1.0",
             **binding, "items": drafts, "review_status": "unreviewed", **_FLAGS}
    files = {"transcription-draft.json": _bytes(draft)}
    text_refs = []
    for index, (image, row, decision) in enumerate(zip(binding["images"], drafts, decisions, strict=True), 1):
        text = build_bound_manual_transcription(
            source_id=image["source_id"], document_id=image["source_document_id"],
            image_path=Path(image["image"]["path"]), sidecar_path=Path(image["sidecar"]["path"]),
            text=row["text"], provenance={**image, "source_report": binding["source_report"],
                                         "scope": row["scope"], "coverage": row["coverage"],
                                         "transcriber": transcriber}, review_decision=decision["decision"],
        )
        name = f"image-{index}.text.json"
        files[name] = _bytes(text)
        ref = {"path": str(output / name), "sha256": _digest(files[name]),
               "source_document_id": image["source_document_id"]}
        text_refs.append(ref)
        decision["processed_text"] = ref
    manifest = {"@type": "ManualTranscriptionManifest", "schema_version": "1.0", **binding,
                "draft": {"path": str(output / "transcription-draft.json"),
                          "sha256": _digest(files["transcription-draft.json"])},
                "processed_texts": text_refs, **_FLAGS}
    files["transcription-manifest.json"] = _bytes(manifest)
    complete = all(item["decision"] != "needs_more_evidence" for item in decisions)
    receipt = {"@type": "ManualTranscriptionReviewReceipt", "schema_version": "1.0",
               "manifest": {"path": str(output / "transcription-manifest.json"),
                            "sha256": _digest(files["transcription-manifest.json"])},
               "decisions": decisions, "decision_count": len(decisions),
               "decision_counts": dict(Counter(item["decision"] for item in decisions)),
               "review_status": "complete" if complete else "pending", "review_complete": complete,
               "human_review_recorded": True, "reviewer_identity_authenticated": False,
               "transcriber_identity_authenticated": False, "decision_method": "interactive_cli_wizard",
               "transcription_method": "manual_transcription", **_FLAGS}
    files["transcription-review-receipt.json"] = _bytes(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".transcription-", dir=output.parent) as scratch:
        stage = Path(scratch)
        for name, raw in files.items():
            (stage / name).write_bytes(raw)
        if _load_images(source_report, document_ids) != binding or output.exists():
            raise ValueError("Source inputs or output changed before publication; no artifacts saved.")
        # Reserve the destination exclusively, including on POSIX where rename
        # could otherwise replace an existing empty directory in a race.
        output.mkdir()
        published = []
        try:
            for name in files:  # Receipt is deliberately published last.
                if name == "transcription-review-receipt.json" and _load_images(source_report, document_ids) != binding:
                    raise ValueError("Source inputs changed before receipt publication.")
                destination = output / name
                with destination.open("xb") as stream:
                    published.append(destination)
                    stream.write((stage / name).read_bytes())
        except (OSError, ValueError):
            for destination in reversed(published):
                destination.unlink()
            output.rmdir()
            raise
    return {"output_dir": str(output), "receipt": str(output / "transcription-review-receipt.json"),
            "review_complete": complete, "decision_count": len(decisions), **_FLAGS}
