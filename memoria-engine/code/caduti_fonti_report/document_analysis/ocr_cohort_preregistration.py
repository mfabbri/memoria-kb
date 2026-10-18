"""Offline preregistration checks; never dereference page content or image paths."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any


def _allowed_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    if set(data) - allowed:
        raise ValueError(f"{field}: campi sconosciuti o contenuto non ammesso.")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field}: stringa non vuota senza spazi esterni richiesta.")
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{64}", value) is None:
        raise ValueError(f"{field}: SHA-256 non valido.")
    return value.lower()


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value
    ) is None:
        raise ValueError(f"{field}: timestamp ISO con fuso richiesto.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}: timestamp non valido.") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Chiave JSON duplicata.")
        result[key] = value
    return result


def _read_manifest_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSON non valido.") from exc
    if not isinstance(data, dict):
        raise ValueError("Oggetto JSON richiesto.")
    return data, raw


def require_external_path(path: Path) -> Path:
    """Resolve links and reject both this workspace and any other Git repository."""
    resolved = Path(path).resolve()
    workspace = Path(__file__).resolve().parents[4]
    if resolved.is_relative_to(workspace) or any(
        (parent / ".git").exists() for parent in (resolved.parent, *resolved.parents)
    ):
        raise ValueError("Il percorso deve essere esterno ai repository.")
    return resolved


def validate_ocr_cohort_preregistration(
    *, manifest_path: Path, freeze_receipt_path: Path | None = None
) -> dict[str, Any]:
    """Read only the explicit manifest and (for frozen state) external receipt."""
    manifest, raw = _read_manifest_json(require_external_path(manifest_path))
    _allowed_keys(manifest, {
        "@type", "schema_version", "cohort_id", "state", "prepared_at", "frozen_at",
        "sampling_design", "required_strata", "stratum_definitions", "pages",
    }, "manifest")
    if manifest.get("@type") != "OcrCohortPreregistration" or manifest.get("schema_version") != "1.0":
        raise ValueError("Richiesto OcrCohortPreregistration schema_version 1.0.")
    cohort_id = _text(manifest.get("cohort_id"), "cohort_id")
    state = manifest.get("state")
    if state not in ("prepared", "frozen"):
        raise ValueError("state deve essere prepared o frozen.")
    prepared_at = _timestamp(manifest.get("prepared_at"), "prepared_at")
    frozen_at = None
    if state == "frozen":
        frozen_at = _timestamp(manifest.get("frozen_at"), "frozen_at")
        if frozen_at < prepared_at:
            raise ValueError("frozen_at precede prepared_at.")
        if freeze_receipt_path is None:
            raise ValueError("Stato frozen richiede ricevuta esterna esplicita.")
    elif freeze_receipt_path is not None or manifest.get("frozen_at") is not None:
        raise ValueError("Stato prepared incompatibile con ricevuta o frozen_at.")
    design = manifest.get("sampling_design")
    if not isinstance(design, dict) or design.get("independence_unit") != "source_document_id":
        raise ValueError("sampling_design.independence_unit deve essere source_document_id.")
    _allowed_keys(design, {"frame", "method", "independence_unit"}, "sampling_design")
    for field in ("frame", "method"):
        _text(design.get(field), f"sampling_design.{field}")
    strata = manifest.get("required_strata")
    if not isinstance(strata, list) or not strata:
        raise ValueError("required_strata non vuoto richiesto.")
    for name in strata:
        _text(name, "required_strata")
    if len(set(strata)) != len(strata):
        raise ValueError("required_strata duplicati.")
    definitions = manifest.get("stratum_definitions")
    if not isinstance(definitions, dict) or set(definitions) != set(strata):
        raise ValueError("stratum_definitions deve definire esattamente required_strata.")
    descriptors = ("language", "readability", "layout")
    for definition in definitions.values():
        if not isinstance(definition, dict) or set(definition) != set(descriptors):
            raise ValueError("Ogni strato richiede language/readability/layout.")
        for field in descriptors:
            _text(definition.get(field), f"stratum_definitions.{field}")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("pages non vuoto richiesto.")
    page_ids: set[str] = set()
    hashes: set[str] = set()
    documents: set[str] = set()
    counts = {partition: {name: 0 for name in strata} for partition in ("calibration", "holdout")}
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise ValueError(f"pages[{index}]: oggetto richiesto.")
        _allowed_keys(page, {
            "page_id", "source_document_id", "source_image_sha256", "partition", "stratum",
            "language", "readability", "layout", "selection_reason", "selector", "responsible",
            "prior_engine_exposure", "transformations",
        }, f"pages[{index}]")
        page_id = _text(page.get("page_id"), "page_id")
        document = _text(page.get("source_document_id"), "source_document_id")
        digest = _sha256(page.get("source_image_sha256"), "source_image_sha256")
        if page_id in page_ids or digest in hashes or document in documents:
            raise ValueError("Identita' duplicata o sovrapposta tra partizioni (pagina, TIFF o documento).")
        page_ids.add(page_id)
        hashes.add(digest)
        documents.add(document)
        partition = page.get("partition")
        if partition not in ("calibration", "holdout"):
            raise ValueError("partition deve essere calibration o holdout.")
        stratum = _text(page.get("stratum"), "stratum")
        if stratum not in definitions:
            raise ValueError("Strato non preregistrato.")
        for field in descriptors:
            if page.get(field) != definitions[stratum][field]:
                raise ValueError(f"pages[{index}].{field} non corrisponde allo strato.")
        _text(page.get("selection_reason"), "selection_reason")
        _text(page.get("selector", page.get("responsible")), "selector/responsible")
        if "responsible" in page:
            _text(page["responsible"], "responsible")
        exposure = page.get("prior_engine_exposure")
        if not isinstance(exposure, list) or not exposure:
            raise ValueError("prior_engine_exposure non vuoto richiesto.")
        engines: set[str] = set()
        for item in exposure:
            if not isinstance(item, dict) or item.get("status") not in ("exposed", "not_exposed", "unknown"):
                raise ValueError("prior_engine_exposure status non valido.")
            _allowed_keys(item, {"engine", "status"}, "prior_engine_exposure")
            engine = _text(item.get("engine"), "prior_engine_exposure.engine")
            if engine in engines:
                raise ValueError("prior_engine_exposure engine duplicato.")
            engines.add(engine)
        transformations = page.get("transformations")
        if not isinstance(transformations, list):
            raise ValueError("transformations deve essere una lista.")
        for item in transformations:
            if not isinstance(item, dict) or not isinstance(item.get("applied"), bool):
                raise ValueError("transformations richiede name e applied booleano.")
            _allowed_keys(item, {"name", "applied", "output_sha256"}, "transformations")
            _text(item.get("name"), "transformations.name")
            if item.get("output_sha256") is not None:
                _sha256(item["output_sha256"], "transformations.output_sha256")
        counts[partition][stratum] += 1
    if any(sum(values.values()) == 0 for values in counts.values()):
        raise ValueError("Entrambe le partizioni calibration e holdout sono richieste.")
    if state == "frozen" and any(count == 0 for values in counts.values() for count in values.values()):
        raise ValueError("Stato frozen richiede tutti gli strati in entrambe le partizioni.")
    manifest_digest = hashlib.sha256(raw).hexdigest()
    receipt_digest = None
    if freeze_receipt_path is not None:
        receipt_path = require_external_path(freeze_receipt_path)
        if receipt_path == Path(manifest_path).resolve():
            raise ValueError("La ricevuta deve essere separata dal manifest.")
        receipt, receipt_raw = _read_manifest_json(receipt_path)
        _allowed_keys(receipt, {"manifest_sha256", "record_id", "storage_reference", "recorded_at"}, "receipt")
        if _sha256(receipt.get("manifest_sha256"), "receipt.manifest_sha256") != manifest_digest:
            raise ValueError("Digest ricevuta diverso dai byte esatti del manifest.")
        for field in ("record_id", "storage_reference"):
            _text(receipt.get(field), f"receipt.{field}")
        if _timestamp(receipt.get("recorded_at"), "receipt.recorded_at") < frozen_at:
            raise ValueError("receipt.recorded_at precede frozen_at.")
        receipt_digest = hashlib.sha256(receipt_raw).hexdigest()
    return {
        "@type": "OcrCohortPreregistrationReport", "schema_version": "1.0",
        "cohort_id": cohort_id, "state": state, "status": "valid_preregistration",
        "manifest_sha256": manifest_digest, "freeze_receipt_sha256": receipt_digest,
        "freeze_receipt_binding_verified": receipt_digest is not None,
        "page_count": len(pages), "source_document_count": len(documents),
        "partitions": {name: {"page_count": sum(values.values()), "strata": values} for name, values in counts.items()},
        "machine_pass": False, "auto_validation_enabled": False,
        "external_immutability_certified": False, "statistical_independence_certified": False,
        "limitations": [
            "Digest binding does not certify external immutability or statistical independence.",
            "Sampling provenance is declared, not independently verified; statistical adequacy is not assessed.",
            "Only predeclared cohort metadata, including holdout metadata, was read from the manifest; "
            "no TIFF bytes, OCR/reference/evaluation text or labels were opened.",
        ],
    }
