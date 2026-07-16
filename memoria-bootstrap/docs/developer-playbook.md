# Developer Playbook

This playbook is the entry point for agent-assisted development in the
Me.Mo.Ri.A multi-repository workspace.

## Repository map

- `memoria-bootstrap`: operating model, roadmap, playbooks, decisions and
  contracts;
- `memoria-engine`: Python package, CLI, pipelines, store, reports and tests;
- `memoria-workspace`: descriptor repository; real data remains external;
- `memoria-knowledge`: historical knowledge, terminology and models;
- `memoria-rules`: deterministic rules, validation and LLM contracts;
- `memoria-sources`: source registry, strategies and source-specific logic.

External data root:

```text
P:\Comune\Me.Mo.Ri.a
```

## Start of session

Read, in order:

1. `memoria-bootstrap/AGENTS.md`;
2. `docs/roadmap/00-roadmap-master.md`;
3. `docs/roadmap/01-mvp-roadmap.md`;
4. `docs/roadmap/02-technical-roadmap.md`;
5. `docs/funding-demo-golden-path.md`;
6. `docs/current-next-increment.md`;
7. `docs/decision-log.md`;
8. one relevant vertical playbook.

Do not implement code until the current increment and acceptance criteria are
clear.

## Current programme priority

The post-migration baseline is closed. The priority lane is T29-T33:

```text
T29 contract golden path
T30 canonical multi-source run
T31 closed historian feedback loop
T32 demo hardening
T33 funding package
```

Until T33 is closed:

- do not select cloud T26-T28 as the ordinary next step;
- do not select opportunistic Q2 work unless it removes a documented demo
  blocker;
- do not add sources unless the selected case cannot prove multi-source merge
  with material already available;
- do not broaden the pilot beyond the minimum case.

## Core implementation rule

One session completes one small, verifiable increment.

A valid increment has:

- one roadmap ID;
- explicit entry and exit criteria;
- a minimal file set;
- a focused test or read-only verification;
- a documentation touchpoint;
- a stop condition.

## Funding-demo invariants

Changes in T29-T33 must preserve:

- one canonical demo run;
- provenance for every historical claim;
- explicit multi-source reconciliation;
- visible conflicts and uncertainty;
- human review before verified facts;
- profile patches as preview/dry-run only;
- at least one feedback action executed to an auditable outcome;
- no automatic publication.

## Repository selection

| Change type | Repository |
|---|---|
| CLI, Python package, tests, parsers, store, reports | `memoria-engine` |
| roadmap, decisions, agent workflow, demo contract | `memoria-bootstrap` |
| workspace manifest and provider descriptors | `memoria-workspace` |
| domain knowledge and terminology | `memoria-knowledge` |
| merge/provenance/review rules and LLM contracts | `memoria-rules` |
| source registry, strategy and source-specific logic | `memoria-sources` |

## Standard workflow

1. **Analyze**
   - confirm the current increment;
   - identify the repository and minimal files;
   - identify how the change advances the golden run.

2. **Design**
   - define acceptance criteria;
   - record an architectural/methodological decision only when needed;
   - specify tests and data-root safety.

3. **Implement**
   - change the minimum;
   - prefer existing pipeline and store contracts;
   - do not create a parallel MVP pipeline.

4. **Test**
   - run focused offline tests first;
   - run wider regression tests when public behaviour changes;
   - use dry-run before any controlled write.

5. **Document**
   - update `current-next-increment.md`;
   - update golden-path artifact map or walkthrough when impacted;
   - update playbooks only when workflow or source-of-truth changes.

6. **Review**
   - confirm no real data entered Git;
   - confirm no preview was promoted to publishable;
   - confirm run, document, claim and decision IDs remain traceable.

## CLI direction

The installable Python CLI `memoria` is the future canonical cross-platform
surface. PowerShell remains an accepted compatibility surface for MVP write
workflows already validated on Windows. Do not delay the funding demo merely to
complete CLI migration.

## Continuous refactor lane

Use `docs/playbooks/09-continuous-refactor.md` only for small,
behaviour-preserving work. During T29-T33, a Q2 increment requires a direct link
to a demo blocker and focused regression tests.

## Safety constraints

- Do not copy real data into Git repositories.
- Operational writes are authorized only inside `P:\Comune\Me.Mo.Ri.a` and its
  subdirectories, and only when required by the current documented increment.
- Do not write outside `P:\Comune\Me.Mo.Ri.a` for real-data operations.
- Do not delete, overwrite massively, modify canonical profiles, apply profile
  patches, or promote canonical verified facts without a dedicated increment,
  backup and audit trail.
- Use fixture data for tests.
- Do not scrape aggressively.
- Do not save credentials or session secrets.
- Do not merge profile patches automatically.
- Do not infer that `no_results` disproves a historical fact.
