[CmdletBinding()]
param(
    [string]$DatabasePath,
    [string]$ProfileId,
    [string[]]$EvidenceSourceRunId = @(),
    [string]$OutputJson = "",
    [string]$OutputMd = "",
    [int]$Limit = 50,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
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

if ([string]::IsNullOrWhiteSpace($DatabasePath)) {
    throw "Specificare -DatabasePath, per esempio P:\Comune\Me.Mo.Ri.a\database\evidence.sqlite."
}
if ([string]::IsNullOrWhiteSpace($ProfileId)) {
    throw "Specificare -ProfileId, per esempio person:purocielo:andreoli-dino."
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
        "-m", "caduti_fonti_report.document_analysis.evidence_store_profile_status",
        "--db", $DatabasePath,
        "--profile-id", $ProfileId,
        "--limit", "$Limit"
    )
    if (-not [string]::IsNullOrWhiteSpace($OutputJson)) {
        $argsList += @("--output-json", $OutputJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputMd)) {
        $argsList += @("--output-md", $OutputMd)
    }
    foreach ($runId in $EvidenceSourceRunId) {
        if (-not [string]::IsNullOrWhiteSpace($runId)) {
            $argsList += @("--evidence-source-run-id", $runId)
        }
    }
    $argsList += $ExtraArgs
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
