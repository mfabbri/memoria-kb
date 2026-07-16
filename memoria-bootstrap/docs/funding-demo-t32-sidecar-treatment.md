# T32 Sidecar Treatment

Data: 2026-07-16

Stato: sotto-incremento T32 completato e risolto con implementazione standard.
Nota aggiornata 2026-07-16: anche il blocco del pacchetto distribuibile esterno
e' stato trattato; T32 complessivo e' chiuso.

## Scope

Questo sotto-incremento verifica e documenta la dipendenza T30 dal sidecar
preview-only:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.t30-preview.json
```

Vincoli rispettati:

- nessuna scrittura nel data root esterno;
- nessuna rigenerazione di pipeline;
- nessun OCR o ricerca live;
- nessuna modifica a profili canonici;
- nessuna promozione di claim o verified facts;
- nessuna applicazione di `ProfilePatch`.

## Verifica read-only

Comando eseguito:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

Esito:

- descrittore attivo valido;
- status `ready_for_internal_demo`;
- run canonica `prova-preview-profili-5-reviewed-01-pipeline`;
- artefatto `ledger` puntato al sidecar T30
  `mvp_consolidated_review_ledger.t30-preview.json`;
- tutti gli artefatti T30/T31 dichiarati presenti;
- safety flag preview-only confermate:
  `applies_profile_patch=false`,
  `creates_canonical_verified_facts=false`,
  `modifies_canonical_profiles=false`,
  `publication_ready=false`.

Comando eseguito senza sidecar:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo-build `
  --data-root "P:\Comune\Me.Mo.Ri.a" `
  --run-id "prova-preview-profili-5-reviewed-01-pipeline"
```

Esito atteso e osservato:

- exit code `1`;
- readiness `blocked_for_internal_demo`;
- nessun output scritto;
- famiglie coperte senza sidecar: `partigiani_italia`;
- famiglie mancanti senza sidecar: `legacy_csv`, `local_docx`;
- documenti coperti senza sidecar: `2/4`;
- documenti mancanti:
  `legacy_csv:a4ac96061a2381b5` e
  `local_docx:4c2ad1d2ab937913`.

Diagnostica del blocco:

- `legacy_csv:a4ac96061a2381b5` e' presente nei profili demo selezionati ma
  non ha claim candidati nel ledger standard;
- `local_docx:4c2ad1d2ab937913` e' presente nei profili demo selezionati ma ha
  claim solo fuori dal perimetro dei profili demo selezionati;
- il piano di riallineamento preview propone:
  `produce_candidate_claims` per `legacy_csv` e
  `attach_existing_claims_to_demo_profile` per `local_docx`.

## Trattamento iniziale T32

Il sidecar T30 resta accettabile per la prova interna perche':

- e' dichiarato preview-only;
- aggiunge solo claim candidati `unreviewed`;
- marca i claim con `alignment_status=t30_preview_candidate`;
- non crea verified facts canonici;
- non applica patch;
- non modifica profili canonici;
- mantiene visibile la provenance e il fatto che si tratta di un ponte
  temporaneo.

Il sidecar non e' accettabile come percorso canonico per T33. Prima del
pacchetto finanziatori esterno bisogna sostituirlo o motivarlo come limite
esplicito non risolto. La sostituzione deve rigenerare lo stesso risultato dal
flusso standard:

```text
documenti/CSV/DOCX
  -> person linking
  -> candidate_evidence_claims
  -> evidence store
  -> consolidated ledger
```

## Criterio operativo

T32 puo' continuare a usare il sidecar per walkthrough interno e verifiche
read-only, ma non puo' essere chiusa come readiness esterna se il descrittore
attivo dipende ancora dal sidecar come artefatto `ledger`.

Per chiudere il tema in un incremento successivo servono almeno:

- claim candidati standard per `legacy_csv:a4ac96061a2381b5`;
- claim `local_docx:4c2ad1d2ab937913` ricondotti al profilo demo tramite il
  flusso standard, non tramite copia sidecar;
- `memoria mvp demo-build` senza `--ledger` e senza sidecar con readiness
  `ready_for_internal_demo`;
- assenza di nuovi verified facts canonici, patch applicate o modifiche ai
  profili canonici.

## Implementazione T32

Implementato in `memoria-engine` il riallineamento standard preview-only dentro
il builder del consolidated review ledger:

- da un link documento-persona senza claim viene creato un claim candidato
  `identity.canonical_name` con metodo
  `ledger_standard_from_candidate_document_person_link`;
- da un documento collegato al profilo demo ma con claim finiti fuori perimetro
  viene creata una proiezione candidata con metodo
  `ledger_standard_projection_from_linked_document_claim`;
- i claim restano `unreviewed` e marcati
  `ledger_derivation_status=standard_preview_candidate`;
- non vengono creati verified facts canonici;
- non vengono applicate patch;
- non vengono modificati profili canonici.

Validazione sintetica:

```powershell
cd memoria-engine
.\.venv\Scripts\python.exe -m unittest `
  tests.test_mvp_consolidated_review_ledger `
  tests.test_mvp_demo_descriptor
```

Esito: `16 tests`, `OK`.

Validazione sulla run canonica:

```powershell
cd memoria-engine
.\scripts\build_mvp_consolidated_review_ledger.ps1 `
  -RunDir "P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline" `
  -OutputJson "P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.t32-standard-preview.json" `
  -OutputMd "P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.t32-standard-preview.md"
```

Il ledger T32 standard preview ha superato `memoria mvp demo-build` senza
`--output-aligned-ledger` e senza usare il sidecar T30.

## Chiusura operativa

Sono stati creati backup prima della sostituzione:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.before-t32-standard.json
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.before-t32-standard.md
P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.before-t32-standard-ledger.json
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.before-t32-standard.md
```

Poi sono stati aggiornati:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.json
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_consolidated_review_ledger.md
P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json
P:\Comune\Me.Mo.Ri.a\risultati\runs\prova-preview-profili-5-reviewed-01-pipeline\mvp_demo_reconciliation_table.md
```

Verifica finale:

```powershell
cd memoria-engine
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\python.exe -m unittest `
  tests.test_mvp_consolidated_review_ledger `
  tests.test_mvp_demo_descriptor `
  tests.test_memoria_diagnostic_cli `
  tests.test_packaging
```

Esito:

- `memoria mvp demo` mostra il ledger standard
  `mvp_consolidated_review_ledger.json`, non il sidecar T30;
- status `ready_for_internal_demo`;
- famiglie coperte: `legacy_csv`, `local_docx`, `partigiani_italia`;
- documenti coperti: `4/4`;
- safety flag preview-only confermate;
- `66 tests`, `OK`.

## Impatto sulla golden run

La golden run ora non dipende piu' dal sidecar T30 come ledger attivo:

- demo interna: `ready_for_internal_demo` con ledger standard;
- flusso standard senza sidecar: sbloccato per il perimetro T32;
- pubblicazione: non pronta;
- T33: ora puo' partire perche' la chiusura complessiva di T32 e il blocco del
  pacchetto distribuibile esterno sono stati trattati.
