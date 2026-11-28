---
name: memoria-roadmap-selector
description: Seleziona T85-T89 solo dopo verifica del planner e di un risultato storico misurabile.
---

# Selector source-first (2026-11-21)

1. Apri `memoria-bootstrap/docs/current-focus.md` + esegui
   `python memoria-bootstrap/planning/current-work-summary.py`.
2. Se il planner contiene lavoro `selected/in_progress`, confronta con le
   priorita' source-first; non riprendere automaticamente task superati.
   Se `completed` (T84 nello snapshot), leggi la sola sezione T85-T89
   di `docs/roadmap/02-technical-roadmap.md`.
3. Seleziona la prima slice non conclusa che porta nuovi SourceDocument,
   EvidenceClaim, link persone/luoghi/eventi, review umana o feedback reale.
   Un test addizionale fine a se stesso non costituisce incremento.
4. Prima della selezione registra limiti di accesso a data root, fonti,
   query/attempt, decisioni e requisiti di consenso; non inventare esiti.
5. Output: ID, artefatti attesi, dipendenze, write set minimo, test mirato,
   metrica e stop condition. Crea l'envelope persistente solo all'avvio.

T29-T84 sono storico; T41 OCR e T27/T28 pCloud sospesi.
La selezione non autorizza ricerche live, review o apply canonico.
