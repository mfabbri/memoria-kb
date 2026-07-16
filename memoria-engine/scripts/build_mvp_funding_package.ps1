[CmdletBinding()]
param(
    [string]$RunDir,
    [ValidateSet("passed", "failed", "not_recorded")]
    [string]$QualityGateStatus = "not_recorded",
    [string]$DemoDescriptorJson = "",
    [string]$OutputChecklistJson = "",
    [string]$OutputChecklistMd = "",
    [string]$OutputIndexMd = ""
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

if ([string]::IsNullOrWhiteSpace($RunDir)) {
    throw "Specificare -RunDir, per esempio P:\Comune\Me.Mo.Ri.a\risultati\runs\mvp-finanziabile-final-check-pipeline."
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
        "-m", "caduti_fonti_report.document_analysis.mvp_funding_package",
        "--run-dir", $RunDir,
        "--quality-gate-status", $QualityGateStatus
    )
    if (-not [string]::IsNullOrWhiteSpace($OutputChecklistJson)) {
        $argsList += @("--output-checklist-json", $OutputChecklistJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($DemoDescriptorJson)) {
        $argsList += @("--demo-descriptor-json", $DemoDescriptorJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputChecklistMd)) {
        $argsList += @("--output-checklist-md", $OutputChecklistMd)
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputIndexMd)) {
        $argsList += @("--output-index-md", $OutputIndexMd)
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
