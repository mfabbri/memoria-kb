from __future__ import annotations

from pathlib import Path

from .raw_store import slugify_identifier


AUTO_BEGIN = "<!-- BEGIN AUTO-GENERATED -->"
AUTO_END = "<!-- END AUTO-GENERATED -->"

def _mvp_person_markdown(
    *,
    profile: dict[str, object],
    profile_payload: dict[str, object],
    payload: dict[str, object],
    links: list[dict[str, object]],
    claims: list[dict[str, object]],
    signals: list[dict[str, object]],
    readiness: dict[str, object],
    review_session: dict[str, object],
) -> str:
    profile_id = str(profile.get("profile_id", ""))
    name = str(profile.get("canonical_name") or profile_id)
    lines = [
        "---",
        "type: mvp_pilot_person_review",
        f"profile_id: {_yaml_value(profile_id)}",
        f"name: {_yaml_value(name)}",
        f"review_status: {_yaml_value(payload.get('review_status', 'unreviewed'))}",
        f"publication_status: {_yaml_value(payload.get('publication_status', 'not_publishable_without_human_review'))}",
        "---",
        "",
        f"# {name}",
        "",
        AUTO_BEGIN,
        "",
        "## Stato MVP",
        "",
        f"- Profile ID: `{profile_id}`",
        f"- Stato revisione: `{payload.get('review_status', 'unreviewed')}`",
        f"- Pubblicabilita': `{payload.get('publication_status', '')}`",
        f"- Stato scheda pilota: `{readiness.get('readiness_status', 'needs_documents')}`",
        f"- Prossima azione: {readiness.get('next_action', 'Registrare o collegare almeno un documento revisionabile.')}",
        "",
        "## Stato review storica",
        "",
        f"- Stato sessione: `{review_session.get('session_status', 'not_started')}`",
        f"- Item review: `{review_session.get('item_count', 0)}`",
        f"- Accettati: `{review_session.get('accepted_count', 0)}`",
        f"- Pending: `{review_session.get('pending_count', 0)}`",
        f"- Invalidi: `{review_session.get('invalid_count', 0)}`",
        "",
        "## Profilo operativo JSON-LD",
        "",
        *_mvp_profile_context_lines(profile=profile, profile_payload=profile_payload),
        "",
        "## Documenti collegati candidati",
        "",
    ]
    if links:
        for link in links:
            document_id = str(link.get("source_document_id", ""))
            lines.append(f"- {_obsidian_link('02_Documenti', document_id)} | score={link.get('score', '')} | stato={link.get('review_status', '')}")
    else:
        lines.append("- Nessun link documento-persona candidato.")

    lines.extend(["", "## Claim candidati", ""])
    if claims:
        for claim in claims:
            lines.append(
                "- "
                f"`{claim.get('field', '')}` = {claim.get('value', '')} "
                f"| documento `{claim.get('source_document_id', '')}` "
                f"| stato={claim.get('review_status', '')}"
            )
    else:
        lines.append("- Nessun claim candidato.")

    lines.extend(["", "## Piste documentali da revisionare", ""])
    if signals:
        for signal in signals:
            lines.append(
                "- "
                f"`{signal.get('signal_type', '')}` | documento `{signal.get('source_document_id', '')}` "
                f"| stato={signal.get('review_status', '')}"
            )
            reasons = _json_string_list(signal.get("reasons"))
            if reasons:
                lines.append(f"  - Motivi: {', '.join(reasons)}")
            context = str(signal.get("context", "")).strip()
            if context:
                lines.append(f"  - Contesto: {context}")
    else:
        lines.append("- Nessuna pista documentale nel perimetro pilota.")

    lines.extend(
        [
            "",
            "## Avvertenze",
            "",
            "- Scheda di revisione, non scheda pubblicabile.",
            "- Nessun claim candidato e' promosso a fatto verificato.",
            "- I profili JSON-LD reali non vengono modificati da questo export.",
            "",
            AUTO_END,
        ]
    )
    return "\n".join(lines)


def _mvp_publication_candidate_markdown(
    *,
    profile: dict[str, object],
    profile_payload: dict[str, object],
    links: list[dict[str, object]],
    claims: list[dict[str, object]],
    signals: list[dict[str, object]],
    readiness: dict[str, object],
    review_session: dict[str, object],
    candidate_status: str,
) -> str:
    profile_id = str(profile.get("profile_id", ""))
    name = str(profile.get("canonical_name") or profile_id)
    lines = [
        "---",
        "type: publication_card_candidate",
        f"profile_id: {_yaml_value(profile_id)}",
        f"name: {_yaml_value(name)}",
        f"candidate_status: {_yaml_value(candidate_status)}",
        "publication_status: \"not_publishable_without_curator_review\"",
        "---",
        "",
        f"# Scheda candidata - {name}",
        "",
        AUTO_BEGIN,
        "",
        "## Stato candidatura",
        "",
        f"- Stato candidatura: `{candidate_status}`",
        f"- Scheda di revisione: {_obsidian_link('01_Persone', name)}",
        f"- Stato scheda pilota: `{readiness.get('readiness_status', 'needs_documents')}`",
        f"- Stato sessione storici: `{review_session.get('session_status', 'not_started')}`",
        f"- Item review: `{review_session.get('item_count', 0)}`",
        f"- Decisioni accettate: `{review_session.get('accepted_count', 0)}`",
        f"- Decisioni pending: `{review_session.get('pending_count', 0)}`",
        f"- Decisioni invalide: `{review_session.get('invalid_count', 0)}`",
        "",
        "## Profilo sintetico",
        "",
        *_mvp_publication_profile_lines(profile=profile, profile_payload=profile_payload),
        "",
        "## Documenti e fonti candidate",
        "",
    ]
    if links:
        for link in links:
            document_id = str(link.get("source_document_id", ""))
            lines.append(
                "- "
                f"{_obsidian_link('02_Documenti', document_id)} "
                f"| score={link.get('score', '')} "
                f"| stato={link.get('review_status', '')}"
            )
    else:
        lines.append("- Nessun documento candidato collegato.")

    lines.extend(["", "## Evidenze candidate", ""])
    if claims:
        for claim in claims:
            lines.append(
                "- "
                f"`{claim.get('field', '')}` = {claim.get('value', '')} "
                f"| documento `{claim.get('source_document_id', '')}` "
                f"| stato={claim.get('review_status', '')}"
            )
    else:
        lines.append("- Nessun claim candidato. Usare le piste documentali come lavoro di review, non come fatti.")

    lines.extend(["", "## Piste documentali", ""])
    if signals:
        for signal in signals:
            lines.append(
                "- "
                f"`{signal.get('signal_type', '')}` | documento `{signal.get('source_document_id', '')}` "
                f"| stato={signal.get('review_status', '')}"
            )
            context = str(signal.get("context", "")).strip()
            if context:
                lines.append(f"  - Contesto: {context}")
    else:
        lines.append("- Nessuna pista documentale nel perimetro pilota.")

    lines.extend(
        [
            "",
            "## Vincoli editoriali",
            "",
            "- Scheda candidata generata automaticamente per demo e revisione.",
            "- Nessun claim candidato e' trattato come fatto verificato.",
            "- Nessun profilo JSON-LD canonico viene modificato da questo export.",
            "- La scheda non e' una scheda museale definitiva.",
            "",
            AUTO_END,
        ]
    )
    return "\n".join(lines)


def _mvp_publication_profile_lines(*, profile: dict[str, object], profile_payload: dict[str, object]) -> list[str]:
    if not profile_payload:
        return [
            f"- Nome canonico: {profile.get('canonical_name') or profile.get('profile_id') or '(non indicato)'}",
            "- Profilo sorgente non disponibile nel summary MVP.",
        ]
    identity = _dict_object(profile_payload.get("identity"))
    birth = _dict_object(profile_payload.get("birth"))
    death = _dict_object(profile_payload.get("death"))
    seed = _dict_object(profile_payload.get("seed"))
    seed_payload = _dict_object(seed.get("payload"))
    lines = [
        f"- Nome canonico: {identity.get('canonical_name') or profile.get('canonical_name') or '(non indicato)'}",
        f"- Forme nome: {_format_list(_json_string_list(identity.get('name_forms')))}",
        f"- Nascita seed/indizio: {birth.get('date') or '(non indicata)'}",
        f"- Morte seed/indizio: {death.get('date') or '(non indicata)'}",
        f"- Formazioni seed/indizio: {_format_list(_json_string_list(profile_payload.get('formations')))}",
        f"- Luoghi seed/indizio: {_format_list(_json_string_list(profile_payload.get('places')))}",
    ]
    bio = str(seed_payload.get("profilo_biografico", "")).strip()
    if bio:
        lines.extend(["", "Sintesi seed non pubblicabile:", "", f"> {bio}"])
    return lines

def _mvp_profile_context_lines(*, profile: dict[str, object], profile_payload: dict[str, object]) -> list[str]:
    if not profile_payload:
        source_file = str(profile.get("profile_source_file", "")).strip()
        if source_file:
            return [f"- Profilo sorgente non leggibile: `{source_file}`"]
        return ["- Profilo sorgente non indicato nel summary MVP."]
    identity = _dict_object(profile_payload.get("identity"))
    seed = _dict_object(profile_payload.get("seed"))
    seed_payload = _dict_object(seed.get("payload"))
    birth = _dict_object(profile_payload.get("birth"))
    death = _dict_object(profile_payload.get("death"))
    lines = [
        f"- Profile source: `{profile.get('profile_source_file', '')}`",
        f"- Nome canonico: {identity.get('canonical_name') or profile.get('canonical_name') or '(non indicato)'}",
        f"- Forme nome: {_format_list(_json_string_list(identity.get('name_forms')))}",
        f"- Nascita seed/indizio: {birth.get('date') or '(non indicata)'}",
        f"- Morte seed/indizio: {death.get('date') or '(non indicata)'}",
        f"- Formazioni seed/indizio: {_format_list(_json_string_list(profile_payload.get('formations')))}",
        f"- Luoghi seed/indizio: {_format_list(_json_string_list(profile_payload.get('places')))}",
    ]
    events = _json_string_list(profile_payload.get("events"))
    if events:
        lines.append(f"- Evento seed/indizio: {events[0]}")
    fonti = str(seed_payload.get("fonti_richiamate", "")).strip()
    if fonti:
        lines.append(f"- Fonti richiamate dal seed: {fonti}")
    bio = str(seed_payload.get("profilo_biografico", "")).strip()
    if bio:
        lines.extend(["", "Sintesi seed non pubblicabile:", "", f"> {bio}"])
    hints = _json_object_list(profile_payload.get("search_hints"))
    if hints:
        lines.extend(["", "Search hints principali:"])
        for hint in hints[:5]:
            field = str(hint.get("field", ""))
            value = str(hint.get("value", ""))
            status = str(hint.get("review_status", "unreviewed"))
            provenance = str(hint.get("provenance", ""))
            lines.append(f"- `{field}`: {value} | stato={status} | provenance={provenance or '(non dichiarata)'}")
    lines.extend(
        [
            "",
            "- Nota: questa sezione usa seed e indizi operativi; non e' una biografia pubblicabile.",
        ]
    )
    return lines


def _mvp_document_markdown(*, document: dict[str, object], payload: dict[str, object]) -> str:
    document_id = str(document.get("source_document_id", ""))
    title = str(document.get("title") or document_id)
    lines = [
        "---",
        "type: mvp_pilot_document_review",
        f"source_document_id: {_yaml_value(document_id)}",
        f"review_status: {_yaml_value(document.get('review_status', payload.get('review_status', 'unreviewed')))}",
        "---",
        "",
        f"# {title}",
        "",
        AUTO_BEGIN,
        "",
        f"- Documento: `{document_id}`",
        f"- Classe: `{document.get('document_class', '')}`",
        f"- Stato qualita': `{document.get('quality_status', '')}`",
        f"- Stato revisione: `{document.get('review_status', payload.get('review_status', 'unreviewed'))}`",
        f"- Path qualita': `{document.get('quality_path', '')}`",
        "",
        AUTO_END,
    ]
    return "\n".join(lines)


def _mvp_evidence_markdown(
    *,
    payload: dict[str, object],
    claims: list[dict[str, object]],
    profiles: list[dict[str, object]],
) -> str:
    selected = {str(profile.get("profile_id", "")) for profile in profiles}
    selected_claims = [claim for claim in claims if _profile_id_from_item(claim) in selected]
    lines = [
        "---",
        "type: mvp_pilot_evidence_index",
        f"review_status: {_yaml_value(payload.get('review_status', 'unreviewed'))}",
        "---",
        "",
        "# Evidenze candidate MVP",
        "",
        AUTO_BEGIN,
        "",
    ]
    if selected_claims:
        for claim in selected_claims:
            lines.append(
                "- "
                f"`{claim.get('@id', '')}`: `{_profile_id_from_item(claim)}` | "
                f"{claim.get('field', '')} = {claim.get('value', '')} | "
                f"documento `{claim.get('source_document_id', '')}` | "
                f"stato={claim.get('review_status', '')}"
            )
    else:
        lines.append("Nessun claim candidato nel perimetro pilota esportato.")
    lines.extend(["", AUTO_END])
    return "\n".join(lines)


def _mvp_dashboard_markdown(
    *,
    payload: dict[str, object],
    profiles: list[dict[str, object]],
    readiness: dict[str, dict[str, object]],
    review_queue_md: Path | None = None,
    review_decisions_summary: Path | None = None,
    review_session: dict[str, object] | None = None,
    publication_candidates: list[dict[str, object]] | None = None,
) -> str:
    lines = [
        "---",
        "type: mvp_pilot_review_dashboard",
        f"review_status: {_yaml_value(payload.get('review_status', 'unreviewed'))}",
        "---",
        "",
        "# MVP Pilot Review",
        "",
        AUTO_BEGIN,
        "",
        "## Riepilogo",
        "",
        f"- Profili esportati: {len(profiles)}",
        f"- Documenti nel summary: {payload.get('document_count', 0)}",
        f"- Link candidati: {payload.get('candidate_document_person_link_count', 0)}",
        f"- Claim candidati: {payload.get('candidate_evidence_claim_count', 0)}",
        f"- Piste documentali revisionabili: {payload.get('reviewable_document_signal_count', 0)}",
        f"- Stato pubblicazione: `{payload.get('publication_status', '')}`",
        "",
        "## Scorecard pacchetto MVP",
        "",
    ]
    lines.extend(_mvp_pilot_package_scorecard_markdown(payload.get("pilot_package_scorecard")))
    lines.extend(
        [
            "",
            "## Schede pilota",
            "",
        ]
    )
    if profiles:
        for profile in profiles:
            name = str(profile.get("canonical_name") or profile.get("profile_id", ""))
            lines.append(f"- {_obsidian_link('01_Persone', name)}")
    else:
        lines.append("- Nessuna scheda pilota esportata.")

    lines.extend(
        [
            "",
            "## Stato schede pilota",
            "",
            "| Profilo | Documenti | Link | Claim | Piste | Stato | Prossima azione |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
    )
    if profiles:
        for profile in profiles:
            profile_id = str(profile.get("profile_id", ""))
            item = readiness.get(profile_id, {})
            name = str(profile.get("canonical_name") or profile_id)
            lines.append(
                "| "
                f"{_obsidian_link('01_Persone', name)} "
                f"| {item.get('document_count', 0)} "
                f"| {item.get('candidate_document_person_link_count', 0)} "
                f"| {item.get('candidate_evidence_claim_count', 0)} "
                f"| {item.get('reviewable_document_signal_count', 0)} "
                f"| `{item.get('readiness_status', 'needs_documents')}` "
                f"| {item.get('next_action', 'Registrare o collegare almeno un documento revisionabile.')} |"
            )
    else:
        lines.append("| Nessun profilo | 0 | 0 | 0 | 0 | `needs_documents` | Selezionare profili pilota. |")

    lines.extend(["", "## Stato ingest documentale", ""])
    lines.extend(_mvp_document_intake_markdown(payload.get("document_intake_readiness")))

    lines.extend(["", "## Diagnostica segnale MVP", ""])
    lines.extend(_mvp_signal_diagnostics_markdown(payload.get("mvp_signal_diagnostics"), include_details=True))

    if review_queue_md is not None:
        lines.extend(
            [
                "",
                "## Prossime decisioni",
                "",
                f"- Review queue: `{review_queue_md}`",
                *([f"- Riepilogo decisioni: `{review_decisions_summary}`"] if review_decisions_summary is not None else []),
                "- Usare la queue come lista di lavoro: non applica patch e non valida fatti.",
            ]
        )

    review_session = review_session if isinstance(review_session, dict) else {}
    if review_session:
        lines.extend(
            [
                "",
                "## Sessione review storici",
                "",
                f"- Stato sessione: `{review_session.get('session_status', 'not_started')}`",
                f"- Profili in sessione: `{review_session.get('profile_count', 0)}`",
                f"- Pronti per revisione curatoriale: `{review_session.get('ready_for_curator_review_count', 0)}`",
                "",
                "| Profilo | Item | Accettati | Pending | Invalidi | Stato sessione |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        profile_sessions = _json_object_list(review_session.get("profiles"))
        if profile_sessions:
            for item in profile_sessions:
                profile_id = str(item.get("profile_id", ""))
                name = _profile_name_for_id(profiles, profile_id)
                profile_label = _obsidian_link("01_Persone", name) if name else f"`{profile_id}`"
                lines.append(
                    "| "
                    f"{profile_label} "
                    f"| {item.get('item_count', 0)} "
                    f"| {item.get('accepted_count', 0)} "
                    f"| {item.get('pending_count', 0)} "
                    f"| {item.get('invalid_count', 0)} "
                    f"| `{item.get('session_status', 'not_started')}` |"
                )
        else:
            lines.append("| Nessun profilo | 0 | 0 | 0 | 0 | `not_started` |")

    publication_candidates = publication_candidates or []
    lines.extend(["", "## Schede candidate", ""])
    if publication_candidates:
        lines.extend(
            [
                "| Profilo | Stato candidatura | Scheda candidata |",
                "|---|---|---|",
            ]
        )
        for item in publication_candidates:
            name = str(item.get("canonical_name") or item.get("profile_id", ""))
            lines.append(
                "| "
                f"{_obsidian_link('01_Persone', name)} "
                f"| `{item.get('candidate_status', 'draft')}` "
                f"| {_obsidian_link('40_Publication_Candidates', name)} |"
            )
    else:
        lines.append("- Nessuna scheda candidata generata.")

    lines.extend(["", "## Warning", ""])
    warnings = _json_string_list(payload.get("warnings"))
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- Nessun warning nel summary.")

    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Questo vault e' un pacchetto di revisione.",
            "- Obsidian non e' il database canonico.",
            "- Nessun output automatico e' pubblicabile senza revisione umana.",
            "",
            AUTO_END,
        ]
    )
    return "\n".join(lines)


def _mvp_curatorial_brief_markdown(
    *,
    payload: dict[str, object],
    profiles: list[dict[str, object]],
    readiness: dict[str, dict[str, object]],
    review_session: dict[str, object],
    publication_candidates: list[dict[str, object]],
) -> str:
    scorecard = _dict_object(payload.get("pilot_package_scorecard"))
    intake = _dict_object(payload.get("document_intake_readiness"))
    signal_diagnostics = _dict_object(payload.get("mvp_signal_diagnostics"))
    lines = [
        "---",
        "type: mvp_curatorial_brief",
        f"review_status: {_yaml_value(payload.get('review_status', 'unreviewed'))}",
        "publication_status: \"not_publishable_without_curator_review\"",
        "---",
        "",
        "# Brief curatoriale MVP Purocielo",
        "",
        AUTO_BEGIN,
        "",
        "## Obiettivo",
        "",
        "Presentare un pacchetto revisionabile dell'Archivio digitale verificabile dei caduti di Purocielo: profili pilota, documenti, evidenze candidate, piste documentali e schede candidate, senza pubblicare automaticamente fatti storici.",
        "",
        "## Stato del pacchetto",
        "",
        f"- Stato pacchetto: `{scorecard.get('package_status', 'not_available')}`",
        f"- Profili esportati: `{len(profiles)}`",
        f"- Documenti nel summary: `{payload.get('document_count', 0)}`",
        f"- Link persona-documento candidati: `{payload.get('candidate_document_person_link_count', 0)}`",
        f"- Claim candidati: `{payload.get('candidate_evidence_claim_count', 0)}`",
        f"- Piste documentali revisionabili: `{payload.get('reviewable_document_signal_count', 0)}`",
        f"- Item minimi di revisione: `{scorecard.get('minimum_review_item_count', 0)}`",
        f"- Prossima azione: {scorecard.get('next_action') or payload.get('next_action') or 'Completare la revisione storica del pacchetto pilota.'}",
        "",
        "## Materiali consultabili",
        "",
        f"- Dashboard operativa: {_obsidian_link('10_Output', 'MVP_Pilot_Review')}",
        f"- Schede candidate: {_obsidian_link('40_Publication_Candidates', publication_candidates[0]['canonical_name']) if publication_candidates else '`40_Publication_Candidates/`'}",
        "- Le schede candidate sono viste preview-only, non schede museali definitive.",
        "",
        "## Profili pilota",
        "",
        "| Profilo | Stato scheda | Stato candidatura | Prossima azione |",
        "|---|---|---|---|",
    ]
    candidates_by_profile = {
        str(item.get("profile_id", "")): item for item in publication_candidates if str(item.get("profile_id", "")).strip()
    }
    if profiles:
        for profile in profiles:
            profile_id = str(profile.get("profile_id", ""))
            name = str(profile.get("canonical_name") or profile_id)
            ready = readiness.get(profile_id, {})
            candidate = candidates_by_profile.get(profile_id, {})
            lines.append(
                "| "
                f"{_obsidian_link('01_Persone', name)} "
                f"| `{ready.get('readiness_status', 'needs_documents')}` "
                f"| `{candidate.get('candidate_status', 'draft')}` "
                f"| {ready.get('next_action', 'Revisionare il profilo pilota.')} |"
            )
    else:
        lines.append("| Nessun profilo | `needs_documents` | `draft` | Selezionare profili pilota. |")

    lines.extend(
        [
            "",
            "## Sessione storici",
            "",
            f"- Stato sessione: `{review_session.get('session_status', 'not_started') if isinstance(review_session, dict) else 'not_started'}`",
            f"- Profili in sessione: `{review_session.get('profile_count', 0) if isinstance(review_session, dict) else 0}`",
            f"- Profili pronti per revisione curatoriale: `{review_session.get('ready_for_curator_review_count', 0) if isinstance(review_session, dict) else 0}`",
            "",
            "## Blocchi documentali",
            "",
        ]
    )
    blockers = _json_string_list(intake.get("mvp_blockers")) if intake else []
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- Nessun blocco documentale dichiarato nel summary MVP.")
    lines.extend(
        [
            f"- Prossima azione documentale: {intake.get('next_action', 'Controllare OCR, testi e documenti collegati.') if intake else 'Collegare la run locale al riepilogo MVP.'}",
            "",
            "## Segnale MVP per finanziamento",
            "",
            *_mvp_signal_diagnostics_markdown(signal_diagnostics, include_details=False),
            "",
            "## Vincoli editoriali",
            "",
            "- Questo brief e' una sintesi curatoriale generata automaticamente.",
            "- Nessun claim candidato e' promosso a fatto verificato.",
            "- Nessun profilo JSON-LD canonico viene modificato.",
            "- Nessuna scheda candidata e' pubblicabile senza revisione umana.",
            "",
            AUTO_END,
        ]
    )
    return "\n".join(lines)


def _mvp_document_intake_markdown(value: object) -> list[str]:
    intake = value if isinstance(value, dict) else {}
    if not intake or not intake.get("available"):
        return [
            "- Stato: `not_available`",
            f"- Prossima azione: {intake.get('next_action', 'Collegare la run locale al riepilogo MVP.')}",
        ]
    input_plan = intake.get("input_processing_plan", {})
    metadata = intake.get("metadata_extraction", {})
    text = intake.get("text_extraction", {})
    ocr = intake.get("ocr_batch", {})
    lines = [
        f"- Run locale: `{intake.get('local_run_dir', '')}`",
        f"- Asset raw rilevati: `{_dict_get(input_plan, 'asset_count', 0)}`",
        f"- Documenti metadatati: `{_dict_get(metadata, 'document_count', 0)}`",
        f"- Testi estratti: `{_dict_get(text, 'extracted_count', 0)}` / `{_dict_get(text, 'document_count', 0)}`",
        f"- Documenti nel summary MVP: `{intake.get('mvp_document_count', 0)}`",
    ]
    action_counts = input_plan.get("action_counts") if isinstance(input_plan, dict) else {}
    if isinstance(action_counts, dict) and action_counts:
        lines.extend(["", "Azioni raw principali:"])
        for action, count in sorted(action_counts.items()):
            lines.append(f"- `{action}`: `{count}`")
    ocr_summary = ocr.get("summary") if isinstance(ocr, dict) else {}
    if isinstance(ocr_summary, dict) and ocr_summary:
        lines.extend(["", "OCR batch:"])
        for key in ("processed", "skipped_existing_text", "skipped_missing_sidecar", "skipped_duplicate_output", "error"):
            lines.append(f"- `{key}`: `{ocr_summary.get(key, 0)}`")
    lines.extend(["", "Blocchi/prossime azioni:"])
    blockers = _json_string_list(intake.get("mvp_blockers"))
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- Nessun blocco documentale dichiarato.")
    lines.append(f"- Prossima azione consigliata: {intake.get('next_action', '')}")
    return lines


def _mvp_signal_diagnostics_markdown(value: object, *, include_details: bool) -> list[str]:
    diagnostics = value if isinstance(value, dict) else {}
    if not diagnostics:
        return ["- Diagnostica segnale non disponibile nel summary MVP."]
    lines = [
        f"- Documenti nel pacchetto: `{diagnostics.get('document_count', 0)}`",
        f"- Documenti unici stimati: `{diagnostics.get('estimated_unique_document_count', 0)}`",
        f"- Gruppi duplicati: `{diagnostics.get('duplicate_document_group_count', 0)}`",
        f"- Link nominali deboli: `{diagnostics.get('weak_nominal_link_count', 0)}` / `{diagnostics.get('candidate_document_person_link_count', 0)}`",
        f"- Profili con link ma zero claim: `{diagnostics.get('profiles_with_links_no_claims_count', 0)}`",
        f"- Prossima azione segnale: {diagnostics.get('next_action', '')}",
    ]
    blockers = _json_string_list(diagnostics.get("mvp_blockers"))
    if blockers:
        lines.extend(["", "Blocchi segnale:"])
        lines.extend(f"- {blocker}" for blocker in blockers[:5])
    if include_details:
        duplicate_groups = _json_object_list(diagnostics.get("duplicate_document_groups"))
        if duplicate_groups:
            lines.extend(["", "Duplicati da revisionare:"])
            for group in duplicate_groups[:5]:
                source_ids = ", ".join(_json_string_list(group.get("source_document_ids")))
                lines.append(
                    f"- `{group.get('key_kind', '')}` = `{group.get('key_value', '')}` "
                    f"({group.get('document_count', 0)} documenti: {source_ids})"
                )
        profiles = _json_object_list(diagnostics.get("profiles_with_links_no_claims"))
        if profiles:
            lines.extend(["", "Profili con link ma zero claim:"])
            for profile in profiles[:10]:
                label = str(profile.get("canonical_name") or profile.get("profile_id", ""))
                lines.append(
                    f"- `{profile.get('profile_id', '')}` - {label}: "
                    f"{profile.get('candidate_document_person_link_count', 0)} link, "
                    f"{profile.get('reviewable_document_signal_count', 0)} piste, "
                    f"stato `{profile.get('readiness_status', '')}`"
                )
    return lines


def _mvp_pilot_package_scorecard_markdown(value: object) -> list[str]:
    scorecard = value if isinstance(value, dict) else {}
    if not scorecard:
        return ["_Scorecard pacchetto MVP non disponibile nel summary._"]
    lines = [
        f"- Stato pacchetto: `{scorecard.get('package_status', '')}`",
        f"- Profili pronti per review: `{scorecard.get('ready_for_review_profile_count', 0)}` / `{scorecard.get('profile_count', 0)}`",
        f"- Profili con blocchi: `{scorecard.get('blocked_profile_count', 0)}`",
        f"- Documenti collegati nel pacchetto: `{scorecard.get('document_count', 0)}`",
        f"- Link persona-documento candidati: `{scorecard.get('candidate_document_person_link_count', 0)}`",
        f"- Claim candidati: `{scorecard.get('candidate_evidence_claim_count', 0)}`",
        f"- Piste documentali revisionabili: `{scorecard.get('reviewable_document_signal_count', 0)}`",
        f"- Item minimi di revisione: `{scorecard.get('minimum_review_item_count', 0)}`",
        f"- Prossima azione: {scorecard.get('next_action', '')}",
    ]
    blockers = _json_string_list(scorecard.get("top_blockers"))
    if blockers:
        lines.extend(["", "Blocchi principali:"])
        lines.extend(f"- {blocker}" for blocker in blockers)
    return lines


def _obsidian_link(folder: str, identifier: str) -> str:
    return f"[[../{folder}/{slugify_identifier(identifier)}]]"


def _profile_id_from_item(item: dict[str, object]) -> str:
    return str(item.get("profile_id") or item.get("person_candidate_id") or item.get("person_id") or "")


def _profile_name_for_id(profiles: list[dict[str, object]], profile_id: str) -> str:
    for profile in profiles:
        if str(profile.get("profile_id", "")) == profile_id:
            return str(profile.get("canonical_name") or profile_id)
    return ""


def _dict_object(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _dict_get(value: object, key: str, default: object = "") -> object:
    return value.get(key, default) if isinstance(value, dict) else default


def _json_object_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _json_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _format_list(values: list[str]) -> str:
    if not values:
        return "(nessuno)"
    return ", ".join(values)


def _yaml_value(value: object) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'
