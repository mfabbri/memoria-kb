# Aggiornamento 2026-06-12 - Consolidamento output MVP

Il pacchetto MVP non introduce un nuovo artefatto separato
`mvp_model_cards_reviewed.md/json`. La lettura delle schede modello in
revisione viene consolidata dentro `historian_review/review_session.md/json`,
che ora deve restare la vista canonica per storici/curatori.

`mvp_run_index.md/json` classifica gli artefatti per ruolo: output principali
da leggere, review storica, audit macchina e diagnostica tecnica. La scelta
riduce la dispersione dei file nella cartella `risultati\runs` e mantiene il
wrapper `run_mvp_workspace_pipeline.ps1` come unico flusso canonico.

Aggiornamento operativo: `run_mvp_workspace_pipeline.ps1` accetta ora
`-OutputProfile Demo|Full|Debug`, con `Full` come default compatibile. Il
profilo non cancella file e non cambia la pipeline: governa la lettura di
`mvp_run_index.md/json`, indicando quali categorie aprire per prime e quali
trattare come audit o diagnostica.

Aggiornamento percorso Demo: in modalita' `Demo`, `mvp_run_index.md/json`
include anche un `recommended_reading_order` e una sezione `Percorso Demo`.
Il percorso apre prima readiness, dossier, digest schede, review session,
riepilogo decisioni e materiali curatoriale/vault; ledger, queue, JSON e
diagnostica restano disponibili come approfondimento.

Regola per i prossimi incrementi: non aggiungere nuove coppie `.json/.md` senza
prima verificare se la vista puo' essere assorbita da un output esistente. I
`.json` restano utili per audit macchina e test; i `.md` devono essere
mantenuti solo quando servono davvero a una lettura umana.

Nota di rotta 2026-06-13: il ciclo MVP e' ormai abbastanza leggibile tramite
run specifiche, reports-only e wrapper `run_mvp_workspace_pipeline.ps1`. Il
prossimo consolidamento deve rientrare nel flusso principale: importare output
auditabili in uno store generale append-only, a partire da
`P:\Comune\Me.Mo.Ri.a\database\evidence.sqlite` se adatto, e derivare da li'
ledger, report, vault e pacchetto MVP. Il wrapper MVP resta preset/packager,
non database della conoscenza. Qualunque import deve conservare provenance,
run di origine, `source_document_id`, hash, sidecar, chunk/segmenti e stati
`unreviewed`/`pending`, senza creare `verified_facts` o modificare profili
canonici.

Aggiornamento 2026-06-13: il primo raccordo append-only verso lo store generale
e' implementato. `SQLiteEvidenceStore` include ora
`evidence_import_batches` e `evidence_records`, pensate per conservare segnali
candidati e decisioni di review senza usare la tabella dei claim validati.
Il comando `import_document_analysis_evidence_to_db.ps1` importa da una run
documentale/MVP link documento-persona, entita', claim candidati, claim
saltati, item di review queue, decisioni e piste documentali quando disponibili.
`run_mvp_workspace_pipeline.ps1` esegue questo import e registra
`evidence_store_import.md/json` in `mvp_run_index`. Il passaggio e'
idempotente per payload identico e append-only quando il payload cambia; non
crea `verified_facts`, non modifica profili JSON-LD e non promuove
`CandidateEvidenceClaim` a `EvidenceClaim`.

Aggiornamento 2026-06-13: `inspect_evidence_db.ps1` espone anche viste
read-only per lo store append-only: `-EvidenceImports`, `-EvidenceRecords` e
`-EvidenceSubjects`. Il run index MVP include un quicklook verso queste viste,
cosi' batch, tipi record e profili con segnali candidati sono verificabili
senza aprire manualmente i JSON tecnici. Anche questa ispezione non applica
decisioni e non deriva fatti.

Aggiornamento 2026-06-13: l'import append-only e l'ispezione dello store
espongono anche la copertura di scoping. `evidence_store_import.md/json`
riporta quanti record hanno un soggetto, un documento, o sono warning workflow
non scopiati; `inspect_evidence_db.ps1 -EvidenceCoverage` mostra la stessa
diagnostica per tipo record. Questo evita di interpretare i warning generali
come evidenze persona e prepara il futuro raccordo del ledger allo store,
senza creare `verified_facts` o modificare profili.

Aggiornamento 2026-06-13: `mvp_consolidated_review_ledger.md/json` puo'
includere una sezione di copertura read-only dallo store generale. Il ledger
resta derivato dai `mvp_pilot_summary.json`, ma il wrapper workspace lo genera
dopo l'import append-only e gli passa `database\evidence.sqlite` filtrato sulla
run corrente. La sezione indica quanti record dello store sono collegati ai
profili del ledger, ai documenti o a workflow non scopiati; non crea nuovi
profili, non applica decisioni e non produce fatti verificati.

Aggiornamento 2026-06-13: `historian_review/review_session.md/json` puo'
mostrare la stessa copertura passando dal ledger consolidato. La sessione non
interroga direttamente `evidence.sqlite`: riceve
`mvp_consolidated_review_ledger.json` dal wrapper workspace e riporta record
store, documenti distinti, tipi record e stati review come contesto operativo
per storici e curatori. Anche questo passaggio non applica decisioni e non
abilita patch o fatti verificati.

Aggiornamento 2026-06-14: il funnel dei claim documentali rende revisionabili
anche gli skip dei documenti strutturati online. I record
`SkippedStructuredDocumentClaimCandidate` conservano documento, fonte, URL,
profili/link candidati, motivo di blocco, prossima azione e stati
`unreviewed`/`not_publishable_without_human_review`. Il `MvpPilotSummary` li
porta nelle `reviewable_document_signals` quando rientrano nel perimetro
pilota, e la review queue li trasforma in domande per lo storico senza creare
claim, `verified_facts` o patch profilo.

Aggiornamento 2026-06-14: la review storica MVP espone anche
`historian_review/review_focus_decisions_table.md`, tabella Markdown
compilabile derivata da `review_session.json`. La tabella e' un adattatore
umano per gli item prioritari del `review_focus`: puo' essere convertita in
`review_decisions.compilato.json` e validata dal riepilogo decisioni esistente.
Non applica patch, non crea `verified_facts` e non modifica profili JSON-LD.

Aggiornamento 2026-06-19: lo stesso adattatore supporta anche
`historian_review/review_focus_decisions_cards.md`, dossier Markdown a schede
per storici e curatori non tecnici. `build_mvp_review_focus_decisions_table.ps1
-Mode ConvertTable` legge direttamente sia la tabella larga sia le cards,
produce `review_decisions.compilato.json` e puo' scrivere
`review_focus_decisions_cards_summary.md/json` accanto alla run. Le cards del
vault `40_Publication_Candidates` restano solo contesto di lettura; le decisioni
umane stanno in `historian_review`. Una micro-sessione compilata puo' portare
il riepilogo canonico a `partial_review`, ma continua a non pubblicare claim,
non creare `verified_facts` e non modificare profili.

Aggiornamento 2026-06-21: il flusso dataset-centrico minimo fino a
`verified_facts.preview` e' verificato. Una decisione su claim candidato puo'
essere raccolta in Markdown tramite
`build_mvp_review_focus_decisions_table.ps1 -Mode BuildQueueCards`, convertita
in JSON tecnico con `ConvertTable`, validata con
`summarize_mvp_review_decisions.ps1`, importata nello store append-only e
trasformata in `verified_facts.preview.md/json`. La run step 2
`mvp-step2-historical-targets-preview8-20260620-pipeline` ha prodotto una
preview con `Fatti preview: 1` e `Decisioni escluse: 5`. Il risultato resta
preview-only: non scrive fatti canonici, non modifica profili JSON-LD e non
applica patch.
La stabilizzazione successiva ha fissato anche il confine tecnico: una
`review_decision` generica non genera fact preview, nemmeno con `confirm`;
servono record importati come `historical_review_decision`. Le decisioni
workflow e le decisioni di ricerca restano escluse con motivo esplicito.

Aggiornamento operativo successivo: il wrapper MVP collega ora
`historian_review/verified_facts.preview.json` anche a
`historian_review/review_dashboard.md/json` e a `mvp_funding_dossier.md/json`.
La dashboard puo' mostrare dettagli brevi dei fact preview; il dossier espone
solo conteggi e stato. Entrambe le superfici ribadiscono che il risultato e'
preview-only e non canonico.

Aggiornamento dataset preview successivo: sono disponibili anche
`build_dataset_export_preview.ps1` e
`build_publication_card_snapshot_preview.ps1`. Il primo produce
`DatasetExportPreview` read-only da `evidence.sqlite`, `verified_facts.preview`
e, se disponibile, `profile_patch.preview`, con sezioni per persone, documenti,
decisioni, fact preview, patch preview e provenance. Il secondo congela le
`schede_modello` in `PublicationCardSnapshotPreview`, salvando hash della
scheda modello, hash del dataset export, decisioni/fatti preview collegati e
snapshot Markdown/JSON per profilo. Entrambi restano preview-only: non scrivono
nel DB, non modificano profili JSON-LD, non applicano patch e non pubblicano
schede.

Aggiornamento 2026-06-26: dataset export, snapshot schede e registro
decisioni/conflitti preview sono ora integrati nel wrapper MVP e nel
`mvp_run_index.md/json`. Con import evidence attivo vengono generati e
registrati; con `-SkipEvidenceImport` sono marcati skipped in modo esplicito.
Il `ReviewStorePreview` resta invece un wrapper dedicato
(`build_review_store_preview.ps1`) che legge il registro decisioni/conflitti e,
opzionalmente, valida read-only i record nello store. Non crea tabelle
canoniche, non migra dati reali e non produce `verified_facts` canonici.

Aggiornamento codice 2026-06-26/27: dopo l'audit
`docs/audit-preview-chain-codice.md`, e' stato introdotto un helper interno
`document_analysis/preview_payloads.py`, prima applicato al modulo pilota
`review_store_preview.py` e poi esteso a
`review_decision_conflict_register_preview.py`. Il refactor non cambia output
JSON/Markdown, wrapper pubblici o comportamento operativo; serve solo a
consolidare helper preview duplicati prima di eventuali tabelle canoniche.

# Aggiornamento 2026-06-05 - Digest schede pilota MVP

La run workspace MVP genera ora anche `mvp_pilot_cards_digest.md/json` nella
cartella `<RunId>-pipeline`. Il digest riassume le schede candidate del vault
per revisione e demo: stato per profilo, documenti principali, claim candidati,
piste documentali, prossima azione e path della scheda in
`40_Publication_Candidates/`.

Il digest e' un output derivato preview-only: non legge le note editoriali
Obsidian come fonte canonica, non modifica profili JSON-LD e non promuove claim
candidati a fatti verificati.

# Aggiornamento 2026-06-05 - Indice operativo run MVP

`run_mvp_workspace_pipeline.ps1` genera ora anche
`mvp_run_index.md/json` nella cartella `<RunId>-pipeline`. L'indice e' il primo
file da aprire dopo una run: riporta modalita' online/offline, indice profili,
profili selezionati, cartelle principali, artefatti presenti o mancanti e
prossime azioni di review.

Aggiornamento 2026-06-12: l'indice include anche `quicklook_commands` nel JSON
e una sezione `Comandi rapidi PowerShell` nel Markdown. I comandi sono pensati
per essere copiati una riga alla volta e mostrano subito readiness, dossier,
summary MVP, riepilogo decisioni e segnali chiave del pacchetto.

L'output e' solo operativo e preview-only: non modifica profili JSON-LD, non
promuove claim candidati e non rende Obsidian una fonte canonica.

# Aggiornamento 2026-06-05 - Diagnostica segnale MVP

`MvpPilotSummary` include ora una sezione `mvp_signal_diagnostics` preview-only
per rendere piu' leggibile il segnale effettivo del pacchetto pilota:
documenti totali, documenti unici stimati, gruppi duplicati, link nominali
deboli e profili con link ma zero claim.

La sezione non deduplica fisicamente documenti, non modifica profili JSON-LD e
non promuove claim candidati. Serve a distinguere conteggi grezzi e lavoro
revisionabile in una demo MVP finanziabile.

La stessa diagnostica viene esposta anche nel vault MVP, nel brief curatoriale e
nel `mvp_funding_dossier.md/json`, cosi' revisori e finanziatori possono leggere
il segnale netto senza aprire i JSON tecnici del riepilogo.

# Aggiornamento 2026-06-05 - Source coverage nel dossier MVP

La run workspace MVP puo' ora inoltrare alla pipeline documentale una fonte
online esplicita tramite `-Source`, insieme a `-IncludeSearchPlan` e
`-ExecuteFirstPlannedAttempt`. Quando la fase online produce
`online/profiles_meta_search.json`, il wrapper genera anche
`source_coverage_summary.json/.md` nella run pipeline.

Il dossier finanziamento puo' leggere questa copertura fonti e renderizzarla
come sezione audit-only: fonti riepilogate, profili coperti, candidati,
dettagli, `no_results`, documenti, claim candidati e azione consigliata. Il
report non modifica fonti YAML, profili JSON-LD, cache o fatti storici.

# Aggiornamento 2026-06-05 - Profili pilota preview dal workspace MVP

`run_mvp_workspace_pipeline.ps1` puo' ora costruire, su richiesta, una review
preview dei `CandidatePersonProfile` prodotti dalla run locale. Con
`-BuildCandidateProfileReview` e un piccolo insieme di
`-AcceptedCandidateProfileId`, il wrapper genera
`candidate_profile_review/preview_person_profiles/purocielo.index.jsonld` e lo
usa come indice profili della run MVP se non e' stato passato un
`-ProfilesIndex` esplicito.

Il passaggio resta preview-only: non modifica `ricerche/person_profiles`, non
promuove il CSV legacy a sorgente canonica, non crea `verified_facts` e serve
solo a confezionare schede pilota revisionabili per Obsidian e dossier.

# Aggiornamento 2026-06-05 - ReportsOnly workspace MVP

`run_mvp_workspace_pipeline.ps1` espone ora `-ReportsOnly`,
`-ReuseLocalRunId` e `-ReusePipelineRunId`. La modalita' riusa run locale e run
pipeline gia' presenti sotto `risultati\runs`, salta processazione locale,
review candidati, pipeline documentale e online, e rigenera solo gli output
derivati finali del pacchetto MVP.

Serve per iterare rapidamente su summary, review queue/sessione, vault, digest
schede, readiness, dossier e indice run quando gli input documentali sono gia'
stati prodotti. Il wrapper fallisce se le run riusate non esistono e mantiene il
flusso preview-only: nessuna modifica a profili JSON-LD, raw, cache o claim.

# Aggiornamento 2026-06-06 - Acquisizione fonti online nel flusso offline

`run_profiles_meta_search.ps1` espone ora `-AcquireDocumentsRoot`. Quando una
run online controllata produce `SourceDocument` di dettaglio con testo, il
runner puo' salvarlo come documento processabile sotto
`documenti_da_processare/fonti_online/<source_id>/<profile_slug>/`, insieme a
un sidecar `*.document.yaml` con `source_id`, URL, access date, `profile_id`,
`source_document_id`, `review_status: unreviewed` e `claim_eligible: true`.

Il passaggio resta preview-only: i report in `risultati/source_scouting` sono
solo scouting/audit, le result list non diventano documenti storici e nessun
claim candidato viene promosso a fatto verificato o applicato ai profili
JSON-LD canonici.

# Aggiornamento 2026-06-07 - Claim strutturati da sidecar online

La pipeline offline puo' ora trasformare i campi strutturati acquisiti dalle
schede online in `CandidateEvidenceClaim` preview-only. Il generatore legge i
metadata collegati ai quality file, riconosce `detail_assessment:
claim_candidates_extracted`, interpreta `detail_extracted_fields_json` tramite i
`claim_mappings` delle `DetailPageLogic` e produce claim con
`extraction_method: online_detail_structured_fields`.

Il comportamento resta source-aware e generale: `partigiani_italia` e' solo il
pilota, mentre la stessa logica vale per future fonti con `DetailPageLogic` e
mapping dichiarati. I claim restano `review_status: unreviewed`, richiedono un
link persona-documento non ambiguo e non modificano profili JSON-LD, cache, raw
archive o fatti verificati.

# Stato operativo dell'implementazione del meta motore

Data aggiornamento: 2026-05-31

## Scopo

Questo documento descrive lo stato **implementativo e operativo** del meta
motore di ricerca sulla Resistenza nel repository Ca' di Malanca.

Non e' una roadmap e non ricostruisce la sequenza dei passi svolti. Serve invece
a rispondere a queste domande pratiche:

- qual e' oggi la sorgente canonica dei profili persona;
- quali componenti del motore sono realmente implementati;
- quali comandi usare;
- quali test sono affidabili come quality gate;
- quali parti sono legacy, sperimentali o da non usare come base per nuove
  funzionalita'.

## Stato sintetico

Il meta motore oggi e' un package Python locale:

```text
code/caduti_fonti_report/
```

con entrypoint PowerShell in:

```text
scripts/
```

Sul portatile operativo usare preferibilmente PowerShell 7 (`pwsh`) per
wrapper, quality gate e verifiche manuali. Le invocazioni con
`powershell -ExecutionPolicy Bypass -File ...` restano compatibili come
fallback Windows PowerShell 5.1.

Nel sandbox Codex del repository usare invece il PowerShell 7 portable
allowlistato:

```powershell
.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Nota operativa per Codex: dentro il sandbox non usare `Start-Process` o
`Start-Job` per mettere in background quality gate o wrapper lunghi; possono
fallire con `windows sandbox: spawn setup refresh` prima di avviare il comando.
In sandbox usare il wrapper diretto con timeout adeguato. Fuori sandbox, per
verifiche lunghe, usare `Start-Process -Wait -PassThru` con stdout/stderr su
file log e controllare l'`ExitCode`.

La direzione architetturale corrente e':

```text
PersonResearchProfile JSON-LD
  -> PersonQuery compatibile
  -> SourceDefinition
  -> SearchStrategy
  -> Executor
  -> ResultListLogic
  -> DetailPageLogic
  -> SourceDocument / EvidenceClaim
  -> audit / report / revisione
```

La parte piu' importante da tenere ferma: **i profili JSON-LD sono ora la
sorgente operativa preferita solo se non derivano dal seed legacy
`caduti_purocielo.csv`**. Il CSV storico e' dismesso e non deve guidare nuove
run.

## Sorgente dati persona

### Canonica per le nuove iterazioni

Usare:

```text
P:\Comune\Me.Mo.Ri.a\ricerche\person_profiles\purocielo.index.jsonld
P:\Comune\Me.Mo.Ri.a\ricerche\person_profiles\purocielo-*.jsonld
```

Dal hardening T13 questi path devono essere passati in modo esplicito ai
wrapper o alle CLI Python, per esempio con `-ProfilesIndex
"$WorkspaceRoot\ricerche\person_profiles\purocielo.index.jsonld"`. Il package
installabile non deve piu' usare `memoria-engine\ricerche\person_profiles` come
fallback operativo implicito.

Stato dell'export:

```text
57 profili persona
1 indice JSON-LD
```

Ogni profilo e' un `PersonResearchProfile`, cioe' una memoria di ricerca, non
una biografia pubblicabile.

Contiene:

- `identity`: nome canonico, nome, cognome, alias, forme di nome;
- `seed`: payload originale importato dal CSV;
- `birth`, `death`, `formations`, `events`, `places`: dati iniziali come indizi;
- `search_hints`: indizi operativi revisionabili;
- `evidence_claim_ids`: collegamenti futuri a claim;
- `verified_facts`: vuoto finche' non esiste revisione;
- `conflicts`, `searched_sources`, `next_research`: spazi per feedback loop e
  revisione.

### Legacy

Il file:

```text
P:\Comune\Me.Mo.Ri.a\ricerche\caduti_purocielo.csv
```

resta solo come riferimento storico. Non va usato per nuove run, nuovi profili o
decisioni operative; i profili ancora marcati con quel `seed.source` vanno
rigenerati da fonti strutturate correnti.

Dal hardening T13 i comandi che leggono un CSV richiedono `--csv` o `-Csv`
esplicito. Il seed `caduti_purocielo.csv` resta bloccato per la generazione di
profili operativi salvo `--allow-legacy-csv`/`-AllowLegacyCsv` usato solo per
audit storico controllato.

Uso ammesso: recupero come documento. Il CSV puo' essere copiato in
`documenti_da_processare\legacy_documents\` e processato da inventario,
metadata/text extraction, link, claim e review. In quel caso entra nel flusso
come `tabular_document` auditabile, non come generatore privilegiato di profili.
La run locale produce anche:

```text
risultati/runs/<run_id>/document_analysis/candidate_person_profiles_from_documents.json
risultati/runs/<run_id>/document_analysis/candidate_person_profiles_from_documents.md
```

Questi output sono `CandidatePersonProfile` preview-only: riportano le righe
persona estratte dai documenti tabellari processati, con `review_status =
unreviewed` e `promotion_status = not_promoted`. Servono per far rientrare i
nominativi del CSV storico nel flusso ufficiale come candidati auditabili, non
per promuoverli automaticamente a `PersonResearchProfile` canonici.

Per trasformare un sottoinsieme in profili pilota senza toccare il repository
canonico usare:

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\build_candidate_person_profile_review.ps1 -CandidatesJson "P:\Comune\Me.Mo.Ri.a\risultati\runs\<run_id>\document_analysis\candidate_person_profiles_from_documents.json" -OutputDir "P:\Comune\Me.Mo.Ri.a\risultati\runs\<run_id>\document_analysis\candidate_profile_review" -Limit 10
```

Il wrapper produce una tabella Markdown, un template decisionale JSON e, quando
riceve decisioni compilate, un indice `preview_person_profiles\purocielo.index.jsonld`.
Questo indice e' un output di run: puo' alimentare summary e revisione MVP, ma
non sostituisce `ricerche\person_profiles\purocielo.index.jsonld`.

Per demo rapide il wrapper accetta anche `-AcceptedCandidateProfileId`, con
array di `candidate_profile_id` da trattare come `accepted` senza editare il
template JSON. Se e' presente `-DecisionsJson`, il file decisioni compilato ha
precedenza e gli ID inline vengono ignorati. Entrambi i percorsi producono solo
profili preview, summary e audit di run.

Debito roadmap aperto: i profili gia' presenti in
`ricerche\person_profiles\purocielo-*.jsonld` che riportano
`seed.source = ricerche\caduti_purocielo.csv` restano conservati per audit e non
vanno ripuliti manualmente in-place. In una fase successiva vanno sostituiti o
migrati con profili operativi ricostruiti da documenti processati, claim
candidati revisionati e fonti strutturate correnti. La migrazione dovra'
produrre report di audit, elenco profili legacy coinvolti, mappatura vecchio
profilo -> nuovo profilo e nessuna promozione automatica del seed a fatto
verificato.

## Componenti implementati

### Modelli principali

File:

```text
code/caduti_fonti_report/models.py
```

Modelli disponibili:

- `Caduto`: riga legacy dal CSV;
- `PersonQuery`: input compatibile per il motore corrente;
- `PersonResearchProfile`: profilo JSON-LD operativo;
- `ProfileSeed`, `ProfileIdentity`, `ProfileSearchHint`;
- `SourceDocument`;
- `EvidenceClaim`;
- `SearchRun`;
- `ResearchReport`;
- `SourceQualityAudit`.

### Profili persona JSON-LD

File:

```text
code/caduti_fonti_report/person_profiles.py
code/caduti_fonti_report/profile_repository.py
code/caduti_fonti_report/profiles_runner.py
code/caduti_fonti_report/planned_search_attempts.py
code/caduti_fonti_report/search_strategy_planner.py
code/caduti_fonti_report/candidate_profile_updates.py
code/caduti_fonti_report/apply_profile_patch.py
scripts/export_person_profiles.ps1
scripts/run_profiles_meta_search.ps1
scripts/plan_profile_search.ps1
scripts/build_candidate_profile_updates.ps1
scripts/build_profile_patch.ps1
scripts/apply_profile_patch.ps1
tests/test_person_profiles.py
tests/test_profile_repository.py
tests/test_profiles_runner.py
tests/test_search_strategy_planner.py
tests/test_candidate_profile_updates.py
tests/test_apply_profile_patch.py
```

Capacita' attuali:

- generare profili JSON-LD dal CSV seed;
- scrivere indice `purocielo.index.jsonld`;
- leggere e riserializzare profili;
- convertire `PersonResearchProfile -> PersonQuery`;
- preservare il seed senza promuoverlo a fatto verificato.
- caricare profili dall'indice JSON-LD senza leggere il CSV;
- lanciare una run operativa da `PersonResearchProfile`;
- conservare `profile_id` e `profile_source_file` negli output.
- pianificare tentativi di ricerca da `PersonResearchProfile` e definizioni
  fonte YAML come `PlannedSearchAttempt` read-only, con priorita', campi usati,
  rischio, `manual_review_required`, motivazioni e uso esplicito dei
  `search_hints` solo come indizi;
- includere opzionalmente i `PlannedSearchAttempt` nel JSON di una run profili,
  come audit del piano previsto, senza cambiare i tentativi eseguiti dai
  connettori;
- collegare in modo audit-only ogni `SourceResult` al `PlannedSearchAttempt`
  corrispondente quando `-IncludeSearchPlan` e' attivo, tramite campi
  `matched_planned_attempt_*` basati su confronto esatto della query;
- eseguire, con modalita' esplicita, solo il primo tentativo pianificato per
  una coppia `ProfileId`/`Source` e `Limit > 0`, conservando nel JSON il piano,
  la modalita' di esecuzione e il match audit-only;
- rendere visibile nel Markdown generale e nelle schede singole l'audit del
  piano di ricerca, inclusi modalita' di esecuzione, limite tentativi,
  `matched_planned_attempt_*`, tentativo e query pianificata quando disponibili;
- generare anteprime `CandidateProfileUpdate` dai claim estratti, senza merge
  automatico nei profili.
- generare anteprime `CandidateProfileUpdate` anche da
  `CandidateEvidenceClaim` documentali non revisionati, mantenendole
  `pending` e preview-only.
- classificare le proposte in bucket di revisione;
- generare `CandidateNewProfile` preview-only per persone collegate;
- separare persone collegate gia' presenti nell'indice profili da nuovi profili
  candidati;
- generare `ProfilePatch` da `ReviewDecision` accettate;
- applicare una `ProfilePatch` a un singolo profilo solo con comando esplicito,
  backup, dry-run e audit JSON/Markdown.

Il vecchio comando di export da `ricerche\caduti_purocielo.csv` e' dismesso.
`scripts/export_person_profiles.ps1` richiede ora `-Csv` esplicito e blocca quel
file salvo recupero storico dichiarato con `-AllowLegacyCsv`.

Run da profilo JSON-LD:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 `
  -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld `
  -ProfileId person:purocielo:andreoli-dino `
  -Source memorie_locali `
  -Limit 1
```

Run da profilo JSON-LD con piano di ricerca incluso nel JSON:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 `
  -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld `
  -ProfileId person:purocielo:andreoli-dino `
  -Source storia_memoria_bo `
  -Limit 1 `
  -IncludeSearchPlan
```

I report JSON prodotti da `run_profiles_meta_search.ps1` possono essere
riepilogati in un `SourceCoverageSummary` offline. Il riepilogo misura copertura
fonte-profilo, stati dei risultati, hit, documenti e claim candidati, senza
interrogare fonti live, modificare profili o promuovere fatti verificati.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\summarize_source_coverage.ps1 `
  -InputJson risultati\source_scouting\partigiani_italia_purocielo_top10.json `
  -OutputJson risultati\source_scouting\source_coverage_summary.json `
  -OutputMd risultati\source_scouting\source_coverage_summary.md
```

Piano di ricerca da profilo JSON-LD, senza esecuzione live:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\plan_profile_search.ps1 `
  -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld `
  -ProfileId person:purocielo:andreoli-dino `
  -Source partigiani_italia `
  -OutputJson risultati\profile_search_plan_andreoli_partigiani.json
```

Anteprima feedback loop:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_candidate_profile_updates.ps1 `
  -ReportJson risultati\test_profili_guazzaloca_storia_memoria_bo.json `
  -ProfileJsonld ricerche\person_profiles\purocielo-guazzaloca-laura.jsonld `
  -OutputJsonld risultati\candidate_profile_updates_guazzaloca_laura.jsonld `
  -OutputMd risultati\candidate_profile_updates_guazzaloca_laura.md
```

Anteprima feedback loop con claim candidati documentali:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_candidate_profile_updates.ps1 `
  -CandidateClaimsJson risultati\document_analysis\candidate_evidence_claims.json `
  -ProfileJsonld ricerche\person_profiles\purocielo-guazzaloca-laura.jsonld `
  -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld `
  -OutputJsonld risultati\candidate_profile_updates_guazzaloca_laura.jsonld `
  -OutputMd risultati\candidate_profile_updates_guazzaloca_laura.md
```

Patch preview da decisioni:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_profile_patch.ps1 `
  -CandidateUpdatesJsonld risultati\candidate_profile_updates_guazzaloca_laura.jsonld `
  -DecisionsJson risultati\review_decisions_guazzaloca_laura.sample.json `
  -OutputJson risultati\profile_patch_guazzaloca_laura.preview.json `
  -OutputMd risultati\profile_patch_guazzaloca_laura.preview.md
```

### Registry fonti

File:

```text
../memoria-sources/registry/camalanca_fonti.yaml
```

Il registry attivo contiene 18 fonti. Tutte hanno copertura dichiarativa nei
quattro livelli:

```text
../memoria-sources/source_profiles/
../memoria-sources/source_strategies/
../memoria-sources/source_result_logic/
../memoria-sources/source_detail_logic/
```

Regola operativa: ogni nuova fonte deve entrare direttamente da questi livelli,
senza nuovi connettori legacy.

### Motore uniforme fonti

Componenti principali:

```text
code/caduti_fonti_report/source_definitions.py
code/caduti_fonti_report/source_strategies.py
code/caduti_fonti_report/search_result_logic.py
code/caduti_fonti_report/detail_page_logic.py
code/caduti_fonti_report/connectors/uniform_source_connector.py
```

Flusso implementato:

```text
SourceDefinition
  -> SearchStrategy dichiarativa
  -> SearchExecutor
  -> GenericResultParser / parser dedicato
  -> SearchResultAssessment
  -> fetch dettaglio
  -> DetailPageAssessment
  -> SourceDocument / EvidenceClaim candidati
```

Le liste risultati producono candidati, non fatti storici. Le schede dettaglio
possono produrre claim candidati solo se la `detail_logic` lo consente. I claim
restano `unreviewed`.

### Quality gate fonti

Componenti:

```text
code/caduti_fonti_report/source_quality_audit.py
scripts/test_quality_gate.ps1
scripts/run_source_quality_audit.ps1
scripts/run_quality_gate.ps1
```

Il quality gate mirato corrente esegue:

- repository e runner da profili JSON-LD;
- planner read-only da `PersonResearchProfile` a `PlannedSearchAttempt`;
- analisi documentale offline, inclusi input processing plan, OCR Tesseract,
  OCR batch, qualita', chunking fisico, classificazione LLM/fake dei chunk,
  language detection documentale, segmentazione debole, menzioni candidate,
  linking persona-documento, entita, claim candidati, duplicati, cluster e run
  documentale ripetibile;
- filtri candidati del parser generico;
- parsing/scaffolding Bundesarchiv Invenio offline;
- audit qualita' fonti;
- validazione registry;
- detail page logic.

Comando consigliato:

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Ultimo stato verificato:

```text
222 test OK
registry valido
18 fonti analizzate
0 errori
0 warning
```

### Persistenza e output

Implementati:

- raw document store in `data/raw/`;
- inventario documenti raw/cache in `document_analysis`, con report JSON e
  Markdown;
- registrazione manuale di foto/scansioni tramite sidecar `document.yaml`,
  senza modificare il file originale e senza OCR automatico;
- registrazione batch ricorsiva di foto/scansioni manuali tramite sidecar
  per-file `<nomefile>.<estensione>.document.yaml` minimi, con titolo derivato,
  riferimento archivistico di raccolta/cartella, `review_status: unreviewed` e
  senza modificare i file originali;
- acquisizione controllata di campioni da German Docs in Russia tramite
  `scripts/download_german_docs_sample.ps1`, con Playwright usato solo come
  executor tecnico, limite esplicito `-MaxPages`, download di immagini pagina,
  sidecar per-file `<nomefile>.jpg.document.yaml`, manifest JSON/Markdown e
  `review_status: unreviewed`; il comando non esegue OCR, non produce claim e
  non e' un percorso di scraping massivo;
- registrazione esplicita di trascrizioni manuali o OCR esterni non revisionati
  per foto/scansioni gia' registrate, come `ProcessedDocumentText` derivato,
  senza modificare l'immagine originale e senza produrre claim;
- OCR locale opzionale con Tesseract per foto/scansioni gia' registrate, con
  registrazione del testo derivato come `external_ocr_unreviewed` e diagnostica
  tecnica di qualita OCR, opzioni PSM/OEM/DPI e candidati revisionabili a note
  di pagina/riferimenti dal layout TSV, fallback prudente di PSM quando il PSM
  richiesto produce pagina vuota, piu' OCR opzionale a regioni su copie
  temporanee preprocessate; conserva `ocr_page_segmentation_mode`,
  `ocr_effective_page_segmentation_mode` e `ocr_fallback_attempts`, senza
  modificare l'immagine originale e senza produrre claim;
- OCR batch ricorsivo e parallelizzabile in modo controllato su immagini gia'
  registrate con sidecar per-file `<nomefile>.<estensione>.document.yaml` o
  fallback legacy `document.yaml`, con skip degli output esistenti, distinzione
  tra testi gia' presenti ed errori reali, e report JSON/Markdown finale;
- registrazione batch di HTML locali tramite sidecar automatici derivati, senza
  modificare gli HTML originali e senza produrre claim;
- processed metadata dei documenti raw/cache in `data/processed/documents`,
  senza estrazione testo, OCR o claim automatici; i sidecar per-file copiati in
  una run locale preferiscono il raw sibling corrente rispetto al path
  originario dichiarato nel campo `file`, evitando doppi record
  `file_without_sidecar` quando si prepara un dataset pilota;
- piano preview-only di processing degli input locali, con catalogazione
  ricorsiva di documenti testuali, DOCX, HTML, immagini, mappe storiche
  candidate, PDF, audio, video e formati non supportati; produce solo azioni
  proposte come `image_ocr_required`, `historical_map_georeferencing_required`,
  `audio_transcription_required` o `video_transcription_required`, senza
  avviare OCR, trascrizioni, georeferenziazioni, LLM o claim;
- catalogo preview-only delle mappe storiche candidate, derivato dal piano
  input locale, con `HistoricalMapCandidate`, provenance, hash,
  `georeferencing_status: not_georeferenced`,
  `map_ocr_status: not_extracted` e `review_status: unreviewed`, senza OCR,
  senza georeferenziazione e senza claim;
- estrazione testo offline da HTML/testo/DOCX locale gia' inventariato in
  `data/processed/documents`, senza OCR, senza claim e preservando
  `claim_eligible`, `review_status` e provenienza dai metadati;
- chunking fisico offline di `ProcessedDocumentText` gia' estratti, con
  `PhysicalDocumentChunk` derivati, offset carattere, overlap controllato,
  confini boundary-aware quando disponibili, hash del chunk, provenance verso
  il file testo, `review_status: unreviewed`, metadati audit-only sul confine
  e warning tecnici audit-only su encoding sospetto/mojibake, senza
  segmentazione semantica, senza claim e senza modificare testi originali o
  profili;
- classificazione LLM/fake preview-only dei `PhysicalDocumentChunk`, con
  `LLMChunkClassification` derivati, modello/prompt, confidenza, ragioni,
  warning, persone/luoghi/date menzionate come candidati di triage e
  `review_status: unreviewed`, senza runtime LLM obbligatorio nella quality
  gate, senza claim, senza profili e senza fatti verificati;
- language detection documentale offline su `ProcessedDocumentText` gia'
  estratti, con `DocumentLanguageAssessment` deterministici per documento,
  lingua primaria, candidate language, confidenza, warning, provenance e
  `review_status: unreviewed`, senza LLM, senza traduzioni, senza routing
  automatico OCR/prompt e senza claim;
- segmentazione debole offline su `PhysicalDocumentChunk` gia' prodotti, con
  `WeakDocumentSegment` deterministici per triage, offset nel chunk, regole
  applicate, confidenza, provenance, warning tecnici propagati dal chunk e
  `review_status: unreviewed`, senza LLM, senza menzioni risolte, senza claim,
  senza fatti verificati e senza modifiche ai profili;
- estrazione di menzioni candidate offline da `WeakDocumentSegment`, con
  `PersonMentionCandidate`, `PlaceMentionCandidate`, `DateMentionCandidate`,
  `FormationMentionCandidate` e `ArchivalReferenceMentionCandidate`
  deterministici, offset nel segmento, contesto, regole applicate, confidenza,
  provenance e `review_status: unreviewed`, senza risoluzione automatica a
  profili o oggetti JSON-LD non-persona, senza claim, senza fatti verificati e
  senza modifiche ai profili;
- catalogo operativo minimo dei luoghi in `../memoria-knowledge/places/`, con
  indice JSON-LD e identita' luogo revisionabili usate solo per linking
  preview-only; il duplicato legacy `ricerche/places/` e' stato rimosso;
- collegamento offline preview-only tra `PlaceMentionCandidate` e luoghi
  esistenti del catalogo tramite `CandidateDocumentPlaceLink`, con match
  normalizzato esatto su etichetta preferita o alias, score, warning,
  provenance e `review_status: unreviewed`, senza geocoding, eventi impliciti,
  claim, presenza persona-luogo o fatti verificati;
- estrazione preview-only di `CandidateMilitaryGlossaryMention` da
  `ProcessedDocumentText`, con glossario JSON-LD minimo in
  `../memoria-knowledge/glossary/military`, matching deterministico di termini,
  alias e abbreviazioni militari, provenance verso testo, metadati e raw,
  supporto ai testi derivati sia da documenti sia da immagini/OCR gia'
  registrati; il duplicato legacy `ricerche/military_glossaries` e' stato
  rimosso,
  `review_status: unreviewed`, senza OCR automatico, senza risoluzione a
  `MilitaryUnit`, senza presenze territoriali, claim, patch profilo o fatti
  verificati;
- generazione offline preview-only di `ResearchFeedbackAction` da menzioni
  documentali supportate nello stesso segmento o chunk da formazione,
  riferimento archivistico, luogo o data, con contesto, fonti suggerite,
  warning, provenance e `review_status: unreviewed`, senza eseguire ricerche,
  senza generare claim, senza modificare profili e senza promuovere indizi a
  fatti;
- generazione offline preview-only di `FeedbackSearchPlan` da
  `ResearchFeedbackAction`, `CandidateDocumentPersonLink`, profili JSON-LD
  esistenti e fonti censite, usando il planner fonte-specifico solo per
  produrre tentativi revisionabili; le azioni senza `person_id` possono essere
  risolte solo da un link documento-persona unico e non ambiguo della stessa
  run, altrimenti restano `manual_profile_resolution_required`, e nessuna
  ricerca online viene avviata;
- assessment qualita' offline dei documenti processati, con classificazione
  prudente per revisione, audit-only o OCR manuale, senza produrre claim;
- collegamento offline preview-only tra testi documentali processati e profili
  persona JSON-LD esistenti, tramite `CandidateDocumentPersonLink` con score,
  motivi, contesto e `review_status: unreviewed`, senza modificare profili e
  senza produrre claim; il matching include forme canoniche, alias, varianti di
  nome, varianti normalizzate conservative con punteggiatura/spazi e
  `search_hints` identitari usati solo come indizi revisionabili;
- estrazione offline preview-only di `ExtractedEntity` da testi documentali
  processati, limitata a pattern prudenti per date, formazioni e riferimenti
  archivistici, inclusi riferimenti Bundesarchiv `RH` emersi da OCR/testi
  processati, con contesto, score, motivi e `review_status: unreviewed`, senza
  produrre claim;
- generazione offline preview-only di `CandidateEvidenceClaim` documentali da
  entita estratte e link documento-persona non ambigui, solo per documenti
  classificati `ready_for_manual_review`, senza promuoverli a `EvidenceClaim`
  e senza modificare profili o `verified_facts`; questo flusso include anche
  DOCX/Word testuali locali gia' processati, limitatamente ai campi coperti da
  regole testate come date esplicite di nascita/morte e formazione;
- generazione offline preview-only di `CandidateDuplicateDocument` per duplicati
  esatti rilevati da `sha256` nei metadati processati, senza eliminare,
  unificare o modificare documenti originali;
- generazione offline preview-only di `DocumentCluster` per documenti testuali
  simili, tramite similarita TF-IDF/coseno deterministica in puro Python su
  `ProcessedDocumentText`, senza merge, deduplicazione definitiva, claim o
  modifiche ai documenti originali;
- SQLite evidence store;
- import report JSON in DB;
- import `PersonQuery` in DB;
- export audit Markdown;
- export audit CSV;
- export Obsidian;
- report Markdown/JSON e schede singole.

Questi componenti funzionano ancora soprattutto sul modello `PersonQuery` e sul
runner corrente. Il collegamento diretto da `PersonResearchProfile` al runner e'
il prossimo raccordo architetturale da implementare.

## Fonti: maturita' operativa

### Piu' consolidate

- `partigiani_italia`: percorso uniforme con cache/sessione autenticata
  assistita;
- `storia_memoria_bo`: executor dedicato e detail logic con claim candidati;
  i permalink persona costruiti ma non validati live restano riferimenti da
  revisione manuale e non forzano il fetch della scheda dettaglio; quando la
  scheda persona e' validata, la detail logic estrae anche campi candidati come
  genitori, titolo di studio, occupazione, causa morte, servizio militare,
  luogo operativo, periodo di riconoscimento, memoriale, ruolo/status e
  bibliografia;
- `storia_memoria_bo_excel`: fonte locale tabellare forte;
- `cwgc`: strategia e result logic stabili;
- `tna_wo417`: percorso uniforme con detail logic archivistica.
- `german_docs_in_russia_wwii`: fonte archivistica pubblica per documenti
  tedeschi della Seconda guerra mondiale. Entra dal registry a quattro livelli
  e viene usata soprattutto via gerarchia Fond/Opis/Delo/pagina; il motore di
  ricerca interno resta secondario perche' l'indice puo' essere incompleto.
  Il downloader dedicato lavora solo su campioni piccoli e produce immagini
  pagina con sidecar e manifest, senza claim automatici.

### In transizione

- `bundesarchiv_invenio`: login, submit e candidati Tektonik/Klassifikation
  stabilizzati; scaffolding offline per possibili record puntuali aggiunto; il
  live resta da consolidare sui nodi realmente espandibili.
- `tna_hs9`, `oesta_ais_feldsuche`, `oesta_kriegsarchiv`, `noi_partigiani`,
  `atlante_stragi`, `albi_memoria_re`: copertura dichiarativa presente, ma non
  tutte hanno lo stesso livello di fixture e test specifici.

Aggiornamento 2026-05-27: `atlante_stragi` ha ora un primo raffinamento
offline e live controllato della ricerca avanzata. La fonte non viene piu'
interrogata come ricerca persona WordPress generica: usa il form avanzato
`page_id=349` via POST con data, luogo dedotto e tipologia vittima. La result
logic accetta solo link a schede episodio `id_strage`, esclude pagine
istituzionali/navigazione e mantiene il dettaglio come `detail_document_only`
finche' non esiste un parser fonte-specifico di schede episodio/vittime. Nessun
titolo pagina viene promosso a claim candidato.

Aggiornamento successivo 2026-05-27: la risoluzione dei luoghi per
`atlante_stragi` e' ora dichiarata nella strategia fonte e propagata nei
metadata dei `PlannedSearchAttempt` come `field_resolution.*`. Per esempio, il
mapping operativo `Purocielo / Ca Marcone -> comune=4030, provincia=39,
regione=8` e' tracciato con provenance, termini agganciati, label dei campi e
`review_status: unreviewed`. Questo mapping serve solo a compilare il form
avanzato della fonte e non modifica profili JSON-LD, claim o `verified_facts`.

Verifica eseguita:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
201 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
atlante_stragi: ricerca avanzata POST, no claim da titolo pagina
```

### Prudenziali/reference-only

- `memorie_locali`;
- `obd_memorial`;
- `pamyat_naroda`;
- `icrc_pow`.

Queste fonti vanno trattate come orientamento, `search_url_ready`,
`manual_review` o `reference_only` finche' non esistono fixture e detail logic
piu' forti.

### Acquisizione campione German Docs in Russia

Comando per un download controllato di poche pagine da un nodo `Delo` gia'
identificato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_german_docs_sample.ps1 `
  -NodeUrl "https://wwii.germandocsinrussia.org/ru/nodes/<delo-node>" `
  -OutputDir "P:\Comune\Me.Mo.Ri.a\Foto\wwii.germandocsinrussia.org\Fond 500\Opis 12475\Delo 30" `
  -ArchivalReference "Fond 500, Opis 12475, Delo 30" `
  -TitlePrefix "Fond 500 Opis 12475 Delo 30" `
  -StartPage 1 `
  -MaxPages 3 `
  -Zoom 7 `
  -DelaySeconds 1 `
  -OutputJson "risultati\runs\german-docs-delo-30-sample\german_docs_download_manifest.json" `
  -OutputMd "risultati\runs\german-docs-delo-30-sample\german_docs_download_manifest.md"
```

Comando per partire da un nodo `Opis`, enumerare i nodi `Delo` collegati e
scaricare le relative pagine in una struttura gerarchica `Fond/Opis/Delo`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_german_docs_sample.ps1 `
  -NodeUrl "https://wwii.germandocsinrussia.org/ru/nodes/<opis-node>" `
  -DownloadOpisDelos `
  -OutputDir "P:\Comune\Me.Mo.Ri.a\Foto\wwii.germandocsinrussia.org" `
  -ArchivalReference "Fond 500, Opis 12475" `
  -MaxDelos 5 `
  -MaxPagesPerDelo 0 `
  -MaxTotalPages 100 `
  -Zoom 7 `
  -DelaySeconds 1 `
  -OutputJson "risultati\runs\german-docs-opis-sample\german_docs_opis_download_manifest.json" `
  -OutputMd "risultati\runs\german-docs-opis-sample\german_docs_opis_download_manifest.md"
```

`-MaxPagesPerDelo 0` significa tutte le pagine del `Delo` selezionato, ma
resta sempre attivo il limite complessivo `-MaxTotalPages`.

Regole operative:

- usare solo nodi appartenenti alla fonte censita `german_docs_in_russia_wwii`;
- iniziare sempre con `-MaxPages` basso e manifest revisionabile;
- per il flusso `Opis`, iniziare sempre con `-MaxDelos` e `-MaxTotalPages`
  bassi prima di estendere l'acquisizione;
- conservare URL pagina, riferimento archivistico, `page_id`, numero pagina,
  data accesso e sidecar;
- non avviare OCR, georeferenziazione, claim o ricerche online a valle senza
  un comando esplicito separato.

### Form pubblici prudenziali

- `fondazione_fossoli`: il form pubblico "I Nomi di Fossoli" espone campi
  strutturati nome/cognome/luogo e data di nascita ed e' configurato tramite
  Playwright form executor; la result logic filtra i link di navigazione e la
  detail logic conserva eventuali record come documenti candidati senza
  produrre claim automatici.

## Comandi operativi principali

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Audit qualita' fonti:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_source_quality_audit.ps1 -ShowSummary
```

Esportazione profili persona JSON-LD: non usare piu'
`ricerche\caduti_purocielo.csv`. Per nuovi profili usare fonti strutturate
correnti e mantenere il CSV storico fuori dalle run operative.

Report operativo da profili JSON-LD:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 -ProfileId person:purocielo:andreoli-dino -Source memorie_locali -Limit 1
```

Report operativo legacy/compatibile da CSV:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_caduti_fonti_report.ps1 -Csv "P:\Comune\Me.Mo.Ri.a\ricerche\caduti_purocielo.csv" --limit 1 --source storia_memoria_bo
```

Inventario documenti raw/cache:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_raw_document_inventory.ps1 -RootDir data\raw -OutputJson risultati\document_analysis\document_inventory.json -OutputMd risultati\document_analysis\document_inventory.md
```

Wrapper locale delta per documenti gia' raccolti:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_local_document_processing.ps1 -RootDir data\raw -ProcessedDir data\processed\documents -RunId local-document-processing
```

Per il workspace condiviso `P:\Comune\Me.Mo.Ri.a`, il comando operativo
consigliato e':

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot "P:\Comune\Me.Mo.Ri.a" `
  -RunId "mvp-workspace-check" `
  -SkipOnline
```

Per una demo MVP ristretta a schede pilota scelte esplicitamente, lo stesso
wrapper accetta `-ProfileId` multipli e li inoltra al riepilogo MVP. Il filtro
non limita il processamento documentale: serve solo a produrre summary e vault
Obsidian piu' leggibili per revisione/finanziamento.

Il wrapper accetta anche `-ProfilesIndex`. Il default resta
`ricerche\person_profiles\purocielo.index.jsonld`, ma per una demo basata su
profili scelti da `CandidatePersonProfile` si puo' passare l'indice preview
generato dalla review:

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot "P:\Comune\Me.Mo.Ri.a" `
  -RunId "verify-mvp-preview-profile-index" `
  -SkipOnline `
  -ForceDerived `
  -ProfilesIndex "P:\Comune\Me.Mo.Ri.a\risultati\runs\<run_id>\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld" `
  -ProfileId "person:purocielo:andreoli-dino","person:purocielo:guazzaloca-laura" `
  -VaultLimit 10
```

Questo indice viene passato alla pipeline documentale e al riepilogo MVP. Resta
un output di run preview-only e non sostituisce il repository canonico dei
profili.

Il wrapper accetta anche `-ReviewDecisionsJson`. Se omesso, il riepilogo usa il
template generato in `historian_review\review_decisions.template.json`; se
fornito, il file compilato dallo storico viene passato a
`summarize_mvp_review_decisions.ps1` e aggiorna `review_decisions_summary`,
vault Obsidian e `mvp_package_readiness`. Questo passaggio resta una review
session: non applica patch ai profili e non marca i claim come verificati.

Nota PowerShell: `run_mvp_workspace_pipeline.ps1` espone
`[string[]]$ProfileId`; i profili multipli vanno passati come array sullo
stesso parametro, per esempio
`-ProfileId "person:purocielo:andreoli-dino","person:purocielo:guazzaloca-laura"`.
Non ripetere `-ProfileId` piu' volte nello stesso comando.

Il wrapper usa solo `documenti_da_processare` come input raw, scrive derivati
in `documenti_processati`, report in `risultati`, cataloghi da `ricerche` e
inizializza/usa `database\evidence.sqlite` come SQLite compatibile per audit.
Non va usata l'intera root condivisa come `RootDir` documentale.

Il wrapper scrive `manifest.json`, `run_summary.md` e report sotto
`risultati/runs/<run_id>/`. Orchestra metadati, testo,
`DocumentLanguageAssessment`, chunk fisici, classificazione LLM opzionale dei
chunk, segmenti deboli, menzioni candidate e `ResearchFeedbackAction` usando
cache delta hash-based: una seconda run con input e parametri invariati marca
gli step attivi come `skipped_cached`; il summary mostra anche il delta degli
input per step, con conteggi di file aggiunti, modificati o rimossi e path di
esempio; `-ForceDerived` rigenera gli output derivati. Lo step OCR batch e'
parte del wrapper locale ma resta opt-in: si attiva solo con `-RunOcr`, puo'
usare `-PreprocessBeforeOcr` e `-EnableRegionOcr`, e `-ForceOcr` rigenera gli
output OCR esistenti solo quando `-RunOcr` e' presente. Quando OCR e' attivo,
il wrapper locale crea anche
`risultati/runs/<run_id>/document_analysis/ocr_batch.log`, passa il progresso
OCR al `run.log` generale come `STEP PROGRESS ocr_batch ...` e consente di
regolare la frequenza con `-OcrProgressEvery`. La classificazione LLM
resta spenta di default e viene registrata come `skipped_not_enabled` finche'
non si passa `-EnableLlmChunkClassification` o si imposta
`CADUTI_LLM_CHUNK_ENABLED=true` nel `.env` locale. Senza `-RunOcr`, una richiesta
`-ForceOcr` viene tracciata ma non avvia OCR, per evitare OCR accidentale su
archivi locali reali.
I runner documentali scrivono anche `run.log` nella cartella della run, con
timestamp ISO, inizio/fine run, inizio/fine step, stato, motivo di skip/cache
e durata. Lo standard di roadmap e' piu' ampio del solo start/end: ogni wrapper
end-to-end deve esporre fasi e progressi consultabili durante la run, inclusi
scan/snapshot/hash degli input, conteggi di item, errori non fatali, fase
corrente, scrittura degli output e heartbeat per lavori lunghi. Il wrapper
locale ha iniziato questo allineamento con `SNAPSHOT START/PROGRESS/END` e
`STEP PROGRESS` per `input_processing_plan` e con log OCR dedicato per
`ocr_batch`; lo stesso criterio va portato agli altri wrapper. Il wrapper MVP
workspace usa inoltre un transcript PowerShell in
`risultati/runs/<run_id>-wrapper.log`, utile per ricostruire l'orchestrazione
complessiva e l'output dei comandi figli.

Registrazione prudente di un documento manuale gia' raccolto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_manual_document.ps1 -File data\raw\manual_uploads\2026\05\documenti-foto-test\RH_20_10_199_0006.jpg -SourceId manual_uploads -Title "Foto documento RH 20/10/199 0006" -ArchivalReference "RH 20/10/199 0006"
```

Registrazione batch prudente di immagini manuali gia' raccolte:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_manual_documents_batch.ps1 -RootDir data\raw\manual_uploads\2026\05\documenti-foto-test -SourceId manual_uploads -TitleTemplate "{filename}" -ArchivalReference "Da assegnare - import batch documenti-foto-test" -AccessDate 2026-05-16 -OutputJson risultati\document_analysis\manual_image_registration_batch.json -OutputMd risultati\document_analysis\manual_image_registration_batch.md
```

Nota: per cartelle con piu' immagini, la registrazione batch crea sidecar
per-file nel formato `<nomefile>.<estensione>.document.yaml`. Il vecchio
`document.yaml` accanto al file resta supportato per il caso singolo documento.

Registrazione batch di HTML locali gia' raccolti:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_html_documents.ps1 -RootDir data\raw\manual_uploads\2026\05\documenti-foto-test\www.camalanca.it -SourceId camalanca_html -BaseUrl https://www.camalanca.it/ -AccessDate 2026-05-11
```

Processed metadata offline dei documenti:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\extract_document_metadata.ps1 -RootDir data\raw -OutputDir data\processed\documents -SummaryJson risultati\document_analysis\document_metadata_extraction.json
```

Text extraction offline da HTML/testo/DOCX processato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\extract_document_text.ps1 -MetadataDir data\processed\documents -RawRootDir data\raw -OutputDir data\processed\documents -SummaryJson risultati\document_analysis\document_text_extraction.json
```

Chunking fisico offline da testi processati:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\chunk_document_text.ps1 -TextDir data\processed\documents -OutputDir data\processed\documents -OutputJson risultati\document_analysis\document_chunks.json -OutputMd risultati\document_analysis\document_chunks.md
```

I `PhysicalDocumentChunk` sono un livello tecnico di preparazione per
segmentazione debole, menzioni candidate e routing linguistico. Non sono
segmenti semantici, non producono claim e non validano fatti storici.

Verifica eseguita il 2026-05-18 con piano operativo salvato in:

```text
docs/prossimo-passo-document-chunking-fisico.md
```

Test focalizzati:

```powershell
python -m unittest tests/test_document_chunking.py tests/test_document_text_extraction.py tests/test_document_research_pipeline.py -v
```

Esito:

```text
10 test OK
```

Quality gate mirato dopo l'aggiunta di `tests/test_document_chunking.py`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
125 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Verifiche live separate su fonti censite:

```text
storia_memoria_bo: candidate_results, first_planned_attempt, match matched
fondazione_fossoli: no_results, first_planned_attempt, match matched
```

Chunking boundary-aware:

Verifica eseguita il 2026-05-19 con piano operativo salvato in:

```text
docs/prossimo-passo-chunking-boundary-aware.md
```

I `PhysicalDocumentChunk` provano ora a chiudere vicino a un confine testuale
affidabile, come fine paragrafo, fine frase o spazio vicino al limite massimo.
Quando non esiste un confine utile resta attivo il fallback a finestra fissa.
Ogni chunk conserva `boundary_strategy`, `boundary_adjusted` e
`boundary_reason` come metadati audit-only. Il testo sorgente non viene
normalizzato o riscritto; offset, hash, provenance e `review_status` restano
il riferimento operativo.

Test focalizzati:

```powershell
python -m unittest tests/test_document_chunking.py tests/test_weak_document_segmentation.py tests/test_document_mention_extraction.py -v
```

Esito:

```text
15 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
144 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Classificazione LLM/fake preview-only dei chunk:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\classify_document_chunks.ps1 -ChunkDir data\processed\documents -OutputDir data\processed\documents -OutputJson risultati\document_analysis\llm_chunk_classifications.json -OutputMd risultati\document_analysis\llm_chunk_classifications.md
```

Le `LLMChunkClassification` sono sidecar di triage per i
`PhysicalDocumentChunk`. Conservano chunk, modello, prompt, provider,
confidenza, ragioni, warning e `review_status: unreviewed`; non producono
claim, non modificano profili e non validano fatti. Il provider predefinito e'
deterministico/fake per rendere test e quality gate indipendenti da un runtime
LLM reale; e' disponibile anche il provider opzionale `ollama-wsl`, che invoca
l'API locale di Ollama tramite `wsl -e curl http://127.0.0.1:11434/api/generate`,
con `format: json`, `stream: false` e prompt passato via stdin. Il parser legge
il campo `response`, accetta anche JSON incapsulato come stringa e, se il
provider restituisce output non valido, conserva un breve
`provider_diagnostics` preview-only per audit. Le liste LLM vengono normalizzate
anche quando il modello restituisce una singola stringa; chunk con molte persone
o molti luoghi sono marcati `triage_only`. Prompt e schema versionabili sono
salvati in `../memoria-rules/llm_prompts/chunk_classification/`; il percorso
legacy `ricerche/llm_prompts` non e' piu' un fallback operativo.

Esempio con Ollama installato in WSL:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\classify_document_chunks.ps1 -ChunkDir data\processed\documents -OutputDir data\processed\documents -OutputJson risultati\document_analysis\llm_chunk_classifications.json -OutputMd risultati\document_analysis\llm_chunk_classifications.md -Provider ollama-wsl -ModelName gemma3:4b
```

Verifica eseguita il 2026-05-19 con piano operativo salvato in:

```text
docs/prossimo-passo-classificazione-llm-chunk.md
```

Test focalizzati:

```powershell
python -m unittest tests/test_llm_chunk_classifier.py tests/test_document_chunking.py tests/test_weak_document_segmentation.py -v
```

Esito:

```text
24 test OK
```

Quality gate mirato dopo l'aggiunta di `tests/test_llm_chunk_classifier.py` e
del provider opzionale `ollama-wsl`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
151 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Classificazione prudente dei chunk affollati:

Verifica eseguita il 2026-05-21 con piano operativo salvato in:

```text
docs/prossimo-passo-classificazione-llm-chunk-affollati.md
```

`LLMChunkClassification` supporta ora la classe
`multi_person_biographical_list` per chunk che contengono molte persone,
elenchi di caduti o piu' schede biografiche. Questi output sono forzati a
`recommended_use: triage_only`, conservano warning audit-only come
`many_people_in_chunk` e restano `review_status: unreviewed`. La classe e'
presente anche nello schema e nel prompt `chunk_classification`; non abilita
claim, profili, patch o fatti verificati.

Test focalizzati:

```powershell
python -m unittest tests/test_llm_chunk_classifier.py tests/test_document_chunking.py tests/test_weak_document_segmentation.py -v
```

Esito:

```text
26 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
159 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Warning encoding nei chunk e segmenti:

Verifica eseguita il 2026-05-19 con piano operativo salvato in:

```text
docs/prossimo-passo-warning-encoding-chunk-segmentazione.md
```

I `PhysicalDocumentChunk` espongono ora `text_quality_warnings` quando il testo
contiene segnali tecnici di encoding sospetto/mojibake. I
`WeakDocumentSegment` propagano questi warning e li mantengono anche nel campo
`warnings`. Il testo originale non viene modificato o normalizzato: il warning
serve solo a triage e revisione.

Test focalizzati:

```powershell
python -m unittest tests/test_document_chunking.py tests/test_weak_document_segmentation.py tests/test_document_mention_extraction.py -v
```

Esito:

```text
15 test OK
```

Language detection documentale offline:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\detect_document_language.ps1 -TextDir data\processed\documents -OutputDir data\processed\documents -OutputJson risultati\document_analysis\document_language_assessments.json -OutputMd risultati\document_analysis\document_language_assessments.md
```

I `DocumentLanguageAssessment` stimano la lingua del documento per triage e
routing futuro. Non traducono, non sostituiscono il testo originale, non
selezionano automaticamente OCR/prompt e non validano fatti storici.

Verifica eseguita il 2026-05-18 con piano operativo salvato in:

```text
docs/prossimo-passo-language-detection-documentale-mvp.md
```

Test focalizzati:

```powershell
python -m unittest tests/test_document_language_detection.py tests/test_document_chunking.py tests/test_document_text_extraction.py -v
```

Esito:

```text
13 test OK
```

Quality gate mirato dopo l'aggiunta di `tests/test_document_language_detection.py`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
130 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Verifiche live separate su fonti censite:

```text
storia_memoria_bo: candidate_results, first_planned_attempt, match matched
fondazione_fossoli: no_results, first_planned_attempt, match matched
```

Segmentazione debole offline da chunk fisici:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\weak_segment_document.ps1 -ChunkDir data\processed\documents -OutputDir data\processed\documents -OutputJson risultati\document_analysis\weak_document_segments.json -OutputMd risultati\document_analysis\weak_document_segments.md
```

I `WeakDocumentSegment` sono output preview-only per triage manuale e ricerca
successiva. Conservano chunk, offset, regole applicate, confidenza e
`review_status: unreviewed`; non sono menzioni risolte, non producono claim,
non validano fatti storici e non aggiornano profili.

Verifica eseguita il 2026-05-18 con piano operativo salvato in:

```text
docs/prossimo-passo-segmentazione-debole-documentale-mvp.md
```

Test focalizzati:

```powershell
python -m unittest tests/test_weak_document_segmentation.py tests/test_document_chunking.py tests/test_document_language_detection.py -v
```

Esito:

```text
13 test OK
```

Quality gate mirato dopo l'aggiunta di
`tests/test_weak_document_segmentation.py`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
134 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Verifiche live separate su fonti censite:

```text
storia_memoria_bo: candidate_results, first_planned_attempt, match matched
fondazione_fossoli: no_results, first_planned_attempt, match matched
```

Estrazione menzioni candidate da segmenti deboli:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\extract_document_mentions.ps1 -SegmentsDir data\processed\documents -OutputDir data\processed\documents -OutputJson risultati\document_analysis\document_mentions.json -OutputMd risultati\document_analysis\document_mentions.md
```

I `DocumentMentionCandidate` sono output preview-only per triage manuale e
ricerche successive. Conservano segmento debole, chunk, contesto, offset,
regole applicate, confidenza e `review_status: unreviewed`; non risolvono
identita', non producono claim, non validano fatti storici e non aggiornano
profili.

Verifica eseguita il 2026-05-18 con piano operativo salvato in:

```text
docs/prossimo-passo-estrazione-menzioni-documentali-mvp.md
```

Test focalizzati:

```powershell
python -m unittest tests/test_document_mention_extraction.py tests/test_weak_document_segmentation.py tests/test_document_chunking.py -v
```

Esito:

```text
12 test OK
```

Quality gate mirato dopo l'aggiunta di
`tests/test_document_mention_extraction.py`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
138 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Verifiche live separate su fonti censite:

```text
storia_memoria_bo: candidate_results, first_planned_attempt, match matched
fondazione_fossoli: no_results, first_planned_attempt, match matched
```

ResearchFeedbackAction documentali preview-only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_document_research_feedback_actions.ps1 -MentionsDir data\processed\documents -OutputDir data\processed\documents -OutputJson risultati\document_analysis\research_feedback_actions.json -OutputMd risultati\document_analysis\research_feedback_actions.md
```

Le `ResearchFeedbackAction` documentali raccordano menzioni persona supportate
nello stesso segmento o nello stesso chunk da formazione o riferimento
archivistico a piste di ricerca revisionabili. Conservano
`source_document_id`, `chunk_id`, `weak_segment_id`, contesto, `support_scope`,
warning, fonti suggerite e `review_status: unreviewed`. Non sono
`EvidenceClaim`, non lanciano ricerche online e non modificano profili JSON-LD.

Triage storici per `ResearchFeedbackAction`:

```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\build_research_feedback_actions_review_table.ps1 -ActionsJson risultati\document_analysis\research_feedback_actions.json -OutputMd risultati\document_analysis\research_feedback_actions_review_table.md
pwsh -ExecutionPolicy Bypass -File .\scripts\summarize_research_feedback_actions_review_table.ps1 -ActionsJson risultati\document_analysis\research_feedback_actions.json -ReviewTableMd risultati\document_analysis\research_feedback_actions_review_table.md -OutputJson risultati\document_analysis\research_feedback_actions_review_summary.json -OutputMd risultati\document_analysis\research_feedback_actions_review_summary.md
```

La tabella Markdown ha colonne stabili `decisione`, `valore`, `action_id`,
`documento`, `fonti_suggerite`, `indizi`, `contesto`, `note_storico`. Lo
storico compila solo `decisione` (`BUONA`, `DUBBIA`, `INUTILE`) e
`note_storico`; il riepilogo e' audit-only e serve a ordinare piste, profili e
documenti prioritari senza applicare patch, validare claim o aggiornare
`verified_facts`.

FeedbackSearchPlan documentale preview-only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_feedback_search_plan.ps1 -ActionsJson risultati\document_analysis\research_feedback_actions.json -LinksJson risultati\document_analysis\candidate_document_person_links.json -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld -SourcesYaml ..\memoria-sources\registry\camalanca_fonti.yaml -OutputJson risultati\document_analysis\feedback_search_plan.json -OutputMd risultati\document_analysis\feedback_search_plan.md
```

Il `FeedbackSearchPlan` collega azioni documentali, link documento-persona,
profili persona esistenti e fonti censite al planner fonte-specifico. Resta un
output revisionabile e non eseguibile automaticamente: conserva `action_id`,
`source_document_id`, `chunk_id`, `weak_segment_id`, `person_id`,
`profile_resolution`, `suggested_search_hints`, tentativi pianificati e
warning. Se manca `person_id`, puo' risolverlo solo da un
`CandidateDocumentPersonLink` unico e non ambiguo dello stesso documento; se il
link manca o e' ambiguo, il piano resta `manual_profile_resolution_required`;
se una fonte non e' censita, lo source plan resta `source_not_registered`. Non
crea claim, non applica patch profilo e non produce `verified_facts`.

Piano operativo salvato in:

```text
docs/prossimo-passo-feedback-search-plan-profile-resolution.md
```

Test focalizzati:

```powershell
python -m unittest tests/test_feedback_search_plan.py tests/test_document_person_linking.py -v
python -m unittest tests/test_document_research_pipeline.py tests/test_feedback_search_plan.py -v
```

Verifica locale eseguita il 2026-05-30:

```text
run_id: verify-feedback-search-plan-profile-resolution-after-impl
plans=1421
skipped=1331
resolved_from_candidate_links=90
ready_for_review=90
online_search_started=False
```

Verifica online singola eseguita su fonte censita:

```text
profile_id: person:purocielo:andreoli-dino
source: atlante_stragi
planned_execution_mode: first_planned_attempt
matched_planned_attempt_status: matched
result_status: no_results
```

Esito:

```text
18 test OK
7 test OK
```

Verifiche operative eseguite il 2026-05-30:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld -ProfileId person:purocielo:andreoli-dino -Source atlante_stragi -Limit 1 -IncludeSearchPlan -ExecuteFirstPlannedAttempt -OutputJson risultati\verify_live_atlante_stragi_andreoli_dino_feedback_plan.json -OutputMd risultati\verify_live_atlante_stragi_andreoli_dino_feedback_plan.md -OutputDir risultati\verify_live_atlante_stragi_andreoli_dino_feedback_plan_schede
```

Esito sintetico:

```text
source=atlante_stragi
status=no_results
planned_execution_mode=first_planned_attempt
matched_planned_attempt_status=matched
matched_planned_attempt_id=data-luogo-vittima-partigiana
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_local_document_processing.ps1 -RootDir data\raw -ProcessedDir data\processed\documents -RunId verify-feedback-search-plan-local
```

Esito sintetico:

```text
status=completed
run_id=verify-feedback-search-plan-local
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_document_research_pipeline.ps1 -RunId verify-feedback-search-plan-pipeline -ProcessedDir data\processed\documents -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld -SkipOnline
```

Esito sintetico:

```text
status=completed
feedback_search_plan: plan_count=1421, skipped_count=1421, online_search_started=False
```

Verifica eseguita il 2026-05-21 con piano operativo salvato in:

```text
docs/prossimo-passo-research-feedback-actions-documentali.md
```

Test focalizzati:

```powershell
python -m unittest tests/test_document_research_feedback_actions.py tests/test_document_mention_extraction.py tests/test_weak_document_segmentation.py -v
```

Esito:

```text
14 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
165 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Nota da prova reale sul DOCX Ca' di Malanca:

```text
segmenti deboli: 814
menzioni candidate: 934
ResearchFeedbackAction con supporto nello stesso segmento: 0
ResearchFeedbackAction con fallback stesso chunk: 736
```

Il fallback `support_scope:same_chunk` evita di perdere piste di ricerca nei
documenti lunghi, ma produce una coda molto rumorosa perche' molte
`PersonMentionCandidate` sono falsi positivi da menu, navigazione o intestazioni
editoriali, per esempio `Malanca Salta`, `Info Mostra` e `Documenti Statuto`.
Il prossimo micro-incremento consigliato e' filtrare meglio le menzioni persona
prima di generare azioni di feedback, senza cambiare profili reali, connettori o
claim.

Filtro falsi positivi delle menzioni persona:

Verifica eseguita il 2026-05-21 con piano operativo salvato in:

```text
docs/prossimo-passo-filtro-falsi-positivi-menzioni-persona.md
```

L'estrazione di `PersonMentionCandidate` scarta ora candidati con token
strutturali da menu, navigazione e intestazioni editoriali, come `Menu`,
`Video`, `Info`, `Mostra`, `Visita`, `Informazioni`, `Documenti`, `Statuto`,
`Centro`, `Salta`, `Pag` e `Quando`. Il filtro si applica solo alle menzioni
persona: formazioni e riferimenti archivistici restano invariati. I nomi reali
di test, come `Alfonso Bagni` e `Adelmo Brini`, restano candidati
`unreviewed`.

Test focalizzati:

```powershell
python -m unittest tests/test_document_mention_extraction.py tests/test_document_research_feedback_actions.py tests/test_weak_document_segmentation.py -v
```

Esito:

```text
17 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
167 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Menzioni candidate di luoghi e date:

Verifica eseguita il 2026-05-24 con piano operativo salvato in:

```text
docs/prossimo-passo-menzioni-luoghi-date-documentali.md
```

L'estrazione di `DocumentMentionCandidate` produce ora anche
`PlaceMentionCandidate` e `DateMentionCandidate` deterministici. Il supporto e'
conservativo: i luoghi sono limitati a un piccolo insieme esplicito di toponimi
ricorrenti nel dominio Ca' di Malanca/Resistenza locale, mentre le date sono
limitate a date numeriche o testuali esplicite; un anno isolato non viene
estratto come data candidata. I campi di linking JSON-LD non-persona restano
vuoti finche' non esiste uno step dedicato e testato. Le menzioni restano
`unreviewed`, non generano claim, patch, `verified_facts` o modifiche ai
profili reali.

Test focalizzati:

```powershell
python -m unittest tests/test_document_mention_extraction.py -v
```

Esito:

```text
8 test OK
```

Verifica di compatibilita' con `ResearchFeedbackAction`:

```powershell
python -m unittest tests/test_document_research_feedback_actions.py tests/test_document_mention_extraction.py -v
```

Esito:

```text
14 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
169 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

ResearchFeedbackAction con supporto luogo/data audit-only:

Verifica eseguita il 2026-05-24 con piano operativo salvato in:

```text
docs/prossimo-passo-research-feedback-actions-luoghi-date.md
```

Le `ResearchFeedbackAction` documentali possono ora usare anche
`PlaceMentionCandidate` e `DateMentionCandidate` come supporto audit-only per
una `PersonMentionCandidate`, oltre a formazione e riferimento archivistico. Il
supporto nello stesso segmento resta preferito; se necessario resta disponibile
il fallback prudente nello stesso chunk con `support_scope:same_chunk`. Luoghi e
date vengono aggiunti solo ai `suggested_search_hints` revisionabili: non
risolvono identificativi JSON-LD non-persona, non generano `FeedbackSearchPlan`
eseguibile, non lanciano ricerche online automatiche, non producono claim,
patch, `verified_facts` o modifiche ai profili reali. Solo un riferimento
archivistico continua ad alzare il rischio a `high` e a suggerire fonti
archivistiche estere.

Test focalizzati:

```powershell
python -m unittest tests/test_document_research_feedback_actions.py tests/test_document_mention_extraction.py -v
```

Esito:

```text
16 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
171 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Registrazione trascrizione manuale/OCR esterno per immagine gia' registrata:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_document_transcription.ps1 -File data\raw\manual_uploads\2026\05\documenti-foto-test\RH_20_10_199_0006.jpg -TextFile C:\tmp\trascrizione-rh-20-10-199-0006.txt -RootDir data\raw -OutputDir data\processed\documents -TranscriptionMethod manual_transcription -ReviewStatus unreviewed
```

OCR locale Tesseract per immagine gia' registrata:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_document_ocr.ps1 -File data\raw\manual_uploads\2026\05\documenti-foto-test\RH_20_10_199_0006.jpg -RootDir data\raw -OutputDir data\processed\documents -Language ita -PreprocessBeforeOcr -ReviewStatus unreviewed
```

Il testo OCR derivato conserva anche segnali tecnici come
`ocr_quality_status`, `ocr_word_count`, `ocr_mean_confidence` e
`ocr_low_confidence_words_count`. Quando il TSV di Tesseract e' disponibile,
conserva anche `ocr_layout_status`, dimensioni pagina, conteggio righe,
`ocr_footnote_candidates` e `ocr_reference_candidates`. Questi segnali sono
solo supporto alla revisione e non validano automaticamente alcun fatto storico.
Se il PSM richiesto non produce testo, il comando prova fallback controllati
`12`, `6` e `11` e registra il PSM effettivo in
`ocr_effective_page_segmentation_mode` insieme a `ocr_fallback_attempts`. Con
`-PreprocessBeforeOcr` usa una derivata temporanea scuro-su-bianco senza
toccare il raw originale e registra `ocr_preprocessing_status`; con
`-EnableRegionOcr` produce anche `ocr_region_outputs` per fascia bassa, pagina
sinistra e pagina destra, usando solo crop temporanei.

Nota: il fallback PSM evita molti casi `OCR Tesseract vuoto`, ma le foto
inclinate, curve o con ombre possono restare `low_confidence` e contenere
caratteri o righe riconosciuti male. Questi testi restano
`external_ocr_unreviewed` e non devono alimentare claim o fatti senza revisione.

OCR batch ricorsivo su cartella di immagini gia' registrate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_document_ocr_batch.ps1 `
  -RootDir data\raw\manual_uploads\2026\05\documenti-foto-test `
  -OutputDir data\processed\documents `
  -Language ita `
  -TesseractPath "C:\Program Files\Tesseract-OCR\tesseract.exe" `
  -PageSegmentationMode 4 `
  -Dpi 300 `
  -PreprocessBeforeOcr `
  -EnableRegionOcr `
  -MaxWorkers 2 `
  -ProgressEvery 25 `
  -LogFile risultati\document_analysis\ocr_batch.log `
  -OutputJson risultati\document_analysis\ocr_batch_report.json `
  -OutputMd risultati\document_analysis\ocr_batch_report.md
```

Il batch OCR scrive progressi timestampati su stdout e, se indicato
`-LogFile`, nello stesso file log: avvio, conteggio candidati, OCR progressivo,
report scritto e fine run.

Il report batch distingue:

- `processed`: OCR registrato nella run;
- `skipped_existing_text`: testo gia' presente, incluso il caso in cui il testo
  esiste in un percorso risolto dai metadati gia' processati;
- `skipped_missing_sidecar`, `skipped_sidecar_mismatch` e
  `skipped_duplicate_output`: skip strutturali;
- `error`: errore reale da diagnosticare.

Ultima verifica reale su `P:\Comune\Me.Mo.Ri.a\Foto` con PSM 4, DPI 300,
region OCR e fallback PSM:

```text
65 immagini
65 skipped_existing_text
0 errori OCR residui
```

Assessment qualita' documenti processati:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\assess_document_quality.ps1 -MetadataDir data\processed\documents -TextDir data\processed\documents -OutputDir data\processed\documents -SummaryJson risultati\document_analysis\document_quality_assessment.json
```

Link documento-persona preview-only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\analyze_source_documents.ps1 -TextDir data\processed\documents -MetadataDir data\processed\documents -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld -OutputJson risultati\document_analysis\candidate_document_person_links.json -OutputMd risultati\document_analysis\candidate_document_person_links.md
```

Link documento-luogo preview-only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_candidate_document_place_links.ps1 -MentionsDir data\processed\documents -PlacesIndex ..\memoria-knowledge\places\places.index.jsonld -OutputJson risultati\document_analysis\candidate_document_place_links.json -OutputMd risultati\document_analysis\candidate_document_place_links.md
```

I `CandidateDocumentPlaceLink` collegano menzioni luogo a identita' luogo gia'
presenti nel catalogo operativo `../memoria-knowledge/places/`. Restano
`unreviewed`, non
geocodificano, non creano eventi, non dimostrano presenza persona-luogo e non
generano claim o fatti verificati. I contesti chiaramente editoriali o di
navigazione vengono scartati solo come link derivati, mantenendo audit in
`skipped_mentions`.

Verifica eseguita il 2026-05-30:

```text
docs/prossimo-passo-candidate-document-place-links.md
wrapper: link_count=182, skipped_mention_count=461
run_id: verify-candidate-document-place-links
run_status=completed
candidate_document_place_links.step=completed
online_profile_search=skipped
quality_gate_targeted=214 test OK
```

Aggiornamento filtro rumore eseguito il 2026-05-30:

```text
docs/prossimo-passo-candidate-document-place-link-filter.md
wrapper: link_count=144, skipped_mention_count=499
navigation_or_boilerplate_context=38
duplicate_place_link_in_segment=0
run_id: verify-candidate-document-place-link-filter
run_status=completed
candidate_document_place_links.step=completed
online_profile_search=skipped
quality_gate_targeted=216 test OK
```

Verifica online singola di guardia su fonte censita:

```text
profile_id: person:purocielo:andreoli-dino
source: atlante_stragi
planned_execution_mode: first_planned_attempt
matched_planned_attempt_status: matched
result_status: no_results
```

Estrazione entita documentali preview-only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\extract_document_entities.ps1 -TextDir data\processed\documents -MetadataDir data\processed\documents -OutputJson risultati\document_analysis\extracted_entities.json -OutputMd risultati\document_analysis\extracted_entities.md
```

Claim candidati documentali preview-only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_candidate_document_claims.ps1 -EntitiesJson risultati\document_analysis\extracted_entities.json -LinksJson risultati\document_analysis\candidate_document_person_links.json -QualityDir data\processed\documents -OutputJson risultati\document_analysis\candidate_evidence_claims.json -OutputMd risultati\document_analysis\candidate_evidence_claims.md
```

I `CandidateEvidenceClaim` documentali possono alimentare il feedback loop dei
profili solo come `CandidateProfileUpdate` `pending`, senza generare patch o
modificare profili reali.

Duplicati documentali preview-only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\find_candidate_duplicate_documents.ps1 -MetadataDir data\processed\documents -OutputJson risultati\document_analysis\candidate_duplicate_documents.json -OutputMd risultati\document_analysis\candidate_duplicate_documents.md
```

Cluster documentali preview-only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\find_document_clusters.ps1 -TextDir data\processed\documents -OutputJson risultati\document_analysis\document_clusters.json -OutputMd risultati\document_analysis\document_clusters.md -SimilarityThreshold 0.86
```

Glossario militare preview-only:

Verifica eseguita il 2026-05-24 con piano operativo salvato in:

```text
docs/prossimo-passo-military-glossary-mvp.md
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\extract_military_glossary_mentions.ps1 -TextDir data\processed\documents -GlossaryDir ..\memoria-knowledge\glossary\military -OutputJson risultati\document_analysis\military_glossary_mentions.json -OutputMd risultati\document_analysis\military_glossary_mentions.md
```

Lo step carica glossari JSON-LD revisionabili e produce solo
`CandidateMilitaryGlossaryMention` da `ProcessedDocumentText`. I testi possono
derivare da documenti testuali, DOCX/HTML o da immagini/scansioni/mappe dopo
OCR o trascrizione gia' registrati; immagini senza testo restano saltate. Ogni
menzione conserva `document_class`, `raw_file`, `metadata_file`, `text_file`,
`extraction_status` e `review_status`. Non esegue OCR, non crea
`MilitaryUnit`, non collega unita' a luoghi o mappe e non produce claim o fatti
verificati.

Test focalizzati:

```powershell
python -m unittest tests/test_military_glossary.py -v
```

Esito:

```text
5 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
193 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Run documentale ripetibile con output isolati:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_document_research_pipeline.ps1 -RunId test-document-run -ProcessedDir data\processed\documents -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld -SkipOnline
```

La run scrive `manifest.json`, `run_summary.md` e report documentali sotto:

```text
risultati/runs/<run_id>/
```

La run documentale include anche `research_feedback_actions.json`,
`research_feedback_actions.md`, `feedback_search_plan.json` e
`feedback_search_plan.md` come output isolati. Include inoltre
`mvp_pilot_summary.json` e `mvp_pilot_summary.md`, un riepilogo derivato per
dimostrare un perimetro pilota dell'MVP con profili, documenti, link
persona-documento, entita', claim candidati e piste di revisione. Le azioni
sono generate da
menzioni gia' processate in `data/processed/documents`; il piano di feedback
raccorda solo azioni con profilo gia' risolto al planner fonte-specifico e
marca gli altri casi per revisione manuale. Questi report restano piste di
ricerca revisionabili e non avviano ricerche online automatiche, claim o fatti
verificati. Il riepilogo MVP e' preview-only: non modifica profili JSON-LD e
non rende pubblicabili i claim non revisionati.

Il riepilogo `mvp_pilot_summary.json` puo' alimentare un pacchetto Obsidian di
revisione con massimo 10 schede pilota, documenti collegati, indice evidenze
candidate e dashboard `10_Output/MVP_Pilot_Review.md`. Anche questo export e'
editoriale e preview-only: preserva le note umane, non applica patch e non
promuove claim a fatti verificati. Le schede persona MVP leggono anche il
`profile_source_file` del `PersonResearchProfile` quando disponibile e mostrano
un blocco di contesto operativo read-only: identita', nascita/morte seed,
formazioni, luoghi, eventi, fonti richiamate e search hints. Seed e search
hints sono marcati come indizi non pubblicabili.

Il riepilogo MVP include anche `profile_readiness`, una matrice derivata per
profilo pilota con conteggi di documenti, link persona-documento e claim
candidati, stato `ready_for_review`/`needs_*` e prossima azione revisionabile.
`ready_for_review` significa solo pronto per revisione umana, non pubblicabile.
Include inoltre `pilot_package_scorecard`, una sintesi compatta del pacchetto
demo con stato complessivo, profili pronti o bloccati, documenti, link, claim
candidati, item minimi di revisione e prossima azione. Anche questa scorecard
e' preview-only e serve a spiegare il perimetro MVP a revisori e finanziatori,
non a validare fatti storici.

Nota emersa dal test su documenti reali: zero claim candidati non significa
necessariamente zero materiale storico. Nei documenti multi-scheda, un singolo
DOCX puo' contenere molte biografie; il generatore di `CandidateEvidenceClaim`
usa ancora il documento intero come perimetro di attribuzione e blocca le
entita' quando trova piu' link persona-documento, con motivo
`ambiguous_or_missing_document_person_link`. Questo e' prudente, ma il pacchetto
MVP deve mostrare comunque le piste documentali revisionabili per profilo:
menzioni, contesti, entita' estratte, link persona-documento e
`ResearchFeedbackAction`.

Implementazione aggiornata: `MvpPilotSummary` include
`reviewable_document_signals` e `reviewable_document_signal_count`, derivati da
link persona-documento, entita' estratte, `ResearchFeedbackAction` e claim
saltati. La readiness per profilo puo' ora distinguere `needs_signal_review`
da `needs_claims`; la scorecard conta le piste come item minimi di revisione.
La review queue genera item `document_signal_review`, e il vault Obsidian mostra
le piste nella dashboard e nelle schede persona. Tutto resta `unreviewed` e
preview-only: nessun claim, profilo o fatto verificato viene promosso.

Aggiornamento 2026-06-12: i claim saltati da entita' estratte non sono piu'
solo contatori diagnostici. `candidate_claims.py` serializza
`SkippedCandidateClaim` con valore, contesto, tipo entita', segmento/chunk,
profili/link candidati e `recommended_next_action`; il summary li propaga come
`reviewable_document_signals` di tipo `skipped_claim_candidate`; la review queue
li rende item revisionabili mantenendo
`publication_status=not_publishable_without_human_review`.

Incremento segment-aware iniziale: `CandidateDocumentPersonLink` puo' ora
derivare anche da `DocumentMentionCandidate` e conservare `chunk_id` /
`weak_segment_id`; `ExtractedEntity` puo' derivare da menzioni segmentate di
date, formazioni e riferimenti archivistici; `CandidateEvidenceClaim` seleziona
il link persona-documento compatibile quando entita' e link condividono segmento
o chunk. Nei documenti multi-profilo questo riduce gli skip
`ambiguous_or_missing_document_person_link` senza promuovere claim a fatti.

Prossimo passo documentato:

```text
docs/prossimo-passo-mvp-piste-documentali-claim-zero.md
docs/prossimo-passo-mvp-piste-documentali-reviewable-signals.md
docs/prossimo-passo-mvp-link-claim-segment-aware.md
```
Quando il wrapper workspace collega la run locale, il riepilogo include anche
`document_intake_readiness`: asset raw rilevati, azioni input, OCR batch, testi
estratti, blocchi MVP e prossima azione raw-to-processed.

Implementato: la readiness separa immagini `ocr_required` da immagini di
supporto/controllo `claim_eligible: false`. Se un OCR produce `OCR Tesseract
vuoto` su un'immagine non decisiva e la scheda testuale equivalente e' gia'
disponibile, il pacchetto MVP mostra un warning revisionabile, non
`needs_document_intake`. Il blocco resta corretto solo quando l'OCR mancante
impedisce segnali storici necessari. La verifica
`mvp-sidecar-images-local-path-v1-ready` ha prodotto `ready_for_demo`, 3 profili
pilota, 36 claim candidati, 83 item di review, 6 immagini di supporto e 0
immagini blocking/unknown.

Dal riepilogo MVP si puo' generare anche una review queue minima sotto
`historian_review/`: `review_queue.json`, `review_queue.md` e
`review_decisions.template.json`. La queue trasforma readiness, link candidati,
claim candidati e warning in domande operative per il revisore, mantenendo
tutto `unreviewed` e preview-only. Il wrapper MVP la genera automaticamente e
la dashboard Obsidian la linka come lista di prossime decisioni.

La review queue distingue ora anche l'oggetto storico della decisione tramite
`subject_kind`: `person`, `date`, `place`, `event_context`, `claim`,
`document_signal` o `workflow`. I claim candidati su date, luoghi e contesti
evento vengono presentati con item dedicati (`date_entity_review`,
`place_entity_review`, `event_context_review`) e il Markdown mostra conteggi
per oggetto. Questo serve a dare agli storici una coda piu' leggibile senza
creare cataloghi evento/luogo definitivi e senza promuovere claim a fatti.

Il wrapper MVP genera inoltre, sempre sotto `historian_review/`, la tabella
`research_feedback_actions_review_table.md` e il riepilogo
`research_feedback_actions_review_summary.md/json` derivati dalle
`ResearchFeedbackAction` della run. Il primo summary resta normalmente
`pending`, perche' parte dalla tabella vuota: diventa utile dopo la restituzione
del file compilato dagli storici.

Il template decisioni compilato puo' essere validato e riepilogato in
`review_decisions_summary.json` e `review_decisions_summary.md`. Questo passo
conta decisioni accettate, pending e invalide, segnala item sconosciuti o
azioni non ammesse e ora aggiunge una `review_session` per profilo con stato
`not_started`, `in_review`, `ready_for_curator_review` o `invalid`. Il wrapper
MVP genera automaticamente il riepilogo dal template e lo passa al vault
Obsidian, dove dashboard e schede persona mostrano lo stato della sessione
storica. Il riepilogo resta audit-only: non modifica profili, database,
documenti processati, patch o fatti verificati.

Il riepilogo decisioni conserva `subject_kind` per ogni item e aggiunge
`counts_by_subject_kind`, anche dentro le sessioni per profilo. In questo modo
una sessione breve puo' essere centrata, per esempio, su tre profili e solo su
date/luoghi/eventi da chiarire, invece di costringere lo storico a una revisione
indifferenziata di tutte le piste.

Il vault MVP genera anche `40_Publication_Candidates/`, con una scheda candidata
preview-only per ogni profilo pilota esportato. Le schede candidate sintetizzano
profilo, documenti, claim candidati, piste documentali e stato della
`review_session`, ma restano viste editoriali derivate: non promuovono claim a
fatti verificati e non sono schede museali definitive.

Il vault scrive inoltre `10_Output/mvp_curatorial_brief.md`, una sintesi
curatoriale pensata per revisori, partner locali e finanziatori. Il brief
riassume obiettivo, stato pacchetto, profili pilota, schede candidate, sessione
storici, blocchi documentali e prossima azione, mantenendo esplicito che il
materiale e' revisionabile e non pubblicato.

Dopo l'export Obsidian il wrapper MVP genera anche
`mvp_package_readiness.json` e `mvp_package_readiness.md` nella run pipeline.
Il report controlla artifact richiesti, review queue, riepilogo decisioni,
dashboard, brief curatoriale, schede candidate e blocchi di intake, poi assegna
uno stato operativo (`ready_for_demo`, `needs_review_material`,
`needs_document_intake` o `missing_required_outputs`). E' un derivato
preview-only: non modifica profili, documenti, claim, patch o vault.

Il wrapper genera inoltre `mvp_funding_dossier.json` e
`mvp_funding_dossier.md`: un dossier breve, preview-only, pensato per partner
locali e finanziatori. Il dossier riusa readiness, summary MVP, riepilogo
decisioni e brief curatoriale; non modifica profili, non applica patch e non
presenta claim candidati come fatti storici.

Con `-SkipOnline` la run resta offline. Senza `-SkipOnline`, la ricerca online
passa da `PersonResearchProfile` JSON-LD e dalle fonti censite nel registry,
ma richiede filtri espliciti `-ProfileId`, `-Source` e `-Limit` maggiore di 0
per evitare run troppo ampie.

Wrapper locale delta documenti:

Verifica eseguita il 2026-05-24 con piano operativo salvato in:

```text
docs/prossimo-passo-wrapper-locale-delta-documenti.md
docs/prossimo-passo-wrapper-llm-opzionale-env.md
docs/prossimo-passo-wrapper-military-glossary.md
docs/prossimo-passo-language-routing-preview.md
```

Il wrapper locale delta:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_local_document_processing.ps1 -RootDir data\raw -ProcessedDir data\processed\documents -RunId local-document-processing
```

esegue in modo ripetibile gli step documentali locali gia' disponibili:

```text
input plan -> historical map catalog -> metadata -> text -> language -> language routing -> military glossary mentions -> chunks -> optional LLM chunk classification -> weak segments -> mentions -> ResearchFeedbackAction
```

Prima di `metadata`, lo step `input_processing_plan` cataloga gli asset della
cartella root e scrive `input_processing_plan.json/.md` nella run. Le azioni
proposte sono solo indicazioni di triage e non avviano OCR, trascrizioni
audio/video, georeferenziazioni, claim o ricerche online.

Subito dopo, `image_preprocessing_plan` legge `input_processing_plan.json` e
scrive `image_preprocessing_plan.json/.md`: classifica in modo conservativo le
immagini candidate, propone preprocessing/OCR strategy e lascia ogni decisione
in stato `unreviewed`. Il piano non modifica raw, non produce OCR e non e'
ancora consumato automaticamente da `ocr_batch`.

Subito dopo, lo step `historical_map_catalog` filtra le mappe candidate e
scrive `historical_map_catalog.json/.md` nella run. Il catalogo conserva
provenance e hash, marca OCR mappa e georeferenziazione come non eseguiti e
mantiene ogni candidato `unreviewed`.

Ogni run scrive un `LocalDocumentProcessingRunManifest` e un summary sotto
`risultati/runs/<run_id>/`. La radice dei report e' configurabile con
`-ResultsDir`; lo script PowerShell accetta anche l'alias esplicito
`-RemoteResultsDir`, utile per scrivere manifest, summary e report in una
cartella condivisa come `P:\Comune\Me.Mo.Ri.a\risultati`. `-ProcessedDir`
resta il parametro separato per sidecar, testi estratti e derivati tecnici; se
si vuole evitare storage locale sul portatile va spostato anche quello.
`-ResearchDir` permette di usare una radice `ricerche` remota, ad esempio
`P:\Comune\Me.Mo.Ri.a\ricerche`: nel wrapper locale deriva
`military_glossaries` solo per radici esplicite non-default, mentre senza
override il motore preferisce `..\memoria-knowledge\glossary\military`. Nella
pipeline documentale `person_profiles\purocielo.index.jsonld` resta derivato da
`ResearchDir`, mentre i luoghi preferiscono
`..\memoria-knowledge\places\places.index.jsonld` quando si usa la root
default. I parametri specifici restano disponibili come override espliciti
quando serve puntare a un file diverso. Gli
step sono cacheabili tramite firma hash-based
di input, parametri e output: se nulla cambia vengono marcati
`skipped_cached`; il summary mostra per ogni step il delta degli input,
inclusi file aggiunti, modificati o rimossi; con `-ForceDerived` vengono
rigenerati. Lo step `document_language_detection` produce report isolati nella
run e sidecar `*.language.json` nel processed store, mantenendo
`review_status: unreviewed`; non attiva routing automatico, traduzioni, OCR,
claim o ricerche. Lo step `document_language_routing` produce
`DocumentLanguageRoutingPlan` preview-only con language pack OCR, rule set e
lingua prompt suggeriti, piu' warning per casi multilingua, incerti o a bassa
confidenza; non avvia OCR, traduzioni, LLM, estrazioni o ricerche. Lo step
`llm_chunk_classification` e' opzionale, usa i
default locali `CADUTI_LLM_CHUNK_*` quando non si passano parametri espliciti e
produce solo `LLMChunkClassification` preview-only con
`review_status: unreviewed`. Lo step `military_glossary_mentions` produce
report isolati nella run da `ProcessedDocumentText` della run corrente, usando
i glossari JSON-LD revisionabili e mantenendo ogni menzione
`CandidateMilitaryGlossaryMention` `unreviewed`; non crea `MilitaryUnit`,
presenze territoriali, claim, patch profilo o fatti verificati. Gli step
`text`, `language`, `document_language_routing`,
`military_glossary_mentions`, `chunks`,
`llm_chunk_classification`, `weak segments`, `mentions` e
`ResearchFeedbackAction` sono ora limitati agli output della run corrente:
una run su una cartella di sole immagini senza OCR non riusa testi, chunk o
menzioni gia' presenti in `ProcessedDir`. Il wrapper non lancia ricerche online automatiche, non genera
`FeedbackSearchPlan`, non modifica profili JSON-LD reali, raw archive, cache
scaricate, claim validati o `verified_facts`. L'OCR batch resta opt-in:
`-RunOcr` abilita lo step, mentre `-ForceOcr` rigenera OCR solo insieme a
`-RunOcr`.

Test focalizzati:

```powershell
python -m unittest tests/test_document_language_detection.py tests/test_document_language_routing.py tests/test_local_document_processing_runner.py -v
```

Esito:

```text
20 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
193 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

ResearchFeedbackAction nella run documentale ripetibile:

Verifica eseguita il 2026-05-24 con piano operativo salvato in:

```text
docs/prossimo-passo-run-documentale-research-feedback-actions.md
```

Gli step `research_feedback_actions` e `feedback_search_plan` sono ora parte
della run documentale ripetibile. Il primo legge i `*.mentions.json` gia'
presenti nel processed store; il secondo legge le azioni isolate nella run e
produce un piano preview-only con `plan_count`. Entrambi scrivono i report solo
nella cartella della run e mantengono il manifest allineato. Non modificano
raw/cache, documenti processati, profili JSON-LD reali o connettori sorgente;
non generano `EvidenceClaim`, `ProfilePatch` o `verified_facts` e non avviano
ricerche online automatiche.

Test focalizzati:

```powershell
python -m unittest tests/test_document_research_pipeline.py tests/test_document_research_feedback_actions.py tests/test_feedback_search_plan.py -v
```

Esito:

```text
15 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
171 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Suite completa:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1
```

Nota: la suite completa contiene test legacy non ancora riallineati. Non usarla
come blocco architetturale per i prossimi passi, salvo intervento esplicito di
riallineamento.

## Cosa non usare come base per nuove funzionalita'

Non investire nuove funzionalita' su:

- modalita' legacy che assumono `runner.run_source` come punto centrale;
- aspettative vecchie su `storia_memoria_bo` basate sul generico
  `playwright_form_executor`;
- fallback di ricerca Storia e Memoria BO per data nascita/morte rimossi per
  ridurre duplicati;
- CSV come sorgente canonica della conoscenza;
- estrazione automatica di fatti storici da pagine risultato.

Questi elementi possono restare per compatibilita' o recupero, ma non devono
guidare la nuova architettura.

## Prossimo raccordo implementativo

Il feedback loop profili e la prima analisi documentale offline sono presenti
come percorsi preview-only e auditabili. La registrazione revisionabile di
trascrizioni manuali/OCR esterni per immagini e l'OCR locale opzionale con
Tesseract sono ora disponibili come raccordo minimo tra foto/scansioni e
analisi testuale; il batch OCR ora distingue correttamente testi gia' presenti
da errori reali e usa fallback PSM per ridurre i casi di pagina vuota. Sono
supportati anche DOCX/Word testuali locali gia' inventariati, estratti solo
come `ProcessedDocumentText` revisionabile; quando il documento e' collegato in
modo non ambiguo a un profilo persona e supera il quality assessment, puo'
produrre `CandidateEvidenceClaim` preview-only per campi coperti da regole
testate, senza generare fatti verificati. Sono
disponibili anche claim
candidati documentali preview-only, generati solo da documenti pronti per
revisione e link persona-documento non ambigui, e duplicati documentali esatti
preview-only basati su hash. Sono disponibili anche cluster documentali
preview-only basati su similarita testuale conservativa, utili per priorita di
revisione ma non per merge automatici. I claim candidati documentali possono
ora essere raccordati al feedback loop dei profili solo come update
revisionabili `pending`. E' disponibile anche un planner read-only che produce
`PlannedSearchAttempt` da `PersonResearchProfile` e YAML fonte senza eseguire
ricerche, senza modificare profili e senza promuovere indizi a fatti; il
runner profili puo' includere questi tentativi pianificati nel JSON di output
come audit opzionale, senza cambiare l'esecuzione dei connettori, puo'
segnare quale tentativo pianificato corrisponde a ciascun `SourceResult` tramite
campi audit-only `matched_planned_attempt_*` e puo' limitare esplicitamente la
run al primo tentativo pianificato quando sono indicati `ProfileId`, `Source` e
`Limit > 0`; il Markdown generale e le schede singole mostrano ora un blocco
audit-only del piano di ricerca con modalita' di esecuzione, limite dei
tentativi, stato match, tentativo e query pianificata quando disponibili. E'
disponibile anche una run documentale ripetibile
che raccoglie questi passaggi in `risultati/runs/<run_id>/`, con manifest e
summary Markdown, senza modificare profili reali o promuovere claim.

### Verifica live del planner eseguito

Verifica eseguita il 2026-05-18 con piano operativo salvato in:

```text
docs/prossimo-passo-verifica-live-planner-eseguito.md
```

Test focalizzati:

```powershell
python -m unittest tests/test_profiles_runner.py tests/test_search_strategy_planner.py tests/test_renderers.py -v
```

Esito:

```text
16 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
121 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Run live controllate eseguite:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld -ProfileId person:purocielo:andreoli-dino -Source storia_memoria_bo -Limit 1 -IncludeSearchPlan -ExecuteFirstPlannedAttempt -OutputJson risultati\verify_live_storia_memoria_bo_first_planned_andreoli_dino.json -OutputMd risultati\verify_live_storia_memoria_bo_first_planned_andreoli_dino.md -OutputDir risultati\verify_live_storia_memoria_bo_first_planned_andreoli_dino_schede
```

Esito verificato:

```text
source_id: storia_memoria_bo
status: candidate_results
planned_execution_mode: first_planned_attempt
planned_attempt_execution_limit: 1
matched_planned_attempt_status: matched
matched_planned_attempt_id: nome-cognome
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld -ProfileId person:purocielo:guazzaloca-laura -Source fondazione_fossoli -Limit 1 -IncludeSearchPlan -ExecuteFirstPlannedAttempt -OutputJson risultati\verify_live_fondazione_fossoli_first_planned_guazzaloca_laura.json -OutputMd risultati\verify_live_fondazione_fossoli_first_planned_guazzaloca_laura.md -OutputDir risultati\verify_live_fondazione_fossoli_first_planned_guazzaloca_laura_schede
```

Esito verificato:

```text
source_id: fondazione_fossoli
status: no_results
planned_execution_mode: first_planned_attempt
planned_attempt_execution_limit: 1
matched_planned_attempt_status: matched
matched_planned_attempt_id: nome-cognome
```

In entrambi i casi JSON e Markdown riportano coerentemente il blocco audit-only
del piano di ricerca. Gli output restano candidati revisionabili: nessun
`search_hint`, risultato o claim e' stato promosso a fatto verificato.

### Run documentale con audit planner online

Verifica eseguita il 2026-05-19 con piano operativo salvato in:

```text
docs/prossimo-passo-run-documentale-planner-audit.md
```

La run documentale ripetibile puo' ora passare allo step online del runner
profili le opzioni audit-only del planner:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_document_research_pipeline.ps1 `
  -RunId verify-pipeline-planner-storia-memoria-bo `
  -ProcessedDir data\processed\documents `
  -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld `
  -ProfileId person:purocielo:andreoli-dino `
  -Source storia_memoria_bo `
  -Limit 1 `
  -IncludeSearchPlan `
  -ExecuteFirstPlannedAttempt
```

Questi switch vengono registrati nel `manifest.json` della run e passati a
`run_profiles_report`, che conserva nel JSON/Markdown online il piano di
ricerca e puo' limitare l'esecuzione al primo tentativo pianificato. Il flusso
resta preview-only: non modifica profili JSON-LD reali, non modifica raw/cache,
non tocca connettori sorgente e non promuove claim o indizi a fatti verificati.

Test focalizzati:

```powershell
python -m unittest tests/test_document_research_pipeline.py tests/test_profiles_runner.py tests/test_renderers.py -v
```

Esito:

```text
14 test OK
```

Quality gate mirato:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_quality_gate.ps1 -TestSuite Targeted -ShowAuditSummary
```

Esito:

```text
139 test OK
registry valido
17 fonti analizzate
0 errori
0 warning
```

Verifiche live consigliate su fonti censite:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_document_research_pipeline.ps1 -RunId verify-pipeline-planner-storia-memoria-bo -ProcessedDir data\processed\documents -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld -ProfileId person:purocielo:andreoli-dino -Source storia_memoria_bo -Limit 1 -IncludeSearchPlan -ExecuteFirstPlannedAttempt
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_document_research_pipeline.ps1 -RunId verify-pipeline-planner-fondazione-fossoli -ProcessedDir data\processed\documents -ProfilesIndex ricerche\person_profiles\purocielo.index.jsonld -ProfileId person:purocielo:guazzaloca-laura -Source fondazione_fossoli -Limit 1 -IncludeSearchPlan -ExecuteFirstPlannedAttempt
```

Nuovo traguardo inserito in roadmap: introdurre un orchestratore offline da
cartella radice che cataloghi ricorsivamente documenti, immagini, PDF, audio,
video e formati non supportati, producendo un piano di processing con azioni
come OCR immagini, estrazione testo o trascrizione media. Questo traguardo e'
in corso nel wrapper locale unico: l'OCR batch e' disponibile solo con
`-RunOcr`, resta revisionabile, e il wrapper continua a non avviare
trascrizioni audio/video automatiche o promuovere output non revisionati a
claim o fatti verificati.
# Aggiornamento 2026-06-05 - Sessione revisione MVP

La run workspace MVP genera ora anche
`historian_review/review_session.md/json` nella cartella `<RunId>-pipeline`.
La sessione aggrega `mvp_pilot_summary`, `mvp_pilot_cards_digest`,
`review_queue` e `review_decisions_summary` per offrire a storici e curatori
una vista compatta: stato scheda per profilo, item prioritari, decisioni
accettate/pending/invalide, path della scheda candidata e prossima azione.

L'output e' derivato e preview-only: non applica decisioni, non modifica
profili JSON-LD, non legge Obsidian come fonte canonica e non promuove claim
candidati a fatti verificati.

Debito operativo chiuso per il perimetro MVP Purocielo: il wrapper workspace
espone `-ReportsOnly`, `-ReuseLocalRunId` e `-ReusePipelineRunId` per
rigenerare report, vault, digest, sessione review, readiness, dossier e indice
run a partire da run locale/pipeline gia' completate, senza rilanciare
processazione locale o pipeline documentale completa.
# Aggiornamento 2026-06-06 - Acquisizione online nel preset MVP

`run_document_research_pipeline.ps1` e `run_mvp_workspace_pipeline.ps1`
possono ora inoltrare l'acquisizione dei `SourceDocument` online tramite
`-AcquireDocumentsRoot`; il wrapper MVP espone anche `-AcquireOnlineDocuments`,
che usa come default
`<WorkspaceRoot>\documenti_da_processare\fonti_online`.

Il passaggio non processa immediatamente i documenti appena acquisiti: li rende
grezzi e auditabili per una successiva run locale su quel sottoinsieme. Le
schede dettaglio restano `unreviewed`, non aggiornano profili JSON-LD e non
promuovono claim candidati.
# Aggiornamento 2026-06-06 - InputRootDir nel preset MVP

`run_mvp_workspace_pipeline.ps1` espone ora `-InputRootDir` per processare un
sottoinsieme raw esplicito nella fase locale MVP. Se il parametro e' omesso, il
default resta `P:\Comune\Me.Mo.Ri.a\documenti_da_processare`; se e' passato,
il wrapper usa quella cartella come `RootDir` e registra root effettiva, root
default e flag sottoinsieme in `mvp_run_index.md/json`.

Quando la root e' un sottoinsieme, il wrapper usa anche un processed store
isolato sotto `risultati\runs\<RunId>-local\processed_documents` e registra sia
`processed_dir` sia `default_processed_dir` nell'indice run. Questa cartella e'
un derivato tecnico della run: non sostituisce
`P:\Comune\Me.Mo.Ri.a\documenti_processati`, che resta il processed store
condiviso/canonico del workspace.

Questo chiude l'handoff operativo tra acquisizione online e flusso offline: le
schede salvate sotto `documenti_da_processare\fonti_online\<source_id>\<slug>`
possono entrare in una nuova run MVP ristretta senza rilanciare tutta la
processazione del workspace.
# Aggiornamento 2026-06-08 - Consolidated Review Ledger MVP

La run workspace MVP genera ora anche
`mvp_consolidated_review_ledger.md/json` nella cartella `<RunId>-pipeline`.
Il ledger e' un primo registro consolidato preview-only dei profili pilota:
raccoglie da uno o piu' `mvp_pilot_summary` documenti collegati, link
persona-documento, claim candidati, piste documentali e run di origine,
deduplicando solo in modo conservativo.

Nel wrapper MVP corrente il ledger viene prodotto dalla run appena generata e
registrato in `mvp_run_index.md/json`; il comando dedicato
`build_mvp_consolidated_review_ledger.ps1` puo' invece ricevere piu' summary o
piu' run pipeline per costruire una vista cumulativa. Il ledger non modifica
profili JSON-LD, raw, cache, Obsidian o claim e non promuove candidati a fatti
verificati.
