from __future__ import annotations

from typing import Any


def render_candidate_person_profiles_markdown(payload: dict[str, Any]) -> str:
    candidates = _list_items(payload.get("candidate_person_profiles"))
    lines = [
        "# CandidatePersonProfile preview",
        "",
        f"- Documenti letti: `{payload.get('document_count', 0)}`",
        f"- Documenti tabellari: `{payload.get('tabular_document_count', 0)}`",
        f"- Profili candidati: `{payload.get('candidate_profile_count', 0)}`",
        f"- Righe saltate: `{payload.get('skipped_count', 0)}`",
        f"- Stato revisione: `{payload.get('review_status', '')}`",
        f"- Stato promozione: `{payload.get('promotion_status', '')}`",
        "",
        "## Profili candidati",
        "",
    ]
    if not candidates:
        lines.append("_Nessun profilo candidato._")
    else:
        lines.extend(
            [
                "| Nome | Profilo suggerito | Documento | Riga | Nascita | Morte | Stato |",
                "| --- | --- | --- | ---: | --- | --- | --- |",
            ]
        )
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(candidate.get("canonical_name", "")),
                        f"`{_md_cell(candidate.get('suggested_profile_id', ''))}`",
                        f"`{_md_cell(candidate.get('source_document_id', ''))}`",
                        _md_cell(candidate.get("row_number", "")),
                        _md_cell(candidate.get("birth", {}).get("raw", "") if isinstance(candidate.get("birth"), dict) else ""),
                        _md_cell(candidate.get("death", {}).get("raw", "") if isinstance(candidate.get("death"), dict) else ""),
                        f"`{_md_cell(candidate.get('review_status', ''))}`",
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Questo report non modifica i profili JSON-LD reali.",
            "- Nessun candidato viene promosso automaticamente a PersonResearchProfile canonico.",
            "- Ogni riga resta `unreviewed` finche' non viene validata da revisione umana.",
            "",
        ]
    )
    return "\n".join(lines)


def _list_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()
