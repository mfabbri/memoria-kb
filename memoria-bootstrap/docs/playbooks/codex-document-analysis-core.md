# Document Analysis Core

## Scopo

Guidare incrementi su OCR, registrazione documenti, chunking, menzioni,
candidate claim, ledger, review queue, riconciliazione multi-fonte, dataset
preview e output MVP.

## Principio

L'analisi documentale lavora su documenti acquisiti o referenziati. Non produce
fatti verificati senza review e non crea una pipeline parallela per la demo.

## Regole

- Non modificare raw archive, cache o documenti originali.
- Creare solo sidecar, inventari, processed output o report derivati.
- Ogni documento ha fonte, data accesso/riferimento e identificatore.
- Claim candidati sempre `unreviewed`.
- Import store append-only: non promuove claim e non modifica profili.
- `verified_facts.preview` deriva solo da decisioni approvate e resta preview.
- Dataset export e card snapshot restano preview finche' non esiste approvazione
  canonica/editoriale.
- MVP e wrapper aggregano la pipeline principale.

## Golden run multi-fonte

Per T29-T33:

- selezionare 2-4 documenti, non una scansione massiva;
- includere almeno due fonti/famiglie differenti;
- produrre una vista di riconciliazione che mantenga ogni claim separato;
- mostrare compatibilita', complementarita' o conflitto;
- collegare decisioni, verified facts e patch allo stesso `run_id` canonico;
- ridurre worklist e report al caso dimostrativo.

## File tipici

```text
memoria-engine/code/caduti_fonti_report/document_analysis/
memoria-engine/scripts/*document*.ps1
memoria-engine/scripts/*mvp*.ps1
memoria-engine/tests/test_*document*.py
memoria-engine/tests/test_*mvp*.py
```

## Test

Usare fixture offline, directory temporanee o DB SQLite temporaneo. Le run reali
possono essere lette solo in modalita' controllata e read-only quando
l'incremento lo richiede.
