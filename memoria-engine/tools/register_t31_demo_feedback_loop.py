from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = PROJECT_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from caduti_fonti_report.document_analysis.feedback_loop_outcome import build_feedback_loop_outcome
from caduti_fonti_report.document_analysis.feedback_search_plan import render_feedback_search_plan_markdown
from caduti_fonti_report.document_analysis.research_feedback_triage import render_research_feedback_actions_review_summary


RUN_ID = "prova-preview-profili-5-reviewed-01-pipeline"
ACTION_ID = "research-feedback-action:7bdbb2060d955baa"
PLAN_ID = "feedback-search-plan:a19b13e6e3cd8b0d"
PROFILE_ID = "person:purocielo:andreoli-dino"
SOURCE_DOCUMENT_ID = "legacy_csv:a4ac96061a2381b5"
SOURCE_ID = "storia_memoria_bo"


def main() -> int:
    parser = argparse.ArgumentParser(description="Registra gli artefatti preview-only T31 per la golden run demo.")
    parser.add_argument("--data-root", default=r"P:\Comune\Me.Mo.Ri.a")
    parser.add_argument("--run-id", default=RUN_ID)
    args = parser.parse_args()

    data_root = Path(args.data_root)
    run_dir = data_root / "risultati" / "runs" / args.run_id
    document_analysis_dir = run_dir / "document_analysis"
    historian_dir = run_dir / "historian_review"
    database_dir = data_root / "database"
    for path in [run_dir, document_analysis_dir, historian_dir, database_dir]:
        if not path.exists():
            raise SystemExit(f"Missing expected path: {path}")
        _assert_inside(path, data_root)

    now = datetime.now(UTC).isoformat()
    summary_path = document_analysis_dir / "mvp_pilot_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    action = _find_by_id(summary.get("research_feedback_actions", []), "action_id", ACTION_ID)
    plan = _find_by_id(summary.get("feedback_search_plans", []), "feedback_search_plan_id", PLAN_ID)
    if action is None:
        raise SystemExit(f"Action not found: {ACTION_ID}")
    if plan is None:
        raise SystemExit(f"Plan not found: {PLAN_ID}")

    plan_json, plan_md = _write_plan_sidecar(
        document_analysis_dir=document_analysis_dir,
        data_root=data_root,
        summary_path=summary_path,
        plan=plan,
        generated_at=now,
    )
    review_table_md, review_summary_json, review_summary_md = _write_review_sidecars(
        historian_dir=historian_dir,
        data_root=data_root,
        summary_path=summary_path,
        action=action,
        generated_at=now,
    )
    outcome_json = historian_dir / "feedback_loop_outcome.t31-demo.json"
    outcome_md = historian_dir / "feedback_loop_outcome.t31-demo.md"
    for path in [outcome_json, outcome_md]:
        _assert_inside(path, data_root)

    query = 'nome-cognome; nom="Dino"; cog="Andreoli" | testo-libero-nome-completo; s="Dino Andreoli"'
    notes = (
        "Sessione manuale tracciata T31: il piano fonte-specifico su "
        "storia_memoria_bo e partigiani_italia richiede revisione manuale "
        "prima di acquisire nuovi claim; nessun fatto viene promosso e nessun "
        "profilo canonico viene modificato."
    )
    outcome = build_feedback_loop_outcome(
        feedback_plan_json=plan_json,
        review_summary_json=review_summary_json,
        action_id=ACTION_ID,
        plan_id=PLAN_ID,
        source_id=SOURCE_ID,
        outcome_status="needs_manual_review",
        execution_mode="manual_review_session",
        query=query,
        result_source_document_ids=[],
        notes=notes,
        run_id=args.run_id,
        executed_at=now,
        output_json=outcome_json,
        output_md=outcome_md,
    )
    if outcome.get("loop_status") != "closed_with_auditable_outcome":
        raise SystemExit(f"Unexpected loop status: {outcome.get('loop_status')}")

    descriptor_path, backup_path = _update_descriptor(
        data_root=data_root,
        run_id=args.run_id,
        generated_at=now,
        query=query,
        outcome=outcome,
        review_table_md=review_table_md,
        review_summary_json=review_summary_json,
        plan_json=plan_json,
        outcome_json=outcome_json,
        outcome_md=outcome_md,
    )

    print(
        json.dumps(
            {
                "loop_status": outcome.get("loop_status"),
                "outcome_status": outcome.get("outcome_status"),
                "files": [
                    str(plan_json),
                    str(plan_md),
                    str(review_table_md),
                    str(review_summary_json),
                    str(review_summary_md),
                    str(outcome_json),
                    str(outcome_md),
                    str(descriptor_path),
                    str(backup_path),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _write_plan_sidecar(
    *,
    document_analysis_dir: Path,
    data_root: Path,
    summary_path: Path,
    plan: dict[str, Any],
    generated_at: str,
) -> tuple[Path, Path]:
    plan_set = {
        "@type": "FeedbackSearchPlanSet",
        "generated_at": generated_at,
        "source_mvp_pilot_summary": str(summary_path),
        "generation_method": "t31_demo_single_plan_selection_from_existing_preview",
        "review_status": "reviewed_for_demo",
        "execution_allowed": False,
        "online_search_started": False,
        "profile_write_allowed": False,
        "plan_count": 1,
        "skipped_count": 0,
        "plans": [plan],
        "skipped_actions": [],
        "warnings": [
            "t31_demo_plan_selection_preview_only",
            "requires_manual_review_before_any_claim_promotion",
        ],
    }
    plan_json = document_analysis_dir / "feedback_search_plan.t31-demo.json"
    plan_md = document_analysis_dir / "feedback_search_plan.t31-demo.md"
    _write_json(plan_json, plan_set, data_root=data_root)
    _write_text(plan_md, render_feedback_search_plan_markdown(plan_set), data_root=data_root)
    return plan_json, plan_md


def _write_review_sidecars(
    *,
    historian_dir: Path,
    data_root: Path,
    summary_path: Path,
    action: dict[str, Any],
    generated_at: str,
) -> tuple[Path, Path, Path]:
    decision_record = {
        "@type": "ResearchFeedbackActionTriageDecision",
        "row": 1,
        "decision_status": "accepted",
        "decision": "BUONA",
        "action_id": ACTION_ID,
        "value": str(action.get("value", "ANDREOLI DINO")),
        "source_document_id": SOURCE_DOCUMENT_ID,
        "suggested_sources": ["storia_memoria_bo", "partigiani_italia"],
        "notes": "Azione selezionata per la demo T31: richiede verifica manuale fonte-specifica prima di qualunque nuovo claim.",
        "review_status": "reviewed_for_demo",
        "person_id": PROFILE_ID,
        "chunk_id": str(action.get("chunk_id", "")),
        "weak_segment_id": str(action.get("weak_segment_id", "")),
        "priority": str(action.get("priority", "medium")),
        "risk": str(action.get("risk", "medium")),
    }
    review_summary = {
        "@type": "ResearchFeedbackActionReviewSummary",
        "generated_at": generated_at,
        "source_actions_json": str(summary_path),
        "source_review_table_md": str(historian_dir / "research_feedback_actions_review_table.md"),
        "review_status": "reviewed",
        "action_count": 1,
        "row_count": 1,
        "accepted_count": 1,
        "pending_count": 0,
        "invalid_count": 0,
        "validation_error_count": 0,
        "counts_by_decision": {"BUONA": 1},
        "validation_errors": [],
        "decisions": [decision_record],
        "accepted_by_decision": {"BUONA": [decision_record]},
        "warnings": [
            "t31_demo_triage_summary_is_audit_only",
            "decision_does_not_create_verified_facts",
            "decision_does_not_modify_profiles",
        ],
    }
    review_summary_json = historian_dir / "research_feedback_actions_review_summary.t31-demo.json"
    review_summary_md = historian_dir / "research_feedback_actions_review_summary.t31-demo.md"
    review_table_md = historian_dir / "research_feedback_actions_review_table.t31-demo.md"
    _write_json(review_summary_json, review_summary, data_root=data_root)
    _write_text(review_summary_md, render_research_feedback_actions_review_summary(review_summary), data_root=data_root)
    _write_text(review_table_md, _render_review_table(decision_record), data_root=data_root)
    return review_table_md, review_summary_json, review_summary_md


def _update_descriptor(
    *,
    data_root: Path,
    run_id: str,
    generated_at: str,
    query: str,
    outcome: dict[str, Any],
    review_table_md: Path,
    review_summary_json: Path,
    plan_json: Path,
    outcome_json: Path,
    outcome_md: Path,
) -> tuple[Path, Path]:
    descriptor_path = data_root / "database" / "memoria_mvp_demo.active.json"
    backup_path = data_root / "database" / "memoria_mvp_demo.active.before-t31-feedback-loop.json"
    _assert_inside(descriptor_path, data_root)
    _assert_inside(backup_path, data_root)
    descriptor_text = descriptor_path.read_text(encoding="utf-8")
    if not backup_path.exists():
        backup_path.write_text(descriptor_text, encoding="utf-8")
    descriptor = json.loads(descriptor_text)
    descriptor["updated_at"] = generated_at
    descriptor.setdefault("artifacts", {}).update(
        {
            "feedback_action_review_table": str(review_table_md),
            "feedback_action_review_summary": str(review_summary_json),
            "feedback_search_plan": str(plan_json),
            "feedback_outcome": str(outcome_json),
            "feedback_outcome_markdown": str(outcome_md),
        }
    )
    descriptor["t31_feedback_loop"] = {
        "status": outcome.get("loop_status"),
        "outcome_status": outcome.get("outcome_status"),
        "research_feedback_action_id": ACTION_ID,
        "feedback_search_plan_id": PLAN_ID,
        "feedback_loop_outcome_id": outcome.get("feedback_loop_outcome_id"),
        "profile_id": PROFILE_ID,
        "source_document_id": SOURCE_DOCUMENT_ID,
        "source_id": SOURCE_ID,
        "execution_mode": outcome.get("execution_mode"),
        "query": query,
        "preview_only": True,
        "creates_verified_facts": False,
        "applies_profile_patch": False,
        "modifies_canonical_profiles": False,
    }
    note = (
        "T31 feedback loop chiuso con esito preview-only needs_manual_review; "
        "nessun claim promosso e nessun profilo canonico modificato."
    )
    descriptor.setdefault("notes", [])
    if note not in descriptor["notes"]:
        descriptor["notes"].append(note)
    _write_json(descriptor_path, descriptor, data_root=data_root)
    return descriptor_path, backup_path


def _render_review_table(decision: dict[str, Any]) -> str:
    return (
        "# ResearchFeedbackAction triage table T31 demo\n\n"
        "Tabella audit-only ridotta alla singola azione T31. Non valida fatti, "
        "non modifica profili e non crea claim verificati.\n\n"
        "| decisione | valore | action_id | documento | fonti_suggerite | indizi | contesto | note_storico |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        f"| BUONA | {decision['value']} | {ACTION_ID} | {SOURCE_DOCUMENT_ID} | "
        "storia_memoria_bo, partigiani_italia | person_name: ANDREOLI DINO; "
        "formation: 36a Brigata; place: Bologna; place: Purocielo | "
        f"intestazione_pdf: ANDREOLI DINO | {decision['notes']} |\n"
    )


def _find_by_id(items: Any, key: str, expected: str) -> dict[str, Any] | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get(key) == expected:
            return item
    return None


def _write_json(path: Path, payload: dict[str, Any], *, data_root: Path) -> None:
    _assert_inside(path, data_root)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str, *, data_root: Path) -> None:
    _assert_inside(path, data_root)
    path.write_text(text, encoding="utf-8")


def _assert_inside(path: Path, data_root: Path) -> None:
    resolved_root = data_root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        raise SystemExit(f"Refusing to write outside workspace: {resolved}")


if __name__ == "__main__":
    raise SystemExit(main())
