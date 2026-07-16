# Guida rapida - Comandi per processazione locale, online e MVP

Questa e' una delle tre guide operative vive. Per scegliere la guida giusta
partire da `docs/guida-orientamento-operativo.md`. Per le attivita'
quotidiane guidate usare prima `docs/guida-attivita-quotidiane-cli.md`.

Questa guida serve a scegliere il wrapper giusto senza dover ricordare tutta la
pipeline.

Regola pratica:

```text
solo documenti locali -> run_local_document_processing.ps1
documenti processati + linking/claim/report -> run_document_research_pipeline.ps1
fonte online singola su profili JSON-LD -> run_profiles_meta_search.ps1
pacchetto MVP completo workspace -> run_mvp_workspace_pipeline.ps1
solo report MVP da run gia' completate -> run_mvp_workspace_pipeline.ps1 -ReportsOnly
ledger MVP da una o piu' run -> build_mvp_consolidated_review_ledger.ps1
```

Nel sandbox Codex usare sempre il PowerShell 7 portable:

```powershell
.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\<wrapper>.ps1
```

Sul portatile, fuori da Codex, si puo' usare `pwsh -ExecutionPolicy Bypass -File
...`. Il vecchio `powershell -ExecutionPolicy Bypass -File ...` resta fallback
Windows PowerShell 5.1.

## 1. Processazione locale dei documenti

Usare quando vuoi leggere `documenti_da_processare`, creare sidecar/testi
derivati, OCR opzionale, chunk, lingua, glossari, menzioni e candidati profilo.

Comando workspace consigliato:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_document_processing.ps1 `
  -RootDir "$WorkspaceRoot\documenti_da_processare" `
  -ProcessedDir "$WorkspaceRoot\documenti_processati" `
  -ResultsDir "$WorkspaceRoot\risultati" `
  -ResearchDir "$WorkspaceRoot\ricerche" `
  -RunId "local-check" `
  -ForceDerived
```

Output principali:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>\manifest.json
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>\run_summary.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>\run.log
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>\document_analysis\candidate_person_profiles_from_documents.md
```

Opzioni utili:

- `-RootDir`: cartella raw da processare. Non passare l'intera root workspace.
- `-ProcessedDir`: dove scrivere sidecar, testi e derivati tecnici.
- `-ResultsDir`: dove scrivere manifest e report di run.
- `-ResearchDir`: root legacy/esterna per profili e fallback. Senza override
  espliciti, luoghi e glossari militari sono preferiti da `..\memoria-knowledge`.
- `-RunId`: nome stabile della run sotto `risultati\runs`.
- `-ForceDerived`: rigenera output derivati anche se la cache li salterebbe.
- `-RunOcr`: abilita OCR batch. Senza questo switch l'OCR non parte.
- `-ForceOcr`: rigenera testi OCR esistenti, ma solo insieme a `-RunOcr`.
- `-PreprocessBeforeOcr`: usa preprocessing immagine prima di OCR.
- `-EnableRegionOcr`: abilita letture OCR a regioni.
- `-OcrLanguage`: lingua Tesseract, default `ita`.
- `-PageSegmentationMode`: PSM Tesseract, per esempio `4` o `6`.
- `-OcrMaxWorkers`: parallelismo OCR, default `2`.
- `-OcrProgressEvery`: ogni quanti documenti completati loggare progresso.
- `-EnableLlmChunkClassification`: opzionale, fuori dal flusso ordinario.

Esempio con OCR:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_document_processing.ps1 `
  -RootDir "$WorkspaceRoot\documenti_da_processare" `
  -ProcessedDir "$WorkspaceRoot\documenti_processati" `
  -ResultsDir "$WorkspaceRoot\risultati" `
  -ResearchDir "$WorkspaceRoot\ricerche" `
  -RunId "local-ocr-check" `
  -RunOcr `
  -ForceDerived `
  -ForceOcr `
  -PreprocessBeforeOcr `
  -OcrLanguage ita `
  -PageSegmentationMode 4 `
  -OcrProgressEvery 25
```

## 2. Pipeline documentale su documenti gia' processati

Usare quando hai gia' `documenti_processati` e vuoi produrre link
documento-persona, entita', claim candidati, duplicati, cluster, feedback e
summary MVP.

Comando offline:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_document_research_pipeline.ps1 `
  -RunId "pipeline-offline-check" `
  -ProcessedDir "$WorkspaceRoot\documenti_processati" `
  -ResultsDir "$WorkspaceRoot\risultati" `
  -ResearchDir "$WorkspaceRoot\ricerche" `
  -ProfilesIndex "$WorkspaceRoot\ricerche\person_profiles\purocielo.index.jsonld" `
  -SkipOnline
```

Opzioni utili:

- `-ProcessedDir`: cartella dei documenti processati.
- `-ResultsDir`: root dei risultati.
- `-ResearchDir`: root di profili/fonti/luoghi/glossari.
- `-ProfilesIndex`: indice profili JSON-LD, canonico o preview. Passarlo
  sempre in modo esplicito. Per profili operativi usare il data root, ad
  esempio `$WorkspaceRoot\ricerche\person_profiles\purocielo.index.jsonld`;
  per demo/review usare un indice preview sotto `risultati\runs`.
- `-SourcesYaml`: registry fonti alternativo, se serve.
- `-PlacesIndex`: indice luoghi alternativo, se serve. Il default preferisce
  `..\memoria-knowledge\places\places.index.jsonld`.
- `-ProfileId`: limita il summary/pacchetto a un profilo.
- `-SkipOnline`: non esegue ricerche online.
- `-AcquireDocumentsRoot`: se la fase online e' abilitata, acquisisce le
  schede dettaglio con testo come documenti offline processabili.
- `-SimilarityThreshold`: soglia cluster documenti, default `0.86`.

Output principali:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>\document_analysis\mvp_pilot_summary.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>\document_analysis\candidate_document_person_links.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>\document_analysis\candidate_evidence_claims.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>\document_analysis\feedback_search_plan.md
```

## 3. Ricerca online controllata su una fonte

Usare quando vuoi interrogare una fonte censita nel registry partendo da
`PersonResearchProfile` JSON-LD.

Comando singolo profilo/singola fonte:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 `
  -ProfilesIndex "$WorkspaceRoot\ricerche\person_profiles\purocielo.index.jsonld" `
  -SourcesYaml "..\memoria-sources\registry\camalanca_fonti.yaml" `
  -ProfileId "person:purocielo:andreoli-dino" `
  -Source "storia_memoria_bo" `
  -Limit 1 `
  -IncludeSearchPlan `
  -ExecuteFirstPlannedAttempt `
  -OutputJson "$WorkspaceRoot\risultati\verify-online-andreoli.json" `
  -OutputMd "$WorkspaceRoot\risultati\verify-online-andreoli.md" `
  -OutputDir "$WorkspaceRoot\risultati\verify-online-andreoli-schede"
```

Opzioni utili:

- `-ProfilesIndex`: indice profili JSON-LD esplicito. Non usare path relativi
  al repository per profili reali; usare `$WorkspaceRoot\ricerche` oppure un
  indice preview di run.
- `-SourcesYaml`: registry fonti.
- `-ProfileId`: profilo singolo da cercare.
- `-Source`: source id del registry.
- `-Limit`: numero massimo profili, usare `1` per verifiche controllate.
- `-IncludeSearchPlan`: mostra il piano fonte-specifico.
- `-ExecuteFirstPlannedAttempt`: esegue solo il primo tentativo pianificato.
- `-EnsureAuthenticatedSession`: per fonti con sessione manuale persistente,
  apre/riusa il browser Playwright prima della ricerca e aspetta il login
  umano, per esempio SPID/CIE su `partigiani_italia`.
- `-RefreshAuthenticatedCache`: ignora la cache autenticata locale e forza una
  nuova lettura live delle pagine protette.
- `-KeepAuthenticatedBrowserOpenSeconds`: mantiene visibile il browser
  autenticato per N secondi prima della chiusura finale; utile con SPID/CIE.
- `-AcquireDocumentsRoot`: acquisisce le schede dettaglio con testo come
  documenti offline processabili sotto `<root>\<source_id>\<profile_slug>`.
- `-OutputJson`, `-OutputMd`, `-OutputDir`: destinazioni report.
- `-Delay`: pausa tra richieste, se serve prudenza.

Nota importante: una lista risultati non produce fatti storici. Solo schede
dettaglio, documenti identificabili, OCR/testi o documenti strutturati possono
produrre candidati revisionabili.

Per `partigiani_italia`, che puo' richiedere sessione autenticata manuale,
aggiungere `-EnsureAuthenticatedSession`. Il browser resta visibile e il runner
prosegue solo quando rileva la sessione valida. La stessa finestra/sessione
viene poi riusata dal connettore, senza aprire un secondo login; il timeout
configurato per la fonte e' 900 secondi. Se la ricerca anonima restituisce
`blocked_or_dynamic`, il retry autenticato forza comunque il controllo login e
bypassa la cache locale della pagina di ricerca. Dopo la verifica v8 su Balboni
William, il comportamento atteso e': 1 documento testuale acquisito, 2 immagini
scheda correlate, sidecar del testo con `detail_assessment:
claim_candidates_extracted`, `detail_extracted_fields_json`, `claim_eligible:
true` e immagini con `document_type: online_detail_image`.

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$ProfilesIndex = "$WorkspaceRoot\risultati\runs\verify-csv-candidate-profiles\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld"
$AcquireRoot = "$WorkspaceRoot\documenti_da_processare\fonti_online"
$ScoutRoot = "$WorkspaceRoot\risultati\source_scouting"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 `
  -ProfilesIndex $ProfilesIndex `
  -SourcesYaml "..\memoria-sources\registry\camalanca_fonti.yaml" `
  -ProfileId "person:purocielo:balboni-william" `
  -Source "partigiani_italia" `
  -Limit 1 `
  -IncludeSearchPlan `
  -ExecuteFirstPlannedAttempt `
  -EnsureAuthenticatedSession `
  -AcquireDocumentsRoot $AcquireRoot `
  -OutputJson "$ScoutRoot\balboni_partigiani_italia_acquisition_v8.json" `
  -OutputMd "$ScoutRoot\balboni_partigiani_italia_acquisition_v8.md" `
  -OutputDir "$ScoutRoot\balboni_partigiani_italia_schede_v8" `
  -KeepAuthenticatedBrowserOpenSeconds 45
```

Se vuoi evitare che una scheda autenticata vecchia resti in cache, aggiungere
anche `-RefreshAuthenticatedCache`.

### Verifica online -> offline con claim strutturati

Questo e' il percorso da usare quando vuoi verificare che le informazioni
arrivate da una fonte online rientrino nella processazione offline e nei report
MVP. Il caso pilota sotto usa `partigiani_italia`, ma la logica vale per ogni
fonte con `DetailPageLogic` e `claim_mappings`.

1. Acquisire la scheda online come documento processabile:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$ProfilesIndex = "$WorkspaceRoot\risultati\runs\verify-csv-candidate-profiles\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld"
$AcquireRoot = "$WorkspaceRoot\documenti_da_processare\fonti_online"
$ScoutRoot = "$WorkspaceRoot\risultati\source_scouting"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 `
  -ProfilesIndex $ProfilesIndex `
  -SourcesYaml "..\memoria-sources\registry\camalanca_fonti.yaml" `
  -ProfileId "person:purocielo:balboni-william" `
  -Source "partigiani_italia" `
  -Limit 1 `
  -IncludeSearchPlan `
  -ExecuteFirstPlannedAttempt `
  -EnsureAuthenticatedSession `
  -AcquireDocumentsRoot $AcquireRoot `
  -OutputJson "$ScoutRoot\balboni_partigiani_italia_structured_claims_v1.json" `
  -OutputMd "$ScoutRoot\balboni_partigiani_italia_structured_claims_v1.md" `
  -OutputDir "$ScoutRoot\balboni_partigiani_italia_structured_claims_v1_schede" `
  -KeepAuthenticatedBrowserOpenSeconds 45
```

2. Verificare che il sidecar contenga i campi strutturati:

```powershell
$Sidecars = Get-ChildItem -Path "$AcquireRoot\partigiani_italia\balboni-william" -Filter "*.document.yaml" -Recurse
$Sidecars | Select-Object -ExpandProperty FullName
Select-String -Path $Sidecars.FullName -Pattern "detail_assessment|detail_extracted_fields_json|claim_eligible|online_detail_image"
```

Il sidecar testuale deve mostrare `detail_assessment:
claim_candidates_extracted`, `detail_extracted_fields_json` e
`claim_eligible: true`. Le immagini correlate devono restare documenti
processabili ma non claim-eligible.

3. Lanciare la run offline ristretta, senza riprocessare tutto il workspace:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "verify-offline-balboni-structured-claims-v1"
$ProfilesIndex = "$WorkspaceRoot\risultati\runs\verify-csv-candidate-profiles\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld"
$InputRootDir = "$WorkspaceRoot\documenti_da_processare\fonti_online\partigiani_italia\balboni-william"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -InputRootDir $InputRootDir `
  -SkipOnline `
  -ForceDerived `
  -ProfilesIndex $ProfilesIndex `
  -ProfileId "person:purocielo:balboni-william" `
  -VaultLimit 10
```

4. Aprire i report da controllare:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\verify-offline-balboni-structured-claims-v1-pipeline\document_analysis\candidate_evidence_claims.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\verify-offline-balboni-structured-claims-v1-pipeline\document_analysis\candidate_document_person_links.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\verify-offline-balboni-structured-claims-v1-pipeline\document_analysis\mvp_pilot_summary.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\verify-offline-balboni-structured-claims-v1-pipeline\mvp_pilot_cards_digest.md
```

Nel report claim cercare `online_detail_structured_fields`: e' il segnale che i
campi strutturati online sono stati trasformati in claim candidati offline. I
claim restano `unreviewed` e non modificano i profili JSON-LD.

Comando con acquisizione documentale della scheda dettaglio:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$ProfilesIndex = "$WorkspaceRoot\risultati\runs\verify-csv-candidate-profiles\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_profiles_meta_search.ps1 `
  -ProfilesIndex $ProfilesIndex `
  -SourcesYaml "..\memoria-sources\registry\camalanca_fonti.yaml" `
  -ProfileId "person:purocielo:bendini-ateo" `
  -Source "storia_memoria_bo" `
  -Limit 1 `
  -IncludeSearchPlan `
  -ExecuteFirstPlannedAttempt `
  -AcquireDocumentsRoot "$WorkspaceRoot\documenti_da_processare\fonti_online" `
  -OutputJson "$WorkspaceRoot\risultati\source_scouting\bendini_storia_memoria_bo_acquisition.json" `
  -OutputMd "$WorkspaceRoot\risultati\source_scouting\bendini_storia_memoria_bo_acquisition.md" `
  -OutputDir "$WorkspaceRoot\risultati\source_scouting\bendini_storia_memoria_bo_schede"
```

Le pagine acquisite entrano poi nella processazione locale:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_local_document_processing.ps1 `
  -RootDir "$WorkspaceRoot\documenti_da_processare\fonti_online\storia_memoria_bo\bendini-ateo" `
  -ProcessedDir "$WorkspaceRoot\documenti_processati" `
  -ResultsDir "$WorkspaceRoot\risultati" `
  -ResearchDir "$WorkspaceRoot\ricerche" `
  -RunId "verify-online-acquisition-local-bendini" `
  -ForceDerived
```

Per processare la scheda `partigiani_italia` acquisita nella verifica v8:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId "verify-online-acquired-balboni-partigiani-local" `
  -InputRootDir "$WorkspaceRoot\documenti_da_processare\fonti_online\partigiani_italia\balboni-william" `
  -SkipOnline `
  -ForceDerived `
  -ProfileId "person:purocielo:balboni-william" `
  -VaultLimit 10
```

Oppure, se vuoi rigenerare direttamente il pacchetto MVP sul solo sottoinsieme
acquisito, usare `-InputRootDir`:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId "verify-online-acquisition-mvp-bendini" `
  -InputRootDir "$WorkspaceRoot\documenti_da_processare\fonti_online\storia_memoria_bo\bendini-ateo" `
  -SkipOnline `
  -ForceDerived `
  -ProfileId "person:purocielo:bendini-ateo" `
  -VaultLimit 10
```

## 4. Workspace MVP completo

Usare quando vuoi il pacchetto MVP end-to-end: locale, pipeline documentale,
review queue, Obsidian, readiness, dossier finanziamento e, se richiesto,
source coverage online.

Comando offline sui profili canonici:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "mvp-offline-check"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -SkipOnline `
  -ForceDerived `
  -VaultLimit 10
```

Comando offline con 3 profili scelti da un indice preview:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "mvp-3-profili-preview"
$PreviewIndex = "P:\Comune\Me.Mo.Ri.a\risultati\runs\<run-id-local>\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -SkipOnline `
  -ForceDerived `
  -ProfilesIndex $PreviewIndex `
  -VaultLimit 10
```

Comando per generare anche l'indice preview dai candidati accettati:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "mvp-3-profili-da-candidati"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -SkipOnline `
  -ForceDerived `
  -BuildCandidateProfileReview `
  -AcceptedCandidateProfileId "candidate-person-profile:<id1>","candidate-person-profile:<id2>","candidate-person-profile:<id3>" `
  -CandidateProfileLimit 20 `
  -VaultLimit 10
```

Opzioni MVP utili:

- `-WorkspaceRoot`: root condivisa predefinita `P:\Comune\Me.Mo.Ri.a`.
- `-RunId`: nome della run; produce `<RunId>-local`, `<RunId>-pipeline` e `<RunId>-vault`.
- `-InputRootDir`: sottoinsieme raw da usare nella fase locale MVP. Se omesso
  usa `$WorkspaceRoot\documenti_da_processare`. Se valorizzato, il wrapper usa
  anche una cartella processed isolata
  `risultati\runs\<RunId>-local\processed_documents`, cosi' la pipeline
  successiva non scandisce tutto `$WorkspaceRoot\documenti_processati`.
  Questa cartella non sostituisce il processed store condiviso: e' un derivato
  tecnico della run. La radice canonica resta
  `$WorkspaceRoot\documenti_processati`; usare
  `risultati\runs\<RunId>-local\processed_documents` solo insieme alla run che
  lo ha generato e considerarlo rigenerabile/cancellabile con quella run.
- `-SkipOnline`: disabilita online.
- `-RunOcr`: abilita OCR durante la fase locale.
- `-ForceDerived`: rigenera derivati.
- `-ProfilesIndex`: usa un indice profili alternativo, per esempio preview.
- `-ProfileId`: restringe summary/vault a uno o piu' profili. Per array usare
  una sola occorrenza: `"id1","id2"`.
- `-ReviewDecisionsJson`: usa decisioni storico compilate invece del template.
- `-AcquireOnlineDocuments`: nella run online MVP acquisisce le schede
  dettaglio sotto `documenti_da_processare\fonti_online`.
- `-AcquireDocumentsRoot`: override esplicito della cartella di acquisizione.
- `-VaultLimit`: numero massimo schede esportate nel vault.
- `-BuildCandidateProfileReview`: genera review profili candidati dalla run locale.
- `-AcceptedCandidateProfileId`: accetta inline candidati per creare profili preview.
- `-CandidateProfileLimit`: quanti candidati considerare per review.
- `-ReportsOnly`: salta processazione locale e pipeline documentale; rigenera
  solo report e pacchetto finale da run esistenti.
- `-ReuseLocalRunId`: run locale esistente da riusare sotto `risultati\runs`.
  Se omesso usa `<RunId>-local`.
- `-ReusePipelineRunId`: run pipeline esistente da riusare sotto
  `risultati\runs`. In `-ReportsOnly` e' la sorgente documentale; i report
  rigenerati vengono scritti nella nuova cartella `<RunId>-pipeline`.

Comando reports-only da run gia' completata:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "mvp-reports-refresh"
$PreviewIndex = "$WorkspaceRoot\risultati\runs\<run-id-con-preview-approvata>\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -ReportsOnly `
  -SkipOnline `
  -ReuseLocalRunId "verify-mvp-run-index-digest-3-profili-local" `
  -ReusePipelineRunId "verify-mvp-run-index-digest-3-profili-pipeline" `
  -ProfilesIndex $PreviewIndex `
  -VaultLimit 10
```

Comando reale per rigenerare i report nel formato corrente dalla run lunga dei
tre profili `verify-mvp-run-index-digest-3-profili`:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "verify-mvp-3-profili-report-refresh"
$PreviewIndex = "$WorkspaceRoot\risultati\runs\verify-csv-candidate-profiles\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -ReportsOnly `
  -SkipOnline `
  -ReuseLocalRunId "verify-mvp-run-index-digest-3-profili-local" `
  -ReusePipelineRunId "verify-mvp-run-index-digest-3-profili-pipeline" `
  -ProfilesIndex $PreviewIndex `
  -VaultLimit 10
```

Output da aprire dopo questa rigenerazione:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\verify-mvp-3-profili-report-refresh-pipeline\mvp_run_index.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\verify-mvp-3-profili-report-refresh-pipeline\mvp_pilot_cards_digest.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\verify-mvp-3-profili-report-refresh-pipeline\historian_review\review_session.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\verify-mvp-3-profili-report-refresh-pipeline\mvp_package_readiness.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\verify-mvp-3-profili-report-refresh-pipeline\mvp_funding_dossier.md
```

Questa modalita' e' pensata per iterare su summary, ledger, review
queue/sessione, dashboard, target storici, vault, digest schede, readiness,
dossier e indice run senza rilanciare OCR, processazione locale, linking o
pipeline documentale completa. Il dossier funding riceve automaticamente il
`mvp_consolidated_review_ledger.json` generato nella nuova run e puo' mostrare
il `Raccordo step 2 storico` con decisioni, ledger e copertura evidence store.
Se una delle run riusate non esiste, il wrapper si ferma subito invece di creare
una nuova run incompleta. `-ReusePipelineRunId` indica la pipeline sorgente da
leggere; la destinazione dei report aggiornati resta sempre
`risultati\runs\<RunId>-pipeline`.

Output principali MVP:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\mvp_run_index.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\mvp_consolidated_review_ledger.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\mvp_pilot_cards_digest.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-local\run_summary.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\document_analysis\mvp_pilot_summary.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\historical_review_targets.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_queue.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_session.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_focus_decisions_cards.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\verified_facts.preview.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\mvp_package_readiness.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\mvp_funding_dossier.md
P:\Comune\Me.Mo.Ri.a\risultati\<RunId>-vault\10_Output\MVP_Pilot_Review.md
P:\Comune\Me.Mo.Ri.a\risultati\<RunId>-vault\10_Output\mvp_curatorial_brief.md
```

`verified_facts.preview.md/json` viene generato automaticamente dal wrapper
dopo l'import append-only nello evidence store. Legge solo decisioni storiche
approvate importate come `historical_review_decision`, resta `preview-only` e
non modifica profili JSON-LD o dati canonici. Se la run usa
`-SkipEvidenceImport`, il wrapper scrive un artefatto `skipped` per evitare di
leggere record stale dal DB.
Le `review_decision` generiche non alimentano la preview, anche se riportano
`confirm`: servono record storici sostanziali importati come
`historical_review_decision`.
La sintesi di questa preview viene riportata anche in
`historian_review/review_dashboard.md` e in `mvp_funding_dossier.md`, cosi'
storici, curatori e finanziatori vedono conteggi/stato senza aprire il JSON
tecnico.
Quando si rigenerano manualmente le schede modello MVP, passare la stessa
preview con `-VerifiedFactsPreviewJson`: la scheda mostra una sezione
`Fatti preview` filtrata per `profile_id`, sempre preview-only e senza
modificare profili o DB.

```powershell
.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_mvp_model_cards.ps1 `
  -DigestJson "$WorkspaceRoot\risultati\runs\<RunId>-pipeline\mvp_pilot_cards_digest.json" `
  -SummaryJson "$WorkspaceRoot\risultati\runs\<RunId>-pipeline\document_analysis\mvp_pilot_summary.json" `
  -ReviewSessionJson "$WorkspaceRoot\risultati\runs\<RunId>-pipeline\historian_review\review_session.json" `
  -VerifiedFactsPreviewJson "$WorkspaceRoot\risultati\runs\<RunId>-pipeline\historian_review\verified_facts.preview.json" `
  -OutputDir "$WorkspaceRoot\risultati\runs\<RunId>-pipeline\schede_modello" `
  -FundingExcerptsDir "$WorkspaceRoot\risultati\runs\<RunId>-pipeline\funding_excerpts"
```

Per leggere lo stato evidence store di un profilo pilota senza mescolare run
vecchie e correnti, usare il filtro run:

```powershell
.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_evidence_store_profile_status.ps1 `
  -DatabasePath "$WorkspaceRoot\database\evidence.sqlite" `
  -ProfileId "person:purocielo:andreoli-dino" `
  -EvidenceSourceRunId "<RunId>-pipeline" `
  -OutputJson "$WorkspaceRoot\risultati\runs\<RunId>-pipeline\historian_review\andreoli.evidence_store_profile_status.json" `
  -OutputMd "$WorkspaceRoot\risultati\runs\<RunId>-pipeline\historian_review\andreoli.evidence_store_profile_status.md"
```

Se il filtro produce `Record profilo: 0`, l'output Markdown aggiunge
`Diagnostica risultato vuoto` con eventuali run alternative che contengono il
profilo o profili presenti nella run richiesta. La diagnostica e' read-only e
serve solo a scegliere il prossimo comando operativo.

### Sessione storica senza JSON manuale

Le schede in
`P:\Comune\Me.Mo.Ri.a\risultati\<RunId>-vault\40_Publication_Candidates`
sono solo materiale di lettura: mostrano documenti, claim candidati e piste per
profilo. Non vanno usate come file decisionale.

Per la routine guidata piu' breve, partire dalla Me.Mo.Ria CLI:

```powershell
.\scripts\memoria.ps1 review start --auto -WorkspaceRoot "P:\Comune\Me.Mo.Ri.a"
.\scripts\memoria.ps1 review work -WorkspaceRoot "P:\Comune\Me.Mo.Ri.a"
.\scripts\memoria.ps1 review accept 1 -WorkspaceRoot "P:\Comune\Me.Mo.Ri.a"
.\scripts\memoria.ps1 review reject 1 -WorkspaceRoot "P:\Comune\Me.Mo.Ri.a"
.\scripts\memoria.ps1 review uncertain 1 -WorkspaceRoot "P:\Comune\Me.Mo.Ri.a"
.\scripts\memoria.ps1 review refresh -WorkspaceRoot "P:\Comune\Me.Mo.Ri.a"
```

I comandi `review accept/reject/uncertain <numero>` usano la worklist numerata
della sessione attiva, scrivono `review_decisions.compilato.json` e rigenerano
`review_decisions_summary.json/md`. `reject` e `uncertain` scrivono solo azioni
ammesse dall'item. Restano preview-only: non creano `verified_facts`, non
modificano profili JSON-LD e non pubblicano schede.

Per una sessione con storico/curatore, generare o aprire il dossier cards:

```powershell
.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_mvp_review_focus_decisions_table.ps1 `
  -Mode BuildCards `
  -ReviewSessionJson "P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_session.json" `
  -OutputMd "P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_focus_decisions_cards.md" `
  -Limit 15
```

Compilare nel Markdown solo `selected_action`, `reviewer`, `reviewed_at` e
`note`. `reviewer` e `reviewed_at` possono restare vuoti durante una prova
tecnica, ma per una sessione storica firmata vanno compilati. Poi convertire:

```powershell
.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_mvp_review_focus_decisions_table.ps1 `
  -Mode ConvertTable `
  -ReviewTableMd "P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_focus_decisions_cards.md" `
  -OutputDecisionsJson "P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_decisions.compilato.json" `
  -OutputSummaryJson "P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_focus_decisions_cards_summary.json" `
  -OutputSummaryMd "P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_focus_decisions_cards_summary.md"
```

`ConvertTable` accetta sia la tabella larga
`review_focus_decisions_table.md` sia il dossier a schede
`review_focus_decisions_cards.md`. Quando si convertono le cards, passare anche
`-OutputSummaryJson` e `-OutputSummaryMd` per scrivere il riepilogo accanto alla
run reale ed evitare il path di default.

Il JSON compilato e' un derivato tecnico generato e va poi passato al wrapper
con `-ReviewDecisionsJson` o validato con `summarize_mvp_review_decisions.ps1`.

Quando serve revisionare un claim specifico che non e' entrato nel focus della
`review_session`, non costruire JSON a mano. Generare invece una card Markdown
direttamente dalla `review_queue.json`:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "mvp-step2-historical-targets-preview8-20260620"
$PipelineRunId = "$RunId-pipeline"
$RunDir = "$WorkspaceRoot\risultati\runs\$PipelineRunId"
$ReviewDir = "$RunDir\historian_review"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_mvp_review_focus_decisions_table.ps1 `
  -Mode BuildQueueCards `
  -ReviewQueueJson "$ReviewDir\review_queue.json" `
  -ItemId "mvp-review-item:0041" `
  -OutputMd "$ReviewDir\review_claim_0041.cards.md"
```

Lo storico compila solo la tabella finale nel Markdown. Il tecnico poi usa la
stessa modalita' `ConvertTable` descritta sopra per produrre il JSON derivato e
validarlo con `summarize_mvp_review_decisions.ps1`. Questo mantiene il
contratto della roadmap: gli storici lavorano su Markdown leggibile; JSON,
summary, import store e `verified_facts.preview` restano passaggi tecnici.

Esempio reale step 2 con 3 profili e output storico sostanziale:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "mvp-step2-historical-targets-preview8-20260620"
$PreviewIndex = "$WorkspaceRoot\risultati\runs\mvp-expand-pilot-preview-profiles-v1-local\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -ReportsOnly `
  -SkipOnline `
  -SkipEvidenceImport `
  -ReuseLocalRunId "mvp-expand-pilot-preview-profiles-v1-local" `
  -ReusePipelineRunId "mvp-expand-pilot-preview-profiles-v1-pipeline" `
  -ProfilesIndex $PreviewIndex `
  -ProfileId "person:purocielo:andreoli-dino","person:purocielo:balboni-william","person:purocielo:bendini-ateo" `
  -OutputProfile Full
```

Output da aprire:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\mvp-step2-historical-targets-preview8-20260620-pipeline\historian_review\historical_review_targets.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\mvp-step2-historical-targets-preview8-20260620-pipeline\historian_review\review_decisions.storico-1.summary.md
```

La run ha prodotto 10 target storici revisionabili e una prima review parziale
con 5 decisioni accettate, 78 pending e 0 errori di validazione. Resta
`not_publishable_without_human_review`.

Dopo una run MVP aprire per primo
`P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\mvp_run_index.md`: e'
l'indice operativo che mostra artefatti presenti/mancanti e il prossimo report
da leggere.

Per scegliere rapidamente quali schede pilota mostrare a revisori o
finanziatori, aprire poi
`P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\mvp_pilot_cards_digest.md`.

Per costruire un ledger MVP cumulativo da piu' run pipeline gia' completate:

```powershell
.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_mvp_consolidated_review_ledger.ps1 `
  -RunDir "P:\Comune\Me.Mo.Ri.a\risultati\runs\<run-a>-pipeline","P:\Comune\Me.Mo.Ri.a\risultati\runs\<run-b>-pipeline" `
  -OutputJson "P:\Comune\Me.Mo.Ri.a\risultati\runs\mvp-ledger-refresh\mvp_consolidated_review_ledger.json" `
  -OutputMd "P:\Comune\Me.Mo.Ri.a\risultati\runs\mvp-ledger-refresh\mvp_consolidated_review_ledger.md"
```

Quando le decisioni storiche sono gia' state importate in
`evidence.sqlite`, si puo' rigenerare una vista store-first senza riaprire i
summary di run come fonte primaria:

```powershell
$RunDir = "P:\Comune\Me.Mo.Ri.a\risultati\runs\mvp-step2-historical-targets-preview8-20260620-pipeline"
$DbPath = "P:\Comune\Me.Mo.Ri.a\database\evidence.sqlite"
$SourceRunId = "mvp-step2-historical-targets-preview8-20260620-pipeline"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_mvp_consolidated_review_ledger.ps1 `
  -EvidenceDatabasePath $DbPath `
  -EvidenceSourceRunId $SourceRunId `
  -OutputJson "$RunDir\mvp_consolidated_review_ledger.store_first.d2.json" `
  -OutputMd "$RunDir\mvp_consolidated_review_ledger.store_first.d2.md"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_mvp_historical_review_targets.ps1 `
  -EvidenceDatabasePath $DbPath `
  -EvidenceSourceRunId $SourceRunId `
  -OutputJson "$RunDir\historian_review\historical_review_targets.store_first.json" `
  -OutputMd "$RunDir\historian_review\historical_review_targets.store_first.md"
```

Questi output leggono record, item e `historical_review_decision` dallo store,
conservano `record_id`, `source_document_id`, `profile_id` e azioni ammesse, ma
restano derivati preview-only: non scrivono nel database, non modificano profili
e non creano fatti verificati.

Per organizzare la sessione storici/curatori, aprire anche
`P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\historian_review\review_session.md`.

## 5. MVP con fonte online e source coverage

La parte online nel wrapper MVP va usata con un solo profilo, una fonte e
`-Limit 1`.

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "mvp-online-storia-memoria-andreoli"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -ForceDerived `
  -ProfileId "person:purocielo:andreoli-dino" `
  -Source "storia_memoria_bo" `
  -Limit 1 `
  -IncludeSearchPlan `
  -ExecuteFirstPlannedAttempt `
  -AcquireOnlineDocuments `
  -VaultLimit 10
```

Con `-AcquireOnlineDocuments`, le eventuali schede dettaglio con testo vengono
salvate sotto
`$WorkspaceRoot\documenti_da_processare\fonti_online\<source_id>\<profile_slug>`.
Per farle entrare nei link/claim candidati serve poi una run locale su quel
sottoinsieme. Usare `-InputRootDir` nel wrapper MVP: la run processa quel raw e
crea un processed store isolato della run, evitando di ripassare l'intero
workspace.

Nota sulla cartella processed: `documenti_processati` resta la radice condivisa
e canonica del workspace. La cartella
`risultati\runs\<RunId>-local\processed_documents` nasce solo quando
`-InputRootDir` restringe l'input, ed e' un derivato tecnico da usare insieme a
quella run, non una seconda area permanente di documenti processati.

Comando successivo sul sottoinsieme acquisito:

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "mvp-online-acquired-andreoli-local"

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -InputRootDir "$WorkspaceRoot\documenti_da_processare\fonti_online\storia_memoria_bo\andreoli-dino" `
  -SkipOnline `
  -ForceDerived `
  -ProfileId "person:purocielo:andreoli-dino" `
  -VaultLimit 10
```

Output online aggiuntivi:

```text
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\online\profiles_meta_search.json
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\source_coverage_summary.md
P:\Comune\Me.Mo.Ri.a\risultati\runs\<RunId>-pipeline\source_coverage_summary.json
```

## 6. Comandi di lettura rapida dei report

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "mvp-3-profili-preview"
$PipelineRun = "$WorkspaceRoot\risultati\runs\$RunId-pipeline"
$VaultRun = "$WorkspaceRoot\risultati\$RunId-vault"

Get-Content -Path "$PipelineRun\mvp_run_index.md" -TotalCount 220
Get-Content -Path "$PipelineRun\mvp_consolidated_review_ledger.md" -TotalCount 220
Get-Content -Path "$PipelineRun\mvp_pilot_cards_digest.md" -TotalCount 220
Get-Content -Path "$PipelineRun\historian_review\review_session.md" -TotalCount 220
Get-Content -Path "$PipelineRun\document_analysis\mvp_pilot_summary.md" -TotalCount 220
Get-Content -Path "$PipelineRun\mvp_package_readiness.md" -TotalCount 220
Get-Content -Path "$PipelineRun\mvp_funding_dossier.md" -TotalCount 260
Get-Content -Path "$PipelineRun\historian_review\review_queue.md" -TotalCount 220
Get-Content -Path "$VaultRun\10_Output\MVP_Pilot_Review.md" -TotalCount 260
```

## 7. Errori comuni

- `Cannot find path ... <run_id-local-precedente>`: hai lasciato un placeholder
  nel comando. Sostituirlo con una run reale.
- `online requires ProfileId, Source e Limit > 0`: la parte online richiede
  sempre profilo singolo, fonte singola e limite maggiore di zero.
- `-ProfileId` ripetuto piu' volte: usare un solo parametro con array
  `"id1","id2","id3"`.
- `-ForceOcr` senza `-RunOcr`: non avvia OCR. Serve solo a forzare OCR quando
  `-RunOcr` e' presente.
- `P:\Comune\Me.Mo.Ri.a` passato come `RootDir`: sbagliato. Usare
  `P:\Comune\Me.Mo.Ri.a\documenti_da_processare`.
- `-AcquireOnlineDocuments` lanciato nella run online e poi nessun nuovo segnale
  nel report: le schede acquisite vanno processate in una seconda run con
  `-InputRootDir` puntato al sottoinsieme creato.


