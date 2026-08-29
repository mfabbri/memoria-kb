# Codex Context Budget

| Modalita' | Letture | Modifiche | Route |
|---|---:|---:|---|
| `discovery-lite` | max 10 file | 0 | scanner Luna/low |
| docs review | file pertinenti | 0 | docs_reviewer Luna/medium |
| docs/config edit | max 20 file | max 5 | docs_editor Luna/medium |
| `scoped-fix` | max 20 file | max 5 | implementer Terra/medium |
| `feature-slice` | max 30 file | max 8 | implementer Terra/medium |
| `quality-slice` | file/test pertinenti | 0 | test_reviewer Terra/high |
| `architecture-review` | contratti mirati | docs only | architect Sol/high |

- usare `rg`, `rg --files` e ricerca per simbolo;
- leggere interfacce, test e contratti prima delle implementazioni;
- non caricare run, OCR, dataset o roadmap completi senza necessita';
- riusare task envelope e routing record;
- superare budget o tier solo con motivazione registrata.
