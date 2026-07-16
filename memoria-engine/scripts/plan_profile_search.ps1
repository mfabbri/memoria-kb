[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProfilesIndex,
    [string]$SourcesYaml = "..\memoria-sources\registry\camalanca_fonti.yaml",
    [Parameter(Mandatory = $true)]
    [string]$ProfileId,
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [string]$OutputJson = "risultati\profile_search_plan.json",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$systemPython = "python"

function Test-PythonCanImportProject {
    param([string]$PythonExe)
    try {
        $null = & $PythonExe -c "import yaml; import caduti_fonti_report" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-PythonExe {
    if (Test-Path -LiteralPath $venvPython) {
        if (Test-PythonCanImportProject -PythonExe $venvPython) {
            return $venvPython
        }
    }

    if (Test-PythonCanImportProject -PythonExe $systemPython) {
        return $systemPython
    }

    throw "Nessun interprete Python disponibile con PyYAML e package del progetto importabile."
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
    $resolvedPython = (& $pythonExe -c "import sys; print(sys.executable)")
    Write-Host "Uso Python: $resolvedPython"

    $argsList = @(
        "-m", "caduti_fonti_report.search_strategy_planner",
        "--profiles-index", $ProfilesIndex,
        "--sources-yaml", $SourcesYaml,
        "--profile-id", $ProfileId,
        "--source", $Source,
        "--output-json", $OutputJson
    )
    if ($ExtraArgs -and $ExtraArgs.Count -gt 0) {
        $argsList += $ExtraArgs
    }

    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
