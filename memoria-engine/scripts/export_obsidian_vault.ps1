[CmdletBinding()]
param(
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
    & $pythonExe -m caduti_fonti_report.export_obsidian_vault @ExtraArgs
    exit $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
