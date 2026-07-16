[CmdletBinding()]
param(
    [string]$RepoRoot,
    [ValidateSet("Targeted", "CandidateFilters", "SourceAudit", "Registry", "DetailLogic", "Full")]
    [string]$Suite = "Targeted",
    [string[]]$TestPath,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultRepoRoot = Split-Path -Parent $scriptDir
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = $defaultRepoRoot
}
$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$venvPython = Join-Path $resolvedRepoRoot ".venv\Scripts\python.exe"
$systemPython = "python"

function Test-PythonCanImportProject {
    param([string]$PythonExe)
    try {
        $null = & $PythonExe -c "import yaml; import caduti_fonti_report" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-PythonExe {
    if (Test-Path -LiteralPath $venvPython) {
        if (Test-PythonCanImportProject -PythonExe $venvPython) {
            return $venvPython
        }
    }

    if (Test-PythonCanImportProject -PythonExe $systemPython) {
        return $systemPython
    }

    throw "Nessun interprete Python disponibile con PyYAML e package del progetto importabile."
}

function Get-TestPathsForSuite {
    param([string]$SuiteName)
    switch ($SuiteName) {
        "CandidateFilters" { return @("tests/test_generic_result_parser_candidate_filters.py") }
        "SourceAudit" { return @("tests/test_source_quality_audit.py") }
        "Registry" { return @("tests/test_sources_registry_validation.py") }
        "DetailLogic" { return @("tests/test_detail_page_logic.py") }
        "Targeted" {
            return @(
                "tests/test_profile_repository.py",
                "tests/test_profiles_runner.py",
                "tests/test_search_strategy_planner.py",
                "tests/test_candidate_profile_updates.py",
                "tests/test_apply_profile_patch.py",
                "tests/test_sqlite_store.py",
                "tests/test_inspect_evidence_db.py",
                "tests/test_document_inventory.py",
                "tests/test_input_processing_plan.py",
                "tests/test_historical_map_catalog.py",
                "tests/test_military_glossary.py",
                "tests/test_manual_document_registration.py",
                "tests/test_manual_document_registration_batch.py",
                "tests/test_german_docs_downloader.py",
                "tests/test_html_document_registration.py",
                "tests/test_document_metadata_extraction.py",
                "tests/test_document_text_extraction.py",
                "tests/test_document_chunking.py",
                "tests/test_llm_chunk_classifier.py",
                "tests/test_document_language_detection.py",
                "tests/test_document_language_routing.py",
                "tests/test_weak_document_segmentation.py",
                "tests/test_document_mention_extraction.py",
                "tests/test_document_research_feedback_actions.py",
                "tests/test_feedback_search_plan.py",
                "tests/test_document_quality_assessment.py",
                "tests/test_document_transcription_registration.py",
                "tests/test_image_preprocessing.py",
                "tests/test_image_preprocessing_plan.py",
                "tests/test_document_ocr_tesseract.py",
                "tests/test_document_ocr_batch.py",
                "tests/test_document_person_linking.py",
                "tests/test_document_place_linking.py",
                "tests/test_document_entity_extraction.py",
                "tests/test_document_candidate_claims.py",
                "tests/test_document_duplicates.py",
                "tests/test_document_clusters.py",
                "tests/test_document_research_pipeline.py",
                "tests/test_document_analysis_evidence_store_import.py",
                "tests/test_source_coverage_summary.py",
                "tests/test_mvp_review_queue.py",
                "tests/test_mvp_review_decisions.py",
                "tests/test_mvp_consolidated_review_ledger.py",
                "tests/test_mvp_pilot_cards_digest.py",
                "tests/test_mvp_model_cards.py",
                "tests/test_mvp_review_session.py",
                "tests/test_mvp_workspace_reports_only.py",
                "tests/test_mvp_funding_dossier.py",
                "tests/test_mvp_funding_package.py",
                "tests/test_memoria_cli.py",
                "tests/test_mvp_review_dashboard.py",
                "tests/test_quality_gate_baseline.py",
                "tests/test_mvp_document_intake_preflight.py",
                "tests/test_local_document_processing_runner.py",
                "tests/test_generic_result_parser_candidate_filters.py",
                "tests/test_atlante_stragi_source_logic.py",
                "tests/test_bundesarchiv_invenio_executor.py",
                "tests/test_source_quality_audit.py",
                "tests/test_sources_registry_validation.py",
                "tests/test_detail_page_logic.py"
            )
        }
        "Full" { return @() }
        default { throw "Suite non supportata: $SuiteName" }
    }
}

$previousPythonPath = $env:PYTHONPATH
$codePath = Join-Path $resolvedRepoRoot "code"
if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $env:PYTHONPATH = $codePath
} else {
    $env:PYTHONPATH = "$codePath;$previousPythonPath"
}

try {
    Push-Location $resolvedRepoRoot
    $pythonExe = Resolve-PythonExe
    $resolvedPython = (& $pythonExe -c "import sys; print(sys.executable)")
    Write-Host "Uso Python: $resolvedPython"

    $selectedTests = @()
    if ($TestPath -and $TestPath.Count -gt 0) {
        $selectedTests = $TestPath
    } else {
        $selectedTests = Get-TestPathsForSuite -SuiteName $Suite
    }

    if ($Suite -eq "Full" -and (-not $TestPath -or $TestPath.Count -eq 0)) {
        Write-Host "Eseguo suite completa unittest discover -s tests -v"
        & $pythonExe -m unittest discover -s tests -v @ExtraArgs
        exit $LASTEXITCODE
    }

    foreach ($test in $selectedTests) {
        if (-not (Test-Path -LiteralPath (Join-Path $resolvedRepoRoot $test))) {
            throw "Test non trovato: $test"
        }
    }

    Write-Host "Suite: $Suite"
    Write-Host "Test selezionati:"
    foreach ($test in $selectedTests) {
        Write-Host " - $test"
    }

    & $pythonExe -m unittest @selectedTests -v @ExtraArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
