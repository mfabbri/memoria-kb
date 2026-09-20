# Model routing policy v2.1

Data: 2026-09-20

## Obiettivo

Routing Codex multi-model verificabile e token-efficient, con due livelli:

- decisione intenzionale versionata nel planner;
- modello effettivamente eseguito registrato localmente dagli hook.

La policy sceglie prima una classe di capacita' sufficiente al rischio del task e
solo dopo ottimizza costo, latenza e token. La dimensione del repository, da
sola, non giustifica escalation.

## Policy

| Tier | Agent | Modello | Reasoning | Responsabilita' |
|---|---|---|---|---|
| router | parent | Luna | medium | classificare, delegare, sintetizzare |
| low | mmr_scanner | Luna | low | discovery read-only |
| low | mmr_docs_reviewer | Luna | medium | review documentale read-only |
| low | mmr_docs_editor | Luna | medium | docs/planner/config agent |
| medium | mmr_implementer | Terra | medium | codice e micro-feature |
| review | mmr_test_reviewer | Terra | high | quality/regr./provenance |
| high | mmr_architect | GPT-6 Astra | low | architettura/migrazioni/trade-off |

## Perche' Astra solo sul tier high

La documentazione OpenAI corrente presenta GPT-6 Astra come modello piu'
capace per coding, ricerca e problem solving complesso, mentre Luna e Terra
restano le scelte indicate per workload mirati, ripetitivi o quotidiani. OpenAI
raccomanda inoltre di partire da reasoning basso e aumentarlo solo quando serve;
in particolare suggerisce di provare Astra `low` o `medium` quando in precedenza
si usava Sol con effort alto.

Per Me.Mo.Ri.A questo porta a una sostituzione minima:

```text
Sol/high per architettura -> Astra/low
```

Gli altri tier restano invariati finche' benchmark o quality gate del progetto
non dimostrano un vantaggio concreto nel cambiarli.

## Disciplina subagent e token

I subagent migliorano isolamento e specializzazione, ma duplicano parte del
contesto e consumano piu' token di una singola esecuzione. Quindi:

- un solo subagent e' il default;
- parallelismo solo per lavori indipendenti con beneficio concreto;
- task envelope, path e simboli sostituiscono copie di file nei messaggi;
- non rileggere file invariati dopo l'handoff;
- eseguire il quality gate minimo significativo e non ripeterlo se non cambia
  codice o non emergono failure/rischi nuovi;
- reasoning maggiore non compensa accessi, fonti o requisiti mancanti.

Il budget file in `docs/playbooks/codex-context-budget.md` resta un limite di
sicurezza, non un obiettivo da saturare.

## Prompt e istruzioni

Astra segue con particolare attenzione `AGENTS.md`, skill e altri file di
istruzioni. Per questo il tier high deve leggere solo le istruzioni e i contratti
pertinenti e deve evitare di caricare automaticamente tutte le roadmap o tutti i
playbook. I custom agent devono mantenere scope e criteri di uscita stretti.

## Audit runtime

Gli hook `SessionStart`, `SubagentStart` e `SubagentStop` registrano sessione,
evento, model slug, agent type/id e permission mode.

Output locale:

```text
memoria-bootstrap/planning/.runtime/model-routing.ndjson
```

Il file non viene versionato.

## Compatibilita' planner

- i nuovi routing record usano `policy_version: 2.1`;
- lo schema continua ad accettare `2.0` per leggere planner/storia precedente;
- i nuovi route `high` devono usare `mmr_architect` / `gpt-6-astra` / `low`;
- i vecchi eventi Sol/high restano validi come audit storico e non vanno riscritti.

## Guardrail

- nessun `[profiles.*]` project-local;
- nessuna escalation dovuta alla sola dimensione del repository;
- nessun fan-out automatico;
- ogni fallback e' esplicito;
- niente chain-of-thought nel planner o nei log;
- non sostituire silenziosamente un modello non disponibile.

## Riferimenti OpenAI verificati il 2026-09-20

- https://developers.openai.com/api/docs/guides/latest-model
- https://developers.openai.com/api/docs/guides/model-selection
- https://developers.openai.com/docs/agent-configuration/subagents
- https://help.openai.com/articles/20001516-managing-usage-with-gpt-6-astra-in-work-and-codex
