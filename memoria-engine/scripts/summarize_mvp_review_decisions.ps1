[CmdletBinding()]
param(
    [string]$ReviewQueueJson,
    [string]$DecisionsJson,
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

if ([string]::IsNullOrWhiteSpace($ReviewQueueJson)) {
    throw "Specificare -ReviewQueueJson, per esempio risultati\runs\<run>\historian_review\review_queue.json."
}
if ([string]::IsNullOrWhiteSpace($DecisionsJson)) {
    throw "Specificare -DecisionsJson, per esempio risultati\runs\<run>\historian_review\review_decisions.template.json compilato."
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
        "-m", "caduti_fonti_report.document_analysis.mvp_review_decisions",
        "--review-queue-json", $ReviewQueueJson,
        "--decisions-json", $DecisionsJson
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
