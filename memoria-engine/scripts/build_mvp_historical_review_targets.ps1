[CmdletBinding()]
param(
    [string]$ReviewQueueJson,
    [string]$ReviewSessionJson = "",
    [string]$EvidenceDatabasePath = "",
    [string[]]$EvidenceSourceRunId = @(),
    [string]$OutputJson,
    [string]$OutputMd,
    [int]$Limit = 10,
    [string[]]$PreferredProfileId = @()
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

if ([string]::IsNullOrWhiteSpace($ReviewQueueJson) -and [string]::IsNullOrWhiteSpace($EvidenceDatabasePath)) {
    throw "Specificare -ReviewQueueJson oppure -EvidenceDatabasePath."
}
if (-not [string]::IsNullOrWhiteSpace($EvidenceDatabasePath) -and $EvidenceSourceRunId.Count -eq 0) {
    throw "Quando si usa -EvidenceDatabasePath, specificare almeno -EvidenceSourceRunId."
}
if ([string]::IsNullOrWhiteSpace($OutputJson)) {
    throw "Specificare -OutputJson."
}
if ([string]::IsNullOrWhiteSpace($OutputMd)) {
    throw "Specificare -OutputMd."
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
        "-m", "caduti_fonti_report.document_analysis.mvp_historical_review_targets",
        "--output-json", $OutputJson,
        "--output-md", $OutputMd,
        "--limit", "$Limit"
    )
    if (-not [string]::IsNullOrWhiteSpace($ReviewQueueJson)) {
        $argsList += @("--review-queue-json", $ReviewQueueJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($ReviewSessionJson)) {
        $argsList += @("--review-session-json", $ReviewSessionJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($EvidenceDatabasePath)) {
        $argsList += @("--evidence-db", $EvidenceDatabasePath)
    }
    foreach ($runId in $EvidenceSourceRunId) {
        if (-not [string]::IsNullOrWhiteSpace($runId)) {
            $argsList += @("--evidence-source-run-id", $runId)
        }
    }
    foreach ($profileId in $PreferredProfileId) {
        if (-not [string]::IsNullOrWhiteSpace($profileId)) {
            $argsList += @("--preferred-profile-id", $profileId)
        }
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
