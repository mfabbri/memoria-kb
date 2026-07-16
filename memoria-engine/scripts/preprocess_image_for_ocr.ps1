[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$File,
    [Parameter(Mandatory = $true)]
    [string]$OutputFile,
    [string]$MaskFile = "",
    [string]$ReportJson = "",
    [int]$MedianBackgroundSize = 31,
    [int]$AbsoluteDarkThreshold = 118,
    [int]$LocalContrastThreshold = 22,
    [int]$MedianCleanupSize = 3,
    [switch]$Overwrite
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
        "-m", "caduti_fonti_report.document_analysis.image_preprocessing",
        "--file", $File,
        "--output-file", $OutputFile,
        "--median-background-size", "$MedianBackgroundSize",
        "--absolute-dark-threshold", "$AbsoluteDarkThreshold",
        "--local-contrast-threshold", "$LocalContrastThreshold",
        "--median-cleanup-size", "$MedianCleanupSize"
    )
    if (-not [string]::IsNullOrWhiteSpace($MaskFile)) {
        $argsList += @("--mask-file", $MaskFile)
    }
    if (-not [string]::IsNullOrWhiteSpace($ReportJson)) {
        $argsList += @("--report-json", $ReportJson)
    }
    if ($Overwrite) {
        $argsList += "--overwrite"
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
