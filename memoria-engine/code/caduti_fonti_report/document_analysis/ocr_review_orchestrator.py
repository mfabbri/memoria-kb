"""Single page-level OCR review preflight that composes every diagnostic gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from .ocr_alert_dispositions import audit_ocr_alert_dispositions
from .ocr_candidate_assessment import build_ocr_candidate_assessment
from .ocr_evidence_comparison import compare_ocr_page_evidence
from .ocr_page_layout import audit_ocr_page_layout
from .ocr_visual_review_ledger import audit_ocr_visual_review_ledger


def run_ocr_review(*, image_path: Path, evidence_path: Path, structure_path: Path,
                   markdown_path: Path, lexicon_review_path: Path, layout_path: Path,
                   ledger_path: Path, dispositions_path: Path,
                   comparison_path: Path, tesseract_evidence_path: Path) -> dict[str, Any]:
    """Recompute upstream audits and prepare only the residual human queue.

    All artifacts are read-only. A visual correction proposal blocks review
    preparation until the candidate and all dependent artifacts are regenerated.
    """
    paths = {"image": Path(image_path), "evidence": Path(evidence_path),
             "structure": Path(structure_path), "markdown": Path(markdown_path),
             "lexicon_review": Path(lexicon_review_path), "layout": Path(layout_path),
             "ledger": Path(ledger_path), "dispositions": Path(dispositions_path),
             "comparison": Path(comparison_path), "tesseract_evidence": Path(tesseract_evidence_path)}
    stages: list[dict[str, Any]] = []
    input_snapshot, input_issues = _snapshot_inputs(paths)
    if input_issues:
        stages.append({"stage": "input_snapshot", "status": "blocked", "issues": input_issues})
        return _blocked_report(paths, stages)
    stages.append({"stage": "input_snapshot", "status": "passed", "issue_count": 0, "issues": []})

    def failed_stage(name: str, exc: Exception) -> dict[str, Any]:
        return {"stage": name, "status": "blocked", "issues": [{"code": "stage_error",
                "detail": str(exc)}]}

    def append_stage(name: str, report: dict[str, Any], status_field: str = "processability_status") -> bool:
        checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
        issues = checks.get("issues") if isinstance(checks.get("issues"), list) else []
        passed = report.get(status_field) in ("diagnostic_only", "complete_for_declared_units") and not issues
        stages.append({"stage": name, "status": "passed" if passed else "blocked",
                       "issue_count": len(issues), "issues": issues})
        return passed

    try:
        _validate_evidence_comparison(paths, input_snapshot)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        stages.append(failed_stage("evidence_comparison", exc))
        return _blocked_report(paths, stages)
    stages.append({"stage": "evidence_comparison", "status": "passed", "issue_count": 0,
                   "issues": [], "diagnostic_only": True, "semantic_accuracy_status": "not_attested",
                   "auto_validation_enabled": False, "machine_pass": False})

    try:
        candidate = build_ocr_candidate_assessment(
            structure_path=paths["structure"], markdown_path=paths["markdown"],
            evidence_path=paths["evidence"], lexicon_review_path=paths["lexicon_review"],
            output_path=Path(tempfile.gettempdir()) / "ocr-review-assessment-preview.json", apply=False)
    except (OSError, ValueError, TypeError) as exc:
        stages.append(failed_stage("candidate_assessment", exc))
        return _blocked_report(paths, stages)
    if not append_stage("candidate_assessment", candidate):
        return _blocked_report(paths, stages, candidate_assessment=candidate)

    try:
        visual = audit_ocr_visual_review_ledger(
            ledger_path=paths["ledger"], image_path=paths["image"],
            evidence_path=paths["evidence"], structure_path=paths["structure"])
    except (OSError, ValueError, TypeError) as exc:
        stages.append(failed_stage("visual_audit", exc))
        return _blocked_report(paths, stages, candidate_assessment=candidate)
    if not append_stage("visual_audit", visual):
        return _blocked_report(paths, stages, candidate_assessment=candidate, visual_audit=visual)

    with tempfile.TemporaryDirectory(prefix="memoria-ocr-review-") as temporary:
        visual_path = Path(temporary) / "visual-audit.json"
        visual_path.write_text(json.dumps(visual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            layout = audit_ocr_page_layout(layout_path=paths["layout"], evidence_path=paths["evidence"],
                                           visual_audit_path=visual_path)
        except (OSError, ValueError, TypeError) as exc:
            stages.append(failed_stage("layout_audit", exc))
            return _blocked_report(paths, stages, candidate_assessment=candidate, visual_audit=visual)
        if not append_stage("layout_audit", layout):
            return _blocked_report(paths, stages, candidate_assessment=candidate,
                                   visual_audit=visual, layout_audit=layout)
        try:
            dispositions = audit_ocr_alert_dispositions(
                structure_path=paths["structure"], lexicon_review_path=paths["lexicon_review"],
                visual_audit_path=visual_path, ledger_path=paths["ledger"],
                dispositions_path=paths["dispositions"])
        except (OSError, ValueError, TypeError) as exc:
            stages.append(failed_stage("alert_dispositions", exc))
            return _blocked_report(paths, stages, candidate_assessment=candidate,
                                   visual_audit=visual, layout_audit=layout)
        if not append_stage("alert_dispositions", dispositions):
            return _blocked_report(paths, stages, candidate_assessment=candidate,
                                   visual_audit=visual, layout_audit=layout,
                                   alert_dispositions=dispositions)

    visual_inputs = visual.get("inputs", {})
    ledger_entry = visual_inputs.get("ledger", {}) if isinstance(visual_inputs, dict) else {}
    expected_ledger_digest = ledger_entry.get("digest") if isinstance(ledger_entry, dict) else None
    illegible_units = _visual_illegible_units(paths["ledger"], expected_ledger_digest)
    if illegible_units is None:
        stages.append({"stage": "visual_queue", "status": "blocked",
                       "issues": [{"code": "ledger_changed_after_visual_audit"}]})
        return _blocked_report(paths, stages, candidate_assessment=candidate,
                               visual_audit=visual, layout_audit=layout,
                               alert_dispositions=dispositions)
    stages.append({"stage": "review_queue", "status": "passed", "issue_count": 0, "issues": []})
    review_queue = _build_review_queue(dispositions, illegible_units)
    current_snapshot, input_issues = _snapshot_inputs(paths)
    if input_issues or current_snapshot != input_snapshot:
        stages.append({"stage": "input_integrity", "status": "blocked",
                       "issues": input_issues or [{"code": "input_changed_during_review"}]})
        return _blocked_report(paths, stages, candidate_assessment=candidate,
                               visual_audit=visual, layout_audit=layout,
                               alert_dispositions=dispositions)
    stages.append({"stage": "input_integrity", "status": "passed", "issue_count": 0, "issues": []})
    corrections = dispositions.get("counts", {}).get("correction_proposals", 0)
    if corrections:
        status = "correction_required"
        allowed = False
    elif review_queue:
        status = "needs_review"
        allowed = True
    else:
        status = "candidate_ready"
        allowed = False
    queue_output = review_queue if status == "needs_review" else []
    action_count: int | None = (len(review_queue) if status == "needs_review"
                                else 0 if status == "candidate_ready" else None)
    return {
        "@type": "OcrReviewPreparation", "schema_version": "1.0",
        "inputs": input_snapshot,
        "stages": stages, "status": status, "review_preparation_status": "ready" if status == "needs_review" else status,
        "human_review_queue": queue_output, "manual_action_count": action_count,
        "human_review_request_allowed": allowed,
        "counts": {"candidate_lexical_alerts": dispositions["counts"]["lexical_alerts"],
                   "visually_confirmed": dispositions["counts"]["visually_confirmed"],
                   "correction_proposals": corrections, "unresolved_lexical_alerts": dispositions["counts"]["unresolved"],
                   "visual_illegible_units": len(illegible_units)},
        "semantic_accuracy_status": "not_attested", "auto_validation_enabled": False,
        "machine_pass": False, "human_verified": False, "gold_promotion_allowed": False,
        "claim_extraction_allowed": False, "preview_only": True, "operation_status": "preview",
    }


def _validate_evidence_comparison(paths: dict[str, Path], snapshot: dict[str, dict[str, str]]) -> None:
    """Bind a diagnostic comparison to both current readings and the page image."""
    loaded = {name: json.loads(paths[name].read_text(encoding="utf-8"))
              for name in ("evidence", "tesseract_evidence", "comparison")}
    if any(not isinstance(value, dict) for value in loaded.values()):
        raise ValueError("OCR evidence and comparison must be JSON objects.")
    candidate, tesseract, report = (loaded[name] for name in ("evidence", "tesseract_evidence", "comparison"))
    if tesseract.get("engine") != "tesseract" or candidate.get("engine") != "paddle-ocr-v5":
        raise ValueError("Comparison requires PP-OCR (paddle-ocr-v5) and Tesseract readings.")
    if candidate.get("source_image_hash") != snapshot["image"]["digest"].removeprefix("sha256:"):
        raise ValueError("Comparison evidence does not identify the current image.")
    required_status = {"diagnostic_only": True, "machine_pass": False, "auto_validation_enabled": False,
                       "semantic_accuracy_status": "not_attested", "review_status": "unreviewed",
                       "promotion_status": "unreviewed"}
    if any(type(report.get(key)) is not type(value) or report.get(key) != value
           for key, value in required_status.items()) or report.get("operation_status") not in ("preview", "written"):
        raise ValueError("Comparison must retain diagnostic-only, unreviewed status.")
    inputs = report.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("Comparison requires source input provenance.")
    oriented = None
    for left_name, right_name in (("evidence", "tesseract_evidence"), ("tesseract_evidence", "evidence")):
        matches = True
        for side, name in (("left", left_name), ("right", right_name)):
            source = inputs.get(side)
            if not isinstance(source, dict) or not isinstance(source.get("path"), str):
                matches = False
                break
            # Comparison CLI paths are relative to its invocation directory,
            # just like the explicit paths supplied to this orchestrator.
            if (Path(source["path"]).resolve() != paths[name].resolve()
                    or source.get("sha256") != snapshot[name]["digest"].removeprefix("sha256:")):
                matches = False
                break
        if matches:
            oriented = (loaded[left_name], loaded[right_name])
            break
    if oriented is None:
        raise ValueError("Comparison source paths/digests do not match current evidence files.")
    expected = compare_ocr_page_evidence(left=oriented[0], right=oriented[1])
    # Recompute identities, geometry and diagnostic results. A current digest
    # alone does not establish that the report actually compared those inputs.
    if any(type(report.get(key)) is not type(value) or report.get(key) != value
           for key, value in expected.items()):
        raise ValueError("Comparison schema, evidence identities or diagnostic results are stale/incompatible.")


def _blocked_report(paths: dict[str, Path], stages: list[dict[str, Any]], **reports: dict[str, Any]) -> dict[str, Any]:
    return {"@type": "OcrReviewPreparation", "schema_version": "1.0",
            "inputs": _snapshot_inputs(paths)[0],
            "stages": stages, "status": "blocked", "review_preparation_status": "incomplete",
            "human_review_queue": [], "manual_action_count": None,
            "human_review_request_allowed": False,
            "diagnostics": {name: _report_summary(report) for name, report in reports.items()},
            "semantic_accuracy_status": "not_attested", "auto_validation_enabled": False,
            "machine_pass": False, "human_verified": False, "gold_promotion_allowed": False,
            "claim_extraction_allowed": False, "preview_only": True, "operation_status": "preview"}


def _snapshot_inputs(paths: dict[str, Path]) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    snapshots: dict[str, dict[str, str]] = {}
    issues: list[dict[str, str]] = []
    for name, path in paths.items():
        try:
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
            digest = "sha256:" + hasher.hexdigest()
            snapshots[name] = {"path": str(path), "digest": digest}
        except OSError:
            issues.append({"code": "unreadable_input", "input": name})
    return snapshots, issues


def _report_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {"processability_status": report.get("processability_status"),
            "checks": report.get("checks"), "counts": report.get("counts")}


def _visual_illegible_units(ledger_path: Path, expected_digest: Any) -> list[dict[str, Any]] | None:
    try:
        raw = ledger_path.read_bytes()
        if "sha256:" + hashlib.sha256(raw).hexdigest() != expected_digest:
            return None
        ledger = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    observations = ledger.get("observations") if isinstance(ledger, dict) else None
    return [row for row in observations if isinstance(row, dict) and row.get("outcome") == "illegible"] \
        if isinstance(observations, list) else []


def _build_review_queue(dispositions: dict[str, Any], illegible_units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for residual in dispositions.get("residual_groups", []):
        key = ("block", str(residual.get("block_id", "")))
        grouped[key] = {"unit_type": key[0], "unit_id": key[1],
                        "source_region_ids": residual.get("source_region_ids", []),
                        "residuals": list(residual.get("residuals", []))}
    # The orchestrator digest-checks the ledger against the visual audit before
    # adding unreadable units, avoiding a second unbound interpretation.
    for row in illegible_units:
        unit_type, unit_id = row.get("unit_type"), row.get("unit_id")
        if not isinstance(unit_type, str) or not isinstance(unit_id, str):
            continue
        key = (unit_type, unit_id)
        grouped.setdefault(key, {"unit_type": unit_type, "unit_id": unit_id,
                                 "source_region_ids": row.get("source_region_ids", []), "residuals": []})
        grouped[key]["residuals"].append({"kind": "visual_illegibility", "observation_id": row.get("observation_id")})
    return [grouped[key] for key in sorted(grouped)]
