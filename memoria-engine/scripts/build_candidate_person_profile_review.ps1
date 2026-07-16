[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CandidatesJson,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$DecisionsJson = "",
    [string[]]$AcceptedCandidateProfileId = @(),
    [int]$Limit = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }

$previousPythonPath = $env:PYTHONPATH
$codePath = Join-Path $repoRoot "code"
if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $env:PYTHONPATH = $codePath
} else {
    $env:PYTHONPATH = "$codePath;$previousPythonPath"
}

try {
    Push-Location $repoRoot
    $argsList = @(
        "-m", "caduti_fonti_report.document_analysis.candidate_person_profile_review",
        "--candidates-json", $CandidatesJson,
        "--output-dir", $OutputDir
    )
    if (-not [string]::IsNullOrWhiteSpace($DecisionsJson)) {
        $argsList += @("--decisions-json", $DecisionsJson)
    }
    foreach ($candidateProfileId in $AcceptedCandidateProfileId) {
        if (-not [string]::IsNullOrWhiteSpace($candidateProfileId)) {
            $argsList += @("--accepted-candidate-profile-id", $candidateProfileId)
        }
    }
    if ($Limit -gt 0) {
        $argsList += @("--limit", "$Limit")
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
