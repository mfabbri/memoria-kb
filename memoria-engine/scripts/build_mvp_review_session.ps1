[CmdletBinding()]
param(
    [string]$SummaryJson = "",
    [string]$DigestJson = "",
    [string]$ReviewQueueJson = "",
    [string]$ReviewDecisionsSummaryJson = "",
    [string]$ConsolidatedLedgerJson = "",
    [string]$OutputJson = "",
    [string]$OutputMd = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$env:PYTHONPATH = Join-Path $repoRoot "code"
$pythonExe = if ($env:PYTHON) { $env:PYTHON } else { "python" }

if ([string]::IsNullOrWhiteSpace($SummaryJson)) {
    throw "Specificare -SummaryJson, per esempio risultati\runs\<run>\document_analysis\mvp_pilot_summary.json."
}
if ([string]::IsNullOrWhiteSpace($DigestJson)) {
    throw "Specificare -DigestJson, per esempio risultati\runs\<run>\mvp_pilot_cards_digest.json."
}
if ([string]::IsNullOrWhiteSpace($ReviewQueueJson)) {
    throw "Specificare -ReviewQueueJson, per esempio risultati\runs\<run>\historian_review\review_queue.json."
}
if ([string]::IsNullOrWhiteSpace($ReviewDecisionsSummaryJson)) {
    throw "Specificare -ReviewDecisionsSummaryJson, per esempio risultati\runs\<run>\historian_review\review_decisions_summary.json."
}

$argsList = @(
    "-m", "caduti_fonti_report.document_analysis.mvp_review_session",
    "--summary-json", $SummaryJson,
    "--digest-json", $DigestJson,
    "--review-queue-json", $ReviewQueueJson,
    "--review-decisions-summary-json", $ReviewDecisionsSummaryJson
)
if (-not [string]::IsNullOrWhiteSpace($ConsolidatedLedgerJson)) {
    $argsList += @("--consolidated-ledger-json", $ConsolidatedLedgerJson)
}
if (-not [string]::IsNullOrWhiteSpace($OutputJson)) {
    $argsList += @("--output-json", $OutputJson)
}
if (-not [string]::IsNullOrWhiteSpace($OutputMd)) {
    $argsList += @("--output-md", $OutputMd)
}

& $pythonExe @argsList
exit $LASTEXITCODE
