# Migrazione ai workflow Codex ottimizzati

## Obiettivo

Ridurre token e ambiguità separando:

- regole globali in `AGENTS.md`;
- selezione del modello in `.codex/config.toml`;
- attività riusabili nelle skill;
- ricognizione, implementazione e review nei subagent;
- roadmap e decision log come fonti consultate in modo mirato.

## Cambiamenti inclusi

1. `AGENTS.md` diventa l'unico bootstrap globale.
2. I profili `fast`, `standard`, `deep` e `review` evitano l'uso indiscriminato
   del modello/reasoning più costoso.
3. Il task envelope conserva lo scope tra discovery, implementazione e review.
4. Le skill sostituiscono progressivamente i playbook verticali caricati a mano.
5. I subagent separano scansioni meccaniche e quality review dal lavoro
   implementativo principale.

## Compatibilità

Il pacchetto non elimina i playbook esistenti. Dopo 3-5 sessioni riuscite si può
spostare in `docs/playbooks/legacy/` quanto segue:

```text
01-start-session.md ... 09-continuous-refactor.md
codex-session-contract.md
codex-roadmap-task-selector.md
codex-*-core.md già coperti dalle skill
```

Prima di archiviare un file, verificare che non contenga una regola unica non
migrata. `codex-task-router.md`, `codex-context-budget.md` e il README sono già
aggiornati dal pacchetto.

## Validazione suggerita

Eseguire tre sessioni campione:

1. discovery read-only con profilo `fast`;
2. fix locale con profilo `standard` e test reviewer;
3. decisione multi-repository con profilo `deep`.

Per ciascuna verificare: numero di file letti, aderenza al task envelope,
assenza di espansione dello scope, test mirato e documentazione coerente.
