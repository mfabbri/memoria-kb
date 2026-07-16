[CmdletBinding()]
param(
    [string]$MetadataDir = "data\processed\documents",
    [string]$OutputJson = "risultati\document_analysis\candidate_duplicate_documents.json",
    [string]$OutputMd = "risultati\document_analysis\candidate_duplicate_documents.md"
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
        -m caduti_fonti_report.document_analysis.document_duplicates `
        --metadata-dir $MetadataDir `
        --output-json $OutputJson `
        --output-md $OutputMd
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
