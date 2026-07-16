[CmdletBinding()]
param(
    [string]$EvidenceDatabasePath,
    [string[]]$EvidenceSourceRunId = @(),
    [string[]]$ProfileId = @(),
    [string]$VerifiedFactsPreviewJson = "",
    [string]$ProfilePatchPreviewJson = "",
    [string]$OutputJson,
    [string]$OutputMd,
    [int]$Limit = 0
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

if ([string]::IsNullOrWhiteSpace($EvidenceDatabasePath)) {
    throw "Specificare -EvidenceDatabasePath, per esempio P:\Comune\Me.Mo.Ri.a\database\evidence.sqlite."
}
if ($EvidenceSourceRunId.Count -eq 0) {
    throw "Specificare almeno un -EvidenceSourceRunId."
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
        "-m", "caduti_fonti_report.document_analysis.dataset_export_preview",
        "--evidence-db", $EvidenceDatabasePath,
        "--output-json", $OutputJson,
        "--output-md", $OutputMd,
        "--limit", "$Limit"
    )
    foreach ($runId in $EvidenceSourceRunId) {
        if (-not [string]::IsNullOrWhiteSpace($runId)) {
            $argsList += @("--evidence-source-run-id", $runId)
        }
    }
    foreach ($id in $ProfileId) {
        if (-not [string]::IsNullOrWhiteSpace($id)) {
            $argsList += @("--profile-id", $id)
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($VerifiedFactsPreviewJson)) {
        $argsList += @("--verified-facts-preview-json", $VerifiedFactsPreviewJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($ProfilePatchPreviewJson)) {
        $argsList += @("--profile-patch-preview-json", $ProfilePatchPreviewJson)
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
