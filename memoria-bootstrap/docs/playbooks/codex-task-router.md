# Codex Task Router

## Routing

| Richiesta | Profilo | Modalità | Skill/subagent |
|---|---|---|---|
| trovare file o funzioni | `fast` | `discovery-lite` | scanner |
| fix localizzato | `standard` | `scoped-fix` | implementer + test reviewer |
| micro-feature | `standard` | `feature-slice` | implementer + skill verticale |
| registry o nuova fonte | `standard` | `feature-slice` | `$memoria-source-registry` |
| feedback o patch profilo | `standard` | `feature-slice` | `$memoria-profile-feedback` |
| audit o regressione | `fast`/`review` | `quality-slice` | test reviewer |
| scelta architetturale | `deep` | `architecture-review` | scanner, poi review umana |
| sola documentazione | `fast` | `scoped-fix` | docs reviewer |

## Procedura

1. Crea il task envelope con `$memoria-session`.
2. Delega la ricognizione al subagent `scanner` quando il punto d'intervento non
   è noto.
3. Carica una sola skill verticale.
4. Implementa con il subagent `implementer` o nella sessione principale.
5. Esegui test mirato e review separata.
6. Controlla il documentation touchpoint.
7. Chiudi aggiornando la nota di incremento.

## Escalation

Usa il profilo `deep` soltanto quando il task attraversa più contratti, richiede
una migrazione o presenta un trade-off architetturale non già deciso. La sola
dimensione del repository non giustifica un reasoning elevato.
