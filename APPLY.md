# Correzione discovery Codex — Me.Mo.Ri.A

Questa patch corregge la posizione dei file installati dal precedente pacchetto.
Codex deve trovare dalla radice del repository:

```text
AGENTS.md
.codex/config.toml
.codex/agents/*.toml
.agents/skills/<skill>/SKILL.md
```

La patch **non modifica** `memoria-bootstrap/planning/current-work.json` e non
elimina le copie precedenti sotto `memoria-bootstrap/.codex`.

## Verifica preventiva

```powershell
.\apply.ps1 -TargetRoot "D:\CaDiMalanca\me.mo.ri.a-kb" -DryRun
```

## Applicazione

```powershell
.\apply.ps1 -TargetRoot "D:\CaDiMalanca\me.mo.ri.a-kb"
```

Dopo l'applicazione, chiudi la sessione Codex corrente e avviane una nuova dalla
radice del repository, quindi usa il prompt quotidiano consueto.
