# Agent Session Prompt

Prompt quotidiano consigliato, ridotto per Codex corrente:

```text
Lavora nel repository Me.Mo.Ri.A seguendo AGENTS.md.

Controlla memoria-bootstrap/planning/current-work.json. Se esiste lavoro
selected/in_progress ancora valido, riprendilo. Se serve scegliere un nuovo
micro-incremento, usa $memoria-roadmap-selector e apri solo le sezioni di roadmap
o decision log pertinenti.

Per un write task definisci un task envelope minimo con objective, repository,
read_set, write_set, test mirato e stop condition. Usa $memoria-model-router una
sola volta prima della delega/write e registra nel planner la route intenzionale.

Routing corrente:
- discovery/docs -> GPT-6 Luna / low;
- implementazione -> mmr_implementer / GPT-6.1 Sol / medium;
- quality review -> mmr_test_reviewer / GPT-6.1 Sol / medium;
- architettura/migrazione -> mmr_architect / GPT-6 Astra / low.

Usa un solo subagent per default. Passa path, simboli e criteri di accettazione,
non copie di file gia accessibili. Non aumentare reasoning per compensare
contesto, permessi o fonti mancanti. Se il modello richiesto non e disponibile,
registra il fallback prima di usare un modello diverso.

Implementa nella stessa sessione quando lo scope e eseguibile; altrimenti
registra un blocco reale. Dopo una delega verifica diff e quality gate mirato.
Aggiorna solo planner e documentazione realmente impattati.

Non approvare claim, non fondere profili, non promuovere verified facts e non
pubblicare schede senza review/autorizzazione esplicita.
```
