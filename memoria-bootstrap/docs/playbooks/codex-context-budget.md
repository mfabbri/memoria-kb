# Codex Context Budget

Il budget e un guardrail, non un obiettivo da saturare. Preferire progressive
disclosure e letture per simbolo/path.

| Modalita | Letture | Modifiche | Route |
|---|---:|---:|---|
| `discovery-lite` | max 10 file | 0 | mmr_scanner GPT-6 Luna/low |
| docs review | file pertinenti | 0 | mmr_docs_reviewer GPT-6 Luna/low |
| docs/config edit | max 15 file | max 5 | mmr_docs_editor GPT-6 Luna/low |
| `scoped-fix` | max 20 file | max 5 | mmr_implementer GPT-6.1 Sol/medium |
| `feature-slice` | max 30 file | max 8 | mmr_implementer GPT-6.1 Sol/medium |
| `quality-slice` | file/test pertinenti | 0 | mmr_test_reviewer GPT-6.1 Sol/medium |
| `architecture-review` | contratti mirati | docs only | mmr_architect GPT-6 Astra/low |

Regole:

- usare `rg`, `rg --files` e ricerca per simbolo;
- leggere interfacce, test e contratti prima dell'implementazione;
- non caricare run, OCR, dataset o roadmap completi senza necessita;
- una skill verticale alla volta; riferimenti della skill solo on-demand;
- un solo subagent per default;
- passare path/simboli/task envelope invece di duplicare contenuti;
- non rileggere file invariati dopo handoff salvo diff inatteso o quality gate;
- non ripetere test verdi senza nuova modifica, failure o rischio residuo;
- superare budget o tier solo con motivazione registrata.
