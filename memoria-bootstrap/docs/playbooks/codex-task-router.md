# Codex Task Router

## Routing canonico

| Tier | Richiesta | Agent | Modello / effort |
|---|---|---|---|
| `low` | trovare file/funzioni | `mmr_scanner` | Luna / low |
| `low` | verificare docs/contratti | `mmr_docs_reviewer` | Luna / medium |
| `low` | modificare solo docs/planner/config agent | `mmr_docs_editor` | Luna / medium |
| `medium` | fix/micro-feature runtime | `mmr_implementer` | Terra / medium |
| `review` | audit, regressione, edge case | `mmr_test_reviewer` | Terra / high |
| `high` | architettura, migrazione, conflitti di contratto | `mmr_architect` | Sol / high |

Il parent Luna/medium classifica, delega e sintetizza. Non deve assorbire
direttamente task medium/review/high.

## Procedura

1. Crea il task envelope con `$memoria-session`.
2. Esegui `$memoria-model-router`.
3. Registra il routing intenzionale nel planner.
4. Delega al custom agent.
5. Attendi la restituzione del delegato; una delega pendente non è un risultato
   e non autorizza la risposta finale.
6. Controlla il diff effettivo nel worktree condiviso e verifica che resti nel
   `write_set`; non assumere che una patch sia stata applicata o integrata.
7. Esegui il quality gate pertinente, inclusi i test mirati e i controlli
   documentali richiesti.
8. Registra escalation/fallback prima di cambiare tier.
9. Aggiorna planner e documentation touchpoint con risultato, file modificati,
   test, rischi residui e prossimo passo; solo allora chiudi la sessione.

## Execution gate per task runtime

Uno stato `selected` o `in_progress` con tier `medium` e write set runtime e'
un impegno di esecuzione nella sessione corrente, non un risultato di planning.
Subito dopo il routing il parent deve avviare la delega oppure, se il subagent
non e' callable, registrare il fallback consentito ed eseguire direttamente lo
slice delimitato.

Prima della risposta finale deve esistere una delle sole tre evidenze seguenti:

- diff runtime entro il write set e quality gate eseguito;
- blocco reale, riproducibile e registrato nel planner;
- invalidazione del candidato da roadmap o decision log, anch'essa registrata.

Aggiornare solo planner, note o playbook non soddisfa questo gate. Non usare
`next_action: resume` per rinviare un task runtime eseguibile senza un blocco
reale: in quel caso la sessione resta aperta fino a esecuzione o blocco.

## Regola di chiusura

Il parent non può dichiarare un incremento completato, né presentare una
sessione come conclusa, se non ha verificato almeno:

- stato finale dell'agente o blocco documentato;
- `git diff`/`git status` e corrispondenza con il write set;
- quality gate passato o fallito esplicitamente;
- planner aggiornato con l'esito reale.

Se il risultato è solo documentale, va dichiarato come tale. Se il task
richiede codice ma il diff runtime è vuoto, la sessione resta `in_progress` o
`blocked`: non va chiusa come avanzamento dell'implementazione.

Gli hook Codex registrano separatamente il model slug effettivo.
