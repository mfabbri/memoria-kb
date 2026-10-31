"""Apply explicit, image-bound visual corrections to a derived OCR candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from .document_structure import DocumentBlock, DocumentStructure, EvidenceReference, render_document_structure_markdown
from .ocr_visual_review_ledger import audit_ocr_visual_review_ledger


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Atteso un oggetto JSON: {path}")
    json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return value, raw


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _typed_structure(structure: dict[str, Any]) -> DocumentStructure:
    source = structure.get("source_evidence")
    if not isinstance(source, dict):
        raise ValueError("DocumentStructure.source_evidence mancante.")
    evidence_ref = EvidenceReference(
        page_id=source["page_id"], source_image_hash=source["source_image_hash"],
        transform_id=source["transform_id"], engine=source["engine"], language=source["language"],
        source_page_json=json.dumps(source["source_page"], ensure_ascii=False),
        model_json=json.dumps(source["model"], ensure_ascii=False),
        image_transform_json=json.dumps(source["image_transform"], ensure_ascii=False)
        if source.get("image_transform") is not None else None,
    )
    typed_blocks = tuple(DocumentBlock(
        block_id=block["block_id"], kind=block["kind"],
        source_region_ids=tuple(block["source_region_ids"]), text=block["text"],
        status=block["status"], structure_confidence=block["structure_confidence"],
        value=block.get("value"),
    ) for block in structure["blocks"])
    return DocumentStructure(page_id=structure["page_id"], profile=structure["profile"],
                             blocks=typed_blocks, source_evidence=evidence_ref)


def apply_ocr_visual_corrections(*, image_path: Path, evidence_path: Path,
                                 structure_path: Path, markdown_path: Path,
                                 ledger_path: Path, correction_set_path: Path,
                                 output_dir: Path, apply: bool = False) -> dict[str, Any]:
    """Derive a corrected candidate from explicit readable human observations.

    Inputs remain untouched. The new package contains corrected structure and
    Markdown, a provenance ledger rebound to that structure, copied crop
    evidence, and the audit of the resulting ledger. Downstream lexical/layout
    sidecars must be regenerated from these new candidate artifacts.
    """
    paths = {key: Path(value) for key, value in {
        "image": image_path, "evidence": evidence_path, "structure": structure_path,
        "markdown": markdown_path, "ledger": ledger_path, "correction_set": correction_set_path,
    }.items()}
    loaded: dict[str, dict[str, Any]] = {}
    raw: dict[str, bytes] = {}
    for name, path in paths.items():
        if name != "image" and name != "markdown":
            loaded[name], raw[name] = _read_json(path)
        else:
            raw[name] = path.read_bytes()
    markdown_text = raw["markdown"].decode("utf-8").replace("\r\n", "\n")
    structure = loaded["structure"]
    evidence = loaded["evidence"]
    ledger = loaded["ledger"]
    corrections = loaded["correction_set"]
    if markdown_text != render_document_structure_markdown(_typed_structure(structure)):
        raise ValueError("Markdown sorgente non corrisponde alla struttura candidata corrente.")
    if corrections.get("@type") != "OcrVisualCorrectionSet" or corrections.get("schema_version") != "1.0":
        raise ValueError("Serve OcrVisualCorrectionSet v1.0.")
    source_digests = corrections.get("source_digests")
    if not isinstance(source_digests, dict) or any(
            source_digests.get(name) != _digest(raw[name]) for name in ("image", "evidence", "structure", "markdown", "ledger")):
        raise ValueError("Il correction set non lega i byte esatti di immagine e candidati sorgente.")
    original_audit = audit_ocr_visual_review_ledger(
        ledger_path=paths["ledger"], image_path=paths["image"],
        evidence_path=paths["evidence"], structure_path=paths["structure"])
    if original_audit.get("processability_status") != "diagnostic_only" \
            or original_audit.get("checks", {}).get("issues"):
        raise ValueError("Il ledger visuale sorgente deve superare l'audit prima della correzione.")
    if ledger.get("template_status") != "complete":
        raise ValueError("Il ledger visuale deve essere completo.")
    blocks = structure.get("blocks")
    observations = ledger.get("observations")
    proposed = corrections.get("corrections")
    if not isinstance(blocks, list) or not isinstance(observations, list) or not isinstance(proposed, list) or not proposed:
        raise ValueError("Servono blocchi, osservazioni e almeno una correzione esplicita.")
    block_map = {item.get("block_id"): item for item in blocks if isinstance(item, dict)}
    observation_map = {item.get("observation_id"): item for item in observations if isinstance(item, dict)}
    updated: dict[str, dict[str, Any]] = {}
    for item in proposed:
        if not isinstance(item, dict):
            raise ValueError("Ogni correzione deve essere un oggetto.")
        block_id, observation_id = item.get("block_id"), item.get("observation_id")
        block, observation = block_map.get(block_id), observation_map.get(observation_id)
        if block is None or observation is None or observation.get("unit_type") != "block" \
                or observation.get("unit_id") != block_id:
            raise ValueError("Ogni correzione deve riferirsi a un'osservazione visuale del blocco esatto.")
        if block_id in updated:
            raise ValueError("Una sola correzione per blocco per esecuzione.")
        field = item.get("field", "text")
        if field not in ("text", "value") or (field == "value" and "value" not in block):
            raise ValueError("field deve identificare text o il value presente nel blocco.")
        current_text = block.get(field)
        observed_candidate = observation.get("candidate_text") if field == "text" else observation.get("candidate_value")
        if (observation.get("outcome") != "readable" or observation.get("text") != item.get("corrected_text")
                or observed_candidate != current_text or item.get("expected_candidate_text") != current_text):
            raise ValueError("Il testo proposto deve coincidere con l'osservazione leggibile sul candidato corrente.")
        observer = observation.get("observer")
        if not isinstance(observer, dict) or observer.get("observer_id") != item.get("reviewer_id"):
            raise ValueError("reviewer_id deve coincidere con l'osservatore registrato nel ledger.")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            raise ValueError("Ogni correzione richiede una motivazione visuale.")
        updated[block_id] = item | {"field": field}
    corrected = json.loads(json.dumps(structure, ensure_ascii=False))
    corrected_blocks = {block["block_id"]: block for block in corrected["blocks"]}
    for block_id, item in updated.items():
        corrected_blocks[block_id][item["field"]] = item["corrected_text"]
    typed = _typed_structure(corrected)
    corrected_structure_raw = (json.dumps(corrected, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    corrected_markdown_raw = render_document_structure_markdown(typed).encode("utf-8")
    correction_digest = _digest(raw["correction_set"])
    rebound_ledger = json.loads(json.dumps(ledger, ensure_ascii=False))
    for observation in rebound_ledger["observations"]:
        block_id = observation.get("unit_id")
        if observation.get("unit_type") == "block" and block_id in updated:
            field = updated[block_id]["field"]
            ledger_field = "candidate_text" if field == "text" else "candidate_value"
            observation[ledger_field + "_before_correction"] = observation.get(ledger_field)
            observation[ledger_field] = updated[block_id]["corrected_text"]
            observation["correction_set_digest"] = correction_digest
    output_path = Path(output_dir).resolve()
    if output_path.exists():
        raise ValueError("output_dir deve essere nuovo e inesistente.")
    report = {
        "@type": "OcrVisualCorrectionApplication", "schema_version": "1.0",
        "source_digests": {name: _digest(raw[name]) for name in ("image", "evidence", "structure", "markdown", "ledger", "correction_set")},
        "corrections": [{"block_id": key, "field": value["field"], "observation_id": value["observation_id"],
                         "before": value["expected_candidate_text"], "after": value["corrected_text"],
                         "reviewer_id": value["reviewer_id"], "reason": value["reason"]}
                        for key, value in updated.items()],
        "derived": {"structure_sha256": _digest(corrected_structure_raw),
                    "markdown_sha256": _digest(corrected_markdown_raw)},
        "downstream_sidecars": "stale_and_must_be_regenerated_from_corrected_candidate",
        "human_verified": False, "machine_pass": False, "auto_validation_enabled": False,
        "semantic_accuracy_status": "not_attested", "claim_extraction_allowed": False,
        "operation_status": "preview", "output_dir": str(output_path),
    }
    if apply:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(paths["ledger"].parent / "crops", output_path / "crops")
        (output_path / "structure.json").write_bytes(corrected_structure_raw)
        (output_path / "candidate.md").write_bytes(corrected_markdown_raw)
        rebound_ledger["source_structure_digest"] = _digest(corrected_structure_raw)
        rebound_raw = (json.dumps(rebound_ledger, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        (output_path / "visual-ledger.json").write_bytes(rebound_raw)
        post_audit = audit_ocr_visual_review_ledger(
            ledger_path=output_path / "visual-ledger.json", image_path=paths["image"],
            evidence_path=paths["evidence"], structure_path=output_path / "structure.json")
        (output_path / "visual-audit.json").write_text(
            json.dumps(post_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["post_correction_visual_audit"] = post_audit
        report["operation_status"] = "written"
        (output_path / "correction-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
