---
name: memoria-planner
description: Maintain the persistent current-work state without replacing roadmap authority.
---

# Me.Mo.Ri.A persistent planner

Use this skill at session start and close.

## Start

1. Read `memoria-bootstrap/planning/current-work.json`.
2. Check the referenced files and repository state.
3. Resume only when status is `selected` or `in_progress`, the increment remains
   aligned with current roadmaps, and the stop condition is not already met.
4. Otherwise use `$memoria-roadmap-selector`, then record one micro-increment.
5. Never infer completion from planner text alone; verify code and tests.

## Selection record

Record:

- roadmap path and section;
- objective and explicit scope;
- routing tier, agent, model, reasoning effort and rationale;
- out-of-scope items;
- minimum candidate files;
- targeted tests and documentation touchpoints;
- objective stop condition;
- `next_action.mode = resume`.

## Close

Update status, verification result, concise notes, routing trace and next action:

- unfinished and valid: `in_progress` + `resume`;
- blocked: `blocked` + `review` or `recalculate`;
- stop condition met and tests acceptable: `completed` + `recalculate`;
- invalidated by newer decisions: `superseded` + `recalculate`.

Do not preload another implementation task at close. A candidate next step can
be noted, but the next session must validate it against the roadmap.
