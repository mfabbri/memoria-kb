# Roadmap generale

Data: 2026-07-12

## Phase 0 — Refactor sicuro

Separare codice, workspace, fonti, conoscenza e regole mantenendo compatibilita'
con la pipeline esistente.

Stato: sostanzialmente completato.

## Phase 1 — MVP finanziatori: golden run tracciabile

Mostrare con un solo caso e una sola run:

```text
documenti offline e online
  -> evidenze con provenance
  -> riconciliazione multi-fonte
  -> merge/review dello storico
  -> scheda JSON-LD e patch preview
  -> feedback query
  -> nuova evidenza o no-result tracciato
```

Criteri obbligatori:

- almeno due fonti eterogenee nella stessa vista;
- conflitti e incertezze visibili;
- decisione storica registrata;
- nessun merge automatico sul canonico;
- almeno un feedback loop realmente chiuso;
- dossier e walkthrough collegati alla stessa golden run.

Priorita' corrente: T29-T33.

## Phase 2 — Historian workspace

Dashboard di revisione, decision trail, conflitti, patch controllate e
suggerimenti di nuove ricerche su un perimetro piu' ampio.

## Phase 3 — Multi-source expansion

Wrapper online/offline, source registry, OCR profiles, cataloghi, scoring,
provenance avanzata e collaborazione con nuovi istituti.

## Phase 4 — Knowledge platform

Grafo interrogabile, API, storage pluggable, export pubblico selettivo,
governance dei dati e contributi storici revisionati.
