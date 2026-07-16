# T32 Funding Demo Hardening Readiness

Data: 2026-07-15

Stato: sotto-incremento T32 completato. Nota aggiornata 2026-07-16: walkthrough,
sidecar e rischio pacchetto distribuibile sono stati chiusi in sotto-incrementi
successivi; T32 complessivo e' chiuso.

## Scope

Questo sotto-incremento verifica e corregge la run selection read-only della
demo finanziatori senza rigenerare pipeline, senza rete live e senza scritture
nel data root.

Obiettivo puntuale:

- rendere `memoria mvp status` coerente con `memoria mvp demo`;
- mostrare la golden run canonica e i safety flag gia' dal comando di stato;
- verificare che gli artefatti T30/T31 siano presenti;
- avviare la verifica repository rispetto al vincolo "no real data in Git".

## Modifiche

Repository `memoria-engine`:

- `code/caduti_fonti_report/memoria_cli.py`
  - `inspect_mvp_demo_status` legge anche il descrittore
    `database/memoria_mvp_demo.active.json`;
  - `memoria mvp status` stampa una sezione `Golden run` con descriptor,
    status, run canonica, conteggio artefatti, `preview_only`,
    `publication_ready` e `publication_status`.

- `tests/test_memoria_diagnostic_cli.py`
  - il test di `mvp status` ora richiede che la golden run sia visibile nello
    status composito read-only.

## Verifiche eseguite

Comandi mirati:

```powershell
cd memoria-engine
.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli tests.test_mvp_demo_descriptor tests.test_packaging
.\.venv\Scripts\memoria.exe mvp status --data-root "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
```

Esito:

- `56 tests`, `OK`;
- `memoria mvp status` mostra:
  - descriptor presente e JSON valido;
  - status `ready_for_internal_demo`;
  - run canonica `prova-preview-profili-5-reviewed-01-pipeline`;
  - `12/12` artefatti dichiarati presenti;
  - `preview_only=true`;
  - `publication_ready=false`;
  - `publication_status=not_publishable_without_human_review`.
- `memoria mvp demo` conferma gli stessi artefatti T30/T31 e le safety flag:
  `applies_profile_patch=false`, `creates_canonical_verified_facts=false`,
  `modifies_canonical_profiles=false`.

## Verifica repository distribuibile

Scansione eseguita:

```powershell
Get-ChildItem -Path . -Recurse -File -Include *.pdf,*.doc,*.docx,*.jpg,*.jpeg,*.png,*.tif,*.tiff,*.jsonld,*.sqlite,*.db,*.log
```

Risultato:

- nessun PDF, DOC/DOCX, immagine, database SQLite o log corpus-like trovato nel
  workspace Git;
- trovati `58` profili JSON-LD legacy in
  `memoria-engine/ricerche/person_profiles`;
- trovati JSON-LD di fixture/test e knowledge versionabile gia' attesi.

Impatto T32: i profili JSON-LD legacy sono un rischio residuo per il pacchetto
distribuibile e devono essere esclusi, rimossi con incremento dedicato o
riclassificati prima della readiness esterna. Non sono stati modificati in
questo sotto-incremento.

## Limiti

- Nessun file del data root esterno e' stato scritto.
- Nessuna pipeline, OCR, ricerca live o generazione schede e' stata eseguita.
- La sostituzione del sidecar T30 con il flusso standard resta un lavoro T32
  ancora aperto o da motivare esplicitamente per il pacchetto interno.
- Il walkthrough di 7-10 minuti non e' ancora registrato come prova generale
  completa.

## Stato successivo

La prova asciutta del walkthrough, il trattamento sidecar e il pacchetto
distribuibile sono stati completati. Il prossimo incremento ordinario e' T33.
