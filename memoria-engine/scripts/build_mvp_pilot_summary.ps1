[CmdletBinding()]
param(
    [string]$RunDir,
    [string]$LocalRunDir = "",
    [Parameter(Mandatory = $true)]
    [string]$ProfilesIndex,
    [string[]]$ProfileId = @(),
    [string]$OutputJson = "",
    [string]$OutputMd = ""
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

function Normalize-StringArray {
    param([string[]]$Values)
    $normalized = New-Object System.Collections.Generic.List[string]
    foreach ($rawValue in $Values) {
        if ([string]::IsNullOrWhiteSpace($rawValue)) {
            continue
        }
        foreach ($part in ($rawValue -split ",")) {
            $value = $part.Trim().Trim('"').Trim("'").Trim()
            if (-not [string]::IsNullOrWhiteSpace($value) -and -not $normalized.Contains($value)) {
                $normalized.Add($value)
            }
        }
    }
    return [string[]]$normalized.ToArray()
}

if ([string]::IsNullOrWhiteSpace($RunDir)) {
    throw "Specificare -RunDir, per esempio risultati\runs\mvp-pilot-local-processing."
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
        "-m", "caduti_fonti_report.document_analysis.mvp_pilot_summary",
        "--run-dir", $RunDir
    )
    if (-not [string]::IsNullOrWhiteSpace($LocalRunDir)) {
        $argsList += @("--local-run-dir", $LocalRunDir)
    }
    if (-not [string]::IsNullOrWhiteSpace($ProfilesIndex)) {
        $argsList += @("--profiles-index", $ProfilesIndex)
    }
    foreach ($id in (Normalize-StringArray -Values $ProfileId)) {
        if (-not [string]::IsNullOrWhiteSpace($id)) {
            $argsList += @("--profile-id", $id)
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputJson)) {
        $argsList += @("--output-json", $OutputJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputMd)) {
        $argsList += @("--output-md", $OutputMd)
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
