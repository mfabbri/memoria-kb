"""Compose the explicit, offline HistoricalEvent review preview artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from ..candidate_event_updates import build_candidate_event_updates
from .event_linking import build_candidate_document_event_links
from .mention_extraction import extract_document_mentions


def run_historical_event_preview(
    *, segments_dir: Path, events_index_json: Path, event_jsonld: Path,
    candidate_claims_json: Path, output_dir: Path,
) -> dict[str, Any]:
    """Write review artifacts into an empty directory, or verify an identical retry."""
    if not segments_dir.is_dir():
        raise ValueError("Expected an existing segments directory.")
    segment_paths = sorted(segments_dir.rglob("*.weak-segments.json"))
    if not segment_paths:
        raise ValueError("The segments directory contains no weak segment documents.")
    input_files = [events_index_json, event_jsonld, candidate_claims_json, *segment_paths]
    resolved_output = output_dir.resolve()
    for path in [segments_dir, *input_files]:
        resolved_input = path.resolve()
        if resolved_output.is_relative_to(resolved_input) or resolved_input.is_relative_to(resolved_output):
            raise ValueError("The output directory must not overlap any input.")
    event_id = _validate_event_inputs(events_index_json, event_jsonld, candidate_claims_json)
    inputs = {
        "events_index": _reference(events_index_json), "event": _reference(event_jsonld),
        "candidate_claims": _reference(candidate_claims_json),
        "segments": [_reference(path) for path in segment_paths],
    }
    manifest_path = output_dir / "manifest.json"
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        return _verified_retry(manifest_path, inputs, event_id, resolved_output)

    # Extract in memory first; generated file names never derive from untrusted IDs.
    mentions = extract_document_mentions(
        segments_dir=segments_dir, segment_paths=segment_paths, events_index_json=events_index_json,
    )
    mentions_dir = output_dir / "mentions"
    mentions["output_dir"] = str(mentions_dir)
    mention_paths = []
    for number, document in enumerate(mentions["documents"]):
        path = mentions_dir / f"{number:06d}.mentions.json"
        document["mentions_file"] = str(path)
        _write(path, document)
        mention_paths.append(path)
    summary_path = output_dir / "document_mentions.json"
    _write(summary_path, mentions)
    links_path = output_dir / "candidate_document_event_links.json"
    links = build_candidate_document_event_links(
        mentions_dir=mentions_dir, events_index_json=events_index_json, output_json=links_path,
    )
    updates = build_candidate_event_updates(
        candidate_claims_json=candidate_claims_json, candidate_event_links_json=links_path,
        event_jsonld=event_jsonld,
    )
    updates_path = output_dir / "candidate_event_updates.json"
    _write(updates_path, updates)
    manifest = {
        "@type": "HistoricalEventPreviewManifest", "event_id": event_id,
        "preview_only": True, "review_status": "pending", "requires_human_review": True,
        "apply_allowed": False, "automatic_merge_allowed": False, "event_write_allowed": False,
        "claim_extraction_allowed": False, "network_access_allowed": False,
        "inputs": inputs,
        "artifacts": {
            "mention_summary": _reference(summary_path),
            "mention_documents": [_reference(path) for path in mention_paths],
            "event_links": _reference(links_path), "event_updates": _reference(updates_path),
        },
        "counts": {
            "documents": mentions["document_count"],
            "event_mentions": sum(mention.get("mention_kind") == "event"
                                  for document in mentions["documents"] for mention in document["mentions"]),
            "event_links": links["link_count"], "candidate_updates": len(updates["candidate_updates"]),
            "skipped_claims": len(updates["skipped_claims"]),
        },
        "source_ids": sorted({link["source_id"] for link in links["candidate_document_event_links"]}),
        "source_document_ids": sorted({link["source_document_id"] for link in links["candidate_document_event_links"]}),
        "warnings": ["event_preview_not_verified_fact", "event_preview_not_person_participation",
                     "source_document_ids_not_catalog_verified"],
    }
    _write(manifest_path, manifest)
    return manifest


def _validate_event_inputs(index_path: Path, event_path: Path, claims_path: Path) -> str:
    index = _load(index_path, "HistoricalEventIndex")
    event = _load(event_path, "HistoricalEvent")
    claims = _load(claims_path, "CandidateEvidenceClaimSet")
    if not isinstance(claims.get("candidate_evidence_claims"), list):
        raise ValueError("CandidateEvidenceClaimSet requires candidate_evidence_claims.")
    entries = index.get("events")
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
        raise ValueError("The preview requires an index containing exactly one event.")
    entry = entries[0]
    event_id = _text(event.get("event_id") or event.get("@id"))
    if not event_id or any(_text(event.get(key)) not in ("", event_id) for key in ("event_id", "@id")):
        raise ValueError("HistoricalEvent identifiers are missing or divergent.")
    if _text(entry.get("event_id")) != event_id or _text(entry.get("@id")) not in ("", event_id):
        raise ValueError("The index and selected HistoricalEvent identifiers must match.")
    if not _text(event.get("label")) or _normalize(entry.get("label")) != _normalize(event["label"]):
        raise ValueError("The index and selected HistoricalEvent labels must match.")
    return event_id


def _verified_retry(path: Path, inputs: dict[str, Any], event_id: str, output_dir: Path) -> dict[str, Any]:
    try:
        manifest = _load(path, "HistoricalEventPreviewManifest")
        if (manifest.get("inputs") != inputs or manifest.get("event_id") != event_id
                or manifest.get("preview_only") is not True or manifest.get("requires_human_review") is not True
                or manifest.get("review_status") != "pending"
                or any(manifest.get(flag) is not False for flag in (
                    "apply_allowed", "automatic_merge_allowed", "event_write_allowed",
                    "claim_extraction_allowed", "network_access_allowed"))):
            raise ValueError("The output directory belongs to a different preview.")
        artifacts = manifest["artifacts"]
        references = [artifacts[key] for key in ("mention_summary", "event_links", "event_updates")]
        references.extend(artifacts["mention_documents"])
        expected = {path.resolve()}
        for reference in references:
            artifact = Path(reference["path"])
            if artifact.is_symlink() or not artifact.resolve().is_relative_to(output_dir):
                raise ValueError("Preview artifacts must remain inside the output directory.")
            if _reference(artifact) != reference:
                raise ValueError("A previous preview artifact has changed.")
            expected.add(artifact.resolve())
        if {item.resolve() for item in output_dir.rglob("*") if item.is_file()} != expected:
            raise ValueError("The output directory contains unexpected files.")
        return manifest
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Use an empty output directory or an intact identical preview.") from error


def _load(path: Path, kind: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("@type") != kind:
        raise ValueError("Expected a " + kind + ".")
    return payload


def _reference(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize(value: Any) -> str:
    return " ".join(_text(value).casefold().split())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compone la preview offline di un HistoricalEvent da input espliciti.")
    parser.add_argument("--segments-dir", type=Path, required=True)
    parser.add_argument("--events-index-json", type=Path, required=True)
    parser.add_argument("--event-jsonld", type=Path, required=True)
    parser.add_argument("--candidate-claims-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_historical_event_preview(**vars(args))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"HistoricalEvent preview: {result['event_id']}; manifest: {args.output_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
