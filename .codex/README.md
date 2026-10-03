# Codex model routing per Me.Mo.Ri.A

## Policy attiva: v3.0

Routing consigliato dal progetto:

- parent/controller: `gpt-6-luna` / `low`;
- discovery: `mmr_scanner` -> GPT-6 Luna / `low`;
- docs review: `mmr_docs_reviewer` -> GPT-6 Luna / `low`;
- docs/planner/config: `mmr_docs_editor` -> GPT-6 Luna / `low`;
- implementation: `mmr_implementer` -> GPT-6.1 Sol / `medium`;
- quality review: `mmr_test_reviewer` -> GPT-6.1 Sol / `medium`;
- architecture/migration: `mmr_architect` -> GPT-6 Astra / `low`.

La scelta segue la famiglia GPT-6 corrente: Luna per lavoro mirato ed economico,
GPT-6.1 Sol per lavoro tecnico complesso con buon rapporto capacita/costo, Astra
solo per problemi ambigui o ad alto rischio. Un reasoning piu alto non e un
quality gate automatico: si aumenta solo dopo un limite osservabile del risultato.

## Requisiti client e disponibilita

Per questa configurazione e consigliato Codex CLI `0.159.2` o successivo.
GPT-6.1 Sol e soggetto a disponibilita per account/workspace. Prima di una
sessione importante usare `/model` per verificare che `gpt-6.1-sol` sia
selezionabile. Non sostituire silenziosamente un modello non disponibile:
registrare il fallback nel planner e usare un modello disponibile esplicitamente.

Project-local `[profiles.*]` non sono usati. I profili Codex sono file separati
sotto `CODEX_HOME`; il routing di questo repository usa custom agent.

## Context e token discipline

- un solo subagent e il default;
- parallelismo solo per workstream indipendenti;
- passare task envelope, path e simboli, non copie di file;
- skill solo on-demand: il metadata serve alla discovery, il corpo va caricato
  solo quando il workflow e pertinente;
- `AGENTS.md` contiene solo regole sempre valide; i dettagli vivono in skill o
  contratti caricati su necessita;
- test mirati prima della suite ampia; non ripetere test verdi senza nuova
  modifica, failure o rischio residuo.

## Tracciabilita

1. `memoria-bootstrap/planning/current-work.json` registra la route intenzionale.
2. `.codex/hooks.json` registra il modello effettivo in
   `memoria-bootstrap/planning/.runtime/model-routing.ndjson`.

Il runtime log resta locale e ignorato da Git.

## Hook trust

Dopo modifiche agli hook, revisarli/autorizzarli con `/hooks`.

## Validazione

```powershell
python .\memoria-bootstrap\planningalidate-codex-model-routing.py
python -m json.tool .\memoria-bootstrap\planning\current-work.json
git diff --check
```

## Riferimenti OpenAI (verificati 2026-10-02)

- https://learn.chatgpt.com/docs/models
- https://learn.chatgpt.com/docs/agent-configuration/subagents
- https://learn.chatgpt.com/docs/build-skills
- https://developers.openai.com/api/docs/guides/model-selection
- https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
