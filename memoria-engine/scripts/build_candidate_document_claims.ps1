[CmdletBinding()]
param(
    [string]$EntitiesJson = "risultati\document_analysis\extracted_entities.json",
    [string]$LinksJson = "risultati\document_analysis\candidate_document_person_links.json",
    [string]$QualityDir = "data\processed\documents",
    [string]$OutputJson = "risultati\document_analysis\candidate_evidence_claims.json",
    [string]$OutputMd = "risultati\document_analysis\candidate_evidence_claims.md"
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
        -m caduti_fonti_report.document_analysis.candidate_claims `
        --entities-json $EntitiesJson `
        --links-json $LinksJson `
        --quality-dir $QualityDir `
        --output-json $OutputJson `
        --output-md $OutputMd
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
