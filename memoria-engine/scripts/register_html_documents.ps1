[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RootDir,
    [Parameter(Mandatory = $true)]
    [string]$SourceId,
    [string]$BaseUrl = "",
    [string]$AccessDate = "",
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
        "-m", "caduti_fonti_report.document_analysis.html_registration",
        "--root-dir", $RootDir,
        "--source-id", $SourceId,
        "--review-status", $ReviewStatus
    )
    if (-not [string]::IsNullOrWhiteSpace($BaseUrl)) {
        $argsList += @("--base-url", $BaseUrl)
    }
    if (-not [string]::IsNullOrWhiteSpace($AccessDate)) {
        $argsList += @("--access-date", $AccessDate)
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
