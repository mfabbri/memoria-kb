from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_quality_gate_baseline(
    *,
    output_dir: Path,
    run_id: str,
    test_suite: str,
    status: str,
    command: str,
    audit_output_json: str = "",
    audit_output_md: str = "",
    registry_validation_status: str = "not_recorded",
    source_quality_audit_status: str = "not_recorded",
    ruff_status: str = "not_run",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline = {
        "@type": "MvpQualityGateBaseline",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "unreviewed",
        "output_policy": "preview-only",
        "publication_status": "not_publishable_without_human_review",
        "run_id": run_id,
        "status": status,
        "test_suite": test_suite,
        "command": command,
        "registry_validation_status": registry_validation_status,
        "source_quality_audit_status": source_quality_audit_status,
        "ruff_status": ruff_status,
        "audit_output_json": audit_output_json,
        "audit_output_md": audit_output_md,
        "mvp_indicator": "quality_gate_targeted_green",
        "warnings": [
            "Baseline tecnica preview-only: non valida fatti storici.",
            "L'esito del gate riduce blocchi go/no-go ma non pubblica schede.",
        ],
    }
    json_path = output_dir / "quality_gate_baseline.json"
    md_path = output_dir / "quality_gate_baseline.md"
    json_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_quality_gate_baseline_markdown(baseline), encoding="utf-8")
    return {
        "@type": "MvpQualityGateBaselineBuild",
        "quality_gate_baseline_json": str(json_path),
        "quality_gate_baseline_md": str(md_path),
        "baseline": baseline,
    }


def render_quality_gate_baseline_markdown(baseline: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_quality_gate_baseline",
        f"review_status: {_yaml_value(baseline.get('review_status', 'unreviewed'))}",
        f"output_policy: {_yaml_value(baseline.get('output_policy', 'preview-only'))}",
        f"status: {_yaml_value(baseline.get('status', ''))}",
        "---",
        "",
        "# Baseline quality gate MVP",
        "",
        "Baseline preview-only del quality gate tecnico usato come evidenza go/no-go MVP.",
        "",
        "## Esito",
        "",
        f"- Stato: `{baseline.get('status', '')}`",
        f"- Suite test: `{baseline.get('test_suite', '')}`",
        f"- Run id: `{baseline.get('run_id', '')}`",
        f"- Indicatore MVP: `{baseline.get('mvp_indicator', '')}`",
        f"- Registry validation: `{baseline.get('registry_validation_status', '')}`",
        f"- Source quality audit: `{baseline.get('source_quality_audit_status', '')}`",
        f"- Ruff: `{baseline.get('ruff_status', '')}`",
        "",
        "## Comando",
        "",
        "```powershell",
        str(baseline.get("command", "")),
        "```",
        "",
        "## Output collegati",
        "",
        f"- Audit JSON: `{baseline.get('audit_output_json', '')}`",
        f"- Audit Markdown: `{baseline.get('audit_output_md', '')}`",
        "",
        "## Vincoli",
        "",
        "- Non modifica profili JSON-LD.",
        "- Non approva claim o fatti storici.",
        "- Non rende pubblicabile alcuna scheda senza revisione umana.",
        "",
    ]
    return "\n".join(lines)


def _yaml_value(value: object) -> str:
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera baseline preview-only del quality gate MVP.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--test-suite", required=True)
    parser.add_argument("--status", choices=["passed", "failed"], required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--audit-output-json", default="")
    parser.add_argument("--audit-output-md", default="")
    parser.add_argument("--registry-validation-status", default="not_recorded")
    parser.add_argument("--source-quality-audit-status", default="not_recorded")
    parser.add_argument("--ruff-status", default="not_run")
    args = parser.parse_args(argv)
    result = build_quality_gate_baseline(
        output_dir=Path(args.output_dir),
        run_id=args.run_id,
        test_suite=args.test_suite,
        status=args.status,
        command=args.command,
        audit_output_json=args.audit_output_json,
        audit_output_md=args.audit_output_md,
        registry_validation_status=args.registry_validation_status,
        source_quality_audit_status=args.source_quality_audit_status,
        ruff_status=args.ruff_status,
    )
    print(f"Quality gate baseline JSON: {result['quality_gate_baseline_json']}")
    print(f"Quality gate baseline Markdown: {result['quality_gate_baseline_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
