# Codex Task Router

## Scopo

Instradare ogni richiesta verso il minimo contesto utile.

## Regola principale

```text
Leggi session contract + current-next-increment.
Per T29-T33 leggi anche funding-demo-golden-path.
Aggiungi un solo playbook verticale core, solo se serve.
```

## Routing rapido

| Tipo richiesta | Modalita' | Playbook verticale |
|---|---|---|
| golden run / demo / finanziamento | `feature-slice` | `codex-document-analysis-core.md` o `codex-person-profile-feedback-loop-core.md` |
| trovare file/funzioni | `discovery-lite` | nessuno |
| fix test fallito | `scoped-fix` | verticale pertinente + quality gate |
| documenti, OCR, claim, ledger | `feature-slice` | `codex-document-analysis-core.md` |
| profili, merge, feedback, patch | `feature-slice` | `codex-person-profile-feedback-loop-core.md` |
| nuova fonte o YAML registry | `feature-slice` | `codex-source-registry-four-levels-core.md` |
| fonte dinamica/browser | `feature-slice` | `codex-playwright-dynamic-source-core.md` |
| Obsidian/export | `scoped-fix` | `codex-obsidian-export-core.md` |
| CLI o wrapper pubblici | `feature-slice` | verticale del dominio toccato |
| audit o micro-refactor | `quality-slice` | `09-continuous-refactor.md` |
| scelta tecnica/roadmap | `architecture-review` | nessuno |
| aggiornare playbook | `playbook-maintenance` | `codex-retrospective-update-process.md` |

## Vincolo di priorita'

Prima di T33, un task cloud, nuova fonte o Q2 deve dichiarare perche' e'
necessario alla golden run. In assenza di un blocco documentato, non e' il
prossimo incremento.

## Procedura

1. Leggere il current increment.
2. Classificare la richiesta.
3. Scegliere la modalita' da `codex-context-budget.md`.
4. Dichiarare 3-8 file minimi.
5. Indicare test, documentation touchpoint e impatto sulla golden run.
6. Eseguire il test piu' piccolo sufficiente.
7. Aggiornare guide solo se cambia comportamento operativo.
8. Aggiornare `current-next-increment.md` con stato e prossimo ID roadmap.

## Riepilogo finale obbligatorio

```text
Incremento:
Criteri soddisfatti:
Test/verifiche:
Impatto sulla golden run:
Documentation touchpoint:
Rischi residui:
Prossimo incremento roadmap:
```

## Escalation

Se il contesto non basta, dichiarare la domanda aperta e il solo file aggiuntivo
necessario. Non caricare tutte le run o tutte le guide per default.
