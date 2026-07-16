from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..raw_store import slugify_identifier


def build_mvp_model_cards(
    *,
    digest_json: Path,
    summary_json: Path,
    review_session_json: Path,
    output_dir: Path,
    funding_excerpts_dir: Path | None = None,
    verified_facts_preview_json: Path | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    digest = _load_json_object(digest_json)
    summary = _load_json_object(summary_json)
    review_session = _load_json_object(review_session_json)
    verified_facts_by_profile = _verified_fact_previews_by_profile(
        _load_json_object(verified_facts_preview_json) if verified_facts_preview_json else {}
    )
    session_by_profile = {
        str(item.get("profile_id", "")): item
        for item in _list_items(review_session.get("profiles"))
        if str(item.get("profile_id", ""))
    }
    summary_profiles = {
        str(item.get("profile_id", "")): item
        for item in _list_items(summary.get("profiles"))
        if str(item.get("profile_id", ""))
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    if funding_excerpts_dir is not None:
        funding_excerpts_dir.mkdir(parents=True, exist_ok=True)

    cards = []
    for card in _list_items(digest.get("cards"))[: max(limit, 0) or None]:
        profile_id = str(card.get("profile_id", ""))
        canonical_name = str(card.get("canonical_name") or profile_id)
        slug = slugify_identifier(canonical_name or profile_id)
        session_profile = session_by_profile.get(profile_id, {})
        summary_profile = summary_profiles.get(profile_id, {})
        model_card = _model_card_payload(
            card=card,
            summary_profile=summary_profile,
            session_profile=session_profile,
            verified_fact_previews=verified_facts_by_profile.get(profile_id, []),
            output_path=output_dir / f"{slug}.md",
        )
        model_card["output_path"].write_text(render_mvp_model_card_markdown(model_card), encoding="utf-8")
        excerpt_path = ""
        if funding_excerpts_dir is not None:
            excerpt = _funding_excerpt_payload(model_card)
            path = funding_excerpts_dir / f"{slug}.md"
            path.write_text(render_funding_excerpt_markdown(excerpt), encoding="utf-8")
            excerpt_path = str(path)
        cards.append(
            {
                "profile_id": profile_id,
                "canonical_name": canonical_name,
                "model_card_path": str(model_card["output_path"]),
                "funding_excerpt_path": excerpt_path,
                "readiness_status": model_card["readiness_status"],
                "model_card_review_status": model_card["model_card_review_status"],
                "accepted_decision_count": model_card["accepted_decision_count"],
                "approved_decision_count": model_card["approved_decision_count"],
                "rejected_decision_count": model_card["rejected_decision_count"],
                "uncertain_decision_count": model_card["uncertain_decision_count"],
                "pending_decision_count": model_card["pending_decision_count"],
                "invalid_decision_count": model_card["invalid_decision_count"],
                "verified_fact_preview_count": model_card["verified_fact_preview_count"],
                "review_status": "unreviewed",
                "publication_status": "not_publishable_without_human_review",
            }
        )

    manifest = {
        "@type": "MvpModelCardsBuild",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "source_digest_json": str(digest_json),
        "source_summary_json": str(summary_json),
        "source_review_session_json": str(review_session_json),
        "source_verified_fact_preview_json": str(verified_facts_preview_json or ""),
        "output_dir": str(output_dir),
        "funding_excerpts_dir": str(funding_excerpts_dir or ""),
        "model_card_count": len(cards),
        "cards": cards,
        "warnings": [
            "Schede modello preview-only: non pubblicabili senza validazione storica e curatoriale.",
            "Nessun claim candidato viene promosso a fatto verificato.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "README.md").write_text(render_model_cards_index_markdown(manifest), encoding="utf-8")
    return manifest


def render_mvp_model_card_markdown(card: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_model_card",
        f"profile_id: {_yaml_value(card.get('profile_id', ''))}",
        f"canonical_name: {_yaml_value(card.get('canonical_name', ''))}",
        "review_status: \"unreviewed\"",
        "publication_status: \"not_publishable_without_human_review\"",
        "output_policy: \"preview-only\"",
        "---",
        "",
        f"# {card.get('canonical_name') or card.get('profile_id', '')}",
        "",
        "**Bozza di revisione - non pubblicabile senza validazione storica.**",
        "",
        "Questa scheda modello deriva da output automatici gia' generati nella run MVP. Serve a orientare revisione e finanziamento, non a pubblicare una biografia.",
        "",
        "## Identita operativa",
        "",
        f"- ProfileId: `{card.get('profile_id', '')}`",
        f"- Nome operativo: {card.get('canonical_name', '')}",
        f"- Readiness automatica: `{card.get('readiness_status', '')}`",
        f"- Stato scheda modello: `{card.get('model_card_review_status', '')}`",
        f"- Stato sessione review: `{card.get('review_session_status', '')}`",
        "",
        "## Dati seed non pubblicabili senza fonte",
        "",
    ]
    seed_fields = _list_strings(card.get("seed_fields"))
    if seed_fields:
        lines.extend(f"- {item}" for item in seed_fields)
    else:
        lines.append("- Nessun campo seed viene ripubblicato da questo output; usare il profilo JSON-LD solo come memoria di ricerca.")
    lines.extend(["", "## Documenti collegati", ""])
    documents = _list_items(card.get("top_documents"))
    if documents:
        for document in documents:
            lines.append(f"- `{document.get('source_document_id', '')}` - {document.get('title', '')}")
    else:
        lines.append("- Nessun documento principale nel digest.")
    lines.extend(["", "## Fatti preview", ""])
    facts = _list_items(card.get("verified_fact_previews"))
    if facts:
        for fact in facts:
            lines.append(
                f"- `{fact.get('field', '')}`: {fact.get('value', '')} "
                f"(documento `{fact.get('source_document_id', '')}`, decisione `{fact.get('source_decision_record_id', '')}`, "
                f"review `{fact.get('review_status', '')}`, revisore `{fact.get('reviewer', '')}`, data `{fact.get('reviewed_at', '')}`)"
            )
    else:
        lines.append("- Nessun fatto preview per questo profilo.")
    lines.append("- Sezione preview-only: non scrive profili e non crea fatti verificati canonici.")
    lines.extend(["", "## Evidenze candidate", ""])
    claims = _list_items(card.get("top_claims"))
    if claims:
        for claim in claims:
            lines.append(
                f"- `{claim.get('field', '')}`: {claim.get('value', '')} "
                f"(documento `{claim.get('source_document_id', '')}`, review `{claim.get('review_status', 'unreviewed')}`)"
            )
    else:
        lines.append("- Nessun claim candidato.")
    lines.extend(["", "## Piste documentali senza claim", ""])
    signals = _list_items(card.get("top_signals"))
    if signals:
        for signal in signals:
            lines.append(
                f"- `{signal.get('signal_type', '')}` su `{signal.get('source_document_id', '')}`: "
                f"{signal.get('summary', '')} (review `{signal.get('review_status', 'unreviewed')}`)"
            )
    else:
        lines.append("- Nessuna pista documentale aggiuntiva.")
    lines.extend(
        [
            "",
            "## Decisioni storiche",
            "",
            f"- Decisioni accettate: `{card.get('accepted_decision_count', 0)}`",
            f"- Decisioni approvate: `{card.get('approved_decision_count', 0)}`",
            f"- Decisioni respinte: `{card.get('rejected_decision_count', 0)}`",
            f"- Decisioni incerte o conflittuali: `{card.get('uncertain_decision_count', 0)}`",
            f"- Decisioni pending: `{card.get('pending_decision_count', 0)}`",
            f"- Decisioni invalide: `{card.get('invalid_decision_count', 0)}`",
            "- Le decisioni sono contesto di revisione: non promuovono claim candidati a fatti verificati.",
            "",
            "## Incertezze e warning",
            "",
            f"- Vincolo pubblicazione: {card.get('publication_constraint', '')}",
            "",
            "## Stato revisione",
            "",
            f"- Review status: `unreviewed`",
            f"- Publication status: `not_publishable_without_human_review`",
            f"- Scheda candidata nel vault: `{card.get('candidate_card_path', '')}`",
            "",
            "## Prossima azione",
            "",
            f"{card.get('next_action', '') or 'Completare la revisione storica degli item associati al profilo.'}",
            "",
            "## Testo divulgativo",
            "",
            "_Non generato automaticamente: mancano decisioni storiche validate. Questa sezione va compilata solo dopo revisione umana._",
            "",
            "## Vincoli",
            "",
            "- Non modifica profili JSON-LD.",
            "- Non crea patch profilo.",
            "- Non crea fatti verificati.",
            "- Non trasforma claim candidati in fatti storici.",
            "",
        ]
    )
    return "\n".join(lines)


def render_funding_excerpt_markdown(excerpt: dict[str, Any]) -> str:
    return "\n".join(
        [
            "---",
            "type: mvp_funding_excerpt",
            f"profile_id: {_yaml_value(excerpt.get('profile_id', ''))}",
            "review_status: \"unreviewed\"",
            "publication_status: \"not_publishable_without_human_review\"",
            "---",
            "",
            f"# Estratto finanziatore - {excerpt.get('canonical_name', '')}",
            "",
            "**Preview-only: esempio di dossier revisionabile, non biografia pubblicabile.**",
            "",
            f"- Stato: `{excerpt.get('readiness_status', '')}` / `{excerpt.get('model_card_review_status', '')}`",
            f"- Documenti collegati nel digest: `{excerpt.get('document_count', 0)}`",
            f"- Link documento-persona candidati: `{excerpt.get('candidate_document_person_link_count', 0)}`",
            f"- Claim candidati: `{excerpt.get('candidate_evidence_claim_count', 0)}`",
            f"- Fatti preview: `{excerpt.get('verified_fact_preview_count', 0)}`",
            f"- Piste documentali: `{excerpt.get('reviewable_document_signal_count', 0)}`",
            f"- Decisioni storiche: accettate `{excerpt.get('accepted_decision_count', 0)}`, respinte `{excerpt.get('rejected_decision_count', 0)}`, incerte `{excerpt.get('uncertain_decision_count', 0)}`, pending `{excerpt.get('pending_decision_count', 0)}`",
            f"- Prossima azione: {excerpt.get('next_action', '')}",
            "",
            "Valore dimostrativo: mostra come Me.Mo.Ri.a raccoglie documenti, segnali e decisioni da sottoporre a revisione umana.",
            "",
        ]
    )


def render_model_cards_index_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_model_cards_index",
        "review_status: \"unreviewed\"",
        "publication_status: \"not_publishable_without_human_review\"",
        "---",
        "",
        "# Schede modello MVP",
        "",
        "Indice preview-only delle schede modello generate per revisione e finanziamento.",
        "",
        f"- Schede generate: `{manifest.get('model_card_count', 0)}`",
        f"- Digest sorgente: `{manifest.get('source_digest_json', '')}`",
        f"- Review session sorgente: `{manifest.get('source_review_session_json', '')}`",
        "",
        "| Scheda | Stato | File | Estratto |",
        "|---|---|---|---|",
    ]
    for card in _list_items(manifest.get("cards")):
        lines.append(
            "| "
            f"{card.get('canonical_name', '')} "
            f"| `{card.get('model_card_review_status', '')}` "
            f"| `{card.get('model_card_path', '')}` "
            f"| `{card.get('funding_excerpt_path', '')}` |"
        )
    lines.extend(["", "## Vincoli", ""])
    lines.extend(f"- {warning}" for warning in _list_strings(manifest.get("warnings")))
    lines.append("")
    return "\n".join(lines)


def _model_card_payload(
    *,
    card: dict[str, Any],
    summary_profile: dict[str, Any],
    session_profile: dict[str, Any],
    verified_fact_previews: list[dict[str, Any]],
    output_path: Path,
) -> dict[str, Any]:
    fact_previews = [_verified_fact_preview_summary(fact) for fact in verified_fact_previews]
    return {
        "output_path": output_path,
        "profile_id": str(card.get("profile_id", "")),
        "canonical_name": str(card.get("canonical_name", "")),
        "readiness_status": str(card.get("readiness_status", "")),
        "model_card_review_status": str(session_profile.get("model_card_review_status", "candidate_model_card")),
        "review_session_status": str(session_profile.get("review_session_status", "not_started")),
        "document_count": _int_value(card.get("document_count")),
        "candidate_document_person_link_count": _int_value(card.get("candidate_document_person_link_count")),
        "candidate_evidence_claim_count": _int_value(card.get("candidate_evidence_claim_count")),
        "reviewable_document_signal_count": _int_value(card.get("reviewable_document_signal_count")),
        "accepted_decision_count": _int_value(session_profile.get("accepted_decision_count")),
        "approved_decision_count": _int_value(session_profile.get("approved_decision_count")),
        "rejected_decision_count": _int_value(session_profile.get("rejected_decision_count")),
        "uncertain_decision_count": _int_value(session_profile.get("uncertain_decision_count")),
        "pending_decision_count": _int_value(session_profile.get("pending_decision_count")),
        "invalid_decision_count": _int_value(session_profile.get("invalid_decision_count")),
        "decision_counts_by_action": _dict_int_counts(session_profile.get("decision_counts_by_action")),
        "decision_counts_by_status": _dict_int_counts(session_profile.get("decision_counts_by_status")),
        "publication_constraint": str(
            session_profile.get("publication_constraint")
            or "Non pubblicabile senza review curatoriale umana."
        ),
        "candidate_card_path": str(card.get("candidate_card_path", "")),
        "next_action": str(session_profile.get("next_action") or card.get("next_action") or ""),
        "top_documents": _list_items(card.get("top_documents")),
        "top_claims": _list_items(card.get("top_claims")),
        "top_signals": _list_items(card.get("top_signals")),
        "verified_fact_previews": fact_previews,
        "verified_fact_preview_count": len(fact_previews),
        "seed_fields": _seed_fields(summary_profile),
    }


def _funding_excerpt_payload(card: dict[str, Any]) -> dict[str, Any]:
    return {
        key: card.get(key)
        for key in [
            "profile_id",
            "canonical_name",
            "readiness_status",
            "model_card_review_status",
            "document_count",
            "candidate_document_person_link_count",
            "candidate_evidence_claim_count",
            "reviewable_document_signal_count",
            "verified_fact_preview_count",
            "accepted_decision_count",
            "approved_decision_count",
            "rejected_decision_count",
            "uncertain_decision_count",
            "pending_decision_count",
            "invalid_decision_count",
            "next_action",
        ]
    }


def _seed_fields(profile: dict[str, Any]) -> list[str]:
    seed = profile.get("seed")
    if not isinstance(seed, dict):
        return []
    fields = []
    for key in ["full_name", "given_name", "family_name", "birth_date", "death_date", "origin_place"]:
        value = seed.get(key)
        if value:
            fields.append(f"`{key}`: {value} (seed operativo, non fatto verificato)")
    return fields


def _verified_fact_previews_by_profile(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if str(payload.get("status", "")).lower() == "skipped":
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for fact in _list_items(payload.get("facts")):
        profile_id = str(fact.get("profile_id", "")).strip()
        if profile_id:
            grouped.setdefault(profile_id, []).append(fact)
    return grouped


def _verified_fact_preview_summary(fact: dict[str, Any]) -> dict[str, str]:
    return {
        "field": str(fact.get("field", "")),
        "value": str(fact.get("value", "")),
        "source_document_id": str(fact.get("source_document_id", "")),
        "source_decision_record_id": str(
            fact.get("source_decision_record_id")
            or fact.get("decision_record_id")
            or fact.get("record_id")
            or ""
        ),
        "reviewer": str(fact.get("reviewer", "")),
        "reviewed_at": str(fact.get("reviewed_at", "")),
        "review_status": str(fact.get("review_status", "preview-only")),
        "publication_status": str(fact.get("publication_status", "not_publishable_without_editorial_review")),
    }


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


def _dict_int_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _int_value(raw_value) for key, raw_value in sorted(value.items())}


def _yaml_value(value: object) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera schede modello MVP preview-only.")
    parser.add_argument("--digest-json", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--review-session-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--funding-excerpts-dir", default="")
    parser.add_argument("--verified-facts-preview-json", default="")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    manifest = build_mvp_model_cards(
        digest_json=Path(args.digest_json),
        summary_json=Path(args.summary_json),
        review_session_json=Path(args.review_session_json),
        output_dir=Path(args.output_dir),
        funding_excerpts_dir=Path(args.funding_excerpts_dir) if args.funding_excerpts_dir else None,
        verified_facts_preview_json=(
            Path(args.verified_facts_preview_json) if args.verified_facts_preview_json else None
        ),
        limit=args.limit,
    )
    print(f"Schede modello MVP: {manifest['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
