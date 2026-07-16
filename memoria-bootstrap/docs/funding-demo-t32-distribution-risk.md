# T32 Distribution Risk Treatment

Data: 2026-07-16

Stato: sotto-incremento T32 completato e blocker distribuibile trattato; T32
puo' chiudersi insieme agli altri hardening gia' completati.

## Scope

Questo sotto-incremento tratta il rischio gia' rilevato nel pacchetto
distribuibile: la presenza di profili JSON-LD legacy nominativi nel repository
`memoria-engine`.

Vincoli rispettati:

- nessuna scrittura nel data root esterno;
- nessuna cancellazione o migrazione fisica di profili;
- nessuna modifica a profili canonici;
- nessuna pipeline, OCR o ricerca live;
- nessuna copia di dati reali nei repository.

## Esito della verifica

Verifica mirata:

```powershell
Get-ChildItem -Path memoria-engine\ricerche\person_profiles -Filter *.jsonld |
  Measure-Object
```

Esito:

- `58` profili JSON-LD legacy presenti in
  `memoria-engine/ricerche/person_profiles`;
- i file non sono necessari al package Python installabile, perche'
  `memoria-engine/pyproject.toml` limita il package discovery a `code`;
- il rischio resta rilevante per un archivio repository/workspace distribuibile,
  perche' la directory e' nel tree di lavoro.

## Trattamento T32

Decisione operativa per la readiness:

- il package Python installabile puo' restare verificabile con i test packaging
  esistenti;
- il tree locale non deve essere consegnato direttamente come pacchetto
  distribuibile;
- il pacchetto repository/workspace e' considerato distribuibile solo se
  prodotto tramite un archivio che rispetta `.gitattributes`;
- T33 non deve presentare un archivio repository completo se le regole
  `export-ignore` non sono applicate o verificate;
- l'esclusione/rimozione deve preservare il vincolo gia' chiuso in T13/T13b:
  i profili operativi ordinari sono letti dal data root esterno
  `P:\Comune\Me.Mo.Ri.a\ricerche\person_profiles`, non dal repository.

## Piano minimo per chiudere il rischio

Prima della readiness esterna scegliere uno dei due percorsi:

1. rimozione controllata dal repository dei profili legacy, se risultano
   versionati o inclusi nel pacchetto distribuibile, mantenendo solo riferimenti
   documentali e fixture sintetiche;
2. esclusione esplicita dall'archivio distribuibile, con checklist di packaging
   che verifichi l'assenza della directory e dei `*.jsonld` nominativi.

In entrambi i casi la verifica finale deve confermare:

```powershell
Get-ChildItem -Path <distribution-root> -Recurse -File -Include *.jsonld |
  Select-String -Pattern "person:purocielo:" -Quiet
```

Esito atteso per il pacchetto esterno: nessun match.

## Chiusura del rischio

Percorso scelto: esclusione esplicita dall'archivio distribuibile.

File aggiunto:

```text
.gitattributes
```

Regole:

```text
memoria-engine/ricerche/person_profiles/** export-ignore
memoria-engine/ricerche/caduti_purocielo.csv export-ignore
memoria-engine/ricerche/mvp/** export-ignore
```

Il tree di lavoro puo' ancora contenere i `58` profili legacy per continuita'
locale, ma un archivio Git/distribuibile configurato con queste regole non deve
includere i profili nominativi, il CSV Purocielo legacy o gli artefatti MVP
legacy sotto `memoria-engine/ricerche`.

Test di regressione aggiunto:

```text
memoria-engine/tests/test_packaging.py
```

Il test `test_distribution_archive_excludes_legacy_operational_data` fallisce
se le esclusioni vengono rimosse.

## Impatto sulla golden run

La golden run non cambia:

- descrittore attivo invariato:
  `P:\Comune\Me.Mo.Ri.a\database\memoria_mvp_demo.active.json`;
- run canonica invariata:
  `prova-preview-profili-5-reviewed-01-pipeline`;
- artefatti T30/T31 invariati;
- safety flag preview-only invariati.

Questo sotto-incremento non modifica la prova demo interna. Il pacchetto
distribuibile esterno non e' piu' bloccato dalla presenza dei profili legacy nel
tree locale, a condizione che venga prodotto tramite un archivio che rispetti
`.gitattributes`.

## Validazione

Validazioni eseguite:

```powershell
Get-Content memoria-bootstrap\docs\funding-demo-t32-distribution-risk.md
Get-ChildItem -Path memoria-engine\ricerche\person_profiles -Filter *.jsonld |
  Measure-Object
Get-Content memoria-engine\pyproject.toml
Get-Content .gitattributes
cd memoria-engine
.\.venv\Scripts\python.exe -m unittest tests.test_packaging
```

Esito:

- `58` profili JSON-LD legacy ancora presenti nel tree locale;
- esclusioni `export-ignore` presenti;
- `tests.test_packaging`: `19 tests`, `OK`;
- nessun file del data root esterno modificato.
