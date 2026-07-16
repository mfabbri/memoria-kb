# Post-migration validation

Validated on: 2026-07-05

Scope: initial multi-repo migration validation for `D:\CaDiMalanca\me.mo.ri.a-kb`.

Hard constraints:

- [x] Real data must stay outside Git repositories.
- [x] External data root is `P:\Comune\Me.Mo.Ri.a`.
- [x] No migration or copy of real data was performed during this validation.
- [x] No write operation was performed under `P:\Comune\Me.Mo.Ri.a`.

## Documents read

- [x] `README.md`
- [x] `MIGRATION_PLAN.md`
- [x] `EXTERNAL_DATA_ROOT.md`
- [x] `memoria-bootstrap/AGENTS.md`
- [x] `memoria-bootstrap/docs/developer-playbook.md`
- [x] `memoria-bootstrap/docs/project-context.md`
- [x] `memoria-bootstrap/docs/repository-map.md`
- [x] `memoria-bootstrap/docs/current-next-increment.md`
- [x] `memoria-bootstrap/docs/playbooks/08-migration.md`
- [x] `memoria-bootstrap/docs/playbooks/04-testing.md`

## Layout

- [x] `memoria-bootstrap` exists
- [x] `memoria-engine` exists
- [x] `memoria-knowledge` exists
- [x] `memoria-rules` exists
- [x] `memoria-sources` exists
- [x] `memoria-workspace` exists
- [x] `memoria-bootstrap/memoria.code-workspace` exists

## Workspace descriptor

- [x] `memoria-workspace` contains descriptor files only in this validation scan
- [x] `memoria-workspace/manifest.yml` declares `repository_role: descriptor_only`
- [x] `memoria-workspace/manifest.yml` declares `data_root.type: external_path`
- [x] `memoria-workspace/manifest.yml` points to `P:\Comune\Me.Mo.Ri.a`
- [x] `memoria-workspace` scan found no `*.pdf`, images, `*.jsonld`, database, or log files

## External data root

Read-only `Test-Path` checks:

- [x] `P:\Comune\Me.Mo.Ri.a` exists
- [x] `P:\Comune\Me.Mo.Ri.a\risultati` exists
- [x] `P:\Comune\Me.Mo.Ri.a\documenti_da_processare` exists
- [x] `P:\Comune\Me.Mo.Ri.a\documenti_processati` exists
- [x] `P:\Comune\Me.Mo.Ri.a\docs` exists
- [x] `P:\Comune\Me.Mo.Ri.a\logs` exists
- [x] `P:\Comune\Me.Mo.Ri.a\ricerche` exists
- [x] `P:\Comune\Me.Mo.Ri.a\archivi` exists
- [x] `P:\Comune\Me.Mo.Ri.a\secure` exists
- [x] `P:\Comune\Me.Mo.Ri.a\database` exists

## Engine install/test

- [x] Existing Python virtualenv found at `memoria-engine/.venv`
- [x] `pip install -e .` completed
- [x] `pip install -e .` attempted
- [x] `pytest tests` completed
- [x] `pytest` completed with the project virtualenv active
- [x] `memoria-engine` build backend declares `wheel`
- [x] VS Code workspace points Python to `memoria-engine/.venv`
- [x] `memoria data-root` completed
- [x] `memoria inventory` completed
- [x] `memoria doctor` completed

Results:

- `.\.venv\Scripts\python.exe -m pip install -e .`
  - Result: completed after approved retry outside sandbox.
- `.\.venv\Scripts\python.exe -m pip install -e . --no-build-isolation`
  - Earlier result before approved build-isolation retry: failed with `error: invalid command 'bdist_wheel'`.
- `.\.venv\Scripts\python.exe -m pytest tests`
  - Result: `623 passed in 169.25s (0:02:49)`.
- `pytest`
  - Result with `.venv` active after diagnostic CLI increment: `629 passed in 182.63s (0:03:02)`.
  - Result without `.venv` active: command not found because `.venv\Scripts` is not in `PATH`.
- `memoria data-root`
  - Result: resolved `P:\Comune\Me.Mo.Ri.a` from `memoria-workspace/manifest.yml`.
- `memoria inventory`
  - Result: required top-level data-root folders present.
- `memoria doctor`
  - Result: data root, required folders, and sibling repositories present.

## Safety scan

- [x] No bulk real-data files detected in `memoria-workspace`
- [x] No PDF corpus detected in `memoria-workspace`
- [x] No OCR bulk output detected in `memoria-workspace`
- [x] No write to external data root performed

## Problems open

- [ ] A plain external shell still needs the virtualenv active, or `.venv\Scripts` on `PATH`, before `pytest` is available.
- [ ] `memoria-engine` still contains many relative legacy operational defaults such as `risultati`, `documenti_da_processare`, and `documenti_processati`; tests pass, but these should remain on the migration radar for path-resolution hardening.
