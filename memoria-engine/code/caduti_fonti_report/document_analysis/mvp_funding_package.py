from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_mvp_funding_package(
    *,
    run_dir: Path,
    quality_gate_status: str = "not_recorded",
    demo_descriptor_json: Path | None = None,
    output_checklist_json: Path | None = None,
    output_checklist_md: Path | None = None,
    output_index_md: Path | None = None,
) -> dict[str, Any]:
    readiness_path = run_dir / "mvp_package_readiness.json"
    dossier_path = run_dir / "mvp_funding_dossier.json"
    run_index_path = run_dir / "mvp_run_index.json"
    model_cards_manifest_path = run_dir / "schede_modello" / "manifest.json"
    readiness = _load_json_object(readiness_path)
    dossier = _load_json_object(dossier_path)
    run_index = _load_json_object(run_index_path)
    model_cards = _load_json_object(model_cards_manifest_path)
    demo_descriptor = _load_json_object(demo_descriptor_json) if demo_descriptor_json else {}

    checks = _go_no_go_checks(
        run_dir=run_dir,
        readiness=readiness,
        dossier=dossier,
        run_index=run_index,
        model_cards=model_cards,
        quality_gate_status=quality_gate_status,
        demo_descriptor=demo_descriptor,
    )
    blocker_checks = [item for item in checks if item["status"] == "blocker"]
    review_blocker_checks = [item for item in checks if item["status"] == "review_blocker"]
    if blocker_checks:
        overall_status = "no_go_missing_outputs"
    elif review_blocker_checks:
        overall_status = "go_with_review_blockers"
    else:
        overall_status = "go_for_funding_demo"

    checklist = {
        "@type": "MvpGoNoGoChecklist",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "output_policy": "preview-only",
        "run_dir": str(run_dir),
        "demo_descriptor_json": str(demo_descriptor_json) if demo_descriptor_json else "",
        "demo_status": str(demo_descriptor.get("status", "")),
        "demo_run_id": str(demo_descriptor.get("run_id", "")),
        "overall_status": overall_status,
        "quality_gate_status": quality_gate_status,
        "profile_count": _demo_profile_count(demo_descriptor)
        or _integer(readiness.get("profile_count"), _integer(dossier.get("profile_count"))),
        "ready_profile_count": _integer(readiness.get("ready_profile_count"), _integer(dossier.get("ready_profile_count"))),
        "model_card_count": _integer(model_cards.get("model_card_count")),
        "source_document_count": len(_list_strings(demo_descriptor.get("source_document_ids"))),
        "source_family_count": len(_list_strings(demo_descriptor.get("source_families"))),
        "review_queue_item_count": _integer(readiness.get("review_queue_item_count"), _integer(dossier.get("review_queue_item_count"))),
        "pending_review_count": _integer(readiness.get("pending_review_count"), _integer(dossier.get("pending_review_count"))),
        "checks": checks,
        "next_actions": _next_actions(overall_status=overall_status, checks=checks),
        "warnings": [
            "Go/no-go preview-only: misura presentabilita' del pacchetto, non pubblicabilita' storica.",
            "Decisioni storiche e curatorali restano manuali.",
        ],
    }
    output_checklist_json = output_checklist_json or run_dir / "mvp_go_no_go_checklist.json"
    output_checklist_md = output_checklist_md or run_dir / "mvp_go_no_go_checklist.md"
    output_index_md = output_index_md or run_dir / "funding_package_index.md"
    output_checklist_json.parent.mkdir(parents=True, exist_ok=True)
    output_checklist_md.parent.mkdir(parents=True, exist_ok=True)
    output_index_md.parent.mkdir(parents=True, exist_ok=True)
    output_checklist_json.write_text(json.dumps(checklist, ensure_ascii=False, indent=2), encoding="utf-8")
    output_checklist_md.write_text(render_go_no_go_markdown(checklist), encoding="utf-8")
    funding_index = _funding_index_payload(
        run_dir=run_dir,
        checklist=checklist,
        readiness=readiness,
        dossier=dossier,
        run_index=run_index,
        model_cards=model_cards,
        demo_descriptor=demo_descriptor,
        demo_descriptor_json=demo_descriptor_json,
    )
    output_index_md.write_text(render_funding_package_index_markdown(funding_index), encoding="utf-8")
    return {
        "@type": "MvpFundingPackageBuild",
        "generated_at": checklist["generated_at"],
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "overall_status": overall_status,
        "demo_descriptor_json": str(demo_descriptor_json) if demo_descriptor_json else "",
        "go_no_go_checklist_json": str(output_checklist_json),
        "go_no_go_checklist_md": str(output_checklist_md),
        "funding_package_index_md": str(output_index_md),
        "checklist": checklist,
        "funding_index": funding_index,
    }


def render_go_no_go_markdown(checklist: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_go_no_go_checklist",
        f"review_status: {_yaml_value(checklist.get('review_status', 'unreviewed'))}",
        f"publication_status: {_yaml_value(checklist.get('publication_status', 'not_publishable_without_human_review'))}",
        f"overall_status: {_yaml_value(checklist.get('overall_status', ''))}",
        "---",
        "",
        "# Go/no-go MVP finanziamento",
        "",
        "Checklist preview-only: misura se il pacchetto e' presentabile come demo finanziabile, non se le schede sono pubblicabili.",
        "",
        "## Esito",
        "",
        f"- Stato complessivo: `{checklist.get('overall_status', '')}`",
        f"- Quality gate mirato: `{checklist.get('quality_gate_status', '')}`",
        f"- Descriptor demo: `{checklist.get('demo_descriptor_json', '')}`",
        f"- Stato descriptor: `{checklist.get('demo_status', '')}`",
        f"- Profili demo: `{checklist.get('profile_count', 0)}`",
        f"- Documenti fonte demo: `{checklist.get('source_document_count', 0)}`",
        f"- Famiglie fonte demo: `{checklist.get('source_family_count', 0)}`",
        f"- Profili ready_for_review: `{checklist.get('ready_profile_count', 0)}`",
        f"- Schede modello: `{checklist.get('model_card_count', 0)}`",
        f"- Item review queue: `{checklist.get('review_queue_item_count', 0)}`",
        f"- Decisioni pending: `{checklist.get('pending_review_count', 0)}`",
        "",
        "## Checklist",
        "",
        "| Voce | Stato | Evidenza | Nota |",
        "|---|---|---|---|",
    ]
    for item in _list_items(checklist.get("checks")):
        lines.append(
            "| "
            f"{item.get('label', '')} "
            f"| `{item.get('status', '')}` "
            f"| `{item.get('evidence', '')}` "
            f"| {item.get('note', '')} |"
        )
    lines.extend(["", "## Prossime azioni", ""])
    lines.extend(f"- {action}" for action in _list_strings(checklist.get("next_actions")))
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Non approva decisioni storiche.",
            "- Non modifica profili JSON-LD.",
            "- Non trasforma claim candidati in fatti.",
            "- Non rende pubblicabile alcuna scheda senza revisione umana.",
            "",
        ]
    )
    return "\n".join(lines)


def render_funding_package_index_markdown(index: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: funding_package_index",
        f"review_status: {_yaml_value(index.get('review_status', 'unreviewed'))}",
        f"publication_status: {_yaml_value(index.get('publication_status', 'not_publishable_without_human_review'))}",
        "---",
        "",
        "# Pacchetto finanziatore Me.Mo.Ri.a",
        "",
        "Pagina di ingresso preview-only per leggere la demo finanziabile senza attraversare i JSON tecnici.",
        "",
        "## Esito rapido",
        "",
        f"- Stato go/no-go: `{index.get('overall_status', '')}`",
        f"- Run: `{index.get('run_dir', '')}`",
        f"- Descriptor demo: `{index.get('demo_descriptor_json', '')}`",
        f"- Profili demo: `{index.get('profile_count', 0)}`",
        f"- Documenti fonte demo: `{index.get('source_document_count', 0)}`",
        f"- Famiglie fonte demo: `{index.get('source_family_count', 0)}`",
        f"- Schede modello: `{index.get('model_card_count', 0)}`",
        f"- Decisioni pending: `{index.get('pending_review_count', 0)}`",
        "",
        "## Aprire in questo ordine",
        "",
    ]
    for number, item in enumerate(_list_items(index.get("reading_order")), start=1):
        lines.append(f"{number}. {item.get('label', '')}: `{item.get('path', '')}`")
    lines.extend(["", "## Materiali", ""])
    lines.extend(["| Materiale | Stato | Percorso |", "|---|---|---|"])
    for item in _list_items(index.get("materials")):
        lines.append(f"| {item.get('label', '')} | `{item.get('status', '')}` | `{item.get('path', '')}` |")
    lines.extend(
        [
            "",
            "## Messaggio chiave",
            "",
            "Me.Mo.Ri.a non promette biografie generate automaticamente: mostra un metodo verificabile per collegare persone, fonti, documenti, evidenze e decisioni di revisione.",
            "",
            "## Vincoli editoriali",
            "",
            "- Tutti gli output automatici restano preview-only, unreviewed o pending.",
            "- Le schede modello sono esempi di dossier di revisione, non biografie pubblicabili.",
            "- Il finanziamento serve a completare revisione, trattamento documentale e confezionamento museale.",
            "",
        ]
    )
    return "\n".join(lines)


def _go_no_go_checks(
    *,
    run_dir: Path,
    readiness: dict[str, Any],
    dossier: dict[str, Any],
    run_index: dict[str, Any],
    model_cards: dict[str, Any],
    quality_gate_status: str,
    demo_descriptor: dict[str, Any],
) -> list[dict[str, str]]:
    model_card_count = _integer(model_cards.get("model_card_count"))
    pending_review_count = _integer(readiness.get("pending_review_count"), _integer(dossier.get("pending_review_count")))
    checks = [
        _check(
            "quality_gate_targeted_green",
            "Quality gate mirato verde",
            quality_gate_status == "passed",
            "current_session",
            "Esito dichiarato dal comando di verifica dell'incremento.",
            missing_status="blocker",
        ),
    ]
    if demo_descriptor:
        readiness_descriptor = _dict_object(demo_descriptor.get("readiness"))
        safety = _dict_object(demo_descriptor.get("safety"))
        source_documents = _list_strings(demo_descriptor.get("source_document_ids"))
        source_families = _list_strings(demo_descriptor.get("source_families"))
        demo_profiles = _demo_profile_ids(demo_descriptor)
        selected_documents = _integer(readiness_descriptor.get("selected_document_count"), len(source_documents))
        covered_documents = _integer(readiness_descriptor.get("covered_document_count"))
        missing_families = _list_strings(readiness_descriptor.get("missing_source_families"))
        checks.extend(
            [
                _check(
                    "demo_descriptor_ready",
                    "Descriptor golden run pronto",
                    demo_descriptor.get("status") == "ready_for_internal_demo",
                    "memoria_mvp_demo.active.json",
                    "Il descriptor dichiara la demo interna pronta.",
                ),
                _check(
                    "demo_preview_only",
                    "Vincoli preview-only dichiarati",
                    demo_descriptor.get("preview_only") is True
                    and safety.get("publication_ready") is False
                    and safety.get("modifies_canonical_profiles") is False
                    and safety.get("applies_profile_patch") is False
                    and safety.get("creates_canonical_verified_facts") is False,
                    "memoria_mvp_demo.active.json",
                    "Il pacchetto non applica patch, non modifica profili e non promuove fatti canonici.",
                ),
                _check(
                    "demo_scope_profiles",
                    "Perimetro profili demo T33",
                    1 <= len(demo_profiles) <= 2,
                    "memoria_mvp_demo.active.json",
                    f"Profili demo dichiarati: {len(demo_profiles)}.",
                ),
                _check(
                    "demo_scope_documents",
                    "Perimetro documenti fonte demo T33",
                    2 <= len(source_documents) <= 4,
                    "memoria_mvp_demo.active.json",
                    f"Documenti fonte dichiarati: {len(source_documents)}.",
                ),
                _check(
                    "demo_multi_source_coverage",
                    "Copertura multi-fonte demo",
                    len(source_families) >= 2
                    and covered_documents == selected_documents
                    and not missing_families,
                    "memoria_mvp_demo.active.json",
                    f"Famiglie fonte: {len(source_families)}; documenti coperti: {covered_documents}/{selected_documents}.",
                ),
                _check(
                    "demo_descriptor_artifacts",
                    "Artifact descriptor presenti",
                    all(
                        _descriptor_artifact_present(demo_descriptor, artifact_name)
                        for artifact_name in [
                            "ledger",
                            "reconciliation_table",
                            "review_decisions_summary",
                            "verified_facts_preview",
                            "profile_patch_preview",
                            "readiness_report",
                        ]
                    ),
                    "memoria_mvp_demo.active.json",
                    "Ledger, riconciliazione, decisioni e preview sono puntati dal descriptor.",
                ),
                _check(
                    "feedback_loop_outcome",
                    "Feedback loop T31 confezionato",
                    (run_dir / "historian_review" / "feedback_loop_outcome.t31-demo.md").is_file()
                    or (run_dir / "historian_review" / "feedback_loop_outcome.t31-demo.json").is_file(),
                    "historian_review/feedback_loop_outcome.t31-demo.md",
                    "Esito feedback loop disponibile come evidenza narrativa.",
                ),
            ]
        )
    else:
        checks.extend(
            [
                _check("pilot_scope", "Perimetro pilota congelato", len(_list_strings(run_index.get("profile_ids"))) >= 3, "mvp_run_index.json", "Profili espliciti nella run finale."),
                _check("obsidian_vault", "Vault Obsidian generato", bool(_artifact_present(run_index, "vault_dir")), "mvp_run_index.json", "Vault presente come output editoriale."),
                _check("model_cards", "3-5 schede modello", 3 <= model_card_count <= 5, "schede_modello/manifest.json", f"Schede modello rilevate: {model_card_count}."),
                _check("pilot_cards_digest", "Digest finanziatore", (run_dir / "mvp_pilot_cards_digest.md").is_file(), "mvp_pilot_cards_digest.md", "Digest schede pilota presente."),
            ]
        )
    checks.extend(
        [
        _check("final_run_indexed", "Run finale indicizzata", (run_dir / "mvp_run_index.md").is_file(), "mvp_run_index.md", "Indice operativo della run finale."),
        _check("review_queue", "Review queue generata", (run_dir / "historian_review" / "review_queue.md").is_file(), "historian_review/review_queue.md", "Coda decisioni per storici."),
        _check("funding_dossier", "Dossier finanziamento", (run_dir / "mvp_funding_dossier.md").is_file(), "mvp_funding_dossier.md", "Dossier leggibile da non tecnici."),
        _check("no_unreviewed_facts", "Nessun fatto non revisionato presentato come definitivo", True, "policy", "Output marcati non pubblicabili senza revisione."),
        _check(
            "review_session_plan",
            "Sessione revisione o piano calendarizzabile",
            (run_dir / "historian_review" / "review_session.md").is_file(),
            "historian_review/review_session.md",
            "Sessione review presente; decisioni ancora da compilare.",
        ),
        ]
    )
    if pending_review_count > 0:
        checks.append(
            {
                "id": "pending_review_decisions",
                "label": "Decisioni storiche pending",
                "status": "review_blocker",
                "evidence": "mvp_package_readiness.json",
                "note": f"Restano {pending_review_count} decisioni pending: il pacchetto e' finanziabile come demo, non pubblicabile.",
            }
        )
    return checks


def _funding_index_payload(
    *,
    run_dir: Path,
    checklist: dict[str, Any],
    readiness: dict[str, Any],
    dossier: dict[str, Any],
    run_index: dict[str, Any],
    model_cards: dict[str, Any],
    demo_descriptor: dict[str, Any],
    demo_descriptor_json: Path | None,
) -> dict[str, Any]:
    materials = [
        _material("Go/no-go checklist", run_dir / "mvp_go_no_go_checklist.md"),
        _material("Dossier finanziamento", run_dir / "mvp_funding_dossier.md"),
        _material("Readiness pacchetto", run_dir / "mvp_package_readiness.md"),
        _material("Indice schede modello", run_dir / "schede_modello" / "README.md"),
        _material("Estratti finanziatore", run_dir / "funding_excerpts", kind="directory"),
        _material("Review session", run_dir / "historian_review" / "review_session.md"),
        _material("Review dashboard", run_dir / "historian_review" / "review_dashboard.md"),
        _material("Run index", run_dir / "mvp_run_index.md"),
    ]
    if demo_descriptor:
        materials[1:1] = [
            _material("Descriptor golden run", demo_descriptor_json) if demo_descriptor_json else {},
            _descriptor_material("Tabella riconciliazione", demo_descriptor, "reconciliation_table"),
            _descriptor_material("Decisioni review", demo_descriptor, "review_decisions_summary"),
            _descriptor_material("Verified facts preview", demo_descriptor, "verified_facts_preview"),
            _descriptor_material("ProfilePatch preview", demo_descriptor, "profile_patch_preview"),
            _material("Feedback loop T31", run_dir / "historian_review" / "feedback_loop_outcome.t31-demo.md"),
        ]
    materials = [item for item in materials if item]
    reading_order = [item for item in materials if item["status"] == "present"]
    return {
        "@type": "MvpFundingPackageIndex",
        "generated_at": checklist["generated_at"],
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "run_dir": str(run_dir),
        "demo_descriptor_json": str(demo_descriptor_json) if demo_descriptor_json else "",
        "demo_status": str(demo_descriptor.get("status", "")),
        "demo_run_id": str(demo_descriptor.get("run_id", "")),
        "overall_status": checklist["overall_status"],
        "profile_count": _demo_profile_count(demo_descriptor)
        or _integer(readiness.get("profile_count"), _integer(dossier.get("profile_count"))),
        "source_document_count": len(_list_strings(demo_descriptor.get("source_document_ids"))),
        "source_family_count": len(_list_strings(demo_descriptor.get("source_families"))),
        "model_card_count": _integer(model_cards.get("model_card_count")),
        "pending_review_count": checklist.get("pending_review_count", 0),
        "recommended_reading_order_from_run_index": _list_items(run_index.get("recommended_reading_order")),
        "reading_order": reading_order,
        "materials": materials,
    }


def _check(
    check_id: str,
    label: str,
    condition: bool,
    evidence: str,
    note: str,
    *,
    missing_status: str = "blocker",
) -> dict[str, str]:
    return {
        "id": check_id,
        "label": label,
        "status": "go" if condition else missing_status,
        "evidence": evidence,
        "note": note,
    }


def _material(label: str, path: Path, *, kind: str = "file") -> dict[str, str]:
    exists = path.is_dir() if kind == "directory" else path.is_file()
    return {
        "label": label,
        "path": str(path),
        "kind": kind,
        "status": "present" if exists else "missing",
    }


def _descriptor_material(label: str, descriptor: dict[str, Any], artifact_name: str) -> dict[str, str]:
    artifact_path = _descriptor_artifact_path(descriptor, artifact_name)
    if not artifact_path:
        return {
            "label": label,
            "path": "",
            "kind": "file",
            "status": "missing",
        }
    return _material(label, artifact_path)


def _artifact_present(run_index: dict[str, Any], name: str) -> bool:
    for item in _list_items(run_index.get("artifacts")):
        if item.get("name") == name and item.get("status") == "present":
            return True
    return False


def _descriptor_artifact_present(descriptor: dict[str, Any], artifact_name: str) -> bool:
    artifact_path = _descriptor_artifact_path(descriptor, artifact_name)
    return bool(artifact_path and artifact_path.is_file())


def _descriptor_artifact_path(descriptor: dict[str, Any], artifact_name: str) -> Path | None:
    artifacts = _dict_object(descriptor.get("artifacts"))
    value = artifacts.get(artifact_name)
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def _next_actions(*, overall_status: str, checks: list[dict[str, str]]) -> list[str]:
    if overall_status == "no_go_missing_outputs":
        missing = [item["label"] for item in checks if item["status"] == "blocker"]
        return [f"Completare output mancante o bloccante: {label}." for label in missing]
    if overall_status == "go_with_review_blockers":
        return [
            "Usare il pacchetto per richiesta finanziamento come demo revisionabile.",
            "Calendarizzare la compilazione delle decisioni storiche pending.",
            "Non presentare schede o claim come pubblicabili prima della review.",
        ]
    return [
        "Usare funding_package_index.md come prima pagina del pacchetto finanziatore.",
        "Mantenere i vincoli preview-only fino alla revisione curatoriale.",
    ]


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _list_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _demo_profile_ids(descriptor: dict[str, Any]) -> list[str]:
    profile_ids = _list_strings(descriptor.get("primary_profile_ids"))
    primary = descriptor.get("primary_profile_id")
    if isinstance(primary, str) and primary.strip():
        profile_ids.append(primary)
    profile_ids.extend(_list_strings(descriptor.get("contrast_profile_ids")))
    return list(dict.fromkeys(profile_ids))


def _demo_profile_count(descriptor: dict[str, Any]) -> int:
    return len(_demo_profile_ids(descriptor))


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _yaml_value(value: object) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera go/no-go e indice del pacchetto finanziatore MVP.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--quality-gate-status",
        choices=["passed", "failed", "not_recorded"],
        default="not_recorded",
    )
    parser.add_argument("--demo-descriptor-json", default="")
    parser.add_argument("--output-checklist-json", default="")
    parser.add_argument("--output-checklist-md", default="")
    parser.add_argument("--output-index-md", default="")
    args = parser.parse_args(argv)
    result = build_mvp_funding_package(
        run_dir=Path(args.run_dir),
        quality_gate_status=args.quality_gate_status,
        demo_descriptor_json=Path(args.demo_descriptor_json) if args.demo_descriptor_json else None,
        output_checklist_json=Path(args.output_checklist_json) if args.output_checklist_json else None,
        output_checklist_md=Path(args.output_checklist_md) if args.output_checklist_md else None,
        output_index_md=Path(args.output_index_md) if args.output_index_md else None,
    )
    print(f"Go/no-go MVP: {result['go_no_go_checklist_md']}")
    print(f"Funding package index: {result['funding_package_index_md']}")
    print(f"Stato: {result['overall_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
