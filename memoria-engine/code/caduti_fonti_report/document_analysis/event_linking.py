"""Preview-only HistoricalEvent links from explicit event mention candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def build_candidate_document_event_links(
    *, mentions_dir: Path, events_index_json: Path,
    output_json: Path | None = None, output_md: Path | None = None,
) -> dict[str, Any]:
    index_bytes = events_index_json.read_bytes()
    labels = _event_labels(json.loads(index_bytes.decode("utf-8")))
    index_reference = {"path": str(events_index_json), "sha256": _digest(index_bytes)}
    links, skipped_mentions, skipped_documents = [], [], []
    seen: set[tuple[str, str, str, str]] = set()
    inputs = [events_index_json, *sorted(mentions_dir.rglob("*.mentions.json"))]
    for output in (output_json, output_md):
        if output is not None and output.resolve() in {path.resolve() for path in inputs}:
            raise ValueError("Event link output must not overwrite an input artifact.")
    if output_json is not None and output_md is not None and output_json.resolve() == output_md.resolve():
        raise ValueError("JSON and Markdown outputs require distinct paths.")

    for path in inputs[1:]:
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            skipped_documents.append({"mentions_file": str(path), "reason": "unreadable_mentions_payload"})
            continue
        if not isinstance(payload, dict) or payload.get("@type") != "DocumentMentionCandidateDocument":
            skipped_documents.append({"mentions_file": str(path), "reason": "unsupported_payload_type"})
            continue
        if not isinstance(payload.get("mentions"), list):
            skipped_documents.append({"mentions_file": str(path), "reason": "mentions_not_list"})
            continue
        for mention in payload["mentions"]:
            reason = _mention_error(mention, payload, index_reference["sha256"])
            matches = labels.get(_normalize(mention.get("value")), []) if isinstance(mention, dict) else []
            if not reason and len(matches) != 1:
                reason = "event_not_found" if not matches else "ambiguous_event_label"
            if not reason:
                event = matches[0]
                segment = _text(mention.get("weak_segment_id")) or (
                    "context:" + _digest((_text(mention.get("chunk_id")) + "|" + _normalize(mention.get("context"))).encode("utf-8"))
                    if _text(mention.get("context")) else _mention_id(mention)
                )
                key = (_text(mention["source_id"]), _text(mention["source_document_id"]), event["event_id"], segment)
                if key in seen:
                    reason = "duplicate_event_link_in_segment"
                else:
                    seen.add(key)
            if reason:
                skipped_mentions.append({
                    "mention_id": _mention_id(mention) if isinstance(mention, dict) else "",
                    "source_document_id": _text(mention.get("source_document_id")) if isinstance(mention, dict) else "",
                    "mentions_file": str(path), "reason": reason,
                })
                continue
            identity = [event["event_id"], mention["source_id"], mention["source_document_id"], _mention_id(mention)]
            link = {
                "@type": "CandidateDocumentEventLink",
                "@id": "candidate-document-event-link:" + _digest(json.dumps(identity).encode("utf-8"))[:16],
                "event_id": event["event_id"], "event_label": event["label"],
                "matched_label": mention["value"], "match_kind": "exact_label",
                "mention_id": _mention_id(mention),
                **{key: mention.get(key, "") for key in (
                    "source_id", "source_document_id", "chunk_id", "weak_segment_id", "context",
                    "segment_char_start", "segment_char_end", "segment_type",
                )},
                "score": 1.0, "confidence": _confidence(mention.get("confidence")),
                "events_index": index_reference,
                "mentions_source": {"path": str(path), "sha256": _digest(raw)},
                "mention_event_label_index": mention.get("event_label_index"),
                "catalog_review_status": _text(event.get("review_status")) or "unreviewed",
                "review_status": "unreviewed", "requires_human_review": True,
                "event_write_allowed": False, "claim_extraction_allowed": False,
                "warnings": ["event_link_not_verified_fact", "event_link_not_person_participation", "event_identity_requires_human_review"],
            }
            links.append(link)
    result = {
        "@type": "CandidateDocumentEventLinkSet", "mentions_dir": str(mentions_dir),
        "events_index": index_reference, "preview_only": True, "event_write_allowed": False,
        "review_status": "unreviewed", "link_count": len(links),
        "skipped_mention_count": len(skipped_mentions), "skipped_document_count": len(skipped_documents),
        "candidate_document_event_links": links,
        "skipped_mentions": skipped_mentions, "skipped_documents": skipped_documents,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_candidate_document_event_links_markdown(result), encoding="utf-8")
    return result


def _event_labels(payload: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict) or payload.get("@type") != "HistoricalEventIndex" or not isinstance(payload.get("events"), list):
        raise ValueError("Expected a HistoricalEventIndex with an events list.")
    labels: dict[str, list[dict[str, Any]]] = {}
    seen = set()
    for event in payload["events"]:
        if not isinstance(event, dict) or not _text(event.get("event_id")) or not _text(event.get("label")):
            raise ValueError("HistoricalEventIndex requires event_id and label strings.")
        event_id = _text(event["event_id"])
        if event_id in seen or ("@id" in event and event["@id"] != event_id):
            raise ValueError("HistoricalEventIndex identifiers must be unique and consistent.")
        seen.add(event_id)
        labels.setdefault(_normalize(event["label"]), []).append({**event, "event_id": event_id, "label": event["label"].strip()})
    return labels


def _mention_error(mention: Any, payload: dict[str, Any], index_sha256: str) -> str:
    if not isinstance(mention, dict) or mention.get("mention_kind") != "event" or mention.get("@type") != "EventMentionCandidate":
        return "unsupported_mention_type"
    for field in ("source_document_id", "source_id"):
        if not _text(mention.get(field)):
            return f"missing_{field}"
        if _text(payload.get(field)) and _text(payload[field]) != _text(mention[field]):
            return "document_provenance_mismatch"
    if not _mention_id(mention):
        return "missing_mention_id"
    if mention.get("review_status") != "unreviewed":
        return "mention_not_unreviewed"
    if not _text(mention.get("value")):
        return "missing_event_label"
    reference = mention.get("event_label_index")
    if reference is not None and (not isinstance(reference, dict) or reference.get("sha256") != index_sha256):
        return "event_index_provenance_mismatch"
    if any(marker in _normalize(mention.get("context")) for marker in ("salta al contenuto", "menu home", "centro di documentazione", "documentazione dalla resistenza")):
        return "navigation_or_boilerplate_context"
    return ""


def _mention_id(mention: dict[str, Any]) -> str:
    return _text(mention.get("mention_id") or mention.get("@id"))


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize(value: Any) -> str:
    return " ".join(_text(value).casefold().split())


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _confidence(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1:
        return float(value)
    return None


def render_candidate_document_event_links_markdown(payload: dict[str, Any]) -> str:
    lines = ["# CandidateDocumentEventLink preview", "", "Event identity and facts require human review.", "",
             f"- Candidate links: `{payload.get('link_count', 0)}`",
             f"- Skipped mentions: `{payload.get('skipped_mention_count', 0)}`", ""]
    for link in payload.get("candidate_document_event_links", []):
        lines.append(f"- `{link['event_id']}` / `{link['source_document_id']}` / `{link['mention_id']}`: {link['matched_label']} (`unreviewed`)")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build preview-only HistoricalEvent links from event mentions.")
    parser.add_argument("--mentions-dir", required=True)
    parser.add_argument("--events-index-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md")
    args = parser.parse_args()
    build_candidate_document_event_links(mentions_dir=Path(args.mentions_dir), events_index_json=Path(args.events_index_json),
        output_json=Path(args.output_json), output_md=Path(args.output_md) if args.output_md else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
