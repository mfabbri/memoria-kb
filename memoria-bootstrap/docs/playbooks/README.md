# Playbook e skill Codex — post-MVP

Entrypoint unico: `AGENTS.md` → stato `planning/current-work.json` → skill
selezionata. Il prompt quotidiano e' `docs/agent-session-prompt.md`.

- `$memoria-roadmap-selector`: se l'incremento e' chiuso, T45-T49.
- `$memoria-session`: task sostanziale multi-step, non typo.
- `$memoria-model-router`: solo se delega/cambio modello richiede routing.
- `$memoria-planner`: per creare/riprendere/chiudere lavoro persistente.
- Skill verticale (ad es. quality gate) e sezioni del playbook core solo quando
  il task ne dipende.

Parent Luna/low per task brevi, Sol/medium per code slice e review significativa,
Astra/low per architettura difficile. Nessun subagent obbligatorio. Non
precaricare storico, roadmap integrali o il lungo playbook OCR.

Le pagine `codex-*` sono riferimenti selettivi, non una checklist iniziale.
La procedura OCR dettagliata vive soltanto in
`codex-document-analysis-core.md`.
