# Model routing e context efficiency — policy v3.1

Aggiornamento: 2026-11-01. Sostituisce v3.0 **per nuove sessioni** senza
riscrivere route o audit di sessioni precedenti.

## Criterio principale: costo per task concluso, non costo per singolo token

La scelta del modello e del numero di agent dipende da rischio, ambiguita',
qualita' misurata e costo complessivo (input/output/reasoning, retry e subagent).
Per task semplici non delegare: il parent evita un secondo prompt, ripetizioni
di contesto e overhead di coordinamento.

| Lavoro | Default | Quando delegare |
|---|---|---|
| Discovery, typo, docs mirate, aggiornamento planner | parent `gpt-6-luna`, low | Solo se un confronto indipendente ha valore |
| Fix meccanico isolato con test immediato | parent Luna/low; verificare risultato | Se cambia comportamento/contratto, passare a Sol |
| Implementazione, parser, CLI, provenance, test | `mmr_implementer`, `gpt-6.1-sol`, medium | Se il task e' sostanziale e delegabile; altrimenti cambiare modello in sessione |
| Review di regressioni/contratti | `mmr_test_reviewer`, Sol/medium | Solo per rischio reale e revisione indipendente |
| Architettura, migrazione con trade-off ambigui | `mmr_architect`, `gpt-6-astra`, low | Solo se il problema richiede una valutazione dedicata |

Gli agent specializzati docs/scanner sono **opzionali** e non obbligatori in
ogni sessione. I custom agent `.codex/agents/*.toml` ereditano sandbox e
approval policy dalla sessione parent: istruzioni read-only riducono il rischio
ma non configurano un sandbox separato. Per isolamento tecnico eseguire una
sessione distinta con permessi compatibili; non impostare `sandbox_mode` nei
file custom agent. Non eseguire una review LLM indipendente quando test automatici
mirati e diff sono sufficienti. `high` reasoning non e' un sostituto di dati o
accessi mancanti. Modifiche ai modelli sono subordinate a disponibilita'
verificata in `/model`; in caso contrario rendere esplicito il fallback,
l'eventuale cambio di tier e il modello realmente usato.

## Contesto e prompt

- `AGENTS.md` solo invarianti; `docs/current-focus.md` e summary planner;
  prompt quotidiano breve, senza procedure OCR
  incorporate. Skill con descrizioni specifiche e dettagli *on-demand*.
- Leggi interfacce, contratti e test pertinenti (ricerca per path/simbolo), non
  dump di interi file/roadmap, ZIP di run o report di migliaia di righe.
- Usa output delle CLI concisi, `rg -n`, `git diff --stat` e sezioni mirate;
  conserva nei handoff: obiettivo, path, vincoli, evidenza e stop condition.
- Un solo subagent di default, nessuno per task brevi. Parallelismo soltanto
  per analisi veramente indipendenti; non far editare gli stessi file a due agent.
- Evita di rilanciare una suite gia' verde e invariata; espandi i test soltanto
  per rischio residuo documentato.
- Dopo una lunga sessione compatta solo quando utile al costo totale e conserva
  un breve checkpoint: obiettivo, modifiche, test, stato e questioni aperte.

## Prompt caching: distinzione fra API e Codex

Per integrazioni **Responses API**: preservare il prefisso stabile (istruzioni,
schemi, strumenti ordinati), aggiungere dettagli dinamici in coda, mantenere
cronologia append-only; misurare `cached input tokens`, output e costo totale.
Con GPT-5.6+ le opzioni `prompt_cache_options`, breakpoint e
`configuration_update` dipendono dal modello/API scelti. Non aggiungere
padding privo di valore per inseguire la soglia cache. Compaction puo' ridurre
hit-rate ma anche costo totale; testare su trace reali. Queste opzioni **non**
sono chiavi trasferibili a `.codex/config.toml` e la cache non e' garantita per
la sola permanenza della sessione Codex.

## Evidenza e versioni

- `current-work.json` registra la decisione intenzionale: nuove route attive
  `policy_version: "3.1"`; il validatore accetta le route storiche 2.0/2.1/3.0.
- `.codex/hooks.json` registra eventi runtime in
  `memoria-bootstrap/planning/.runtime/model-routing.ndjson` (se gli hook sono
  stati trusted nel client). I log possono non fornire sempre il model id;
  non inventare quel dato.
- Verifica `codex --version`, `/model`, `/hooks` e i limiti del workspace prima
  di assumere compatibilita'; gli ID API non garantiscono accesso Codex.
- Metriche di valutazione: task corretti al primo tentativo, retry, durata,
  token input non cached / cached / output quando disponibili, costo totale,
  subagent avviati, esiti dei test e patch non richieste. Registrare baseline
  e confronto su task equivalenti prima di affermare risparmi percentuali.

## Fonti OpenAI consultate il 2026-11-01

- https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
- https://developers.openai.com/api/docs/guides/model-selection
- https://developers.openai.com/api/docs/guides/prompt-caching
- https://developers.openai.com/api/docs/guides/agents-api/observability
- https://developers.openai.com/api/docs/guides/agents-api/multi-agent
- https://learn.chatgpt.com/docs/hooks
