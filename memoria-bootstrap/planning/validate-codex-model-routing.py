from __future__ import annotations
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXPECTED = {
    "scanner": ("gpt-5.6-luna", "low"),
    "docs-reviewer": ("gpt-5.6-luna", "medium"),
    "docs-editor": ("gpt-5.6-luna", "medium"),
    "implementer": ("gpt-5.6-terra", "medium"),
    "test-reviewer": ("gpt-5.6-terra", "high"),
    "architect": ("gpt-5.6-sol", "high"),
}

ROUTES = {
    "low": {
        ("scanner","gpt-5.6-luna","low"),
        ("docs_reviewer","gpt-5.6-luna","medium"),
        ("docs_editor","gpt-5.6-luna","medium"),
    },
    "medium": {("implementer","gpt-5.6-terra","medium")},
    "review": {("test_reviewer","gpt-5.6-terra","high")},
    "high": {("architect","gpt-5.6-sol","high")},
}

def fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)

def main() -> int:
    cfg = tomllib.loads((ROOT/".codex/config.toml").read_text(encoding="utf-8"))
    if "profiles" in cfg:
        fail("project-local profiles present")
    if (cfg.get("model"), cfg.get("model_reasoning_effort")) != ("gpt-5.6-luna","medium"):
        fail("parent must be Luna/medium router")

    ag = cfg.get("agents", {})
    if ag.get("max_concurrent_threads_per_session") != 3:
        fail("max_concurrent_threads_per_session != 3")
    if "max_threads" in ag:
        fail("legacy max_threads still present")

    for filename, expected in EXPECTED.items():
        p = ROOT/".codex/agents"/f"{filename}.toml"
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        if (data.get("model"), data.get("model_reasoning_effort")) != expected:
            fail(f"{filename} model/effort mismatch")

    planner_path = ROOT/"memoria-bootstrap/planning/current-work.json"
    planner = json.loads(planner_path.read_text(encoding="utf-8"))
    active = planner.get("status") in {"selected","in_progress","blocked"}
    route = planner.get("routing")
    if active and not route:
        fail("active planner has no routing block")
    if route:
        tup = (route.get("agent"), route.get("model"), route.get("reasoning_effort"))
        if tup not in ROUTES.get(route.get("tier"), set()):
            fail(f"unsupported planner route: {route.get('tier')} {tup}")

    try:
        import jsonschema
    except ImportError:
        print("WARN: jsonschema not installed; schema validation skipped")
    else:
        schema = json.loads((ROOT/"memoria-bootstrap/planning/current-work.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(planner)

    for rel in [".agents/skills/memoria-model-router/SKILL.md",
                "memoria-bootstrap/planning/validate-codex-model-routing.py"]:
        try:
            r = subprocess.run(["git","check-ignore","-q",rel], cwd=ROOT)
            if r.returncode == 0:
                fail(f"required routing asset is ignored by git: {rel}")
        except FileNotFoundError:
            print("WARN: git not found; ignore validation skipped")

    hooks = json.loads((ROOT/".codex/hooks.json").read_text(encoding="utf-8"))
    if not (ROOT/".codex/hooks/model-routing-audit.py").is_file():
        fail("runtime audit hook script missing")

    print("OK: Codex model routing v2 is structurally coherent")
    if route:
        print(f"planner: tier={route['tier']} agent={route['agent']} model={route['model']} effort={route['reasoning_effort']}")

    runtime = ROOT/"memoria-bootstrap/planning/.runtime/model-routing.ndjson"
    if runtime.exists():
        lines = runtime.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
        print("runtime audit (last events):")
        for line in lines:
            try:
                e=json.loads(line)
                print(f"  {e.get('event')}: agent={e.get('agent_type')} model={e.get('model')}")
            except Exception:
                pass
    else:
        print("runtime audit: no events yet (trust hooks with /hooks, then run a session)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
