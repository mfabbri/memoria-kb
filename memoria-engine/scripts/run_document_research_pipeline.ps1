[CmdletBinding()]
param(
    [string]$RunId = "",
    [string]$ProcessedDir = "data\processed\documents",
    [Alias("RemoteResultsDir")]
    [string]$ResultsDir = "risultati",
    [string]$ResearchDir = "ricerche",
    [string]$ProfilesIndex = "",
    [string]$SourcesYaml = "",
    [string]$PlacesIndex = "",
    [string]$ProfileId = "",
    [string]$Source = "",
    [int]$Limit = 0,
    [switch]$SkipOnline,
    [switch]$IncludeSearchPlan,
    [switch]$ExecuteFirstPlannedAttempt,
    [string]$AcquireDocumentsRoot = "",
    [double]$SimilarityThreshold = 0.86
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
        "-m", "caduti_fonti_report.document_analysis.pipeline_runner",
        "--processed-dir", $ProcessedDir,
        "--results-dir", $ResultsDir,
        "--research-dir", $ResearchDir,
        "--limit", "$Limit",
        "--similarity-threshold", "$SimilarityThreshold"
    )
    if (-not [string]::IsNullOrWhiteSpace($ProfilesIndex)) {
        $argsList += @("--profiles-index", $ProfilesIndex)
    }
    if (-not [string]::IsNullOrWhiteSpace($SourcesYaml)) {
        $argsList += @("--sources-yaml", $SourcesYaml)
    }
    if (-not [string]::IsNullOrWhiteSpace($PlacesIndex)) {
        $argsList += @("--places-index", $PlacesIndex)
    }
    if (-not [string]::IsNullOrWhiteSpace($RunId)) {
        $argsList += @("--run-id", $RunId)
    }
    if (-not [string]::IsNullOrWhiteSpace($ProfileId)) {
        $argsList += @("--profile-id", $ProfileId)
    }
    if (-not [string]::IsNullOrWhiteSpace($Source)) {
        $argsList += @("--source", $Source)
    }
    if ($SkipOnline) {
        $argsList += "--skip-online"
    }
    if ($IncludeSearchPlan) {
        $argsList += "--include-search-plan"
    }
    if ($ExecuteFirstPlannedAttempt) {
        $argsList += "--execute-first-planned-attempt"
    }
    if (-not [string]::IsNullOrWhiteSpace($AcquireDocumentsRoot)) {
        $argsList += @("--acquire-documents-root", $AcquireDocumentsRoot)
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
