[CmdletBinding()]
param(
    [string]$TextDir = "data\processed\documents",
    [string]$OutputDir = "data\processed\documents",
    [string]$OutputJson = "risultati\document_analysis\document_chunks.json",
    [string]$OutputMd = "risultati\document_analysis\document_chunks.md",
    [int]$MaxChars = 4500,
    [int]$OverlapChars = 300
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
        -m caduti_fonti_report.document_analysis.document_chunking `
        --text-dir $TextDir `
        --output-dir $OutputDir `
        --output-json $OutputJson `
        --output-md $OutputMd `
        --max-chars $MaxChars `
        --overlap-chars $OverlapChars
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
