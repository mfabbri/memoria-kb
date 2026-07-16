[CmdletBinding()]
param(
    [string]$DatabasePath = "",
    [switch]$Summary,
    [switch]$Runs,
    [string]$RunId = "",
    [switch]$Documents,
    [switch]$Sources,
    [switch]$EvidenceImports,
    [switch]$EvidenceRecords,
    [switch]$EvidenceSubjects,
    [switch]$EvidenceCoverage,
    [int]$Limit = 0,
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
    if (Test-Path $venvPython) {
        return $venvPython
    }

    try {
        $null = & $systemPython -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $systemPython
        }
    } catch {
        # Fall through to the explicit error below.
    }

    throw "Nessun interprete Python disponibile. Crea .venv oppure installa Python nel PATH."
}

$pythonExe = Resolve-PythonExe
$resolvedPython = (& $pythonExe -c "import sys; print(sys.executable)")
Write-Host "Uso Python: $resolvedPython"

$previousPythonPath = $env:PYTHONPATH
if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $env:PYTHONPATH = Join-Path $repoRoot "code"
} else {
    $env:PYTHONPATH = "$(Join-Path $repoRoot "code");$previousPythonPath"
}

try {
    $argsList = @("-m", "caduti_fonti_report.inspect_evidence_db")
    if (-not [string]::IsNullOrWhiteSpace($DatabasePath)) {
        $argsList += @("--db", $DatabasePath)
    }
    if ($Summary) {
        $argsList += "--summary"
    }
    if ($Runs) {
        $argsList += "--runs"
    }
    if (-not [string]::IsNullOrWhiteSpace($RunId)) {
        $argsList += @("--run-id", $RunId)
    }
    if ($Documents) {
        $argsList += "--documents"
    }
    if ($Sources) {
        $argsList += "--sources"
    }
    if ($EvidenceImports) {
        $argsList += "--evidence-imports"
    }
    if ($EvidenceRecords) {
        $argsList += "--evidence-records"
    }
    if ($EvidenceSubjects) {
        $argsList += "--evidence-subjects"
    }
    if ($EvidenceCoverage) {
        $argsList += "--evidence-coverage"
    }
    if ($Limit -gt 0) {
        $argsList += @("--limit", "$Limit")
    }
    $argsList += $ExtraArgs
    & $pythonExe @argsList
    exit $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
