# Persistent session planner

`current-work.json` conserva lo stato operativo minimo tra una sessione e la
successiva. Non sostituisce le roadmap e non è una backlog indipendente.

## Autorità

1. roadmap e decision log definiscono direzione e priorità;
2. `current-work.json` registra l'incremento selezionato e il suo avanzamento;
3. codice e test mostrano lo stato implementativo reale.

In caso di conflitto prevalgono roadmap, decisioni e stato verificabile del
repository. Il planner deve essere marcato `superseded` e ricalcolato.

## Ciclo

- `uninitialized`, `completed` o `superseded`: ricalcolare dalle roadmap;
- `selected` o `in_progress`: verificare che sia ancora valido e riprenderlo;
- `blocked`: non aggirare il blocco; scegliere un altro incremento solo se la
  roadmap lo consente e registrare la decisione;
- a fine sessione aggiornare test, risultato, note e `next_action`.

## Regole

- un solo incremento attivo;
- ogni incremento attivo registra il routing model/agent prima della delega;
- escalation e fallback aggiornano la routing trace senza salvare chain-of-thought;
- nessun fatto storico o decisione editoriale nel planner;
- percorsi relativi al repository;
- date ISO 8601 UTC;
- aggiornamenti piccoli e leggibili in diff;
- non riscrivere il file con una copia template durante gli aggiornamenti del
  pacchetto Codex.

La struttura è validabile con `current-work.schema.json`. Nel workspace
Me.Mo.Ri.A Windows, `jsonschema` è installato nel virtualenv
`memoria-engine/.venv` (versione `4.26.0`, verificata il 2026-10-03). Per
eseguire la validazione completa del planner e del routing, usare da root:

```powershell
& .\memoria-engine\.venv\Scripts\python.exe .\memoria-bootstrap\planning\validate-codex-model-routing.py
```

## Aggiornamento sicuro su Windows

`current-work.json` può contenere note locali non ancora salvate in Git. Prima
di riscriverlo, conservarne una copia byte-per-byte in una directory temporanea
ignorata da Git. Impostare `$ErrorActionPreference = 'Stop'` prima di leggere o
trasformare il JSON: Windows PowerShell 5.1 non supporta
`ConvertFrom-Json -AsHashtable` e un errore di parsing non intercettato può
lasciare `$null`, mentre gli statement successivi continuano.

Preparare la modifica in un file temporaneo; rileggerlo, validarlo contro
`current-work.schema.json` e verificare routing/status/ID prima di sostituire
l'originale con un rename atomico. Conservare il backup fino al passaggio del
validatore completo. In caso di errore non scrivere un JSON vuoto o parziale e
non ricostruire le note storiche da memoria quando esiste ancora una copia
recuperabile. Aggiornare solo i campi dell'incremento attivo e le note
strettamente pertinenti.
