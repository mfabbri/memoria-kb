---
name: memoria-model-router
description: Route a Me.Mo.Ri.A task to the smallest sufficient Codex agent/model.
---

# Me.Mo.Ri.A model router

Use once after scope/risk are clear and before delegation or substantive write.

| tier | task | agent | model | effort |
|---|---|---|---|---|
| low | discovery | mmr_scanner | gpt-6-luna | low |
| low | docs review | mmr_docs_reviewer | gpt-6-luna | low |
| low | docs/planner/agent config edit | mmr_docs_editor | gpt-6-luna | low |
| medium | runtime micro-increment | mmr_implementer | gpt-6.1-sol | medium |
| review | regression/provenance quality gate | mmr_test_reviewer | gpt-6.1-sol | medium |
| high | architecture/migration/contract conflict | mmr_architect | gpt-6-astra | low |

Decision order: architecture/migration -> high; independent quality review ->
review; runtime write -> medium; docs-only write/review -> low; otherwise scan
with low. Repository size alone never escalates a task.

Write `policy_version: 3.0` in new routing records. Record escalation/fallback
before changing tier/model. `/model` is authoritative for account availability;
do not silently replace an unavailable model.

Token discipline: one subagent by default, no duplicated file bodies, targeted
reads/tests, and no reasoning increase to compensate for missing access/context.
