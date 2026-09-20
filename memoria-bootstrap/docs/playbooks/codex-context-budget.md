# Codex Context Budget

| Modalita' | Letture | Modifiche | Route |
|---|---:|---:|---|
| `discovery-lite` | max 10 file | 0 | mmr_scanner Luna/low |
| docs review | file pertinenti | 0 | mmr_docs_reviewer Luna/medium |
| docs/config edit | max 20 file | max 5 | mmr_docs_editor Luna/medium |
| `scoped-fix` | max 20 file | max 5 | mmr_implementer Terra/medium |
| `feature-slice` | max 30 file | max 8 | mmr_implementer Terra/medium |
| `quality-slice` | file/test pertinenti | 0 | mmr_test_reviewer Terra/high |
| `architecture-review` | contratti mirati | docs only | mmr_architect Astra/low |

- usare `rg`, `rg --files` e ricerca per simbolo;
- leggere interfacce, test e contratti prima delle implementazioni;
- non caricare run, OCR, dataset o roadmap completi senza necessita';
- riusare task envelope e routing record;
- superare budget o tier solo con motivazione registrata.

- un solo subagent per default; non saturare `max_concurrent_threads_per_session`;
- parallelizzare solo task indipendenti con beneficio concreto;
- passare path/simboli/task envelope invece di duplicare contenuti inter-agent;
- non rileggere file invariati dopo handoff salvo diff inatteso o quality gate;
- non ripetere test passati senza nuova modifica, failure o rischio residuo.
