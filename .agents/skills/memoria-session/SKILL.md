---
name: memoria-session
description: Open or close a Me.Mo.Ri.A write session with a minimal task envelope.
---

# Me.Mo.Ri.A session

Use for write tasks or multi-step implementation. Pure read-only questions do
not need the full session workflow.

## Minimal input

Read `AGENTS.md`, then only the current-work/contract sections needed by the task.
Do not preload all roadmaps or playbooks.

## Task envelope

```yaml
mode: discovery-lite | scoped-fix | feature-slice | quality-slice | architecture-review
objective: una frase verificabile
repositories: []
read_set: []
write_set: []
test_command: ""
documentation_touchpoint: []
stop_conditions: []
```

Keep the read/write set small. Use `$memoria-model-router` once after this
envelope if the task needs delegation or model routing. Use `$memoria-planner`
only when persistent work state must change.

## OCR session boundary

For OCR reviews, follow the project procedure in
`memoria-bootstrap/docs/agent-session-prompt.md` and the document-analysis
playbook. Keep provisional auto-validation distinct from formal `machine_pass`.
The T42 provisional tuning is closed only for German / PP-OCRv5 /
`numbered_report`, with cutoff `1.0`; do not reopen it or extend it to another
scope without a changed user decision. If manual review exceeds 3% of a batch,
the CLI fails closed and the batch is blocked; do not describe it as completed
within the review cap.

## Stop condition

Stop before approving claims, changing canonical verified facts/profiles,
resolving historical conflicts, publishing records, exposing credentials, or
starting broad scraping without an explicit authorized increment.

## Close

Update only the persistent planner/notes and documentation actually affected by
the completed work. Report file changes, targeted tests, result and residual risk.
