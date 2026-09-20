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

Stato: T29-T33 completati; T34/T34b hanno chiuso la migrazione controllata dei profili legacy.

## Phase 2 — Historian workspace e document intelligence

Dashboard di revisione, decision trail, conflitti, patch controllate e
suggerimenti di nuove ricerche su un perimetro piu' ampio.

Priorita' corrente: T35-T40 per il flusso immagini/OCR:

```text
PP-OCRv5 structured evidence
  -> high-resolution crop/tiling
  -> deterministic DocumentStructure
  -> Markdown derivato
  -> reference e metriche
  -> eventuale VLM selettivo
  -> integrazione CLI
```

Il VLM non e' un sostituto page-level dell'OCR. PP-StructureV3 e Docling restano
comparativi, non dipendenze del percorso corrente.

## Phase 3 — Multi-source expansion

Wrapper online/offline, source registry, OCR profiles, cataloghi, scoring,
provenance avanzata e collaborazione con nuovi istituti.

## Phase 4 — Knowledge platform

Grafo interrogabile, API, storage pluggable, export pubblico selettivo,
governance dei dati e contributi storici revisionati.
