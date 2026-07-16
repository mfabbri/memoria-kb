[CmdletBinding()]
param(
    [ValidateSet("BuildTable", "BuildCards", "BuildQueueCards", "ConvertTable")]
    [string]$Mode = "BuildTable",
    [string]$ReviewSessionJson = "",
    [string]$ReviewQueueJson = "",
    [string]$ReviewTableMd = "",
    [string]$OutputMd = "risultati\runs\mvp-workspace-pipeline\historian_review\review_focus_decisions_table.md",
    [string]$OutputDecisionsJson = "risultati\runs\mvp-workspace-pipeline\historian_review\review_decisions.compilato.json",
    [string]$OutputSummaryJson = "risultati\runs\mvp-workspace-pipeline\historian_review\review_focus_decisions_table_summary.json",
    [string]$OutputSummaryMd = "risultati\runs\mvp-workspace-pipeline\historian_review\review_focus_decisions_table_summary.md",
    [string[]]$ProfileId = @(),
    [string[]]$ItemId = @(),
    [int]$Limit = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$systemPython = "python"

function Resolve-PythonExe {
    if (Test-Path -LiteralPath $venvPython) {
        return $venvPython
    }
    return $systemPython
}

$previousPythonPath = $env:PYTHONPATH
$codePath = Join-Path $repoRoot "code"
if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $env:PYTHONPATH = $codePath
} else {
    $env:PYTHONPATH = "$codePath;$previousPythonPath"
}

try {
    Push-Location $repoRoot
    $pythonExe = Resolve-PythonExe
    if ($Mode -eq "BuildTable") {
        if ([string]::IsNullOrWhiteSpace($ReviewSessionJson)) {
            throw "Specificare -ReviewSessionJson, per esempio risultati\runs\<run>\historian_review\review_session.json."
        }
        $argsList = @(
            "-m", "caduti_fonti_report.document_analysis.mvp_review_focus_table",
            "build-table",
            "--review-session-json", $ReviewSessionJson,
            "--output-md", $OutputMd,
            "--limit", "$Limit"
        )
        foreach ($profile in $ProfileId) {
            if (-not [string]::IsNullOrWhiteSpace($profile)) {
                $argsList += @("--profile-id", $profile)
            }
        }
        & $pythonExe @argsList
        exit $LASTEXITCODE
    }
    if ($Mode -eq "BuildCards") {
        if ([string]::IsNullOrWhiteSpace($ReviewSessionJson)) {
            throw "Specificare -ReviewSessionJson, per esempio risultati\runs\<run>\historian_review\review_session.json."
        }
        $argsList = @(
            "-m", "caduti_fonti_report.document_analysis.mvp_review_focus_table",
            "build-cards",
            "--review-session-json", $ReviewSessionJson,
            "--output-md", $OutputMd,
            "--limit", "$Limit"
        )
        foreach ($profile in $ProfileId) {
            if (-not [string]::IsNullOrWhiteSpace($profile)) {
                $argsList += @("--profile-id", $profile)
            }
        }
        & $pythonExe @argsList
        exit $LASTEXITCODE
    }
    if ($Mode -eq "BuildQueueCards") {
        if ([string]::IsNullOrWhiteSpace($ReviewQueueJson)) {
            throw "Specificare -ReviewQueueJson, per esempio risultati\runs\<run>\historian_review\review_queue.json."
        }
        $argsList = @(
            "-m", "caduti_fonti_report.document_analysis.mvp_review_focus_table",
            "build-queue-cards",
            "--review-queue-json", $ReviewQueueJson,
            "--output-md", $OutputMd,
            "--limit", "$Limit"
        )
        foreach ($item in $ItemId) {
            if (-not [string]::IsNullOrWhiteSpace($item)) {
                $argsList += @("--item-id", $item)
            }
        }
        foreach ($profile in $ProfileId) {
            if (-not [string]::IsNullOrWhiteSpace($profile)) {
                $argsList += @("--profile-id", $profile)
            }
        }
        & $pythonExe @argsList
        exit $LASTEXITCODE
    }
    if ([string]::IsNullOrWhiteSpace($ReviewTableMd)) {
        throw "Specificare -ReviewTableMd, per esempio risultati\runs\<run>\historian_review\review_focus_decisions_table.md."
    }
    & $pythonExe `
        -m caduti_fonti_report.document_analysis.mvp_review_focus_table `
        convert-table `
        --review-table-md $ReviewTableMd `
        --output-decisions-json $OutputDecisionsJson `
        --output-summary-json $OutputSummaryJson `
        --output-summary-md $OutputSummaryMd
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
