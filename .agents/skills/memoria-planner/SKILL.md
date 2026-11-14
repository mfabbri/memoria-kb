---
name: memoria-planner
description: Gestisci il planner persistente all'avvio/chiusura di una slice, con backup, validazione e conservazione delle note storiche.
---

# Planner persistente

## Lettura e selezione

- Usa `python memoria-bootstrap/planning/current-work-summary.py` per la lettura
  quotidiana. Apri il JSON completo **solo quando devi aggiornarlo** oppure
  verificare una nota specifica: contiene molte sessioni storiche.
- Se stato `selected/in_progress`, valida dipendenze e stop condition;
  altrimenti seleziona una slice da `docs/current-focus.md` e roadmap tecnica.
- Non inferire la chiusura da `status`: controlla test e artefatti.
- Registra increment, roadmap_basis, routing v3.1, scope, out_of_scope, files,
  test, stop condition e next_action solo quando inizi davvero il task.

## Scrittura sicura

1. Preserva `current-work.json` e le note pregresse: prima crea backup byte-exact
   fuori da Git o in cartella ignorata. Mai rigenerare il planner dalla summary.
2. Su Windows PowerShell 5.1 imposta `$ErrorActionPreference = 'Stop'` e verifica
   parsing e forma prima di qualsiasi write (non usare `-AsHashtable`).
3. Serializza in un temporaneo, riparsalo e valida lo schema JSON, routing e
   campi prima di sostituire in modo controllato il file corrente.
4. Non cancellare `session_notes` o record routing preesistenti. Aggiungi una
   sola nota breve con evidenze/paths, non lunghe trascrizioni di sessione.
5. Dopo la sostituzione esegui
   `memoria-bootstrap/planning/validate-codex-model-routing.py` con `jsonschema`
   installato. Se la validazione è skipped, non considerarla riuscita.

## Chiusura

- `completed` + `recalculate` se il gate è passato;
- `in_progress` + `resume` per un task non concluso ma valido;
- `blocked` + `review`/`recalculate` con blocker verificabile;
- `superseded` + `recalculate` solo con decisione aggiornata esplicita.

Non aprire automaticamente il task successivo a fine sessione.
