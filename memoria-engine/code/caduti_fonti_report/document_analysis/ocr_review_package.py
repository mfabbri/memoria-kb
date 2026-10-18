"""Atomic preparation of diagnostic OCR review packages from explicit artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .ocr_evidence_comparison import compare_ocr_page_evidence
from .ocr_review_scaffold import scaffold_ocr_review, _read_object
from .ocr_transform_structure import export_ocr_transform_structure


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def _artifact(path: Path, *, stage: Path | None = None, destination: Path | None = None) -> dict[str, str]:
    final = destination / path.relative_to(stage) if stage is not None and destination is not None else path
    return {"path": str(final), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build_ocr_review_package(*, manifest_path: Path, variant_id: str,
                             page_profiles: Mapping[str, str],
                             tesseract_evidence: Mapping[str, Path], lexicons: Mapping[str, Path],
                             output_dir: Path, glossaries: Mapping[str, Path] | None = None,
                             apply: bool = False) -> dict[str, Any]:
    """Compose T37, comparison and incomplete review templates without inference.

    Only byte-identical raw single-frame TIFFs can provide the original pixel
    frame required by the review scaffold. The added frame locator is recorded
    in detached copies; all original evidence and its digest remain available.
    """
    destination = Path(output_dir).resolve()
    source_manifest = Path(manifest_path).resolve(strict=True)
    # Reuse T37 validation before creating any temporary output.
    preflight = export_ocr_transform_structure(manifest_path=source_manifest, variant_id=variant_id,
        page_profiles=page_profiles, output_dir=destination, apply=False)
    pages = preflight["pages"]
    ids = {page["page_id"] for page in pages}
    for label, mapping in (("tesseract-evidence", tesseract_evidence), ("lexicon", lexicons)):
        if set(mapping) != ids:
            raise ValueError(f"La mappa --{label} deve dichiarare esattamente ogni page_id del manifest.")
    if glossaries is not None and set(glossaries) != ids:
        raise ValueError("La mappa --glossary deve dichiarare esattamente ogni page_id del manifest.")
    if variant_id != "raw":
        raise ValueError("Il pacchetto review richiede la variante raw byte_copy.")
    from PIL import Image
    for page in pages:
        if page["variant_image"]["sha256"] != page["source_image"]["sha256"]:
            raise ValueError("La variante raw deve essere una copia byte-identica del TIFF sorgente.")
        with Image.open(page["source_image"]["path"]) as image:
            if image.format != "TIFF" or image.n_frames != 1:
                raise ValueError("Il pacchetto review richiede un TIFF single-frame.")

    with tempfile.TemporaryDirectory(prefix=".ocr-review-package-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "package"
        stage.mkdir()
        t37 = export_ocr_transform_structure(manifest_path=source_manifest, variant_id=variant_id,
            page_profiles=page_profiles, output_dir=stage / "t37", apply=True)
        (stage / "pages").mkdir()
        entries = []
        for page in t37["pages"]:
            page_id = page["page_id"]
            original = stage / "t37" / page["evidence"]["path"]
            candidate, _ = _read_object(original, "T37 evidence")
            transform = candidate.get("image_transform")
            source_page = candidate.get("source_page", {})
            if (not isinstance(transform, dict) or set(transform) != {"id", "parameters"}
                    or transform.get("id") != candidate.get("transform_id")
                    or not isinstance(transform.get("parameters"), dict)
                    or set(transform["parameters"]) - {"operation", "source_mode"}
                    or transform["parameters"].get("operation") != "byte_copy"
                    or source_page.get("variant_id") != "raw"
                    or source_page.get("target") != "full_page"
                    or source_page.get("crop") is not None or source_page.get("tile_id") is not None):
                raise ValueError("Evidence raw richiede identita' full-page byte_copy verificabile.")
            if "frame_index" in source_page and (type(source_page["frame_index"]) is not int or source_page["frame_index"] != 0):
                raise ValueError("frame_index incompatibile con TIFF single-frame.")
            right_path = Path(tesseract_evidence[page_id]).resolve(strict=True)
            right, _ = _read_object(right_path, "Tesseract evidence")
            # Validate exact supplied identity before adding the same locator to
            # both detached copies. This prevents silently repairing mismatches.
            compare_ocr_page_evidence(left=candidate, right=right)
            if candidate.get("engine") != "paddle-ocr-v5" or right.get("engine") != "tesseract":
                raise ValueError("Servono evidence paddle-ocr-v5 e tesseract.")
            folder = stage / "pages" / Path(page["evidence"]["path"]).stem
            folder.mkdir()
            candidate = copy.deepcopy(candidate)
            right = copy.deepcopy(right)
            candidate["source_page"]["frame_index"] = right["source_page"]["frame_index"] = 0
            evidence_path, right_copy = folder / "evidence.json", folder / "tesseract-evidence.json"
            _write(evidence_path, candidate)
            _write(right_copy, right)
            structure, _ = _read_object(stage / "t37" / page["structure"]["path"], "T37 structure")
            structure["source_evidence"]["source_page"] = copy.deepcopy(candidate["source_page"])
            structure_path = folder / "structure.json"
            _write(structure_path, structure)
            markdown_path = stage / "t37" / page["markdown"]["path"]
            from .ocr_candidate_assessment import _render_structure
            markdown_path.write_text(_render_structure(structure), encoding="utf-8", newline="\n")
            page["markdown"]["sha256"] = hashlib.sha256(markdown_path.read_bytes()).hexdigest()
            comparison = compare_ocr_page_evidence(left=candidate, right=right)
            comparison.update(inputs={"left": _artifact(evidence_path), "right": _artifact(right_copy)},
                machine_pass=False, auto_validation_enabled=False, semantic_accuracy_status="not_attested",
                review_status="unreviewed", promotion_status="unreviewed", operation_status="written")
            comparison_path = folder / "comparison.json"
            _write(comparison_path, comparison)
            lexicon = Path(lexicons[page_id]).resolve(strict=True)
            glossary = Path(glossaries[page_id]).resolve(strict=True) if glossaries is not None else None
            scaffold_ocr_review(image_path=Path(page["source_image"]["path"]), evidence_path=evidence_path,
                structure_path=structure_path, markdown_path=markdown_path, lexicon_path=lexicon,
                glossary_path=glossary, output_dir=folder / "review", comparison_path=comparison_path,
                variant_image_path=Path(page["variant_image"]["path"]),
                tesseract_evidence_path=right_copy, apply=True)
            # Rewrite only known stage paths, then refresh downstream digests.
            comparison["inputs"] = {"left": _artifact(evidence_path, stage=stage, destination=destination),
                                    "right": _artifact(right_copy, stage=stage, destination=destination)}
            comparison["output_path"] = str(destination / comparison_path.relative_to(stage))
            _write(comparison_path, comparison)
            scaffold_path = folder / "review" / "scaffold-manifest.json"
            scaffold, _ = _read_object(scaffold_path, "scaffold")
            lexical_path = folder / "review" / "lexicon-review.json"
            lexical, _ = _read_object(lexical_path, "lexical review")
            lexical["source_structure"] = str(destination / structure_path.relative_to(stage))
            lexical.pop("@id", None)
            lexical["@id"] = "ocr-lexicon-review:" + hashlib.sha256(
                json.dumps(lexical, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            _write(lexical_path, lexical)
            lexical_digest = "sha256:" + _artifact(lexical_path)["sha256"]
            dispositions_path = folder / "review" / "dispositions.json"
            dispositions, _ = _read_object(dispositions_path, "dispositions")
            dispositions["source_lexicon_review_digest"] = lexical_digest
            _write(dispositions_path, dispositions)
            scaffold["inputs"].update(comparison_path=comparison["output_path"],
                lexicon_review_digest=lexical_digest,
                comparison_digest="sha256:" + _artifact(comparison_path)["sha256"],
                tesseract_evidence_path=str(destination / right_copy.relative_to(stage)))
            _write(scaffold_path, scaffold)
            entry = {"page_id": page_id, "profile": page["profile"], "status": "template_incomplete",
                "review_status": "unreviewed", "frame_locator": {"frame_index": 0, "basis": "verified_single_frame_tiff"},
                "inputs": {"source_image": page["source_image"], "variant_image": page["variant_image"],
                           "tesseract_evidence": _artifact(right_path), "lexicon": _artifact(lexicon)},
                "t37": {name: _artifact(stage / "t37" / page[name]["path"], stage=stage, destination=destination)
                        for name in ("evidence", "structure", "markdown")},
                "outputs": [_artifact(path, stage=stage, destination=destination)
                            for path in sorted(folder.rglob("*")) if path.is_file()]}
            entry["review_inputs"] = {"image": page["source_image"], **{
                role: _artifact(path, stage=stage, destination=destination)
                for role, path in {
                    "evidence": evidence_path, "structure": structure_path, "markdown": markdown_path,
                    "lexicon_review": lexical_path, "layout": folder / "review" / "layout.json",
                    "ledger": folder / "review" / "visual-ledger.json", "dispositions": dispositions_path,
                    "comparison": comparison_path, "tesseract_evidence": right_copy,
                }.items()}}
            if glossary is not None:
                entry["inputs"]["glossary"] = _artifact(glossary)
            entries.append(entry)
        t37["output_dir"] = str(destination / "t37")
        t37["report_path"] = str(destination / "t37" / "run-manifest.json")
        _write(stage / "t37" / "run-manifest.json", t37)
        report = {"@type": "OcrReviewPackage", "schema_version": "1.0",
            "source_manifest": _artifact(source_manifest), "selected_variant": variant_id,
            "t37_manifest": _artifact(stage / "t37" / "run-manifest.json", stage=stage, destination=destination),
            "pages": entries, "status": "template_incomplete", "review_status": "unreviewed",
            "semantic_accuracy_status": "not_attested", "machine_pass": False,
            "auto_validation_enabled": False, "human_review_request_allowed": False,
            "gold_promotion_allowed": False, "operation_status": "written" if apply else "preview",
            "output_dir": str(destination), "report_path": str(destination / "package-manifest.json")}
        _write(stage / "package-manifest.json", report)
        if apply:
            if destination.exists():
                raise FileExistsError(f"La directory output deve essere nuova: {destination}")
            os.rename(stage, destination)
        return report
