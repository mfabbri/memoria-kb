# 01 Start Session

Carica solo il contesto necessario al task.

1. `AGENTS.md` e `memoria-bootstrap/planning/current-work.json`.
2. Se esiste lavoro persistente aperto, apri solo i riferimenti citati dal planner.
3. Se serve scegliere un nuovo incremento, usa `$memoria-roadmap-selector`, che
   cerca e apre solo le sezioni pertinenti delle roadmap.
4. Usa un solo playbook/skill verticale quando il task lo richiede.

Prima di modificare file devono essere chiari objective, write set, test minimo e
stop condition. Non leggere preventivamente tutte le roadmap, il decision log o
la golden run per modifiche che non li coinvolgono.
