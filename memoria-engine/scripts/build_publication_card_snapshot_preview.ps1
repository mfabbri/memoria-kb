[CmdletBinding()]
param(
    [string]$ModelCardsManifestJson,
    [string]$DatasetExportPreviewJson,
    [string]$OutputDir,
    [string[]]$ProfileId = @(),
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

if ([string]::IsNullOrWhiteSpace($ModelCardsManifestJson)) {
    throw "Specificare -ModelCardsManifestJson, per esempio risultati\runs\<run>\schede_modello\manifest.json."
}
if ([string]::IsNullOrWhiteSpace($DatasetExportPreviewJson)) {
    throw "Specificare -DatasetExportPreviewJson, per esempio risultati\runs\<run>\dataset_export.preview.json."
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    throw "Specificare -OutputDir, per esempio risultati\runs\<run>\publication_card_snapshots_preview."
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
        "-m", "caduti_fonti_report.document_analysis.publication_card_snapshot_preview",
        "--model-cards-manifest-json", $ModelCardsManifestJson,
        "--dataset-export-preview-json", $DatasetExportPreviewJson,
        "--output-dir", $OutputDir,
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
