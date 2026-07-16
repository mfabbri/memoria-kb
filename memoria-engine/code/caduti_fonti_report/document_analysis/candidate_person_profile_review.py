from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models import PersonResearchProfile, ProfileIdentity, ProfileSeed
from ..person_profiles import profile_id_from_name, write_profile, write_profile_index

ALLOWED_DECISIONS = {"accepted", "needs_review", "rejected"}


def build_candidate_person_profile_review(
    *,
    candidates_json: Path,
    output_dir: Path,
    decisions_json: Path | None = None,
    accepted_candidate_profile_ids: list[str] | None = None,
    limit: int = 0,
) -> dict[str, Any]:
    candidates_payload = _load_json_object(candidates_json)
    candidates = _candidate_items(candidates_payload)
    if limit > 0:
        candidates = candidates[:limit]

    output_dir.mkdir(parents=True, exist_ok=True)
    template_path = output_dir / "candidate_person_profile_review.template.json"
    if decisions_json is not None and _same_path(decisions_json, template_path):
        raise ValueError(
            "Il file decisioni compilato non puo' coincidere con "
            "candidate_person_profile_review.template.json: copiarlo prima in "
            "candidate_person_profile_review.compilato.json."
        )
    template = _review_template(candidates=candidates, candidates_json=candidates_json)
    template_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "candidate_person_profile_review_table.md").write_text(
        render_review_table(template),
        encoding="utf-8",
    )
    (output_dir / "candidate_person_profile_review_storico.md").write_text(
        render_historian_review_sheet(candidates=candidates, candidates_json=candidates_json),
        encoding="utf-8",
    )

    accepted_ids = _normalize_ids(accepted_candidate_profile_ids or [])
    decisions_source = "decisions_json" if decisions_json is not None else "accepted_candidate_profile_ids" if accepted_ids else ""
    decisions = _decision_map(decisions_json) if decisions_json is not None else _decision_map_from_accepted_ids(accepted_ids)
    accepted_profiles: list[PersonResearchProfile] = []
    decision_rows = []
    skipped_preview = []
    seen_profile_ids: set[str] = set()
    generated_at = datetime.now(UTC).isoformat()
    candidate_ids: set[str] = set()

    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_profile_id") or candidate.get("@id") or "")
        if candidate_id:
            candidate_ids.add(candidate_id)
        decision = decisions.get(candidate_id, {})
        decision_value = str(decision.get("decision", "needs_review")).strip() or "needs_review"
        if decision_value not in ALLOWED_DECISIONS:
            decision_value = "needs_review"
        row = {
            "candidate_profile_id": candidate_id,
            "suggested_profile_id": str(candidate.get("suggested_profile_id", "")),
            "canonical_name": str(candidate.get("canonical_name", "")),
            "decision": decision_value,
            "reviewer": str(decision.get("reviewer", "")),
            "note": str(decision.get("note", "")),
        }
        decision_rows.append(row)
        if decision_value != "accepted":
            continue
        profile = _profile_from_candidate(candidate, decision=decision, generated_at=generated_at)
        if profile.profile_id in seen_profile_ids:
            skipped_preview.append(
                {
                    "candidate_profile_id": candidate_id,
                    "profile_id": profile.profile_id,
                    "reason": "duplicate_profile_id",
                }
            )
            continue
        seen_profile_ids.add(profile.profile_id)
        accepted_profiles.append(profile)

    preview_dir = output_dir / "preview_person_profiles"
    profile_paths = [write_profile(profile, preview_dir) for profile in accepted_profiles]
    index_path = write_profile_index(accepted_profiles, preview_dir)

    summary = {
        "@type": "CandidatePersonProfileReviewSummary",
        "generated_at": generated_at,
        "candidates_json": str(candidates_json),
        "decisions_json": str(decisions_json) if decisions_json is not None else "",
        "decisions_source": decisions_source,
        "accepted_candidate_profile_ids": accepted_ids,
        "ignored_accepted_candidate_profile_ids": accepted_ids if decisions_json is not None else [],
        "unknown_accepted_candidate_profile_ids": sorted(set(accepted_ids) - candidate_ids) if decisions_json is None else [],
        "candidate_count": len(candidates),
        "decision_count": len(decisions),
        "accepted_count": sum(1 for row in decision_rows if row["decision"] == "accepted"),
        "needs_review_count": sum(1 for row in decision_rows if row["decision"] == "needs_review"),
        "rejected_count": sum(1 for row in decision_rows if row["decision"] == "rejected"),
        "preview_profile_count": len(accepted_profiles),
        "preview_profiles_index": str(index_path),
        "preview_profile_files": [str(path) for path in profile_paths],
        "skipped_preview_profiles": skipped_preview,
        "decisions": decision_rows,
    }
    (output_dir / "candidate_person_profile_review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "candidate_person_profile_review_summary.md").write_text(
        render_review_summary(summary),
        encoding="utf-8",
    )
    return summary


def render_review_table(template: dict[str, Any]) -> str:
    decisions = _list_items(template.get("decisions"))
    lines = [
        "# CandidatePersonProfile review",
        "",
        f"- Candidati: `{len(decisions)}`",
        f"- Sorgente candidati: `{template.get('candidates_json', '')}`",
        "",
        "| Decisione | Nome | Profilo suggerito | Documento | Riga | Nascita | Morte | Nota |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    if not decisions:
        lines.append("|  | _Nessun candidato_ |  |  |  |  |  |  |")
    for item in decisions:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(item.get("decision", "")),
                    _md_cell(item.get("canonical_name", "")),
                    f"`{_md_cell(item.get('suggested_profile_id', ''))}`",
                    f"`{_md_cell(item.get('source_document_id', ''))}`",
                    _md_cell(item.get("row_number", "")),
                    _md_cell(item.get("birth", "")),
                    _md_cell(item.get("death", "")),
                    _md_cell(item.get("note", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Come compilare",
            "",
            "- Usare `accepted` solo per candidati da trasformare in profili preview.",
            "- Usare `needs_review` per omonimie, dati dubbi o candidati incompleti.",
            "- Usare `rejected` per righe non pertinenti.",
            "- Compilare il JSON template, non questa tabella, per la fase successiva.",
            "",
        ]
    )
    return "\n".join(lines)


def render_historian_review_sheet(*, candidates: list[dict[str, Any]], candidates_json: Path | str = "") -> str:
    lines = [
        "# Scheda di revisione storica",
        "",
        "Questo foglio serve a decidere se un riferimento trovato nei documenti puo' diventare una scheda provvisoria da rivedere.",
        "Non pubblica nulla e non modifica i profili esistenti.",
        "",
        f"- Candidati da controllare: `{len(candidates)}`",
        f"- Sorgente tecnica: `{candidates_json}`",
        "- Stato: `bozza per revisione umana`",
        "",
        "## Come lavorare",
        "",
        "Per ogni persona scegliere una sola opzione:",
        "",
        "- [ ] Si, preparare una scheda provvisoria",
        "- [ ] No, non riguarda la persona o il riferimento e' troppo debole",
        "- [ ] Da approfondire prima di decidere",
        "",
        "Aggiungere una nota breve spiegando il motivo della scelta.",
        "",
    ]
    if not candidates:
        lines.append("_Nessun candidato da revisionare._")
        return "\n".join(lines) + "\n"

    for index, candidate in enumerate(candidates, start=1):
        canonical_name = str(candidate.get("canonical_name", "")).strip()
        suggested_profile_id = str(candidate.get("suggested_profile_id", "")).strip()
        source_document_id = str(candidate.get("source_document_id", "")).strip()
        raw_file = str(candidate.get("raw_file", "")).strip()
        row_fields = candidate.get("row_fields") if isinstance(candidate.get("row_fields"), dict) else {}
        context = _display_text(str(row_fields.get("mention_context") or row_fields.get("nome") or "").strip())
        mention_value = _display_text(str(row_fields.get("mention_value", "")).strip())
        weak_segment_id = str(row_fields.get("weak_segment_id", "")).strip()
        candidate_id = str(candidate.get("candidate_profile_id") or candidate.get("@id") or "").strip()

        lines.extend(
            [
                f"## {index}. {canonical_name or '_Nome non disponibile_'}",
                "",
                f"- Documento: `{source_document_id}`",
                f"- File di origine: `{raw_file}`",
                f"- Scheda provvisoria proposta: `{suggested_profile_id}`",
                f"- Riferimento tecnico: `{candidate_id}`",
                "",
                "### Estratto da controllare",
                "",
                context or "_Nessun estratto disponibile._",
                "",
                "### Che cosa e' stato riconosciuto",
                "",
                f"- Nome riconosciuto nel testo: {mention_value or canonical_name or '_non disponibile_'}",
                f"- Segmento di lavoro: `{weak_segment_id}`",
                "",
                "### Decisione dello storico",
                "",
                "- [ ] Si, preparare una scheda provvisoria",
                "- [ ] No, non riguarda la persona o il riferimento e' troppo debole",
                "- [ ] Da approfondire prima di decidere",
                "",
                "Nome del revisore:",
                "",
                "Nota:",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)


def render_review_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# CandidatePersonProfile review summary",
        "",
        f"- Candidati: `{summary.get('candidate_count', 0)}`",
        f"- Decisioni lette: `{summary.get('decision_count', 0)}`",
        f"- Accettati: `{summary.get('accepted_count', 0)}`",
        f"- Da rivedere: `{summary.get('needs_review_count', 0)}`",
        f"- Respinti: `{summary.get('rejected_count', 0)}`",
        f"- Profili preview generati: `{summary.get('preview_profile_count', 0)}`",
        f"- Indice preview: `{summary.get('preview_profiles_index', '')}`",
        f"- Sorgente decisioni: `{summary.get('decisions_source', '')}`",
        "",
        "## Decisioni",
        "",
        "| Decisione | Nome | Profilo suggerito | Revisore | Nota |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in _list_items(summary.get("decisions")):
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(item.get("decision", "")),
                    _md_cell(item.get("canonical_name", "")),
                    f"`{_md_cell(item.get('suggested_profile_id', ''))}`",
                    _md_cell(item.get("reviewer", "")),
                    _md_cell(item.get("note", "")),
                ]
            )
            + " |"
        )
    if not _list_items(summary.get("decisions")):
        lines.append("|  | _Nessuna decisione_ |  |  |  |")
    unknown_ids = _list_items(summary.get("unknown_accepted_candidate_profile_ids"))
    if unknown_ids:
        lines.extend(["", "## Accepted candidate id non trovati", ""])
        for candidate_id in unknown_ids:
            lines.append(f"- `{_md_cell(candidate_id)}`")
    return "\n".join(lines) + "\n"


def _review_template(*, candidates: list[dict[str, Any]], candidates_json: Path) -> dict[str, Any]:
    return {
        "@type": "CandidatePersonProfileReviewDecisionSet",
        "candidates_json": str(candidates_json),
        "decision_values": sorted(ALLOWED_DECISIONS),
        "decisions": [_decision_template_item(candidate) for candidate in candidates],
    }


def _decision_template_item(candidate: dict[str, Any]) -> dict[str, Any]:
    birth = candidate.get("birth") if isinstance(candidate.get("birth"), dict) else {}
    death = candidate.get("death") if isinstance(candidate.get("death"), dict) else {}
    return {
        "candidate_profile_id": str(candidate.get("candidate_profile_id") or candidate.get("@id") or ""),
        "suggested_profile_id": str(candidate.get("suggested_profile_id", "")),
        "canonical_name": str(candidate.get("canonical_name", "")),
        "corrected_canonical_name": "",
        "decision": "needs_review",
        "reviewer": "",
        "note": "",
        "source_document_id": str(candidate.get("source_document_id", "")),
        "row_number": int(candidate.get("row_number", 0) or 0),
        "birth": str(birth.get("raw", "")),
        "death": str(death.get("raw", "")),
    }


def _profile_from_candidate(candidate: dict[str, Any], *, decision: dict[str, Any], generated_at: str) -> PersonResearchProfile:
    corrected_name = str(decision.get("corrected_canonical_name", "")).strip()
    canonical_name = corrected_name or str(candidate.get("canonical_name", "")).strip()
    candidate_id = str(candidate.get("candidate_profile_id") or candidate.get("@id") or "")
    identity_payload = candidate.get("identity") if isinstance(candidate.get("identity"), dict) else {}
    birth = candidate.get("birth") if isinstance(candidate.get("birth"), dict) else {}
    death = candidate.get("death") if isinstance(candidate.get("death"), dict) else {}
    row_fields = candidate.get("row_fields") if isinstance(candidate.get("row_fields"), dict) else {}
    provenance = candidate.get("provenance") if isinstance(candidate.get("provenance"), dict) else {}
    profile_id = profile_id_from_name(canonical_name)
    return PersonResearchProfile(
        profile_id=profile_id,
        identity=ProfileIdentity(
            canonical_name=canonical_name,
            aliases=[],
            name_forms=_dedupe([canonical_name, *_string_list(identity_payload.get("name_forms"))]),
        ),
        seed=ProfileSeed(
            source="document_candidate_profile_review",
            source_id=candidate_id,
            imported_at=generated_at,
            payload={
                "candidate_profile_id": candidate_id,
                "source_document_id": str(candidate.get("source_document_id", "")),
                "text_path": str(candidate.get("text_path", "")),
                "raw_file": str(candidate.get("raw_file", "")),
                "row_number": str(candidate.get("row_number", "")),
                "review_decision": str(decision.get("decision", "")),
                "reviewer": str(decision.get("reviewer", "")),
                "review_note": str(decision.get("note", "")),
                **{str(key): str(value) for key, value in row_fields.items()},
            },
        ),
        birth={"raw": str(birth.get("raw", ""))} if str(birth.get("raw", "")).strip() else {},
        death={"raw": str(death.get("raw", ""))} if str(death.get("raw", "")).strip() else {},
        formations=_string_list(candidate.get("formations")),
        places=_string_list(candidate.get("places")),
        metadata={
            "model_version": "person_research_profile.v1",
            "profile_status": "preview",
            "review_status": "candidate",
            "generated_from": "CandidatePersonProfile",
            "source_candidate_profile_id": candidate_id,
            "source_document_id": str(candidate.get("source_document_id", "")),
            "document_text_path": str(provenance.get("document_text_path", "")),
        },
    )


def _decision_map(decisions_json: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json_object_strict(decisions_json, label="decisioni review CandidatePersonProfile")
    decisions: dict[str, dict[str, Any]] = {}
    for item in _list_items(payload.get("decisions")):
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_profile_id", "")).strip()
        if candidate_id:
            decisions[candidate_id] = item
    return decisions


def _decision_map_from_accepted_ids(accepted_ids: list[str]) -> dict[str, dict[str, Any]]:
    return {
        candidate_id: {
            "candidate_profile_id": candidate_id,
            "decision": "accepted",
            "reviewer": "inline_accepted_candidate_profile_id",
            "note": "Accepted via CLI parameter.",
        }
        for candidate_id in accepted_ids
    }


def _candidate_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _list_items(payload.get("candidate_person_profiles")) if isinstance(item, dict)]


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_object_strict(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Impossibile leggere {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON non valido in {label}: {path} ({exc})") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Il file {label} deve contenere un oggetto JSON: {path}")
    return payload


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.absolute() == right.absolute()


def _list_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else []


def _normalize_ids(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        for part in str(raw_value).split(","):
            value = part.strip().strip('"').strip("'").strip()
            if value and value not in seen:
                seen.add(value)
                normalized.append(value)
    return normalized


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        clean = str(value).strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _display_text(value: str) -> str:
    replacements = {
        "â€œ": '"',
        "â€": '"',
        "â€™": "'",
        "â€˜": "'",
        "Âª": "a",
    }
    text = value
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera review e profili JSON-LD preview da CandidatePersonProfile documentali.")
    parser.add_argument("--candidates-json", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decisions-json", default="")
    parser.add_argument("--accepted-candidate-profile-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    summary = build_candidate_person_profile_review(
        candidates_json=Path(args.candidates_json),
        output_dir=Path(args.output_dir),
        decisions_json=Path(args.decisions_json) if args.decisions_json else None,
        accepted_candidate_profile_ids=args.accepted_candidate_profile_id,
        limit=args.limit,
    )
    print(f"Review table: {Path(args.output_dir) / 'candidate_person_profile_review_table.md'}")
    print(f"Decision template: {Path(args.output_dir) / 'candidate_person_profile_review.template.json'}")
    if args.decisions_json:
        print(f"Decision file: {Path(args.decisions_json)}")
        print(f"Decisioni lette: {summary['decision_count']}")
        print(f"Decisioni accepted: {summary['accepted_count']}")
    elif args.accepted_candidate_profile_id:
        print(f"Accepted candidate profile ids: {len(summary['accepted_candidate_profile_ids'])}")
        print(f"Decisioni accepted: {summary['accepted_count']}")
        if summary["unknown_accepted_candidate_profile_ids"]:
            print(f"Accepted candidate profile ids sconosciuti: {len(summary['unknown_accepted_candidate_profile_ids'])}")
    print(f"Summary: {Path(args.output_dir) / 'candidate_person_profile_review_summary.md'}")
    print(f"Profili preview: {summary['preview_profile_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
