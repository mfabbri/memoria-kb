# Model routing, token efficiency e audit — policy v3.2

Aggiornamento: 2026-11-21. Valida per **nuove** sessioni, senza modificare
route storiche 2.x, 3.0 o 3.1 e senza riscrivere `current-work.json`.

## Regola di scelta: risultato verificabile / costo totale

Le linee guida OpenAI per Codex raccomandano GPT-6.2 Sol come punto di partenza
per lavoro ordinario, Astra per complessita' elevata e Luna per operazioni
ripetitive circoscritte. La selezione dipende dalla **disponibilita' reale**
`/model`, non dai soli slug pubblicati nell'API o dalla configurazione locale.

| Task | Route preferita | Perche' |
|---|---|---|
| Slice ordinaria: codice, CLI, ricerca multi-fonte, elaborazione documentale | parent `gpt-6.2-sol` / `medium` | Riduce tentativi falliti e rimbalzi fra agent |
| Correzioni deterministiche, docs piccole, inventory read-only | parent `gpt-6-luna` / `low` se selezionato in `/model` | Nessun overhead di delega |
| Implementazione ampia ma indipendente | `mmr_implementer` / `gpt-6.2-sol` / `medium` | Solo se separabile dal parent |
| Rischio concreto di regressione/storicita' | `mmr_test_reviewer` / Sol / `medium` | Solo se serve indipendenza oltre ai test |
| Contratti ambigui multi-repo / decisione irreversibile | `mmr_architect` / `gpt-6.2-astra` / `medium` | Esamina trade-off, non micro-task |
| Schermate, UI o materialita' visiva | Terra / `medium` (sessione dedicata) | Non usarlo per parsing testuale |

Parti da `medium` per Sol/Astra; eleva effort solo davanti a blocco motivato,
mai per sostituire fonte/documenti mancanti. Sol e Astra 6.2 non supportano
`none`. Un nome di modello API non prova la sua utilizzabilita' su Codex con
il piano corrente. Se `/model` non mostra una route: non provare fallback
silenziosi; scegliere un modello supportato, registrarlo nel planner e
rieseguire i controlli. Non presentare come misurato un costo stimato.

## Budget contestuale e subagent

- Ordine: `AGENTS.md` -> focus breve -> planner summary; poi soltanto file
  e sezioni pertinenti. Non caricare `current-work.json` completo (~12 MB),
  roadmap tecnica storica, ZIP di run e playbook OCR per l'avvio quotidiano.
- Ricerca per path/simbolo/heading; prima `rg -n`, poi estratti di dimensione
  utile. Evitare output lunghi, duplicati e traceback completi se basta l'errore.
- Skill: descrizione corta e contenuto specifico, disclosure progressiva;
  non forzare skill generiche in ogni turno. Non duplicare istruzioni fra
  AGENTS, prompt e playbook.
- Un solo parent per default. Delega quando la revisione e' indipendente e il
  beneficio atteso supera il costo di serializzare handoff e output. Mai due
  agent in scrittura sugli stessi file. `max_concurrent_threads` e' un limite,
  non un obiettivo.
- Handoff breve: obiettivo, input/path, stop condition, risultato atteso,
  test/provenance. Non copiare ogni riga gia' disponibile nel repository.
- Eseguire il test piu' vicino al codice modificato; suite larga solo per
  nuovi rischi. Fermare cicli di test/documentazione privi di miglioramento
  concreto della ricerca storica.
- Dopo sessioni lunghe, checkpoint sintetico prima di compaction:
  decisioni, file, artefatti, test, blocker; compaction non sostituisce le
  evidenze persistite. Non forzare compaction o token cap arbitrari.

## Distingui Codex da Responses API

Per **Codex**: `/model` e `/hooks` sul client determinano modelli, hook e
telemetria disponibili. Non incollare opzioni API (`prompt_cache_options`,
`context_management`, `reasoning.effort`) nel TOML. Il TOML qui usa
`model_reasoning_effort`; la disponibilita' delle chiavi va verificata con la
versione Codex installata. Il hook di audit puo' non contenere model ID.

Per **Responses API**: preserva i prefissi stabili; GPT-6.2 riordina
`instructions` top-level dopo `input`, quindi per caching mettere le
istruzioni stabili in un `developer` iniziale. Configurare TTL della cache
solo se supportato, misurare gli input cached/non-cached e il costo di write;
non promettere automaticamente risparmi dal semplice mantenere una sessione.
Modifiche retroattive al prefisso possono invalidare cache e reasoning items;
compaction e configurazioni dinamiche hanno condizioni specifiche dell'API.

## Osservabilita' / esperimento minimo

Per 3-5 task comparabili (dossier, bug semplice, review e feedback) registra
modello effettivo, effort, input/cached/output/reasoning token se disponibili,
numero subagent, retry, tempo fino al gate, revisione manuale, errori materiali
ed esito. Confronta costo **per risultato accettabile**, non token/test isolati.
I dati API e i limiti ChatGPT/Codex possono essere non comparabili: riportare
`not_available` invece di inventare un prezzo o un risparmio.

Nuove route `policy_version: "3.2"`; validator accetta storico 2.x/3.0/3.1.
I custom agent ereditano sandbox/approval dalla sessione; read-only nel prompt
non e' isolamento tecnico. Per isolamento usare sessione separata read-only.

## Fonti OpenAI (verificate il 2026-11-21)

- https://developers.openai.com/api/docs/guides/model-selection
- https://developers.openai.com/api/docs/guides/latest-model
- https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
- https://developers.openai.com/api/docs/guides/prompt-caching
- https://developers.openai.com/api/docs/guides/agents-api/multi-agent
