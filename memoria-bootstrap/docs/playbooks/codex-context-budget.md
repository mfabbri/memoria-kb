# Codex Context Budget

| Modalità | Letture | Modifiche | Profilo predefinito |
|---|---:|---:|---|
| `discovery-lite` | max 10 file | 0 | `fast` |
| `scoped-fix` | max 20 file | max 5 | `standard` |
| `feature-slice` | max 30 file | max 8 | `standard` |
| `quality-slice` | file/test pertinenti | 0 salvo test | `fast` o `review` |
| `architecture-review` | contratti e sezioni mirate | docs only | `deep` |

## Riduzione del contesto

- usare `rg`, `rg --files` e ricerca per simbolo;
- leggere prima interfacce, test e contratti, poi implementazioni;
- delegare scansioni meccaniche a subagent `fast`;
- non caricare run, OCR, dataset o roadmap completi senza necessità;
- non duplicare nel prompt contenuti già presenti in `AGENTS.md` o nelle skill;
- riusare il task envelope nei passaggi implementazione, test e review.

## Escalation

Superare il budget solo dichiarando: domanda aperta, file già letti, file
aggiuntivi minimi e motivo.
