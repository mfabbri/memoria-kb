[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$File,
    [string]$Sidecar = "",
    [string]$RootDir = "data\raw",
    [string]$OutputDir = "data\processed\documents",
    [string]$Language = "ita",
    [string]$TesseractPath = "tesseract",
    [string]$PageSegmentationMode = "",
    [string]$EngineMode = "",
    [string]$Dpi = "",
    [switch]$PreprocessBeforeOcr,
    [switch]$EnableRegionOcr,
    [string]$ReviewStatus = "unreviewed",
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
        "-m", "caduti_fonti_report.document_analysis.ocr_tesseract",
        "--file", $File,
        "--root-dir", $RootDir,
        "--output-dir", $OutputDir,
        "--language", $Language,
        "--tesseract-path", $TesseractPath,
        "--review-status", $ReviewStatus
    )
    if (-not [string]::IsNullOrWhiteSpace($PageSegmentationMode)) {
        $argsList += @("--psm", $PageSegmentationMode)
    }
    if (-not [string]::IsNullOrWhiteSpace($EngineMode)) {
        $argsList += @("--oem", $EngineMode)
    }
    if (-not [string]::IsNullOrWhiteSpace($Dpi)) {
        $argsList += @("--dpi", $Dpi)
    }
    if ($PreprocessBeforeOcr) {
        $argsList += "--preprocess-before-ocr"
    }
    if ($EnableRegionOcr) {
        $argsList += "--enable-region-ocr"
    }
    if (-not [string]::IsNullOrWhiteSpace($Sidecar)) {
        $argsList += @("--sidecar", $Sidecar)
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
