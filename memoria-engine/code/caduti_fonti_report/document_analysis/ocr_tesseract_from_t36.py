"""Bind existing Tesseract text to validated raw T36 frames, without inference."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .ocr_tesseract_evidence_adapter import adapt_tesseract_page_evidence
from .ocr_transform_structure import (
    _json_bytes, _manifest_artifact_path, _reject_constant, _required_sha256,
    _required_text, _safe_name, _sha256_bytes, _sha256_file, _unique_object,
    _validate_evidence,
)


def _read(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                       parse_constant=_reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f"Oggetto JSON richiesto: {path}")
    return value, data


def export_tesseract_from_t36(*, manifest_path: Path, processed_text: Mapping[str, Path],
                              output_dir: Path, apply: bool = False) -> dict[str, Any]:
    """Prepare all pages before publishing a new, diagnostic evidence directory."""
    source_manifest = Path(manifest_path).resolve(strict=True)
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError(f"La directory output deve essere nuova: {destination}")
    repository_root = Path(__file__).resolve().parents[4]
    if destination == repository_root or repository_root in destination.parents:
        raise ValueError("La directory output deve restare esterna al repository.")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"La directory padre output deve esistere: {destination.parent}")

    manifest, manifest_bytes = _read(source_manifest)
    if manifest.get("@type") != "OcrTransformPilot" or manifest.get("schema_version") != "1.0":
        raise ValueError("E' richiesto un OcrTransformPilot v1.0.")
    if (manifest.get("review_status") != "unreviewed"
            or manifest.get("accuracy_claim") != "none_without_human_reference"):
        raise ValueError("Il manifest T36 deve restare unreviewed senza accuracy claim.")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages or any(not isinstance(page, dict) for page in pages):
        raise ValueError("Manifest T36 senza pagine valide.")
    ids = [_required_text(page.get("page_id"), "page_id") for page in pages]
    names = [_safe_name(page_id).casefold() for page_id in ids]
    if len(set(ids)) != len(ids) or len(set(names)) != len(names):
        raise ValueError("page_id T36 duplicati o collisioni nei nomi artifact.")
    if set(processed_text) != set(ids):
        raise ValueError("La mappa --processed-text deve dichiarare esattamente ogni page_id del manifest.")

    inputs = {source_manifest: _sha256_bytes(manifest_bytes)}
    artifacts: dict[str, bytes] = {}
    entries = []

    def record(path: Path, digest: str) -> dict[str, str]:
        if path in inputs and inputs[path] != digest:
            raise ValueError(f"Digest input incoerente: {path}")
        inputs[path] = digest
        return {"path": str(path), "sha256": digest}

    from PIL import Image
    for page, page_id in zip(pages, ids):
        source = page.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"Sorgente T36 mancante per {page_id}.")
        source_path = Path(_required_text(source.get("path"), "source.path")).resolve(strict=True)
        source_hash = _required_sha256(source.get("sha256"), "source.sha256")
        if _sha256_file(source_path) != source_hash:
            raise ValueError(f"SHA-256 TIFF sorgente divergente per {page_id}.")
        dimensions = source.get("image_dimensions")
        if (not isinstance(dimensions, dict) or set(dimensions) != {"width", "height"}
                or any(type(dimensions[key]) is not int or dimensions[key] <= 0 for key in dimensions)):
            raise ValueError(f"Dimensioni sorgente non valide per {page_id}.")
        with Image.open(source_path) as image:
            if (image.format != "TIFF" or image.n_frames != 1
                    or image.size != (dimensions["width"], dimensions["height"])):
                raise ValueError("Serve un TIFF single-frame con dimensioni originali verificate.")
        variants = page.get("variants")
        raw = [item for item in variants if isinstance(item, dict) and item.get("variant_id") == "raw"] if isinstance(variants, list) else []
        if len(raw) != 1:
            raise ValueError(f"Variante raw mancante o duplicata per {page_id}.")
        variant = raw[0]
        variant_path = _manifest_artifact_path(source_manifest.parent, variant.get("path"))
        variant_hash = _required_sha256(variant.get("sha256"), "raw.sha256")
        if variant_hash != source_hash or _sha256_file(variant_path) != variant_hash:
            raise ValueError("La variante raw deve essere byte-identica al TIFF sorgente.")
        transform = variant.get("transform")
        if (not isinstance(transform, dict) or set(transform) != {"id", "parameters"}
                or not isinstance(transform.get("id"), str) or not transform["id"].strip()
                or not isinstance(transform["parameters"], dict)
                or set(transform["parameters"]) - {"operation", "source_mode"}
                or transform["parameters"].get("operation") != "byte_copy"):
            raise ValueError("La variante raw richiede una trasformazione byte_copy esplicita.")
        outputs = variant.get("ocr_outputs")
        full = [item for item in outputs if isinstance(item, dict) and item.get("target") == "full_page"] if isinstance(outputs, list) else []
        if len(full) != 1:
            raise ValueError("Atteso un solo output OCR full-page raw.")
        output = full[0]
        if (_manifest_artifact_path(source_manifest.parent, output.get("artifact")) != variant_path
                or output.get("artifact_sha256") != variant_hash
                or output.get("source_bbox") != [0, 0, dimensions["width"], dimensions["height"]]
                or output.get("tile_id") is not None):
            raise ValueError("Output full-page non legato alla variante raw.")
        primary = output.get("structured_evidence")
        _validate_evidence(evidence=primary, page_id=page_id, source=source, dimensions=dimensions,
                           variant_id="raw", transform_id=transform["id"], language=manifest.get("language"))
        if primary.get("image_transform") != transform:
            raise ValueError("image_transform evidence divergente dalla variante raw.")
        if "frame_index" in primary["source_page"] and (
                type(primary["source_page"]["frame_index"]) is not int or primary["source_page"]["frame_index"] != 0):
            raise ValueError("frame_index incompatibile con TIFF single-frame.")
        text_path = Path(processed_text[page_id]).resolve(strict=True)
        text, text_bytes = _read(text_path)
        content = text.get("text")
        if (not isinstance(content, str) or not content.strip()
                or _required_sha256(text.get("text_sha256"), "text_sha256") != _sha256_bytes(content.encode("utf-8"))):
            raise ValueError("SHA-256 del testo ProcessedDocumentText divergente.")
        evidence = adapt_tesseract_page_evidence(processed_text=text, primary_evidence=primary,
                                                original_page=primary["source_page"]["original_page"])
        evidence.update(diagnostic_only=True, review_status="unreviewed", semantic_accuracy_status="not_attested",
                        machine_pass=False, auto_validation_enabled=False, gold_promotion_allowed=False)
        name = _safe_name(page_id)
        entry = {"page_id": page_id,
                 "source_image": record(source_path, source_hash),
                 "variant_image": record(variant_path, variant_hash),
                 "processed_text": record(text_path, _sha256_bytes(text_bytes))}
        for role, value in (("primary_evidence", primary), ("evidence", evidence)):
            relative = f"{role}/{name}.json"
            data = _json_bytes(value)
            artifacts[relative] = data
            entry[role] = {"path": str(destination / relative), "sha256": _sha256_bytes(data)}
        entries.append(entry)

    report = {"@type": "TesseractEvidenceFromT36Run", "schema_version": "1.0",
              "source_manifest": {"path": str(source_manifest), "sha256": _sha256_bytes(manifest_bytes)},
              "pages": entries, "status": "diagnostic_evidence_ready", "diagnostic_only": True,
              "review_status": "unreviewed", "semantic_accuracy_status": "not_attested",
              "machine_pass": False, "auto_validation_enabled": False, "gold_promotion_allowed": False,
              "operation_status": "written" if apply else "preview", "output_dir": str(destination),
              "report_path": str(destination / "run-manifest.json")}
    if not apply:
        return report
    with tempfile.TemporaryDirectory(prefix=".ocr-tesseract-from-t36-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "evidence-package"
        stage.mkdir()
        for relative, data in artifacts.items():
            target = stage / relative
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(data)
        (stage / "run-manifest.json").write_bytes(_json_bytes(report))
        for path, digest in inputs.items():
            if _sha256_file(path) != digest:
                raise ValueError(f"Input modificato durante l'operazione: {path}")
        if destination.exists():
            raise FileExistsError(f"La directory output deve essere nuova: {destination}")
        os.rename(stage, destination)
    return report
