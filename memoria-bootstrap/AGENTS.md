# AGENTS.md — Me.Mo.Ri.A

Regole neutrali per qualsiasi coding agent.

## Prima di modificare file

1. Leggi `docs/project-context.md`.
2. Leggi `docs/roadmap/00-roadmap-master.md`.
3. Leggi `docs/roadmap/01-mvp-roadmap.md`.
4. Leggi `docs/roadmap/02-technical-roadmap.md`.
5. Leggi `docs/funding-demo-golden-path.md`.
6. Leggi `docs/current-next-increment.md`.
7. Leggi `docs/decision-log.md`.
8. Leggi un solo playbook pertinente in `docs/playbooks/`.
9. Identifica repository, acceptance criteria, test e stop condition.

## Priorita' corrente

Fino alla chiusura di T33, eseguire T29-T33 in ordine. Non scegliere cloud,
nuove fonti o micro-refactor come prossimo incremento ordinario, salvo richiesta
esplicita o blocco diretto della golden run.

## Principi

- Un incremento alla volta, piccolo e verificabile.
- Il codice non contiene dati storici reali.
- Il workspace Git e' descriptor-only; il corpus reale resta esterno.
- Il perimetro massimo di scrittura sui dati reali e'
  `P:\Comune\Me.Mo.Ri.a` con le sue sotto-cartelle, solo per incrementi
  documentati.
- La conoscenza documentata precede le regole deterministiche.
- Ogni claim conserva provenance, confidence e decision trail.
- Il merge multi-fonte conserva contributi e conflitti delle singole fonti.
- Una feedback action e' completa solo dopo ricerca ed esito registrato.
- Ogni cambiamento aggiorna current increment e documentazione pertinente.

## Ordine preferito per cambiamenti di conoscenza

```text
knowledge -> rules -> tests -> engine -> workspace sample -> report
```

## Non fare

- Non mescolare dati reali e codice.
- Non copiare run o profili operativi nei repository.
- Non scrivere dati reali fuori da `P:\Comune\Me.Mo.Ri.a`.
- Non cancellare OCR, JSON-LD o review senza migrazione esplicita.
- Non applicare patch ai profili canonici automaticamente.
- Non generare schede pubblicabili come obiettivo primario.
- Non interpretare `no_results` come prova dell'inesistenza di un fatto.
