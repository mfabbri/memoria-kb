# T32 Funding Demo Walkthrough Dry Run

Data: 2026-07-15

Stato: sotto-incremento T32 completato. Nota aggiornata 2026-07-16: il rischio
pacchetto distribuibile e il tema sidecar T30 sono stati trattati; T32
complessivo e' chiuso.

## Scope

Questo sotto-incremento verifica il percorso di walkthrough read-only della demo
finanziatori e corregge una discrepanza di run selection visibile durante la
prova asciutta.

Vincoli rispettati:

- nessuna scrittura nel data root esterno;
- nessuna pipeline, OCR o ricerca live;
- nessuna modifica a profili canonici;
- nessuna promozione di claim o verified fact canonici;
- nessuna applicazione di `ProfilePatch`.

## Checklist prova asciutta

| Passo | Comando o artefatto | Esito |
|---|---|---|
| Stato generale MVP | `memoria mvp status --data-root "P:\Comune\Me.Mo.Ri.a"` | OK: golden run visibile, `12/12` artefatti presenti |
| Descrittore demo | `memoria mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"` | OK: descriptor valido, T30/T31 presenti |
| Decisioni storiche | `memoria review decisions --data-root "P:\Comune\Me.Mo.Ri.a"` | OK: `114` decisioni, `10` sostanziali |
| Consolidamento | `memoria consolidate status --data-root "P:\Comune\Me.Mo.Ri.a"` | OK con avviso: sessione attiva diversa dalla golden run |
| Safety | output `mvp demo` e `mvp status` | OK: `preview_only=true`, `publication_ready=false` |

## Discrepanza rilevata

Durante la prova asciutta, `memoria consolidate status` leggeva correttamente la
sessione consolidate attiva, ma questa puntava a:

```text
mvp-candidate-profile-preview-index-v1-pipeline
```

mentre la demo finanziatori usa come golden run:

```text
prova-preview-profili-5-reviewed-01-pipeline
```

Questa differenza non modifica dati, ma poteva confondere il walkthrough T32
perche' due comandi read-only mostravano run diverse senza spiegazione.

## Correzione

Repository `memoria-engine`:

- `code/caduti_fonti_report/memoria_cli.py`
  - `memoria consolidate status` continua a mostrare la sessione consolidate
    attiva;
  - se esiste il descrittore demo, mostra anche `Demo golden run` con run
    canonica, status e conteggio artefatti presenti;
  - se la sessione attiva non coincide con la golden run, stampa una nota
    esplicita.

- `tests/test_memoria_diagnostic_cli.py`
  - il test di `consolidate status` copre il caso in cui sessione attiva e
    golden run differiscono.

## Verifiche eseguite

```powershell
cd memoria-engine
.\.venv\Scripts\python.exe -m unittest tests.test_memoria_diagnostic_cli tests.test_mvp_demo_descriptor tests.test_packaging
.\.venv\Scripts\memoria.exe mvp status --data-root "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe mvp demo --data-root "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe review decisions --data-root "P:\Comune\Me.Mo.Ri.a"
.\.venv\Scripts\memoria.exe consolidate status --data-root "P:\Comune\Me.Mo.Ri.a"
```

Esito:

- `56 tests`, `OK`;
- `mvp status` conferma `ready_for_internal_demo`,
  `prova-preview-profili-5-reviewed-01-pipeline`, `12/12` artefatti presenti,
  `preview_only=true`, `publication_ready=false`;
- `mvp demo` conferma gli artefatti T30/T31 e safety flag preview-only;
- `review decisions` conferma `10` decisioni storiche sostanziali;
- `consolidate status` segnala la sessione attiva diversa dalla golden run
  invece di lasciarla implicita.

## Stato residuo T32 al momento della prova

Al momento della prova T32 non era ancora chiuso.

Restano aperti:

- decidere il trattamento dei `58` profili JSON-LD legacy in
  `memoria-engine/ricerche/person_profiles` per il pacchetto distribuibile;
- chiudere o motivare esplicitamente la dipendenza dal sidecar T30
  `mvp_consolidated_review_ledger.t30-preview.json` rispetto al flusso
  standard;
- eventualmente registrare una prova generale temporizzata di 7-10 minuti
  usando questa checklist come traccia.

## Stato successivo

Il rischio del pacchetto distribuibile e il tema sidecar T30 sono stati chiusi
in sotto-incrementi successivi. T33 e' il prossimo incremento ordinario.
