[CmdletBinding()]
param(
    [string[]]$SummaryJson = @(),
    [string[]]$RunDir = @(),
    [string]$EvidenceDatabasePath = "",
    [string[]]$EvidenceSourceRunId = @(),
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

$normalizedSummaryJson = @(Normalize-StringArray -Values $SummaryJson)
$normalizedRunDir = @(Normalize-StringArray -Values $RunDir)
$normalizedEvidenceSourceRunId = @(Normalize-StringArray -Values $EvidenceSourceRunId)
if ($normalizedSummaryJson.Count -eq 0 -and $normalizedRunDir.Count -eq 0) {
    if ([string]::IsNullOrWhiteSpace($EvidenceDatabasePath)) {
        throw "Specificare almeno -SummaryJson, -RunDir o -EvidenceDatabasePath."
    }
    if ($normalizedEvidenceSourceRunId.Count -eq 0) {
        throw "Quando si usa solo -EvidenceDatabasePath, specificare almeno -EvidenceSourceRunId."
    }
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
    $argsList = @("-m", "caduti_fonti_report.document_analysis.mvp_consolidated_review_ledger")
    foreach ($path in $normalizedSummaryJson) {
        $argsList += @("--summary-json", $path)
    }
    foreach ($path in $normalizedRunDir) {
        $argsList += @("--run-dir", $path)
    }
    if (-not [string]::IsNullOrWhiteSpace($EvidenceDatabasePath)) {
        $argsList += @("--evidence-db", $EvidenceDatabasePath)
    }
    foreach ($runId in $normalizedEvidenceSourceRunId) {
        $argsList += @("--evidence-source-run-id", $runId)
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
