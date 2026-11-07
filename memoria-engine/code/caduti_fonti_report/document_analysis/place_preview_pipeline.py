"""Compose explicit, offline Place review preview artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from ..candidate_place_updates import build_candidate_place_updates
from .mention_extraction import extract_document_mentions
from .place_linking import build_candidate_document_place_links
from .source_document_catalog import resolve_source_documents


def run_place_preview(*, segments_dir: Path, places_index_json: Path, place_jsonld: Path,
                      candidate_claims_json: Path, source_documents_db: Path,
                      output_dir: Path) -> dict[str, Any]:
    if not segments_dir.is_dir():
        raise ValueError("Expected an existing segments directory.")
    segments = sorted(segments_dir.rglob("*.weak-segments.json"))
    if not segments:
        raise ValueError("The segments directory contains no weak segment documents.")
    inputs_paths = [places_index_json, place_jsonld, candidate_claims_json, source_documents_db, *segments]
    out = output_dir.resolve()
    for source in [segments_dir, *inputs_paths]:
        resolved = source.resolve()
        if out.is_relative_to(resolved) or resolved.is_relative_to(out):
            raise ValueError("The output directory must not overlap any input.")
    place = _load(place_jsonld, "Place")
    place_id = _text(place.get("place_id") or place.get("@id"))
    if not place_id or any(_text(place.get(k)) not in ("", place_id) for k in ("place_id", "@id")):
        raise ValueError("Place identifiers are missing or divergent.")
    claims = _load(candidate_claims_json, "CandidateEvidenceClaimSet")
    if not isinstance(claims.get("candidate_evidence_claims"), list):
        raise ValueError("CandidateEvidenceClaimSet requires candidate_evidence_claims.")
    if any(not isinstance(item, dict) or not _text(item.get("source_document_id"))
           for item in claims["candidate_evidence_claims"]):
        raise ValueError("Every candidate claim must identify a source_document_id.")
    document_ids = {_text(item.get("source_document_id")) for item in claims["candidate_evidence_claims"]
                    if isinstance(item, dict)}
    for segment_path in segments:
        segment_document = json.loads(segment_path.read_text(encoding="utf-8"))
        document_ids.add(_text(segment_document.get("source_document_id")))
    document_ids.discard("")
    catalog_reference = resolve_source_documents(source_documents_db, document_ids)
    index = json.loads(places_index_json.read_text(encoding="utf-8"))
    if not isinstance(index, dict):
        raise ValueError("Expected a Place index object.")
    entries = index.get("places")
    if not isinstance(entries, list):
        raise ValueError("Place index requires a places list.")
    matches = [entry for entry in entries if isinstance(entry, dict) and
               _text(entry.get("place_id") or entry.get("@id")) == place_id]
    if len(matches) != 1 or not _text(matches[0].get("file")):
        raise ValueError("The index must reference the selected Place exactly once with an explicit file.")
    indexed_path = (places_index_json.parent / matches[0]["file"]).resolve()
    if indexed_path != place_jsonld.resolve():
        raise ValueError("The index and selected Place files must match.")
    inputs = {"places_index": _ref(places_index_json), "place": _ref(place_jsonld),
              "candidate_claims": _ref(candidate_claims_json),
              "source_documents_catalog": {"path": catalog_reference["path"], "sha256": catalog_reference["sha256"]},
              "segments": [_ref(p) for p in segments]}
    manifest_path = output_dir / "manifest.json"
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        return _retry(manifest_path, inputs, place_id, out)
    mentions = extract_document_mentions(segments_dir=segments_dir, segment_paths=segments)
    mention_dir = output_dir / "mentions"
    mention_files = []
    for i, document in enumerate(mentions["documents"]):
        p = mention_dir / f"{i:06d}.mentions.json"
        document["mentions_file"] = str(p)
        _write(p, document)
        mention_files.append(p)
    mentions_path = output_dir / "document_mentions.json"
    _write(mentions_path, mentions)
    links_path = output_dir / "candidate_document_place_links.json"
    links = build_candidate_document_place_links(mentions_dir=mention_dir, places_index=places_index_json, output_json=links_path)
    updates = build_candidate_place_updates(candidate_claims_json=candidate_claims_json, place_jsonld=place_jsonld)
    update_path = output_dir / "candidate_place_updates.json"
    _write(update_path, updates)
    manifest = {"@type": "PlacePreviewManifest", "place_id": place_id, "preview_only": True,
        "review_status": "pending", "requires_human_review": True, "apply_allowed": False,
        "automatic_merge_allowed": False, "place_write_allowed": False, "claim_extraction_allowed": False,
        "network_access_allowed": False, "inputs": inputs,
        "artifacts": {"mention_summary": _ref(mentions_path),
            "mention_documents": [_ref(p) for p in mention_files], "place_links": _ref(links_path),
            "place_updates": _ref(update_path)},
        "counts": {"documents": mentions["document_count"], "mentions": sum(len(d["mentions"]) for d in mentions["documents"]),
            "place_links": links["link_count"], "candidate_updates": len(updates["candidate_updates"]),
            "skipped_claims": len(updates["skipped_claims"])},
        "warnings": ["place_preview_not_verified_fact", "source_document_content_not_verified"],
        "catalog_resolved_source_document_ids": catalog_reference["resolved_document_ids"]}
    _write(manifest_path, manifest)
    return manifest


def _load(path: Path, kind: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("@type") != kind:
        raise ValueError("Expected a " + kind + ".")
    return value


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _ref(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _retry(path: Path, inputs: dict[str, Any], place_id: str, out: Path) -> dict[str, Any]:
    try:
        manifest = _load(path, "PlacePreviewManifest")
        if manifest.get("inputs") != inputs or manifest.get("place_id") != place_id:
            raise ValueError()
        if any(manifest.get(key) is not False for key in ("apply_allowed", "automatic_merge_allowed", "place_write_allowed", "claim_extraction_allowed", "network_access_allowed")):
            raise ValueError()
        artifacts = manifest["artifacts"]
        refs = [artifacts[k] for k in ("mention_summary", "place_links", "place_updates")] + artifacts["mention_documents"]
        expected = {path.resolve()}
        for ref in refs:
            artifact = Path(ref["path"])
            if artifact.is_symlink() or not artifact.resolve().is_relative_to(out) or _ref(artifact) != ref:
                raise ValueError()
            expected.add(artifact.resolve())
        if {p.resolve() for p in out.rglob("*") if p.is_file()} != expected:
            raise ValueError()
        return manifest
    except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("Use an empty output directory or an intact identical preview.") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compone la preview offline di un Place da input espliciti.")
    for name in ("segments-dir", "places-index-json", "place-jsonld", "candidate-claims-json", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source-documents-db", type=Path, required=True,
                        help="SQLite catalog esistente, sola lettura, con source_documents.document_id.")
    args = parser.parse_args(argv)
    try:
        result = run_place_preview(**{key.replace("-", "_"): value for key, value in vars(args).items()})
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Place preview: {result['place_id']}; manifest: {args.output_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
