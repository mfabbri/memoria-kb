[CmdletBinding()]
param(
    [string]$LanguageDir = "data\processed\documents",
    [string]$LanguageJson = "",
    [string]$OutputDir = "data\processed\documents",
    [string]$OutputJson = "risultati\document_analysis\document_language_routing.json",
    [string]$OutputMd = "risultati\document_analysis\document_language_routing.md"
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
        "-m", "caduti_fonti_report.document_analysis.language_routing",
        "--language-dir", $LanguageDir,
        "--output-dir", $OutputDir,
        "--output-json", $OutputJson,
        "--output-md", $OutputMd
    )
    if (-not [string]::IsNullOrWhiteSpace($LanguageJson)) {
        $argsList += @("--language-json", $LanguageJson)
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
