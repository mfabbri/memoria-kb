[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot,
    [Parameter(Mandatory = $true)]
    [string]$ProfilePatchPreviewJson,
    [Parameter(Mandatory = $true)]
    [string]$ProfileId,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$ProfilesIndex = "",
    [switch]$Apply,
    [switch]$Sandbox,
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

$selectedModes = @(@($Apply.IsPresent, $Sandbox.IsPresent, $DryRun.IsPresent) | Where-Object { $_ })
if ($selectedModes.Count -gt 1) {
    throw "Usare -Apply, -Sandbox oppure -DryRun, non piu' di uno."
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
        "-m", "caduti_fonti_report.promote_profile_patch_preview",
        "--workspace-root", $WorkspaceRoot,
        "--profile-patch-preview-json", $ProfilePatchPreviewJson,
        "--profile-id", $ProfileId,
        "--output-dir", $OutputDir
    )
    if (-not [string]::IsNullOrWhiteSpace($ProfilesIndex)) {
        $argsList += @("--profiles-index", $ProfilesIndex)
    }
    if ($Apply) {
        $argsList += "--apply"
    }
    if ($Sandbox) {
        $argsList += "--sandbox"
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
