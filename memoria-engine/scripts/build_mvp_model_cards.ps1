[CmdletBinding()]
param(
    [string]$DigestJson,
    [string]$SummaryJson,
    [string]$ReviewSessionJson,
    [string]$OutputDir,
    [string]$FundingExcerptsDir = "",
    [string]$VerifiedFactsPreviewJson = "",
    [int]$Limit = 5
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

if ([string]::IsNullOrWhiteSpace($DigestJson)) {
    throw "Specificare -DigestJson, per esempio risultati\runs\<run>\mvp_pilot_cards_digest.json."
}
if ([string]::IsNullOrWhiteSpace($SummaryJson)) {
    throw "Specificare -SummaryJson, per esempio risultati\runs\<run>\document_analysis\mvp_pilot_summary.json."
}
if ([string]::IsNullOrWhiteSpace($ReviewSessionJson)) {
    throw "Specificare -ReviewSessionJson, per esempio risultati\runs\<run>\historian_review\review_session.json."
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    throw "Specificare -OutputDir, per esempio risultati\runs\<run>\schede_modello."
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
        "-m", "caduti_fonti_report.document_analysis.mvp_model_cards",
        "--digest-json", $DigestJson,
        "--summary-json", $SummaryJson,
        "--review-session-json", $ReviewSessionJson,
        "--output-dir", $OutputDir,
        "--limit", "$Limit"
    )
    if (-not [string]::IsNullOrWhiteSpace($FundingExcerptsDir)) {
        $argsList += @("--funding-excerpts-dir", $FundingExcerptsDir)
    }
    if (-not [string]::IsNullOrWhiteSpace($VerifiedFactsPreviewJson)) {
        $argsList += @("--verified-facts-preview-json", $VerifiedFactsPreviewJson)
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
