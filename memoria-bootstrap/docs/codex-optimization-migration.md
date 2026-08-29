# Migrazione ai workflow Codex ottimizzati

## Stato v2

Il routing project-local usa custom agent, non `[profiles.*]`.

La sessione principale e' Luna/medium e ha ruolo di router/controller.
Il lavoro viene delegato in base al task:

```text
discovery/docs          -> Luna
implementation          -> Terra
quality review          -> Terra/high
architecture/migration  -> Sol/high
```

## Tracciabilita'

Il planner versiona la route scelta.
Gli hook registrano il modello effettivo su SessionStart/SubagentStart/SubagentStop
in un log NDJSON locale ignorato da Git.

Questo evita di confondere "modello richiesto" con "modello realmente avviato".

## Validazione

```powershell
python .\memoria-bootstrap\planning\validate-codex-model-routing.py
python -m json.tool .\memoria-bootstrap\planning\current-work.json
git diff --check
```

Dopo la prima riapertura di Codex, revisionare e autorizzare gli hook con `/hooks`.
