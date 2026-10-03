# Developer Playbook

Entry point di sviluppo assistito per la workspace multi-repo Me.Mo.Ri.A.

## Repository map

- `memoria-bootstrap`: roadmap, decisioni, procedure e agent workflow;
- `memoria-engine`: Python package, CLI, pipeline, store, report e test;
- `memoria-workspace`: descriptor del workspace; dati reali esterni;
- `memoria-knowledge`: conoscenza storica, terminologia e modelli;
- `memoria-rules`: regole deterministiche, validazione e contratti LLM;
- `memoria-sources`: registry, strategie e logiche source-specific.

Workspace operativo reale: `P:\Comune\Me.Mo.Ri.a`.

## Start of session

Non usare una lista fissa di documenti da leggere.

1. Codex applica `AGENTS.md`.
2. Leggi `memoria-bootstrap/planning/current-work.json` per sapere se esiste un
   lavoro persistente da riprendere.
3. Apri roadmap, decision log, golden-path contract o playbook solo quando lo
   scope corrente ne dipende.
4. Prima del write definisci objective, repository, write set, test minimo e
   stop condition.

Per selezionare un nuovo incremento usa `$memoria-roadmap-selector`, che deve
cercare sezioni pertinenti invece di caricare roadmap complete.

## Regola di implementazione

Una sessione di modifica completa un solo micro-incremento verificabile. Un
incremento valido ha un confine esplicito, pochi file, un test/controllo mirato,
un touchpoint documentale solo se necessario e una stop condition.

## Repository selection

| Change type | Repository |
|---|---|
| CLI, Python package, tests, parsers, store, reports | `memoria-engine` |
| roadmap, decisions, agent workflow, demo contract | `memoria-bootstrap` |
| workspace manifest and provider descriptors | `memoria-workspace` |
| domain knowledge and terminology | `memoria-knowledge` |
| merge/provenance/review rules and LLM contracts | `memoria-rules` |
| source registry, strategy and source-specific logic | `memoria-sources` |

## Standard workflow

1. **Analyze**: conferma scope e repository; apri solo contratti pertinenti.
2. **Implement**: modifica il minimo e riusa contratti/pipeline esistenti.
3. **Test**: test offline mirato prima; regressione ampia solo se il rischio lo richiede.
4. **Document**: aggiorna planner/guide solo se il comportamento o il workflow cambia.
5. **Review**: verifica provenance, assenza di dati reali in Git e nessuna promozione automatica.

## Routing Codex

La policy attiva vive in `docs/model-routing-policy.md`:

```text
focused/docs       GPT-6 Luna / low
implementation     GPT-6.1 Sol / medium
quality review     GPT-6.1 Sol / medium
architecture       GPT-6 Astra / low
```

Non aumentare reasoning preventivamente. Se un task diventa ambiguo o
architetturale, fai escalation di tier invece di trasformare ogni review in una
sessione high-reasoning.

## Safety constraints

- Non copiare dati reali nei repository Git.
- Scritture sui dati reali solo nell'incremento esplicitamente autorizzato, con
  backup/audit quando il contratto lo richiede.
- Non salvare credenziali o segreti.
- Non fare scraping aggressivo, merge automatici o pubblicazione automatica.
- `no_results` non dimostra l'inesistenza di un fatto storico.
- Refactor ampi richiedono una decisione dedicata.
