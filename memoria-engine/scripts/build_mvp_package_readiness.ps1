[CmdletBinding()]
param(
    [string]$SummaryJson,
    [string]$ReviewQueueJson,
    [string]$ReviewDecisionsSummaryJson,
    [string]$VaultDir,
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

if ([string]::IsNullOrWhiteSpace($SummaryJson)) {
    throw "Specificare -SummaryJson, per esempio risultati\runs\<run>\document_analysis\mvp_pilot_summary.json."
}
if ([string]::IsNullOrWhiteSpace($ReviewQueueJson)) {
    throw "Specificare -ReviewQueueJson, per esempio risultati\runs\<run>\historian_review\review_queue.json."
}
if ([string]::IsNullOrWhiteSpace($ReviewDecisionsSummaryJson)) {
    throw "Specificare -ReviewDecisionsSummaryJson, per esempio risultati\runs\<run>\historian_review\review_decisions_summary.json."
}
if ([string]::IsNullOrWhiteSpace($VaultDir)) {
    throw "Specificare -VaultDir, per esempio risultati\<run>-vault."
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
        "-m", "caduti_fonti_report.document_analysis.mvp_package_readiness",
        "--summary-json", $SummaryJson,
        "--review-queue-json", $ReviewQueueJson,
        "--review-decisions-summary-json", $ReviewDecisionsSummaryJson,
        "--vault-dir", $VaultDir
    )
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
