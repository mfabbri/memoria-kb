[CmdletBinding()]
param(
    [string]$TextDir = "data\processed\documents",
    [string]$GlossaryDir = "..\memoria-knowledge\glossary\military",
    [string]$OutputJson = "risultati\document_analysis\military_glossary_mentions.json",
    [string]$OutputMd = "risultati\document_analysis\military_glossary_mentions.md"
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
    $argsList = @(
        "-m", "caduti_fonti_report.document_analysis.military_glossary",
        "--text-dir", $TextDir,
        "--glossary-dir", $GlossaryDir,
        "--output-json", $OutputJson,
        "--output-md", $OutputMd
    )
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
