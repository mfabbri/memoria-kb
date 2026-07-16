[CmdletBinding()]
param(
    [string]$ReportJson,
    [string]$CandidateClaimsJson = "",
    [string]$ProfileJsonld,
    [string]$ProfilesIndex = "",
    [string]$OutputJsonld = "risultati\candidate_profile_updates.jsonld",
    [string]$OutputMd = "risultati\candidate_profile_updates.md"
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
    $updateArgs = @(
        "-m", "caduti_fonti_report.candidate_profile_updates",
        "updates",
        "--profile-jsonld", $ProfileJsonld,
        "--output-jsonld", $OutputJsonld,
        "--output-md", $OutputMd
    )
    if (-not [string]::IsNullOrWhiteSpace($ReportJson)) {
        $updateArgs += @("--report-json", $ReportJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($CandidateClaimsJson)) {
        $updateArgs += @("--candidate-claims-json", $CandidateClaimsJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($ProfilesIndex)) {
        $updateArgs += @("--profiles-index", $ProfilesIndex)
    }
    & $pythonExe @updateArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
