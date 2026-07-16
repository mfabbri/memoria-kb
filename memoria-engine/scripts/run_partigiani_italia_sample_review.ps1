[CmdletBinding()]
param(
    [string]$Name = "",
    [int]$Limit = 2,
    [string]$RunId = "",
    [switch]$RefreshAuthenticatedCache,
    [string]$OutputMd = "risultati/partigiani_italia_sample_review.md",
    [string]$OutputJson = "risultati/partigiani_italia_sample_review.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$reviewScript = Join-Path $scriptDir "run_evidence_connector_review.ps1"

if (-not (Test-Path $reviewScript)) {
    throw "Script non trovato: $reviewScript"
}

$extraArgs = @(
    "--source", "partigiani_italia",
    "--limit", $Limit.ToString(),
    "--output-md", $OutputMd,
    "--output-json", $OutputJson
)

if (-not [string]::IsNullOrWhiteSpace($Name)) {
    $extraArgs += @("--name", $Name)
}

if (-not [string]::IsNullOrWhiteSpace($RunId)) {
    $extraArgs += @("--run-id", $RunId)
}

if ($RefreshAuthenticatedCache.IsPresent) {
    $extraArgs += "--refresh-authenticated-cache"
}

& $reviewScript @extraArgs
exit $LASTEXITCODE
