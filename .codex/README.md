# Codex model routing per Me.Mo.Ri.A

## Runtime model policy

The parent thread is a low-cost router:

- parent/controller: `gpt-5.6-luna` / `medium`;
- discovery: mmr_scanner -> Luna / `low`;
- docs review: mmr_docs_reviewer -> Luna / `medium`;
- docs/planner/agent-config edits: mmr_docs_editor -> Luna / `medium`;
- implementation: mmr_implementer -> Terra / `medium`;
- quality review: mmr_test_reviewer -> Terra / `high`;
- architecture/migration: mmr_architect -> Sol / `high`.

Project-local `[profiles.*]` are not used. Codex ignores `profiles` in a
project-scoped `.codex/config.toml`.

## Two levels of traceability

1. `memoria-bootstrap/planning/current-work.json` records the intended route.
2. `.codex/hooks.json` records the actual runtime model for the parent and
   subagents in:
   `memoria-bootstrap/planning/.runtime/model-routing.ndjson`.

The runtime log is generated locally and ignored by Git.

## Hook trust

Project-local hooks must be reviewed/trusted by Codex after they change.
Use `/hooks` in Codex and trust the project hook definition.

## Delegation diagnostic

The project configuration makes specialized agents available; it does not
automatically create a subagent or select one from `current-work.json`. The
parent/controller must explicitly delegate the routed task. For an active
`high` route, absence of `SubagentStart` in the runtime audit means that the
mmr_architect was not invoked; the parent must stop rather than perform the
architecture review itself. This is an orchestrator/session capability, not a
TOML setting that can be repaired inside the repository.

## Validation

```powershell
python .\memoria-bootstrap\planning\validate-codex-model-routing.py
python -m json.tool .\memoria-bootstrap\planning\current-work.json
git diff --check
```
