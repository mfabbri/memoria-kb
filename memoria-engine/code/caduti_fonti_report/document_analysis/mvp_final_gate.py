from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .preview_payloads import dict_object, list_items, list_strings


REQUIRED_DESCRIPTOR_ARTIFACTS = (
    "ledger",
    "reconciliation_table",
    "review_decisions_summary",
    "verified_facts_preview",
    "profile_patch_preview",
    "readiness_report",
)

REQUIRED_PACKAGE_FILES = (
    "mvp_go_no_go_checklist.json",
    "mvp_go_no_go_checklist.md",
    "funding_package_index.md",
    "mvp_package_readiness.md",
    "mvp_funding_dossier.md",
    "historian_review/feedback_loop_outcome.t31-demo.md",
)


def build_mvp_final_gate_report(
    *,
    run_dir: Path,
    candidate_descriptor_json: Path,
    active_descriptor_json: Path | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    candidate_descriptor_json = candidate_descriptor_json.resolve()
    active_descriptor_json = active_descriptor_json.resolve() if active_descriptor_json is not None else None
    descriptor = _load_json_object(candidate_descriptor_json)
    checklist = _load_json_object(run_dir / "mvp_go_no_go_checklist.json")
    checks = _gate_checks(
        run_dir=run_dir,
        candidate_descriptor_json=candidate_descriptor_json,
        active_descriptor_json=active_descriptor_json,
        descriptor=descriptor,
        checklist=checklist,
    )
    blocker_count = sum(1 for item in checks if item["status"] == "blocker")
    review_blocker_count = sum(1 for item in checks if item["status"] == "review_blocker")
    gate_status = "ready_for_human_approval" if blocker_count == 0 else "blocked_for_human_approval"
    return {
        "@type": "MvpFinalGateReadOnlyReport",
        "generated_at": datetime.now(UTC).isoformat(),
        "gate_status": gate_status,
        "human_approval_required": True,
        "promotion_allowed_by_report": False,
        "run_dir": str(run_dir),
        "candidate_descriptor_json": str(candidate_descriptor_json),
        "active_descriptor_json": str(active_descriptor_json) if active_descriptor_json is not None else "",
        "candidate_run_id": str(descriptor.get("run_id", "")),
        "funding_overall_status": str(checklist.get("overall_status", "")),
        "blocker_count": blocker_count,
        "review_blocker_count": review_blocker_count,
        "checks": checks,
        "next_actions": _next_actions(blocker_count=blocker_count, review_blocker_count=review_blocker_count),
        "safety": {
            "read_only": True,
            "does_not_modify_active_descriptor": True,
            "does_not_apply_profile_patch": True,
            "does_not_create_canonical_verified_facts": True,
            "does_not_modify_canonical_profiles": True,
        },
    }


def render_mvp_final_gate_markdown(report: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_final_gate_read_only_report",
        f"gate_status: {_yaml_value(report.get('gate_status', ''))}",
        "human_approval_required: true",
        "promotion_allowed_by_report: false",
        "---",
        "",
        "# T33 final gate read-only",
        "",
        "Verifica tecnica preview-only: prepara il gate umano, non promuove la candidata.",
        "",
        "## Esito",
        "",
        f"- Stato gate: `{report.get('gate_status', '')}`",
        f"- Run candidata: `{report.get('candidate_run_id', '')}`",
        f"- Descriptor candidato: `{report.get('candidate_descriptor_json', '')}`",
        f"- Descriptor attivo: `{report.get('active_descriptor_json', '') or 'not_checked'}`",
        f"- Stato funding package: `{report.get('funding_overall_status', '')}`",
        f"- Blocker tecnici: `{report.get('blocker_count', 0)}`",
        f"- Review blocker: `{report.get('review_blocker_count', 0)}`",
        "",
        "## Checklist",
        "",
        "| Check | Stato | Evidenza | Nota |",
        "|---|---|---|---|",
    ]
    for item in list_items(report.get("checks")):
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(item.get("label")),
                    f"`{item.get('status', '')}`",
                    f"`{item.get('evidence', '')}`",
                    _md_cell(item.get("note")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Prossime azioni", ""])
    for action in list_strings(report.get("next_actions")):
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Non approva decisioni storiche.",
            "- Non modifica `memoria_mvp_demo.active.json`.",
            "- Non applica ProfilePatch.",
            "- Non crea verified facts canonici.",
            "- Non rende pubblicabile alcuna scheda.",
            "",
        ]
    )
    return "\n".join(lines)


def _gate_checks(
    *,
    run_dir: Path,
    candidate_descriptor_json: Path,
    active_descriptor_json: Path | None,
    descriptor: dict[str, Any],
    checklist: dict[str, Any],
) -> list[dict[str, str]]:
    safety = dict_object(descriptor.get("safety"))
    readiness = dict_object(descriptor.get("readiness"))
    artifacts = dict_object(descriptor.get("artifacts"))
    source_documents = list_strings(descriptor.get("source_document_ids"))
    source_families = list_strings(descriptor.get("source_families"))
    profile_ids = _descriptor_profile_ids(descriptor)
    covered_documents = _int_value(readiness.get("covered_document_count"))
    selected_documents = _int_value(readiness.get("selected_document_count"), len(source_documents))
    checks = [
        _check(
            "candidate_descriptor_present",
            "Descriptor candidato leggibile",
            bool(descriptor),
            str(candidate_descriptor_json),
            "Il descriptor candidato deve essere un oggetto JSON.",
        ),
        _check(
            "candidate_descriptor_ready",
            "Descriptor pronto per demo interna",
            descriptor.get("status") == "ready_for_internal_demo",
            "candidate_descriptor.status",
            f"Status rilevato: {descriptor.get('status', 'missing')}.",
        ),
        _check(
            "candidate_preview_only",
            "Safety preview-only",
            descriptor.get("preview_only") is True
            and safety.get("publication_ready") is False
            and safety.get("modifies_canonical_profiles") is False
            and safety.get("applies_profile_patch") is False
            and safety.get("creates_canonical_verified_facts") is False,
            "candidate_descriptor.safety",
            "Il gate non puo' applicare patch, creare fatti canonici o dichiarare pubblicabilita'.",
        ),
        _check(
            "candidate_scope_profiles",
            "Perimetro tre profili",
            len(profile_ids) == 3,
            "candidate_descriptor profile ids",
            f"Profili rilevati: {len(profile_ids)}.",
        ),
        _check(
            "candidate_scope_documents",
            "Perimetro cinque documenti",
            len(source_documents) == 5,
            "candidate_descriptor source_document_ids",
            f"Documenti rilevati: {len(source_documents)}.",
        ),
        _check(
            "candidate_multi_source_coverage",
            "Copertura multi-fonte completa",
            len(source_families) >= 2 and selected_documents == covered_documents and selected_documents > 0,
            "candidate_descriptor readiness",
            f"Famiglie: {len(source_families)}; documenti coperti: {covered_documents}/{selected_documents}.",
        ),
        _check(
            "candidate_artifacts_present",
            "Artefatti descriptor presenti nella run candidata",
            _descriptor_artifacts_present(artifacts=artifacts, run_dir=run_dir),
            "candidate_descriptor artifacts",
            "Ledger, riconciliazione, decisioni, preview e readiness devono esistere dentro la run candidata.",
        ),
        _check(
            "funding_checklist_present",
            "Checklist go/no-go presente",
            bool(checklist),
            str(run_dir / "mvp_go_no_go_checklist.json"),
            "La fase 4 deve aver prodotto il pacchetto unico.",
        ),
        _check(
            "funding_package_has_no_technical_blockers",
            "Pacchetto senza blocker tecnici",
            bool(checklist) and str(checklist.get("overall_status")) in {"go_with_review_blockers", "go_for_funding_demo"},
            "mvp_go_no_go_checklist.overall_status",
            f"Stato rilevato: {checklist.get('overall_status', 'missing')}.",
        ),
        _check(
            "package_files_present",
            "Materiali minimi pacchetto presenti",
            all((run_dir / relative).is_file() for relative in REQUIRED_PACKAGE_FILES),
            "run_dir package files",
            "Indice, dossier, readiness, go/no-go e feedback loop markdown devono essere presenti.",
        ),
    ]
    checks.extend(_active_descriptor_checks(active_descriptor_json=active_descriptor_json, descriptor=descriptor))
    pending_review_count = _int_value(checklist.get("pending_review_count"))
    if pending_review_count > 0:
        checks.append(
            {
                "id": "pending_review_decisions",
                "label": "Decisioni storiche pending",
                "status": "review_blocker",
                "evidence": "mvp_go_no_go_checklist.pending_review_count",
                "note": f"Restano {pending_review_count} decisioni pending: serve gate umano, non pubblicazione.",
            }
        )
    return checks


def _active_descriptor_checks(*, active_descriptor_json: Path | None, descriptor: dict[str, Any]) -> list[dict[str, str]]:
    if active_descriptor_json is None:
        return []
    active_descriptor = _load_json_object(active_descriptor_json)
    candidate_run_id = str(descriptor.get("run_id", "")).strip()
    active_run_id = str(active_descriptor.get("run_id", "")).strip()
    return [
        _check(
            "active_descriptor_still_separate",
            "Descriptor attivo non ancora promosso",
            bool(active_descriptor) and active_run_id != candidate_run_id,
            str(active_descriptor_json),
            f"Run attiva: {active_run_id or 'missing'}; run candidata: {candidate_run_id or 'missing'}.",
        )
    ]


def _descriptor_artifacts_present(*, artifacts: dict[str, Any], run_dir: Path) -> bool:
    for name in REQUIRED_DESCRIPTOR_ARTIFACTS:
        value = artifacts.get(name)
        if not isinstance(value, str) or not value.strip():
            return False
        artifact_path = Path(value)
        if not artifact_path.is_file():
            return False
        try:
            artifact_path.resolve().relative_to(run_dir)
        except ValueError:
            return False
    return True


def _descriptor_profile_ids(descriptor: dict[str, Any]) -> list[str]:
    profile_ids = list_strings(descriptor.get("primary_profile_ids"))
    profile_ids.extend(list_strings(descriptor.get("contrast_profile_ids")))
    return list(dict.fromkeys(profile_ids))


def _next_actions(*, blocker_count: int, review_blocker_count: int) -> list[str]:
    if blocker_count:
        return [
            "Correggere i blocker tecnici della candidata o rigenerare il pacchetto unico T33.",
            "Non promuovere il descriptor attivo finche' il gate tecnico non e' verde.",
        ]
    actions = [
        "Portare il report al gate finale umano.",
        "Eseguire la fase 5 solo dopo approvazione esplicita.",
        "Mantenere la candidata fuori da presentazioni esterne finche' non e' promossa.",
    ]
    if review_blocker_count:
        actions.append("Trattare i review blocker come limite editoriale: demo revisionabile, non scheda pubblicabile.")
    return actions


def _check(check_id: str, label: str, condition: bool, evidence: str, note: str) -> dict[str, str]:
    return {
        "id": check_id,
        "label": label,
        "status": "go" if condition else "blocker",
        "evidence": evidence,
        "note": note,
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _yaml_value(value: object) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value).replace("\n", " ").strip()
    return text.replace("|", "\\|")
