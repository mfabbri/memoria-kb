"""Run Tesseract on explicitly bound, independently registered T36 pages."""

from __future__ import annotations

import json
import hashlib
import ntpath
from pathlib import Path
import tempfile
from typing import Any

import yaml

from .ocr_tesseract import CommandRunner, run_document_ocr
from .ocr_transform_structure import _required_sha256, _required_text, _sha256_file
from .ocr_tesseract_from_t36 import _read
from .transcription_registration import _text_relative_path, _validate_explicit_metadata


class _UniqueYamlLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        result: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in result:
                raise ValueError(f"Chiave YAML duplicata: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _resolve(base: Path, value: Any) -> Path:
    return (base / _required_text(value, "path")).resolve()


def _key(path: Path) -> str:
    # Windows also aliases trailing dots/spaces, even on case-sensitive test hosts.
    value = ntpath.normpath(str(path.resolve()).replace("/", "\\"))
    return "\\".join(part.rstrip(" .").casefold() for part in value.split("\\"))


def _disjoint(paths: list[Path]) -> None:
    keys = [_key(path) for path in paths]
    if len(keys) != len(set(keys)):
        raise ValueError("Input e destinazioni devono avere percorsi distinti anche su Windows.")
    for left in keys:
        if any(right.startswith(left + "\\") for right in keys if right != left):
            raise ValueError("Un file non puo' essere anche directory di un altro percorso.")


def _new_target(path: Path) -> None:
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}
    if any(part.rstrip(" .").split(".")[0].casefold() in reserved for part in path.parts):
        raise ValueError(f"Nome riservato Windows nella destinazione: {path}")
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"Destinazione gia' presente: {path}")
    for parent in path.parents:
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"Directory destinazione non valida: {parent}")
    # A directory scan also catches case/trailing-dot aliases on POSIX fixtures.
    for parent in (path, *path.parents):
        if parent != path and parent.exists():
            continue
        if parent.parent.is_dir() and any(
            _key(child) == _key(parent) and child.name != parent.name
            for child in parent.parent.iterdir()
        ):
            raise ValueError(f"Alias Windows nel percorso destinazione: {path}")


def _write_new(path: Path, data: bytes) -> None:
    _new_target(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def run_tesseract_page_batch(
    *, manifest_path: Path, output_dir: Path, report_path: Path,
    apply: bool = False, command_runner: CommandRunner | None = None,
    tesseract_path: str = "tesseract", language: str = "ita",
    page_segmentation_mode: str = "", engine_mode: str = "", dpi: str = "",
    preprocess_before_ocr: bool = False, enable_region_ocr: bool = False,
    _preflight_payloads: tuple[dict[str, Any], dict[str, Any]] | None = None,
    _existing_stage: bool = False,
) -> dict[str, Any]:
    """Validate the whole manifest before OCR; runtime failures remain per page.

    TesseractPageBatchManifest v1.0 declares root_dir, a hash-bound t36_manifest,
    and pages with page_id, source_id, source_document_id, raw_tiff, sidecar and
    metadata. Each file reference contains path and sha256. Relative paths resolve
    from this manifest's directory; metadata internal paths use root_dir.
    """
    if apply and (_preflight_payloads is not None or _existing_stage):
        raise ValueError("Il preflight workflow in memoria non puo' eseguire OCR.")
    manifest_path = Path(manifest_path).resolve(strict=_preflight_payloads is None)
    if _preflight_payloads is None:
        manifest, manifest_bytes = _read(manifest_path)
    else:
        manifest = _preflight_payloads[0]
        manifest_bytes = json.dumps(manifest, sort_keys=True, allow_nan=False).encode("utf-8")
    if set(manifest) != {"@type", "schema_version", "root_dir", "t36_manifest", "pages"}:
        raise ValueError("Campi manifest v1 incompleti o sconosciuti.")
    if (manifest.get("@type") != "TesseractPageBatchManifest"
            or manifest.get("schema_version") != "1.0"):
        raise ValueError("Atteso TesseractPageBatchManifest v1.0.")
    base = manifest_path.parent
    root = _resolve(base, manifest.get("root_dir"))
    if not root.is_dir():
        raise ValueError("root_dir deve essere una directory esistente.")
    destination = _resolve(base, str(output_dir))
    report_target = _resolve(base, str(report_path))
    repository_root = Path(__file__).resolve().parents[4]
    if any(path.is_relative_to(repository_root) for path in (destination, report_target)):
        raise ValueError("Output e rapporto devono restare esterni al repository.")
    inputs = {manifest_path: hashlib.sha256(manifest_bytes).hexdigest()}

    def reference(value: Any, reference_base: Path = base) -> tuple[Path, str]:
        if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
            raise ValueError("Ogni riferimento richiede path e sha256.")
        path = _resolve(reference_base, value["path"])
        digest = _required_sha256(value["sha256"], "sha256")
        if not path.is_file() or _sha256_file(path) != digest:
            raise ValueError(f"File o SHA-256 non corrispondente: {path}")
        return path, digest

    if _preflight_payloads is None:
        t36_path, t36_hash = reference(manifest.get("t36_manifest"))
        t36, t36_bytes = _read(t36_path)
    else:
        # The future T36 descriptor derives solely from validated batch inputs.
        # It is used only to validate bindings before either runtime is called.
        t36_path = _resolve(base, manifest["t36_manifest"]["path"])
        t36 = _preflight_payloads[1]
        t36_bytes = json.dumps(t36, sort_keys=True, allow_nan=False).encode("utf-8")
        t36_hash = hashlib.sha256(t36_bytes).hexdigest()
    if hashlib.sha256(t36_bytes).hexdigest() != t36_hash:
        raise ValueError("Manifest T36 modificato durante il preflight.")
    if (t36.get("@type") != "OcrTransformPilot" or t36.get("schema_version") != "1.0"
            or t36.get("review_status") != "unreviewed"
            or t36.get("accuracy_claim") != "none_without_human_reference"):
        raise ValueError("Atteso OcrTransformPilot v1.0 unreviewed senza accuracy claim.")
    t36_pages = t36.get("pages")
    pages = manifest.get("pages")
    if (not isinstance(pages, list) or not pages or not isinstance(t36_pages, list)
            or not t36_pages or any(not isinstance(page, dict) for page in t36_pages)):
        raise ValueError("Manifest senza pagine valide.")
    t36_ids = [_required_text(page.get("page_id"), "page_id") for page in t36_pages]
    if len(set(page.casefold() for page in t36_ids)) != len(t36_ids):
        raise ValueError("page_id T36 duplicati.")
    if any(page.get("status") != "completed" for page in t36_pages):
        raise ValueError("Tutte le pagine T36 devono essere completed.")
    t36_by_id = dict(zip(t36_ids, t36_pages))
    all_paths = [manifest_path, t36_path, report_target]
    inputs[t36_path] = t36_hash
    prepared = []
    seen_ids: set[str] = set()
    seen_documents: set[tuple[str, str]] = set()
    from PIL import Image
    for page in pages:
        if not isinstance(page, dict) or set(page) != {
            "page_id", "source_id", "source_document_id", "raw_tiff", "sidecar", "metadata"
        }:
            raise ValueError("Campi pagina incompleti o sconosciuti.")
        page_id, source_id, document_id = (
            _required_text(page[key], key) for key in ("page_id", "source_id", "source_document_id")
        )
        identity = (source_id.casefold(), document_id.casefold())
        if page_id.casefold() in seen_ids or identity in seen_documents or page_id not in t36_by_id:
            raise ValueError("Identita pagina/documento duplicata o page_id T36 sconosciuto.")
        seen_ids.add(page_id.casefold())
        seen_documents.add(identity)
        raw, raw_hash = reference(page["raw_tiff"])
        sidecar, sidecar_hash = reference(page["sidecar"])
        metadata, metadata_hash = reference(page["metadata"])
        _read(metadata)  # Reject duplicate JSON keys before the shared legacy validator.
        try:
            yaml.load(sidecar.read_bytes(), Loader=_UniqueYamlLoader)
        except yaml.YAMLError as exc:
            raise ValueError(f"Sidecar YAML non valido: {sidecar}") from exc
        source = t36_by_id[page_id].get("source")
        if not isinstance(source, dict):
            raise ValueError("Sorgente T36 mancante.")
        source_path = _resolve(t36_path.parent, source.get("path"))
        if _key(raw) != _key(source_path) or raw_hash != source.get("sha256"):
            raise ValueError("TIFF pagina non corrisponde alla sorgente raw T36.")
        with Image.open(raw) as image:
            if image.format != "TIFF" or image.n_frames != 1:
                raise ValueError("Richiesto TIFF single-frame per ogni pagina.")
        payload, _ = _validate_explicit_metadata(
            metadata_path=metadata, metadata_sha256=metadata_hash,
            file_path=raw, sidecar_path=sidecar, root_dir=root,
            expected_sidecar_sha256=sidecar_hash,
        )
        if payload["source_id"] != source_id or payload["source_document_id"] != document_id:
            raise ValueError("Identita pagina divergente da metadata/sidecar.")
        relative = _text_relative_path(payload)
        target = (destination / relative).resolve()
        if len(relative.parts) != 2 or not target.is_relative_to(destination):
            raise ValueError("Identita documento non sicura per la directory output.")
        all_paths.extend([raw, sidecar, metadata, target])
        inputs.update({raw: raw_hash, sidecar: sidecar_hash, metadata: metadata_hash})
        prepared.append((page, raw, sidecar, metadata, target))
    if set(t36_ids) != {page["page_id"] for page in pages}:
        raise ValueError("Il manifest deve coprire esattamente tutte le pagine T36.")
    _disjoint(all_paths)
    if not _existing_stage:
        for target in [report_target, *(item[-1] for item in prepared)]:
            _new_target(target)
    report: dict[str, Any] = {
        "@type": "TesseractPageBatchReport", "schema_version": "1.0",
        "manifest": {"path": str(manifest_path), "sha256": inputs[manifest_path]},
        "t36_manifest": {"path": str(t36_path), "sha256": t36_hash},
        "configuration": {"tesseract_path": tesseract_path, "language": language,
                          "page_segmentation_mode": page_segmentation_mode,
                          "engine_mode": engine_mode, "dpi": dpi,
                          "preprocess_before_ocr": preprocess_before_ocr,
                          "enable_region_ocr": enable_region_ocr},
        "diagnostic_only": True, "review_status": "unreviewed",
        "operation_status": "applied" if apply else "preview", "pages": [],
    }
    for page, raw, sidecar, metadata, target in prepared:
        record = {"page_id": page["page_id"], "source_id": page["source_id"],
                  "source_document_id": page["source_document_id"],
                  "inputs": {role: {"path": str(path), "sha256": inputs[path]}
                             for role, path in (("raw_tiff", raw), ("sidecar", sidecar), ("metadata", metadata))},
                  "output_path": str(target), "status": "ready", "written": False}
        report["pages"].append(record)
        if not apply:
            continue
        try:
            # Recheck every binding before each call, including the parent manifests.
            for path in (manifest_path, t36_path, raw, sidecar, metadata):
                if _sha256_file(path) != inputs[path]:
                    raise ValueError(f"Input modificato dopo preflight: {path}")
            _new_target(target)
            with tempfile.TemporaryDirectory(prefix="ocr-tesseract-page-") as temporary:
                result = run_document_ocr(
                    file_path=raw, sidecar_path=sidecar, root_dir=root,
                    output_dir=Path(temporary), metadata_path=metadata,
                    metadata_sha256=inputs[metadata], sidecar_sha256=inputs[sidecar],
                    review_status="unreviewed", overwrite=False,
                    command_runner=command_runner, tesseract_path=tesseract_path, language=language,
                    page_segmentation_mode=page_segmentation_mode, engine_mode=engine_mode, dpi=dpi,
                    preprocess_before_ocr=preprocess_before_ocr, enable_region_ocr=enable_region_ocr,
                )
                data = Path(result["text_path"]).read_bytes()
                for path in (manifest_path, t36_path, raw, sidecar, metadata):
                    if _sha256_file(path) != inputs[path]:
                        raise ValueError(f"Input modificato durante OCR: {path}")
                text = json.loads(data)
                text["diagnostic_only"] = True
                data = (json.dumps(text, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
                _write_new(target, data)
            result["text_path"] = str(target)
            record.update(status="success", written=True, registration=result)
        except Exception as exc:
            record.update(status="error", error={"type": type(exc).__name__, "message": str(exc)})
    report["summary"] = {status: sum(page["status"] == status for page in report["pages"])
                         for status in ("ready", "success", "error")}
    if apply:
        _write_new(report_target, (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))
    return report
