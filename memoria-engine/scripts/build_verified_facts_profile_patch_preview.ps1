[CmdletBinding()]
param(
    [string]$VerifiedFactsPreviewJson,
    [string[]]$ProfileId = @(),
    [string]$OutputJson,
    [string]$OutputMd,
    [int]$Limit = 0
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

if ([string]::IsNullOrWhiteSpace($VerifiedFactsPreviewJson)) {
    throw "Specificare -VerifiedFactsPreviewJson, per esempio P:\Comune\Me.Mo.Ri.a\risultati\runs\<run>\historian_review\verified_facts.preview.json."
}
if ([string]::IsNullOrWhiteSpace($OutputJson)) {
    throw "Specificare -OutputJson."
}
if ([string]::IsNullOrWhiteSpace($OutputMd)) {
    throw "Specificare -OutputMd."
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
        "-m", "caduti_fonti_report.document_analysis.verified_facts_profile_patch_preview",
        "--verified-facts-preview-json", $VerifiedFactsPreviewJson,
        "--output-json", $OutputJson,
        "--output-md", $OutputMd,
        "--limit", "$Limit"
    )
    foreach ($id in $ProfileId) {
        if (-not [string]::IsNullOrWhiteSpace($id)) {
            $argsList += @("--profile-id", $id)
        }
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
