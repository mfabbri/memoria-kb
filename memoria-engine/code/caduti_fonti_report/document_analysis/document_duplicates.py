from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def find_candidate_duplicate_documents(
    *,
    metadata_dir: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    metadata_records: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for metadata_path in sorted(metadata_dir.rglob("*.metadata.json")):
        metadata = _load_json_object(metadata_path)
        if not metadata:
            skipped.append({"metadata_file": str(metadata_path), "reason": "metadata_unreadable"})
            continue
        sha256 = str(metadata.get("sha256", "")).strip().casefold()
        if not sha256:
            skipped.append(
                {
                    "source_document_id": str(metadata.get("source_document_id", "")),
                    "metadata_file": str(metadata_path),
                    "reason": "sha256_missing",
                }
            )
            continue
        metadata["_metadata_file"] = str(metadata_path)
        metadata_records.append(metadata)

    duplicate_groups = _duplicate_groups(metadata_records)
    payload = {
        "@type": "CandidateDuplicateDocumentSet",
        "metadata_dir": str(metadata_dir),
        "duplicate_group_count": len(duplicate_groups),
        "skipped_count": len(skipped),
        "candidate_duplicate_documents": duplicate_groups,
        "skipped_documents": skipped,
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_candidate_duplicate_documents_markdown(payload), encoding="utf-8")

    return payload


def render_candidate_duplicate_documents_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CandidateDuplicateDocument preview",
        "",
        f"- Gruppi duplicati: `{payload.get('duplicate_group_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Duplicati candidati",
        "",
    ]
    groups = payload.get("candidate_duplicate_documents", [])
    if not isinstance(groups, list) or not groups:
        lines.append("_Nessun duplicato candidato._")
    else:
        for group in groups:
            lines.extend(
                [
                    f"### {group.get('duplicate_group_id', '')}",
                    "",
                    f"- Match: `{group.get('match_type', '')}`",
                    f"- SHA256: `{group.get('sha256', '')}`",
                    f"- Documenti: `{group.get('document_count', 0)}`",
                    f"- Stato revisione: `{group.get('review_status', '')}`",
                    f"- Confidenza: `{group.get('confidence', '')}`",
                    "",
                ]
            )
            for document in group.get("documents", []):
                if not isinstance(document, dict):
                    continue
                lines.append(
                    f"- `{document.get('source_document_id', '')}` | "
                    f"{document.get('source_id', '')} | {document.get('title', '')}"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _duplicate_groups(metadata_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for metadata in metadata_records:
        by_hash.setdefault(str(metadata.get("sha256", "")).casefold(), []).append(metadata)

    groups: list[dict[str, Any]] = []
    for sha256, documents in sorted(by_hash.items()):
        if len(documents) < 2:
            continue
        groups.append(
            {
                "@type": "CandidateDuplicateDocument",
                "@id": _duplicate_group_id(sha256),
                "duplicate_group_id": _duplicate_group_id(sha256),
                "match_type": "exact_sha256",
                "sha256": sha256,
                "document_count": len(documents),
                "documents": [_document_preview(document) for document in documents],
                "confidence": 1.0,
                "reasons": ["same_sha256"],
                "review_status": "unreviewed",
            }
        )
    return groups


def _document_preview(metadata: dict[str, Any]) -> dict[str, str]:
    return {
        "source_id": str(metadata.get("source_id", "")),
        "source_document_id": str(metadata.get("source_document_id", "")),
        "title": str(metadata.get("title", "")),
        "document_class": str(metadata.get("document_class", "")),
        "raw_file": str(metadata.get("raw_file", "")),
        "metadata_file": str(metadata.get("_metadata_file", "")),
        "url": str(metadata.get("url", "")),
        "archival_reference": str(metadata.get("archival_reference", "")),
        "review_status": str(metadata.get("review_status", "")) or "unreviewed",
    }


def _duplicate_group_id(sha256: str) -> str:
    digest = hashlib.sha256(f"exact_sha256|{sha256}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-duplicate-document:{digest}"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera CandidateDuplicateDocument preview-only da metadati processati.")
    parser.add_argument("--metadata-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/candidate_duplicate_documents.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/candidate_duplicate_documents.md")
    args = parser.parse_args()

    payload = find_candidate_duplicate_documents(
        metadata_dir=Path(args.metadata_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"CandidateDuplicateDocument JSON scritto in {args.output_json}")
    print(f"CandidateDuplicateDocument Markdown scritto in {args.output_md}")
    print(f"Gruppi duplicati: {payload['duplicate_group_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
