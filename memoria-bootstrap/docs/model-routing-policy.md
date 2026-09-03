# Model routing policy v2

Data: 2026-08-29

## Obiettivo

Routing Codex realmente multi-model e verificabile, con due livelli:

- decisione intenzionale versionata nel planner;
- modello effettivamente eseguito registrato localmente dagli hook.

Gli identificatori dei custom agent sono prefissati con `mmr_` per restare
univoci nel runtime Codex e coincidere tra configurazione, planner e trace.

## Policy

| Tier | Agent | Modello | Reasoning | Responsabilita' |
|---|---|---|---|---|
| router | parent | Luna | medium | classificare, delegare, sintetizzare |
| low | mmr_scanner | Luna | low | discovery read-only |
| low | mmr_docs_reviewer | Luna | medium | review documentale read-only |
| low | mmr_docs_editor | Luna | medium | docs/planner/config agent |
| medium | mmr_implementer | Terra | medium | codice e micro-feature |
| review | mmr_test_reviewer | Terra | high | quality/regr./provenance |
| high | mmr_architect | Sol | high | architettura/migrazioni |

## Audit runtime

Gli hook `SessionStart`, `SubagentStart` e `SubagentStop` registrano:
sessione, evento, model slug, agent type/id e permission mode.

Output locale:

```text
memoria-bootstrap/planning/.runtime/model-routing.ndjson
```

Il file non viene versionato.

## Guardrail

- nessun `[profiles.*]` project-local;
- nessuna escalation dovuta alla sola dimensione del repository;
- ogni fallback e' esplicito;
- niente chain-of-thought nel planner o nei log.
