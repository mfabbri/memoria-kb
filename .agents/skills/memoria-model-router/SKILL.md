---
name: memoria-model-router
description: Choose a model or specialist only for a nontrivial Me.Mo.Ri.A task with known scope and risk.
---

# Routing v3.1

Prima chiediti se serve delegare: per typo, discovery, documentazione limitata
e fix meccanici il parent puo' procedere da solo senza duplicare il contesto.

| Task | Route preferita | Effort iniziale |
|---|---|---|
| Discovery, docs, modifica meccanica limitata | parent GPT-6 Luna | low |
| Codice che modifica comportamento, regole o CLI | mmr_implementer GPT-6.1 Sol | medium |
| Review indipendente per rischio concreto | mmr_test_reviewer GPT-6.1 Sol | medium |
| Migrazione/architettura multi-repo ambigua | mmr_architect GPT-6 Astra | low |

Gli agent read-only/docs restano disponibili solo quando l'indipendenza porta
valore. Un solo subagent alla volta di norma; non forzare la separazione di task
brevi. Registra nel planner `policy_version: "3.1"` per **nuovi** record di routing
attivi; lo storico 2.x/3.0 non si riscrive. `/model` e' il gate di disponibilita':
se il modello non e' accessibile, registra un fallback concordante e non
attribuire al modello richiesto un lavoro eseguito altrove.

Escalation solo davanti a un blocco verificabile, contratti in conflitto o
rischio nuovo. Ridurre prima scope, tool output e materiale duplicato.
