from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .person_profiles import profile_from_jsonld


PROFILE_FIELD_PATHS = {
    "person.full_name": ("identity", "canonical_name"),
    "birth.date": ("birth", "date"),
    "death.date": ("death", "date"),
}

LIST_PROFILE_FIELDS = {
    "formation.name": "formations",
}

UPDATE_PATHS = {
    "person.full_name": "/identity/canonical_name",
    "birth.date": "/birth/date",
    "death.date": "/death/date",
    "death.cause": "/verified_facts/death.cause",
    "formation.name": "/formations/-",
    "occupation": "/verified_facts/occupation",
    "person.education": "/verified_facts/person.education",
}

REVIEW_BUCKETS = {
    "confirm_existing": "da_accettare_facilmente",
    "alternate_name_order": "da_accettare_facilmente",
    "new_fact": "da_accettare_facilmente",
    "refinement": "da_confrontare",
    "conflict_or_revision": "da_discutere",
}

MONTHS = {
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Strumenti preview-only per feedback loop profili.")
    subparsers = parser.add_subparsers(dest="command")

    updates_parser = subparsers.add_parser("updates", help="Genera CandidateProfileUpdate da un report profili.")
    updates_parser.add_argument("--report-json", default="")
    updates_parser.add_argument("--candidate-claims-json", default="")
    updates_parser.add_argument("--profile-jsonld", required=True)
    updates_parser.add_argument("--profiles-index", default="")
    updates_parser.add_argument("--output-jsonld", default="risultati/candidate_profile_updates.jsonld")
    updates_parser.add_argument("--output-md", default="risultati/candidate_profile_updates.md")

    patch_parser = subparsers.add_parser("patch", help="Genera ProfilePatch da ReviewDecision accettate.")
    patch_parser.add_argument("--candidate-updates-jsonld", required=True)
    patch_parser.add_argument("--decisions-json", required=True)
    patch_parser.add_argument("--output-json", default="risultati/profile_patch.json")
    patch_parser.add_argument("--output-md", default="risultati/profile_patch.md")
    args = parser.parse_args()

    if args.command in (None, "updates"):
        updates = build_candidate_profile_updates(
            report_json=Path(args.report_json) if args.report_json else None,
            candidate_claims_json=Path(args.candidate_claims_json) if args.candidate_claims_json else None,
            profile_jsonld=Path(args.profile_jsonld),
            profiles_index=Path(args.profiles_index) if args.profiles_index else None,
        )
        output_jsonld = Path(args.output_jsonld)
        output_md = Path(args.output_md)
        output_jsonld.parent.mkdir(parents=True, exist_ok=True)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_jsonld.write_text(json.dumps(updates, ensure_ascii=False, indent=2), encoding="utf-8")
        output_md.write_text(render_candidate_updates_markdown(updates), encoding="utf-8")

        print(f"CandidateProfileUpdate JSON-LD scritto in {output_jsonld}")
        print(f"Anteprima Markdown scritta in {output_md}")
        print(f"Proposte generate: {len(updates['candidate_updates'])}")
        print(f"CandidateNewProfile preview: {len(updates['candidate_new_profiles'])}")
        print(f"Profili collegati gia' esistenti: {len(updates.get('candidate_existing_profile_links', []))}")
        return 0

    patch = build_profile_patch(
        candidate_updates_jsonld=Path(args.candidate_updates_jsonld),
        decisions_json=Path(args.decisions_json),
    )
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_profile_patch_markdown(patch), encoding="utf-8")
    print(f"ProfilePatch JSON scritto in {output_json}")
    print(f"ProfilePatch Markdown scritto in {output_md}")
    print(f"Operazioni generate: {len(patch['operations'])}")
    return 0


def build_candidate_profile_updates(
    *,
    profile_jsonld: Path,
    report_json: Path | None = None,
    candidate_claims_json: Path | None = None,
    profiles_index: Path | None = None,
) -> dict[str, Any]:
    if report_json is None and candidate_claims_json is None:
        raise ValueError("Specificare report_json o candidate_claims_json.")
    report_payload = _load_json_object(report_json) if report_json is not None else {}
    candidate_claims_payload = _load_json_object(candidate_claims_json) if candidate_claims_json is not None else {}
    profile_payload = json.loads(profile_jsonld.read_text(encoding="utf-8"))
    profile = profile_from_jsonld(profile_payload)
    claims = [
        *_deduplicated_claims(report_payload, profile.profile_id),
        *_candidate_document_claims(candidate_claims_payload, profile.profile_id, input_path=candidate_claims_json),
    ]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        field = str(claim.get("field", "")).strip()
        value = str(claim.get("value", "")).strip()
        if not field or not value:
            continue
        grouped[(field, _normalize(value))].append(claim)

    generated_at = datetime.now(UTC).isoformat()
    candidate_updates = []
    for (field, _normalized_value), field_claims in sorted(grouped.items()):
        value = str(field_claims[0]["value"]).strip()
        current_values = _current_values_for_field(profile_payload, field)
        action, reason = _classify_action(field=field, current_values=current_values, candidate_value=value)
        candidate_updates.append(
            {
                "@type": "CandidateProfileUpdate",
                "@id": _candidate_update_id(profile.profile_id, field, value, field_claims),
                "profile_id": profile.profile_id,
                "profile_source_file": str(profile_jsonld),
                "field": field,
                "candidate_value": value,
                "current_values": current_values,
                "proposed_action": action,
                "classification_reason": reason,
                "review_bucket": REVIEW_BUCKETS.get(action, "da_discutere"),
                "review_status": "pending",
                "confidence": max(float(claim.get("confidence", 0.0) or 0.0) for claim in field_claims),
                "source_claim_ids": [str(claim.get("claim_id", "")).strip() for claim in field_claims],
                "source_document_ids": sorted(
                    {str(claim.get("source_document_id", "")).strip() for claim in field_claims if claim.get("source_document_id")}
                ),
                "source_urls": sorted({str(claim.get("source_url", "")).strip() for claim in field_claims if claim.get("source_url")}),
                "quotes": sorted({str(claim.get("quote", "")).strip() for claim in field_claims if claim.get("quote")}),
            }
        )

    existing_profiles = _load_profile_index_names(profiles_index, source_profile_id=profile.profile_id)
    candidate_new_profiles, candidate_existing_profile_links = _candidate_profiles_from_report(
        report_payload,
        profile.profile_id,
        existing_profiles=existing_profiles,
    )
    return {
        "@context": {
            "ca": "https://ca-di-malanca.local/ontology/",
            "CandidateProfileUpdate": "ca:CandidateProfileUpdate",
            "CandidateNewProfile": "ca:CandidateNewProfile",
            "CandidateExistingProfileLink": "ca:CandidateExistingProfileLink",
            "profile_id": "ca:profile_id",
            "field": "ca:field",
            "candidate_value": "ca:candidate_value",
            "review_status": "ca:review_status",
        },
        "@type": "CandidateProfileUpdateSet",
        "generated_at": generated_at,
        "input_report": str(report_json) if report_json is not None else "",
        "input_candidate_claims": str(candidate_claims_json) if candidate_claims_json is not None else "",
        "profiles_index": str(profiles_index) if profiles_index else "",
        "profile_id": profile.profile_id,
        "profile_source_file": str(profile_jsonld),
        "merge_policy": "preview_only_no_profile_write",
        "candidate_updates": candidate_updates,
        "candidate_new_profiles": candidate_new_profiles,
        "candidate_existing_profile_links": candidate_existing_profile_links,
    }


def render_candidate_updates_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CandidateProfileUpdate preview",
        "",
        f"- Profilo: `{payload['profile_id']}`",
        f"- Profilo sorgente: `{payload['profile_source_file']}`",
        f"- Report: `{payload['input_report']}`",
        f"- Claim documentali: `{payload.get('input_candidate_claims', '')}`",
        f"- Policy: `{payload['merge_policy']}`",
        f"- Proposte: `{len(payload['candidate_updates'])}`",
        f"- Nuovi profili candidati: `{len(payload.get('candidate_new_profiles', []))}`",
        f"- Persone collegate gia' in indice: `{len(payload.get('candidate_existing_profile_links', []))}`",
        "",
    ]

    sections = [
        ("da_accettare_facilmente", "Da accettare facilmente"),
        ("da_confrontare", "Da confrontare"),
        ("da_discutere", "Da discutere"),
    ]
    for bucket, title in sections:
        bucket_updates = [update for update in payload["candidate_updates"] if update.get("review_bucket") == bucket]
        lines.extend(["", f"## {title}", ""])
        if not bucket_updates:
            lines.extend(["Nessuna proposta.", ""])
            continue
        for update in bucket_updates:
            _append_update_markdown(lines, update)

    lines.extend(["", "## CandidateNewProfile preview", ""])
    candidate_new_profiles = payload.get("candidate_new_profiles", [])
    if not candidate_new_profiles:
        lines.extend(["Nessuna proposta.", ""])
    for candidate in candidate_new_profiles:
        lines.extend(
            [
                f"### {candidate['detected_name']}",
                "",
                f"- Relazione: `{candidate['relation_to_profile']}`",
                f"- Profilo suggerito: `{candidate['suggested_profile_id']}`",
                f"- Stato revisione: `{candidate['review_status']}`",
                f"- Documento: `{candidate['source_document_id']}`",
                f"- URL: {candidate['source_url']}",
                f"- Contesto: {candidate['context_quote']}",
                "",
            ]
        )
    lines.extend(["", "## Profili gia' presenti da collegare", ""])
    existing_links = payload.get("candidate_existing_profile_links", [])
    if not existing_links:
        lines.extend(["Nessuna proposta.", ""])
    for link in existing_links:
        lines.extend(
            [
                f"### {link['detected_name']}",
                "",
                f"- Profilo esistente: `{link['existing_profile_id']}`",
                f"- Relazione: `{link['relation_to_profile']}`",
                f"- Stato revisione: `{link['review_status']}`",
                f"- Documento: `{link['source_document_id']}`",
                f"- URL: {link['source_url']}",
                f"- Contesto: {link['context_quote']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_profile_patch(*, candidate_updates_jsonld: Path, decisions_json: Path) -> dict[str, Any]:
    updates_payload = json.loads(candidate_updates_jsonld.read_text(encoding="utf-8"))
    decisions_payload = json.loads(decisions_json.read_text(encoding="utf-8"))
    updates_by_id = {str(update.get("@id", "")): update for update in updates_payload.get("candidate_updates", [])}
    decisions = decisions_payload.get("review_decisions", decisions_payload if isinstance(decisions_payload, list) else [])
    operations = []
    accepted_decisions = []
    for decision in decisions:
        if str(decision.get("decision", "")).strip() != "accepted":
            continue
        update_id = str(decision.get("candidate_update_id", "")).strip()
        update = updates_by_id.get(update_id)
        if update is None:
            continue
        path = str(decision.get("target_path", "")).strip() or UPDATE_PATHS.get(str(update.get("field", "")), "")
        if not path:
            continue
        value = str(decision.get("target_value", "")).strip() or str(update.get("candidate_value", "")).strip()
        requested_op = str(decision.get("op", "")).strip()
        operation = {
            "op": requested_op if requested_op in {"add", "set", "replace"} else ("add" if path.endswith("/-") or "/verified_facts/" in path else "set"),
            "path": path,
            "value": value,
            "candidate_update_id": update_id,
            "source_claim_ids": update.get("source_claim_ids", []),
            "source_document_ids": update.get("source_document_ids", []),
            "note": str(decision.get("note", "")).strip(),
        }
        operations.append(operation)
        accepted_decisions.append(decision)

    return {
        "@type": "ProfilePatch",
        "generated_at": datetime.now(UTC).isoformat(),
        "profile_id": updates_payload.get("profile_id", ""),
        "profile_source_file": updates_payload.get("profile_source_file", ""),
        "source_candidate_updates": str(candidate_updates_jsonld),
        "source_decisions": str(decisions_json),
        "apply_policy": "requires_explicit_apply_profile_patch_command",
        "operations": operations,
        "accepted_decisions": accepted_decisions,
    }


def render_profile_patch_markdown(patch: dict[str, Any]) -> str:
    lines = [
        "# ProfilePatch preview",
        "",
        f"- Profilo: `{patch['profile_id']}`",
        f"- Profilo sorgente: `{patch['profile_source_file']}`",
        f"- Policy: `{patch['apply_policy']}`",
        f"- Operazioni: `{len(patch['operations'])}`",
        "",
        "## Operazioni",
        "",
    ]
    if not patch["operations"]:
        lines.extend(["Nessuna operazione generata.", ""])
    for operation in patch["operations"]:
        lines.extend(
            [
                f"### {operation['path']}",
                "",
                f"- Op: `{operation['op']}`",
                f"- Valore: {operation['value']}",
                f"- Candidate update: `{operation['candidate_update_id']}`",
                f"- Claim: {', '.join(f'`{claim_id}`' for claim_id in operation['source_claim_ids'] if claim_id)}",
                f"- Documenti: {', '.join(f'`{document_id}`' for document_id in operation['source_document_ids'] if document_id)}",
                f"- Nota: {operation['note'] or '(nessuna)'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _append_update_markdown(lines: list[str], update: dict[str, Any]) -> None:
    lines.extend(
        [
            f"### {update['field']}",
            "",
            f"- Azione proposta: `{update['proposed_action']}`",
            f"- Motivo: {update.get('classification_reason', '')}",
            f"- Stato revisione: `{update['review_status']}`",
            f"- Valore candidato: {update['candidate_value']}",
            f"- Valore attuale: {_format_current_values(update['current_values'])}",
            f"- Confidenza massima: {update['confidence']}",
            f"- Claim: {', '.join(f'`{claim_id}`' for claim_id in update['source_claim_ids'] if claim_id)}",
            f"- Documenti: {', '.join(f'`{document_id}`' for document_id in update['source_document_ids'] if document_id)}",
            f"- URL: {', '.join(update['source_urls'])}",
            "",
        ]
    )


def _deduplicated_claims(report_payload: dict[str, Any], profile_id: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    claims: list[dict[str, Any]] = []
    for profile_entry in report_payload.get("profiles", []):
        if str(profile_entry.get("profile_id", "")) != profile_id:
            continue
        for result_entry in profile_entry.get("results", []):
            for claim in result_entry.get("claims", []):
                claim_id = str(claim.get("claim_id", "")).strip()
                key = claim_id or "|".join(
                    [
                        str(claim.get("field", "")),
                        str(claim.get("value", "")),
                        str(claim.get("source_document_id", "")),
                    ]
                )
                if key in seen:
                    continue
                seen.add(key)
                claims.append(claim)
    return claims


def _candidate_document_claims(
    payload: dict[str, Any],
    profile_id: str,
    *,
    input_path: Path | None,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    if str(payload.get("@type", "")) != "CandidateEvidenceClaimSet":
        return claims
    for claim in payload.get("candidate_evidence_claims", []):
        if not isinstance(claim, dict):
            continue
        if str(claim.get("@type", "")) != "CandidateEvidenceClaim":
            continue
        if str(claim.get("review_status", "")) != "unreviewed":
            continue
        if str(claim.get("profile_id", "")).strip() != profile_id:
            continue
        document_id = str(claim.get("source_document_id", "")).strip()
        field = str(claim.get("field", "")).strip()
        value = str(claim.get("value", "")).strip()
        if not document_id or not field or not value:
            continue
        claims.append(
            {
                "claim_id": str(claim.get("@id", "")).strip(),
                "field": field,
                "value": value,
                "source_document_id": document_id,
                "source_url": str(claim.get("url", "")).strip(),
                "quote": str(claim.get("evidence_span") or claim.get("context") or "").strip(),
                "confidence": float(claim.get("confidence", 0.0) or 0.0),
                "profile_source_file": str(claim.get("profile_source_file", "")).strip(),
                "provenance": f"CandidateEvidenceClaimSet:{input_path}" if input_path is not None else "CandidateEvidenceClaimSet",
            }
        )
    return _deduplicate_flat_claims(claims)


def _deduplicate_flat_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for claim in claims:
        key = str(claim.get("claim_id", "")).strip() or "|".join(
            [
                str(claim.get("field", "")),
                str(claim.get("value", "")),
                str(claim.get("source_document_id", "")),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(claim)
    return deduped


def _load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _current_values_for_field(profile_payload: dict[str, Any], field: str) -> list[str]:
    if field in PROFILE_FIELD_PATHS:
        current: Any = profile_payload
        for part in PROFILE_FIELD_PATHS[field]:
            if not isinstance(current, dict):
                return []
            current = current.get(part, "")
        return [str(current).strip()] if str(current).strip() else []

    if field in LIST_PROFILE_FIELDS:
        values = profile_payload.get(LIST_PROFILE_FIELDS[field], [])
        if isinstance(values, list):
            return [str(value).strip() for value in values if str(value).strip()]
    return []


def _classify_action(*, field: str, current_values: list[str], candidate_value: str) -> tuple[str, str]:
    normalized_candidate = _normalize(candidate_value)
    normalized_current = [_normalize(value) for value in current_values]
    if normalized_candidate in normalized_current:
        return "confirm_existing", "Il valore candidato coincide con un valore strutturato gia' presente."
    if not current_values:
        return "new_fact", "Il profilo non contiene ancora un valore strutturato per questo campo."
    if field == "person.full_name" and any(_same_name_tokens(candidate_value, value) for value in current_values):
        return "alternate_name_order", "Il valore usa gli stessi token del nome in ordine diverso."
    if field.endswith(".date") and any(_compatible_partial_date(candidate_value, value) for value in current_values):
        return "refinement", "Il valore candidato e il valore attuale condividono una data compatibile, con granularita' diversa."
    if any(normalized_candidate in value or value in normalized_candidate for value in normalized_current):
        return "refinement", "Il valore candidato e' contenuto nel valore attuale, o viceversa."
    return "conflict_or_revision", "Il valore candidato non e' conciliabile automaticamente con il valore attuale."


def _candidate_profiles_from_report(
    report_payload: dict[str, Any],
    profile_id: str,
    *,
    existing_profiles: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    new_candidates: dict[str, dict[str, Any]] = {}
    existing_links: dict[str, dict[str, Any]] = {}
    for profile_entry in report_payload.get("profiles", []):
        if str(profile_entry.get("profile_id", "")) != profile_id:
            continue
        current_name = str(profile_entry.get("canonical_name", "")).strip()
        for result_entry in profile_entry.get("results", []):
            for document in result_entry.get("documents", []):
                raw_text = str(document.get("raw_text", ""))
                for detected_name, quote in _extract_related_person_names(raw_text, current_name=current_name):
                    key = _profile_name_key(detected_name)
                    if key in existing_profiles:
                        if key in existing_links:
                            continue
                        existing = existing_profiles[key]
                        existing_links[key] = {
                            "@type": "CandidateExistingProfileLink",
                            "@id": _candidate_existing_profile_link_id(profile_id, str(existing.get("profile_id", "")), str(document.get("document_id", ""))),
                            "source_profile_id": profile_id,
                            "existing_profile_id": str(existing.get("profile_id", "")),
                            "existing_profile_name": str(existing.get("canonical_name", "")),
                            "detected_name": detected_name,
                            "relation_to_profile": "mentioned_in_same_source_document",
                            "source_document_id": str(document.get("document_id", "")),
                            "source_url": str(document.get("url", "")),
                            "context_quote": quote,
                            "review_status": "pending",
                        }
                        continue
                    if key in new_candidates:
                        continue
                    new_candidates[key] = {
                        "@type": "CandidateNewProfile",
                        "@id": _candidate_new_profile_id(profile_id, detected_name, str(document.get("document_id", ""))),
                        "source_profile_id": profile_id,
                        "detected_name": detected_name,
                        "relation_to_profile": "mentioned_in_same_source_document",
                        "source_document_id": str(document.get("document_id", "")),
                        "source_url": str(document.get("url", "")),
                        "context_quote": quote,
                        "suggested_profile_id": f"person:candidate:{_slugify_name(detected_name)}",
                        "review_status": "pending",
                    }
    return (
        sorted(new_candidates.values(), key=lambda item: item["detected_name"]),
        sorted(existing_links.values(), key=lambda item: item["detected_name"]),
    )


def _load_profile_index_names(index_path: Path | None, *, source_profile_id: str) -> dict[str, dict[str, str]]:
    if index_path is None:
        return {}
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    existing: dict[str, dict[str, str]] = {}
    for item in payload.get("profiles", []):
        if not isinstance(item, dict):
            continue
        profile_id = str(item.get("@id", "")).strip()
        canonical_name = str(item.get("canonical_name", "")).strip()
        if not profile_id or not canonical_name or profile_id == source_profile_id:
            continue
        for key in _profile_name_keys(canonical_name):
            existing[key] = {"profile_id": profile_id, "canonical_name": canonical_name}
    return existing


def _profile_name_key(name: str) -> str:
    tokens = _normalize_for_compare(name).split()
    return " ".join(sorted(tokens))


def _profile_name_keys(name: str) -> set[str]:
    tokens = _normalize_for_compare(name).split()
    keys = {_profile_name_key(name)} if tokens else set()
    if len(tokens) >= 3 and len(tokens[0]) <= 6:
        keys.add(" ".join(sorted(tokens[1:])))
    return keys


def _extract_related_person_names(raw_text: str, *, current_name: str) -> list[tuple[str, str]]:
    names: list[tuple[str, str]] = []
    section_match = re.search(r"\bPersone\b(?P<section>.*?)(?:\bBibliografia\b|\bDocumenti\b|$)", raw_text, flags=re.S)
    if not section_match:
        return names
    section = section_match.group("section")
    for match in re.finditer(r"\b([A-Z][A-Za-zÀ-ÖØ-öø-ÿ']+)\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ']+)\b", section):
        first, second = match.group(1), match.group(2)
        if first in {"Tutti", "Bologna"} or second in {"Bologna", "Tutti"}:
            continue
        detected = f"{first} {second}"
        if _same_name_tokens(detected, current_name):
            continue
        quote = section[max(0, match.start() - 60) : min(len(section), match.end() + 60)].strip()
        names.append((detected, " ".join(quote.split())))
    return names


def _same_name_tokens(left: str, right: str) -> bool:
    left_tokens = sorted(_normalize_for_compare(left).split())
    right_tokens = sorted(_normalize_for_compare(right).split())
    return len(left_tokens) >= 2 and left_tokens == right_tokens


def _compatible_partial_date(candidate_value: str, current_value: str) -> bool:
    candidate_tokens = set(_normalize_for_compare(candidate_value).split())
    current_tokens = set(_normalize_for_compare(current_value).replace(",", " ").split())
    years = {token for token in candidate_tokens if re.fullmatch(r"\d{4}", token)}
    if years and not years.intersection(current_tokens):
        return False
    months = candidate_tokens.intersection(MONTHS)
    if months and not months.intersection(current_tokens):
        return False
    meaningful_tokens = years.union(months)
    if not meaningful_tokens:
        return False
    return meaningful_tokens.issubset(current_tokens)


def _candidate_update_id(profile_id: str, field: str, value: str, claims: list[dict[str, Any]]) -> str:
    claim_ids = "|".join(sorted(str(claim.get("claim_id", "")) for claim in claims))
    digest = hashlib.sha256(f"{profile_id}|{field}|{value}|{claim_ids}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-profile-update:{digest}"


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalize_for_compare(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.replace("ª", "a").replace("º", "o"))
    asciiish = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", asciiish.casefold()).strip()


def _slugify_name(value: str) -> str:
    return "-".join(token for token in _normalize_for_compare(value).split() if token) or "unknown"


def _candidate_new_profile_id(profile_id: str, detected_name: str, document_id: str) -> str:
    digest = hashlib.sha256(f"{profile_id}|{detected_name}|{document_id}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-new-profile:{digest}"


def _candidate_existing_profile_link_id(source_profile_id: str, existing_profile_id: str, document_id: str) -> str:
    digest = hashlib.sha256(f"{source_profile_id}|{existing_profile_id}|{document_id}".encode("utf-8")).hexdigest()[:16]
    return f"candidate-existing-profile-link:{digest}"


def _format_current_values(values: list[str]) -> str:
    if not values:
        return "(nessun valore strutturato nel profilo)"
    return "; ".join(values)


if __name__ == "__main__":
    raise SystemExit(main())
