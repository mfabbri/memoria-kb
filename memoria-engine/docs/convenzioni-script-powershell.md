# Convenzioni script PowerShell

Questo progetto usa wrapper PowerShell versionati per i comandi operativi.
Non creare nuovi entrypoint console Python tramite `[project.scripts]` per
replicare pipeline o workflow PowerShell esistenti: gli script in `scripts/`
restano il punto di ingresso stabile per automazione, documentazione e sessioni
Codex. Fa eccezione la CLI diagnostica minima `memoria`, usata per validare
installazione, data root e layout multi-repo dopo la migrazione.

Nel sandbox Codex su Windows, se il PowerShell di sistema fallisce con
`windows sandbox: spawn setup refresh`, usare il runtime portable incluso nel
repository:

```powershell
.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1
```

Per ispezioni rapide preferire comandi PowerShell semplici e leggibili:

```powershell
Get-Content -Path .\file.py -TotalCount 40
```

Quando servono letture indipendenti, parallelizzare con `multi_tool_use.parallel` solo comandi senza pipeline shell.
Le pipeline PowerShell sono utili per uso umano, ma nei turni Codex rendono
piu' fragile la raccolta dell'output.

Per parametri array in PowerShell usare sintassi esplicita, ad esempio:

```powershell
.\scripts\run_mvp_workspace_pipeline.ps1 -ProfileId "person:purocielo:andreoli-dino","person:purocielo:guazzaloca-laura"
```
