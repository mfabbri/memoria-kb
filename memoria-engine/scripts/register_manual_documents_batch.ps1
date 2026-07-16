[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RootDir,
    [Parameter(Mandatory = $true)]
    [string]$SourceId,
    [Parameter(Mandatory = $true)]
    [string]$ArchivalReference,
    [string]$AccessDate = "",
    [string]$TitleTemplate = "{filename}",
    [string]$ReviewStatus = "unreviewed",
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
        "-m", "caduti_fonti_report.document_analysis.manual_registration_batch",
        "--root-dir", $RootDir,
        "--source-id", $SourceId,
        "--archival-reference", $ArchivalReference,
        "--title-template", $TitleTemplate,
        "--review-status", $ReviewStatus,
        "--output-json", $OutputJson
    )
    if (-not [string]::IsNullOrWhiteSpace($AccessDate)) {
        $argsList += @("--access-date", $AccessDate)
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

