---
name: memoria-model-router
description: Classifica il task Me.Mo.Ri.A, seleziona il custom agent/modello appropriato e registra routing intenzionale ed escalation nel planner.
---

# Me.Mo.Ri.A model router

## Principio

Prima raggiungi il livello di qualita' richiesto, poi ottimizza costo, latenza e
token. Usa il modello meno costoso che ha capacita' adeguate per la classe di
task; la dimensione del repository non determina il tier.

Per i task architetturali difficili usa Astra con reasoning `low` come punto di
partenza. Non aumentare automaticamente reasoning o numero di agenti: fallo solo
in presenza di un limite osservabile del risultato, non per accessi o contesto
mancanti.

## Tabella

| tier | tipo | agent | model | effort | write |
|---|---|---|---|---|---|
| low | discovery | mmr_scanner | gpt-5.6-luna | low | no |
| low | document review | mmr_docs_reviewer | gpt-5.6-luna | medium | no |
| low | docs/planner/agent config edit | mmr_docs_editor | gpt-5.6-luna | medium | si, solo confini indicati |
| medium | code/config runtime entro contratti esistenti | mmr_implementer | gpt-5.6-terra | medium | si |
| review | regressioni, edge case, provenance, quality gate | mmr_test_reviewer | gpt-5.6-terra | high | no |
| high | architettura, migrazione, conflitto di contratti | mmr_architect | gpt-6-astra | low | no |

## Decisione deterministica

1. Se ci sono migrazione, architettura o trade-off non deciso -> `high`.
2. Altrimenti, se e' quality/audit/regressione indipendente -> `review`.
3. Altrimenti, se `write_set` contiene codice runtime o configurazione applicativa -> `medium`.
4. Altrimenti, se `write_set` contiene solo docs, planner, AGENTS, `.codex` o `.agents` -> `low/mmr_docs_editor`.
5. Altrimenti, se e' read-only documentale -> `low/mmr_docs_reviewer`.
6. Altrimenti -> `low/mmr_scanner` per discovery o `medium/mmr_implementer` come default prudente.

Usa `policy_version: 2.1` per i nuovi record di routing. Registra il blocco
`routing` nel planner prima della delega o dell'esecuzione. Aggiungi un evento
`escalated` o `fallback` prima di cambiare tier/modello. Il fallback al parent e'
consentito per un micro-slice `medium` gia' delimitato e verificabile; non vale
per `review` o `high`. Non sostituire silenziosamente Astra se il modello non e'
disponibile nel workspace Codex.

## Disciplina token

- Un solo subagent per default. Non fare fan-out perche' sono disponibili thread.
- Parallelizza solo task indipendenti quando il beneficio atteso supera il costo
  di contesto duplicato.
- Passa ai subagent task envelope, path, simboli e criteri di accettazione; evita
  di ricopiare file o roadmap gia' accessibili.
- Mantieni output inter-agent concisi: evidenze, file, rischi, esito; niente
  narrazione estesa o chain-of-thought.
- Dopo una delega, non rileggere tutto: verifica diff, file toccati e quality
  gate mirato.
- Non ripetere test gia' passati senza nuova modifica, failure o dubbio concreto.
- Accessi, file o requisiti mancanti richiedono recupero del contesto o un blocco,
  non un reasoning effort maggiore.

La traccia runtime effettiva viene prodotta dagli hook e non va copiata nel planner:
`memoria-bootstrap/planning/.runtime/model-routing.ndjson`.
