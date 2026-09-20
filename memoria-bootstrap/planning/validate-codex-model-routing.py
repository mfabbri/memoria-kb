from __future__ import annotations
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXPECTED = {
    "mmr-scanner": ("gpt-5.6-luna", "low"),
    "mmr-docs-reviewer": ("gpt-5.6-luna", "medium"),
    "mmr-docs-editor": ("gpt-5.6-luna", "medium"),
    "mmr-implementer": ("gpt-5.6-terra", "medium"),
    "mmr-test-reviewer": ("gpt-5.6-terra", "high"),
    "mmr-architect": ("gpt-6-astra", "low"),
}

ROUTES_V20 = {
    "low": {
        ("mmr_scanner","gpt-5.6-luna","low"),
        ("mmr_docs_reviewer","gpt-5.6-luna","medium"),
        ("mmr_docs_editor","gpt-5.6-luna","medium"),
    },
    "medium": {("mmr_implementer","gpt-5.6-terra","medium")},
    "review": {("mmr_test_reviewer","gpt-5.6-terra","high")},
    "high": {("mmr_architect","gpt-5.6-sol","high")},
}

ROUTES_V21 = {
    **{key: value for key, value in ROUTES_V20.items() if key != "high"},
    "high": {("mmr_architect","gpt-6-astra","low")},
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
    configured_agent_keys = {key for key, value in ag.items() if isinstance(value, dict)}
    expected_agent_keys = {filename.replace("-", "_") for filename in EXPECTED}
    if configured_agent_keys != expected_agent_keys:
        fail(f"configured agent keys mismatch: {sorted(configured_agent_keys)}")

    for filename, expected in EXPECTED.items():
        p = ROOT/".codex/agents"/f"{filename}.toml"
        if not p.is_file():
            fail(f"agent config missing: {p.relative_to(ROOT)}")
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        if data.get("name") != filename.replace("-", "_"):
            fail(f"{filename} name mismatch")
        if (data.get("model"), data.get("model_reasoning_effort")) != expected:
            fail(f"{filename} model/effort mismatch")
        configured = ag.get(data["name"], {})
        if configured.get("config_file") != f"agents/{filename}.toml":
            fail(f"{filename} config_file mismatch")

    planner_path = ROOT/"memoria-bootstrap/planning/current-work.json"
    planner = json.loads(planner_path.read_text(encoding="utf-8"))
    active = planner.get("status") in {"selected","in_progress","blocked"}
    route = planner.get("routing")
    if active and not route:
        fail("active planner has no routing block")
    if route:
        policy_version = route.get("policy_version", "2.0")
        if active and policy_version != "2.1":
            fail("active planner must be re-routed with policy_version 2.1")
        routes = ROUTES_V21 if policy_version == "2.1" else ROUTES_V20
        tup = (route.get("agent"), route.get("model"), route.get("reasoning_effort"))
        if tup not in routes.get(route.get("tier"), set()):
            fail(f"unsupported planner route for policy {policy_version}: {route.get('tier')} {tup}")

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
    for hook_event in ("SessionStart", "SubagentStart", "SubagentStop"):
        if not hooks.get("hooks", {}).get(hook_event):
            fail(f"required hook event missing: {hook_event}")
    if not (ROOT/".codex/hooks/model-routing-audit.py").is_file():
        fail("runtime audit hook script missing")

    print("OK: Codex model routing v2.1 is structurally coherent")
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
