# Codex model routing per Me.Mo.Ri.A

## Runtime model policy

The parent thread is a low-cost router:

- parent/controller: `gpt-5.6-luna` / `medium`;
- discovery: scanner -> Luna / `low`;
- docs review: docs_reviewer -> Luna / `medium`;
- docs/planner/agent-config edits: docs_editor -> Luna / `medium`;
- implementation: implementer -> Terra / `medium`;
- quality review: test_reviewer -> Terra / `high`;
- architecture/migration: architect -> Sol / `high`.

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

## Validation

```powershell
python .\memoria-bootstrap\planning\validate-codex-model-routing.py
python -m json.tool .\memoria-bootstrap\planning\current-work.json
git diff --check
```
