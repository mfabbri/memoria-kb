# Playbook e skill Codex — post-MVP (2026-11-14)

Entrypoint operativo breve: `AGENTS.md` -> `docs/current-focus.md` ->
`python memoria-bootstrap/planning/current-work-summary.py`.
Prompt quotidiano: `docs/agent-session-prompt.md` (non duplicare il contenuto
nelle skill). Roadmap tecnica T53-T58 contiene i criteri di accettazione.

- `$memoria-roadmap-selector`: usa il focus se il planner è chiuso;
- `$memoria-session`: solo task sostanziali/multi-step;
- `$memoria-planner`: solo quando si apre/aggiorna/chiude lavoro persistente;
- `$memoria-model-router`: routing/delega solo per rischio o compito separabile;
- skill verticali e playbook di dominio **on-demand**.

Policy modelli v3.1 rimane attiva, condizionata a disponibilità effettiva;
nessun subagent obbligatorio. Hook opzionali soltanto se approvati in `/hooks`.
Non caricare integralmente il planner, le roadmap storiche o il lungo playbook
OCR in ogni sessione. Non usare T45-T49 come backlog aperto.
