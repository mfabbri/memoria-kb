# memoria-engine

Codice riutilizzabile di Me.Mo.Ri.A. Non contiene dati reali.

## Moduli previsti

- CLI `memoria`
- OCR orchestration
- document ingestion
- chunking
- extraction orchestration
- graph/jsonld writer
- review dashboard generator
- reporting
- validation

## Dipendenze sibling

Percorsi di default:

- `../memoria-workspace`
- `../memoria-rules`
- `../memoria-knowledge`
- `../memoria-sources`

Override tramite variabili:

- `MEMORIA_WORKSPACE_PATH`
- `MEMORIA_RULES_PATH`
- `MEMORIA_KNOWLEDGE_PATH`
- `MEMORIA_SOURCES_PATH`

## CLI diagnostica minima

Dopo l'installazione editable, il comando `memoria` espone solo controlli
diagnostici di migrazione:

```powershell
memoria data-root
memoria inventory
memoria doctor
```

Il data root viene risolto da `--data-root`, poi da `MEMORIA_DATA_ROOT`, poi da
`../memoria-workspace/manifest.yml`. I comandi non scansionano ricorsivamente i
dati e non modificano `P:\Comune\Me.Mo.Ri.a`.

`memoria inventory` senza opzioni mantiene il controllo delle cartelle
principali. Per un inventario superficiale di una sezione:

```powershell
memoria inventory --section risultati
memoria inventory --section documenti_processati
memoria inventory --section documenti_da_processare
memoria inventory --section all
memoria inventory --section risultati --output markdown
```

L'inventario di sezione controlla solo il livello top-level: esistenza della
sezione, conteggio di file e directory immediati e al massimo i primi 20 nomi.
Non legge i contenuti dei file e non attraversa ricorsivamente il data root.

La CLI Python installabile `memoria` e' riservata a questa diagnostica minima.
I workflow operativi legacy/preview restano nella CLI PowerShell
`.\scripts\memoria.ps1`, per esempio:

```powershell
.\scripts\memoria.ps1 review discover -WorkspaceRoot "P:\Comune\Me.Mo.Ri.a"
```
