[CmdletBinding()]
param(
    [string]$PackageReadinessJson,
    [string]$SummaryJson,
    [string]$ReviewDecisionsSummaryJson,
    [string]$CuratorialBriefMd = "",
    [string]$SourceCoverageSummaryJson = "",
    [string]$ConsolidatedLedgerJson = "",
    [string]$VerifiedFactsPreviewJson = "",
    [string]$OutputJson = "",
    [string]$OutputMd = ""
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

if ([string]::IsNullOrWhiteSpace($PackageReadinessJson)) {
    throw "Specificare -PackageReadinessJson, per esempio risultati\runs\<run>\mvp_package_readiness.json."
}
if ([string]::IsNullOrWhiteSpace($SummaryJson)) {
    throw "Specificare -SummaryJson, per esempio risultati\runs\<run>\document_analysis\mvp_pilot_summary.json."
}
if ([string]::IsNullOrWhiteSpace($ReviewDecisionsSummaryJson)) {
    throw "Specificare -ReviewDecisionsSummaryJson, per esempio risultati\runs\<run>\historian_review\review_decisions_summary.json."
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
    $argsList = @(
        "-m", "caduti_fonti_report.document_analysis.mvp_funding_dossier",
        "--package-readiness-json", $PackageReadinessJson,
        "--summary-json", $SummaryJson,
        "--review-decisions-summary-json", $ReviewDecisionsSummaryJson
    )
    if (-not [string]::IsNullOrWhiteSpace($CuratorialBriefMd)) {
        $argsList += @("--curatorial-brief-md", $CuratorialBriefMd)
    }
    if (-not [string]::IsNullOrWhiteSpace($SourceCoverageSummaryJson) -and (Test-Path -LiteralPath $SourceCoverageSummaryJson -PathType Leaf)) {
        $argsList += @("--source-coverage-summary-json", $SourceCoverageSummaryJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($ConsolidatedLedgerJson) -and (Test-Path -LiteralPath $ConsolidatedLedgerJson -PathType Leaf)) {
        $argsList += @("--consolidated-ledger-json", $ConsolidatedLedgerJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($VerifiedFactsPreviewJson) -and (Test-Path -LiteralPath $VerifiedFactsPreviewJson -PathType Leaf)) {
        $argsList += @("--verified-facts-preview-json", $VerifiedFactsPreviewJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputJson)) {
        $argsList += @("--output-json", $OutputJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputMd)) {
        $argsList += @("--output-md", $OutputMd)
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
