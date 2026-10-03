# Migrazione ai workflow Codex ottimizzati

Data aggiornamento: 2026-10-02

## Stato v3

Il routing project-local usa custom agent e policy `3.0`:

```text
controller/discovery/docs -> GPT-6 Luna / low
implementation            -> GPT-6.1 Sol / medium
quality review             -> GPT-6.1 Sol / medium
architecture/migration     -> GPT-6 Astra / low
```

La configurazione non usa `[profiles.*]` project-local. I profili Codex moderni
sono file separati sotto `CODEX_HOME`; il repository usa invece custom agent
versionati per rendere il routing riproducibile.

## Perche cambia

- GPT-6 Luna sostituisce GPT-5.6 Luna per lavoro focalizzato e ad alto volume.
- GPT-6.1 Sol sostituisce Terra nei task tecnici sostanziali e nella review.
- Astra resta limitato al tier high.
- Reasoning parte basso/medio; non viene alzato preventivamente.

## Context optimization

La migrazione riduce anche scaffolding non necessario:

- `AGENTS.md` contiene solo invarianti e rimandi contestuali;
- le skill sono invocate on-demand, non tutte a inizio sessione;
- le descrizioni skill sono corte e specifiche;
- un solo subagent e il default;
- file e roadmap non vengono duplicati nei prompt inter-agent;
- test mirati prima di suite estese.

## Compatibilita

I planner storici v2.0/v2.1 restano validi. Solo i nuovi routing attivi devono
usare v3.0. Non riscrivere la cronologia del planner per cambiare nomi modello.

GPT-6.1 Sol e soggetto a disponibilita dell'account/workspace. Se `/model` non
lo mostra, non mascherare l'errore: registra il fallback e scegli esplicitamente
un modello disponibile secondo le indicazioni correnti di Codex.

## Validazione

```powershell
python .\memoria-bootstrap\planningalidate-codex-model-routing.py
python -m json.tool .\memoria-bootstrap\planning\current-work.json
git diff --check
```

Dopo modifiche agli hook, usare `/hooks`. Per controllare disponibilita modello,
usare `/model` e `/status`.
