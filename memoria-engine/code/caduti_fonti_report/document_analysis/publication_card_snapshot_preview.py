from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..raw_store import slugify_identifier
from .preview_payloads import (
    dict_object as _dict_object,
    list_items as _list_items,
    list_strings as _list_strings,
    load_json_object as _load_json_object,
    unique_non_empty as _unique_non_empty,
    write_json as _write_json,
    write_markdown as _write_markdown,
    yaml_value as _yaml_value,
)


def build_publication_card_snapshot_preview(
    *,
    model_cards_manifest_json: Path,
    dataset_export_preview_json: Path,
    output_dir: Path,
    profile_id: list[str] | None = None,
    limit: int = 0,
) -> dict[str, Any]:
    if not model_cards_manifest_json.is_file():
        raise FileNotFoundError(f"Manifest schede modello non trovato: {model_cards_manifest_json}")
    if not dataset_export_preview_json.is_file():
        raise FileNotFoundError(f"Dataset export preview non trovato: {dataset_export_preview_json}")

    model_manifest = _load_json_object(model_cards_manifest_json)
    dataset = _load_json_object(dataset_export_preview_json)
    profile_filter = _unique_non_empty(profile_id or [])
    cards = [
        card
        for card in _list_items(model_manifest.get("cards"))
        if not profile_filter or str(card.get("profile_id", "")).strip() in profile_filter
    ]
    if limit > 0:
        cards = cards[:limit]

    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()
    dataset_hash = _sha256_file(dataset_export_preview_json)
    snapshots: list[dict[str, Any]] = []
    skipped_cards: list[dict[str, str]] = []

    for card in cards:
        profile = str(card.get("profile_id", "")).strip()
        canonical_name = str(card.get("canonical_name") or profile).strip()
        model_card_path = _resolve_path(str(card.get("model_card_path", "")), base_dir=model_cards_manifest_json.parent)
        if not model_card_path.is_file():
            skipped_cards.append(
                {
                    "profile_id": profile,
                    "canonical_name": canonical_name,
                    "model_card_path": str(model_card_path),
                    "reason": "model_card_missing",
                }
            )
            continue

        model_card_text = model_card_path.read_text(encoding="utf-8")
        model_card_hash = _sha256_file(model_card_path)
        dataset_profile = _dataset_profile(dataset, profile_id=profile)
        snapshot = _snapshot_payload(
            card=card,
            profile_id=profile,
            canonical_name=canonical_name,
            generated_at=generated_at,
            model_card_path=model_card_path,
            model_card_sha256=model_card_hash,
            dataset_export_preview_json=dataset_export_preview_json,
            dataset_export_sha256=dataset_hash,
            dataset_profile=dataset_profile,
            model_card_text=model_card_text,
        )
        slug = slugify_identifier(canonical_name or profile)
        snapshot_json = output_dir / f"{slug}.snapshot.json"
        snapshot_md = output_dir / f"{slug}.snapshot.md"
        snapshot["snapshot_json_path"] = str(snapshot_json)
        snapshot["snapshot_md_path"] = str(snapshot_md)
        _write_json(snapshot_json, snapshot)
        _write_markdown(snapshot_md, render_publication_card_snapshot_markdown(snapshot))
        snapshots.append(_manifest_snapshot_item(snapshot))

    manifest: dict[str, Any] = {
        "@type": "PublicationCardSnapshotPreviewIndex",
        "generated_at": generated_at,
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "source_model_cards_manifest_json": str(model_cards_manifest_json),
        "source_dataset_export_preview_json": str(dataset_export_preview_json),
        "source_dataset_export_sha256": dataset_hash,
        "output_dir": str(output_dir),
        "profile_ids": profile_filter,
        "snapshot_count": len(snapshots),
        "skipped_card_count": len(skipped_cards),
        "snapshots": snapshots,
        "skipped_cards": skipped_cards,
        "safety_notes": [
            "Snapshot preview-only: congela schede modello per revisione, non per pubblicazione.",
            "Non modifica profili JSON-LD.",
            "Non applica ProfilePatch.",
            "Non crea verified_facts canonici.",
        ],
    }
    _write_json(output_dir / "manifest.json", manifest)
    _write_markdown(output_dir / "README.md", render_snapshot_index_markdown(manifest))
    return manifest


def render_publication_card_snapshot_markdown(snapshot: dict[str, Any]) -> str:
    dataset_profile = _dict_object(snapshot.get("dataset_profile"))
    lines = [
        "---",
        "type: publication_card_snapshot_preview",
        f"profile_id: {_yaml_value(snapshot.get('profile_id', ''))}",
        f"card_snapshot_id: {_yaml_value(snapshot.get('card_snapshot_id', ''))}",
        "review_status: \"preview-only\"",
        "publication_status: \"not_publishable_without_editorial_review\"",
        "preview_only: true",
        "---",
        "",
        f"# Snapshot scheda - {snapshot.get('canonical_name') or snapshot.get('profile_id', '')}",
        "",
        "Snapshot tecnico preview-only. Non e' una scheda pubblicabile e non sostituisce revisione storica/editoriale.",
        "",
        "## Sintesi",
        "",
        f"- Profilo: `{snapshot.get('profile_id', '')}`",
        f"- Snapshot ID: `{snapshot.get('card_snapshot_id', '')}`",
        f"- Scheda modello sorgente: `{snapshot.get('source_model_card_path', '')}`",
        f"- Hash scheda modello: `{snapshot.get('source_model_card_sha256', '')}`",
        f"- Dataset export preview: `{snapshot.get('source_dataset_export_preview_json', '')}`",
        f"- Hash dataset export: `{snapshot.get('source_dataset_export_sha256', '')}`",
        f"- Stato dataset profilo: `{dataset_profile.get('dataset_profile_status', '')}`",
        "",
        "## Provenance dataset",
        "",
        f"- Documenti: `{', '.join(_list_strings(dataset_profile.get('source_document_ids')))}`",
        f"- Decisioni review: `{len(_list_items(dataset_profile.get('review_decisions')))}`",
        f"- Fatti preview: `{len(_list_items(dataset_profile.get('verified_facts_preview')))}`",
        f"- ProfilePatch preview: `{len(_list_items(dataset_profile.get('profile_patch_preview')))}`",
        "",
    ]
    decisions = _list_items(dataset_profile.get("review_decisions"))
    if decisions:
        lines.extend(["### Decisioni", ""])
        for decision in decisions:
            lines.append(
                f"- `{decision.get('record_id', '')}` su `{decision.get('source_document_id', '')}`: "
                f"`{decision.get('selected_action', '')}` / `{decision.get('decision_status', '')}` "
                f"(hash `{decision.get('payload_hash', '')}`)"
            )
        lines.append("")
    facts = _list_items(dataset_profile.get("verified_facts_preview"))
    if facts:
        lines.extend(["### Fatti preview", ""])
        for fact in facts:
            lines.append(
                f"- `{fact.get('field', '')}`: {fact.get('value', '')} "
                f"(documento `{fact.get('source_document_id', '')}`, decisione `{fact.get('source_decision_record_id', '')}`)"
            )
        lines.append("")
    lines.extend(
        [
            "## Scheda modello congelata",
            "",
            str(snapshot.get("model_card_markdown", "")),
            "",
            "## Vincoli",
            "",
            "- Output automatico preview-only.",
            "- Non modifica profili JSON-LD.",
            "- Non applica ProfilePatch.",
            "- Non crea fatti canonici.",
            "- Non e' pubblicabile senza revisione editoriale.",
            "",
        ]
    )
    return "\n".join(lines)


def render_snapshot_index_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: publication_card_snapshot_preview_index",
        "review_status: \"preview-only\"",
        "publication_status: \"not_publishable_without_editorial_review\"",
        "preview_only: true",
        "---",
        "",
        "# PublicationCardSnapshot preview",
        "",
        "Indice preview-only degli snapshot schede. Non e' un pacchetto pubblicabile.",
        "",
        f"- Snapshot generati: `{manifest.get('snapshot_count', 0)}`",
        f"- Schede saltate: `{manifest.get('skipped_card_count', 0)}`",
        f"- Dataset export: `{manifest.get('source_dataset_export_preview_json', '')}`",
        "",
        "| Profilo | Stato dataset | Snapshot | JSON |",
        "|---|---|---|---|",
    ]
    for item in _list_items(manifest.get("snapshots")):
        lines.append(
            "| "
            f"`{item.get('profile_id', '')}` "
            f"| `{item.get('dataset_profile_status', '')}` "
            f"| `{item.get('snapshot_md_path', '')}` "
            f"| `{item.get('snapshot_json_path', '')}` |"
        )
    skipped = _list_items(manifest.get("skipped_cards"))
    if skipped:
        lines.extend(["", "## Schede saltate", ""])
        for item in skipped:
            lines.append(f"- `{item.get('profile_id', '')}`: {item.get('reason', '')} (`{item.get('model_card_path', '')}`)")
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Snapshot preview-only.",
            "- Nessuna pubblicazione.",
            "- Nessuna scrittura DB o modifica profili JSON-LD.",
            "",
        ]
    )
    return "\n".join(lines)


def _snapshot_payload(
    *,
    card: dict[str, Any],
    profile_id: str,
    canonical_name: str,
    generated_at: str,
    model_card_path: Path,
    model_card_sha256: str,
    dataset_export_preview_json: Path,
    dataset_export_sha256: str,
    dataset_profile: dict[str, Any],
    model_card_text: str,
) -> dict[str, Any]:
    snapshot_id = _snapshot_id(profile_id, model_card_sha256, dataset_export_sha256)
    return {
        "@type": "PublicationCardSnapshotPreview",
        "card_snapshot_id": snapshot_id,
        "generated_at": generated_at,
        "profile_id": profile_id,
        "canonical_name": canonical_name,
        "review_status": "preview-only",
        "publication_status": "not_publishable_without_editorial_review",
        "preview_only": True,
        "source_model_card_path": str(model_card_path),
        "source_model_card_sha256": model_card_sha256,
        "source_dataset_export_preview_json": str(dataset_export_preview_json),
        "source_dataset_export_sha256": dataset_export_sha256,
        "source_model_card_manifest_item": card,
        "dataset_profile": dataset_profile,
        "model_card_markdown": model_card_text,
        "safety_notes": [
            "Snapshot tecnico non pubblicabile.",
            "La scheda congelata resta derivata da output automatici e preview.",
            "Ogni pubblicazione richiede revisione storica/editoriale separata.",
        ],
    }


def _dataset_profile(dataset: dict[str, Any], *, profile_id: str) -> dict[str, Any]:
    person = next(
        (item for item in _list_items(dataset.get("persons")) if str(item.get("profile_id", "")).strip() == profile_id),
        {},
    )
    source_document_ids = _list_strings(person.get("source_document_ids")) if person else []
    documents = [
        document
        for document in _list_items(dataset.get("source_documents"))
        if str(document.get("source_document_id", "")).strip() in source_document_ids
        or profile_id in _list_strings(document.get("profile_ids"))
    ]
    decisions = [
        decision
        for decision in _list_items(dataset.get("review_decisions"))
        if str(decision.get("profile_id", "")).strip() == profile_id
    ]
    verified = _dict_object(dataset.get("verified_facts_preview"))
    facts = [
        fact
        for fact in _list_items(verified.get("facts"))
        if str(fact.get("profile_id", "")).strip() == profile_id
    ]
    patch = _dict_object(dataset.get("profile_patch_preview"))
    patches = [
        item
        for item in _list_items(patch.get("profile_patches"))
        if str(item.get("profile_id", "")).strip() == profile_id
    ]
    return {
        "dataset_profile_status": "available" if person else "missing",
        "profile_id": profile_id,
        "person": person,
        "source_document_ids": source_document_ids,
        "source_documents": documents,
        "review_decisions": decisions,
        "verified_facts_preview": facts,
        "profile_patch_preview": patches,
        "provenance": {
            "record_ids": _unique_non_empty(
                [
                    str(decision.get("record_id", ""))
                    for decision in decisions
                ]
                + [
                    str(fact.get("source_decision_record_id", ""))
                    for fact in facts
                ]
            ),
            "source_run_ids": _unique_non_empty(
                [
                    str(decision.get("source_run_id", ""))
                    for decision in decisions
                ]
                + [
                    str(fact.get("source_run_id", ""))
                    for fact in facts
                ]
            ),
            "payload_hashes": _unique_non_empty([str(decision.get("payload_hash", "")) for decision in decisions]),
        },
    }


def _manifest_snapshot_item(snapshot: dict[str, Any]) -> dict[str, Any]:
    dataset_profile = _dict_object(snapshot.get("dataset_profile"))
    return {
        "card_snapshot_id": snapshot.get("card_snapshot_id", ""),
        "profile_id": snapshot.get("profile_id", ""),
        "canonical_name": snapshot.get("canonical_name", ""),
        "dataset_profile_status": dataset_profile.get("dataset_profile_status", ""),
        "source_model_card_path": snapshot.get("source_model_card_path", ""),
        "source_model_card_sha256": snapshot.get("source_model_card_sha256", ""),
        "snapshot_json_path": snapshot.get("snapshot_json_path", ""),
        "snapshot_md_path": snapshot.get("snapshot_md_path", ""),
        "review_status": snapshot.get("review_status", "preview-only"),
        "publication_status": snapshot.get("publication_status", "not_publishable_without_editorial_review"),
    }


def _snapshot_id(profile_id: str, model_card_sha256: str, dataset_export_sha256: str) -> str:
    digest = hashlib.sha256(f"{profile_id}|{model_card_sha256}|{dataset_export_sha256}".encode("utf-8")).hexdigest()[:16]
    return f"publication-card-snapshot-preview:{slugify_identifier(profile_id)}:{digest}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_path(value: str, *, base_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def main() -> int:
    parser = argparse.ArgumentParser(description="Congela schede modello in PublicationCardSnapshot preview.")
    parser.add_argument("--model-cards-manifest-json", required=True)
    parser.add_argument("--dataset-export-preview-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    try:
        manifest = build_publication_card_snapshot_preview(
            model_cards_manifest_json=Path(args.model_cards_manifest_json),
            dataset_export_preview_json=Path(args.dataset_export_preview_json),
            output_dir=Path(args.output_dir),
            profile_id=args.profile_id,
            limit=args.limit,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc))
        return 2
    print(f"PublicationCardSnapshot preview: {manifest['output_dir']}")
    print(f"Snapshot generati: {manifest['snapshot_count']}")
    print(f"Schede saltate: {manifest['skipped_card_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
