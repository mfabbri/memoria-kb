[CmdletBinding()]
param(
    [string]$MentionsDir = "data\processed\documents",
    [string]$PlacesIndex = "..\memoria-knowledge\places\places.index.jsonld",
    [string]$OutputJson = "risultati\document_analysis\candidate_document_place_links.json",
    [string]$OutputMd = "risultati\document_analysis\candidate_document_place_links.md"
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
        -m caduti_fonti_report.document_analysis.place_linking `
        --mentions-dir $MentionsDir `
        --places-index $PlacesIndex `
        --output-json $OutputJson `
        --output-md $OutputMd
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
