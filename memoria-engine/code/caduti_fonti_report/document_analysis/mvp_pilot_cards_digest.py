from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..raw_store import slugify_identifier


def build_mvp_pilot_cards_digest(
    *,
    summary_json: Path,
    vault_dir: Path,
    limit: int = 10,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    summary = _load_json_object(summary_json)
    profiles = _list_items(summary.get("profiles"))[: max(limit, 0) or None]
    readiness_by_profile = {
        str(item.get("profile_id", "")): item
        for item in _list_items(summary.get("profile_readiness"))
        if str(item.get("profile_id", ""))
    }
    links_by_profile = _items_by_profile(_list_items(summary.get("candidate_document_person_links")))
    claims_by_profile = _items_by_profile(_list_items(summary.get("candidate_evidence_claims")))
    signals_by_profile = {
        str(group.get("profile_id", "")): _list_items(group.get("signals"))
        for group in _list_items(summary.get("reviewable_document_signals"))
        if str(group.get("profile_id", ""))
    }
    documents_by_id = {
        str(document.get("source_document_id", "")): document
        for document in _list_items(summary.get("documents"))
        if str(document.get("source_document_id", ""))
    }

    cards = []
    for profile in profiles:
        profile_id = str(profile.get("profile_id", ""))
        canonical_name = str(profile.get("canonical_name") or profile_id)
        links = links_by_profile.get(profile_id, [])
        claims = claims_by_profile.get(profile_id, [])
        signals = signals_by_profile.get(profile_id, [])
        readiness = readiness_by_profile.get(profile_id, {})
        candidate_card_path = vault_dir / "40_Publication_Candidates" / f"{slugify_identifier(canonical_name or profile_id)}.md"
        cards.append(
            {
                "profile_id": profile_id,
                "canonical_name": canonical_name,
                "readiness_status": str(readiness.get("readiness_status", "")),
                "next_action": str(readiness.get("next_action", "")),
                "candidate_card_path": str(candidate_card_path),
                "candidate_card_exists": candidate_card_path.is_file(),
                "document_count": _int_value(readiness.get("document_count")),
                "candidate_document_person_link_count": len(links),
                "candidate_evidence_claim_count": len(claims),
                "reviewable_document_signal_count": len(signals),
                "top_documents": _top_documents(links=links, claims=claims, documents_by_id=documents_by_id),
                "top_claims": [_claim_summary(claim) for claim in claims[:3]],
                "top_signals": [_signal_summary(signal) for signal in signals[:3]],
                "review_status": "unreviewed",
                "publication_status": "not_publishable_without_curator_review",
            }
        )

    digest = {
        "@type": "MvpPilotCardsDigest",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_curator_review",
        "source_summary_json": str(summary_json),
        "source_vault_dir": str(vault_dir),
        "profile_count": len(cards),
        "ready_for_review_count": sum(1 for card in cards if card.get("readiness_status") == "ready_for_review"),
        "candidate_card_count": sum(1 for card in cards if card.get("candidate_card_exists")),
        "cards": cards,
        "warnings": _warnings(cards),
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_pilot_cards_digest_markdown(digest), encoding="utf-8")
    return digest


def render_mvp_pilot_cards_digest_markdown(digest: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_pilot_cards_digest",
        f"review_status: {_yaml_value(digest.get('review_status', 'unreviewed'))}",
        f"publication_status: {_yaml_value(digest.get('publication_status', 'not_publishable_without_curator_review'))}",
        "---",
        "",
        "# Digest schede pilota MVP",
        "",
        "Output preview-only per revisione e demo: non e' una pubblicazione storica.",
        "",
        "## Sintesi",
        "",
        f"- Profili nel digest: `{digest.get('profile_count', 0)}`",
        f"- Profili pronti per review: `{digest.get('ready_for_review_count', 0)}`",
        f"- Schede candidate presenti nel vault: `{digest.get('candidate_card_count', 0)}`",
        f"- Vault: `{digest.get('source_vault_dir', '')}`",
        "",
        "## Schede",
        "",
    ]
    cards = _list_items(digest.get("cards"))
    if not cards:
        lines.append("_Nessuna scheda pilota nel digest._")
    else:
        lines.extend(
            [
                "| Scheda | Stato | Documenti | Link | Claim | Piste | Prossima azione |",
                "|---|---|---:|---:|---:|---:|---|",
            ]
        )
        for card in cards:
            card_label = str(card.get("canonical_name") or card.get("profile_id", ""))
            if card.get("candidate_card_exists"):
                card_label = f"[{card_label}]({card.get('candidate_card_path', '')})"
            lines.append(
                "| "
                f"{card_label} "
                f"| `{card.get('readiness_status', '')}` "
                f"| {card.get('document_count', 0)} "
                f"| {card.get('candidate_document_person_link_count', 0)} "
                f"| {card.get('candidate_evidence_claim_count', 0)} "
                f"| {card.get('reviewable_document_signal_count', 0)} "
                f"| {card.get('next_action', '')} |"
            )
    for card in cards:
        lines.extend(["", f"## {card.get('canonical_name') or card.get('profile_id', '')}", ""])
        lines.append(f"- ProfileId: `{card.get('profile_id', '')}`")
        lines.append(f"- Stato: `{card.get('readiness_status', '')}`")
        lines.append(f"- Scheda candidata: `{card.get('candidate_card_path', '')}`")
        lines.append(f"- Presente nel vault: `{'si' if card.get('candidate_card_exists') else 'no'}`")
        lines.append(f"- Prossima azione: {card.get('next_action', '')}")
        lines.extend(["", "Documenti principali:"])
        documents = _list_items(card.get("top_documents"))
        if documents:
            for document in documents:
                lines.append(f"- `{document.get('source_document_id', '')}` - {document.get('title', '')}")
        else:
            lines.append("- Nessun documento principale nel digest.")
        lines.extend(["", "Claim candidati principali:"])
        claims = _list_items(card.get("top_claims"))
        if claims:
            for claim in claims:
                lines.append(f"- `{claim.get('field', '')}`: {claim.get('value', '')} | documento `{claim.get('source_document_id', '')}`")
        else:
            lines.append("- Nessun claim candidato.")
        lines.extend(["", "Piste documentali principali:"])
        signals = _list_items(card.get("top_signals"))
        if signals:
            for signal in signals:
                lines.append(f"- `{signal.get('signal_type', '')}` su `{signal.get('source_document_id', '')}`: {signal.get('summary', '')}")
        else:
            lines.append("- Nessuna pista documentale aggiuntiva.")
    warnings = _list_strings(digest.get("warnings"))
    if warnings:
        lines.extend(["", "## Warning", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Il digest riassume output automatici gia' generati.",
            "- Non legge note editoriali Obsidian come fonte canonica.",
            "- Nessun claim candidato viene trattato come fatto storico.",
            "- Nessun profilo JSON-LD canonico viene modificato.",
            "",
        ]
    )
    return "\n".join(lines)


def _top_documents(
    *,
    links: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    documents_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    ordered_ids = []
    for item in [*claims, *links]:
        document_id = str(item.get("source_document_id", "")).strip()
        if document_id and document_id not in ordered_ids:
            ordered_ids.append(document_id)
    result = []
    for document_id in ordered_ids[:3]:
        document = documents_by_id.get(document_id, {})
        result.append(
            {
                "source_document_id": document_id,
                "title": str(document.get("title") or document.get("raw_file") or document_id),
            }
        )
    return result


def _claim_summary(claim: dict[str, Any]) -> dict[str, str]:
    return {
        "field": str(claim.get("field", "")),
        "value": str(claim.get("value", "")),
        "source_document_id": str(claim.get("source_document_id", "")),
        "review_status": str(claim.get("review_status", "unreviewed")) or "unreviewed",
    }


def _signal_summary(signal: dict[str, Any]) -> dict[str, str]:
    summary = str(signal.get("value") or signal.get("context") or "")
    if len(summary) > 180:
        summary = summary[:177].rstrip() + "..."
    return {
        "signal_type": str(signal.get("signal_type", "")),
        "source_document_id": str(signal.get("source_document_id", "")),
        "summary": summary,
        "review_status": str(signal.get("review_status", "unreviewed")) or "unreviewed",
    }


def _warnings(cards: list[dict[str, Any]]) -> list[str]:
    warnings = [
        "Digest preview-only: serve revisione storica e curatoriale prima della pubblicazione.",
    ]
    missing_cards = [card for card in cards if not card.get("candidate_card_exists")]
    if missing_cards:
        warnings.append(f"{len(missing_cards)} schede candidate non sono presenti nel vault.")
    if not any(card.get("readiness_status") == "ready_for_review" for card in cards):
        warnings.append("Nessuna scheda risulta ready_for_review: usare il digest per scegliere i blocchi da risolvere.")
    return warnings


def _items_by_profile(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        profile_id = str(item.get("profile_id") or item.get("person_candidate_id") or item.get("person_id") or "")
        if profile_id:
            grouped.setdefault(profile_id, []).append(item)
    return grouped


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _yaml_value(value: object) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera un digest delle schede pilota MVP.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--vault-dir", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args(argv)
    summary_json = Path(args.summary_json)
    output_json = Path(args.output_json) if args.output_json else summary_json.parent.parent / "mvp_pilot_cards_digest.json"
    output_md = Path(args.output_md) if args.output_md else summary_json.parent.parent / "mvp_pilot_cards_digest.md"
    build_mvp_pilot_cards_digest(
        summary_json=summary_json,
        vault_dir=Path(args.vault_dir),
        limit=args.limit,
        output_json=output_json,
        output_md=output_md,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
