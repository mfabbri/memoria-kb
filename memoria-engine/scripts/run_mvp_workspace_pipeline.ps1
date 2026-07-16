[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot,
    [string]$RunId = "mvp-workspace-pipeline",
    [string]$InputRootDir = "",
    [switch]$ReportsOnly,
    [switch]$SkipEvidenceImport,
    [string]$ReuseLocalRunId = "",
    [string]$ReusePipelineRunId = "",
    [switch]$SkipOnline,
    [switch]$RunOcr,
    [switch]$ForceDerived,
    [switch]$ForceOcr,
    [switch]$PreprocessBeforeOcr,
    [switch]$EnableRegionOcr,
    [string]$OcrLanguage = "ita",
    [string]$TesseractPath = "tesseract",
    [string]$PageSegmentationMode = "",
    [string]$EngineMode = "",
    [string]$Dpi = "",
    [int]$OcrMaxWorkers = 2,
    [int]$OcrProgressEvery = 25,
    [int]$Limit = 0,
    [int]$VaultLimit = 10,
    [int]$MinLanguageTextChars = 40,
    [string]$ProfilesIndex = "",
    [string]$ReviewDecisionsJson = "",
    [string]$Source = "",
    [switch]$IncludeSearchPlan,
    [switch]$ExecuteFirstPlannedAttempt,
    [switch]$AcquireOnlineDocuments,
    [string]$AcquireDocumentsRoot = "",
    [switch]$BuildCandidateProfileReview,
    [string[]]$AcceptedCandidateProfileId = @(),
    [int]$CandidateProfileLimit = 10,
    [ValidateSet("Demo", "Full", "Debug")]
    [string]$OutputProfile = "Full",
    [string[]]$ProfileId = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

function Require-Directory {
    param(
        [string]$Path,
        [string]$Label
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label non trovata: $Path"
    }
}

$resolvedWorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
$defaultRawDir = Join-Path $resolvedWorkspaceRoot "documenti_da_processare"
$rawDir = if ([string]::IsNullOrWhiteSpace($InputRootDir)) { $defaultRawDir } else { (Resolve-Path -LiteralPath $InputRootDir).Path }
$processedDir = Join-Path $resolvedWorkspaceRoot "documenti_processati"
$resultsDir = Join-Path $resolvedWorkspaceRoot "risultati"
$researchDir = Join-Path $resolvedWorkspaceRoot "ricerche"
$resolvedAcquireDocumentsRoot = if (-not [string]::IsNullOrWhiteSpace($AcquireDocumentsRoot)) { $AcquireDocumentsRoot } elseif ($AcquireOnlineDocuments) { Join-Path $defaultRawDir "fonti_online" } else { "" }
$defaultProfilesIndex = Join-Path (Join-Path $researchDir "person_profiles") "purocielo.index.jsonld"
$resolvedProfilesIndex = if ([string]::IsNullOrWhiteSpace($ProfilesIndex)) { $defaultProfilesIndex } else { (Resolve-Path -LiteralPath $ProfilesIndex).Path }
$localRunId = if ([string]::IsNullOrWhiteSpace($ReuseLocalRunId)) { "$RunId-local" } else { $ReuseLocalRunId }
$pipelineRunId = "$RunId-pipeline"
$sourcePipelineRunId = if ([string]::IsNullOrWhiteSpace($ReusePipelineRunId)) { $pipelineRunId } else { $ReusePipelineRunId }
$localRunDir = Join-Path (Join-Path $resultsDir "runs") $localRunId
$inputRootIsSubset = ($rawDir -ne $defaultRawDir)
$effectiveProcessedDir = if ($inputRootIsSubset) { Join-Path $localRunDir "processed_documents" } else { $processedDir }
$localDocumentAnalysisDir = Join-Path $localRunDir "document_analysis"
$candidateProfilesJson = Join-Path $localDocumentAnalysisDir "candidate_person_profiles_from_documents.json"
$candidateProfileReviewDir = Join-Path $localDocumentAnalysisDir "candidate_profile_review"
$previewProfilesIndex = Join-Path (Join-Path $candidateProfileReviewDir "preview_person_profiles") "purocielo.index.jsonld"
$databaseDir = Join-Path $resolvedWorkspaceRoot "database"
$dbPath = Join-Path $databaseDir "evidence.sqlite"
$pipelineRunDir = Join-Path (Join-Path $resultsDir "runs") $pipelineRunId
$sourcePipelineRunDir = Join-Path (Join-Path $resultsDir "runs") $sourcePipelineRunId
$sourceResearchFeedbackActionsJson = Join-Path (Join-Path $sourcePipelineRunDir "document_analysis") "research_feedback_actions.json"
$sourceOnlineProfilesReportJson = Join-Path (Join-Path $sourcePipelineRunDir "online") "profiles_meta_search.json"
$summaryJson = Join-Path (Join-Path $pipelineRunDir "document_analysis") "mvp_pilot_summary.json"
$researchFeedbackActionsJson = Join-Path (Join-Path $pipelineRunDir "document_analysis") "research_feedback_actions.json"
$historianReviewDir = Join-Path $pipelineRunDir "historian_review"
$researchFeedbackReviewTableMd = Join-Path $historianReviewDir "research_feedback_actions_review_table.md"
$researchFeedbackReviewSummaryJson = Join-Path $historianReviewDir "research_feedback_actions_review_summary.json"
$researchFeedbackReviewSummaryMd = Join-Path $historianReviewDir "research_feedback_actions_review_summary.md"
$reviewQueueJson = Join-Path $historianReviewDir "review_queue.json"
$reviewQueueMd = Join-Path $historianReviewDir "review_queue.md"
$reviewDecisionsTemplateJson = Join-Path $historianReviewDir "review_decisions.template.json"
$resolvedReviewDecisionsJson = if ([string]::IsNullOrWhiteSpace($ReviewDecisionsJson)) { $reviewDecisionsTemplateJson } else { (Resolve-Path -LiteralPath $ReviewDecisionsJson).Path }
$reviewDecisionsSummaryJson = Join-Path $historianReviewDir "review_decisions_summary.json"
$reviewDecisionsSummaryMd = Join-Path $historianReviewDir "review_decisions_summary.md"
$reviewSessionJson = Join-Path $historianReviewDir "review_session.json"
$reviewSessionMd = Join-Path $historianReviewDir "review_session.md"
$historicalReviewTargetsJson = Join-Path $historianReviewDir "historical_review_targets.json"
$historicalReviewTargetsMd = Join-Path $historianReviewDir "historical_review_targets.md"
$verifiedFactsPreviewJson = Join-Path $historianReviewDir "verified_facts.preview.json"
$verifiedFactsPreviewMd = Join-Path $historianReviewDir "verified_facts.preview.md"
$profilePatchPreviewJson = Join-Path $historianReviewDir "profile_patch.preview.json"
$profilePatchPreviewMd = Join-Path $historianReviewDir "profile_patch.preview.md"
$reviewDecisionConflictRegisterPreviewJson = Join-Path $historianReviewDir "review_decision_conflict_register.preview.json"
$reviewDecisionConflictRegisterPreviewMd = Join-Path $historianReviewDir "review_decision_conflict_register.preview.md"
$reviewFocusDecisionsTableMd = Join-Path $historianReviewDir "review_focus_decisions_table.md"
$reviewDashboardJson = Join-Path $historianReviewDir "review_dashboard.json"
$reviewDashboardMd = Join-Path $historianReviewDir "review_dashboard.md"
$vaultDir = Join-Path $resultsDir "$RunId-vault"
$packageReadinessJson = Join-Path $pipelineRunDir "mvp_package_readiness.json"
$packageReadinessMd = Join-Path $pipelineRunDir "mvp_package_readiness.md"
$consolidatedLedgerJson = Join-Path $pipelineRunDir "mvp_consolidated_review_ledger.json"
$consolidatedLedgerMd = Join-Path $pipelineRunDir "mvp_consolidated_review_ledger.md"
$pilotCardsDigestJson = Join-Path $pipelineRunDir "mvp_pilot_cards_digest.json"
$pilotCardsDigestMd = Join-Path $pipelineRunDir "mvp_pilot_cards_digest.md"
$modelCardsDir = Join-Path $pipelineRunDir "schede_modello"
$fundingExcerptsDir = Join-Path $pipelineRunDir "funding_excerpts"
$datasetExportPreviewJson = Join-Path $pipelineRunDir "dataset_export.preview.json"
$datasetExportPreviewMd = Join-Path $pipelineRunDir "dataset_export.preview.md"
$publicationCardSnapshotsDir = Join-Path $pipelineRunDir "publication_card_snapshots_preview"
$fundingDossierJson = Join-Path $pipelineRunDir "mvp_funding_dossier.json"
$fundingDossierMd = Join-Path $pipelineRunDir "mvp_funding_dossier.md"
$evidenceStoreImportJson = Join-Path $pipelineRunDir "evidence_store_import.json"
$evidenceStoreImportMd = Join-Path $pipelineRunDir "evidence_store_import.md"
$onlineProfilesReportJson = Join-Path (Join-Path $pipelineRunDir "online") "profiles_meta_search.json"
$sourceCoverageJson = Join-Path $pipelineRunDir "source_coverage_summary.json"
$sourceCoverageMd = Join-Path $pipelineRunDir "source_coverage_summary.md"
$mvpRunIndexJson = Join-Path $pipelineRunDir "mvp_run_index.json"
$mvpRunIndexMd = Join-Path $pipelineRunDir "mvp_run_index.md"
$wrapperLog = Join-Path (Join-Path $resultsDir "runs") "$RunId-wrapper.log"

Require-Directory -Path $rawDir -Label "Cartella documenti da processare"
Require-Directory -Path $researchDir -Label "Cartella ricerche"
New-Item -ItemType Directory -Force -Path $effectiveProcessedDir | Out-Null
New-Item -ItemType Directory -Force -Path $resultsDir | Out-Null
New-Item -ItemType Directory -Force -Path $databaseDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $resultsDir "runs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $pipelineRunDir "document_analysis") | Out-Null
New-Item -ItemType Directory -Force -Path $historianReviewDir | Out-Null

function Write-RunLog {
    param([string]$Message)
    Write-Host "[$((Get-Date).ToString('o'))] $Message"
}

function Normalize-StringArray {
    param([string[]]$Values)
    $normalized = New-Object System.Collections.Generic.List[string]
    foreach ($rawValue in $Values) {
        if ([string]::IsNullOrWhiteSpace($rawValue)) {
            continue
        }
        foreach ($part in ($rawValue -split ",")) {
            $value = $part.Trim().Trim('"').Trim("'").Trim()
            if (-not [string]::IsNullOrWhiteSpace($value) -and -not $normalized.Contains($value)) {
                $normalized.Add($value)
            }
        }
    }
    return [string[]]$normalized.ToArray()
}

function New-MvpRunIndexArtifact {
    param(
        [string]$Name,
        [string]$Label,
        [string]$Path,
        [string]$Kind = "file",
        [bool]$Required = $true,
        [string]$Category = "technical_diagnostics"
    )
    $pathType = if ($Kind -eq "directory") { "Container" } else { "Leaf" }
    $status = if ([string]::IsNullOrWhiteSpace($Path)) { "not_configured" } elseif (Test-Path -LiteralPath $Path -PathType $pathType) { "present" } else { "missing" }
    return [ordered]@{
        name = $Name
        label = $Label
        path = $Path
        kind = $Kind
        category = $Category
        required = $Required
        status = $status
    }
}

function Get-MvpOutputProfileGuidance {
    param([string]$Profile)
    if ($Profile -eq "Demo") {
        return [ordered]@{
            summary = "Lettura breve per demo, finanziamento e review rapida."
            primary_categories = @("primary_human_output")
            secondary_categories = @("historian_review")
            hidden_categories = @("machine_audit", "technical_diagnostics")
            note = "Aprire prima gli output principali. Usare review storica, audit macchina e diagnostica solo se serve approfondire."
        }
    }
    if ($Profile -eq "Debug") {
        return [ordered]@{
            summary = "Lettura tecnica completa, inclusi audit macchina e diagnostica."
            primary_categories = @("primary_human_output", "historian_review", "machine_audit", "technical_diagnostics")
            secondary_categories = @()
            hidden_categories = @()
            note = "Tutti gli artefatti sono rilevanti per diagnosi, regressioni e audit tecnico."
        }
    }
    return [ordered]@{
        summary = "Lettura completa compatibile con il comportamento storico del wrapper."
        primary_categories = @("primary_human_output", "historian_review")
        secondary_categories = @("machine_audit", "technical_diagnostics")
        hidden_categories = @()
        note = "Usare gli output principali per la lettura, mantenendo audit e diagnostica disponibili nella stessa run."
    }
}

function Get-MvpRecommendedReadingOrder {
    param(
        [string]$Profile,
        [object[]]$Artifacts
    )
    $artifactByName = @{}
    foreach ($artifact in $Artifacts) {
        $artifactByName[$artifact.name] = $artifact
    }
    if ($Profile -eq "Demo") {
        $names = @(
            "package_readiness",
            "funding_dossier",
            "model_cards_index",
            "pilot_cards_digest",
            "review_session",
            "review_dashboard",
            "historical_review_targets",
            "review_focus_decisions_table",
            "review_decisions_summary",
            "verified_facts_preview",
            "review_decision_conflict_register_preview",
            "dataset_export_preview",
            "publication_card_snapshot_index",
            "vault_dashboard",
            "curatorial_brief"
        )
    } elseif ($Profile -eq "Debug") {
        $names = @(
            "package_readiness",
            "mvp_pilot_summary",
            "mvp_pilot_summary_json",
            "mvp_consolidated_review_ledger",
            "mvp_consolidated_review_ledger_json",
            "review_queue",
            "review_decisions_summary",
            "review_session",
            "review_dashboard",
            "historical_review_targets",
            "historical_review_targets_json",
            "verified_facts_preview",
            "verified_facts_preview_json",
            "profile_patch_preview",
            "profile_patch_preview_json",
            "review_decision_conflict_register_preview",
            "review_decision_conflict_register_preview_json",
            "dataset_export_preview",
            "dataset_export_preview_json",
            "publication_card_snapshot_index",
            "publication_card_snapshot_manifest",
            "review_focus_decisions_table",
            "feedback_review_table",
            "model_cards_index",
            "model_cards_manifest",
            "funding_excerpts",
            "pilot_cards_digest",
            "funding_dossier",
            "local_manifest",
            "pipeline_manifest",
            "wrapper_log"
        )
    } else {
        $names = @(
            "mvp_pilot_summary",
            "mvp_consolidated_review_ledger",
            "pilot_cards_digest",
            "model_cards_index",
            "review_session",
            "review_dashboard",
            "historical_review_targets",
            "review_focus_decisions_table",
            "verified_facts_preview",
            "review_decision_conflict_register_preview",
            "dataset_export_preview",
            "publication_card_snapshot_index",
            "package_readiness",
            "funding_dossier",
            "review_queue",
            "vault_dashboard"
        )
    }
    $items = New-Object System.Collections.Generic.List[object]
    foreach ($name in $names) {
        if ($artifactByName.ContainsKey($name)) {
            $artifact = $artifactByName[$name]
            $items.Add([ordered]@{
                name = $artifact.name
                label = $artifact.label
                path = $artifact.path
                category = $artifact.category
                status = $artifact.status
            })
        }
    }
    return [object[]]$items.ToArray()
}

function Write-MvpRunIndex {
    $artifacts = @(
        New-MvpRunIndexArtifact -Name "local_run_summary" -Label "Summary locale" -Path (Join-Path $localRunDir "run_summary.md") -Category "technical_diagnostics"
        New-MvpRunIndexArtifact -Name "local_manifest" -Label "Manifest locale" -Path (Join-Path $localRunDir "manifest.json") -Category "technical_diagnostics"
        New-MvpRunIndexArtifact -Name "candidate_profile_review" -Label "Review profili candidati" -Path $candidateProfileReviewDir -Kind "directory" -Required:$false
        New-MvpRunIndexArtifact -Name "preview_profiles_index" -Label "Indice profili preview" -Path $previewProfilesIndex -Required:$false -Category "technical_diagnostics"
        New-MvpRunIndexArtifact -Name "pipeline_manifest" -Label "Manifest pipeline documentale" -Path (Join-Path $pipelineRunDir "manifest.json") -Required:(!$ReportsOnly) -Category "technical_diagnostics"
        New-MvpRunIndexArtifact -Name "mvp_pilot_summary" -Label "Summary MVP" -Path (Join-Path (Join-Path $pipelineRunDir "document_analysis") "mvp_pilot_summary.md") -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "mvp_pilot_summary_json" -Label "Summary MVP JSON" -Path $summaryJson -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "mvp_consolidated_review_ledger" -Label "Consolidated Review Ledger MVP" -Path $consolidatedLedgerMd -Category "historian_review"
        New-MvpRunIndexArtifact -Name "mvp_consolidated_review_ledger_json" -Label "Consolidated Review Ledger MVP JSON" -Path $consolidatedLedgerJson -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "review_queue" -Label "Review queue storici" -Path $reviewQueueMd -Category "historian_review"
        New-MvpRunIndexArtifact -Name "review_decisions_template" -Label "Template decisioni review" -Path $reviewDecisionsTemplateJson -Category "historian_review"
        New-MvpRunIndexArtifact -Name "review_decisions_summary" -Label "Summary decisioni review" -Path $reviewDecisionsSummaryMd -Category "historian_review"
        New-MvpRunIndexArtifact -Name "review_session" -Label "Sessione revisione MVP" -Path $reviewSessionMd -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "review_dashboard" -Label "Review dashboard storici" -Path $reviewDashboardMd -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "review_dashboard_json" -Label "Review dashboard storici JSON" -Path $reviewDashboardJson -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "historical_review_targets" -Label "Target storici revisionabili" -Path $historicalReviewTargetsMd -Category "historian_review"
        New-MvpRunIndexArtifact -Name "historical_review_targets_json" -Label "Target storici revisionabili JSON" -Path $historicalReviewTargetsJson -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "verified_facts_preview" -Label "Verified facts preview" -Path $verifiedFactsPreviewMd -Category "historian_review"
        New-MvpRunIndexArtifact -Name "verified_facts_preview_json" -Label "Verified facts preview JSON" -Path $verifiedFactsPreviewJson -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "profile_patch_preview" -Label "ProfilePatch preview" -Path $profilePatchPreviewMd -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "profile_patch_preview_json" -Label "ProfilePatch preview JSON" -Path $profilePatchPreviewJson -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "review_decision_conflict_register_preview" -Label "ReviewDecision/Conflict register preview" -Path $reviewDecisionConflictRegisterPreviewMd -Category "historian_review"
        New-MvpRunIndexArtifact -Name "review_decision_conflict_register_preview_json" -Label "ReviewDecision/Conflict register preview JSON" -Path $reviewDecisionConflictRegisterPreviewJson -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "dataset_export_preview" -Label "Dataset export preview" -Path $datasetExportPreviewMd -Category "historian_review"
        New-MvpRunIndexArtifact -Name "dataset_export_preview_json" -Label "Dataset export preview JSON" -Path $datasetExportPreviewJson -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "review_focus_decisions_table" -Label "Tabella decisioni focus review" -Path $reviewFocusDecisionsTableMd -Category "historian_review"
        New-MvpRunIndexArtifact -Name "feedback_review_table" -Label "Tabella feedback ricerca" -Path $researchFeedbackReviewTableMd -Category "historian_review"
        New-MvpRunIndexArtifact -Name "pilot_cards_digest" -Label "Digest schede pilota MVP" -Path $pilotCardsDigestMd -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "model_cards_index" -Label "Indice schede modello MVP" -Path (Join-Path $modelCardsDir "README.md") -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "model_cards_manifest" -Label "Manifest schede modello MVP" -Path (Join-Path $modelCardsDir "manifest.json") -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "publication_card_snapshot_index" -Label "PublicationCardSnapshot preview" -Path (Join-Path $publicationCardSnapshotsDir "README.md") -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "publication_card_snapshot_manifest" -Label "PublicationCardSnapshot preview manifest" -Path (Join-Path $publicationCardSnapshotsDir "manifest.json") -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "funding_excerpts" -Label "Estratti finanziatore da schede modello" -Path $fundingExcerptsDir -Kind "directory" -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "package_readiness" -Label "Readiness pacchetto MVP" -Path $packageReadinessMd -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "funding_dossier" -Label "Dossier finanziamento MVP" -Path $fundingDossierMd -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "evidence_store_import" -Label "Import evidence store generale" -Path $evidenceStoreImportMd -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "evidence_store_import_json" -Label "Import evidence store generale JSON" -Path $evidenceStoreImportJson -Category "machine_audit"
        New-MvpRunIndexArtifact -Name "online_profiles_report" -Label "Report online profili" -Path $onlineProfilesReportJson -Required:(!$SkipOnline -and !$ReportsOnly)
        New-MvpRunIndexArtifact -Name "source_coverage_summary" -Label "Source coverage summary" -Path $sourceCoverageMd -Required:(!$SkipOnline -and !$ReportsOnly)
        New-MvpRunIndexArtifact -Name "online_acquired_documents" -Label "Documenti online acquisiti" -Path $resolvedAcquireDocumentsRoot -Kind "directory" -Required:$false
        New-MvpRunIndexArtifact -Name "vault_dashboard" -Label "Dashboard Obsidian MVP" -Path (Join-Path (Join-Path $vaultDir "10_Output") "MVP_Pilot_Review.md") -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "curatorial_brief" -Label "Brief curatoriale" -Path (Join-Path (Join-Path $vaultDir "10_Output") "mvp_curatorial_brief.md") -Category "primary_human_output"
        New-MvpRunIndexArtifact -Name "vault_dir" -Label "Vault Obsidian" -Path $vaultDir -Kind "directory" -Category "historian_review"
        New-MvpRunIndexArtifact -Name "wrapper_log" -Label "Log wrapper" -Path $wrapperLog -Category "technical_diagnostics"
    )
    $outputProfileGuidance = Get-MvpOutputProfileGuidance -Profile $OutputProfile
    $recommendedReadingOrder = @(Get-MvpRecommendedReadingOrder -Profile $OutputProfile -Artifacts $artifacts)
    $hiddenCategories = @($outputProfileGuidance.hidden_categories)
    $hiddenByProfile = @($artifacts | Where-Object { $hiddenCategories -contains $_.category })
    $missingRequired = @($artifacts | Where-Object { $_.required -and $_.status -ne "present" })
    $mode = if ($ReportsOnly) { "reports_only" } elseif ($SkipOnline) { "offline" } else { "online_enabled" }
    $warnings = New-Object System.Collections.Generic.List[string]
    foreach ($artifact in $missingRequired) {
        $warnings.Add("Artefatto richiesto mancante: $($artifact.name)")
    }
    if ($normalizedProfileId.Count -eq 0) {
        $warnings.Add("Nessun ProfileId esplicito: summary e vault possono includere tutto l'indice profili attivo.")
    }
    if (-not $ReportsOnly -and -not $SkipOnline -and [string]::IsNullOrWhiteSpace($Source)) {
        $warnings.Add("Online abilitato senza Source esplicita: la pipeline documentale puo' bloccare o saltare la parte online.")
    }
    if ($ReportsOnly) {
        $warnings.Add("Modalita' ReportsOnly: processazione locale e pipeline documentale sono state riusate, non rilanciate.")
    }
    if ($SkipEvidenceImport) {
        $warnings.Add("Import evidence store saltato su richiesta: il database SQLite non e' aggiornato da questa run.")
    }
    $reviewDecisionsInput = [ordered]@{
        path = $resolvedReviewDecisionsJson
        source = if ([string]::IsNullOrWhiteSpace($ReviewDecisionsJson)) { "generated_template" } else { "external_compiled_file" }
        explicit_parameter = [bool](-not [string]::IsNullOrWhiteSpace($ReviewDecisionsJson))
        status = if (Test-Path -LiteralPath $resolvedReviewDecisionsJson -PathType Leaf) { "present" } else { "missing" }
        template_path = $reviewDecisionsTemplateJson
        note = "Input usato per review_decisions_summary; non applica patch, non crea verified_facts e non modifica profili JSON-LD."
    }
    $quicklookCommands = @(
        ('$run = "' + $pipelineRunDir + '"')
        'Get-Content "$run\mvp_package_readiness.md"'
        ('$db = "' + $dbPath + '"')
        'Get-Content "$run\mvp_funding_dossier.md"'
        'Get-Content "$run\document_analysis\mvp_pilot_summary.md"'
        'Get-Content "$run\schede_modello\README.md"'
        'Get-Content "$run\historian_review\review_dashboard.md"'
        'Get-Content "$run\historian_review\historical_review_targets.md"'
        'Get-Content "$run\historian_review\review_focus_decisions_table.md"'
        'Get-Content "$run\historian_review\review_decisions_summary.md"'
        'Get-Content "$run\historian_review\verified_facts.preview.md"'
        'Get-Content "$run\historian_review\review_decision_conflict_register.preview.md"'
        'Get-Content "$run\dataset_export.preview.md"'
        'Get-Content "$run\publication_card_snapshots_preview\README.md"'
        '.\tools\pwsh\pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\inspect_evidence_db.ps1 -DatabasePath $db -EvidenceImports -EvidenceRecords -EvidenceSubjects -EvidenceCoverage -Limit 20'
        'Select-String -Path "$run\document_analysis\mvp_pilot_summary.json","$run\historian_review\review_queue.json","$run\mvp_package_readiness.json" -Pattern "skipped_claim_candidate","not_publishable_without_human_review","ready_for_demo","publication_candidate"'
    )
    $payload = [ordered]@{
        type = "mvp_run_index"
        generated_at = (Get-Date).ToString("o")
        run_id = $RunId
        pipeline_run_id = $pipelineRunId
        source_pipeline_run_id = $sourcePipelineRunId
        mode = $mode
        output_profile = $OutputProfile
        output_profile_guidance = $outputProfileGuidance
        reports_only = [bool]$ReportsOnly
        skip_evidence_import = [bool]$SkipEvidenceImport
        local_run_id = $localRunId
        reuse_local_run_id = $ReuseLocalRunId
        reuse_pipeline_run_id = $ReusePipelineRunId
        skip_online = [bool]$SkipOnline
        source = $Source
        limit = $Limit
        acquire_online_documents = [bool]$AcquireOnlineDocuments
        acquire_documents_root = $resolvedAcquireDocumentsRoot
        workspace_root = $resolvedWorkspaceRoot
        input_root_dir = $rawDir
        default_input_root_dir = $defaultRawDir
        input_root_is_subset = $inputRootIsSubset
        processed_dir = $effectiveProcessedDir
        default_processed_dir = $processedDir
        profiles_index = $resolvedProfilesIndex
        profile_ids = $normalizedProfileId
        accepted_candidate_profile_ids = $normalizedAcceptedCandidateProfileId
        review_decisions_input = $reviewDecisionsInput
        paths = [ordered]@{
            local_run_dir = $localRunDir
            pipeline_run_dir = $pipelineRunDir
            source_pipeline_run_dir = $sourcePipelineRunDir
            evidence_database = $dbPath
            vault_dir = $vaultDir
            wrapper_log = $wrapperLog
        }
        artifacts = $artifacts
        artifact_groups = [ordered]@{
            primary_human_output = @($artifacts | Where-Object { $_.category -eq "primary_human_output" })
            historian_review = @($artifacts | Where-Object { $_.category -eq "historian_review" })
            machine_audit = @($artifacts | Where-Object { $_.category -eq "machine_audit" })
            technical_diagnostics = @($artifacts | Where-Object { $_.category -eq "technical_diagnostics" })
        }
        recommended_reading_order = $recommendedReadingOrder
        hidden_by_profile = $hiddenByProfile
        quicklook_commands = $quicklookCommands
        warnings = [string[]]$warnings.ToArray()
        next_actions = @(
            "Aprire mvp_pilot_summary.md per il quadro tecnico MVP.",
            "Aprire mvp_consolidated_review_ledger.md per la memoria revisionabile consolidata.",
            "Aprire mvp_pilot_cards_digest.md per scegliere le schede pilota da mostrare.",
            "Aprire historian_review/review_dashboard.md come vista iniziale della sessione storici/curatori.",
            "Aprire historian_review/review_session.md per organizzare la sessione storici/curatori.",
            "Aprire historian_review/verified_facts.preview.md per controllare eventuali fatti preview derivati da decisioni approvate.",
            "Aprire historian_review/review_decision_conflict_register.preview.md per controllare decisioni, ambiguita' e conflitti aperti.",
            "Aprire dataset_export.preview.md per la fotografia preview-only di persone, documenti, decisioni e facts preview.",
            "Aprire publication_card_snapshots_preview/README.md per le schede modello congelate come snapshot revisionabili.",
            "Aprire mvp_package_readiness.md per il semaforo del pacchetto.",
            "Aprire mvp_funding_dossier.md per la lettura da partner/finanziatore.",
            "Aprire historian_review/review_queue.md per le decisioni storiche.",
            "Se sono stati acquisiti documenti online, processare il sottoinsieme in documenti_da_processare/fonti_online con run_local_document_processing.ps1.",
            "Aprire il vault Obsidian e il brief curatoriale per la review editoriale."
        )
        note = "Output preview-only: non promuove claim candidati, non aggiorna profili JSON-LD e non rende Obsidian fonte canonica."
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $mvpRunIndexJson -Encoding UTF8

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# Indice run MVP")
    $lines.Add("")
    $lines.Add("Output preview-only: non promuove claim candidati, non aggiorna profili JSON-LD e non rende Obsidian fonte canonica.")
    $lines.Add("")
    $lines.Add("## Run")
    $lines.Add("")
    $lines.Add("- RunId: ``$RunId``")
    $lines.Add("- Modalita': ``$mode``")
    $lines.Add("- Profilo output: ``$OutputProfile``")
    $lines.Add("- Workspace: ``$resolvedWorkspaceRoot``")
    $lines.Add("- Input raw: ``$rawDir``")
    $lines.Add("- Processed: ``$effectiveProcessedDir``")
    if ($inputRootIsSubset) {
        $lines.Add("- Processed default workspace: ``$processedDir``")
    }
    $lines.Add("- Indice profili: ``$resolvedProfilesIndex``")
    if ($normalizedProfileId.Count -gt 0) {
        $lines.Add("- Profili: ``$($normalizedProfileId -join ', ')``")
    } else {
        $lines.Add("- Profili: tutti quelli disponibili nell'indice attivo")
    }
    if (-not [string]::IsNullOrWhiteSpace($Source)) {
        $lines.Add("- Fonte online: ``$Source``")
    }
    $lines.Add("- Run locale: ``$localRunDir``")
    $lines.Add("- Run pipeline: ``$pipelineRunDir``")
    if ($ReportsOnly -and $sourcePipelineRunDir -ne $pipelineRunDir) {
        $lines.Add("- Run pipeline sorgente: ``$sourcePipelineRunDir``")
    }
    $lines.Add("- Vault: ``$vaultDir``")
    $lines.Add("")
    $lines.Add("## Decisioni review usate")
    $lines.Add("")
    $lines.Add("- File decisioni: ``$($reviewDecisionsInput.path)``")
    $lines.Add("- Origine: ``$($reviewDecisionsInput.source)``")
    $lines.Add("- Parametro esplicito: ``$($reviewDecisionsInput.explicit_parameter)``")
    $lines.Add("- Stato file: ``$($reviewDecisionsInput.status)``")
    $lines.Add("- Template generato: ``$($reviewDecisionsInput.template_path)``")
    $lines.Add("- Nota: $($reviewDecisionsInput.note)")
    $lines.Add("")
    $lines.Add("## Profilo output")
    $lines.Add("")
    $lines.Add("- Profilo attivo: ``$OutputProfile``")
    $lines.Add("- Scopo: $($outputProfileGuidance.summary)")
    $lines.Add("- Categorie primarie: ``$($outputProfileGuidance.primary_categories -join ', ')``")
    if ($outputProfileGuidance.secondary_categories.Count -gt 0) {
        $lines.Add("- Categorie secondarie: ``$($outputProfileGuidance.secondary_categories -join ', ')``")
    }
    if ($hiddenByProfile.Count -gt 0) {
        $lines.Add("- Non aprire di default in questo profilo: ``$($hiddenCategories -join ', ')``")
    }
    $lines.Add("- Nota: $($outputProfileGuidance.note)")
    $lines.Add("")
    if ($OutputProfile -eq "Demo") {
        $lines.Add("## Percorso Demo")
        $lines.Add("")
        $lines.Add("Aprire questi file nell'ordine indicato. Ledger, queue, JSON e diagnostica restano disponibili come approfondimento.")
        $lines.Add("")
        $demoIndex = 1
        foreach ($item in $recommendedReadingOrder) {
            $lines.Add("$demoIndex. $($item.label): ``$($item.path)``")
            $demoIndex += 1
        }
        $lines.Add("")
    }
    $lines.Add("## Aprire per primi")
    $lines.Add("")
    $readingIndex = 1
    foreach ($item in $recommendedReadingOrder) {
        $lines.Add("$readingIndex. $($item.label): ``$($item.path)``")
        $readingIndex += 1
    }
    $lines.Add("")
    $lines.Add("## Mappa output")
    $lines.Add("")
    $lines.Add("- Output principali: file Markdown da leggere per demo, finanziamento e review rapida.")
    $lines.Add("- Review storica: materiali per decisioni umane e audit curatoriale.")
    $lines.Add("- Audit macchina: JSON da usare per test, tracciabilita' e rigenerazione report.")
    $lines.Add("- Diagnostica tecnica: log, manifest e file utili al debug, non alla lettura primaria.")
    $lines.Add("")
    $lines.Add("## Comandi rapidi PowerShell")
    $lines.Add("")
    $lines.Add("Copiare un comando per riga in PowerShell. Se si incollano piu' comandi sulla stessa riga, separarli con ``;``.")
    $lines.Add("")
    $lines.Add("``````powershell")
    foreach ($command in $quicklookCommands) {
        $lines.Add($command)
    }
    $lines.Add("``````")
    $lines.Add("")
    $lines.Add("## Artefatti")
    $lines.Add("")
    $lines.Add("| Stato | Categoria | Nome | Percorso |")
    $lines.Add("| --- | --- | --- | --- |")
    foreach ($artifact in $artifacts) {
        $lines.Add("| $($artifact.status) | ``$($artifact.category)`` | $($artifact.label) | ``$($artifact.path)`` |")
    }
    if ($warnings.Count -gt 0) {
        $lines.Add("")
        $lines.Add("## Warning")
        $lines.Add("")
        foreach ($warning in $warnings) {
            $lines.Add("- $warning")
        }
    }
    $lines.Add("")
    $lines.Add("## Prossime azioni")
    $lines.Add("")
    foreach ($action in $payload.next_actions) {
        $lines.Add("- $action")
    }
    $lines | Set-Content -LiteralPath $mvpRunIndexMd -Encoding UTF8
}

$normalizedProfileId = @(Normalize-StringArray -Values $ProfileId)
$normalizedAcceptedCandidateProfileId = @(Normalize-StringArray -Values $AcceptedCandidateProfileId)

Start-Transcript -Path $wrapperLog -Append | Out-Null
Push-Location $repoRoot
try {
    $wrapperStart = Get-Date
    Write-RunLog "RUN START mvp_workspace_pipeline run_id=$RunId"
    Write-RunLog "Workspace: $resolvedWorkspaceRoot"
    Write-RunLog "Input raw: $rawDir"
    if ($inputRootIsSubset) {
        Write-RunLog "Input raw subset: true"
    }
    Write-RunLog "Processed: $effectiveProcessedDir"
    if ($inputRootIsSubset) {
        Write-RunLog "Processed default workspace: $processedDir"
    }
    Write-RunLog "Risultati: $resultsDir"
    Write-RunLog "Ricerche: $researchDir"
    if ($ReportsOnly) {
        Write-RunLog "ReportsOnly: enabled"
        Write-RunLog "Reuse local run id: $localRunId"
        Write-RunLog "Reuse pipeline run id: $sourcePipelineRunId"
        Write-RunLog "Reports output pipeline run id: $pipelineRunId"
    }
    if ($SkipEvidenceImport) {
        Write-RunLog "SkipEvidenceImport: enabled"
    }
    Write-RunLog "Indice profili: $resolvedProfilesIndex"
    Write-RunLog "Decisioni review: $resolvedReviewDecisionsJson"
    if (-not [string]::IsNullOrWhiteSpace($Source)) {
        Write-RunLog "Fonte online: $Source"
    }
    if (-not [string]::IsNullOrWhiteSpace($resolvedAcquireDocumentsRoot)) {
        Write-RunLog "Acquisizione documenti online: $resolvedAcquireDocumentsRoot"
    }
    Write-RunLog "Database: $dbPath"
    Write-RunLog "Wrapper log: $wrapperLog"
    if ($normalizedProfileId.Count -gt 0) {
        Write-RunLog "Profili pilota: $($normalizedProfileId -join ', ')"
    }
    if ($BuildCandidateProfileReview) {
        Write-RunLog "CandidatePersonProfile review: enabled"
        if ($normalizedAcceptedCandidateProfileId.Count -gt 0) {
            Write-RunLog "CandidatePersonProfile accettati inline: $($normalizedAcceptedCandidateProfileId -join ', ')"
        }
    }

    if ($ReportsOnly) {
        Require-Directory -Path $localRunDir -Label "Run locale da riusare"
        Require-Directory -Path $sourcePipelineRunDir -Label "Run pipeline da riusare"
        if (-not (Test-Path -LiteralPath (Join-Path $sourcePipelineRunDir "document_analysis") -PathType Container)) {
            throw "Document analysis della run pipeline da riusare non trovato: $(Join-Path $sourcePipelineRunDir 'document_analysis')"
        }
        Write-RunLog "STEP SKIP init_evidence_db reason=reports_only"
    } else {
        Write-RunLog "STEP START init_evidence_db"
        & (Join-Path $scriptDir "init_evidence_db.ps1") -DatabasePath $dbPath
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END init_evidence_db exit_code=$LASTEXITCODE"
    }

    if ($ReportsOnly) {
        Write-RunLog "STEP SKIP run_local_document_processing reason=reports_only"
        if ($BuildCandidateProfileReview) {
            Write-RunLog "STEP SKIP build_candidate_person_profile_review reason=reports_only"
        }
    } else {
        $localArgs = @{
            RootDir = $rawDir
            ProcessedDir = $effectiveProcessedDir
            ResultsDir = $resultsDir
            ResearchDir = $researchDir
            RunId = $localRunId
            MinLanguageTextChars = $MinLanguageTextChars
        }
        if ($ForceDerived) {
            $localArgs["ForceDerived"] = $true
        }
        if ($RunOcr) {
            $localArgs["RunOcr"] = $true
        }
        if ($ForceOcr) {
            $localArgs["ForceOcr"] = $true
        }
        if ($PreprocessBeforeOcr) {
            $localArgs["PreprocessBeforeOcr"] = $true
        }
        if ($EnableRegionOcr) {
            $localArgs["EnableRegionOcr"] = $true
        }
        if (-not [string]::IsNullOrWhiteSpace($OcrLanguage)) {
            $localArgs["OcrLanguage"] = $OcrLanguage
        }
        if (-not [string]::IsNullOrWhiteSpace($TesseractPath)) {
            $localArgs["TesseractPath"] = $TesseractPath
        }
        if (-not [string]::IsNullOrWhiteSpace($PageSegmentationMode)) {
            $localArgs["PageSegmentationMode"] = $PageSegmentationMode
        }
        if (-not [string]::IsNullOrWhiteSpace($EngineMode)) {
            $localArgs["EngineMode"] = $EngineMode
        }
        if (-not [string]::IsNullOrWhiteSpace($Dpi)) {
            $localArgs["Dpi"] = $Dpi
        }
        if ($OcrMaxWorkers -gt 0) {
            $localArgs["OcrMaxWorkers"] = $OcrMaxWorkers
        }
        if ($OcrProgressEvery -gt 0) {
            $localArgs["OcrProgressEvery"] = $OcrProgressEvery
        }
        Write-RunLog "STEP START run_local_document_processing"
        & (Join-Path $scriptDir "run_local_document_processing.ps1") @localArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END run_local_document_processing exit_code=$LASTEXITCODE"
    }

    if (-not $ReportsOnly -and $BuildCandidateProfileReview) {
        if (Test-Path -LiteralPath $candidateProfilesJson -PathType Leaf) {
            $candidateReviewArgs = @{
                CandidatesJson = $candidateProfilesJson
                OutputDir = $candidateProfileReviewDir
                Limit = $CandidateProfileLimit
            }
            if ($normalizedAcceptedCandidateProfileId.Count -gt 0) {
                $candidateReviewArgs["AcceptedCandidateProfileId"] = $normalizedAcceptedCandidateProfileId
            }
            Write-RunLog "STEP START build_candidate_person_profile_review"
            & (Join-Path $scriptDir "build_candidate_person_profile_review.ps1") @candidateReviewArgs
            if ($LASTEXITCODE -ne 0) {
                exit $LASTEXITCODE
            }
            Write-RunLog "STEP END build_candidate_person_profile_review exit_code=$LASTEXITCODE"
            if ([string]::IsNullOrWhiteSpace($ProfilesIndex) -and (Test-Path -LiteralPath $previewProfilesIndex -PathType Leaf)) {
                $resolvedProfilesIndex = (Resolve-Path -LiteralPath $previewProfilesIndex).Path
                Write-RunLog "Indice profili preview attivo: $resolvedProfilesIndex"
                try {
                    $previewIndexPayload = Get-Content -LiteralPath $resolvedProfilesIndex -Raw | ConvertFrom-Json
                    $previewProfileIds = @($previewIndexPayload.profiles | ForEach-Object { $_.'@id' } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
                    if ($normalizedProfileId.Count -eq 0 -and $previewProfileIds.Count -eq 1) {
                        $normalizedProfileId = @($previewProfileIds[0])
                        Write-RunLog "Profilo pilota preview auto: $($normalizedProfileId[0])"
                    }
                } catch {
                    Write-RunLog "WARN preview_profiles_index_read_failed message=$($_.Exception.Message)"
                }
            } elseif (-not [string]::IsNullOrWhiteSpace($ProfilesIndex)) {
                Write-RunLog "STEP SKIP preview_profiles_index reason=explicit_profiles_index"
            } else {
                Write-RunLog "STEP SKIP preview_profiles_index reason=no_preview_index"
            }
        } else {
            Write-RunLog "STEP SKIP build_candidate_person_profile_review reason=no_candidate_person_profiles"
        }
    }

    if ($ReportsOnly) {
        Write-RunLog "STEP SKIP run_document_research_pipeline reason=reports_only"
    } else {
        $pipelineArgs = @{
            RunId = $pipelineRunId
            ProcessedDir = $effectiveProcessedDir
            ResultsDir = $resultsDir
            ResearchDir = $researchDir
            ProfilesIndex = $resolvedProfilesIndex
            Limit = $Limit
        }
        if ($SkipOnline) {
            $pipelineArgs["SkipOnline"] = $true
        }
        if ($normalizedProfileId.Count -eq 1) {
            $pipelineArgs["ProfileId"] = $normalizedProfileId[0]
        }
        if (-not [string]::IsNullOrWhiteSpace($Source)) {
            $pipelineArgs["Source"] = $Source
        }
        if ($IncludeSearchPlan) {
            $pipelineArgs["IncludeSearchPlan"] = $true
        }
        if ($ExecuteFirstPlannedAttempt) {
            $pipelineArgs["ExecuteFirstPlannedAttempt"] = $true
        }
        if (-not [string]::IsNullOrWhiteSpace($resolvedAcquireDocumentsRoot)) {
            $pipelineArgs["AcquireDocumentsRoot"] = $resolvedAcquireDocumentsRoot
        }
        Write-RunLog "STEP START run_document_research_pipeline"
        & (Join-Path $scriptDir "run_document_research_pipeline.ps1") @pipelineArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END run_document_research_pipeline exit_code=$LASTEXITCODE"
    }

    $coverageInputJson = if ($ReportsOnly) { $sourceOnlineProfilesReportJson } else { $onlineProfilesReportJson }
    if (Test-Path -LiteralPath $coverageInputJson -PathType Leaf) {
        Write-RunLog "STEP START summarize_source_coverage"
        & (Join-Path $scriptDir "summarize_source_coverage.ps1") `
            -InputJson $coverageInputJson `
            -OutputJson $sourceCoverageJson `
            -OutputMd $sourceCoverageMd
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END summarize_source_coverage exit_code=$LASTEXITCODE"
    } else {
        Write-RunLog "STEP SKIP summarize_source_coverage reason=no_online_profiles_report"
    }

    $feedbackActionsInputJson = if ($ReportsOnly) { $sourceResearchFeedbackActionsJson } else { $researchFeedbackActionsJson }

    Write-RunLog "STEP START build_research_feedback_actions_review_table"
    & (Join-Path $scriptDir "build_research_feedback_actions_review_table.ps1") `
        -ActionsJson $feedbackActionsInputJson `
        -OutputMd $researchFeedbackReviewTableMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_research_feedback_actions_review_table exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START summarize_research_feedback_actions_review_table"
    & (Join-Path $scriptDir "summarize_research_feedback_actions_review_table.ps1") `
        -ActionsJson $feedbackActionsInputJson `
        -ReviewTableMd $researchFeedbackReviewTableMd `
        -OutputJson $researchFeedbackReviewSummaryJson `
        -OutputMd $researchFeedbackReviewSummaryMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END summarize_research_feedback_actions_review_table exit_code=$LASTEXITCODE"

    $summaryArgs = @{
        RunDir = if ($ReportsOnly) { $sourcePipelineRunDir } else { $pipelineRunDir }
        LocalRunDir = $localRunDir
        ProfilesIndex = $resolvedProfilesIndex
        OutputJson = $summaryJson
        OutputMd = (Join-Path (Join-Path $pipelineRunDir "document_analysis") "mvp_pilot_summary.md")
    }
    if ($normalizedProfileId.Count -gt 0) {
        $summaryArgs["ProfileId"] = $normalizedProfileId
    }
    Write-RunLog "STEP START build_mvp_pilot_summary"
    & (Join-Path $scriptDir "build_mvp_pilot_summary.ps1") @summaryArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_pilot_summary exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START build_mvp_review_queue"
    & (Join-Path $scriptDir "build_mvp_review_queue.ps1") `
        -SummaryJson $summaryJson `
        -OutputJson $reviewQueueJson `
        -OutputMd $reviewQueueMd `
        -DecisionsTemplateJson $reviewDecisionsTemplateJson
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_review_queue exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START summarize_mvp_review_decisions"
    & (Join-Path $scriptDir "summarize_mvp_review_decisions.ps1") `
        -ReviewQueueJson $reviewQueueJson `
        -DecisionsJson $resolvedReviewDecisionsJson `
        -OutputJson $reviewDecisionsSummaryJson `
        -OutputMd $reviewDecisionsSummaryMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END summarize_mvp_review_decisions exit_code=$LASTEXITCODE"

    if ($SkipEvidenceImport) {
        Write-RunLog "STEP SKIP import_document_analysis_evidence_to_db reason=skip_evidence_import"
        $evidenceSkipPayload = [ordered]@{
            type = "document_analysis_evidence_store_import"
            status = "skipped"
            reason = "skip_evidence_import"
            review_status = "unreviewed"
            publication_status = "not_publishable_without_human_review"
            preview_only = $true
            generated_at = (Get-Date).ToString("o")
            run_dir = $pipelineRunDir
            database_path = $dbPath
            note = "Import SQLite saltato su richiesta; nessun profilo JSON-LD, claim verificato o dato storico e' stato modificato."
        }
        $evidenceSkipPayload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $evidenceStoreImportJson -Encoding UTF8
        @(
            "# Import evidence store"
            ""
            '- Stato: `skipped`'
            '- Motivo: `skip_evidence_import`'
            '- Revisione: `unreviewed`'
            '- Pubblicazione: `not_publishable_without_human_review`'
            '- Preview-only: `true`'
            ""
            "Import SQLite saltato su richiesta. Questo output non modifica profili JSON-LD, claim verificati o dati storici."
        ) | Set-Content -LiteralPath $evidenceStoreImportMd -Encoding UTF8
        Write-RunLog "STEP SKIP build_verified_facts_preview reason=skip_evidence_import"
        $verifiedFactsSkipPayload = [ordered]@{
            type = "verified_facts_preview"
            status = "skipped"
            reason = "skip_evidence_import"
            review_status = "preview-only"
            publication_status = "not_publishable_without_editorial_review"
            preview_only = $true
            generated_at = (Get-Date).ToString("o")
            run_dir = $pipelineRunDir
            database_path = $dbPath
            source_run_id = $pipelineRunId
            note = "Preview verified facts saltata per evitare letture stale dallo evidence store."
        }
        $verifiedFactsSkipPayload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $verifiedFactsPreviewJson -Encoding UTF8
        @(
            "# Verified facts preview"
            ""
            '- Stato: `skipped`'
            '- Motivo: `skip_evidence_import`'
            '- Revisione: `preview-only`'
            '- Pubblicazione: `not_publishable_without_editorial_review`'
            '- Preview-only: `true`'
            ""
            "Preview verified facts saltata per evitare letture stale dallo evidence store."
        ) | Set-Content -LiteralPath $verifiedFactsPreviewMd -Encoding UTF8
        Write-RunLog "STEP SKIP build_verified_facts_profile_patch_preview reason=skip_evidence_import"
        $profilePatchSkipPayload = [ordered]@{
            type = "profile_patch_preview_batch"
            status = "skipped"
            reason = "skip_evidence_import"
            review_status = "preview-only"
            publication_status = "not_publishable_without_editorial_review"
            preview_only = $true
            generated_at = (Get-Date).ToString("o")
            source_verified_facts_preview = $verifiedFactsPreviewJson
            note = "ProfilePatch preview saltata perche' verified_facts.preview e' skipped."
        }
        $profilePatchSkipPayload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $profilePatchPreviewJson -Encoding UTF8
        @(
            "# ProfilePatch preview"
            ""
            '- Stato: `skipped`'
            '- Motivo: `skip_evidence_import`'
            '- Revisione: `preview-only`'
            '- Pubblicazione: `not_publishable_without_editorial_review`'
            '- Preview-only: `true`'
            ""
            "ProfilePatch preview saltata perche' verified_facts.preview e' skipped."
        ) | Set-Content -LiteralPath $profilePatchPreviewMd -Encoding UTF8

        Write-RunLog "STEP SKIP build_review_decision_conflict_register_preview reason=skip_evidence_import"
        $decisionConflictRegisterSkipPayload = [ordered]@{
            type = "review_decision_conflict_register_preview"
            status = "skipped"
            reason = "skip_evidence_import"
            review_status = "preview-only"
            publication_status = "not_publishable_without_editorial_review"
            preview_only = $true
            generated_at = (Get-Date).ToString("o")
            run_dir = $pipelineRunDir
            database_path = $dbPath
            source_run_id = $pipelineRunId
            note = "Registro decisioni/conflitti saltato per evitare letture stale dallo evidence store."
        }
        $decisionConflictRegisterSkipPayload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reviewDecisionConflictRegisterPreviewJson -Encoding UTF8
        @(
            "# ReviewDecision/Conflict register preview"
            ""
            '- Stato: `skipped`'
            '- Motivo: `skip_evidence_import`'
            '- Revisione: `preview-only`'
            '- Pubblicazione: `not_publishable_without_editorial_review`'
            '- Preview-only: `true`'
            ""
            "Registro decisioni/conflitti saltato per evitare letture stale dallo evidence store."
        ) | Set-Content -LiteralPath $reviewDecisionConflictRegisterPreviewMd -Encoding UTF8

        Write-RunLog "STEP SKIP build_dataset_export_preview reason=skip_evidence_import"
        $datasetExportSkipPayload = [ordered]@{
            type = "dataset_export_preview"
            status = "skipped"
            reason = "skip_evidence_import"
            review_status = "preview-only"
            publication_status = "not_publishable_without_editorial_review"
            preview_only = $true
            generated_at = (Get-Date).ToString("o")
            run_dir = $pipelineRunDir
            database_path = $dbPath
            note = "Dataset export preview saltato per evitare letture stale dallo evidence store."
        }
        $datasetExportSkipPayload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $datasetExportPreviewJson -Encoding UTF8
        @(
            "# Dataset export preview"
            ""
            '- Stato: `skipped`'
            '- Motivo: `skip_evidence_import`'
            '- Revisione: `preview-only`'
            '- Pubblicazione: `not_publishable_without_editorial_review`'
            '- Preview-only: `true`'
            ""
            "Dataset export preview saltato per evitare letture stale dallo evidence store."
        ) | Set-Content -LiteralPath $datasetExportPreviewMd -Encoding UTF8
    } else {
        Write-RunLog "STEP START import_document_analysis_evidence_to_db"
        & (Join-Path $scriptDir "import_document_analysis_evidence_to_db.ps1") `
            -RunDir $pipelineRunDir `
            -DatabasePath $dbPath `
            -OutputJson $evidenceStoreImportJson `
            -OutputMd $evidenceStoreImportMd
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END import_document_analysis_evidence_to_db exit_code=$LASTEXITCODE"

        Write-RunLog "STEP START build_verified_facts_preview"
        $verifiedFactsPreviewArgs = @{
            EvidenceDatabasePath = $dbPath
            EvidenceSourceRunId = $pipelineRunId
            OutputJson = $verifiedFactsPreviewJson
            OutputMd = $verifiedFactsPreviewMd
        }
        if ($normalizedProfileId.Count -gt 0) {
            $verifiedFactsPreviewArgs["ProfileId"] = $normalizedProfileId
        }
        & (Join-Path $scriptDir "build_verified_facts_preview.ps1") @verifiedFactsPreviewArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END build_verified_facts_preview exit_code=$LASTEXITCODE"

        Write-RunLog "STEP START build_verified_facts_profile_patch_preview"
        $profilePatchPreviewArgs = @{
            VerifiedFactsPreviewJson = $verifiedFactsPreviewJson
            OutputJson = $profilePatchPreviewJson
            OutputMd = $profilePatchPreviewMd
        }
        if ($normalizedProfileId.Count -gt 0) {
            $profilePatchPreviewArgs["ProfileId"] = $normalizedProfileId
        }
        & (Join-Path $scriptDir "build_verified_facts_profile_patch_preview.ps1") @profilePatchPreviewArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END build_verified_facts_profile_patch_preview exit_code=$LASTEXITCODE"

        Write-RunLog "STEP START build_review_decision_conflict_register_preview"
        $decisionConflictRegisterPreviewArgs = @{
            EvidenceDatabasePath = $dbPath
            EvidenceSourceRunId = $pipelineRunId
            OutputJson = $reviewDecisionConflictRegisterPreviewJson
            OutputMd = $reviewDecisionConflictRegisterPreviewMd
        }
        if ($normalizedProfileId.Count -gt 0) {
            $decisionConflictRegisterPreviewArgs["ProfileId"] = $normalizedProfileId
        }
        & (Join-Path $scriptDir "build_review_decision_conflict_register_preview.ps1") @decisionConflictRegisterPreviewArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END build_review_decision_conflict_register_preview exit_code=$LASTEXITCODE"
    }

    Write-RunLog "STEP START build_mvp_consolidated_review_ledger"
    $ledgerArgs = @{
        SummaryJson = $summaryJson
        OutputJson = $consolidatedLedgerJson
        OutputMd = $consolidatedLedgerMd
    }
    if (-not $SkipEvidenceImport) {
        $ledgerArgs["EvidenceDatabasePath"] = $dbPath
        $ledgerArgs["EvidenceSourceRunId"] = $pipelineRunId
    }
    & (Join-Path $scriptDir "build_mvp_consolidated_review_ledger.ps1") @ledgerArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_consolidated_review_ledger exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START export_obsidian_vault"
    & (Join-Path $scriptDir "export_obsidian_vault.ps1") `
        --mvp-pilot-summary $summaryJson `
        --mvp-review-queue $reviewQueueMd `
        --mvp-review-decisions-summary $reviewDecisionsSummaryJson `
        --output-dir $vaultDir `
        --limit "$VaultLimit"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END export_obsidian_vault exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START build_mvp_pilot_cards_digest"
    & (Join-Path $scriptDir "build_mvp_pilot_cards_digest.ps1") `
        -SummaryJson $summaryJson `
        -VaultDir $vaultDir `
        -Limit $VaultLimit `
        -OutputJson $pilotCardsDigestJson `
        -OutputMd $pilotCardsDigestMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_pilot_cards_digest exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START build_mvp_review_session"
    & (Join-Path $scriptDir "build_mvp_review_session.ps1") `
        -SummaryJson $summaryJson `
        -DigestJson $pilotCardsDigestJson `
        -ReviewQueueJson $reviewQueueJson `
        -ReviewDecisionsSummaryJson $reviewDecisionsSummaryJson `
        -ConsolidatedLedgerJson $consolidatedLedgerJson `
        -OutputJson $reviewSessionJson `
        -OutputMd $reviewSessionMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_review_session exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START build_mvp_model_cards"
    & (Join-Path $scriptDir "build_mvp_model_cards.ps1") `
        -DigestJson $pilotCardsDigestJson `
        -SummaryJson $summaryJson `
        -ReviewSessionJson $reviewSessionJson `
        -VerifiedFactsPreviewJson $verifiedFactsPreviewJson `
        -OutputDir $modelCardsDir `
        -FundingExcerptsDir $fundingExcerptsDir `
        -Limit $VaultLimit
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_model_cards exit_code=$LASTEXITCODE"

    if ($SkipEvidenceImport) {
        Write-RunLog "STEP SKIP build_publication_card_snapshot_preview reason=skip_evidence_import"
        New-Item -ItemType Directory -Force -Path $publicationCardSnapshotsDir | Out-Null
        $snapshotSkipPayload = [ordered]@{
            "@type" = "PublicationCardSnapshotPreviewIndex"
            status = "skipped"
            reason = "skip_evidence_import"
            review_status = "preview-only"
            publication_status = "not_publishable_without_editorial_review"
            preview_only = $true
            generated_at = (Get-Date).ToString("o")
            source_model_cards_manifest_json = (Join-Path $modelCardsDir "manifest.json")
            source_dataset_export_preview_json = $datasetExportPreviewJson
            output_dir = $publicationCardSnapshotsDir
            snapshot_count = 0
            skipped_card_count = 0
            snapshots = @()
            skipped_cards = @()
            note = "Snapshot schede saltati perche' dataset_export.preview e' skipped."
        }
        $snapshotSkipPayload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $publicationCardSnapshotsDir "manifest.json") -Encoding UTF8
        @(
            "# PublicationCardSnapshot preview"
            ""
            '- Stato: `skipped`'
            '- Motivo: `skip_evidence_import`'
            '- Revisione: `preview-only`'
            '- Pubblicazione: `not_publishable_without_editorial_review`'
            '- Preview-only: `true`'
            ""
            "Snapshot schede saltati perche' dataset_export.preview e' skipped."
        ) | Set-Content -LiteralPath (Join-Path $publicationCardSnapshotsDir "README.md") -Encoding UTF8
    } else {
        Write-RunLog "STEP START build_dataset_export_preview"
        $datasetExportPreviewArgs = @{
            EvidenceDatabasePath = $dbPath
            EvidenceSourceRunId = $pipelineRunId
            VerifiedFactsPreviewJson = $verifiedFactsPreviewJson
            ProfilePatchPreviewJson = $profilePatchPreviewJson
            OutputJson = $datasetExportPreviewJson
            OutputMd = $datasetExportPreviewMd
        }
        if ($normalizedProfileId.Count -gt 0) {
            $datasetExportPreviewArgs["ProfileId"] = $normalizedProfileId
        }
        & (Join-Path $scriptDir "build_dataset_export_preview.ps1") @datasetExportPreviewArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END build_dataset_export_preview exit_code=$LASTEXITCODE"

        Write-RunLog "STEP START build_publication_card_snapshot_preview"
        $snapshotPreviewArgs = @{
            ModelCardsManifestJson = (Join-Path $modelCardsDir "manifest.json")
            DatasetExportPreviewJson = $datasetExportPreviewJson
            OutputDir = $publicationCardSnapshotsDir
        }
        if ($normalizedProfileId.Count -gt 0) {
            $snapshotPreviewArgs["ProfileId"] = $normalizedProfileId
        }
        & (Join-Path $scriptDir "build_publication_card_snapshot_preview.ps1") @snapshotPreviewArgs
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Write-RunLog "STEP END build_publication_card_snapshot_preview exit_code=$LASTEXITCODE"
    }

    Write-RunLog "STEP START build_mvp_historical_review_targets"
    & (Join-Path $scriptDir "build_mvp_historical_review_targets.ps1") `
        -ReviewQueueJson $reviewQueueJson `
        -ReviewSessionJson $reviewSessionJson `
        -OutputJson $historicalReviewTargetsJson `
        -OutputMd $historicalReviewTargetsMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_historical_review_targets exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START build_mvp_review_focus_decisions_table"
    & (Join-Path $scriptDir "build_mvp_review_focus_decisions_table.ps1") `
        -Mode BuildTable `
        -ReviewSessionJson $reviewSessionJson `
        -OutputMd $reviewFocusDecisionsTableMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_review_focus_decisions_table exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START build_mvp_review_dashboard"
    & (Join-Path $scriptDir "build_mvp_review_dashboard.ps1") `
        -ReviewSessionJson $reviewSessionJson `
        -ReviewQueueJson $reviewQueueJson `
        -ReviewDecisionsSummaryJson $reviewDecisionsSummaryJson `
        -ConsolidatedLedgerJson $consolidatedLedgerJson `
        -VerifiedFactsPreviewJson $verifiedFactsPreviewJson `
        -OutputJson $reviewDashboardJson `
        -OutputMd $reviewDashboardMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_review_dashboard exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START build_mvp_package_readiness"
    & (Join-Path $scriptDir "build_mvp_package_readiness.ps1") `
        -SummaryJson $summaryJson `
        -ReviewQueueJson $reviewQueueJson `
        -ReviewDecisionsSummaryJson $reviewDecisionsSummaryJson `
        -VaultDir $vaultDir `
        -OutputJson $packageReadinessJson `
        -OutputMd $packageReadinessMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_package_readiness exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START build_mvp_funding_dossier"
    & (Join-Path $scriptDir "build_mvp_funding_dossier.ps1") `
        -PackageReadinessJson $packageReadinessJson `
        -SummaryJson $summaryJson `
        -ReviewDecisionsSummaryJson $reviewDecisionsSummaryJson `
        -CuratorialBriefMd (Join-Path (Join-Path $vaultDir "10_Output") "mvp_curatorial_brief.md") `
        -SourceCoverageSummaryJson $sourceCoverageJson `
        -ConsolidatedLedgerJson $consolidatedLedgerJson `
        -VerifiedFactsPreviewJson $verifiedFactsPreviewJson `
        -OutputJson $fundingDossierJson `
        -OutputMd $fundingDossierMd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-RunLog "STEP END build_mvp_funding_dossier exit_code=$LASTEXITCODE"

    Write-RunLog "STEP START write_mvp_run_index"
    Write-MvpRunIndex
    Write-RunLog "STEP END write_mvp_run_index exit_code=0"

    Write-RunLog "Run locale: $localRunDir"
    Write-RunLog "CandidatePersonProfile review: $candidateProfileReviewDir"
    Write-RunLog "Run pipeline: $pipelineRunDir"
    Write-RunLog "Indice run MVP: $mvpRunIndexMd"
    Write-RunLog "Summary MVP: $summaryJson"
    Write-RunLog "Consolidated Review Ledger MVP: $consolidatedLedgerMd"
    Write-RunLog "Research feedback triage table: $researchFeedbackReviewTableMd"
    Write-RunLog "Research feedback triage summary: $researchFeedbackReviewSummaryMd"
    Write-RunLog "Review queue MVP: $reviewQueueMd"
    Write-RunLog "Review decisions summary MVP: $reviewDecisionsSummaryMd"
    Write-RunLog "Verified facts preview MVP: $verifiedFactsPreviewMd"
    Write-RunLog "ProfilePatch preview MVP: $profilePatchPreviewMd"
    Write-RunLog "ReviewDecision/Conflict register preview MVP: $reviewDecisionConflictRegisterPreviewMd"
    Write-RunLog "Dataset export preview MVP: $datasetExportPreviewMd"
    Write-RunLog "PublicationCardSnapshot preview MVP: $publicationCardSnapshotsDir"
    Write-RunLog "Review dashboard MVP: $reviewDashboardMd"
    Write-RunLog "Target storici revisionabili MVP: $historicalReviewTargetsMd"
    Write-RunLog "Review focus decisions table MVP: $reviewFocusDecisionsTableMd"
    Write-RunLog "Evidence store import: $evidenceStoreImportMd"
    Write-RunLog "Digest schede pilota MVP: $pilotCardsDigestMd"
    Write-RunLog "Schede modello MVP: $modelCardsDir"
    Write-RunLog "Estratti finanziatore MVP: $fundingExcerptsDir"
    Write-RunLog "Sessione revisione MVP: $reviewSessionMd"
    Write-RunLog "Package readiness MVP: $packageReadinessMd"
    Write-RunLog "Dossier finanziamento MVP: $fundingDossierMd"
    Write-RunLog "Source coverage summary: $sourceCoverageMd"
    Write-RunLog "Vault MVP: $vaultDir"
    Write-RunLog "Log wrapper: $wrapperLog"
    $wrapperDuration = ((Get-Date) - $wrapperStart).TotalSeconds
    Write-RunLog ("RUN END mvp_workspace_pipeline run_id={0} status=completed duration={1:N2}s" -f $RunId, $wrapperDuration)
}
finally {
    Pop-Location
    Stop-Transcript | Out-Null
}
