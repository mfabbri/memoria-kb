"""Derive T37 structure candidates from hash-checked T36 pilot evidence."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from .document_structure import reconstruct_document_structure, render_document_structure_markdown


_VARIANTS = {"raw", "grayscale", "contrast", "threshold"}
_PROFILES = {"leader_list_report", "numbered_report"}


def export_ocr_transform_structure(
    *, manifest_path: Path, variant_id: str, page_profiles: Mapping[str, str],
    output_dir: Path, apply: bool = False,
) -> dict[str, Any]:
    """Validate one explicit T36 full-page variant and derive T37 artifacts.

    The output package contains detached ``OcrPageEvidence`` files,
    ``DocumentStructure`` JSON, Markdown, and an audit manifest. No OCR is run
    here and no variant/profile is inferred.
    """
    source_manifest = Path(manifest_path).resolve(strict=True)
    destination = Path(output_dir).resolve()
    if variant_id not in _VARIANTS:
        raise ValueError(f"Variante T36 non supportata: {variant_id}.")
    if not source_manifest.is_file():
        raise FileNotFoundError(f"Manifest T36 non trovato: {source_manifest}")
    if destination.exists():
        raise FileExistsError(f"La directory output deve essere nuova: {destination}")
    repository_root = Path(__file__).resolve().parents[4]
    try:
        destination.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise ValueError(f"La directory output deve restare esterna al repository: {repository_root}")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"La directory padre output deve esistere: {destination.parent}")

    manifest_bytes = source_manifest.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
    if not isinstance(manifest, dict) or manifest.get("@type") != "OcrTransformPilot" or manifest.get("schema_version") != "1.0":
        raise ValueError("E' richiesto un OcrTransformPilot v1.0.")
    if manifest.get("review_status") != "unreviewed" or manifest.get("accuracy_claim") != "none_without_human_reference":
        raise ValueError("Il manifest T36 deve mantenere review_status=unreviewed e accuracy_claim=none_without_human_reference.")
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Manifest T36 senza pagine.")
    page_ids = [_required_text(item.get("page_id"), "page_id") if isinstance(item, dict) else "" for item in pages]
    if any(not page_id for page_id in page_ids) or len(set(page_ids)) != len(page_ids):
        raise ValueError("page_id T36 mancanti o duplicati.")
    safe_names = [_safe_name(page_id) for page_id in page_ids]
    if len(set(safe_names)) != len(safe_names):
        raise ValueError("I page_id T36 collidono dopo la normalizzazione dei nomi artifact.")
    if set(page_profiles) != set(page_ids):
        raise ValueError("La mappa --page-profile deve dichiarare esattamente ogni page_id del manifest.")
    if any(profile not in _PROFILES for profile in page_profiles.values()):
        raise ValueError("Profilo strutturale non supportato.")

    manifest_root = source_manifest.parent
    prepared: list[dict[str, Any]] = []
    for page in pages:
        page_id = str(page["page_id"])
        source = page.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"Sorgente T36 mancante per {page_id}.")
        source_path = Path(_required_text(source.get("path"), "source.path")).resolve(strict=True)
        source_hash = _required_sha256(source.get("sha256"), "source.sha256")
        if not source_path.is_file() or _sha256_file(source_path) != source_hash:
            raise ValueError(f"SHA-256 TIFF sorgente divergente per {page_id}.")
        dimensions = source.get("image_dimensions")
        if not isinstance(dimensions, dict) or any(type(dimensions.get(key)) is not int or dimensions[key] <= 0 for key in ("width", "height")):
            raise ValueError(f"Dimensioni sorgente non valide per {page_id}.")
        variants = page.get("variants")
        if not isinstance(variants, list):
            raise ValueError(f"Varianti T36 non valide per {page_id}.")
        matches = [item for item in variants if isinstance(item, dict) and item.get("variant_id") == variant_id]
        if len(matches) != 1:
            raise ValueError(f"Variante {variant_id} mancante o duplicata per {page_id}.")
        variant = matches[0]
        variant_path = _manifest_artifact_path(manifest_root, variant.get("path"))
        variant_hash = _required_sha256(variant.get("sha256"), f"{page_id}.{variant_id}.sha256")
        if _sha256_file(variant_path) != variant_hash:
            raise ValueError(f"SHA-256 immagine variante divergente per {page_id}/{variant_id}.")
        transform = variant.get("transform")
        if not isinstance(transform, dict) or not isinstance(transform.get("id"), str):
            raise ValueError(f"Trasformazione variante non valida per {page_id}/{variant_id}.")
        outputs = variant.get("ocr_outputs")
        full_page = [item for item in outputs if isinstance(item, dict) and item.get("target") == "full_page"] if isinstance(outputs, list) else []
        if len(full_page) != 1:
            raise ValueError(f"Atteso un solo output OCR full-page per {page_id}/{variant_id}.")
        output = full_page[0]
        output_path = _manifest_artifact_path(manifest_root, output.get("artifact"))
        if output_path != variant_path or output.get("artifact_sha256") != variant_hash:
            raise ValueError(f"L'OCR full-page non e' legato all'immagine variante per {page_id}/{variant_id}.")
        if output.get("source_bbox") != [0, 0, dimensions["width"], dimensions["height"]]:
            raise ValueError(f"L'output selezionato non copre l'intera pagina {page_id}/{variant_id}.")
        evidence = output.get("structured_evidence")
        _validate_evidence(
            evidence=evidence, page_id=page_id, source=source, dimensions=dimensions,
            variant_id=variant_id, transform_id=transform["id"], language=manifest.get("language"),
        )
        profile = page_profiles[page_id]
        structure = reconstruct_document_structure(evidence=evidence, profile=profile)
        markdown = render_document_structure_markdown(structure)
        evidence_bytes = _json_bytes(evidence)
        structure_bytes = _json_bytes(structure.to_dict())
        markdown_bytes = markdown.encode("utf-8")
        safe_page = _safe_name(page_id)
        prepared.append({
            "page_id": page_id,
            "variant_id": variant_id,
            "profile": profile,
            "source_image": {"path": str(source_path), "sha256": source_hash},
            "variant_image": {"path": str(variant_path), "sha256": variant_hash},
            "evidence": {"path": f"evidence/{safe_page}.evidence.json", "sha256": _sha256_bytes(evidence_bytes)},
            "structure": {"path": f"structure/{safe_page}.structure.json", "sha256": _sha256_bytes(structure_bytes)},
            "markdown": {"path": f"markdown/{safe_page}.md", "sha256": _sha256_bytes(markdown_bytes)},
            "region_count": len(evidence["regions"]),
            "block_count": len(structure.blocks),
            "_evidence_bytes": evidence_bytes,
            "_structure_bytes": structure_bytes,
            "_markdown_bytes": markdown_bytes,
        })

    report = {
        "@type": "OcrTransformStructureRun",
        "schema_version": "1.0",
        "source_manifest": {"path": str(source_manifest), "sha256": _sha256_bytes(manifest_bytes)},
        "selected_variant": variant_id,
        "pages": [{key: value for key, value in item.items() if not key.startswith("_")} for item in prepared],
        "completed_stages": ["t36_manifest_validation", "t36_source_hash_verification", "t37_structure", "t37_markdown"],
        "pending_stages": ["tesseract_comparison", "lexical_review", "visual_coverage_audit", "layout_audit", "alert_disposition", "page_level_review"],
        "status": "structure_candidate_ready_pending_required_reviews",
        "review_status": "unreviewed",
        "semantic_accuracy_status": "not_attested",
        "machine_pass": False,
        "auto_validation_enabled": False,
        "gold_promotion_allowed": False,
        "operation_status": "preview",
        "output_dir": str(destination),
    }
    if not apply:
        return report

    temporary: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix=".ocr-transform-structure-", dir=destination.parent) as temp_name:
            temporary = Path(temp_name)
            for folder in ("evidence", "structure", "markdown"):
                (temporary / folder).mkdir()
            for item in prepared:
                for key, internal in (("evidence", "_evidence_bytes"), ("structure", "_structure_bytes"), ("markdown", "_markdown_bytes")):
                    target = temporary / item[key]["path"]
                    target.write_bytes(item[internal])
            report["operation_status"] = "written"
            report_path = temporary / "run-manifest.json"
            report["report_path"] = str(destination / "run-manifest.json")
            report_path.write_bytes(_json_bytes(report))
            os.rename(temporary, destination)
            temporary = None
    except FileExistsError:
        raise FileExistsError(f"La directory output e' stata creata durante l'operazione: {destination}")
    return report


def _validate_evidence(*, evidence: Any, page_id: str, source: Mapping[str, Any],
                       dimensions: Mapping[str, int], variant_id: str, transform_id: str,
                       language: Any) -> None:
    if not isinstance(evidence, dict) or evidence.get("@type") != "OcrPageEvidence" or evidence.get("schema_version") != "1.0":
        raise ValueError(f"OcrPageEvidence v1 mancante per {page_id}/{variant_id}.")
    anchor = evidence.get("source_page", {}).get("original_page") if isinstance(evidence.get("source_page"), dict) else None
    if (evidence.get("page_id") != page_id or evidence.get("source_image_hash") != source.get("sha256")
            or evidence.get("transform_id") != transform_id or evidence.get("language") != language
            or not isinstance(anchor, dict) or anchor.get("page_id") != page_id
            or anchor.get("source_image_hash") != source.get("sha256")
            or anchor.get("source_file") != source.get("path")
            or anchor.get("source_dimensions") != dimensions):
        raise ValueError(f"Identita' o anchor sorgente divergente per {page_id}/{variant_id}.")
    source_page = evidence.get("source_page")
    if (source_page.get("variant_id") != variant_id or source_page.get("target") != "full_page"
            or source_page.get("tile_id") is not None or source_page.get("source_bbox") is not None):
        raise ValueError(f"Il payload evidence non e' full-page per la variante {page_id}/{variant_id}.")
    regions = evidence.get("regions")
    if not isinstance(regions, list) or not regions:
        raise ValueError(f"Evidence senza regioni OCR per {page_id}/{variant_id}.")
    seen: set[str] = set()
    width, height = dimensions["width"], dimensions["height"]
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError(f"Regione OCR non valida per {page_id}/{variant_id}.")
        region_id = _required_text(region.get("region_id"), "region_id")
        if region_id in seen:
            raise ValueError(f"region_id duplicato per {page_id}/{variant_id}: {region_id}.")
        seen.add(region_id)
        geometry = region.get("geometry")
        bbox = geometry.get("bbox") if isinstance(geometry, dict) else None
        if (not isinstance(bbox, list) or len(bbox) != 4
                or not all(isinstance(value, (int, float)) for value in bbox)
                or not all(math.isfinite(value) for value in bbox)
                or bbox[0] < 0 or bbox[1] < 0 or bbox[2] > width or bbox[3] > height
                or bbox[2] < bbox[0] or bbox[3] < bbox[1]):
            raise ValueError(f"Bounding box fuori pagina o non valida per {page_id}/{variant_id}/{region_id}.")


def _manifest_artifact_path(root: Path, value: Any) -> Path:
    relative = Path(_required_text(value, "artifact path"))
    if relative.is_absolute():
        raise ValueError("I path degli artifact T36 devono essere relativi al manifest.")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Artifact T36 fuori dalla root del manifest: {value}") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"Artifact T36 mancante: {resolved}")
    return resolved


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")
    if safe in {"", ".", ".."}:
        raise ValueError("page_id non valido come nome artifact.")
    return safe


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} deve essere testo non vuoto.")
    return value.strip()


def _required_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{field} deve essere SHA-256 esadecimale.")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Chiave JSON duplicata: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Costante JSON non finita non consentita: {value}")
