[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$NodeUrl,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [Parameter(Mandatory = $true)]
    [string]$ArchivalReference,
    [string]$TitlePrefix = "",
    [int]$StartPage = 1,
    [int]$MaxPages = 3,
    [switch]$DownloadOpisDelos,
    [int]$MaxDelos = 25,
    [int]$MaxPagesPerDelo = 0,
    [int]$MaxTotalPages = 100,
    [int]$Zoom = 7,
    [double]$DelaySeconds = 1.0,
    [Parameter(Mandatory = $true)]
    [string]$OutputJson,
    [string]$OutputMd = "",
    [switch]$Overwrite,
    [switch]$Headed
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
        "-m", "caduti_fonti_report.document_analysis.german_docs_downloader",
        "--node-url", $NodeUrl,
        "--output-dir", $OutputDir,
        "--archival-reference", $ArchivalReference,
        "--start-page", "$StartPage",
        "--max-pages", "$MaxPages",
        "--zoom", "$Zoom",
        "--delay-seconds", "$DelaySeconds",
        "--output-json", $OutputJson
    )
    if (-not [string]::IsNullOrWhiteSpace($TitlePrefix)) {
        $argsList += @("--title-prefix", $TitlePrefix)
    }
    if ($DownloadOpisDelos) {
        $argsList += @(
            "--download-opis-delos",
            "--max-delos", "$MaxDelos",
            "--max-pages-per-delo", "$MaxPagesPerDelo",
            "--max-total-pages", "$MaxTotalPages"
        )
    }
    if (-not [string]::IsNullOrWhiteSpace($OutputMd)) {
        $argsList += @("--output-md", $OutputMd)
    }
    if ($Overwrite) {
        $argsList += "--overwrite"
    }
    if ($Headed) {
        $argsList += "--headed"
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
