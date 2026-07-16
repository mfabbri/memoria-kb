# Me.Mo.Ri.A — Migration Plan dettagliato

## 0. Scopo della migrazione

Questo piano descrive come rifattorizzare l’attuale repository monolitico di Me.Mo.Ri.A in una struttura multi-repository basata su sei responsabilità distinte:

1. `memoria-bootstrap` — metodo di lavoro, playbook, roadmap, contratti e workspace multi-repo.
2. `memoria-engine` — codice riutilizzabile: OCR orchestration, parsing, extraction, JSON-LD, graph, dashboard e report.
3. `memoria-workspace` — repository di configurazione/manifest e contratti del workspace dati. I dati reali non vivono nel repo, ma in una cartella esterna controllata: `P:\Comune\Me.Mo.Ri.a`.
4. `memoria-knowledge` — conoscenza storica e metodologica: glossari, ontologie, linee guida, modelli di scheda, criteri storiografici.
5. `memoria-rules` — regole deterministiche: entity resolution, merge policy, confidence, provenance, review gating.
6. `memoria-sources` — fonti e connettori: wrapper, downloader, cataloghi, configurazioni OCR per fonte, metadati archivistici.

La migrazione deve essere **non distruttiva**, **incrementale** e **verificabile**. Il repository attuale non deve essere cancellato finché la pipeline MVP non produce gli stessi risultati minimi nel nuovo layout.

---

## 1. Principi non negoziabili

### 1.1 Nessuna perdita di dati

Durante la migrazione non eliminare:

- documenti originali;
- immagini/scansioni;
- OCR grezzo;
- OCR normalizzato;
- JSON-LD già generati;
- dashboard di revisione storica;
- log di esecuzione;
- decision log;
- note di feedback dello storico.

Ogni spostamento deve avvenire inizialmente tramite **copia**, non tramite `move`.

### 1.2 Separazione codice/dati

Il codice deve vivere in `memoria-engine`.

I dati reali devono vivere in `memoria-workspace` o in storage esterno controllato. Non devono finire in `memoria-engine`.


### 1.2.1 Workspace dati esterno obbligatorio

Per Me.Mo.Ri.A il repository `memoria-workspace` non deve diventare il contenitore fisico principale dei dati. Deve invece puntare alla cartella esterna già definita:

```text
P:\Comune\Me.Mo.Ri.a
```

Questa cartella è il **data root operativo** del progetto e contiene documenti originali, OCR, output, JSON-LD, review, report e backup. Il repo `memoria-workspace` deve contenere solo:

- `README_WORKSPACE.md`;
- `manifest.yml`;
- configurazioni;
- template;
- script di validazione;
- eventuali `.gitkeep`;
- esempi non sensibili.

Non copiare massivamente `P:\Comune\Me.Mo.Ri.a` dentro Git. Se serve versionare dataset campione, usare solo `sample-data/` con dati minimi e non sensibili.

### 1.3 Provenienza preservata

Ogni entità prodotta deve poter rispondere a tre domande:

1. Da quale documento proviene?
2. Da quale passaggio della pipeline è stata generata?
3. Quale umano o agente l’ha revisionata o modificata?

### 1.4 Refactor senza cambio funzionale iniziale

La prima migrazione non deve introdurre nuove funzionalità. Deve solo rendere il sistema più ordinato e riproducibile.

### 1.5 Agent-agnostic

Non introdurre file specifici per un singolo agente AI come unica fonte di verità. Le istruzioni comuni devono vivere in:

- `AGENTS.md` nel bootstrap;
- `docs/playbooks/` nel bootstrap;
- `INTEGRATION.md` nei repository.

---

## 2. Layout target consigliato

```text
memoria/
├── memoria-bootstrap/
├── memoria-engine/
├── memoria-workspace/
├── memoria-knowledge/
├── memoria-rules/
└── memoria-sources/
```

Tutti i repository devono essere clonati come **sibling** sotto una cartella comune `memoria/`.

Il repository `memoria-workspace/` è solo il **workspace descriptor**. Il data root reale resta esterno:

```text
P:\Comune\Me.Mo.Ri.a
```

Questa scelta evita di duplicare dataset pesanti e mantiene separato il versionamento del metodo/configurazione dalla custodia dei documenti.

---

## 3. Ruolo dei repository target

### 3.1 `memoria-bootstrap`

Contiene il metodo di lavoro multi-repo.

Contenuto previsto:

```text
memoria-bootstrap/
├── README.md
├── AGENTS.md
├── memoria.code-workspace
├── docs/
│   ├── architecture-overview.md
│   ├── repository-map.md
│   ├── developer-playbook.md
│   ├── workflow.md
│   ├── glossary.md
│   ├── current-next-increment.md
│   ├── decision-log.md
│   ├── roadmap/
│   │   ├── roadmap-mvp.md
│   │   ├── roadmap-v1.md
│   │   └── roadmap-long-term.md
│   ├── playbooks/
│   │   ├── 00-start-session.md
│   │   ├── 01-find-next-increment.md
│   │   ├── 02-design-before-code.md
│   │   ├── 03-implement-one-increment.md
│   │   ├── 04-test-and-regressions.md
│   │   ├── 05-update-docs.md
│   │   ├── 06-review.md
│   │   ├── 07-release.md
│   │   └── 08-knowledge-and-rules-update.md
│   ├── contracts/
│   │   ├── document-contract.md
│   │   ├── ocr-contract.md
│   │   ├── extraction-contract.md
│   │   ├── jsonld-contract.md
│   │   ├── review-contract.md
│   │   └── source-wrapper-contract.md
│   └── adr/
└── scripts/
    ├── validate-layout.ps1
    └── validate-layout.sh
```

### 3.2 `memoria-engine`

Contiene codice e test.

```text
memoria-engine/
├── README.md
├── pyproject.toml
├── src/memoria_engine/
│   ├── cli/
│   ├── ocr/
│   ├── ingestion/
│   ├── extraction/
│   ├── graph/
│   ├── review/
│   ├── reporting/
│   └── utils/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── regression/
├── examples/
└── docs/
    ├── architecture.md
    ├── cli.md
    ├── testing.md
    └── decision-log.md
```

### 3.3 `memoria-workspace`

Contiene il descrittore del workspace dati, non il dataset completo. Il data root operativo è esterno:

```text
P:\Comune\Me.Mo.Ri.a
```

Layout consigliato del repository `memoria-workspace`:

```text
memoria-workspace/
├── README_WORKSPACE.md
├── manifest.yml
├── config/
│   ├── workspace.local.example.yml
│   └── path-mapping.yml
├── templates/
│   ├── document-manifest.template.yml
│   ├── source-manifest.template.yml
│   └── review-item.template.md
├── scripts/
│   ├── validate-external-data-root.ps1
│   └── validate-external-data-root.sh
├── sample-data/
│   └── .gitkeep
└── docs/
    ├── external-data-root.md
    └── data-governance.md
```

Layout atteso nella cartella esterna `P:\Comune\Me.Mo.Ri.a`:

```text
P:\Comune\Me.Mo.Ri.a\
├── inbox\
├── raw\
│   ├── offline\
│   └── online\
├── processed\
│   ├── ocr_raw\
│   ├── ocr_normalized\
│   ├── chunks\
│   └── extraction_candidates\
├── graph\
│   ├── jsonld\
│   ├── indexes\
│   └── snapshots\
├── historian_review\
│   ├── pending\
│   ├── approved\
│   ├── rejected\
│   └── review_dashboard.md
├── reports\
├── exports\
├── logs\
├── config\
└── backups\
```

Il repo `memoria-workspace` deve quindi puntare alla cartella esterna tramite `manifest.yml`, configurazione locale o variabile ambiente `MEMORIA_DATA_ROOT`.

### 3.4 `memoria-knowledge`

Contiene conoscenza storica, ontologica e metodologica.

```text
memoria-knowledge/
├── README.md
├── domain/
│   ├── resistenza-romagna.md
│   ├── brigate-formazioni.md
│   ├── luoghi.md
│   ├── nomi-alias.md
│   └── cronologia.md
├── ontology/
│   ├── cidoc-crm-alignment.md
│   ├── memoria-entity-model.md
│   └── jsonld-context.md
├── guidelines/
│   ├── historian-review.md
│   ├── source-criticism.md
│   ├── evidence-grading.md
│   └── person-card-standard.md
├── prompts/
├── glossary/
├── bibliography/
└── sources-notes/
```

### 3.5 `memoria-rules`

Contiene policy deterministiche e testabili.

```text
memoria-rules/
├── README.md
├── entity-resolution/
│   ├── person-merge-policy.yml
│   ├── alias-policy.yml
│   └── place-normalization-policy.yml
├── confidence/
│   ├── confidence-scoring.yml
│   └── evidence-thresholds.yml
├── provenance/
│   ├── provenance-required-fields.yml
│   └── citation-policy.yml
├── review/
│   ├── review-gates.yml
│   └── historian-decision-policy.yml
├── tests/
└── docs/
    ├── rule-authoring.md
    └── changelog.md
```

### 3.6 `memoria-sources`

Contiene wrapper, cataloghi e configurazioni fonte.

```text
memoria-sources/
├── README.md
├── catalogs/
│   ├── offline-sources.yml
│   ├── online-sources.yml
│   └── archive-register.yml
├── wrappers/
│   ├── germandocs/
│   ├── memorial-sites/
│   └── local-books/
├── downloaders/
├── ocr-profiles/
│   ├── italian-books.yml
│   ├── german-docs.yml
│   └── mixed-language.yml
├── samples/
└── docs/
    ├── source-onboarding.md
    └── wrapper-contract.md
```

---

## 4. Mapping dal repository attuale ai repository target

| Origine nel repository attuale | Destinazione target | Note operative |
|---|---|---|
| `docs/playbooks/` | `memoria-bootstrap/docs/playbooks/` | Consolidare, rimuovere duplicazioni, mantenere playbook giornaliero. |
| `docs/actualMeMoRiAPrompt-dataset-roadmap.md` | `memoria-bootstrap/docs/playbooks/00-start-session.md` + `docs/current-next-increment.md` | Trasformare da prompt monolitico a playbook operativo. |
| `docs/mvp-next-steps*` | `memoria-bootstrap/docs/roadmap/roadmap-mvp.md` | Rendere orientato a valore demo, non a sola implementazione tecnica. |
| `docs/roadmap*` | `memoria-bootstrap/docs/roadmap/` | Separare MVP, V1, long-term. |
| `docs/audit*` | `memoria-engine/docs/` oppure `memoria-bootstrap/docs/adr/` | Gli audit tecnici stanno nell’engine; decisioni architetturali in ADR. |
| `scripts/` | `memoria-engine/src/memoria_engine/` | Codice generalizzabile. |
| script downloader/wrapper online | `memoria-sources/wrappers/` o `downloaders/` | Separare fonte da motore. |
| configurazioni OCR | `memoria-sources/ocr-profiles/` | Profili per tipo fonte/documento. |
| `documenti_processati/` | `P:\Comune\Me.Mo.Ri.a\processed\` | Copia iniziale non distruttiva nel data root esterno; non nel repository Git. |
| scansioni/PDF originali | `P:\Comune\Me.Mo.Ri.a\raw\` | Mantenere struttura per fonte nel data root esterno. |
| OCR grezzo | `P:\Comune\Me.Mo.Ri.a\processed\ocr_raw\` | Non sovrascrivere. |
| OCR ripulito | `P:\Comune\Me.Mo.Ri.a\processed\ocr_normalized\` | Versionare snapshot/manifest, non necessariamente file pesanti in Git. |
| chunk intermedi | `P:\Comune\Me.Mo.Ri.a\processed\chunks\` | Input a extraction. |
| candidati LLM | `P:\Comune\Me.Mo.Ri.a\processed\extraction_candidates\` | Non considerarli entità approvate. |
| JSON-LD generati | `P:\Comune\Me.Mo.Ri.a\graph\jsonld\` | Separare candidate/approved se necessario. |
| `historian_review/` | `P:\Comune\Me.Mo.Ri.a\historian_review\` | Dashboard e decision trail nel data root esterno. |
| linee guida storiche | `memoria-knowledge/guidelines/` | Es. come valutare fonti contraddittorie. |
| ontologie/schema entità | `memoria-knowledge/ontology/` + `memoria-engine/schemas/` | Knowledge spiega; engine valida. |
| regole merge/confidence | `memoria-rules/` | Deterministiche e testabili. |
| output demo | `P:\Comune\Me.Mo.Ri.a\reports\` o `exports\` | Separare report interni da esportazioni pubblicabili. |

---

## 5. Procedura dettagliata

## Fase A — Preparazione

### A.1 Creare un branch di migrazione nel repository attuale

```bash
git checkout main
git pull
git checkout -b refactor/knowledge-workspace-architecture
```

### A.2 Congelare lo stato corrente

Creare un tag o una copia immutabile:

```bash
git tag pre-memoria-refactor-$(date +%Y%m%d)
```

Su Windows PowerShell:

```powershell
git tag "pre-memoria-refactor-$(Get-Date -Format yyyyMMdd)"
```

### A.3 Generare inventario iniziale

Linux/macOS/WSL:

```bash
find . -type f | sort > migration_inventory_before.txt
find . -type f -name "*.md" | sort > migration_markdown_before.txt
find . -type f \( -name "*.py" -o -name "*.ps1" -o -name "*.sh" \) | sort > migration_code_before.txt
```

PowerShell:

```powershell
Get-ChildItem -Recurse -File | Sort-Object FullName | ForEach-Object FullName > migration_inventory_before.txt
Get-ChildItem -Recurse -File -Include *.md | Sort-Object FullName | ForEach-Object FullName > migration_markdown_before.txt
Get-ChildItem -Recurse -File -Include *.py,*.ps1,*.sh | Sort-Object FullName | ForEach-Object FullName > migration_code_before.txt
```

### A.4 Identificare dati sensibili o pesanti

Obiettivo: impedire che dataset o PDF finiscano in repository pubblici.

Cercare:

- PDF;
- immagini;
- OCR;
- output JSON-LD;
- file con nomi personali;
- log con path locali;
- token/API key.

Comandi utili:

```bash
find . -type f \( -name "*.pdf" -o -name "*.jpg" -o -name "*.png" -o -name "*.tif" -o -name "*.jsonld" -o -name "*.log" \) | sort
```

---

## Fase B — Creazione repository target

### B.1 Creare cartella parent

```bash
mkdir memoria
cd memoria
```

### B.2 Estrarre o clonare i sei repo target

```text
memoria/
├── memoria-bootstrap/
├── memoria-engine/
├── memoria-workspace/
├── memoria-knowledge/
├── memoria-rules/
└── memoria-sources/
```


### B.2.1 Configurare il data root esterno

Prima di migrare qualunque documento, verificare l’esistenza della cartella dati esterna:

```powershell
Test-Path "P:\Comune\Me.Mo.Ri.a"
```

Se non esiste, crearla solo dopo aver confermato che il drive `P:` è montato correttamente:

```powershell
New-Item -ItemType Directory -Force "P:\Comune\Me.Mo.Ri.a"
```

Configurare il path in uno dei seguenti modi:

```powershell
$env:MEMORIA_DATA_ROOT = "P:\Comune\Me.Mo.Ri.a"
```

oppure in `memoria-workspace/config/workspace.local.yml`:

```yaml
workspace:
  data_root: "P:\Comune\Me.Mo.Ri.a"
  mode: external_data_root
  repository_role: descriptor_only
```

Il file `workspace.local.yml` deve restare locale e non contenere segreti; può essere ignorato da Git se contiene path specifici della macchina.

### B.3 Aprire il workspace

Aprire `memoria-bootstrap/memoria.code-workspace` in VS Code o nell’ambiente usato dall’agente.

### B.4 Verificare layout

Eseguire lo script di validazione dal bootstrap:

```bash
cd memoria-bootstrap
./scripts/validate-layout.sh
```

PowerShell:

```powershell
cd memoria-bootstrap
.\scripts\validate-layout.ps1
```

Se lo script non esiste ancora, validare manualmente che tutti i sibling repo siano presenti.

---

## Fase C — Migrazione documentazione e metodo

### C.1 Migrare playbook

Origine:

```text
docs/playbooks/
```

Destinazione:

```text
memoria-bootstrap/docs/playbooks/
```

Regole:

- mantenere solo playbook operativi;
- spostare spiegazioni lunghe in `docs/workflow.md` o `docs/architecture-overview.md`;
- eliminare duplicazioni;
- convertire prompt lunghi in procedure a step.

### C.2 Migrare roadmap

Origine probabile:

```text
docs/mvp-next-steps*.md
docs/roadmap*.md
docs/current-next-increment.md
```

Destinazione:

```text
memoria-bootstrap/docs/roadmap/roadmap-mvp.md
memoria-bootstrap/docs/roadmap/roadmap-v1.md
memoria-bootstrap/docs/roadmap/roadmap-long-term.md
memoria-bootstrap/docs/current-next-increment.md
```

Criterio: la roadmap deve descrivere **valore dimostrabile**, non solo componenti tecniche.

Esempio corretto:

> Dimostrare il percorso dal documento grezzo alla scheda persona revisionabile dallo storico, con provenienza e feedback per nuove ricerche.

Esempio da evitare:

> Implementare parser e dashboard.

### C.3 Migrare decisioni architetturali

Se esistono decisioni sparse nei documenti, trasformarle in ADR:

```text
memoria-bootstrap/docs/adr/0001-separate-engine-workspace-knowledge-rules-sources.md
memoria-bootstrap/docs/adr/0002-jsonld-as-interchange-format.md
memoria-bootstrap/docs/adr/0003-human-review-before-publication.md
```

Template consigliato:

```md
# ADR-0001 — Titolo

## Stato
Accettata / Proposta / Superata

## Contesto

## Decisione

## Conseguenze

## Collegamenti
```

---

## Fase D — Migrazione codice verso `memoria-engine`

### D.1 Classificare gli script esistenti

Per ogni script chiedere:

1. È un componente generale della pipeline?
2. È specifico per una fonte?
3. È solo un comando di utilità locale?
4. Dipende da path del vecchio repository?

Mapping:

| Tipo script | Destinazione |
|---|---|
| OCR generale | `memoria-engine/src/memoria_engine/ocr/` |
| Chunking generale | `memoria-engine/src/memoria_engine/ingestion/` |
| Estrazione entità | `memoria-engine/src/memoria_engine/extraction/` |
| JSON-LD / graph | `memoria-engine/src/memoria_engine/graph/` |
| Dashboard review | `memoria-engine/src/memoria_engine/review/` o `reporting/` |
| Downloader sito specifico | `memoria-sources/wrappers/<source>/` |
| Script PowerShell orchestrazione locale | `memoria-engine/src/memoria_engine/cli/` o `scripts/` temporaneo |

### D.2 Introdurre configurazione esplicita dei path

Il codice non deve assumere path hardcoded come:

```text
./documenti_processati
./historian_review
./docs
```

Deve leggere path da:

- argomenti CLI;
- variabili ambiente;
- file config nel workspace.

Variabili consigliate:

```text
MEMORIA_WORKSPACE_PATH=../memoria-workspace
MEMORIA_RULES_PATH=../memoria-rules
MEMORIA_KNOWLEDGE_PATH=../memoria-knowledge
MEMORIA_SOURCES_PATH=../memoria-sources
```

### D.3 Creare CLI minima

Obiettivo iniziale:

```bash
memoria doctor
memoria inventory
memoria import-document --source local-books --path ../memoria-workspace/inbox/file.pdf
memoria run-demo --workspace ../memoria-workspace
memoria build-review-dashboard --workspace ../memoria-workspace
```

Non serve implementare tutto subito: basta definire lo scheletro e uno o due comandi realmente funzionanti.

### D.4 Aggiungere test minimi

Prima della migrazione completa, creare test su:

- validazione layout workspace;
- lettura configurazione;
- generazione path output;
- parsing di un mini documento test;
- output JSON-LD minimo valido.

---

## Fase E — Migrazione workspace dati esterno

Questa fase deve usare `P:\Comune\Me.Mo.Ri.a` come destinazione reale dei dati. Il repository `memoria-workspace` deve contenere solo manifest, configurazioni e template.

### E.0 Creare/validare struttura esterna

PowerShell:

```powershell
$root = "P:\Comune\Me.Mo.Ri.a"
$dirs = @(
  "inbox",
  "raw\offline",
  "raw\online",
  "processed\ocr_raw",
  "processed\ocr_normalized",
  "processed\chunks",
  "processed\extraction_candidates",
  "graph\jsonld",
  "graph\indexes",
  "graph\snapshots",
  "historian_review\pending",
  "historian_review\approved",
  "historian_review\rejected",
  "reports",
  "exports",
  "logs",
  "config",
  "backups"
)
foreach ($d in $dirs) { New-Item -ItemType Directory -Force (Join-Path $root $d) | Out-Null }
```

WSL/Linux, solo se il drive è montato, ad esempio `/mnt/p/Comune/Me.Mo.Ri.a`:

```bash
ROOT="/mnt/p/Comune/Me.Mo.Ri.a"
mkdir -p "$ROOT"/{inbox,reports,exports,logs,config,backups}
mkdir -p "$ROOT/raw"/{offline,online}
mkdir -p "$ROOT/processed"/{ocr_raw,ocr_normalized,chunks,extraction_candidates}
mkdir -p "$ROOT/graph"/{jsonld,indexes,snapshots}
mkdir -p "$ROOT/historian_review"/{pending,approved,rejected}
```

### E.1 Copiare dati originali

Origine tipica:

```text
documenti_processati/
historian_review/
outputs/
jsonld/
ocr/
```

Destinazione nel data root esterno:

```text
P:\Comune\Me.Mo.Ri.a\raw\
P:\Comune\Me.Mo.Ri.a\processed\
P:\Comune\Me.Mo.Ri.a\graph\jsonld\
P:\Comune\Me.Mo.Ri.a\historian_review\
P:\Comune\Me.Mo.Ri.a\reports\
```

### E.2 Separare stati di lavorazione

Consiglio:

```text
raw/                 # documento originale immutato
processed/ocr_raw/   # testo OCR non corretto
processed/ocr_normalized/ # testo normalizzato
processed/chunks/    # chunk per LLM/extraction
processed/extraction_candidates/ # candidati non approvati
historian_review/pending/ # da revisionare
historian_review/approved/ # approvati
historian_review/rejected/ # respinti
```

### E.3 Creare manifest del workspace descriptor

Creare nel repository `memoria-workspace`:

```text
memoria-workspace/manifest.yml
```

Esempio:

```yaml
workspace_id: memoria-cadimalanca-local
created_at: 2026-07-05
owner: APS / project team
data_policy: private-controlled
repository_role: descriptor_only
data_root:
  type: external_path
  windows_path: "P:\\Comune\\Me.Mo.Ri.a"
  env_var: MEMORIA_DATA_ROOT
paths:
  inbox: inbox
  raw: raw
  processed: processed
  graph: graph
  historian_review: historian_review
  reports: reports
  exports: exports
  logs: logs
  backups: backups
```

Il manifest descrive dove si trovano i dati; non li contiene. La CLI deve risolvere il path effettivo così:

1. `--data-root` esplicito;
2. variabile `MEMORIA_DATA_ROOT`;
3. `data_root.windows_path` nel manifest;
4. errore bloccante se il path non esiste.
```

### E.4 Non versionare file pesanti

Poiché i dati reali stanno in `P:\Comune\Me.Mo.Ri.a`, il repo `memoria-workspace` deve ignorare qualunque copia accidentale di dati pesanti:

```gitignore
# real data must stay in external data root
inbox/**
raw/**
processed/**
graph/**
historian_review/**
reports/**
exports/**
logs/**
backups/**

# keep only placeholders/templates
!**/.gitkeep
!sample-data/**
!templates/**
!config/*.example.yml
```

Se vuoi versionare dataset piccoli/demo, usare solo:

```text
memoria-workspace/sample-data/
```

e mai una copia integrale del data root esterno.

---

## Fase F — Migrazione knowledge

### F.1 Estrarre conoscenza dai documenti tecnici

Spostare in `memoria-knowledge` tutto ciò che risponde a domande come:

- Chi sono le entità rilevanti?
- Quali tipi di fonti esistono?
- Come si valuta una fonte storica?
- Come gestiamo alias, nomi incompleti, luoghi incerti?
- Che standard deve avere una scheda persona?
- Come si collega il modello a CIDOC-CRM?

### F.2 Struttura iniziale consigliata

```text
memoria-knowledge/domain/resistenza-romagna.md
memoria-knowledge/domain/caduti-civili-partigiani.md
memoria-knowledge/ontology/memoria-entity-model.md
memoria-knowledge/ontology/cidoc-crm-alignment.md
memoria-knowledge/guidelines/historian-review.md
memoria-knowledge/guidelines/evidence-grading.md
memoria-knowledge/guidelines/person-card-standard.md
memoria-knowledge/glossary/terminology.md
memoria-knowledge/sources-notes/german-docs-russia.md
```

### F.3 Collegare knowledge a rules

Ogni documento di knowledge che implica una regola deve citare la rule target.

Esempio in `evidence-grading.md`:

```md
Related rules:
- ../memoria-rules/confidence/confidence-scoring.yml
- ../memoria-rules/provenance/citation-policy.yml
```

---

## Fase G — Migrazione rules

### G.1 Identificare regole implicite

Cercare nei playbook e prompt frasi del tipo:

- “se due persone hanno stesso nome e stessa data…”;
- “non fondere senza evidenza…”;
- “richiede revisione storica se…”;
- “confidence alta/media/bassa…”;
- “ogni affermazione deve avere provenienza…”.

Queste diventano regole in `memoria-rules`.

### G.2 Regole iniziali consigliate

```text
memoria-rules/entity-resolution/person-merge-policy.yml
memoria-rules/entity-resolution/alias-policy.yml
memoria-rules/confidence/confidence-scoring.yml
memoria-rules/provenance/provenance-required-fields.yml
memoria-rules/review/review-gates.yml
```

### G.3 Esempio `review-gates.yml`

```yaml
version: 0.1.0
rules:
  - id: requires_historian_review_for_person_merge
    description: Person entities may not be automatically merged when birth date, death date, or source attribution conflict.
    severity: blocking
  - id: requires_source_for_claim
    description: Every biographical claim must reference at least one source fragment.
    severity: blocking
```

### G.4 Testare le regole

Ogni regola deve avere almeno un caso positivo e uno negativo in:

```text
memoria-rules/tests/
```

---

## Fase H — Migrazione sources

### H.1 Catalogare fonti

Creare:

```text
memoria-sources/catalogs/offline-sources.yml
memoria-sources/catalogs/online-sources.yml
memoria-sources/catalogs/archive-register.yml
```

Esempio:

```yaml
sources:
  - id: german_docs_russia_fond_500_opis_12475
    type: online_archive
    language: [de, ru]
    access: public_web
    wrapper: wrappers/germandocs
    ocr_profile: ocr-profiles/german-docs.yml
    notes: German wartime documentation from Russian archive portal.
```

### H.2 Spostare wrapper

Script specifici per scaricare o interrogare fonti online devono andare in:

```text
memoria-sources/wrappers/<source_id>/
```

Il motore deve chiamarli attraverso un contratto, non importare path casuali.

### H.3 Separare OCR profile da OCR engine

- `memoria-engine` contiene il codice OCR.
- `memoria-sources` contiene profili come lingua, DPI, PSM, preprocess.

Esempio:

```yaml
profile_id: german_docs_default
languages: [deu, rus]
dpi: 300
psm: 4
preprocess:
  deskew: true
  denoise: true
```

---

## 6. Ordine operativo consigliato per evitare big bang

### Incremento 1 — Solo bootstrap

Obiettivo: gli agenti sanno come lavorare.

Deliverable:

- `memoria-bootstrap/AGENTS.md`;
- developer playbook;
- repository map;
- current-next-increment;
- workspace code file.

Criterio di accettazione:

- un agente può aprire il workspace e spiegare dove modificare codice/dati/knowledge/rules/sources.

### Incremento 2 — Workspace descriptor + data root esterno validabile

Obiettivo: creare `memoria-workspace` come descrittore e validare `P:\Comune\Me.Mo.Ri.a` come root dati, senza migrare tutto.

Deliverable:

- `memoria-workspace/manifest.yml` con `data_root.windows_path: "P:\\Comune\\Me.Mo.Ri.a"`;
- `memoria-workspace/config/workspace.local.example.yml`;
- script `validate-external-data-root`;
- `.gitignore` sicuro;
- struttura minima creata sotto `P:\Comune\Me.Mo.Ri.a`.

Criterio di accettazione:

- `memoria doctor` o script equivalente valida sia il repository descriptor sia il data root esterno.

### Incremento 3 — Engine CLI minima

Obiettivo: comando `doctor` e `inventory`.

Deliverable:

- CLI installabile;
- `memoria doctor`;
- `memoria inventory --workspace ../memoria-workspace`.

Criterio di accettazione:

- la CLI non dipende dal vecchio repo.

### Incremento 4 — Migrazione demo dataset

Obiettivo: migrare solo 1-2 documenti campione.

Deliverable:

- campione in `memoria-workspace/raw/`;
- OCR esistente copiato in `processed/ocr_raw/`;
- un JSON-LD in `graph/jsonld/`;
- una review in `historian_review/pending/`.

Criterio di accettazione:

- il report demo mostra provenienza e stato review.

### Incremento 5 — Sources catalog

Obiettivo: catalogare le fonti senza riscrivere wrapper.

Deliverable:

- `offline-sources.yml`;
- `online-sources.yml`;
- collegamento a OCR profiles.

Criterio di accettazione:

- ogni documento demo ha un `source_id` riconosciuto.

### Incremento 6 — Rules minime

Obiettivo: rendere esplicite le regole più importanti.

Deliverable:

- provenance required fields;
- review gates;
- confidence thresholds.

Criterio di accettazione:

- un JSON-LD senza fonte fallisce la validazione.

### Incremento 7 — Knowledge iniziale

Obiettivo: documentare il modello storico.

Deliverable:

- entity model;
- historian review guideline;
- person card standard;
- evidence grading.

Criterio di accettazione:

- il report demo cita le guideline applicate.

### Incremento 8 — Migrazione pipeline MVP

Obiettivo: eseguire il flusso MVP completo nel nuovo layout.

Deliverable:

```text
raw document
→ OCR/chunk
→ extraction candidate
→ JSON-LD
→ review dashboard
→ feedback note
```

Criterio di accettazione:

- la demo da 10 minuti funziona usando solo i nuovi repository.

### Incremento 9 — Deprecazione vecchi path

Obiettivo: impedire nuove scritture nel layout monolitico.

Deliverable:

- warning nei vecchi script;
- documentazione aggiornata;
- issue di rimozione.

Criterio di accettazione:

- nessun nuovo output viene scritto nei vecchi path.

### Incremento 10 — Rimozione controllata

Solo quando tutto è validato.

Deliverable:

- backup del repo monolitico;
- tag finale;
- archiviazione documentata.

---

## 7. Controlli di qualità

### 7.1 Checklist pre-migrazione

- [ ] Branch/tag creato.
- [ ] Inventario file creato.
- [ ] File pesanti identificati.
- [ ] Dati sensibili identificati.
- [ ] Repository target creati.
- [ ] Workspace multi-repo apribile.
- [ ] `.gitignore` del workspace verificato.

### 7.2 Checklist dopo ogni incremento

- [ ] Test eseguiti.
- [ ] Roadmap aggiornata.
- [ ] `current-next-increment.md` aggiornato.
- [ ] Decision log aggiornato.
- [ ] Nessun dato personale in engine/bootstrap/rules/knowledge/sources se non previsto.
- [ ] Nessun path hardcoded al vecchio repo.

### 7.3 Checklist finale

- [ ] Pipeline demo eseguita nel nuovo layout.
- [ ] Dashboard storico generata.
- [ ] JSON-LD validato.
- [ ] Provenienza verificabile.
- [ ] Feedback per nuove ricerche preservato.
- [ ] Vecchi path deprecati.
- [ ] Documentazione aggiornata.

---

## 8. Testing strategy

### 8.1 Unit test

Nel repository `memoria-engine`:

- parsing path;
- validazione workspace;
- normalizzazione testo;
- generazione JSON-LD minimo;
- caricamento rules;
- caricamento source catalog.

### 8.2 Integration test

Testare il flusso:

```text
sample document → OCR mock → chunks → extraction candidate → JSON-LD → review item
```

### 8.3 Regression test

Usare un golden dataset piccolo, non sensibile:

```text
memoria-engine/examples/golden-dataset/
```

oppure, se contiene dati reali, tenerlo in:

```text
memoria-workspace/sample-data/
```

### 8.4 Test di provenienza

Ogni claim deve avere:

- `source_id`;
- `document_id`;
- `fragment_id` o riferimento equivalente;
- extraction method;
- timestamp;
- review status.

### 8.5 Test di review gating

Un’entità non revisionata non deve essere esportata come pubblicabile.

---

## 9. Rollback plan

La migrazione è reversibile finché:

- il repository originario non viene cancellato;
- i dati sono copiati e non mossi;
- i vecchi script non vengono eliminati;
- i tag Git sono conservati.

### Rollback rapido

Se un incremento fallisce:

1. Fermare la migrazione.
2. Annotare il problema in `memoria-bootstrap/docs/decision-log.md`.
3. Continuare a usare il repository monolitico.
4. Aprire issue o nota tecnica per correggere il nuovo layout.

### Rollback completo

```bash
git checkout main
git checkout pre-memoria-refactor-YYYYMMDD
```

Oppure ripristinare backup zip/cartella.

---

## 10. Rischi principali e mitigazioni

| Rischio | Effetto | Mitigazione |
|---|---|---|
| Migrazione big bang | blocco del progetto | incrementi piccoli, demo dataset prima del dataset completo |
| Path hardcoded | pipeline rotta | variabili `MEMORIA_*_PATH`, config workspace |
| Dati nel repo sbagliato | rischio privacy/IP | `.gitignore`, checklist, review |
| Knowledge duplicata | incoerenza | knowledge repo come fonte esplicativa, rules come fonte eseguibile |
| Regole non testate | merge errati | tests in `memoria-rules` + regression in engine |
| Playbook obsoleti | agenti confusi | aggiornare bootstrap a ogni incremento |
| Perdita provenienza | output non difendibile | provenance contract bloccante |
| Storico escluso dal workflow | schede non affidabili | review gates e dashboard nel workspace |

---

## 11. Contratti minimi tra repository

### 11.1 Engine → Workspace descriptor → External data root

Engine non deve assumere che i dati siano fisicamente dentro `memoria-workspace`. Deve risolvere il data root tramite `manifest.yml`, variabile `MEMORIA_DATA_ROOT` o parametro CLI.

Descriptor repo:

```text
memoria-workspace/manifest.yml
memoria-workspace/config/
memoria-workspace/templates/
```

Data root reale:

```text
P:\Comune\Me.Mo.Ri.a\raw\
P:\Comune\Me.Mo.Ri.a\processed\
P:\Comune\Me.Mo.Ri.a\config\
```

Output nel data root reale:

```text
P:\Comune\Me.Mo.Ri.a\processed\
P:\Comune\Me.Mo.Ri.a\graph\
P:\Comune\Me.Mo.Ri.a\historian_review\
P:\Comune\Me.Mo.Ri.a\reports\
```

Ogni comando CLI deve mostrare il data root risolto prima di scrivere file.

### 11.2 Engine → Rules

Engine legge regole versionate da:

```text
memoria-rules/**
```

Non deve incorporare policy storiche direttamente nel codice.

### 11.3 Engine → Knowledge

Engine può citare knowledge docs nei report, ma non deve dipendere da testo libero per decisioni deterministiche.

### 11.4 Engine → Sources

Engine legge cataloghi e profili OCR da `memoria-sources`.

Wrapper specifici devono rispettare un’interfaccia comune:

```text
source_id
fetch/list/download
metadata output
license/access notes
```

---

## 12. Criteri di accettazione della migrazione

La migrazione può considerarsi riuscita quando:

1. Il workspace multi-repo si apre correttamente.
2. La CLI o gli script equivalenti validano il layout multi-repo e l’esistenza di `P:\Comune\Me.Mo.Ri.a`.
3. Un documento campione attraversa la pipeline nel nuovo layout.
4. Viene prodotto almeno un JSON-LD con provenienza.
5. Viene prodotto almeno un item di review per lo storico.
6. Il report/demo mostra come fonti disomogenee vengono unite in una vista persona/evento/luogo.
7. Il feedback dello storico produce una nuova richiesta di ricerca o una nota di miglioramento.
8. La documentazione indica chiaramente il prossimo incremento.
9. Nessun dato reale è stato copiato in repo pubblicabili; i dati restano in `P:\Comune\Me.Mo.Ri.a` o in storage controllato equivalente.
10. Il repository monolitico può essere archiviato senza perdere operatività MVP.

---

## 13. Primo incremento consigliato dopo questo piano

### Titolo

`Bootstrap multi-repo + workspace vuoto validabile`

### Obiettivo

Permettere a un agente AI o sviluppatore umano di aprire il progetto, capire la struttura multi-repo e validare che i sei repository siano presenti.

### Deliverable

- `memoria-bootstrap/AGENTS.md`
- `memoria-bootstrap/memoria.code-workspace`
- `memoria-bootstrap/docs/developer-playbook.md`
- `memoria-bootstrap/docs/repository-map.md`
- `memoria-bootstrap/docs/current-next-increment.md`
- `memoria-workspace/manifest.yml` con riferimento a `P:\Comune\Me.Mo.Ri.a`
- script `validate-layout`
- script `validate-external-data-root`

### Test

- eseguire `validate-layout`;
- verificare presenza sibling repo;
- verificare `.gitignore` workspace;
- verificare accesso a `P:\Comune\Me.Mo.Ri.a`.

### Non fare ancora

- non migrare tutto il dataset;
- non riscrivere OCR;
- non cambiare modello JSON-LD;
- non introdurre nuove feature.

---

## 14. Nota finale

Questa migrazione non deve essere vista come una riorganizzazione estetica delle cartelle. È il passaggio da un repository di progetto a una **Knowledge Workspace Architecture**: codice, dati, conoscenza, regole, fonti e metodo di lavoro diventano componenti separati, versionabili e verificabili.

Il beneficio principale è che Me.Mo.Ri.A potrà scalare da una demo locale a un sistema collaborativo con più fonti, più storici, più dataset e più agenti AI senza perdere tracciabilità.
