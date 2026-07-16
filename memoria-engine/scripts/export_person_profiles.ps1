[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Csv,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [int]$Limit = 0,
    [string]$Name = "",
    [switch]$AllowLegacyCsv
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
        "-m", "caduti_fonti_report.person_profiles",
        "--csv", $Csv,
        "--output-dir", $OutputDir,
        "--limit", "$Limit"
    )
    if (-not [string]::IsNullOrWhiteSpace($Name)) {
        $argsList += @("--name", $Name)
    }
    if ($AllowLegacyCsv) {
        $argsList += @("--allow-legacy-csv")
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
