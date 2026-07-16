[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot,
    [string]$PilotProfilesJson = "",
    [string]$OutputJson = "",
    [string]$OutputMd = "",
    [switch]$EnsureStructure
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

if ([string]::IsNullOrWhiteSpace($OutputJson)) {
    $OutputJson = Join-Path $WorkspaceRoot "risultati\mvp_document_intake\document_intake_preflight.json"
}
if ([string]::IsNullOrWhiteSpace($OutputMd)) {
    $OutputMd = Join-Path $WorkspaceRoot "risultati\mvp_document_intake\document_intake_preflight.md"
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
        "-m",
        "caduti_fonti_report.document_analysis.mvp_document_intake_preflight",
        "--workspace-root",
        $WorkspaceRoot,
        "--output-json",
        $OutputJson,
        "--output-md",
        $OutputMd
    )
    if (-not [string]::IsNullOrWhiteSpace($PilotProfilesJson)) {
        $argsList += @("--pilot-profiles-json", $PilotProfilesJson)
    }
    if ($EnsureStructure) {
        $argsList += "--ensure-structure"
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
