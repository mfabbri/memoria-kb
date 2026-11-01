# Daily Agent Procedure — post-MVP (2026-11-01)

1. `AGENTS.md` e stato di `memoria-bootstrap/planning/current-work.json`.
2. Se `completed`, selezionare con `$memoria-roadmap-selector` uno dei nuovi
   incrementi T45-T49; se `selected/in_progress`, verificarne solo le dipendenze.
3. Task envelope minimo: obiettivo, write set, test, stop condition e
   documentazione coinvolta. Nessuna lettura automatica di roadmap complete.
4. Parent diretto per task brevi. Router solo per cambio modello, delega
   sostanziale o review indipendente motivata. Un solo subagent per default.
5. Implementare una slice, eseguire i test mirati e il diff. Allargare solo se
   fallimento o rischio dimostrabile.
6. Aggiornare planner e soli documenti impattati. Report breve con il prossimo
   candidato, senza promozioni storiche automatiche.

Per OCR usare il playbook verticale, non incorporarne le procedure nel prompt
quotidiano. T42 provisional non equivale a validazione formale.
