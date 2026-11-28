---
name: memoria-model-router
description: Scegli modello e delega solo per slice di codice o trade-off con rischio definito.
---

# Routing v3.2 — on demand

Non attivare un subagent solo per aderire a una tabella. Il parent Sol/medium
puo' completare direttamente gran parte delle slice. Switch manuale del parent
in `/model` quando il compito e' evidentemente piccolo o strutturalmente arduo.

| Compito | Modello/effort proposto | Delega |
|---|---|---|
| Fix meccanico, ricerca per file, documento breve | Luna/low | Nessuna di norma |
| Dossier reale, integrazione/CLI, test mirati | GPT-6.2 Sol/medium | Solo indipendente e delimitata |
| Review rischio reale: provenance, canonici, regressioni | Sol/medium | Solo quando i test non bastano |
| Architettura ambigua multi-repo, conflitto di contratti | GPT-6.2 Astra/medium | Solo trade-off concreto |
| Interazione visiva non automatizzabile con tool usuali | GPT-6.1 Terra/medium | Solo task effettivamente visuale |

Effort high/xhigh non e' un default, ma escalation per blocco riproducibile.
Verifica disponibilita' in `/model`; gli slug API non garantiscono accesso Codex.
Per nuove route usa `policy_version: "3.2"`, senza riscrivere lo storico.
Se manca il modello, registra quello reale e il motivo di fallback.
Non leggere l'intero planner o la roadmap per scegliere un modello.
