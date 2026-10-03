# Codex Task Router

## Routing canonico v3.0

| Tier | Richiesta | Agent | Modello / effort |
|---|---|---|---|
| `low` | trovare file/funzioni | `mmr_scanner` | GPT-6 Luna / low |
| `low` | verificare docs/contratti | `mmr_docs_reviewer` | GPT-6 Luna / low |
| `low` | modificare solo docs/planner/config agent | `mmr_docs_editor` | GPT-6 Luna / low |
| `medium` | fix/micro-feature runtime | `mmr_implementer` | GPT-6.1 Sol / medium |
| `review` | audit, regressione, edge case | `mmr_test_reviewer` | GPT-6.1 Sol / medium |
| `high` | architettura, migrazione, conflitti di contratto | `mmr_architect` | GPT-6 Astra / low |

Il parent GPT-6 Luna/low classifica, delega e sintetizza. Astra e riservato ai
problemi realmente high. Non alzare reasoning per accessi o contesto mancanti;
se il problema cambia natura, cambia tier in modo esplicito.

## Procedura minima

1. Delimita objective, read/write set, test e stop condition.
2. Esegui `$memoria-model-router` una sola volta per il task sostanziale.
3. Registra il routing nel planner prima della delega/write.
4. Delega al custom agent; non fare fan-out salvo workstream indipendenti.
5. Verifica diff e test mirati.
6. Registra escalation/fallback prima di cambiare modello/tier.
7. Aggiorna planner e solo i touchpoint documentali realmente impattati.

## Availability gate

`/model` mostra i modelli effettivamente disponibili. GPT-6.1 Sol puo essere in
rollout: se manca, il task non deve fingere di averlo usato. Registra il fallback
prima dell'esecuzione e conserva l'audit runtime separato.

## Execution gate per task runtime

Un task `medium` selezionato e un impegno di esecuzione nella sessione corrente.
Prima della risposta finale deve esistere almeno una di queste evidenze:

- diff runtime entro il write set e quality gate eseguito;
- blocco reale e riproducibile registrato nel planner;
- invalidazione del candidato da roadmap/decision log registrata.

Solo aggiornare planner o note non completa un task runtime.

## Chiusura

Verificare stato agente/blocco, `git diff`/`git status`, quality gate e planner.
Gli hook registrano separatamente il model slug effettivamente eseguito.
