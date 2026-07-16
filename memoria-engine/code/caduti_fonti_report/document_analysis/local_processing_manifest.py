from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class StepManifestRecord:
    name: str
    started_at: str
    finished_at: str
    status: str
    outputs: list[str]
    signature: str = ""
    input_file_count: int = 0
    input_read_error_count: int | None = None
    input_delta: dict[str, Any] | None = None
    input_snapshot: list[dict[str, str]] | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "outputs": self.outputs,
            "signature": self.signature,
            "input_file_count": self.input_file_count,
            "input_delta": self.input_delta or {},
            "input_snapshot": self.input_snapshot or [],
        }
        if self.input_read_error_count is not None:
            payload["input_read_error_count"] = self.input_read_error_count
        if self.reason:
            payload["reason"] = self.reason
        return payload


def build_running_step_record(
    *,
    name: str,
    started_at: str,
    output_paths: list[Path],
    signature: str,
    input_snapshot: list[dict[str, str]],
    input_read_error_count: int,
    input_delta: dict[str, Any],
) -> dict[str, Any]:
    return StepManifestRecord(
        name=name,
        started_at=started_at,
        finished_at="",
        status="running",
        outputs=[str(path) for path in output_paths],
        signature=signature,
        input_file_count=len(input_snapshot),
        input_read_error_count=input_read_error_count,
        input_delta=input_delta,
        input_snapshot=input_snapshot,
    ).to_dict()


def build_skipped_step_record(
    *,
    name: str,
    started_at: str,
    finished_at: str,
    status: str,
    reason: str,
    output_paths: list[Path],
) -> dict[str, Any]:
    return StepManifestRecord(
        name=name,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        reason=reason,
        outputs=[str(path) for path in output_paths],
    ).to_dict()


def render_run_summary(manifest: dict[str, Any]) -> str:
    lines = [
        "# Local document processing run",
        "",
        f"- Run ID: `{manifest.get('run_id', '')}`",
        f"- Stato: `{manifest.get('status', '')}`",
        f"- Root dir: `{manifest.get('inputs', {}).get('root_dir', '')}`",
        f"- Processed dir: `{manifest.get('inputs', {}).get('processed_dir', '')}`",
        f"- Force derived: `{manifest.get('inputs', {}).get('force_derived', '')}`",
        f"- Force OCR: `{manifest.get('inputs', {}).get('force_ocr', '')}`",
        "",
        "## Step",
        "",
    ]
    for step in manifest.get("steps", []):
        if not isinstance(step, dict):
            continue
        lines.append(f"- `{step.get('name', '')}`: `{step.get('status', '')}`")
        if step.get("reason"):
            lines.append(f"  - Motivo: {step.get('reason')}")
        lines.append(f"  - Input: {step.get('input_file_count', 0)} file")
        if int(step.get("input_read_error_count", 0) or 0):
            lines.append(f"  - Errori lettura input: {step.get('input_read_error_count', 0)}")
        delta = step.get("input_delta", {})
        if isinstance(delta, dict) and delta:
            lines.append(
                "  - Delta input: "
                f"{delta.get('status', '')}, "
                f"aggiunti={delta.get('added_count', 0)}, "
                f"modificati={delta.get('modified_count', 0)}, "
                f"rimossi={delta.get('removed_count', 0)}"
            )
            for label, key in (("Aggiunti", "added"), ("Modificati", "modified"), ("Rimossi", "removed")):
                values = delta.get(key, [])
                if isinstance(values, list) and values:
                    joined = ", ".join(f"`{value}`" for value in values)
                    lines.append(f"  - {label}: {joined}")
        summary = step.get("summary", {})
        if isinstance(summary, dict) and summary:
            joined = ", ".join(f"{key}={_summary_value(value)}" for key, value in summary.items())
            lines.append(f"  - Summary: {joined}")
        if step.get("error"):
            lines.append(f"  - Errore: {step.get('error')}")
    lines.extend(
        [
            "",
            "## Note operative",
            "",
            "- Gli output automatici restano candidati di revisione.",
            "- Nessun profilo JSON-LD reale viene modificato.",
            "- Nessun claim viene promosso a fatto verificato.",
            "- Il wrapper locale delta non esegue ricerche online automatiche.",
            "",
        ]
    )
    return "\n".join(lines)


def duration_text(started_at: str, finished_at: str) -> str:
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return ""
    return f"{(finished - started).total_seconds():.2f}s"


def _summary_value(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(f"{key}: {value[key]}" for key in sorted(value)) + "}"
    return str(value)
