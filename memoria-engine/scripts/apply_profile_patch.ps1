[CmdletBinding()]
param(
    [string]$ProfileJsonld,
    [string]$PatchJson,
    [string]$OutputJsonld,
    [string]$AuditJson = "risultati\profile_patch.audit.json",
    [string]$AuditMd = "risultati\profile_patch.audit.md",
    [string]$BackupDir = "",
    [switch]$DryRun
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
        "-m", "caduti_fonti_report.apply_profile_patch",
        "--profile-jsonld", $ProfileJsonld,
        "--patch-json", $PatchJson,
        "--output-jsonld", $OutputJsonld,
        "--audit-json", $AuditJson,
        "--audit-md", $AuditMd
    )
    if (-not [string]::IsNullOrWhiteSpace($BackupDir)) {
        $argsList += @("--backup-dir", $BackupDir)
    }
    if ($DryRun) {
        $argsList += "--dry-run"
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
