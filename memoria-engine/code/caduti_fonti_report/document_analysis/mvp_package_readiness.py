from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

READY_FOR_DEMO = "ready_for_demo"
NEEDS_REVIEW_MATERIAL = "needs_review_material"
NEEDS_DOCUMENT_INTAKE = "needs_document_intake"
MISSING_REQUIRED_OUTPUTS = "missing_required_outputs"


def build_mvp_package_readiness(
    *,
    summary_json: Path,
    review_queue_json: Path,
    review_decisions_summary_json: Path,
    vault_dir: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    summary = _load_json_object(summary_json)
    review_queue = _load_json_object(review_queue_json)
    review_decisions_summary = _load_json_object(review_decisions_summary_json)
    publication_candidates_dir = vault_dir / "40_Publication_Candidates"
    output_review_md = vault_dir / "10_Output" / "MVP_Pilot_Review.md"
    curatorial_brief_md = vault_dir / "10_Output" / "mvp_curatorial_brief.md"

    required_outputs = [
        _artifact("mvp_pilot_summary_json", summary_json, "file"),
        _artifact("review_queue_json", review_queue_json, "file"),
        _artifact("review_decisions_summary_json", review_decisions_summary_json, "file"),
        _artifact("obsidian_vault_dir", vault_dir, "dir"),
        _artifact("mvp_pilot_review_md", output_review_md, "file"),
        _artifact("mvp_curatorial_brief_md", curatorial_brief_md, "file"),
        _artifact("publication_candidates_dir", publication_candidates_dir, "dir"),
    ]
    missing_required_outputs = [item for item in required_outputs if not item["exists"]]
    publication_candidate_count = _count_markdown_files(publication_candidates_dir)
    profiles = _list_items(summary.get("profiles"))
    profile_readiness = _list_items(summary.get("profile_readiness"))
    ready_profile_count = sum(
        1 for item in profile_readiness if str(item.get("readiness_status", "")) == "ready_for_review"
    )
    intake_readiness = _dict_object(summary.get("document_intake_readiness"))
    scorecard = _dict_object(summary.get("pilot_package_scorecard"))
    document_intake_blockers = _document_intake_blockers(summary, intake_readiness, scorecard)
    review_queue_item_count = _integer(review_queue.get("item_count"), default=len(_list_items(review_queue.get("items"))))
    review_status = str(review_decisions_summary.get("review_status", ""))
    invalid_review_count = _integer(review_decisions_summary.get("invalid_count"))
    validation_error_count = _integer(review_decisions_summary.get("validation_error_count"))
    pending_review_count = _integer(review_decisions_summary.get("pending_count"))
    blockers = _build_blockers(
        missing_required_outputs=missing_required_outputs,
        document_intake_blockers=document_intake_blockers,
        review_queue_item_count=review_queue_item_count,
        publication_candidate_count=publication_candidate_count,
        review_status=review_status,
        invalid_review_count=invalid_review_count,
        validation_error_count=validation_error_count,
    )
    readiness_status = _readiness_status(
        missing_required_outputs=missing_required_outputs,
        document_intake_blockers=document_intake_blockers,
        review_queue_item_count=review_queue_item_count,
        publication_candidate_count=publication_candidate_count,
        review_status=review_status,
        invalid_review_count=invalid_review_count,
        validation_error_count=validation_error_count,
    )
    report: dict[str, Any] = {
        "@type": "MvpPackageReadiness",
        "generated_at": datetime.now(UTC).isoformat(),
        "readiness_status": readiness_status,
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "source_summary_json": str(summary_json),
        "source_review_queue_json": str(review_queue_json),
        "source_review_decisions_summary_json": str(review_decisions_summary_json),
        "source_vault_dir": str(vault_dir),
        "required_outputs": required_outputs,
        "missing_required_output_count": len(missing_required_outputs),
        "profile_count": len(profiles),
        "ready_profile_count": ready_profile_count,
        "profile_readiness": profile_readiness,
        "review_queue_item_count": review_queue_item_count,
        "review_decisions_status": review_status,
        "pending_review_count": pending_review_count,
        "invalid_review_count": invalid_review_count,
        "validation_error_count": validation_error_count,
        "publication_candidate_count": publication_candidate_count,
        "document_intake_blockers": document_intake_blockers,
        "blockers": blockers,
        "next_actions": _next_actions(readiness_status, blockers),
        "warnings": [
            "Il report e' preview-only e non modifica profili, claim o documenti.",
            "ready_for_demo indica solo che il pacchetto e' consultabile per una demo interna.",
            "La pubblicazione resta bloccata fino a revisione umana esplicita.",
        ],
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_package_readiness_markdown(report), encoding="utf-8")
    return report


def render_mvp_package_readiness_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Readiness pacchetto MVP",
        "",
        f"- Stato pacchetto: `{report.get('readiness_status', '')}`",
        f"- Stato revisione: `{report.get('review_status', '')}`",
        f"- Stato pubblicazione: `{report.get('publication_status', '')}`",
        f"- Profili pilota: `{report.get('profile_count', 0)}`",
        f"- Profili ready_for_review: `{report.get('ready_profile_count', 0)}`",
        f"- Item review queue: `{report.get('review_queue_item_count', 0)}`",
        f"- Candidati pubblicazione: `{report.get('publication_candidate_count', 0)}`",
        "",
        "## Output richiesti",
        "",
        "| Output | Tipo | Presente | Path |",
        "|---|---|---:|---|",
    ]
    for item in _list_items(report.get("required_outputs")):
        present = "si" if item.get("exists") else "no"
        lines.append(f"| `{item.get('label', '')}` | `{item.get('kind', '')}` | {present} | `{item.get('path', '')}` |")
    lines.extend(["", "## Blocker", ""])
    blockers = _list_items(report.get("blockers"))
    if blockers:
        for blocker in blockers:
            lines.append(f"- `{blocker.get('blocker_type', '')}`: {blocker.get('message', '')}")
    else:
        lines.append("_Nessun blocker pratico rilevato._")
    lines.extend(["", "## Prossime azioni", ""])
    next_actions = _list_strings(report.get("next_actions"))
    if next_actions:
        lines.extend(f"- {action}" for action in next_actions)
    else:
        lines.append("_Nessuna azione operativa richiesta dal report._")
    lines.extend(
        [
            "",
            "## Vincoli",
            "",
            "- Questo report non modifica file sorgenti, profili JSON-LD, claim o patch.",
            "- `ready_for_demo` non equivale a pubblicabile.",
            "- Le decisioni storiche e curatorali restano manuali.",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact(label: str, path: Path, kind: str) -> dict[str, Any]:
    exists = path.is_dir() if kind == "dir" else path.is_file()
    return {
        "@type": "MvpPackageArtifactCheck",
        "label": label,
        "path": str(path),
        "kind": kind,
        "exists": exists,
    }


def _document_intake_blockers(
    summary: dict[str, Any],
    intake_readiness: dict[str, Any],
    scorecard: dict[str, Any],
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for blocker in _list_strings(intake_readiness.get("mvp_blockers")):
        if _is_neutral_document_intake_message(blocker):
            continue
        blockers.append({"blocker_type": "document_intake", "message": blocker})
    for blocker in _list_strings(summary.get("mvp_blockers")):
        if _is_neutral_document_intake_message(blocker):
            continue
        blockers.append({"blocker_type": "document_intake", "message": blocker})
    package_status = str(scorecard.get("package_status", ""))
    if package_status in {"needs_document_intake", "document_intake_blocked"}:
        blockers.append(
            {
                "blocker_type": "document_intake",
                "message": f"pilot_package_scorecard.package_status={package_status}",
            }
        )
    return blockers


def _is_neutral_document_intake_message(message: str) -> bool:
    return message.startswith("Nessun blocco documentale evidente")


def _build_blockers(
    *,
    missing_required_outputs: list[dict[str, Any]],
    document_intake_blockers: list[dict[str, str]],
    review_queue_item_count: int,
    publication_candidate_count: int,
    review_status: str,
    invalid_review_count: int,
    validation_error_count: int,
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for item in missing_required_outputs:
        blockers.append(
            {
                "blocker_type": "missing_required_output",
                "message": f"Manca {item.get('label', '')}: {item.get('path', '')}",
            }
        )
    blockers.extend(document_intake_blockers)
    if review_queue_item_count <= 0:
        blockers.append(
            {
                "blocker_type": "review_material",
                "message": "La review queue non contiene item dimostrabili.",
            }
        )
    if publication_candidate_count <= 0:
        blockers.append(
            {
                "blocker_type": "review_material",
                "message": "Il vault non contiene schede candidate in 40_Publication_Candidates.",
            }
        )
    if review_status == "invalid" or invalid_review_count or validation_error_count:
        blockers.append(
            {
                "blocker_type": "review_material",
                "message": "Il riepilogo decisioni contiene errori o decisioni invalide.",
            }
        )
    return blockers


def _readiness_status(
    *,
    missing_required_outputs: list[dict[str, Any]],
    document_intake_blockers: list[dict[str, str]],
    review_queue_item_count: int,
    publication_candidate_count: int,
    review_status: str,
    invalid_review_count: int,
    validation_error_count: int,
) -> str:
    if missing_required_outputs:
        return MISSING_REQUIRED_OUTPUTS
    if document_intake_blockers:
        return NEEDS_DOCUMENT_INTAKE
    if review_queue_item_count <= 0 or publication_candidate_count <= 0:
        return NEEDS_REVIEW_MATERIAL
    if review_status == "invalid" or invalid_review_count or validation_error_count:
        return NEEDS_REVIEW_MATERIAL
    return READY_FOR_DEMO


def _next_actions(readiness_status: str, blockers: list[dict[str, str]]) -> list[str]:
    if readiness_status == READY_FOR_DEMO:
        return ["Aprire il vault MVP e usare il pacchetto per una demo interna guidata."]
    actions_by_type = {
        "missing_required_output": "Rigenerare gli step mancanti della pipeline MVP prima della demo.",
        "document_intake": "Completare intake, OCR o trascrizione dei documenti bloccanti.",
        "review_material": "Rigenerare review queue, decision summary o candidati di pubblicazione.",
    }
    actions: list[str] = []
    for blocker in blockers:
        action = actions_by_type.get(str(blocker.get("blocker_type", "")))
        if action and action not in actions:
            actions.append(action)
    return actions


def _count_markdown_files(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return sum(1 for item in path.glob("*.md") if item.is_file())


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
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


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un report di readiness del pacchetto MVP.")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--review-queue-json", required=True)
    parser.add_argument("--review-decisions-summary-json", required=True)
    parser.add_argument("--vault-dir", required=True)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    summary_json = Path(args.summary_json)
    run_dir = summary_json.parent.parent if summary_json.parent.name == "document_analysis" else summary_json.parent
    output_json = Path(args.output_json) if args.output_json else run_dir / "mvp_package_readiness.json"
    output_md = Path(args.output_md) if args.output_md else run_dir / "mvp_package_readiness.md"
    report = build_mvp_package_readiness(
        summary_json=summary_json,
        review_queue_json=Path(args.review_queue_json),
        review_decisions_summary_json=Path(args.review_decisions_summary_json),
        vault_dir=Path(args.vault_dir),
        output_json=output_json,
        output_md=output_md,
    )
    print(f"Readiness pacchetto MVP: {output_md}")
    print(f"Stato: {report['readiness_status']}")
    print(f"Output mancanti: {report['missing_required_output_count']}")
    print(f"Blocker: {len(report['blockers'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
