[CmdletBinding()]
param(
    [string]$RepoRoot,
    [Alias("sources-yaml")]
    [string]$SourcesYaml = "..\memoria-sources\registry\camalanca_fonti.yaml",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultRepoRoot = Split-Path -Parent $scriptDir
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = $defaultRepoRoot
}
$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$venvPython = Join-Path $resolvedRepoRoot ".venv\Scripts\python.exe"
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
$codePath = Join-Path $resolvedRepoRoot "code"
if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $env:PYTHONPATH = $codePath
} else {
    $env:PYTHONPATH = "$codePath;$previousPythonPath"
}

try {
    Push-Location $resolvedRepoRoot
    $pythonExe = Resolve-PythonExe
    $resolvedPython = (& $pythonExe -c "import sys; print(sys.executable)")
    Write-Host "Uso Python: $resolvedPython"
    Write-Host "Registry fonti: $SourcesYaml"
    & $pythonExe -m caduti_fonti_report.validate_sources_registry --sources-yaml $SourcesYaml @ExtraArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
