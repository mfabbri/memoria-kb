# Model routing policy v3.0

Data: 2026-10-02

## Obiettivo

Usare il modello meno costoso che soddisfa il rischio del task, mantenendo
routing verificabile e contesto minimo. La policy separa decisione intenzionale
(planner) e modello realmente eseguito (hook runtime).

## Routing canonico

| Tier | Agent | Modello | Reasoning | Responsabilita |
|---|---|---|---|---|
| router | parent | GPT-6 Luna | low | classificare, delegare, sintetizzare |
| low | mmr_scanner | GPT-6 Luna | low | discovery read-only |
| low | mmr_docs_reviewer | GPT-6 Luna | low | review documentale mirata |
| low | mmr_docs_editor | GPT-6 Luna | low | docs/planner/config agent |
| medium | mmr_implementer | GPT-6.1 Sol | medium | codice e micro-feature |
| review | mmr_test_reviewer | GPT-6.1 Sol | medium | quality/regressioni/provenance |
| high | mmr_architect | GPT-6 Astra | low | architettura/migrazioni/trade-off |

## Motivazione

OpenAI indica GPT-6 Luna come modello piu efficiente per workload mirati e ad
alto volume, GPT-6.1 Sol come scelta vicina ad Astra per lavoro complesso a costo
inferiore, e Astra come modello piu capace per problemi ambigui e impegnativi.
La guida corrente associa inoltre Luna/low a edit circoscritti e Sol/medium al
lavoro tecnico complesso.

Per Me.Mo.Ri.A questo sostituisce il routing v2.1:

```text
GPT-5.6 Luna -> GPT-6 Luna
GPT-5.6 Terra/medium -> GPT-6.1 Sol/medium
GPT-5.6 Terra/high review -> GPT-6.1 Sol/medium
Astra/low -> invariato
```

La review scende da high a medium perche reasoning maggiore usa piu quota e non
garantisce un risultato migliore. Se la review trova un problema realmente
ambiguo o architetturale, si fa escalation di tier, non si alza il reasoning in
modo automatico.

## Availability gate

GPT-6.1 Sol puo dipendere da piano, client, workspace e rollout. `/model` e la
fonte operativa per i modelli realmente disponibili alla sessione. Un modello
non disponibile non viene sostituito silenziosamente: il planner registra un
`fallback` o un `escalated` prima di eseguire con un modello diverso.

Per la policy v3.0 e consigliato Codex CLI `0.159.2` o successivo.

## Context engineering

Le istruzioni persistenti devono essere piccole:

- `AGENTS.md`: solo regole sempre valide;
- skill: un job riconoscibile, descrizione corta e specifica;
- progressive disclosure: caricare `SKILL.md` e riferimenti solo quando scelti;
- niente stack fisso di documenti da leggere prima di ogni edit;
- niente duplicazione di roadmap/file nei messaggi inter-agent.

## Subagent e token

- un subagent e il default;
- parallelizzare solo workstream indipendenti;
- passare task envelope, path, simboli e acceptance criteria;
- non rileggere file invariati dopo handoff salvo conflitto o diff inatteso;
- eseguire il test piu piccolo significativo; ampliare dopo failure o rischio;
- reasoning maggiore non sostituisce accessi, fonti o requisiti mancanti.

## Audit runtime

Gli hook `SessionStart`, `SubagentStart` e `SubagentStop` registrano modello,
agente ed evento in:

```text
memoria-bootstrap/planning/.runtime/model-routing.ndjson
```

Il file non viene versionato.

## Compatibilita planner

- nuovi record: `policy_version: 3.0`;
- schema e validator continuano a leggere `2.0` e `2.1` come storia;
- i nuovi route attivi devono rispettare la tabella v3.0;
- gli eventi storici GPT-5.6 non vengono riscritti.

## Guardrail

- nessun `[profiles.*]` project-local;
- nessuna escalation dovuta alla sola dimensione del repository;
- nessun fan-out automatico;
- ogni fallback e esplicito;
- niente chain-of-thought nel planner o nei log;
- disponibilita del modello verificata dalla sessione, non presunta.

## Riferimenti OpenAI verificati il 2026-10-02

- https://learn.chatgpt.com/docs/models
- https://learn.chatgpt.com/docs/agent-configuration/subagents
- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/changelog
- https://developers.openai.com/api/docs/guides/model-selection
- https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
