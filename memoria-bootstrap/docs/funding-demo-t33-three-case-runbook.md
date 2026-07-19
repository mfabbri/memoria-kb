# T33 Three-Case Canonical Golden Run Runbook

Data: 2026-07-18

Stato: fase 1 completata il 2026-07-18; candidata creata senza evidence import.
Gate 1 aperto per produrre e approvare le richieste agli storici.

## Obiettivo

Preparare una **candidata alla nuova golden run canonica** con tre casi
approfonditi:

1. `person:purocielo:andreoli-dino`;
2. `person:purocielo:balboni-william`;
3. `person:purocielo:bendini-ateo`.

Andreoli conserva la catena completa e il feedback loop. Balboni mostra
corroborazione e confronto multi-fonte. Bendini mostra review esplicita di un
caso ancora incompleto senza presentare come acquisito o analizzato il materiale
`storia_memoria_bo` non ancora entrato nel ledger.

Questa procedura non crea una run per la presentazione e una run tecnica. Crea
una sola candidata; presentazione, dossier, riconciliazione, review, verified
facts preview, ProfilePatch preview e feedback loop devono puntare alla stessa
run prima della promozione canonica.

## Transizione canonica

Durante la preparazione:

- `prova-preview-profili-5-reviewed-01-pipeline` resta l'unica golden run attiva;
- la candidata non puo' essere usata in presentazioni esterne;
- `memoria_mvp_demo.active.json` non viene modificato;
- gli storici ricevono soltanto le richieste prodotte dalla candidata.

La candidata sostituisce la golden run attiva solo dopo tutti i gate. Non
possono esistere due descriptor attivi o due percorsi di presentazione.

## Perimetro autorizzato

- Una sola run candidata derivata dal corpus pilota gia' processato.
- Tre profili selezionati e cinque documenti sorgente complessivi.
- Nessun OCR, scansione massiva o acquisizione online.
- Nessuna modifica ai profili JSON-LD canonici.
- Nessuna applicazione di `ProfilePatch`.
- Evidence import append-only soltanto dopo decisioni umane validate.
- Feedback loop T31 rigenerato nella candidata prima della promozione.
- Descriptor attivo aggiornato soltanto nel gate finale autorizzato.

## Preparazione

Eseguire da `memoria-engine` in PowerShell. I blocchi non devono essere eseguiti
tutti insieme.

```powershell
$WorkspaceRoot = "P:\Comune\Me.Mo.Ri.a"
$RunId = "funding-demo-golden-3cases-v1"
$PipelineRunId = "${RunId}-pipeline"
$SourceLocalRunId = "mvp-expand-pilot-preview-profiles-v1-local"
$SourcePipelineRunId = "mvp-expand-pilot-preview-profiles-v1-pipeline"
$ProfilesIndex = "$WorkspaceRoot\risultati\runs\$SourceLocalRunId\document_analysis\candidate_profile_review\preview_person_profiles\purocielo.index.jsonld"
$RunDir = "$WorkspaceRoot\risultati\runs\$PipelineRunId"
$ActiveDescriptor = "$WorkspaceRoot\database\memoria_mvp_demo.active.json"
$CandidateDescriptor = "$RunDir\memoria_mvp_demo.candidate.json"
$CandidateReconciliation = "$RunDir\mvp_demo_reconciliation_table.md"
$Profiles = @(
  "person:purocielo:andreoli-dino",
  "person:purocielo:balboni-william",
  "person:purocielo:bendini-ateo"
)
$SourceDocuments = @(
  "legacy_csv:a4ac96061a2381b5",
  "local_docx:4c2ad1d2ab937913",
  "partigiani_italia:b45553cd6b1673d8",
  "partigiani_italia:b6b3c9e526723a27",
  "partigiani_italia:dadc75fad9db03ae"
)
$SourceSummary = "$WorkspaceRoot\risultati\runs\$SourcePipelineRunId\document_analysis\mvp_pilot_summary.json"
$SourceFeedbackActions = "$WorkspaceRoot\risultati\runs\$SourcePipelineRunId\document_analysis\research_feedback_actions.json"
```

Preflight read-only:

```powershell
Test-Path -LiteralPath "$WorkspaceRoot\risultati\runs\$SourceLocalRunId"
Test-Path -LiteralPath "$WorkspaceRoot\risultati\runs\$SourcePipelineRunId"
Test-Path -LiteralPath $ProfilesIndex
Test-Path -LiteralPath $ActiveDescriptor
Test-Path -LiteralPath $SourceSummary
Test-Path -LiteralPath $SourceFeedbackActions
$CandidateFiles = if (Test-Path -LiteralPath $RunDir) {
  @(Get-ChildItem -LiteralPath $RunDir -Recurse -File)
} else {
  @()
}
$CandidateFiles.Count
.\.venv\Scripts\memoria.exe mvp demo --data-root $WorkspaceRoot

$Summary = Get-Content -LiteralPath $SourceSummary -Raw | ConvertFrom-Json
if (-not (@($Summary.research_feedback_actions).action_id -contains "research-feedback-action:7bdbb2060d955baa")) {
  throw "Azione T31 Andreoli assente dal summary sorgente."
}
if (-not (@($Summary.feedback_search_plans).feedback_search_plan_id -contains "feedback-search-plan:a19b13e6e3cd8b0d")) {
  throw "Piano T31 Andreoli assente dal summary sorgente."
}
```

Stop condition:

- i sei `Test-Path` restituiscono `True`;
- `$CandidateFiles.Count` e' `0`; questo ammette sia una candidata mai avviata
  sia la directory vuota lasciata dal tentativo fermato del 2026-07-18;
- `memoria mvp demo` conferma come run attiva
  `prova-preview-profili-5-reviewed-01-pipeline`;
- il descriptor attivo e' valido e `preview_only=true`.

## Fase 1 - Candidata senza evidence import

Questa fase crea solo derivati sotto `risultati/runs` e il relativo vault. Non
modifica `evidence.sqlite` e non cambia la golden run attiva.

```powershell
.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -ReportsOnly `
  -SkipOnline `
  -SkipEvidenceImport `
  -ReuseLocalRunId $SourceLocalRunId `
  -ReusePipelineRunId $SourcePipelineRunId `
  -ProfilesIndex $ProfilesIndex `
  -ProfileId ($Profiles -join ",") `
  -VaultLimit 3 `
  -OutputProfile Demo
```

Creare le viste per gli storici:

```powershell
.\scripts\build_mvp_review_focus_decisions_table.ps1 `
  -Mode BuildCards `
  -ReviewSessionJson "$RunDir\historian_review\review_session.json" `
  -OutputMd "$RunDir\historian_review\review_requests.three_cases.cards.md" `
  -ProfileId $Profiles

Copy-Item `
  -LiteralPath "$RunDir\historian_review\review_focus_decisions_table.md" `
  -Destination "$RunDir\historian_review\review_focus_decisions_table.compilato.md"
```

Materiali da approvare e consegnare:

```text
<RunDir>\historian_review\review_requests.three_cases.cards.md
<RunDir>\historian_review\review_focus_decisions_table.compilato.md
```

Gli storici compilano solo `selected_action`, `reviewer`, `reviewed_at` e
`note`. Non precompilare `confirm`: incertezza, rifiuto o richiesta di altre
fonti sono esiti validi.

## Gate 1 - Approvazione richieste

Fermarsi. Non eseguire la fase 2 finche':

- il committente non ha approvato le richieste;
- gli storici non hanno restituito la tabella;
- ogni decisione compilata contiene revisore e data;
- nessun output e' descritto come fatto storico pubblicabile.

## Conversione e validazione

```powershell
$CompiledTable = "$RunDir\historian_review\review_focus_decisions_table.compilato.md"
$DecisionsJson = "$RunDir\historian_review\review_decisions.compilato.json"

.\scripts\build_mvp_review_focus_decisions_table.ps1 `
  -Mode ConvertTable `
  -ReviewTableMd $CompiledTable `
  -OutputDecisionsJson $DecisionsJson `
  -OutputSummaryJson "$RunDir\historian_review\review_focus_conversion_summary.json" `
  -OutputSummaryMd "$RunDir\historian_review\review_focus_conversion_summary.md"

.\scripts\summarize_mvp_review_decisions.ps1 `
  -ReviewQueueJson "$RunDir\historian_review\review_queue.json" `
  -DecisionsJson $DecisionsJson `
  -OutputJson "$RunDir\historian_review\review_decisions.validation.json" `
  -OutputMd "$RunDir\historian_review\review_decisions.validation.md"

Get-Content "$RunDir\historian_review\review_decisions.validation.md"
```

Stop condition: zero decisioni invalide, zero errori e almeno una decisione
sostanziale valida per ciascuno dei tre profili. Incertezza e richiesta di altre
fonti sono decisioni valide; gli item non decisi restano `pending`.

## Fase 2 - Rigenerazione della stessa candidata

Questa fase importa nella stessa lineage candidata record append-only e produce
verified facts e ProfilePatch esclusivamente preview.

```powershell
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$EvidenceDb = "$WorkspaceRoot\database\evidence.sqlite"
$EvidenceDbBackup = "$WorkspaceRoot\database\evidence.before-${RunId}-${Stamp}.sqlite"
if (Test-Path -LiteralPath "${EvidenceDb}-wal") {
  throw "Backup sospeso: evidence.sqlite-wal presente. Chiudere le sessioni SQLite e verificare il checkpoint."
}
Copy-Item -LiteralPath $EvidenceDb -Destination $EvidenceDbBackup

.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_mvp_workspace_pipeline.ps1 `
  -WorkspaceRoot $WorkspaceRoot `
  -RunId $RunId `
  -ReportsOnly `
  -SkipOnline `
  -ReuseLocalRunId $SourceLocalRunId `
  -ReusePipelineRunId $SourcePipelineRunId `
  -ProfilesIndex $ProfilesIndex `
  -ProfileId ($Profiles -join ",") `
  -ReviewDecisionsJson $DecisionsJson `
  -VaultLimit 3 `
  -OutputProfile Demo
```

## Fase 3 - Descriptor candidato e feedback loop

Costruire il descriptor in un file candidato, mai direttamente nel path
attivo:

```powershell
$DemoBuildArgs = @(
  "mvp", "demo-build",
  "--data-root", $WorkspaceRoot,
  "--run-id", $PipelineRunId,
  "--primary-profile-id", "person:purocielo:andreoli-dino",
  "--contrast-profile-id", "person:purocielo:balboni-william",
  "--contrast-profile-id", "person:purocielo:bendini-ateo",
  "--output-descriptor", $CandidateDescriptor,
  "--output-reconciliation", $CandidateReconciliation
)
foreach ($Document in $SourceDocuments) {
  $DemoBuildArgs += @("--source-document-id", $Document)
}
& .\.venv\Scripts\memoria.exe @DemoBuildArgs
if ($LASTEXITCODE -ne 0) { throw "Descriptor candidato non creato." }
```

Rigenerare il feedback loop T31 dentro la candidata e aggiornare soltanto il
descriptor candidato:

```powershell
.\.venv\Scripts\python.exe .\tools\register_t31_demo_feedback_loop.py `
  --data-root $WorkspaceRoot `
  --run-id $PipelineRunId `
  --descriptor-path $CandidateDescriptor `
  --backup-path "$RunDir\memoria_mvp_demo.candidate.before-t31-feedback-loop.json"

.\.venv\Scripts\memoria.exe mvp demo `
  --data-root $WorkspaceRoot `
  --descriptor $CandidateDescriptor
```

Stop condition:

- `ready_for_internal_demo`;
- un profilo principale e due profili complementari;
- cinque documenti selezionati e almeno due famiglie fonte;
- decisione sostanziale per ogni profilo;
- verified facts e ProfilePatch solo preview;
- `t31_feedback_loop.status=closed_with_auditable_outcome`;
- tutti i path del descriptor candidato puntano a `$PipelineRunId`;
- `publication_ready=false` e nessun profilo canonico modificato.

## Fase 4 - Pacchetto unico e gate finale

```powershell
.\scripts\build_mvp_funding_package.ps1 `
  -RunDir $RunDir `
  -DemoDescriptorJson $CandidateDescriptor `
  -QualityGateStatus passed

Get-Content "$RunDir\mvp_pilot_cards_digest.md"
Get-Content "$RunDir\historian_review\review_decisions_summary.md"
Get-Content "$RunDir\historian_review\verified_facts.preview.md"
Get-Content "$RunDir\historian_review\profile_patch.preview.md"
Get-Content "$RunDir\historian_review\feedback_loop_outcome.t31-demo.md"
Get-Content "$RunDir\mvp_package_readiness.md"
Get-Content "$RunDir\funding_package_index.md"
```

Fermarsi per approvazione umana. La candidata non e' ancora canonica e non va
presentata all'esterno.

## Fase 5 - Promozione canonica autorizzata

Eseguire soltanto dopo approvazione esplicita del gate finale:

```powershell
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ActiveDescriptorBackup = "$WorkspaceRoot\database\memoria_mvp_demo.active.before-${RunId}-${Stamp}.json"
Copy-Item -LiteralPath $ActiveDescriptor -Destination $ActiveDescriptorBackup
Copy-Item -LiteralPath $CandidateDescriptor -Destination $ActiveDescriptor

.\.venv\Scripts\memoria.exe mvp demo --data-root $WorkspaceRoot
.\.venv\Scripts\memoria.exe mvp status --data-root $WorkspaceRoot
```

Se una verifica fallisce, ripristinare immediatamente il descriptor precedente:

```powershell
Copy-Item -LiteralPath $ActiveDescriptorBackup -Destination $ActiveDescriptor -Force
```

Dopo la promozione, `$PipelineRunId` e' l'unica golden run usabile dalla golden
run tecnica e dalla presentazione finanziatori. La run precedente resta
archiviata e auditabile, non attiva.

## Non fare

- Non eseguire piu' la vecchia procedura `t33c-three-deep-cases-v1`.
- Non creare un descriptor separato per la presentazione.
- Non aggiornare `memoria_mvp_demo.active.json` prima della fase 5.
- Non usare `-RunOcr`, `-AcquireOnlineDocuments` o
  `-ExecuteFirstPlannedAttempt`.
- Non dichiarare che il materiale Bendini di `storia_memoria_bo` e' stato
  analizzato da questa procedura.
- Non eseguire `apply_profile_patch.ps1`.
- Non promuovere facts preview a fatti canonici.
