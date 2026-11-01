# Codex Task Router v3.1

Policy canonica: `memoria-bootstrap/docs/model-routing-policy.md`.

| Ambito | Modello/tier | Delega |
|---|---|---|
| Ricerca mirata, docs, micro-fix meccanico | parent GPT-6 Luna/low | No, di norma |
| Implementazione sostanziale, CLI, contratti | GPT-6.1 Sol/medium | Solo se il task e' separabile |
| Review indipendente motivata | GPT-6.1 Sol/medium | Opzionale, non rituale |
| Trade-off multi-repo complessi | GPT-6 Astra/low | Se la questione lo richiede |

Prima: scope e prova minima. Durante: contesto limitato, nessun fan-out salvo
workstream indipendenti. Dopo: test mirato, diff, planner e audit. Nuovi record
usano `policy_version: "3.1"`; non cambiare quelli storici. Verificare i modelli
con `/model`, nessun fallback silenzioso. Il task runtime termina con diff e
verifiche oppure con blocker riproducibile, non soltanto con nuove note.
