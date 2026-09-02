# Audit di modularità di memoria-engine

Data: 2026-09-01

## Metodo e perimetro

Audit read-only del checkout corrente. Sono state usate metriche leggere sulle
righe dei file Python e una lettura delle responsabilità principali; non sono
stati eseguiti refactor, pipeline, accessi live o letture del data root esterno.
Le modifiche già presenti nel worktree non sono state attribuite a questo audit.

## Metriche sintetiche

| Area | File Python | Righe |
|---|---:|---:|
| `document_analysis` | 82 | 24.699 |
| package root `caduti_fonti_report` | 52 | 12.434 |
| `connectors` | 27 | 6.614 |

Moduli più estesi osservati:

| Modulo | Righe | Responsabilità osservata | Rischio |
|---|---:|---|---|
| `memoria_cli.py` | 1.892 | parser CLI, comandi diagnostici, discovery di run/fonti e rendering testuale | alto: superficie pubblica e molte modalità operative |
| `connectors/bundesarchiv_invenio_executor.py` | 1.604 | orchestrazione Playwright/JSF, attese, cattura diagnostica e raccolta risultati | alto: rete, timing e comportamento browser |
| `document_analysis/mvp_pilot_summary.py` | 1.054 | aggregazione summary MVP, readiness e rendering diagnostico | medio: parte della logica è già stata isolata in Q2 |
| `document_analysis/local_processing_runner.py` | 1.015 | orchestrazione pipeline locale, manifest, log e gestione step | medio-alto: sequenza e artefatti osservabili |
| `export_obsidian_vault.py` | 997 | selezione profili, scrittura vault e composizione note | medio-alto: filesystem e output editoriali |
| `document_analysis/mvp_demo_descriptor.py` | 902 | allineamento ledger, descrittore demo, riconciliazione, readiness e Markdown | medio: output preview e contratti demo |
| `document_analysis/mvp_review_focus_table.py` | 757 | parsing tabella/card e conversione decisioni | basso residuo: parser Markdown già estratto in Q2 |
| `document_analysis/mvp_funding_package.py` | 515 | costruzione checklist/package, verifiche artefatti e rendering | medio: gate e output demo |
| `document_analysis/candidate_person_profiles.py` | 447 | estrazione profili candidati, normalizzazione, deduplica e rendering | medio: candidati preview-only |

## Candidati Q2

| Priorità | Candidato | Responsabilità da isolare | Test minimi | Rischio/valore |
|---:|---|---|---|---|
| 1 | `mvp-demo-reconciliation-renderer` | estrarre il solo rendering Markdown della riconciliazione da `mvp_demo_descriptor.py` | `tests.test_mvp_demo_descriptor` | medio-basso rischio, confine chiaro, nessun cambio di ledger/CLI |
| 2 | `candidate-person-profile-renderer` | isolare il rendering Markdown dei profili candidati da `candidate_person_profiles.py` | `tests.test_candidate_person_profiles_from_documents` | medio rischio, riduce mescolanza tra estrazione e presentazione |
| 3 | `mvp-funding-package-renderers` | separare i renderer Markdown dalla costruzione/verifica del package | `tests.test_mvp_funding_package` | medio rischio, output di gate sensibile |
| 4 | `memoria-cli-command-groups` | isolare un gruppo ristretto di funzioni di stampa diagnostica dalla CLI | `tests.test_memoria_cli` | alto rischio, superficie pubblica ampia; non prima dei candidati sopra |

Sono esclusi i confini già coperti dai Q2 documentati in
`current-next-increment.md`: parser `mvp_review_focus_table`, rendering e
diagnostica di `mvp_pilot_summary`, manifest del runner, vault Obsidian,
parser Bundesarchiv, diagnostica/skipped claim, renderer review e
`workspace_resolver`.

## Selezione

Il candidato scelto per il prossimo incremento è
`mvp-demo-reconciliation-renderer`: una sola responsabilità pura, test già
presenti, fixture offline e rischio inferiore rispetto a CLI o browser executor.

Stop condition Q2: estrarre solo il rendering Markdown della riconciliazione;
preservare ledger, readiness, payload, CLI, schema, artefatti e workflow;
eseguire i test mirati; non modificare dati esterni o profili canonici.
