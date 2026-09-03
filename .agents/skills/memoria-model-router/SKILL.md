---
name: memoria-model-router
description: Classifica il task Me.Mo.Ri.A, seleziona il custom agent/modello appropriato e registra routing intenzionale ed escalation nel planner.
---

# Me.Mo.Ri.A model router

## Principio

Usa il modello meno costoso compatibile con rischio e tipo di lavoro.
La dimensione del repository non determina il tier.

## Tabella

| tier | tipo | agent | model | effort | write |
|---|---|---|---|---|---|
| low | discovery | mmr_scanner | gpt-5.6-luna | low | no |
| low | document review | mmr_docs_reviewer | gpt-5.6-luna | medium | no |
| low | docs/planner/agent config edit | mmr_docs_editor | gpt-5.6-luna | medium | si, solo confini indicati |
| medium | code/config runtime entro contratti esistenti | mmr_implementer | gpt-5.6-terra | medium | si |
| review | regressioni, edge case, provenance, quality gate | mmr_test_reviewer | gpt-5.6-terra | high | no |
| high | architettura, migrazione, conflitto di contratti | mmr_architect | gpt-5.6-sol | high | no |

## Decisione deterministica

1. Se ci sono migrazione, architettura o trade-off non deciso -> `high`.
2. Altrimenti, se e' quality/audit/regressione indipendente -> `review`.
3. Altrimenti, se `write_set` contiene codice runtime o configurazione applicativa -> `medium`.
4. Altrimenti, se `write_set` contiene solo docs, planner, AGENTS, `.codex` o `.agents` -> `low/mmr_docs_editor`.
5. Altrimenti, se e' read-only documentale -> `low/mmr_docs_reviewer`.
6. Altrimenti -> `low/mmr_scanner` per discovery o `medium/mmr_implementer` come default prudente.

Registra il blocco `routing` nel planner prima della delega o dell'esecuzione.
Aggiungi un evento `escalated` o `fallback` prima di cambiare tier/modello.
Il fallback al parent e' consentito per un micro-slice `medium` gia' delimitato
e verificabile; non vale per `review` o `high`.
Non salvare chain-of-thought.

La traccia runtime effettiva viene prodotta dagli hook e non va copiata nel planner:
`memoria-bootstrap/planning/.runtime/model-routing.ndjson`.
