# Codex Task Router

## Routing canonico

| Tier | Richiesta | Agent | Modello / effort |
|---|---|---|---|
| `low` | trovare file/funzioni | `scanner` | Luna / low |
| `low` | verificare docs/contratti | `docs_reviewer` | Luna / medium |
| `low` | modificare solo docs/planner/config agent | `docs_editor` | Luna / medium |
| `medium` | fix/micro-feature runtime | `implementer` | Terra / medium |
| `review` | audit, regressione, edge case | `test_reviewer` | Terra / high |
| `high` | architettura, migrazione, conflitti di contratto | `architect` | Sol / high |

Il parent Luna/medium classifica, delega e sintetizza. Non deve assorbire
direttamente task medium/review/high.

## Procedura

1. Crea il task envelope con `$memoria-session`.
2. Esegui `$memoria-model-router`.
3. Registra il routing intenzionale nel planner.
4. Delega al custom agent.
5. Esegui il quality gate pertinente.
6. Registra escalation/fallback prima di cambiare tier.
7. Chiudi planner e documentation touchpoint.

Gli hook Codex registrano separatamente il model slug effettivo.
