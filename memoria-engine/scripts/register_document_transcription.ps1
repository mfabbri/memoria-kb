[CmdletBinding()]
param(
    [string]$File = "",
    [string]$Sidecar = "",
    [string]$TextFile = "",
    [string]$Text = "",
    [string]$RootDir = "data\raw",
    [string]$OutputDir = "data\processed\documents",
    [ValidateSet("manual_transcription", "external_ocr_unreviewed")]
    [string]$TranscriptionMethod = "manual_transcription",
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
        "-m", "caduti_fonti_report.document_analysis.transcription_registration",
        "--root-dir", $RootDir,
        "--output-dir", $OutputDir,
        "--transcription-method", $TranscriptionMethod,
        "--review-status", $ReviewStatus
    )
    if (-not [string]::IsNullOrWhiteSpace($File)) {
        $argsList += @("--file", $File)
    }
    if (-not [string]::IsNullOrWhiteSpace($Sidecar)) {
        $argsList += @("--sidecar", $Sidecar)
    }
    if (-not [string]::IsNullOrWhiteSpace($TextFile)) {
        $argsList += @("--text-file", $TextFile)
    }
    if (-not [string]::IsNullOrWhiteSpace($Text)) {
        $argsList += @("--text", $Text)
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
