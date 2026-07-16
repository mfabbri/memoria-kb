[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RunDir,
    [Parameter(Mandatory = $true)]
    [string]$DatabasePath,
    [string]$OutputJson = "",
    [string]$OutputMd = "",
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
    $argsList = @(
        "-m",
        "caduti_fonti_report.document_analysis.evidence_store_import",
        "--run-dir",
        $RunDir,
        "--db",
        $DatabasePath
    )
    if (-not [string]::IsNullOrWhiteSpace($OutputJson)) {
        $argsList += @("--output-json", $OutputJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputMd)) {
        $argsList += @("--output-md", $OutputMd)
    }
    $argsList += $ExtraArgs
    & $pythonExe @argsList
    exit $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
