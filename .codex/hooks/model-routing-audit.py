from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

def find_root(cwd: Path) -> Path:
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".git").exists():
            return candidate
    return cwd

def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0

    root = find_root(Path(event.get("cwd") or ".").resolve())
    out = root / "memoria-bootstrap" / "planning" / ".runtime" / "model-routing.ndjson"
    out.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "session_id": event.get("session_id"),
        "turn_id": event.get("turn_id"),
        "event": event.get("hook_event_name"),
        "model": event.get("model"),
        "agent_id": event.get("agent_id"),
        "agent_type": event.get("agent_type"),
        "permission_mode": event.get("permission_mode"),
    }
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
