# Migrazione ai workflow Codex ottimizzati

## Stato v2

Il routing project-local usa custom agent, non `[profiles.*]`.

La sessione principale e' Luna/medium e ha ruolo di router/controller.
Il lavoro viene delegato in base al task:

```text
discovery/docs          -> Luna
implementation          -> Terra
quality review          -> Terra/high
architecture/migration  -> Astra/low
```

## Tracciabilita'

Il planner versiona la route scelta.
Gli hook registrano il modello effettivo su SessionStart/SubagentStart/SubagentStop
in un log NDJSON locale ignorato da Git.

Questo evita di confondere "modello richiesto" con "modello realmente avviato".

## Aggiornamento Astra e token 2026-09-20

Il tier high usa ora GPT-6 Astra con reasoning `low`, al posto di Sol/high.
Luna e Terra restano invariati per discovery, documentazione e implementazione
ordinaria. La scelta segue la raccomandazione di partire con reasoning piu' basso
e aumentare capacita' solo quando il task lo richiede.

Per contenere i token, non fare fan-out automatico: un solo subagent e' il
default. Passare path, simboli e task envelope invece di copiare file nei
messaggi inter-agent; ampliare test o riletture solo dopo nuove modifiche, failure
o rischi concreti.

## Validazione

```powershell
python .\memoria-bootstrap\planning\validate-codex-model-routing.py
python -m json.tool .\memoria-bootstrap\planning\current-work.json
git diff --check
```

Dopo la prima riapertura di Codex, revisionare e autorizzare gli hook con `/hooks`.
