[CmdletBinding()]
param(
    [string]$ReviewSessionJson = "",
    [string]$ReviewQueueJson = "",
    [string]$ReviewDecisionsSummaryJson = "",
    [string]$ConsolidatedLedgerJson = "",
    [string]$VerifiedFactsPreviewJson = "",
    [string]$ProfilePatchPreviewJson = "",
    [string]$ProfilePatchSandboxDir = "",
    [string]$OutputJson = "",
    [string]$OutputMd = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$env:PYTHONPATH = Join-Path $repoRoot "code"
$pythonExe = if ($env:PYTHON) { $env:PYTHON } else { "python" }

if ([string]::IsNullOrWhiteSpace($ReviewSessionJson)) {
    throw "Specificare -ReviewSessionJson, per esempio risultati\runs\<run>\historian_review\review_session.json."
}
if ([string]::IsNullOrWhiteSpace($ReviewQueueJson)) {
    throw "Specificare -ReviewQueueJson, per esempio risultati\runs\<run>\historian_review\review_queue.json."
}
if ([string]::IsNullOrWhiteSpace($ReviewDecisionsSummaryJson)) {
    throw "Specificare -ReviewDecisionsSummaryJson, per esempio risultati\runs\<run>\historian_review\review_decisions_summary.json."
}

$argsList = @(
    "-m", "caduti_fonti_report.document_analysis.mvp_review_dashboard",
    "--review-session-json", $ReviewSessionJson,
    "--review-queue-json", $ReviewQueueJson,
    "--review-decisions-summary-json", $ReviewDecisionsSummaryJson
)
if (-not [string]::IsNullOrWhiteSpace($ConsolidatedLedgerJson)) {
    $argsList += @("--consolidated-ledger-json", $ConsolidatedLedgerJson)
}
if (-not [string]::IsNullOrWhiteSpace($VerifiedFactsPreviewJson) -and (Test-Path -LiteralPath $VerifiedFactsPreviewJson -PathType Leaf)) {
    $argsList += @("--verified-facts-preview-json", $VerifiedFactsPreviewJson)
}
if (-not [string]::IsNullOrWhiteSpace($ProfilePatchPreviewJson) -and (Test-Path -LiteralPath $ProfilePatchPreviewJson -PathType Leaf)) {
    $argsList += @("--profile-patch-preview-json", $ProfilePatchPreviewJson)
}
if (-not [string]::IsNullOrWhiteSpace($ProfilePatchSandboxDir) -and (Test-Path -LiteralPath $ProfilePatchSandboxDir -PathType Container)) {
    $argsList += @("--profile-patch-sandbox-dir", $ProfilePatchSandboxDir)
}
if (-not [string]::IsNullOrWhiteSpace($OutputJson)) {
    $argsList += @("--output-json", $OutputJson)
}
if (-not [string]::IsNullOrWhiteSpace($OutputMd)) {
    $argsList += @("--output-md", $OutputMd)
}

& $pythonExe @argsList
exit $LASTEXITCODE
