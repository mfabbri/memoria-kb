[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RootDir,
    [string]$OutputDir = "data\processed\documents",
    [string]$Language = "ita",
    [string]$TesseractPath = "tesseract",
    [string]$PageSegmentationMode = "",
    [string]$EngineMode = "",
    [string]$Dpi = "",
    [switch]$PreprocessBeforeOcr,
    [switch]$EnableRegionOcr,
    [string]$ReviewStatus = "unreviewed",
    [int]$MaxWorkers = 2,
    [int]$ProgressEvery = 25,
    [string]$LogFile = "",
    [Parameter(Mandatory = $true)]
    [string]$OutputJson,
    [string]$OutputMd = "",
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
        "-m", "caduti_fonti_report.document_analysis.ocr_batch",
        "--root-dir", $RootDir,
        "--output-dir", $OutputDir,
        "--language", $Language,
        "--tesseract-path", $TesseractPath,
        "--review-status", $ReviewStatus,
        "--max-workers", $MaxWorkers,
        "--progress-every", $ProgressEvery,
        "--output-json", $OutputJson
    )
    if (-not [string]::IsNullOrWhiteSpace($LogFile)) {
        $argsList += @("--log-file", $LogFile)
    }
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
    if (-not [string]::IsNullOrWhiteSpace($OutputMd)) {
        $argsList += @("--output-md", $OutputMd)
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
