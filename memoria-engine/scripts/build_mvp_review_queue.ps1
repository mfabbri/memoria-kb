[CmdletBinding()]
param(
    [string]$SummaryJson,
    [string]$OutputJson = "",
    [string]$OutputMd = "",
    [string]$DecisionsTemplateJson = ""
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
        "-m", "caduti_fonti_report.document_analysis.mvp_review_queue",
        "--summary-json", $SummaryJson
    )
    if (-not [string]::IsNullOrWhiteSpace($OutputJson)) {
        $argsList += @("--output-json", $OutputJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputMd)) {
        $argsList += @("--output-md", $OutputMd)
    }
    if (-not [string]::IsNullOrWhiteSpace($DecisionsTemplateJson)) {
        $argsList += @("--decisions-template-json", $DecisionsTemplateJson)
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
