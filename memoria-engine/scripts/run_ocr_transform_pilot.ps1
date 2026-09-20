[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$InputTiff,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [Parameter(Mandatory = $true)]
    [string]$Language,
    [Parameter(Mandatory = $true)]
    [string]$TextDetectionModelDir,
    [Parameter(Mandatory = $true)]
    [string]$TextDetectionModelName,
    [Parameter(Mandatory = $true)]
    [string]$TextRecognitionModelDir,
    [Parameter(Mandatory = $true)]
    [string]$TextRecognitionModelName,
    [string]$Device = "cpu",
    [switch]$EnableMkldnn,
    [int]$TextDetLimitSideLen = 8192,
    [ValidateSet("min", "max")]
    [string]$TextDetLimitType = "max",
    [int]$TileWidth = 1800,
    [int]$TileHeight = 1800,
    [int]$TileOverlap = 200
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($InputTiff.Count -ne 2) { throw "Il pilot T36 richiede esattamente due -InputTiff." }
if (Test-Path -LiteralPath $OutputDir) { throw "OutputDir deve essere una directory nuova: $OutputDir" }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$previousPythonPath = $env:PYTHONPATH
$codePath = Join-Path $repoRoot "code"
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($previousPythonPath)) { $codePath } else { "$codePath;$previousPythonPath" }
try {
    $argsList = @("-m", "caduti_fonti_report.document_analysis.ocr_transform_pilot",
        "--input-tiff", $InputTiff[0], "--input-tiff", $InputTiff[1], "--output-dir", $OutputDir, "--language", $Language,
        "--text-detection-model-dir", $TextDetectionModelDir, "--text-detection-model-name", $TextDetectionModelName,
        "--text-recognition-model-dir", $TextRecognitionModelDir, "--text-recognition-model-name", $TextRecognitionModelName,
        "--device", $Device, "--text-det-limit-side-len", "$TextDetLimitSideLen", "--text-det-limit-type", $TextDetLimitType,
        "--tile-width", "$TileWidth", "--tile-height", "$TileHeight", "--tile-overlap", "$TileOverlap")
    if ($EnableMkldnn) { $argsList += "--enable-mkldnn" }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally { $env:PYTHONPATH = $previousPythonPath }
