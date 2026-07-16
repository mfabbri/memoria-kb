[CmdletBinding()]
param(
    [string]$RootDir = "data\raw",
    [string]$OutputDir = "data\processed\documents",
    [string]$SummaryJson = "risultati\document_analysis\document_metadata_extraction.json"
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
    & $pythonExe `
        -m caduti_fonti_report.document_analysis.metadata_extraction `
        --root-dir $RootDir `
        --output-dir $OutputDir `
        --summary-json $SummaryJson
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
