from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .metadata_extraction import extract_document_metadata

ALLOWED_TRANSCRIPTION_METHODS = {"manual_transcription", "external_ocr_unreviewed"}


def register_document_transcription(
    *,
    file_path: Path | None = None,
    sidecar_path: Path | None = None,
    text: str = "",
    text_file: Path | None = None,
    root_dir: Path = Path("data/raw"),
    output_dir: Path = Path("data/processed/documents"),
    transcription_method: str = "manual_transcription",
    review_status: str = "unreviewed",
    derived_metadata: dict[str, Any] | None = None,
    overwrite: bool = False,
    metadata_path: Path | None = None,
    metadata_sha256: str | None = None,
    sidecar_sha256: str | None = None,
) -> dict[str, Any]:
    _check_metadata_binding(metadata_path, metadata_sha256, sidecar_sha256)
    if file_path is None and sidecar_path is None:
        raise ValueError("Specificare file_path o sidecar_path.")
    if transcription_method not in ALLOWED_TRANSCRIPTION_METHODS:
        raise ValueError(f"Metodo trascrizione non supportato: {transcription_method}")

    resolved_sidecar = _resolve_sidecar(file_path=file_path, sidecar_path=sidecar_path)
    sidecar = _load_sidecar(resolved_sidecar)
    resolved_file = _resolve_file(file_path=file_path, sidecar_path=resolved_sidecar, sidecar=sidecar)
    if file_path is not None and Path(file_path).resolve() != resolved_file.resolve():
        raise ValueError("File e sidecar non si riferiscono allo stesso documento.")

    transcription_text = _read_transcription_text(text=text, text_file=text_file)
    explicit_sidecar_sha256 = None
    if metadata_path is not None:
        metadata, explicit_sidecar_sha256 = _validate_explicit_metadata(
            metadata_path=metadata_path, metadata_sha256=metadata_sha256,
            file_path=resolved_file, sidecar_path=resolved_sidecar, root_dir=root_dir,
            expected_sidecar_sha256=sidecar_sha256,
        )
    else:
        metadata = _resolve_or_create_metadata(
            sidecar=sidecar,
            sidecar_path=resolved_sidecar,
            file_path=resolved_file,
            root_dir=root_dir,
            output_dir=output_dir,
        )
    if str(metadata.get("document_class", "")) != "image_scan":
        raise ValueError("La trascrizione manuale e' supportata solo per documenti image_scan.")

    document_text = _processed_text_from_transcription(
        metadata=metadata,
        transcription_text=transcription_text,
        transcription_method=transcription_method,
        review_status=review_status,
        derived_metadata=derived_metadata,
    )
    text_path = output_dir / _text_relative_path(document_text)
    if text_path.exists() and not overwrite:
        raise FileExistsError(f"Testo processato gia' presente: {text_path}")
    if metadata_path is not None:
        _validate_explicit_metadata(
            metadata_path=metadata_path, metadata_sha256=metadata_sha256,
            file_path=resolved_file, sidecar_path=resolved_sidecar, root_dir=root_dir,
            expected_sidecar_sha256=explicit_sidecar_sha256,
        )
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(json.dumps(document_text, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "@type": "DocumentTranscriptionRegistration",
        "text_path": str(text_path),
        "metadata_path": str(metadata.get("_metadata_file", "")),
        "source_document_id": document_text["source_document_id"],
        "transcription_method": transcription_method,
        "review_status": document_text["review_status"],
    }


def _check_metadata_binding(metadata_path: Path | None, metadata_sha256: str | None, sidecar_sha256: str | None) -> None:
    supplied = (metadata_path is not None, metadata_sha256 is not None, sidecar_sha256 is not None)
    if any(supplied) and not all(supplied):
        raise ValueError("metadata_path, metadata_sha256 e sidecar_sha256 devono essere specificati insieme.")
    for name, digest in (("metadata_sha256", metadata_sha256), ("sidecar_sha256", sidecar_sha256)):
        if digest is not None and (
            not isinstance(digest, str) or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise ValueError(f"{name} deve essere uno SHA-256 esadecimale minuscolo.")


def _sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _validate_explicit_metadata(
    *, metadata_path: Path, metadata_sha256: str | None,
    file_path: Path, sidecar_path: Path | None, root_dir: Path,
    expected_sidecar_sha256: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Validate only the supplied document binding, without scanning the root."""
    _check_metadata_binding(metadata_path, metadata_sha256, expected_sidecar_sha256)
    metadata_bytes = Path(metadata_path).read_bytes()
    if hashlib.sha256(metadata_bytes).hexdigest() != metadata_sha256:
        raise ValueError("SHA-256 metadata non corrispondente.")
    metadata = json.loads(metadata_bytes)
    if not isinstance(metadata, dict) or metadata.get("@type") != "ProcessedDocumentMetadata":
        raise ValueError("Atteso ProcessedDocumentMetadata JSON.")
    if metadata.get("document_class") != "image_scan":
        raise ValueError("Metadata esplicito richiede document_class image_scan.")
    resolved_sidecar = _resolve_sidecar(file_path=file_path, sidecar_path=sidecar_path)
    sidecar_bytes = resolved_sidecar.read_bytes()
    sidecar_digest = hashlib.sha256(sidecar_bytes).hexdigest()
    if expected_sidecar_sha256 is not None and sidecar_digest != expected_sidecar_sha256:
        raise ValueError("Sidecar modificato durante la registrazione OCR.")
    sidecar = yaml.safe_load(sidecar_bytes)
    if not isinstance(sidecar, dict):
        raise ValueError("Sidecar deve essere un oggetto YAML.")
    for metadata_key, sidecar_key in (("source_id", "source_id"), ("source_document_id", "document_id")):
        identity = metadata.get(metadata_key)
        if not isinstance(identity, str) or not identity.strip() or identity != sidecar.get(sidecar_key):
            raise ValueError(f"Identita metadata/sidecar non corrispondente: {metadata_key}.")
    for key, expected in (("raw_file", file_path), ("sidecar_file", resolved_sidecar)):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Percorso metadata obbligatorio: {key}.")
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root_dir / candidate
        if candidate.resolve() != expected.resolve():
            raise ValueError(f"Percorso metadata non corrispondente: {key}.")
    local_path = sidecar.get("local_path")
    if not isinstance(local_path, str) or not local_path.strip() or Path(local_path).resolve() != file_path.resolve():
        raise ValueError("local_path sidecar non corrispondente al documento.")
    file_digest = _sha256_file(file_path)
    if metadata.get("sha256") != file_digest:
        raise ValueError("SHA-256 documento non corrispondente al metadata.")
    if "content_hash" in sidecar and sidecar["content_hash"] != file_digest:
        raise ValueError("content_hash sidecar non corrispondente al documento.")
    metadata["_metadata_file"] = str(metadata_path)
    return metadata, sidecar_digest


def _resolve_sidecar(*, file_path: Path | None, sidecar_path: Path | None) -> Path:
    if sidecar_path is not None:
        resolved = Path(sidecar_path)
    else:
        assert file_path is not None
        resolved = _default_sidecar_for_file(Path(file_path))
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"Sidecar non trovato: {resolved}")
    return resolved


def _default_sidecar_for_file(file_path: Path) -> Path:
    per_file_sidecar = file_path.with_name(f"{file_path.name}.document.yaml")
    if per_file_sidecar.exists():
        return per_file_sidecar
    return file_path.with_name("document.yaml")


def _load_sidecar(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _resolve_file(*, file_path: Path | None, sidecar_path: Path, sidecar: dict[str, Any]) -> Path:
    if file_path is not None:
        resolved = Path(file_path)
    else:
        local_path = str(sidecar.get("local_path", "")).strip()
        if local_path:
            resolved = Path(local_path)
        else:
            resolved = sidecar_path.parent / "content"
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"Documento immagine non trovato: {resolved}")
    return resolved


def _read_transcription_text(*, text: str, text_file: Path | None) -> str:
    if text_file is not None:
        path = Path(text_file)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File trascrizione non trovato: {path}")
        value = path.read_text(encoding="utf-8")
    else:
        value = text
    value = " ".join(value.split())
    if not value:
        raise ValueError("Trascrizione vuota.")
    return value


def _resolve_or_create_metadata(
    *,
    sidecar: dict[str, Any],
    sidecar_path: Path,
    file_path: Path,
    root_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    metadata = _find_metadata(sidecar=sidecar, sidecar_path=sidecar_path, file_path=file_path, root_dir=root_dir, output_dir=output_dir)
    if not metadata:
        extract_document_metadata(root_dir=root_dir, output_dir=output_dir)
        metadata = _find_metadata(sidecar=sidecar, sidecar_path=sidecar_path, file_path=file_path, root_dir=root_dir, output_dir=output_dir)
    if not metadata:
        raise FileNotFoundError("Metadato processato non risolto dopo extract_document_metadata.")
    return metadata


def _find_metadata(
    *,
    sidecar: dict[str, Any],
    sidecar_path: Path,
    file_path: Path,
    root_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    document_id = str(sidecar.get("document_id", "")).strip()
    relative_file = _relative_or_str(file_path, root_dir)
    relative_sidecar = _relative_or_str(sidecar_path, root_dir)
    for metadata_path in sorted(output_dir.rglob("*.metadata.json")):
        metadata = _load_json_object(metadata_path)
        if not metadata:
            continue
        if document_id and str(metadata.get("source_document_id", "")) == document_id:
            metadata["_metadata_file"] = str(metadata_path)
            return metadata
        if str(metadata.get("raw_file", "")) == relative_file:
            metadata["_metadata_file"] = str(metadata_path)
            return metadata
        if str(metadata.get("sidecar_file", "")) == relative_sidecar:
            metadata["_metadata_file"] = str(metadata_path)
            return metadata
    return {}


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _processed_text_from_transcription(
    *,
    metadata: dict[str, Any],
    transcription_text: str,
    transcription_method: str,
    review_status: str,
    derived_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "@type": "ProcessedDocumentText",
        "source_id": str(metadata.get("source_id", "")),
        "source_document_id": str(metadata.get("source_document_id", "")),
        "document_class": str(metadata.get("document_class", "")),
        "claim_eligible": bool(metadata.get("claim_eligible", False)),
        "review_status": review_status.strip() or "unreviewed",
        "raw_file": str(metadata.get("raw_file", "")),
        "metadata_file": str(metadata.get("_metadata_file", "")),
        "media_type": str(metadata.get("media_type", "")),
        "extraction_status": _extraction_status(transcription_method),
        "text_status": "extracted",
        "transcription_method": transcription_method,
        "text": transcription_text,
        "text_length": len(transcription_text),
        "text_sha256": hashlib.sha256(transcription_text.encode("utf-8")).hexdigest(),
    }
    if derived_metadata:
        payload.update(derived_metadata)
    return payload


def _extraction_status(transcription_method: str) -> str:
    if transcription_method == "external_ocr_unreviewed":
        return "external_ocr_registered"
    return "manual_transcription_registered"


def _text_relative_path(document_text: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(document_text.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(document_text.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.text.json"


def _relative_or_str(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra una trascrizione revisionabile per immagini/scansioni.")
    parser.add_argument("--file", default="")
    parser.add_argument("--sidecar", default="")
    parser.add_argument("--text-file", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--root-dir", default="data/raw")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--transcription-method", default="manual_transcription")
    parser.add_argument("--review-status", default="unreviewed")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        result = register_document_transcription(
            file_path=Path(args.file) if args.file.strip() else None,
            sidecar_path=Path(args.sidecar) if args.sidecar.strip() else None,
            text=args.text,
            text_file=Path(args.text_file) if args.text_file.strip() else None,
            root_dir=Path(args.root_dir),
            output_dir=Path(args.output_dir),
            transcription_method=args.transcription_method,
            review_status=args.review_status,
            overwrite=args.overwrite,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
