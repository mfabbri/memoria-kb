[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Area = "",
    [Parameter(Position = 1)]
    [string]$Command = "",
    [Parameter(Position = 2)]
    [string]$Item = "",
    [string]$WorkspaceRoot = "",
    [int]$Limit = 5,
    [string]$ProfileId = "",
    [string]$SubjectKind = "",
    [string]$SubjectId = "",
    [string]$SubjectLabel = "",
    [switch]$Auto,
    [switch]$Preview,
    [switch]$Sandbox,
    [switch]$Canonical,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($null -ne $RemainingArgs -and $RemainingArgs.Count -gt 0) {
    $unsupportedArgs = New-Object System.Collections.Generic.List[string]
    for ($i = 0; $i -lt $RemainingArgs.Count; $i += 1) {
        $arg = $RemainingArgs[$i]
        if ($arg -eq "--auto") {
            $Auto = $true
        } elseif ($arg -eq "--preview") {
            $Preview = $true
        } elseif ($arg -eq "--sandbox") {
            $Sandbox = $true
        } elseif ($arg -eq "--canonical") {
            $Canonical = $true
        } elseif ($arg -eq "--profile-id") {
            if (($i + 1) -ge $RemainingArgs.Count) {
                throw "Argomento --profile-id senza valore."
            }
            $ProfileId = [string]$RemainingArgs[$i + 1]
            $i += 1
        } elseif ($arg -eq "--subject-kind") {
            if (($i + 1) -ge $RemainingArgs.Count) {
                throw "Argomento --subject-kind senza valore."
            }
            $SubjectKind = [string]$RemainingArgs[$i + 1]
            $i += 1
        } elseif ($arg -eq "--subject-id") {
            if (($i + 1) -ge $RemainingArgs.Count) {
                throw "Argomento --subject-id senza valore."
            }
            $SubjectId = [string]$RemainingArgs[$i + 1]
            $i += 1
        } elseif ($arg -eq "--subject-label") {
            if (($i + 1) -ge $RemainingArgs.Count) {
                throw "Argomento --subject-label senza valore."
            }
            $SubjectLabel = [string]$RemainingArgs[$i + 1]
            $i += 1
        } else {
            $unsupportedArgs.Add($arg)
        }
    }
    if ($unsupportedArgs.Count -gt 0) {
        throw "Argomenti non supportati: $($unsupportedArgs -join ', ')"
    }
}
if ($Item -eq "--auto") {
    $Auto = $true
    $Item = ""
}
if ($Item -eq "--preview") {
    $Preview = $true
    $Item = ""
}
if ($Item -eq "--sandbox") {
    $Sandbox = $true
    $Item = ""
}
if ($Item -eq "--canonical") {
    $Canonical = $true
    $Item = ""
}

function Show-Usage {
    Write-Host "Me.Mo.Ria CLI"
    Write-Host ""
    Write-Host "Uso:"
    Write-Host "  .\scripts\memoria.ps1 review discover -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review status -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review start --auto -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review work -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review alternatives -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review alternatives -ProfileId <profile-id> -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review accept 1 -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review reject 1 -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review uncertain 1 -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review refresh -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review dashboard -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review dashboard show -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review targets dry-run -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review targets run --preview -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review store dry-run -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review store run --preview -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review dataset-export dry-run -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review dataset-export run --preview -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review dataset-export show -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review verified-facts dry-run -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review verified-facts run --preview -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review profile-patch dry-run -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review profile-patch run --preview -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review profile-patch apply --sandbox -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review profile-patch apply --sandbox -ProfileId <profile-id> -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 review profile-patch apply --canonical -ProfileId <profile-id> -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 consolidate discover -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 consolidate status -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 consolidate start --auto -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 consolidate dry-run -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 consolidate run --preview -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 consolidate profile-status dry-run -ProfileId <profile-id> -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 consolidate profile-status run --preview -ProfileId <profile-id> -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 sources online discover -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 sources online discover -SubjectKind place -SubjectId <place-id> -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 sources online start --auto -SubjectKind event -SubjectId <event-id> -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 sources online status -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 sources online start --auto -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 sources offline discover -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 sources offline status -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 sources offline start --auto -WorkspaceRoot <workspace>"
    Write-Host "  .\scripts\memoria.ps1 status -WorkspaceRoot <workspace>"
    Write-Host ""
    Write-Host "La CLI resta preview-only: non crea verified_facts e non modifica profili JSON-LD."
}

function Resolve-WorkspaceRoot {
    param([string]$Root)
    if ([string]::IsNullOrWhiteSpace($Root)) {
        $Root = "P:\Comune\Me.Mo.Ri.a"
    }
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "WorkspaceRoot non trovata: $Root"
    }
    return (Resolve-Path -LiteralPath $Root).Path
}

function Get-ActiveReviewSessionPath {
    param([string]$Root)
    return (Join-Path (Join-Path $Root "database") "memoria_review_session.active.json")
}

function Get-ActiveConsolidateSessionPath {
    param([string]$Root)
    return (Join-Path (Join-Path $Root "database") "memoria_consolidate_session.active.json")
}

function Get-ActiveSourcesOnlineSessionPath {
    param([string]$Root)
    return (Join-Path (Join-Path $Root "database") "memoria_sources_online_session.active.json")
}

function Read-JsonObject {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Write-JsonObject {
    param(
        [string]$Path,
        [object]$Payload
    )
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $json = $Payload | ConvertTo-Json -Depth 12
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $json, $utf8NoBom)
}

function Resolve-PythonExe {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        return $venvPython
    }
    return "python"
}

function Get-ListCount {
    param(
        [object]$Payload,
        [string[]]$Names
    )
    if ($null -eq $Payload) {
        return 0
    }
    foreach ($name in $Names) {
        if ($Payload.PSObject.Properties.Name -contains $name) {
            $value = $Payload.$name
            if ($null -eq $value) {
                return 0
            }
            if ($value -is [array]) {
                return $value.Count
            }
            return 1
        }
    }
    return 0
}

function Get-ObjectPropertyValue {
    param(
        [object]$Payload,
        [string]$Name,
        [object]$DefaultValue = $null
    )
    if ($null -eq $Payload) {
        return $DefaultValue
    }
    $property = $Payload.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) {
        return $DefaultValue
    }
    return $property.Value
}

function Get-ObjectPropertyText {
    param(
        [object]$Payload,
        [string]$Name,
        [string]$DefaultValue = ""
    )
    $value = Get-ObjectPropertyValue -Payload $Payload -Name $Name -DefaultValue $DefaultValue
    if ($null -eq $value) {
        return $DefaultValue
    }
    return [string]$value
}

function Get-ObjectPropertyInt {
    param(
        [object]$Payload,
        [string]$Name,
        [int]$DefaultValue = 0
    )
    $value = Get-ObjectPropertyValue -Payload $Payload -Name $Name -DefaultValue $DefaultValue
    $parsed = 0
    if ([int]::TryParse(([string]$value), [ref]$parsed)) {
        return $parsed
    }
    return $DefaultValue
}

function Test-SubstantiveDecision {
    param([object]$Decision)
    if ($null -eq $Decision) {
        return $false
    }
    $profileId = ""
    $documentId = ""
    $subjectKind = ""
    $selectedAction = ""
    $decisionStatus = ""
    if ($Decision.PSObject.Properties.Name -contains "profile_id") { $profileId = [string]$Decision.profile_id }
    if ($Decision.PSObject.Properties.Name -contains "source_document_id") { $documentId = [string]$Decision.source_document_id }
    if ($Decision.PSObject.Properties.Name -contains "subject_kind") { $subjectKind = [string]$Decision.subject_kind }
    if ($Decision.PSObject.Properties.Name -contains "selected_action") { $selectedAction = [string]$Decision.selected_action }
    if ($Decision.PSObject.Properties.Name -contains "decision_status") { $decisionStatus = [string]$Decision.decision_status }

    return (
        -not [string]::IsNullOrWhiteSpace($profileId) -and
        -not [string]::IsNullOrWhiteSpace($documentId) -and
        $subjectKind -ne "workflow" -and
        -not [string]::IsNullOrWhiteSpace($selectedAction) -and
        $selectedAction -ne "pending" -and
        $decisionStatus -in @("accepted", "reviewed", "approved")
    )
}

function Get-DecisionItems {
    param([object]$Payload)
    if ($null -eq $Payload) {
        return @()
    }
    foreach ($name in @("decisions", "provided_decisions")) {
        if ($Payload.PSObject.Properties.Name -contains $name) {
            $value = $Payload.$name
            if ($null -eq $value) {
                return @()
            }
            if ($value -is [array]) {
                return @($value)
            }
            return @($value)
        }
    }
    return @()
}

function Get-RunCandidate {
    param([System.IO.DirectoryInfo]$RunDir)
    $reviewDir = Join-Path $RunDir.FullName "historian_review"
    $sessionPath = Join-Path $reviewDir "review_session.json"
    $queuePath = Join-Path $reviewDir "review_queue.json"
    $decisionsPath = Join-Path $reviewDir "review_decisions_summary.json"
    $ledgerPath = Join-Path $RunDir.FullName "mvp_consolidated_review_ledger.json"

    $session = Read-JsonObject -Path $sessionPath
    $queue = Read-JsonObject -Path $queuePath
    $decisions = Read-JsonObject -Path $decisionsPath
    $ledger = Read-JsonObject -Path $ledgerPath

    $hasAnyReviewArtifact = (
        (Test-Path -LiteralPath $sessionPath -PathType Leaf) -or
        (Test-Path -LiteralPath $queuePath -PathType Leaf) -or
        (Test-Path -LiteralPath $decisionsPath -PathType Leaf) -or
        (Test-Path -LiteralPath $ledgerPath -PathType Leaf)
    )
    if (-not $hasAnyReviewArtifact) {
        return $null
    }

    $queueCount = Get-ListCount -Payload $queue -Names @("items", "review_items")
    $decisionItems = @(Get-DecisionItems -Payload $decisions)
    $decisionCount = $decisionItems.Count
    $historicalDecisionCount = 0
    foreach ($decision in $decisionItems) {
        if (Test-SubstantiveDecision -Decision $decision) {
            $historicalDecisionCount += 1
        }
    }
    $profileCount = Get-ListCount -Payload $ledger -Names @("profiles", "profile_records", "records")
    $sessionItemCount = Get-ListCount -Payload $session -Names @("items", "worklist", "focus_items")

    $score = 0
    if ($null -ne $session) { $score += 30 }
    if ($null -ne $queue) { $score += 20 }
    if ($null -ne $decisions) { $score += 20 }
    if ($null -ne $ledger) { $score += 15 }
    $score += [Math]::Min($queueCount, 20)
    $score += ([Math]::Min($historicalDecisionCount, 10) * 2)
    $score += [Math]::Min($profileCount, 10)
    $score += [Math]::Min($sessionItemCount, 10)

    $reasons = New-Object System.Collections.Generic.List[string]
    if ($null -ne $session) { $reasons.Add("review_session") }
    if ($null -ne $queue) { $reasons.Add("review_queue") }
    if ($null -ne $decisions) { $reasons.Add("decisioni") }
    if ($null -ne $ledger) { $reasons.Add("ledger") }
    if ($reasons.Count -eq 0) { $reasons.Add("artefatti review parziali") }

    [pscustomobject]@{
        RunId = $RunDir.Name
        RunDir = $RunDir.FullName
        Score = $score
        ProfileCount = $profileCount
        ReviewQueueCount = $queueCount
        DecisionCount = $decisionCount
        HistoricalDecisionCount = $historicalDecisionCount
        SessionItemCount = $sessionItemCount
        Reason = ($reasons -join " + ")
        ReviewSessionPath = $sessionPath
        ReviewQueuePath = $queuePath
        ReviewDecisionsPath = $decisionsPath
        LedgerPath = $ledgerPath
    }
}

function Get-RunCandidates {
    param([string]$Root)
    $runsRoot = Join-Path (Join-Path $Root "risultati") "runs"
    if (-not (Test-Path -LiteralPath $runsRoot -PathType Container)) {
        return @()
    }
    $candidates = New-Object System.Collections.Generic.List[object]
    foreach ($runDir in Get-ChildItem -LiteralPath $runsRoot -Directory) {
        $candidate = Get-RunCandidate -RunDir $runDir
        if ($null -ne $candidate) {
            $candidates.Add($candidate)
        }
    }
    return @($candidates | Sort-Object -Property @{ Expression = "Score"; Descending = $true }, @{ Expression = "RunId"; Descending = $false })
}

function Test-ReviewProfileFilter {
    param(
        [string]$ProfileId,
        [string]$RequestedProfileId
    )
    if ([string]::IsNullOrWhiteSpace($RequestedProfileId)) {
        return $true
    }
    if ([string]::IsNullOrWhiteSpace($ProfileId)) {
        return $false
    }
    return ($ProfileId.ToLowerInvariant().Contains($RequestedProfileId.ToLowerInvariant()))
}

function Add-ReviewProfileSummary {
    param(
        [System.Collections.Generic.List[object]]$Summaries,
        [hashtable]$Seen,
        [string]$ProfileId,
        [string]$CanonicalName,
        [string]$Source,
        [int]$ReviewItemCount,
        [int]$PendingDecisionCount,
        [int]$AcceptedDecisionCount,
        [int]$InvalidDecisionCount,
        [string]$NextAction,
        [string]$RequestedProfileId
    )
    if (-not (Test-ReviewProfileFilter -ProfileId $ProfileId -RequestedProfileId $RequestedProfileId)) {
        return
    }
    $key = $ProfileId
    if ([string]::IsNullOrWhiteSpace($key)) {
        $key = "__missing_profile_id_$($Summaries.Count)"
    }
    $key = $key.ToLowerInvariant()
    if ($Seen.ContainsKey($key)) {
        return
    }
    $Seen[$key] = $true
    if ([string]::IsNullOrWhiteSpace($CanonicalName)) {
        $CanonicalName = "profilo senza nome"
    }
    $Summaries.Add([pscustomobject]@{
        ProfileId = $ProfileId
        CanonicalName = $CanonicalName
        Source = $Source
        ReviewItemCount = $ReviewItemCount
        PendingDecisionCount = $PendingDecisionCount
        AcceptedDecisionCount = $AcceptedDecisionCount
        InvalidDecisionCount = $InvalidDecisionCount
        NextAction = $NextAction
    })
}

function Get-ReviewProfileSummaries {
    param(
        [object]$Candidate,
        [string]$RequestedProfileId
    )
    $session = Read-JsonObject -Path $Candidate.ReviewSessionPath
    $queue = Read-JsonObject -Path $Candidate.ReviewQueuePath
    $summaries = New-Object System.Collections.Generic.List[object]
    $seen = @{}

    if ($null -ne $session -and $session.PSObject.Properties.Name -contains "profiles") {
        foreach ($profile in @($session.profiles)) {
            Add-ReviewProfileSummary `
                -Summaries $summaries `
                -Seen $seen `
                -ProfileId (Get-ObjectPropertyText -Payload $profile -Name "profile_id") `
                -CanonicalName (Get-ObjectPropertyText -Payload $profile -Name "canonical_name") `
                -Source "review_session" `
                -ReviewItemCount (Get-ObjectPropertyInt -Payload $profile -Name "review_item_count") `
                -PendingDecisionCount (Get-ObjectPropertyInt -Payload $profile -Name "pending_decision_count") `
                -AcceptedDecisionCount (Get-ObjectPropertyInt -Payload $profile -Name "accepted_decision_count") `
                -InvalidDecisionCount (Get-ObjectPropertyInt -Payload $profile -Name "invalid_decision_count") `
                -NextAction (Get-ObjectPropertyText -Payload $profile -Name "next_action") `
                -RequestedProfileId $RequestedProfileId
        }
    }

    $reviewFocus = Get-ObjectPropertyValue -Payload $session -Name "review_focus"
    if ($null -ne $reviewFocus -and $reviewFocus.PSObject.Properties.Name -contains "profiles") {
        foreach ($profile in @($reviewFocus.profiles)) {
            $focusItemsValue = Get-ObjectPropertyValue -Payload $profile -Name "items"
            $focusItems = @()
            if ($null -ne $focusItemsValue) {
                $focusItems = @($focusItemsValue)
            }
            $pendingCount = 0
            foreach ($item in $focusItems) {
                $decisionStatus = Get-ObjectPropertyText -Payload $item -Name "decision_status"
                if ([string]::IsNullOrWhiteSpace($decisionStatus) -or $decisionStatus -in @("pending", "unreviewed", "draft")) {
                    $pendingCount += 1
                }
            }
            Add-ReviewProfileSummary `
                -Summaries $summaries `
                -Seen $seen `
                -ProfileId (Get-ObjectPropertyText -Payload $profile -Name "profile_id") `
                -CanonicalName (Get-ObjectPropertyText -Payload $profile -Name "canonical_name") `
                -Source "review_focus" `
                -ReviewItemCount $focusItems.Count `
                -PendingDecisionCount $pendingCount `
                -AcceptedDecisionCount 0 `
                -InvalidDecisionCount 0 `
                -NextAction "" `
                -RequestedProfileId $RequestedProfileId
        }
    }

    $queueItemsValue = Get-ObjectPropertyValue -Payload $queue -Name "items"
    $queueItems = @()
    if ($null -ne $queueItemsValue) {
        $queueItems = @($queueItemsValue)
    }
    if ($queueItems.Count -eq 0) {
        $reviewItemsValue = Get-ObjectPropertyValue -Payload $queue -Name "review_items"
        if ($null -ne $reviewItemsValue) {
            $queueItems = @($reviewItemsValue)
        }
    }
    $queueCounts = @{}
    foreach ($item in $queueItems) {
        $profileId = Get-ObjectPropertyText -Payload $item -Name "profile_id"
        if ([string]::IsNullOrWhiteSpace($profileId)) {
            continue
        }
        if (-not $queueCounts.ContainsKey($profileId)) {
            $queueCounts[$profileId] = 0
        }
        $queueCounts[$profileId] += 1
    }
    foreach ($profileId in $queueCounts.Keys) {
        Add-ReviewProfileSummary `
            -Summaries $summaries `
            -Seen $seen `
            -ProfileId $profileId `
            -CanonicalName "" `
            -Source "review_queue" `
            -ReviewItemCount ([int]$queueCounts[$profileId]) `
            -PendingDecisionCount ([int]$queueCounts[$profileId]) `
            -AcceptedDecisionCount 0 `
            -InvalidDecisionCount 0 `
            -NextAction "" `
            -RequestedProfileId $RequestedProfileId
    }

    return @($summaries.ToArray())
}

function Get-ReviewFocusWorklist {
    param([object]$SessionPayload)
    if ($null -eq $SessionPayload) {
        return @()
    }
    $reviewFocus = $null
    if ($SessionPayload.PSObject.Properties.Name -contains "review_focus") {
        $reviewFocus = $SessionPayload.review_focus
    }
    if ($null -eq $reviewFocus -or -not ($reviewFocus.PSObject.Properties.Name -contains "profiles")) {
        return @()
    }
    $items = New-Object System.Collections.Generic.List[object]
    $displayNumber = 1
    foreach ($profile in @($reviewFocus.profiles)) {
        $profileId = ""
        $profileLabel = ""
        if ($profile.PSObject.Properties.Name -contains "profile_id") { $profileId = [string]$profile.profile_id }
        if ($profile.PSObject.Properties.Name -contains "canonical_name") { $profileLabel = [string]$profile.canonical_name }
        if (-not ($profile.PSObject.Properties.Name -contains "items")) {
            continue
        }
        foreach ($item in @($profile.items)) {
            $items.Add([pscustomobject]@{
                display_number = $displayNumber
                item_id = if ($item.PSObject.Properties.Name -contains "item_id") { [string]$item.item_id } else { "" }
                source_item_id = if ($item.PSObject.Properties.Name -contains "source_item_id") { [string]$item.source_item_id } else { "" }
                profile_id = $profileId
                profile_label = $profileLabel
                subject_kind = if ($item.PSObject.Properties.Name -contains "subject_kind") { [string]$item.subject_kind } else { "" }
                item_type = if ($item.PSObject.Properties.Name -contains "item_type") { [string]$item.item_type } else { "" }
                question = if ($item.PSObject.Properties.Name -contains "question") { [string]$item.question } else { "" }
                source_document_id = if ($item.PSObject.Properties.Name -contains "source_document_id") { [string]$item.source_document_id } else { "" }
                raw_file = if ($item.PSObject.Properties.Name -contains "raw_file") { [string]$item.raw_file } else { "" }
                metadata_file = if ($item.PSObject.Properties.Name -contains "metadata_file") { [string]$item.metadata_file } else { "" }
                allowed_decisions = if ($item.PSObject.Properties.Name -contains "allowed_decisions") { @($item.allowed_decisions) } else { @() }
                selected_action = if ($item.PSObject.Properties.Name -contains "selected_action") { [string]$item.selected_action } else { "pending" }
                decision_status = if ($item.PSObject.Properties.Name -contains "decision_status") { [string]$item.decision_status } else { "pending" }
            })
            $displayNumber += 1
        }
    }
    return [object[]]$items.ToArray()
}

function Save-ActiveReviewSession {
    param(
        [string]$Root,
        [object]$Candidate
    )
    $reviewSessionPayload = Read-JsonObject -Path $Candidate.ReviewSessionPath
    $worklist = @(Get-ReviewFocusWorklist -SessionPayload $reviewSessionPayload)
    $createdAt = (Get-Date).ToUniversalTime().ToString("o")
    $sessionPath = Get-ActiveReviewSessionPath -Root $Root
    $session = [pscustomobject]@{
        "@type" = "MemoriaReviewSession"
        created_at = $createdAt
        updated_at = $createdAt
        preview_only = $true
        review_status = "unreviewed"
        publication_status = "not_publishable_without_human_review"
        selected_run_id = $Candidate.RunId
        selected_run_dir = $Candidate.RunDir
        discovery_score = $Candidate.Score
        discovery_reason = $Candidate.Reason
        review_session_json = $Candidate.ReviewSessionPath
        review_queue_json = $Candidate.ReviewQueuePath
        review_decisions_summary_json = $Candidate.ReviewDecisionsPath
        consolidated_ledger_json = $Candidate.LedgerPath
        worklist_item_count = $worklist.Count
        worklist = $worklist
        note = "Sessione operativa preview-only: non registra decisioni, non crea verified_facts e non modifica profili JSON-LD."
    }
    Write-JsonObject -Path $sessionPath -Payload $session
    return $session
}

function Get-ActiveReviewSession {
    param([string]$Root)
    $sessionPath = Get-ActiveReviewSessionPath -Root $Root
    return Read-JsonObject -Path $sessionPath
}

function Get-ReviewDashboardPaths {
    param([object]$Session)
    $reviewSessionJson = ""
    if ($Session.PSObject.Properties.Name -contains "review_session_json") {
        $reviewSessionJson = [string]$Session.review_session_json
    }
    if ([string]::IsNullOrWhiteSpace($reviewSessionJson)) {
        throw "La sessione attiva non contiene review_session_json."
    }
    $reviewDir = Split-Path -Parent $reviewSessionJson
    if ([string]::IsNullOrWhiteSpace($reviewDir)) {
        throw "Impossibile risolvere la cartella historian_review dalla sessione attiva."
    }
    return [pscustomobject]@{
        ReviewDir = $reviewDir
        OutputJson = Join-Path $reviewDir "review_dashboard.json"
        OutputMd = Join-Path $reviewDir "review_dashboard.md"
        VerifiedFactsPreviewJson = Join-Path $reviewDir "verified_facts.preview.json"
        ProfilePatchPreviewJson = Join-Path $reviewDir "profile_patch.preview.json"
        ProfilePatchSandboxDir = Join-Path $reviewDir "profile_patch_sandbox"
    }
}

function Show-NoReviewSessionMessage {
    param([string]$ResolvedRoot)
    Write-Host "Nessuna sessione review attiva."
    Write-Host "Avviare prima:"
    Write-Host "  .\scripts\memoria.ps1 review start --auto -WorkspaceRoot `"$ResolvedRoot`""
}

function Get-ReviewSessionProgress {
    param([object]$Session)
    $worklist = @()
    if ($null -ne $Session -and ($Session.PSObject.Properties.Name -contains "worklist") -and $null -ne $Session.worklist) {
        $worklist = @($Session.worklist)
    }
    $totalCount = $worklist.Count
    if (($Session.PSObject.Properties.Name -contains "worklist_item_count") -and $null -ne $Session.worklist_item_count) {
        $totalCount = [int]$Session.worklist_item_count
    }
    $decidedCount = 0
    foreach ($item in $worklist) {
        $selectedAction = ""
        $decisionStatus = ""
        if ($item.PSObject.Properties.Name -contains "selected_action") { $selectedAction = [string]$item.selected_action }
        if ($item.PSObject.Properties.Name -contains "decision_status") { $decisionStatus = [string]$item.decision_status }
        if (
            (-not [string]::IsNullOrWhiteSpace($selectedAction) -and $selectedAction -ne "pending") -or
            (-not [string]::IsNullOrWhiteSpace($decisionStatus) -and $decisionStatus -notin @("pending", "unreviewed", "draft"))
        ) {
            $decidedCount += 1
        }
    }
    $pendingCount = [Math]::Max(0, $totalCount - $decidedCount)
    [pscustomobject]@{
        TotalCount = $totalCount
        DecidedCount = $decidedCount
        PendingCount = $pendingCount
    }
}

function Get-SessionPathValue {
    param(
        [object]$Session,
        [string]$Name
    )
    if ($Session.PSObject.Properties.Name -contains $Name) {
        return [string]$Session.PSObject.Properties[$Name].Value
    }
    return ""
}

function Get-VerifiedFactsPreviewSpec {
    param(
        [string]$ResolvedRoot,
        [object]$Session
    )
    $selectedRunId = Get-SessionPathValue -Session $Session -Name "selected_run_id"
    if ([string]::IsNullOrWhiteSpace($selectedRunId)) {
        throw "La sessione attiva non contiene selected_run_id."
    }
    $reviewSessionJson = Get-SessionPathValue -Session $Session -Name "review_session_json"
    if ([string]::IsNullOrWhiteSpace($reviewSessionJson)) {
        throw "La sessione attiva non contiene review_session_json."
    }
    $reviewDir = Split-Path -Parent $reviewSessionJson
    if ([string]::IsNullOrWhiteSpace($reviewDir)) {
        throw "Impossibile risolvere la cartella historian_review dalla sessione attiva."
    }
    $evidenceDatabasePath = Join-Path (Join-Path $ResolvedRoot "database") "evidence.sqlite"
    if (-not (Test-Path -LiteralPath $evidenceDatabasePath -PathType Leaf)) {
        throw "Evidence DB non trovato per verified facts preview: $evidenceDatabasePath"
    }
    $wrapperPath = Join-Path $PSScriptRoot "build_verified_facts_preview.ps1"
    if (-not (Test-Path -LiteralPath $wrapperPath -PathType Leaf)) {
        throw "Wrapper verified facts preview non trovato: $wrapperPath"
    }
    return [pscustomobject]@{
        WrapperPath = $wrapperPath
        EvidenceDatabasePath = $evidenceDatabasePath
        EvidenceSourceRunId = $selectedRunId
        OutputJson = Join-Path $reviewDir "verified_facts.preview.json"
        OutputMd = Join-Path $reviewDir "verified_facts.preview.md"
    }
}

function Show-VerifiedFactsPreviewDryRun {
    param([string]$Root)
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $previewSpec = Get-VerifiedFactsPreviewSpec -ResolvedRoot $resolvedRoot -Session $session
    Write-Host "Me.Mo.Ria review verified-facts dry-run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $previewSpec.EvidenceSourceRunId)
    Write-Host ("Wrapper tecnico: {0}" -f $previewSpec.WrapperPath)
    Write-Host ("Evidence DB: {0}" -f $previewSpec.EvidenceDatabasePath)
    Write-Host ("Output JSON proposto: {0}" -f $previewSpec.OutputJson)
    Write-Host ("Output Markdown proposto: {0}" -f $previewSpec.OutputMd)
    Write-Host ""
    Write-Host "Comando tecnico preparato:"
    Write-Host ("  .\scripts\build_verified_facts_preview.ps1 ``")
    Write-Host ("    -EvidenceDatabasePath `"{0}`" ``" -f $previewSpec.EvidenceDatabasePath)
    Write-Host ("    -EvidenceSourceRunId `"{0}`" ``" -f $previewSpec.EvidenceSourceRunId)
    Write-Host ("    -OutputJson `"{0}`" ``" -f $previewSpec.OutputJson)
    Write-Host ("    -OutputMd `"{0}`"" -f $previewSpec.OutputMd)
    Write-Host ""
    Write-Host "Nota: dry-run testuale; non crea verified_facts canonici, non genera ProfilePatch e non modifica profili JSON-LD."
}

function Invoke-VerifiedFactsPreviewRun {
    param(
        [string]$Root,
        [switch]$PreviewOnly
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    if (-not $PreviewOnly) {
        Show-Usage
        throw "Per eseguire review verified-facts run usare --preview. Il comando non crea verified_facts canonici e non modifica profili JSON-LD."
    }
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $previewSpec = Get-VerifiedFactsPreviewSpec -ResolvedRoot $resolvedRoot -Session $session
    Write-Host "Me.Mo.Ria review verified-facts run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $previewSpec.EvidenceSourceRunId)
    Write-Host ("Output JSON preview: {0}" -f $previewSpec.OutputJson)
    Write-Host ("Output Markdown preview: {0}" -f $previewSpec.OutputMd)
    Write-Host ""
    & ([string]$previewSpec.WrapperPath) `
        -EvidenceDatabasePath ([string]$previewSpec.EvidenceDatabasePath) `
        -EvidenceSourceRunId ([string]$previewSpec.EvidenceSourceRunId) `
        -OutputJson ([string]$previewSpec.OutputJson) `
        -OutputMd ([string]$previewSpec.OutputMd)
    if ($LASTEXITCODE -ne 0) {
        throw "review verified-facts run --preview fallito con exit code $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "Verified facts preview generata."
    Write-Host "Nota: non crea verified_facts canonici, non genera ProfilePatch e non modifica profili JSON-LD."
}

function Get-HistoricalReviewTargetsSpec {
    param(
        [string]$ResolvedRoot,
        [object]$Session
    )
    $selectedRunId = Get-SessionPathValue -Session $Session -Name "selected_run_id"
    if ([string]::IsNullOrWhiteSpace($selectedRunId)) {
        throw "La sessione attiva non contiene selected_run_id."
    }
    $reviewQueueJson = Get-SessionPathValue -Session $Session -Name "review_queue_json"
    if ([string]::IsNullOrWhiteSpace($reviewQueueJson)) {
        throw "La sessione attiva non contiene review_queue_json."
    }
    $reviewSessionJson = Get-SessionPathValue -Session $Session -Name "review_session_json"
    $reviewDir = Split-Path -Parent $reviewQueueJson
    if ([string]::IsNullOrWhiteSpace($reviewDir)) {
        throw "Impossibile risolvere la cartella historian_review dalla review queue."
    }
    $evidenceDatabasePath = Join-Path (Join-Path $ResolvedRoot "database") "evidence.sqlite"
    $wrapperPath = Join-Path $PSScriptRoot "build_mvp_historical_review_targets.ps1"
    if (-not (Test-Path -LiteralPath $wrapperPath -PathType Leaf)) {
        throw "Wrapper target storici non trovato: $wrapperPath"
    }
    $usesEvidenceStore = Test-Path -LiteralPath $evidenceDatabasePath -PathType Leaf
    return [pscustomobject]@{
        WrapperPath = $wrapperPath
        EvidenceDatabasePath = $evidenceDatabasePath
        EvidenceSourceRunId = $selectedRunId
        UsesEvidenceStore = $usesEvidenceStore
        ReviewQueueJson = $reviewQueueJson
        ReviewSessionJson = $reviewSessionJson
        OutputJson = Join-Path $reviewDir "historical_review_targets.store_first.json"
        OutputMd = Join-Path $reviewDir "historical_review_targets.store_first.md"
    }
}

function Show-HistoricalReviewTargetsDryRun {
    param([string]$Root)
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $targetsSpec = Get-HistoricalReviewTargetsSpec -ResolvedRoot $resolvedRoot -Session $session
    Write-Host "Me.Mo.Ria review targets dry-run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $targetsSpec.EvidenceSourceRunId)
    Write-Host ("Wrapper tecnico: {0}" -f $targetsSpec.WrapperPath)
    Write-Host ("Review queue: {0}" -f $targetsSpec.ReviewQueueJson)
    Write-Host ("Review session: {0}" -f $targetsSpec.ReviewSessionJson)
    if ($targetsSpec.UsesEvidenceStore) {
        Write-Host ("Evidence DB: {0}" -f $targetsSpec.EvidenceDatabasePath)
        Write-Host "Modalita sorgente proposta: evidence_store"
    } else {
        Write-Host "Evidence DB: non disponibile; fallback a review_queue"
        Write-Host "Modalita sorgente proposta: review_queue"
    }
    Write-Host ("Output JSON proposto: {0}" -f $targetsSpec.OutputJson)
    Write-Host ("Output Markdown proposto: {0}" -f $targetsSpec.OutputMd)
    Write-Host ""
    Write-Host "Comando tecnico preparato:"
    Write-Host ("  .\scripts\build_mvp_historical_review_targets.ps1 ``")
    if ($targetsSpec.UsesEvidenceStore) {
        Write-Host ("    -EvidenceDatabasePath `"{0}`" ``" -f $targetsSpec.EvidenceDatabasePath)
        Write-Host ("    -EvidenceSourceRunId `"{0}`" ``" -f $targetsSpec.EvidenceSourceRunId)
    } else {
        Write-Host ("    -ReviewQueueJson `"{0}`" ``" -f $targetsSpec.ReviewQueueJson)
    }
    if (-not [string]::IsNullOrWhiteSpace($targetsSpec.ReviewSessionJson)) {
        Write-Host ("    -ReviewSessionJson `"{0}`" ``" -f $targetsSpec.ReviewSessionJson)
    }
    Write-Host ("    -OutputJson `"{0}`" ``" -f $targetsSpec.OutputJson)
    Write-Host ("    -OutputMd `"{0}`"" -f $targetsSpec.OutputMd)
    Write-Host ""
    Write-Host "Nota: dry-run testuale; non crea decisioni storiche, verified_facts, ProfilePatch o modifiche ai profili JSON-LD."
}

function Invoke-HistoricalReviewTargetsRun {
    param(
        [string]$Root,
        [switch]$PreviewOnly
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    if (-not $PreviewOnly) {
        Show-Usage
        throw "Per eseguire review targets run usare --preview. Il comando genera solo target storici preview e non modifica profili JSON-LD."
    }
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $targetsSpec = Get-HistoricalReviewTargetsSpec -ResolvedRoot $resolvedRoot -Session $session
    Write-Host "Me.Mo.Ria review targets run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $targetsSpec.EvidenceSourceRunId)
    if ($targetsSpec.UsesEvidenceStore) {
        Write-Host "Sorgente: evidence_store"
        Write-Host ("Evidence DB: {0}" -f $targetsSpec.EvidenceDatabasePath)
    } else {
        Write-Host "Sorgente: review_queue"
        Write-Host ("Review queue: {0}" -f $targetsSpec.ReviewQueueJson)
    }
    Write-Host ("Output JSON preview: {0}" -f $targetsSpec.OutputJson)
    Write-Host ("Output Markdown preview: {0}" -f $targetsSpec.OutputMd)
    Write-Host ""
    if ($targetsSpec.UsesEvidenceStore) {
        & ([string]$targetsSpec.WrapperPath) `
            -EvidenceDatabasePath ([string]$targetsSpec.EvidenceDatabasePath) `
            -EvidenceSourceRunId ([string]$targetsSpec.EvidenceSourceRunId) `
            -ReviewSessionJson ([string]$targetsSpec.ReviewSessionJson) `
            -OutputJson ([string]$targetsSpec.OutputJson) `
            -OutputMd ([string]$targetsSpec.OutputMd)
    } else {
        & ([string]$targetsSpec.WrapperPath) `
            -ReviewQueueJson ([string]$targetsSpec.ReviewQueueJson) `
            -ReviewSessionJson ([string]$targetsSpec.ReviewSessionJson) `
            -OutputJson ([string]$targetsSpec.OutputJson) `
            -OutputMd ([string]$targetsSpec.OutputMd)
    }
    if ($LASTEXITCODE -ne 0) {
        throw "review targets run --preview fallito con exit code $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "Target storici preview generati."
    Write-Host "Nota: non crea decisioni storiche, verified_facts, ProfilePatch o modifiche ai profili JSON-LD."
}

function Get-ReviewStorePreviewSpec {
    param(
        [string]$ResolvedRoot,
        [object]$Session
    )
    $selectedRunId = Get-SessionPathValue -Session $Session -Name "selected_run_id"
    if ([string]::IsNullOrWhiteSpace($selectedRunId)) {
        throw "La sessione attiva non contiene selected_run_id."
    }
    $reviewQueueJson = Get-SessionPathValue -Session $Session -Name "review_queue_json"
    if ([string]::IsNullOrWhiteSpace($reviewQueueJson)) {
        throw "La sessione attiva non contiene review_queue_json."
    }
    $reviewDir = Split-Path -Parent $reviewQueueJson
    if ([string]::IsNullOrWhiteSpace($reviewDir)) {
        throw "Impossibile risolvere la cartella historian_review dalla review queue."
    }
    $evidenceDatabasePath = Join-Path (Join-Path $ResolvedRoot "database") "evidence.sqlite"
    $registerWrapperPath = Join-Path $PSScriptRoot "build_review_decision_conflict_register_preview.ps1"
    $storeWrapperPath = Join-Path $PSScriptRoot "build_review_store_preview.ps1"
    if (-not (Test-Path -LiteralPath $registerWrapperPath -PathType Leaf)) {
        throw "Wrapper registro decisioni/conflitti non trovato: $registerWrapperPath"
    }
    if (-not (Test-Path -LiteralPath $storeWrapperPath -PathType Leaf)) {
        throw "Wrapper review store preview non trovato: $storeWrapperPath"
    }
    return [pscustomobject]@{
        RegisterWrapperPath = $registerWrapperPath
        StoreWrapperPath = $storeWrapperPath
        EvidenceDatabasePath = $evidenceDatabasePath
        EvidenceSourceRunId = $selectedRunId
        ReviewDir = $reviewDir
        RegisterJson = Join-Path $reviewDir "review_decision_conflict_register.preview.json"
        RegisterMd = Join-Path $reviewDir "review_decision_conflict_register.preview.md"
        StoreJson = Join-Path $reviewDir "review_store.preview.json"
        StoreMd = Join-Path $reviewDir "review_store.preview.md"
    }
}

function Show-ReviewStorePreviewDryRun {
    param([string]$Root)
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $storeSpec = Get-ReviewStorePreviewSpec -ResolvedRoot $resolvedRoot -Session $session
    Write-Host "Me.Mo.Ria review store dry-run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $storeSpec.EvidenceSourceRunId)
    Write-Host ("Evidence DB: {0}" -f $storeSpec.EvidenceDatabasePath)
    if (Test-Path -LiteralPath $storeSpec.EvidenceDatabasePath -PathType Leaf) {
        Write-Host "Sorgente proposta: evidence_store"
    } else {
        Write-Host "Sorgente proposta: evidence_store non disponibile"
    }
    Write-Host ("Wrapper registro: {0}" -f $storeSpec.RegisterWrapperPath)
    Write-Host ("Wrapper store: {0}" -f $storeSpec.StoreWrapperPath)
    Write-Host ("Registro JSON proposto: {0}" -f $storeSpec.RegisterJson)
    Write-Host ("Registro Markdown proposto: {0}" -f $storeSpec.RegisterMd)
    Write-Host ("Store JSON proposto: {0}" -f $storeSpec.StoreJson)
    Write-Host ("Store Markdown proposto: {0}" -f $storeSpec.StoreMd)
    Write-Host ""
    Write-Host "Comandi tecnici preparati:"
    Write-Host ("  .\scripts\build_review_decision_conflict_register_preview.ps1 ``")
    Write-Host ("    -EvidenceDatabasePath `"{0}`" ``" -f $storeSpec.EvidenceDatabasePath)
    Write-Host ("    -EvidenceSourceRunId `"{0}`" ``" -f $storeSpec.EvidenceSourceRunId)
    Write-Host ("    -OutputJson `"{0}`" ``" -f $storeSpec.RegisterJson)
    Write-Host ("    -OutputMd `"{0}`"" -f $storeSpec.RegisterMd)
    Write-Host ("  .\scripts\build_review_store_preview.ps1 ``")
    Write-Host ("    -ReviewRegisterJson `"{0}`" ``" -f $storeSpec.RegisterJson)
    Write-Host ("    -EvidenceDatabasePath `"{0}`" ``" -f $storeSpec.EvidenceDatabasePath)
    Write-Host ("    -EvidenceSourceRunId `"{0}`" ``" -f $storeSpec.EvidenceSourceRunId)
    Write-Host ("    -OutputJson `"{0}`" ``" -f $storeSpec.StoreJson)
    Write-Host ("    -OutputMd `"{0}`"" -f $storeSpec.StoreMd)
    Write-Host ""
    Write-Host "Nota: dry-run testuale; non crea decisioni canoniche, verified_facts, ProfilePatch o modifiche ai profili JSON-LD."
}

function Invoke-ReviewStorePreviewRun {
    param(
        [string]$Root,
        [switch]$PreviewOnly
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    if (-not $PreviewOnly) {
        Show-Usage
        throw "Per eseguire review store run usare --preview. Il comando genera solo preview read-only e non modifica profili JSON-LD."
    }
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $storeSpec = Get-ReviewStorePreviewSpec -ResolvedRoot $resolvedRoot -Session $session
    if (-not (Test-Path -LiteralPath $storeSpec.EvidenceDatabasePath -PathType Leaf)) {
        throw "Evidence DB non disponibile per review store preview: $($storeSpec.EvidenceDatabasePath). Eseguire prima un import nello store."
    }
    Write-Host "Me.Mo.Ria review store run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $storeSpec.EvidenceSourceRunId)
    Write-Host ("Evidence DB: {0}" -f $storeSpec.EvidenceDatabasePath)
    Write-Host ("Registro JSON preview: {0}" -f $storeSpec.RegisterJson)
    Write-Host ("Store JSON preview: {0}" -f $storeSpec.StoreJson)
    Write-Host ""
    & ([string]$storeSpec.RegisterWrapperPath) `
        -EvidenceDatabasePath ([string]$storeSpec.EvidenceDatabasePath) `
        -EvidenceSourceRunId ([string]$storeSpec.EvidenceSourceRunId) `
        -OutputJson ([string]$storeSpec.RegisterJson) `
        -OutputMd ([string]$storeSpec.RegisterMd)
    if ($LASTEXITCODE -ne 0) {
        throw "review store run --preview fallito nella generazione del registro con exit code $LASTEXITCODE."
    }
    & ([string]$storeSpec.StoreWrapperPath) `
        -ReviewRegisterJson ([string]$storeSpec.RegisterJson) `
        -EvidenceDatabasePath ([string]$storeSpec.EvidenceDatabasePath) `
        -EvidenceSourceRunId ([string]$storeSpec.EvidenceSourceRunId) `
        -OutputJson ([string]$storeSpec.StoreJson) `
        -OutputMd ([string]$storeSpec.StoreMd)
    if ($LASTEXITCODE -ne 0) {
        throw "review store run --preview fallito nella generazione della store preview con exit code $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "Review store preview generata."
    Write-Host "Nota: non crea decisioni canoniche, verified_facts, ProfilePatch o modifiche ai profili JSON-LD."
}

function Get-DatasetExportPreviewSpec {
    param(
        [string]$ResolvedRoot,
        [object]$Session,
        [string]$RequestedProfileId
    )
    $selectedRunId = Get-SessionPathValue -Session $Session -Name "selected_run_id"
    if ([string]::IsNullOrWhiteSpace($selectedRunId)) {
        throw "La sessione attiva non contiene selected_run_id."
    }
    $reviewSessionJson = Get-SessionPathValue -Session $Session -Name "review_session_json"
    if ([string]::IsNullOrWhiteSpace($reviewSessionJson)) {
        $reviewSessionJson = Get-SessionPathValue -Session $Session -Name "review_queue_json"
    }
    if ([string]::IsNullOrWhiteSpace($reviewSessionJson)) {
        throw "La sessione attiva non contiene review_session_json o review_queue_json."
    }
    $reviewDir = Split-Path -Parent $reviewSessionJson
    if ([string]::IsNullOrWhiteSpace($reviewDir)) {
        throw "Impossibile risolvere la cartella historian_review dalla sessione attiva."
    }
    $evidenceDatabasePath = Join-Path (Join-Path $ResolvedRoot "database") "evidence.sqlite"
    $wrapperPath = Join-Path $PSScriptRoot "build_dataset_export_preview.ps1"
    if (-not (Test-Path -LiteralPath $wrapperPath -PathType Leaf)) {
        throw "Wrapper dataset export preview non trovato: $wrapperPath"
    }
    $verifiedFactsPreviewJson = Join-Path $reviewDir "verified_facts.preview.json"
    $profilePatchPreviewJson = Join-Path $reviewDir "profile_patch.preview.json"
    return [pscustomobject]@{
        WrapperPath = $wrapperPath
        EvidenceDatabasePath = $evidenceDatabasePath
        EvidenceSourceRunId = $selectedRunId
        ProfileId = $RequestedProfileId
        VerifiedFactsPreviewJson = $verifiedFactsPreviewJson
        ProfilePatchPreviewJson = $profilePatchPreviewJson
        OutputJson = Join-Path $reviewDir "dataset_export.preview.json"
        OutputMd = Join-Path $reviewDir "dataset_export.preview.md"
    }
}

function Show-DatasetExportPreviewDryRun {
    param(
        [string]$Root,
        [string]$RequestedProfileId
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $exportSpec = Get-DatasetExportPreviewSpec -ResolvedRoot $resolvedRoot -Session $session -RequestedProfileId $RequestedProfileId
    Write-Host "Me.Mo.Ria review dataset-export dry-run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $exportSpec.EvidenceSourceRunId)
    Write-Host ("Evidence DB: {0}" -f $exportSpec.EvidenceDatabasePath)
    if (-not [string]::IsNullOrWhiteSpace($exportSpec.ProfileId)) {
        Write-Host ("ProfileId: {0}" -f $exportSpec.ProfileId)
    }
    if (Test-Path -LiteralPath $exportSpec.VerifiedFactsPreviewJson -PathType Leaf) {
        Write-Host ("Verified facts preview: {0}" -f $exportSpec.VerifiedFactsPreviewJson)
    } else {
        Write-Host "Verified facts preview: non disponibile"
    }
    if (Test-Path -LiteralPath $exportSpec.ProfilePatchPreviewJson -PathType Leaf) {
        Write-Host ("ProfilePatch preview: {0}" -f $exportSpec.ProfilePatchPreviewJson)
    } else {
        Write-Host "ProfilePatch preview: non disponibile"
    }
    Write-Host ("Wrapper tecnico: {0}" -f $exportSpec.WrapperPath)
    Write-Host ("Output JSON proposto: {0}" -f $exportSpec.OutputJson)
    Write-Host ("Output Markdown proposto: {0}" -f $exportSpec.OutputMd)
    Write-Host ""
    Write-Host "Comando tecnico preparato:"
    Write-Host ("  .\scripts\build_dataset_export_preview.ps1 ``")
    Write-Host ("    -EvidenceDatabasePath `"{0}`" ``" -f $exportSpec.EvidenceDatabasePath)
    Write-Host ("    -EvidenceSourceRunId `"{0}`" ``" -f $exportSpec.EvidenceSourceRunId)
    if (-not [string]::IsNullOrWhiteSpace($exportSpec.ProfileId)) {
        Write-Host ("    -ProfileId `"{0}`" ``" -f $exportSpec.ProfileId)
    }
    if (Test-Path -LiteralPath $exportSpec.VerifiedFactsPreviewJson -PathType Leaf) {
        Write-Host ("    -VerifiedFactsPreviewJson `"{0}`" ``" -f $exportSpec.VerifiedFactsPreviewJson)
    }
    if (Test-Path -LiteralPath $exportSpec.ProfilePatchPreviewJson -PathType Leaf) {
        Write-Host ("    -ProfilePatchPreviewJson `"{0}`" ``" -f $exportSpec.ProfilePatchPreviewJson)
    }
    Write-Host ("    -OutputJson `"{0}`" ``" -f $exportSpec.OutputJson)
    Write-Host ("    -OutputMd `"{0}`"" -f $exportSpec.OutputMd)
    Write-Host ""
    Write-Host "Nota: dry-run testuale; non crea dataset canonici, verified_facts canonici, ProfilePatch o modifiche ai profili JSON-LD."
}

function Invoke-DatasetExportPreviewRun {
    param(
        [string]$Root,
        [switch]$PreviewOnly,
        [string]$RequestedProfileId
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    if (-not $PreviewOnly) {
        Show-Usage
        throw "Per eseguire review dataset-export run usare --preview. Il comando genera solo preview read-only e non modifica profili JSON-LD."
    }
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $exportSpec = Get-DatasetExportPreviewSpec -ResolvedRoot $resolvedRoot -Session $session -RequestedProfileId $RequestedProfileId
    if (-not (Test-Path -LiteralPath $exportSpec.EvidenceDatabasePath -PathType Leaf)) {
        throw "Evidence DB non disponibile per dataset export preview: $($exportSpec.EvidenceDatabasePath). Eseguire prima un import nello store."
    }
    Write-Host "Me.Mo.Ria review dataset-export run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $exportSpec.EvidenceSourceRunId)
    Write-Host ("Evidence DB: {0}" -f $exportSpec.EvidenceDatabasePath)
    Write-Host ("Output JSON preview: {0}" -f $exportSpec.OutputJson)
    Write-Host ("Output Markdown preview: {0}" -f $exportSpec.OutputMd)
    Write-Host ""
    $datasetParams = @{
        EvidenceDatabasePath = [string]$exportSpec.EvidenceDatabasePath
        EvidenceSourceRunId = @([string]$exportSpec.EvidenceSourceRunId)
        OutputJson = [string]$exportSpec.OutputJson
        OutputMd = [string]$exportSpec.OutputMd
    }
    if (-not [string]::IsNullOrWhiteSpace($exportSpec.ProfileId)) {
        $datasetParams["ProfileId"] = @([string]$exportSpec.ProfileId)
    }
    if (Test-Path -LiteralPath $exportSpec.VerifiedFactsPreviewJson -PathType Leaf) {
        $datasetParams["VerifiedFactsPreviewJson"] = [string]$exportSpec.VerifiedFactsPreviewJson
    }
    if (Test-Path -LiteralPath $exportSpec.ProfilePatchPreviewJson -PathType Leaf) {
        $datasetParams["ProfilePatchPreviewJson"] = [string]$exportSpec.ProfilePatchPreviewJson
    }
    & ([string]$exportSpec.WrapperPath) @datasetParams
    if ($LASTEXITCODE -ne 0) {
        throw "review dataset-export run --preview fallito con exit code $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "Dataset export preview generata."
    Write-Host "Nota: non crea dataset canonici, verified_facts canonici, ProfilePatch o modifiche ai profili JSON-LD."
}

function Show-DatasetExportPreviewCompact {
    param(
        [string]$Root,
        [string]$RequestedProfileId
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $exportSpec = Get-DatasetExportPreviewSpec -ResolvedRoot $resolvedRoot -Session $session -RequestedProfileId $RequestedProfileId
    $missingCommand = ".\scripts\memoria.ps1 review dataset-export run --preview -WorkspaceRoot `"$resolvedRoot`""
    if (-not [string]::IsNullOrWhiteSpace($exportSpec.ProfileId)) {
        $missingCommand = ".\scripts\memoria.ps1 review dataset-export run --preview -ProfileId `"$($exportSpec.ProfileId)`" -WorkspaceRoot `"$resolvedRoot`""
    }
    Write-Host "Me.Mo.Ria review dataset-export show"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ("Run attiva: {0}" -f $exportSpec.EvidenceSourceRunId)
    if (-not [string]::IsNullOrWhiteSpace($exportSpec.ProfileId)) {
        Write-Host ("ProfileId: {0}" -f $exportSpec.ProfileId)
    }
    Write-Host ""
    Show-MarkdownPreviewExcerpt `
        -Label "Dataset export preview" `
        -Path $exportSpec.OutputMd `
        -MissingCommand $missingCommand
    Write-Host "Nota: comando read-only; non crea dataset canonici, verified_facts canonici, ProfilePatch o modifiche ai profili JSON-LD."
}

function Get-ProfilePatchPreviewSpec {
    param(
        [string]$ResolvedRoot,
        [object]$Session
    )
    $selectedRunId = Get-SessionPathValue -Session $Session -Name "selected_run_id"
    if ([string]::IsNullOrWhiteSpace($selectedRunId)) {
        throw "La sessione attiva non contiene selected_run_id."
    }
    $reviewSessionJson = Get-SessionPathValue -Session $Session -Name "review_session_json"
    if ([string]::IsNullOrWhiteSpace($reviewSessionJson)) {
        throw "La sessione attiva non contiene review_session_json."
    }
    $reviewDir = Split-Path -Parent $reviewSessionJson
    if ([string]::IsNullOrWhiteSpace($reviewDir)) {
        throw "Impossibile risolvere la cartella historian_review dalla sessione attiva."
    }
    $verifiedFactsPreviewJson = Join-Path $reviewDir "verified_facts.preview.json"
    $wrapperPath = Join-Path $PSScriptRoot "build_verified_facts_profile_patch_preview.ps1"
    if (-not (Test-Path -LiteralPath $wrapperPath -PathType Leaf)) {
        throw "Wrapper ProfilePatch preview non trovato: $wrapperPath"
    }
    return [pscustomobject]@{
        WrapperPath = $wrapperPath
        EvidenceSourceRunId = $selectedRunId
        VerifiedFactsPreviewJson = $verifiedFactsPreviewJson
        OutputJson = Join-Path $reviewDir "profile_patch.preview.json"
        OutputMd = Join-Path $reviewDir "profile_patch.preview.md"
    }
}

function Show-MissingVerifiedFactsPreviewMessage {
    param(
        [string]$ResolvedRoot,
        [string]$Path
    )
    Write-Host "Verified facts preview non trovata: $Path"
    Write-Host "Generare prima:"
    Write-Host "  .\scripts\memoria.ps1 review verified-facts run --preview -WorkspaceRoot `"$ResolvedRoot`""
}

function Show-ProfilePatchPreviewDryRun {
    param([string]$Root)
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $previewSpec = Get-ProfilePatchPreviewSpec -ResolvedRoot $resolvedRoot -Session $session
    if (-not (Test-Path -LiteralPath $previewSpec.VerifiedFactsPreviewJson -PathType Leaf)) {
        Show-MissingVerifiedFactsPreviewMessage -ResolvedRoot $resolvedRoot -Path $previewSpec.VerifiedFactsPreviewJson
        return
    }
    Write-Host "Me.Mo.Ria review profile-patch dry-run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $previewSpec.EvidenceSourceRunId)
    Write-Host ("Wrapper tecnico: {0}" -f $previewSpec.WrapperPath)
    Write-Host ("Verified facts preview: {0}" -f $previewSpec.VerifiedFactsPreviewJson)
    Write-Host ("Output JSON proposto: {0}" -f $previewSpec.OutputJson)
    Write-Host ("Output Markdown proposto: {0}" -f $previewSpec.OutputMd)
    Write-Host ""
    Write-Host "Comando tecnico preparato:"
    Write-Host ("  .\scripts\build_verified_facts_profile_patch_preview.ps1 ``")
    Write-Host ("    -VerifiedFactsPreviewJson `"{0}`" ``" -f $previewSpec.VerifiedFactsPreviewJson)
    Write-Host ("    -OutputJson `"{0}`" ``" -f $previewSpec.OutputJson)
    Write-Host ("    -OutputMd `"{0}`"" -f $previewSpec.OutputMd)
    Write-Host ""
    Write-Host "Nota: dry-run testuale; non applica ProfilePatch, non modifica profili JSON-LD e non scrive nello store."
}

function Invoke-ProfilePatchPreviewRun {
    param(
        [string]$Root,
        [switch]$PreviewOnly
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    if (-not $PreviewOnly) {
        Show-Usage
        throw "Per eseguire review profile-patch run usare --preview. Il comando non applica ProfilePatch e non modifica profili JSON-LD."
    }
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $previewSpec = Get-ProfilePatchPreviewSpec -ResolvedRoot $resolvedRoot -Session $session
    if (-not (Test-Path -LiteralPath $previewSpec.VerifiedFactsPreviewJson -PathType Leaf)) {
        Show-MissingVerifiedFactsPreviewMessage -ResolvedRoot $resolvedRoot -Path $previewSpec.VerifiedFactsPreviewJson
        return
    }
    Write-Host "Me.Mo.Ria review profile-patch run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $previewSpec.EvidenceSourceRunId)
    Write-Host ("Input verified facts preview: {0}" -f $previewSpec.VerifiedFactsPreviewJson)
    Write-Host ("Output JSON preview: {0}" -f $previewSpec.OutputJson)
    Write-Host ("Output Markdown preview: {0}" -f $previewSpec.OutputMd)
    Write-Host ""
    & ([string]$previewSpec.WrapperPath) `
        -VerifiedFactsPreviewJson ([string]$previewSpec.VerifiedFactsPreviewJson) `
        -OutputJson ([string]$previewSpec.OutputJson) `
        -OutputMd ([string]$previewSpec.OutputMd)
    if ($LASTEXITCODE -ne 0) {
        throw "review profile-patch run --preview fallito con exit code $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "ProfilePatch preview generata."
    Write-Host "Nota: non applica ProfilePatch, non modifica profili JSON-LD e non scrive nello store."
}

function Get-ProfilePatchProfileIds {
    param([string]$ProfilePatchPreviewJson)
    $payload = Read-JsonObject -Path $ProfilePatchPreviewJson
    if ($null -eq $payload) {
        throw "ProfilePatch preview non leggibile: $ProfilePatchPreviewJson"
    }
    $patches = @()
    if (($payload.PSObject.Properties.Name -contains "@type") -and [string]$payload."@type" -eq "ProfilePatch") {
        $patches = @($payload)
    } elseif (($payload.PSObject.Properties.Name -contains "profile_patches") -and $null -ne $payload.profile_patches) {
        $patches = @($payload.profile_patches)
    }
    $profileIds = @(@(
        foreach ($patch in $patches) {
            if (($patch.PSObject.Properties.Name -contains "profile_id") -and -not [string]::IsNullOrWhiteSpace([string]$patch.profile_id)) {
                [string]$patch.profile_id
            }
        }
    ) | Select-Object -Unique)
    if ($profileIds.Count -eq 0) {
        throw "Nessuna ProfilePatch selezionabile in: $ProfilePatchPreviewJson"
    }
    return [string[]]$profileIds
}

function Resolve-ProfilePatchProfileId {
    param(
        [string]$ProfilePatchPreviewJson,
        [string]$RequestedProfileId
    )
    $profileIds = @(Get-ProfilePatchProfileIds -ProfilePatchPreviewJson $ProfilePatchPreviewJson)
    if (-not [string]::IsNullOrWhiteSpace($RequestedProfileId)) {
        if ($profileIds -notcontains $RequestedProfileId) {
            throw "ProfileId richiesto non presente nella ProfilePatch preview: $RequestedProfileId. Profili disponibili: $($profileIds -join ', ')"
        }
        return $RequestedProfileId
    }
    if ($profileIds.Count -gt 1) {
        throw "ProfilePatch preview contiene piu' profili. Rilanciare con -ProfileId <profile-id>. Profili disponibili: $($profileIds -join ', ')"
    }
    return [string]$profileIds[0]
}

function Invoke-ProfilePatchApply {
    param(
        [string]$Root,
        [switch]$SandboxOnly,
        [switch]$CanonicalOnly,
        [string]$RequestedProfileId = ""
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    if ($SandboxOnly -and $CanonicalOnly) {
        Show-Usage
        throw "Usare --sandbox oppure --canonical, non entrambi."
    }
    if (-not $SandboxOnly -and -not $CanonicalOnly) {
        Show-Usage
        throw "Per eseguire review profile-patch apply usare --sandbox oppure --canonical. L'apply canonico richiede anche -ProfileId."
    }
    if ($CanonicalOnly -and [string]::IsNullOrWhiteSpace($RequestedProfileId)) {
        Show-Usage
        throw "Per eseguire review profile-patch apply --canonical specificare -ProfileId <profile-id>."
    }
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoReviewSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $previewSpec = Get-ProfilePatchPreviewSpec -ResolvedRoot $resolvedRoot -Session $session
    if (-not (Test-Path -LiteralPath $previewSpec.OutputJson -PathType Leaf)) {
        Write-Host "ProfilePatch preview non trovata: $($previewSpec.OutputJson)"
        Write-Host "Generare prima:"
        Write-Host "  .\scripts\memoria.ps1 review profile-patch run --preview -WorkspaceRoot `"$resolvedRoot`""
        return
    }
    $profileId = Resolve-ProfilePatchProfileId -ProfilePatchPreviewJson $previewSpec.OutputJson -RequestedProfileId $RequestedProfileId
    $wrapperPath = Join-Path $PSScriptRoot "promote_profile_patch_preview.ps1"
    if (-not (Test-Path -LiteralPath $wrapperPath -PathType Leaf)) {
        throw "Wrapper promote ProfilePatch preview non trovato: $wrapperPath"
    }
    $outputDirName = if ($CanonicalOnly) { "profile_patch_apply" } else { "profile_patch_sandbox" }
    $modeLabel = if ($CanonicalOnly) { "canonical" } else { "sandbox" }
    $outputDir = Join-Path (Split-Path -Parent $previewSpec.OutputJson) $outputDirName
    Write-Host "Me.Mo.Ria review profile-patch apply"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: $modeLabel"
    Write-Host ""
    Write-Host ("Profile ID: {0}" -f $profileId)
    Write-Host ("ProfilePatch preview: {0}" -f $previewSpec.OutputJson)
    Write-Host ("Output sandbox: {0}" -f $outputDir)
    Write-Host ""
    if ($CanonicalOnly) {
        & $wrapperPath `
            -WorkspaceRoot ([string]$resolvedRoot) `
            -ProfilePatchPreviewJson ([string]$previewSpec.OutputJson) `
            -ProfileId ([string]$profileId) `
            -OutputDir ([string]$outputDir) `
            -Apply
    } else {
        & $wrapperPath `
            -WorkspaceRoot ([string]$resolvedRoot) `
            -ProfilePatchPreviewJson ([string]$previewSpec.OutputJson) `
            -ProfileId ([string]$profileId) `
            -OutputDir ([string]$outputDir) `
            -Sandbox
    }
    if ($LASTEXITCODE -ne 0) {
        throw "review profile-patch apply --sandbox fallito con exit code $LASTEXITCODE."
    }
    Write-Host ""
    if ($CanonicalOnly) {
        Write-Host "ProfilePatch applicata al profilo canonico."
        Write-Host "Nota: verificare backup e audit in profile_patch_apply."
    } else {
        Write-Host "ProfilePatch applicata in sandbox."
        Write-Host "Nota: profilo canonico non modificato; verificare audit e profilo derivato in profile_patch_sandbox."
    }
}

function Get-ReviewDecisionPaths {
    param([object]$Session)
    $reviewQueueJson = Get-SessionPathValue -Session $Session -Name "review_queue_json"
    if ([string]::IsNullOrWhiteSpace($reviewQueueJson)) {
        throw "La sessione attiva non contiene review_queue_json."
    }
    $reviewDir = Split-Path -Parent $reviewQueueJson
    if ([string]::IsNullOrWhiteSpace($reviewDir)) {
        throw "Impossibile risolvere la cartella historian_review dalla review queue."
    }
    return [pscustomobject]@{
        ReviewDir = $reviewDir
        ReviewQueueJson = $reviewQueueJson
        DecisionsTemplateJson = Join-Path $reviewDir "review_decisions.template.json"
        DecisionsCompiledJson = Join-Path $reviewDir "review_decisions.compilato.json"
        SummaryJson = Join-Path $reviewDir "review_decisions_summary.json"
        SummaryMd = Join-Path $reviewDir "review_decisions_summary.md"
    }
}

function Invoke-ReviewDashboardBuild {
    param(
        [object]$Session,
        [object]$DashboardPaths
    )
    $scriptDir = $PSScriptRoot
    $dashboardScript = Join-Path $scriptDir "build_mvp_review_dashboard.ps1"
    if (-not (Test-Path -LiteralPath $dashboardScript -PathType Leaf)) {
        throw "Wrapper dashboard non trovato: $dashboardScript"
    }

    $reviewSessionJson = Get-SessionPathValue -Session $Session -Name "review_session_json"
    $reviewQueueJson = Get-SessionPathValue -Session $Session -Name "review_queue_json"
    $reviewDecisionsSummaryJson = Get-SessionPathValue -Session $Session -Name "review_decisions_summary_json"
    $consolidatedLedgerJson = Get-SessionPathValue -Session $Session -Name "consolidated_ledger_json"
    foreach ($path in @($reviewSessionJson, $reviewQueueJson, $reviewDecisionsSummaryJson)) {
        if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Artefatto review mancante per refresh dashboard: $path"
        }
    }

    $dashboardParams = @{
        ReviewSessionJson = $reviewSessionJson
        ReviewQueueJson = $reviewQueueJson
        ReviewDecisionsSummaryJson = $reviewDecisionsSummaryJson
        OutputJson = [string]$DashboardPaths.OutputJson
        OutputMd = [string]$DashboardPaths.OutputMd
    }
    if (-not [string]::IsNullOrWhiteSpace($consolidatedLedgerJson) -and (Test-Path -LiteralPath $consolidatedLedgerJson -PathType Leaf)) {
        $dashboardParams["ConsolidatedLedgerJson"] = $consolidatedLedgerJson
    }
    if (Test-Path -LiteralPath $DashboardPaths.VerifiedFactsPreviewJson -PathType Leaf) {
        $dashboardParams["VerifiedFactsPreviewJson"] = [string]$DashboardPaths.VerifiedFactsPreviewJson
    }
    if (Test-Path -LiteralPath $DashboardPaths.ProfilePatchPreviewJson -PathType Leaf) {
        $dashboardParams["ProfilePatchPreviewJson"] = [string]$DashboardPaths.ProfilePatchPreviewJson
    }
    if (Test-Path -LiteralPath $DashboardPaths.ProfilePatchSandboxDir -PathType Container) {
        $dashboardParams["ProfilePatchSandboxDir"] = [string]$DashboardPaths.ProfilePatchSandboxDir
    }

    & $dashboardScript @dashboardParams
    if ($LASTEXITCODE -ne 0) {
        throw "Generazione review dashboard fallita con exit code $LASTEXITCODE."
    }
}

function Invoke-ReviewDecisionsSummary {
    param([object]$DecisionPaths)
    $repoRoot = Split-Path -Parent $PSScriptRoot
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
            "-m", "caduti_fonti_report.document_analysis.mvp_review_decisions",
            "--review-queue-json", [string]$DecisionPaths.ReviewQueueJson,
            "--decisions-json", [string]$DecisionPaths.DecisionsCompiledJson,
            "--output-json", [string]$DecisionPaths.SummaryJson,
            "--output-md", [string]$DecisionPaths.SummaryMd
        )
        & $pythonExe @argsList
        if ($LASTEXITCODE -ne 0) {
            throw "Riepilogo decisioni non valido. Exit code: $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
        $env:PYTHONPATH = $previousPythonPath
    }
}

function Get-StringList {
    param([object]$Value)
    if ($null -eq $Value) {
        return @()
    }
    $items = New-Object System.Collections.Generic.List[string]
    foreach ($entry in @($Value)) {
        $text = [string]$entry
        if (-not [string]::IsNullOrWhiteSpace($text)) {
            $items.Add($text.Trim())
        }
    }
    return [string[]]$items.ToArray()
}

function Find-WorklistItem {
    param(
        [object]$Session,
        [int]$DisplayNumber
    )
    foreach ($item in @($Session.worklist)) {
        if ([int]$item.display_number -eq $DisplayNumber) {
            return $item
        }
    }
    return $null
}

function Find-ReviewQueueItem {
    param(
        [object]$DecisionPaths,
        [string]$ItemId
    )
    $queue = Read-JsonObject -Path $DecisionPaths.ReviewQueueJson
    if ($null -eq $queue -or -not ($queue.PSObject.Properties.Name -contains "items")) {
        return $null
    }
    foreach ($queueItem in @($queue.items)) {
        if (($queueItem.PSObject.Properties.Name -contains "item_id") -and [string]$queueItem.item_id -eq $ItemId) {
            return $queueItem
        }
    }
    return $null
}

function Resolve-ReviewAction {
    param(
        [string]$CommandName,
        [string[]]$AllowedDecisions
    )
    if ($AllowedDecisions.Count -eq 0) {
        throw "Item senza allowed_decisions: impossibile registrare una decisione sicura."
    }
    if ($CommandName -eq "accept") {
        return $AllowedDecisions[0]
    }
    $preferredActions = @()
    if ($CommandName -eq "reject") {
        $preferredActions = @("reject_false_positive", "reject", "rejected")
    } elseif ($CommandName -eq "uncertain") {
        $preferredActions = @("uncertain")
    } else {
        throw "Comando decisionale non supportato: $CommandName"
    }
    foreach ($candidateAction in $preferredActions) {
        if ($AllowedDecisions -contains $candidateAction) {
            return $candidateAction
        }
    }
    throw ("L'item non ammette review {0}. Azioni ammesse: {1}" -f $CommandName, ($AllowedDecisions -join ", "))
}

function New-BlankDecisionsPayloadFromQueue {
    param([object]$DecisionPaths)
    $queue = Read-JsonObject -Path $DecisionPaths.ReviewQueueJson
    $decisions = New-Object System.Collections.Generic.List[object]
    if ($null -ne $queue -and ($queue.PSObject.Properties.Name -contains "items")) {
        foreach ($queueItem in @($queue.items)) {
            if ($queueItem.PSObject.Properties.Name -contains "item_id") {
                $decisions.Add([pscustomobject]@{
                    "@type" = "ReviewDecision"
                    item_id = [string]$queueItem.item_id
                    selected_action = ""
                    reviewer = ""
                    reviewed_at = ""
                    notes = ""
                })
            }
        }
    }
    return [pscustomobject]@{
        "@type" = "MvpReviewDecisions"
        decisions = [object[]]$decisions.ToArray()
    }
}

function Read-OrCreateDecisionsPayload {
    param([object]$DecisionPaths)
    if (Test-Path -LiteralPath $DecisionPaths.DecisionsCompiledJson -PathType Leaf) {
        return Read-JsonObject -Path $DecisionPaths.DecisionsCompiledJson
    }
    if (Test-Path -LiteralPath $DecisionPaths.DecisionsTemplateJson -PathType Leaf) {
        return Read-JsonObject -Path $DecisionPaths.DecisionsTemplateJson
    }
    return New-BlankDecisionsPayloadFromQueue -DecisionPaths $DecisionPaths
}

function Set-DecisionInPayload {
    param(
        [object]$Payload,
        [string]$ItemId,
        [string]$SelectedAction,
        [string]$ReviewedAt,
        [string]$CommandName
    )
    if ($null -eq $Payload) {
        $Payload = [pscustomobject]@{
            "@type" = "MvpReviewDecisions"
            decisions = @()
        }
    }
    if (-not ($Payload.PSObject.Properties.Name -contains "decisions") -or $null -eq $Payload.decisions) {
        Add-Member -InputObject $Payload -NotePropertyName "decisions" -NotePropertyValue @()
    }
    $decisions = New-Object System.Collections.Generic.List[object]
    $updated = $false
    foreach ($decision in @($Payload.decisions)) {
        if (($decision.PSObject.Properties.Name -contains "item_id") -and [string]$decision.item_id -eq $ItemId) {
            if ($decision.PSObject.Properties.Name -contains "selected_action") {
                $decision.selected_action = $SelectedAction
            } else {
                Add-Member -InputObject $decision -NotePropertyName "selected_action" -NotePropertyValue $SelectedAction
            }
            if ($decision.PSObject.Properties.Name -contains "reviewer") {
                $decision.reviewer = "memoria-cli"
            } else {
                Add-Member -InputObject $decision -NotePropertyName "reviewer" -NotePropertyValue "memoria-cli"
            }
            if ($decision.PSObject.Properties.Name -contains "reviewed_at") {
                $decision.reviewed_at = $ReviewedAt
            } else {
                Add-Member -InputObject $decision -NotePropertyName "reviewed_at" -NotePropertyValue $ReviewedAt
            }
            $note = "Decisione preview-only tramite Me.Mo.Ria CLI review $CommandName."
            if ($decision.PSObject.Properties.Name -contains "notes") {
                $decision.notes = $note
            } else {
                Add-Member -InputObject $decision -NotePropertyName "notes" -NotePropertyValue $note
            }
            $updated = $true
        }
        $decisions.Add($decision)
    }
    if (-not $updated) {
        $decisions.Add([pscustomobject]@{
            "@type" = "ReviewDecision"
            item_id = $ItemId
            selected_action = $SelectedAction
            reviewer = "memoria-cli"
            reviewed_at = $ReviewedAt
            notes = "Decisione preview-only tramite Me.Mo.Ria CLI review $CommandName."
        })
    }
    $Payload.decisions = [object[]]$decisions.ToArray()
    return $Payload
}

function Update-SessionDecisionState {
    param(
        [string]$Root,
        [object]$Session,
        [int]$DisplayNumber,
        [string]$ItemId,
        [string]$SelectedAction,
        [string]$ReviewedAt
    )
    foreach ($workItem in @($Session.worklist)) {
        if ([int]$workItem.display_number -eq $DisplayNumber) {
            $workItem.selected_action = $SelectedAction
            $workItem.decision_status = "accepted"
        }
    }
    $Session.updated_at = $ReviewedAt
    if ($Session.PSObject.Properties.Name -contains "last_decision_item_number") {
        $Session.last_decision_item_number = $DisplayNumber
    } else {
        Add-Member -InputObject $Session -NotePropertyName "last_decision_item_number" -NotePropertyValue $DisplayNumber
    }
    if ($Session.PSObject.Properties.Name -contains "last_decision_item_id") {
        $Session.last_decision_item_id = $ItemId
    } else {
        Add-Member -InputObject $Session -NotePropertyName "last_decision_item_id" -NotePropertyValue $ItemId
    }
    if ($Session.PSObject.Properties.Name -contains "last_selected_action") {
        $Session.last_selected_action = $SelectedAction
    } else {
        Add-Member -InputObject $Session -NotePropertyName "last_selected_action" -NotePropertyValue $SelectedAction
    }
    Write-JsonObject -Path (Get-ActiveReviewSessionPath -Root $Root) -Payload $Session
}

function Show-ReviewDiscovery {
    param(
        [string]$Root,
        [int]$MaxItems,
        [switch]$AsStart
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $candidates = @(Get-RunCandidates -Root $resolvedRoot)
    Write-Host "Me.Mo.Ria review discovery"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    if ($candidates.Count -eq 0) {
        Write-Host "Nessuna run review trovata in risultati\runs."
        return
    }
    $recommended = $candidates[0]
    if ($AsStart) {
        Write-Host "Run selezionata per start preview-only:"
    } else {
        Write-Host "Run consigliata:"
    }
    Write-Host ("[1] {0}" -f $recommended.RunId)
    Write-Host ("    Score: {0}" -f $recommended.Score)
    Write-Host ("    Motivo: {0}" -f $recommended.Reason)
    Write-Host ("    Review queue: {0}" -f $recommended.ReviewQueueCount)
    Write-Host ("    Decisioni: {0}" -f $recommended.DecisionCount)
    Write-Host ("    Decisioni storiche sostanziali: {0}" -f $recommended.HistoricalDecisionCount)
    Write-Host ("    Profili ledger: {0}" -f $recommended.ProfileCount)
    Write-Host ("    Path: {0}" -f $recommended.RunDir)
    Write-Host ""
    Write-Host "Candidate:"
    $index = 1
    foreach ($candidate in ($candidates | Select-Object -First $MaxItems)) {
        Write-Host ("[{0}] {1} | score={2} | queue={3} | decisioni={4} | motivo={5}" -f $index, $candidate.RunId, $candidate.Score, $candidate.ReviewQueueCount, $candidate.DecisionCount, $candidate.Reason)
        $index += 1
    }
    Write-Host ""
    Write-Host "Prossimi comandi:"
    Write-Host "  .\scripts\memoria.ps1 review status -WorkspaceRoot `"$resolvedRoot`""
    Write-Host "  .\scripts\memoria.ps1 review start --auto -WorkspaceRoot `"$resolvedRoot`""
    if ($AsStart) {
        Write-Host ""
        Write-Host "Nota: start --auto in questo slice non crea sessioni e non registra decisioni."
    }
}

function Show-ReviewAlternatives {
    param(
        [string]$Root,
        [int]$MaxItems,
        [string]$RequestedProfileId
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $candidates = @(Get-RunCandidates -Root $resolvedRoot)
    $activeSession = Get-ActiveReviewSession -Root $resolvedRoot

    Write-Host "Me.Mo.Ria review alternatives"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    if ($null -eq $activeSession) {
        Write-Host "Run attiva: non presente"
    } else {
        Write-Host ("Run attiva: {0}" -f $activeSession.selected_run_id)
    }
    if (-not [string]::IsNullOrWhiteSpace($RequestedProfileId)) {
        Write-Host ("Filtro ProfileId: {0}" -f $RequestedProfileId)
    }
    Write-Host ""

    if ($candidates.Count -eq 0) {
        Write-Host "Nessuna run review trovata in risultati\runs."
        return
    }

    Write-Host "Alternative review candidate:"
    $index = 1
    foreach ($candidate in ($candidates | Select-Object -First $MaxItems)) {
        $profiles = @(Get-ReviewProfileSummaries -Candidate $candidate -RequestedProfileId $RequestedProfileId)
        if (-not [string]::IsNullOrWhiteSpace($RequestedProfileId) -and $profiles.Count -eq 0) {
            continue
        }
        Write-Host ("[{0}] {1} | score={2} | queue={3} | decisioni={4} | decisioni_storiche={5}" -f $index, $candidate.RunId, $candidate.Score, $candidate.ReviewQueueCount, $candidate.DecisionCount, $candidate.HistoricalDecisionCount)
        Write-Host ("    Path: {0}" -f $candidate.RunDir)
        if ($profiles.Count -eq 0) {
            Write-Host "    Profili: non disponibili negli artefatti review"
        } else {
            foreach ($profile in ($profiles | Select-Object -First $MaxItems)) {
                Write-Host ("    Profile: {0}" -f $profile.CanonicalName)
                Write-Host ("      ProfileId: {0}" -f $profile.ProfileId)
                Write-Host ("      Item revisionabili: {0} | pendenti: {1} | accettati: {2} | invalidi: {3}" -f $profile.ReviewItemCount, $profile.PendingDecisionCount, $profile.AcceptedDecisionCount, $profile.InvalidDecisionCount)
                Write-Host ("      Sorgente riepilogo: {0}" -f $profile.Source)
                if (-not [string]::IsNullOrWhiteSpace([string]$profile.NextAction)) {
                    Write-Host ("      Prossima azione: {0}" -f $profile.NextAction)
                }
            }
            if ($profiles.Count -gt $MaxItems) {
                Write-Host ("    Altri profili omessi dal limite: {0}" -f ($profiles.Count - $MaxItems))
            }
        }
        $index += 1
    }

    if ($index -eq 1) {
        Write-Host "Nessuna alternativa compatibile con il filtro richiesto."
    }
    Write-Host ""
    Write-Host "Prossimi comandi:"
    Write-Host "  .\scripts\memoria.ps1 review discover -WorkspaceRoot `"$resolvedRoot`""
    Write-Host "  .\scripts\memoria.ps1 review work -WorkspaceRoot `"$resolvedRoot`""
    Write-Host ""
    Write-Host "Nota: comando read-only; non cambia run attiva, non registra decisioni e non crea verified_facts."
}

function Start-ReviewSession {
    param(
        [string]$Root,
        [int]$MaxItems
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $candidates = @(Get-RunCandidates -Root $resolvedRoot)
    Write-Host "Me.Mo.Ria review start"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    if ($candidates.Count -eq 0) {
        Write-Host "Nessuna run review trovata in risultati\runs."
        return
    }
    $recommended = $candidates[0]
    try {
        $session = Save-ActiveReviewSession -Root $resolvedRoot -Candidate $recommended
    } catch {
        Write-Error ("Impossibile creare la sessione review preview-only: {0}`n{1}" -f $_.Exception.Message, $_.ScriptStackTrace)
        exit 1
    }
    $sessionPath = Get-ActiveReviewSessionPath -Root $resolvedRoot
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ("Score: {0}" -f $session.discovery_score)
    Write-Host ("Motivo: {0}" -f $session.discovery_reason)
    Write-Host ("Worklist item: {0}" -f $session.worklist_item_count)
    Write-Host ("Sessione: {0}" -f $sessionPath)
    Write-Host ""
    Write-Host "Prossimo comando:"
    Write-Host "  .\scripts\memoria.ps1 review work -WorkspaceRoot `"$resolvedRoot`""
    Write-Host ""
    Write-Host "Nota: sessione preview-only; non registra decisioni e non crea verified_facts."
}

function Show-ReviewStatus {
    param(
        [string]$Root,
        [int]$MaxItems
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-ReviewDiscovery -Root $resolvedRoot -MaxItems $MaxItems
        return
    }
    Write-Host "Me.Mo.Ria review status"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ("Worklist item: {0}" -f $session.worklist_item_count)
    $progress = Get-ReviewSessionProgress -Session $session
    Write-Host ("Decisioni sessione: {0}/{1}" -f $progress.DecidedCount, $progress.TotalCount)
    Write-Host ("Pendenti: {0}" -f $progress.PendingCount)
    $lastDecisionItemNumber = Get-SessionPathValue -Session $session -Name "last_decision_item_number"
    $lastDecisionItemId = Get-SessionPathValue -Session $session -Name "last_decision_item_id"
    $lastSelectedAction = Get-SessionPathValue -Session $session -Name "last_selected_action"
    if (-not [string]::IsNullOrWhiteSpace($lastDecisionItemId)) {
        Write-Host ("Ultima decisione: [{0}] {1} -> {2}" -f $lastDecisionItemNumber, $lastDecisionItemId, $lastSelectedAction)
    }
    Write-Host ("Sessione: {0}" -f (Get-ActiveReviewSessionPath -Root $resolvedRoot))
    Write-Host ("Review session JSON: {0}" -f $session.review_session_json)
    try {
        $dashboardPaths = Get-ReviewDashboardPaths -Session $session
        if ((Test-Path -LiteralPath $dashboardPaths.OutputJson -PathType Leaf) -or (Test-Path -LiteralPath $dashboardPaths.OutputMd -PathType Leaf)) {
            Write-Host "Dashboard: disponibile"
            Write-Host ("  JSON: {0}" -f $dashboardPaths.OutputJson)
            Write-Host ("  Markdown: {0}" -f $dashboardPaths.OutputMd)
        } else {
            Write-Host "Dashboard: non generata"
            Write-Host "  Rigenerare: .\scripts\memoria.ps1 review refresh -WorkspaceRoot `"$resolvedRoot`""
        }
    } catch {
        Write-Host "Dashboard: non verificabile dalla sessione attiva"
    }
    Write-Host ""
    Write-Host "Prossimo comando:"
    Write-Host "  .\scripts\memoria.ps1 review work -WorkspaceRoot `"$resolvedRoot`""
}

function Show-ReviewWork {
    param(
        [string]$Root,
        [int]$MaxItems
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Write-Host "Nessuna sessione review attiva."
        Write-Host "Avviare prima:"
        Write-Host "  .\scripts\memoria.ps1 review start --auto -WorkspaceRoot `"$resolvedRoot`""
        return
    }
    Write-Host "Me.Mo.Ria review work"
    Write-Host "Run attiva: $($session.selected_run_id)"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    $worklist = @($session.worklist)
    if ($worklist.Count -eq 0) {
        Write-Host "La sessione attiva non contiene item numerabili."
        Write-Host ("Aprire: {0}" -f $session.review_session_json)
        return
    }
    foreach ($item in ($worklist | Select-Object -First $MaxItems)) {
        Write-Host ("[{0}] {1} | {2} | {3}" -f $item.display_number, $item.profile_label, $item.subject_kind, $item.decision_status)
        Write-Host ("    Item: {0}" -f $item.item_id)
        Write-Host ("    Documento: {0}" -f $item.source_document_id)
        if (($item.PSObject.Properties.Name -contains "raw_file") -and -not [string]::IsNullOrWhiteSpace([string]$item.raw_file)) {
            Write-Host ("    File sorgente: {0}" -f $item.raw_file)
        }
        if (($item.PSObject.Properties.Name -contains "metadata_file") -and -not [string]::IsNullOrWhiteSpace([string]$item.metadata_file)) {
            Write-Host ("    Metadata: {0}" -f $item.metadata_file)
        }
        Write-Host ("    Domanda: {0}" -f $item.question)
        Write-Host ("    Comando breve: .\scripts\memoria.ps1 review accept {0} -WorkspaceRoot `"{1}`"" -f $item.display_number, $resolvedRoot)
        Write-Host ("    Alternative: review reject {0} | review uncertain {0}" -f $item.display_number)
    }
    Write-Host ""
    Write-Host "Nota: i numeri sono una mappa operativa verso gli ID tecnici; non applicano decisioni."
}

function Set-ReviewItemDecision {
    param(
        [string]$Root,
        [string]$ItemNumber,
        [string]$CommandName
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Write-Host "Nessuna sessione review attiva."
        Write-Host "Avviare prima:"
        Write-Host "  .\scripts\memoria.ps1 review start --auto -WorkspaceRoot `"$resolvedRoot`""
        return
    }
    $displayNumber = 0
    if (-not [int]::TryParse($ItemNumber, [ref]$displayNumber) -or $displayNumber -lt 1) {
        throw "Numero item non valido per review ${CommandName}: $ItemNumber"
    }
    $workItem = Find-WorklistItem -Session $session -DisplayNumber $displayNumber
    if ($null -eq $workItem) {
        throw "Item review non trovato nella sessione attiva: $displayNumber"
    }
    $decisionPaths = Get-ReviewDecisionPaths -Session $session
    $queueItem = Find-ReviewQueueItem -DecisionPaths $decisionPaths -ItemId ([string]$workItem.item_id)
    $allowedDecisions = @(Get-StringList -Value $workItem.allowed_decisions)
    if ($allowedDecisions.Count -eq 0 -and $null -ne $queueItem) {
        $allowedDecisions = @(Get-StringList -Value $queueItem.allowed_decisions)
    }
    $selectedAction = Resolve-ReviewAction -CommandName $CommandName -AllowedDecisions $allowedDecisions
    $reviewedAt = (Get-Date).ToUniversalTime().ToString("o")
    $payload = Read-OrCreateDecisionsPayload -DecisionPaths $decisionPaths
    $payload = Set-DecisionInPayload -Payload $payload -ItemId ([string]$workItem.item_id) -SelectedAction $selectedAction -ReviewedAt $reviewedAt -CommandName $CommandName
    Write-JsonObject -Path $decisionPaths.DecisionsCompiledJson -Payload $payload
    Invoke-ReviewDecisionsSummary -DecisionPaths $decisionPaths
    Update-SessionDecisionState -Root $resolvedRoot -Session $session -DisplayNumber $displayNumber -ItemId ([string]$workItem.item_id) -SelectedAction $selectedAction -ReviewedAt $reviewedAt

    Write-Host ("Me.Mo.Ria review {0}" -f $CommandName)
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ("Item: [{0}] {1}" -f $displayNumber, $workItem.item_id)
    Write-Host ("Azione selezionata: {0}" -f $selectedAction)
    Write-Host ("Decisioni compilate: {0}" -f $decisionPaths.DecisionsCompiledJson)
    Write-Host ("Summary: {0}" -f $decisionPaths.SummaryJson)
    Write-Host ""
    Write-Host "Nota: decisione preview-only; non crea verified_facts e non modifica profili JSON-LD."
}

function Accept-ReviewItem {
    param(
        [string]$Root,
        [string]$ItemNumber
    )
    Set-ReviewItemDecision -Root $Root -ItemNumber $ItemNumber -CommandName "accept"
}

function Reject-ReviewItem {
    param(
        [string]$Root,
        [string]$ItemNumber
    )
    Set-ReviewItemDecision -Root $Root -ItemNumber $ItemNumber -CommandName "reject"
}

function Mark-ReviewItemUncertain {
    param(
        [string]$Root,
        [string]$ItemNumber
    )
    Set-ReviewItemDecision -Root $Root -ItemNumber $ItemNumber -CommandName "uncertain"
}

function Refresh-ReviewDashboard {
    param([string]$Root)
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Write-Host "Nessuna sessione review attiva."
        Write-Host "Avviare prima:"
        Write-Host "  .\scripts\memoria.ps1 review start --auto -WorkspaceRoot `"$resolvedRoot`""
        return
    }
    $dashboardPaths = Get-ReviewDashboardPaths -Session $session
    Write-Host "Me.Mo.Ria review refresh"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ""
    Invoke-ReviewDashboardBuild -Session $session -DashboardPaths $dashboardPaths
    Write-Host "Dashboard aggiornata:"
    Write-Host ("  JSON: {0}" -f $dashboardPaths.OutputJson)
    Write-Host ("  Markdown: {0}" -f $dashboardPaths.OutputMd)
    Write-Host ""
    Write-Host "Nota: refresh rigenera solo preview; non registra decisioni e non crea verified_facts."
}

function Show-ReviewDashboard {
    param([string]$Root)
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Write-Host "Nessuna sessione review attiva."
        Write-Host "Avviare prima:"
        Write-Host "  .\scripts\memoria.ps1 review start --auto -WorkspaceRoot `"$resolvedRoot`""
        return
    }
    $dashboardPaths = Get-ReviewDashboardPaths -Session $session
    Write-Host "Me.Mo.Ria review dashboard"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ""
    if ((Test-Path -LiteralPath $dashboardPaths.OutputJson -PathType Leaf) -or (Test-Path -LiteralPath $dashboardPaths.OutputMd -PathType Leaf)) {
        Write-Host "Dashboard disponibile:"
        Write-Host ("  JSON: {0}" -f $dashboardPaths.OutputJson)
        Write-Host ("  Markdown: {0}" -f $dashboardPaths.OutputMd)
    } else {
        Write-Host "Dashboard non ancora generata per la sessione attiva."
        Write-Host "Rigenerare con:"
        Write-Host "  .\scripts\memoria.ps1 review refresh -WorkspaceRoot `"$resolvedRoot`""
    }
}

function Show-MarkdownPreviewExcerpt {
    param(
        [string]$Label,
        [string]$Path,
        [string]$MissingCommand,
        [int]$MaxLines = 45
    )
    Write-Host ("## {0}" -f $Label)
    Write-Host ("Path: {0}" -f $Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Write-Host "Stato: non disponibile"
        Write-Host ("Rigenerare: {0}" -f $MissingCommand)
        Write-Host ""
        return
    }
    $lines = @(Get-Content -LiteralPath $Path -Encoding UTF8)
    if ($lines.Count -eq 0) {
        Write-Host "Stato: file vuoto"
        Write-Host ""
        return
    }
    foreach ($line in ($lines | Select-Object -First $MaxLines)) {
        Write-Host $line
    }
    if ($lines.Count -gt $MaxLines) {
        Write-Host ("... ({0} righe omesse)" -f ($lines.Count - $MaxLines))
    }
    Write-Host ""
}

function Show-ReviewDashboardCompact {
    param([string]$Root)
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveReviewSession -Root $resolvedRoot
    if ($null -eq $session) {
        Write-Host "Nessuna sessione review attiva."
        Write-Host "Avviare prima:"
        Write-Host "  .\scripts\memoria.ps1 review start --auto -WorkspaceRoot `"$resolvedRoot`""
        return
    }
    $dashboardPaths = Get-ReviewDashboardPaths -Session $session
    $verifiedFactsPreviewMd = Join-Path $dashboardPaths.ReviewDir "verified_facts.preview.md"
    $profilePatchPreviewMd = Join-Path $dashboardPaths.ReviewDir "profile_patch.preview.md"
    Write-Host "Me.Mo.Ria review dashboard show"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ""
    Show-MarkdownPreviewExcerpt `
        -Label "Review dashboard" `
        -Path $dashboardPaths.OutputMd `
        -MissingCommand ".\scripts\memoria.ps1 review refresh -WorkspaceRoot `"$resolvedRoot`""
    Show-MarkdownPreviewExcerpt `
        -Label "Verified facts preview" `
        -Path $verifiedFactsPreviewMd `
        -MissingCommand ".\scripts\memoria.ps1 review verified-facts run --preview -WorkspaceRoot `"$resolvedRoot`""
    Show-MarkdownPreviewExcerpt `
        -Label "ProfilePatch preview" `
        -Path $profilePatchPreviewMd `
        -MissingCommand ".\scripts\memoria.ps1 review profile-patch run --preview -WorkspaceRoot `"$resolvedRoot`""
    Write-Host "Nota: comando read-only; non crea verified_facts canonici, non applica ProfilePatch e non modifica profili JSON-LD."
}

function Get-DirectoryCount {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return 0
    }
    return @((Get-ChildItem -LiteralPath $Path -Directory -ErrorAction SilentlyContinue)).Count
}

function Get-FileCount {
    param(
        [string]$Path,
        [switch]$Recurse
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return 0
    }
    if ($Recurse) {
        return @((Get-ChildItem -LiteralPath $Path -File -Recurse -ErrorAction SilentlyContinue)).Count
    }
    return @((Get-ChildItem -LiteralPath $Path -File -ErrorAction SilentlyContinue)).Count
}

function Get-SampleNames {
    param(
        [string]$Path,
        [string]$Mode,
        [int]$MaxItems
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return @()
    }
    if ($Mode -eq "Directory") {
        return @((Get-ChildItem -LiteralPath $Path -Directory -ErrorAction SilentlyContinue | Select-Object -First $MaxItems | ForEach-Object { $_.Name }))
    }
    return @((Get-ChildItem -LiteralPath $Path -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First $MaxItems | ForEach-Object { $_.FullName }))
}

function Get-FirstExistingPath {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            return $path
        }
    }
    return $null
}

function Get-YamlListCount {
    param(
        [string]$Path,
        [string]$Section
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return 0
    }
    $count = 0
    $inSection = $false
    foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
        if ($line -match ("^{0}:\s*$" -f [regex]::Escape($Section))) {
            $inSection = $true
            continue
        }
        if ($inSection -and $line -match "^[A-Za-z0-9_@-]+:") {
            break
        }
        if ($inSection -and $line -match "^\s*-\s+") {
            $count += 1
        }
    }
    return $count
}

function Get-YamlSourceIds {
    param(
        [string]$Path,
        [int]$MaxItems
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }
    $items = New-Object System.Collections.Generic.List[string]
    foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
        if ($line -match "^\s*-\s+id:\s*(.+?)\s*$") {
            $items.Add($Matches[1].Trim('"'' '))
        }
        if ($items.Count -ge $MaxItems) {
            break
        }
    }
    return @($items)
}

function Get-ProfileIndexCount {
    param([string]$Path)
    $payload = Read-JsonObject -Path $Path
    if ($null -eq $payload) {
        return 0
    }
    return (Get-ListCount -Payload $payload -Names @("profiles", "items", "@graph"))
}

function Get-SourcesOnlineSubjectContext {
    param(
        [string]$RequestedProfileId,
        [string]$RequestedSubjectKind,
        [string]$RequestedSubjectId,
        [string]$RequestedSubjectLabel
    )
    $kind = $RequestedSubjectKind.Trim().ToLowerInvariant()
    $id = $RequestedSubjectId.Trim()
    $label = $RequestedSubjectLabel.Trim()
    if (-not [string]::IsNullOrWhiteSpace($RequestedProfileId)) {
        if ([string]::IsNullOrWhiteSpace($kind)) {
            $kind = "person"
        }
        if ([string]::IsNullOrWhiteSpace($id)) {
            $id = $RequestedProfileId.Trim()
        }
    }
    if ([string]::IsNullOrWhiteSpace($kind) -and [string]::IsNullOrWhiteSpace($id)) {
        return $null
    }
    if ($kind -notin @("person", "place", "event")) {
        throw "SubjectKind non supportato per sources online: $RequestedSubjectKind. Usare person, place o event."
    }
    if ([string]::IsNullOrWhiteSpace($id)) {
        throw "SubjectId obbligatorio per sources online quando si specifica SubjectKind."
    }
    if ([string]::IsNullOrWhiteSpace($label)) {
        $label = $id
    }
    $safeId = ($id -replace "[^A-Za-z0-9._-]+", "_").Trim("_")
    if ([string]::IsNullOrWhiteSpace($safeId)) {
        $safeId = "subject"
    }
    return [pscustomobject]@{
        Kind = $kind
        Id = $id
        Label = $label
        SafeId = $safeId
    }
}

function Get-SourcesOnlineIntakePath {
    param(
        [string]$Root,
        [object]$SubjectContext
    )
    return Join-Path (Join-Path (Join-Path $Root "documenti_da_processare") "sources_online") (Join-Path $SubjectContext.Kind $SubjectContext.SafeId)
}

function New-SourcesOnlineSessionPayload {
    param(
        [string]$Root,
        [string]$RegistryPath,
        [bool]$RegistryExists,
        [int]$EnabledSourceCount,
        [int]$SourceDefinitionCount,
        [string]$ProfilesIndexPath,
        [bool]$ProfilesIndexExists,
        [int]$ProfileCount,
        [string[]]$SampleSourceIds,
        [object]$SubjectContext
    )
    $intakePath = Get-SourcesOnlineIntakePath -Root $Root -SubjectContext $SubjectContext
    $candidateSources = @(
        foreach ($sourceId in $SampleSourceIds) {
            [ordered]@{
                source_id = $sourceId
                status = "candidate"
            }
        }
    )
    return [ordered]@{
        "@type" = "MemoriaSourcesOnlineSession"
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        workspace_root = $Root
        preview_only = $true
        review_status = "unreviewed"
        publication_status = "not_publishable_without_human_review"
        subject = [ordered]@{
            kind = $SubjectContext.Kind
            id = $SubjectContext.Id
            label = $SubjectContext.Label
        }
        source_registry = [ordered]@{
            path = $RegistryPath
            present = $RegistryExists
            enabled_source_count = $EnabledSourceCount
            source_definition_count = $SourceDefinitionCount
        }
        profiles_index = [ordered]@{
            path = $ProfilesIndexPath
            present = $ProfilesIndexExists
            profile_count = $ProfileCount
        }
        candidate_sources = $candidateSources
        candidate_query = [ordered]@{
            seed = $SubjectContext.Label
            status = "candidate_unreviewed"
        }
        proposed_intake_path = $intakePath
        candidate_record_preview = [ordered]@{
            record_kind = "sources_online_subject_intake_preview"
            subject_kind = $SubjectContext.Kind
            subject_id = $SubjectContext.Id
            query_seed = $SubjectContext.Label
            intake_path = $intakePath
            review_status = "unreviewed"
        }
        safety_notes = @(
            "Sessione preview-only: non avvia rete, browser, login, pipeline o import.",
            "Non crea cartelle intake e non scrive nello Evidence Store.",
            "Persone, luoghi ed eventi restano soggetti storici con evidenze candidate fino a review esplicita."
        )
    }
}

function Show-SourcesOnlineActiveSession {
    param([string]$Root)
    $sessionPath = Get-ActiveSourcesOnlineSessionPath -Root $Root
    Write-Host ""
    Write-Host "Sessione sources online attiva:"
    Write-Host ("  Path: {0}" -f $sessionPath)
    if (-not (Test-Path -LiteralPath $sessionPath -PathType Leaf)) {
        Write-Host "  Stato: non presente"
        Write-Host "  Avviare: .\scripts\memoria.ps1 sources online start --auto -SubjectKind person|place|event -SubjectId <id> -WorkspaceRoot `"$Root`""
        return
    }
    $session = Read-JsonObject -Path $sessionPath
    if ($null -eq $session) {
        Write-Host "  Stato: non leggibile"
        return
    }
    $subject = Get-ObjectPropertyValue -Payload $session -Name "subject"
    $candidateQuery = Get-ObjectPropertyValue -Payload $session -Name "candidate_query"
    Write-Host "  Stato: presente"
    Write-Host ("  Soggetto: {0} {1}" -f (Get-ObjectPropertyText -Payload $subject -Name "kind"), (Get-ObjectPropertyText -Payload $subject -Name "id"))
    Write-Host ("  Etichetta: {0}" -f (Get-ObjectPropertyText -Payload $subject -Name "label"))
    Write-Host ("  Query seed candidata: {0}" -f (Get-ObjectPropertyText -Payload $candidateQuery -Name "seed"))
    Write-Host ("  Intake proposto: {0}" -f (Get-ObjectPropertyText -Payload $session -Name "proposed_intake_path"))
    Write-Host ("  Preview-only: {0}" -f (Get-ObjectPropertyText -Payload $session -Name "preview_only"))
}

function Get-ConsolidateRunCandidates {
    param([string]$Root)
    $runsDir = Join-Path (Join-Path $Root "risultati") "runs"
    if (-not (Test-Path -LiteralPath $runsDir -PathType Container)) {
        return @()
    }
    $items = New-Object System.Collections.Generic.List[object]
    foreach ($run in @(Get-ChildItem -LiteralPath $runsDir -Directory -ErrorAction SilentlyContinue)) {
        $ledgerJson = Join-Path $run.FullName "mvp_consolidated_review_ledger.json"
        $ledgerMd = Join-Path $run.FullName "mvp_consolidated_review_ledger.md"
        $hasLedgerJson = Test-Path -LiteralPath $ledgerJson -PathType Leaf
        $hasLedgerMd = Test-Path -LiteralPath $ledgerMd -PathType Leaf
        $score = 10
        $reason = "run_candidate_without_ledger"
        if ($hasLedgerMd) {
            $score = 80
            $reason = "ledger_markdown_available"
        }
        if ($hasLedgerJson) {
            $score = 100
            $reason = "ledger_json_available"
        }
        $items.Add([pscustomobject]@{
            RunId = $run.Name
            RunDir = $run.FullName
            LedgerJson = if ($hasLedgerJson) { $ledgerJson } else { "" }
            LedgerMd = if ($hasLedgerMd) { $ledgerMd } else { "" }
            HasLedger = ($hasLedgerJson -or $hasLedgerMd)
            Score = $score
            Reason = $reason
        })
    }
    return @($items | Sort-Object -Property @{ Expression = "Score"; Descending = $true }, @{ Expression = "RunId"; Descending = $false })
}

function Show-SourcesOnlineDiscovery {
    param(
        [string]$Root,
        [int]$MaxItems,
        [string]$RequestedProfileId,
        [string]$RequestedSubjectKind,
        [string]$RequestedSubjectId,
        [string]$RequestedSubjectLabel,
        [switch]$ShowActiveSession,
        [switch]$AsStart
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $registryPath = Get-FirstExistingPath -Paths @(
        (Join-Path $repoRoot "..\memoria-sources\registry\camalanca_fonti.yaml"),
        (Join-Path $resolvedRoot "ricerche\camalanca_fonti.yaml"),
        (Join-Path $repoRoot "ricerche\camalanca_fonti.yaml")
    )
    $profilesIndexPath = Get-FirstExistingPath -Paths @(
        (Join-Path $resolvedRoot "ricerche\person_profiles\purocielo.index.jsonld")
    )
    $registryExists = -not [string]::IsNullOrWhiteSpace($registryPath)
    $profilesIndexExists = -not [string]::IsNullOrWhiteSpace($profilesIndexPath)
    $enabledSourceCount = if ($registryExists) { Get-YamlListCount -Path $registryPath -Section "enabled_sources" } else { 0 }
    $sourceDefinitionCount = if ($registryExists) { Get-YamlListCount -Path $registryPath -Section "sources" } else { 0 }
    $profileCount = if ($profilesIndexExists) { Get-ProfileIndexCount -Path $profilesIndexPath } else { 0 }
    $sampleSourceIds = if ($registryExists) { @(Get-YamlSourceIds -Path $registryPath -MaxItems $MaxItems) } else { @() }
    $subjectContext = Get-SourcesOnlineSubjectContext `
        -RequestedProfileId $RequestedProfileId `
        -RequestedSubjectKind $RequestedSubjectKind `
        -RequestedSubjectId $RequestedSubjectId `
        -RequestedSubjectLabel $RequestedSubjectLabel

    if ($AsStart) {
        Write-Host "Me.Mo.Ria sources online start"
    } else {
        Write-Host "Me.Mo.Ria sources online discovery"
    }
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Registry fonti: {0}" -f $(if ($registryExists) { $registryPath } else { "non trovato" }))
    Write-Host ("  Presente: {0}" -f $registryExists)
    Write-Host ("  Fonti abilitate: {0}" -f $enabledSourceCount)
    Write-Host ("  Definizioni fonte: {0}" -f $sourceDefinitionCount)
    Write-Host ("Indice profili pilota: {0}" -f $(if ($profilesIndexExists) { $profilesIndexPath } else { "non trovato" }))
    Write-Host ("  Presente: {0}" -f $profilesIndexExists)
    Write-Host ("  Profili candidati: {0}" -f $profileCount)
    if ($sampleSourceIds.Count -gt 0) {
        Write-Host ""
        Write-Host "Fonti candidate:"
        foreach ($sourceId in $sampleSourceIds) {
            Write-Host ("- {0}" -f $sourceId)
        }
    }
    if ($null -ne $subjectContext) {
        $intakePath = Get-SourcesOnlineIntakePath -Root $resolvedRoot -SubjectContext $subjectContext
        Write-Host ""
        Write-Host "Soggetto storico richiesto:"
        Write-Host ("  Tipo: {0}" -f $subjectContext.Kind)
        Write-Host ("  ID: {0}" -f $subjectContext.Id)
        Write-Host ("  Etichetta: {0}" -f $subjectContext.Label)
        Write-Host ("  Intake proposto: {0}" -f $intakePath)
        Write-Host ("  Query seed candidata: {0}" -f $subjectContext.Label)
        Write-Host "  Stato: fonte/evidenza candidata, non dato canonico"
    }
    Write-Host ""
    if ($AsStart) {
        if ($null -ne $subjectContext) {
            $sessionPath = Get-ActiveSourcesOnlineSessionPath -Root $resolvedRoot
            $sessionPayload = New-SourcesOnlineSessionPayload `
                -Root $resolvedRoot `
                -RegistryPath $(if ($registryExists) { $registryPath } else { "" }) `
                -RegistryExists $registryExists `
                -EnabledSourceCount $enabledSourceCount `
                -SourceDefinitionCount $sourceDefinitionCount `
                -ProfilesIndexPath $(if ($profilesIndexExists) { $profilesIndexPath } else { "" }) `
                -ProfilesIndexExists $profilesIndexExists `
                -ProfileCount $profileCount `
                -SampleSourceIds $sampleSourceIds `
                -SubjectContext $subjectContext
            Write-JsonObject -Path $sessionPath -Payload $sessionPayload
            Write-Host ("Sessione preview: {0}" -f $sessionPath)
        }
        Write-Host "Nota: start --auto in questo slice non avvia rete, browser, login, pipeline o import."
    } else {
        Write-Host "Prossimo comando:"
        if ($null -ne $subjectContext) {
            Write-Host ("  .\scripts\memoria.ps1 sources online start --auto -SubjectKind {0} -SubjectId `"{1}`" -WorkspaceRoot `"{2}`"" -f $subjectContext.Kind, $subjectContext.Id, $resolvedRoot)
        } else {
            Write-Host "  .\scripts\memoria.ps1 sources online start --auto -WorkspaceRoot `"$resolvedRoot`""
        }
    }
    if ($ShowActiveSession) {
        Show-SourcesOnlineActiveSession -Root $resolvedRoot
    }
    Write-Host "Nota: discovery read-only; non crea run, non scrive nello store e non modifica profili JSON-LD."
}

function Show-ConsolidateDiscovery {
    param(
        [string]$Root,
        [int]$MaxItems,
        [switch]$AsStart
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $runsDir = Join-Path (Join-Path $resolvedRoot "risultati") "runs"
    $databasePath = Join-Path (Join-Path $resolvedRoot "database") "evidence.sqlite"
    $runsDirExists = Test-Path -LiteralPath $runsDir -PathType Container
    $databaseExists = Test-Path -LiteralPath $databasePath -PathType Leaf
    $candidateRuns = @(Get-ConsolidateRunCandidates -Root $resolvedRoot)
    $runsWithLedger = @($candidateRuns | Where-Object { $_.HasLedger })

    if ($AsStart) {
        Write-Host "Me.Mo.Ria consolidate start"
    } else {
        Write-Host "Me.Mo.Ria consolidate discovery"
    }
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Evidence store: {0}" -f $databasePath)
    Write-Host ("  Presente: {0}" -f $databaseExists)
    Write-Host ("Run directory: {0}" -f $runsDir)
    Write-Host ("  Presente: {0}" -f $runsDirExists)
    Write-Host ("  Run candidate: {0}" -f $candidateRuns.Count)
    Write-Host ("  Run con ledger consolidato: {0}" -f $runsWithLedger.Count)
    if ($candidateRuns.Count -gt 0) {
        Write-Host ""
        Write-Host "Run candidate:"
        foreach ($run in ($candidateRuns | Select-Object -First $MaxItems)) {
            Write-Host ("- {0} | ledger={1}" -f $run.RunId, $run.HasLedger)
        }
    }
    Write-Host ""
    if ($AsStart) {
        Write-Host "Nota: start --auto in questo slice non rigenera ledger, non crea run e non importa nel DB."
    } else {
        Write-Host "Prossimo comando:"
        Write-Host "  .\scripts\memoria.ps1 consolidate start --auto -WorkspaceRoot `"$resolvedRoot`""
    }
    Write-Host "Nota: discovery read-only; non crea verified_facts e non modifica profili JSON-LD."
}

function Save-ActiveConsolidateSession {
    param(
        [string]$Root,
        [object]$Candidate
    )
    $createdAt = (Get-Date).ToUniversalTime().ToString("o")
    $databasePath = Join-Path (Join-Path $Root "database") "evidence.sqlite"
    $sessionPath = Get-ActiveConsolidateSessionPath -Root $Root
    $session = [pscustomobject]@{
        "@type" = "MemoriaConsolidateSession"
        created_at = $createdAt
        updated_at = $createdAt
        preview_only = $true
        review_status = "unreviewed"
        publication_status = "not_publishable_without_human_review"
        selected_run_id = $Candidate.RunId
        selected_run_dir = $Candidate.RunDir
        selected_ledger_json = $Candidate.LedgerJson
        selected_ledger_md = $Candidate.LedgerMd
        evidence_database_path = $databasePath
        evidence_database_exists = (Test-Path -LiteralPath $databasePath -PathType Leaf)
        discovery_score = $Candidate.Score
        discovery_reason = $Candidate.Reason
        note = "Sessione consolidate preview-only: non rigenera ledger, non crea run, non importa nel DB, non crea verified_facts e non modifica profili JSON-LD."
    }
    Write-JsonObject -Path $sessionPath -Payload $session
    return $session
}

function Get-ActiveConsolidateSession {
    param([string]$Root)
    return Read-JsonObject -Path (Get-ActiveConsolidateSessionPath -Root $Root)
}

function Start-ConsolidateSession {
    param(
        [string]$Root,
        [int]$MaxItems
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $candidates = @(Get-ConsolidateRunCandidates -Root $resolvedRoot)
    if ($candidates.Count -eq 0) {
        Show-ConsolidateDiscovery -Root $resolvedRoot -MaxItems $MaxItems
        Write-Host ""
        Write-Host "Nessuna run candidate disponibile per una sessione consolidate."
        return
    }
    $candidate = $candidates[0]
    $session = Save-ActiveConsolidateSession -Root $resolvedRoot -Candidate $candidate
    Write-Host "Me.Mo.Ria consolidate start"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ("Score: {0}" -f $session.discovery_score)
    Write-Host ("Motivo: {0}" -f $session.discovery_reason)
    Write-Host ("Ledger JSON: {0}" -f $(if ([string]::IsNullOrWhiteSpace($session.selected_ledger_json)) { "non disponibile" } else { $session.selected_ledger_json }))
    Write-Host ("Ledger Markdown: {0}" -f $(if ([string]::IsNullOrWhiteSpace($session.selected_ledger_md)) { "non disponibile" } else { $session.selected_ledger_md }))
    Write-Host ("Evidence store: {0}" -f $session.evidence_database_path)
    Write-Host ("Sessione: {0}" -f (Get-ActiveConsolidateSessionPath -Root $resolvedRoot))
    Write-Host ""
    Write-Host "Prossimo comando:"
    Write-Host "  .\scripts\memoria.ps1 consolidate dry-run -WorkspaceRoot `"$resolvedRoot`""
    Write-Host "  .\scripts\memoria.ps1 consolidate run --preview -WorkspaceRoot `"$resolvedRoot`""
    Write-Host ""
    Write-Host "Nota: sessione preview-only; non rigenera ledger, non crea run e non importa nel DB."
}

function Show-ConsolidateStatus {
    param(
        [string]$Root,
        [int]$MaxItems
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveConsolidateSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-ConsolidateDiscovery -Root $resolvedRoot -MaxItems $MaxItems
        return
    }
    Write-Host "Me.Mo.Ria consolidate status"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ("Score: {0}" -f $session.discovery_score)
    Write-Host ("Motivo: {0}" -f $session.discovery_reason)
    Write-Host ("Ledger JSON: {0}" -f $(if ([string]::IsNullOrWhiteSpace($session.selected_ledger_json)) { "non disponibile" } else { $session.selected_ledger_json }))
    Write-Host ("Ledger Markdown: {0}" -f $(if ([string]::IsNullOrWhiteSpace($session.selected_ledger_md)) { "non disponibile" } else { $session.selected_ledger_md }))
    Write-Host ("Evidence store: {0}" -f $session.evidence_database_path)
    Write-Host ("Sessione: {0}" -f (Get-ActiveConsolidateSessionPath -Root $resolvedRoot))
    Write-Host ""
    Write-Host "Nota: sessione preview-only; non crea verified_facts e non modifica profili JSON-LD."
}

function Get-ConsolidatePreviewSpec {
    param(
        [string]$ResolvedRoot,
        [object]$Session
    )
    $wrapperPath = Join-Path (Split-Path -Parent $PSScriptRoot) "scripts\build_mvp_consolidated_review_ledger.ps1"
    $outputJson = Join-Path ([string]$session.selected_run_dir) "mvp_consolidated_review_ledger.cli_preview.json"
    $outputMd = Join-Path ([string]$session.selected_run_dir) "mvp_consolidated_review_ledger.cli_preview.md"
    $hasEvidenceDb = $false
    if ($session.PSObject.Properties.Name -contains "evidence_database_exists") {
        $hasEvidenceDb = [bool]$session.evidence_database_exists
    }
    $arguments = New-Object System.Collections.Generic.List[string]
    if ($hasEvidenceDb) {
        $arguments.Add("-EvidenceDatabasePath")
        $arguments.Add([string]$session.evidence_database_path)
        $arguments.Add("-EvidenceSourceRunId")
        $arguments.Add([string]$session.selected_run_id)
    } else {
        $arguments.Add("-RunDir")
        $arguments.Add([string]$session.selected_run_dir)
    }
    $arguments.Add("-OutputJson")
    $arguments.Add($outputJson)
    $arguments.Add("-OutputMd")
    $arguments.Add($outputMd)
    return [pscustomobject]@{
        wrapper_path = $wrapperPath
        output_json = $outputJson
        output_md = $outputMd
        has_evidence_db = $hasEvidenceDb
        arguments = [string[]]$arguments.ToArray()
    }
}

function Show-NoConsolidateSessionMessage {
    param([string]$ResolvedRoot)
    Write-Host "Nessuna sessione consolidate attiva."
    Write-Host "Avviare prima:"
    Write-Host "  .\scripts\memoria.ps1 consolidate start --auto -WorkspaceRoot `"$ResolvedRoot`""
}

function Show-ConsolidateDryRun {
    param([string]$Root)
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveConsolidateSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoConsolidateSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $previewSpec = Get-ConsolidatePreviewSpec -ResolvedRoot $resolvedRoot -Session $session
    Write-Host "Me.Mo.Ria consolidate dry-run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ("Wrapper tecnico: {0}" -f $previewSpec.wrapper_path)
    Write-Host ("Output JSON proposto: {0}" -f $previewSpec.output_json)
    Write-Host ("Output Markdown proposto: {0}" -f $previewSpec.output_md)
    Write-Host ""
    Write-Host "Comando tecnico preparato:"
    Write-Host ("  .\scripts\build_mvp_consolidated_review_ledger.ps1 ``")
    if ([bool]$previewSpec.has_evidence_db) {
        Write-Host ("    -EvidenceDatabasePath `"{0}`" ``" -f $session.evidence_database_path)
        Write-Host ("    -EvidenceSourceRunId `"{0}`" ``" -f $session.selected_run_id)
    } else {
        Write-Host ("    -RunDir `"{0}`" ``" -f $session.selected_run_dir)
    }
    Write-Host ("    -OutputJson `"{0}`" ``" -f $previewSpec.output_json)
    Write-Host ("    -OutputMd `"{0}`"" -f $previewSpec.output_md)
    Write-Host ""
    Write-Host "Nota: dry-run testuale; non esegue il wrapper, non crea ledger, non scrive nello store e non modifica profili JSON-LD."
}

function Invoke-ConsolidateRunPreview {
    param(
        [string]$Root,
        [switch]$PreviewOnly
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    if (-not $PreviewOnly) {
        Show-Usage
        throw "Per eseguire consolidate run usare --preview. Il comando non promuove verified_facts e non modifica profili JSON-LD."
    }
    $session = Get-ActiveConsolidateSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoConsolidateSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $previewSpec = Get-ConsolidatePreviewSpec -ResolvedRoot $resolvedRoot -Session $session
    Write-Host "Me.Mo.Ria consolidate run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $session.selected_run_id)
    Write-Host ("Wrapper tecnico: {0}" -f $previewSpec.wrapper_path)
    Write-Host ("Output JSON preview: {0}" -f $previewSpec.output_json)
    Write-Host ("Output Markdown preview: {0}" -f $previewSpec.output_md)
    Write-Host ""
    if ([bool]$previewSpec.has_evidence_db) {
        & ([string]$previewSpec.wrapper_path) `
            -EvidenceDatabasePath ([string]$session.evidence_database_path) `
            -EvidenceSourceRunId ([string]$session.selected_run_id) `
            -OutputJson ([string]$previewSpec.output_json) `
            -OutputMd ([string]$previewSpec.output_md)
    } else {
        & ([string]$previewSpec.wrapper_path) `
            -RunDir ([string]$session.selected_run_dir) `
            -OutputJson ([string]$previewSpec.output_json) `
            -OutputMd ([string]$previewSpec.output_md)
    }
    if ($LASTEXITCODE -ne 0) {
        throw "consolidate run --preview fallito con exit code $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "Preview ledger generata."
    Write-Host "Nota: non importa nello store, non crea verified_facts e non modifica profili JSON-LD."
}

function Convert-ProfileIdToFileStem {
    param([string]$Value)
    $stem = ($Value -replace "[^A-Za-z0-9]+", "-").Trim("-").ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($stem)) {
        return "profile"
    }
    return $stem
}

function Get-ConsolidateProfileStatusSpec {
    param(
        [object]$Session,
        [string]$RequestedProfileId
    )
    if ([string]::IsNullOrWhiteSpace($RequestedProfileId)) {
        throw "Per consolidate profile-status specificare -ProfileId <profile-id>."
    }
    $databasePath = Get-SessionPathValue -Session $Session -Name "evidence_database_path"
    if ([string]::IsNullOrWhiteSpace($databasePath)) {
        throw "La sessione consolidate attiva non contiene evidence_database_path."
    }
    if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
        throw "Evidence DB non trovato per profile-status: $databasePath"
    }
    $selectedRunId = Get-SessionPathValue -Session $Session -Name "selected_run_id"
    if ([string]::IsNullOrWhiteSpace($selectedRunId)) {
        throw "La sessione consolidate attiva non contiene selected_run_id."
    }
    $selectedRunDir = Get-SessionPathValue -Session $Session -Name "selected_run_dir"
    if ([string]::IsNullOrWhiteSpace($selectedRunDir)) {
        throw "La sessione consolidate attiva non contiene selected_run_dir."
    }
    $wrapperPath = Join-Path $PSScriptRoot "build_evidence_store_profile_status.ps1"
    if (-not (Test-Path -LiteralPath $wrapperPath -PathType Leaf)) {
        throw "Wrapper profile-status non trovato: $wrapperPath"
    }
    $reviewDir = Join-Path $selectedRunDir "historian_review"
    $profileStem = Convert-ProfileIdToFileStem -Value $RequestedProfileId
    return [pscustomobject]@{
        wrapper_path = $wrapperPath
        database_path = $databasePath
        profile_id = $RequestedProfileId
        evidence_source_run_id = $selectedRunId
        output_json = Join-Path $reviewDir ("profile_evidence_status.{0}.cli_preview.json" -f $profileStem)
        output_md = Join-Path $reviewDir ("profile_evidence_status.{0}.cli_preview.md" -f $profileStem)
    }
}

function Show-ConsolidateProfileStatusDryRun {
    param(
        [string]$Root,
        [string]$RequestedProfileId
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $session = Get-ActiveConsolidateSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoConsolidateSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $previewSpec = Get-ConsolidateProfileStatusSpec -Session $session -RequestedProfileId $RequestedProfileId
    Write-Host "Me.Mo.Ria consolidate profile-status dry-run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $previewSpec.evidence_source_run_id)
    Write-Host ("Profile ID: {0}" -f $previewSpec.profile_id)
    Write-Host ("Wrapper tecnico: {0}" -f $previewSpec.wrapper_path)
    Write-Host ("Output JSON proposto: {0}" -f $previewSpec.output_json)
    Write-Host ("Output Markdown proposto: {0}" -f $previewSpec.output_md)
    Write-Host ""
    Write-Host "Comando tecnico preparato:"
    Write-Host ("  .\scripts\build_evidence_store_profile_status.ps1 ``")
    Write-Host ("    -DatabasePath `"{0}`" ``" -f $previewSpec.database_path)
    Write-Host ("    -ProfileId `"{0}`" ``" -f $previewSpec.profile_id)
    Write-Host ("    -EvidenceSourceRunId `"{0}`" ``" -f $previewSpec.evidence_source_run_id)
    Write-Host ("    -OutputJson `"{0}`" ``" -f $previewSpec.output_json)
    Write-Host ("    -OutputMd `"{0}`"" -f $previewSpec.output_md)
    Write-Host ""
    Write-Host "Nota: dry-run testuale; non esegue il wrapper, non scrive nello store e non modifica profili JSON-LD."
}

function Invoke-ConsolidateProfileStatusRun {
    param(
        [string]$Root,
        [string]$RequestedProfileId,
        [switch]$PreviewOnly
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    if (-not $PreviewOnly) {
        Show-Usage
        throw "Per eseguire consolidate profile-status run usare --preview. Il comando non scrive nello store e non modifica profili JSON-LD."
    }
    $session = Get-ActiveConsolidateSession -Root $resolvedRoot
    if ($null -eq $session) {
        Show-NoConsolidateSessionMessage -ResolvedRoot $resolvedRoot
        return
    }
    $previewSpec = Get-ConsolidateProfileStatusSpec -Session $session -RequestedProfileId $RequestedProfileId
    Write-Host "Me.Mo.Ria consolidate profile-status run"
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only"
    Write-Host ""
    Write-Host ("Run attiva: {0}" -f $previewSpec.evidence_source_run_id)
    Write-Host ("Profile ID: {0}" -f $previewSpec.profile_id)
    Write-Host ("Wrapper tecnico: {0}" -f $previewSpec.wrapper_path)
    Write-Host ("Output JSON preview: {0}" -f $previewSpec.output_json)
    Write-Host ("Output Markdown preview: {0}" -f $previewSpec.output_md)
    Write-Host ""
    & ([string]$previewSpec.wrapper_path) `
        -DatabasePath ([string]$previewSpec.database_path) `
        -ProfileId ([string]$previewSpec.profile_id) `
        -EvidenceSourceRunId ([string]$previewSpec.evidence_source_run_id) `
        -OutputJson ([string]$previewSpec.output_json) `
        -OutputMd ([string]$previewSpec.output_md)
    if ($LASTEXITCODE -ne 0) {
        throw "consolidate profile-status run --preview fallito con exit code $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "Profile status preview generata."
    Write-Host "Nota: non scrive nello store, non crea verified_facts e non modifica profili JSON-LD."
}

function Show-SourcesOfflineDiscovery {
    param(
        [string]$Root,
        [int]$MaxItems,
        [switch]$AsStart
    )
    $resolvedRoot = Resolve-WorkspaceRoot -Root $Root
    $intakeDir = Join-Path $resolvedRoot "documenti_da_processare"
    $processedDir = Join-Path $resolvedRoot "documenti_processati"
    $intakeExists = Test-Path -LiteralPath $intakeDir -PathType Container
    $processedExists = Test-Path -LiteralPath $processedDir -PathType Container
    $intakeDirectoryCount = Get-DirectoryCount -Path $intakeDir
    $intakeFileCount = Get-FileCount -Path $intakeDir -Recurse
    $processedFileCount = Get-FileCount -Path $processedDir -Recurse
    $sampleDirectories = @(Get-SampleNames -Path $intakeDir -Mode "Directory" -MaxItems $MaxItems)
    $sampleFiles = @(Get-SampleNames -Path $intakeDir -Mode "File" -MaxItems $MaxItems)

    if ($AsStart) {
        Write-Host "Me.Mo.Ria sources offline start"
    } else {
        Write-Host "Me.Mo.Ria sources offline discovery"
    }
    Write-Host "Workspace: $resolvedRoot"
    Write-Host "Modalita: preview-only/read-only"
    Write-Host ""
    Write-Host ("Documenti da processare: {0}" -f $intakeDir)
    Write-Host ("  Presente: {0}" -f $intakeExists)
    Write-Host ("  Cartelle candidate: {0}" -f $intakeDirectoryCount)
    Write-Host ("  File candidati: {0}" -f $intakeFileCount)
    Write-Host ("Documenti processati: {0}" -f $processedDir)
    Write-Host ("  Presente: {0}" -f $processedExists)
    Write-Host ("  File processati: {0}" -f $processedFileCount)
    if ($sampleDirectories.Count -gt 0) {
        Write-Host ""
        Write-Host "Cartelle candidate:"
        foreach ($name in $sampleDirectories) {
            Write-Host ("- {0}" -f $name)
        }
    }
    if ($sampleFiles.Count -gt 0) {
        Write-Host ""
        Write-Host "File candidati:"
        foreach ($path in $sampleFiles) {
            Write-Host ("- {0}" -f $path)
        }
    }
    Write-Host ""
    if ($AsStart) {
        Write-Host "Nota: start --auto in questo slice non avvia OCR, pipeline o import."
    } else {
        Write-Host "Prossimo comando:"
        Write-Host "  .\scripts\memoria.ps1 sources offline start --auto -WorkspaceRoot `"$resolvedRoot`""
    }
    Write-Host "Nota: discovery read-only; non crea run, non scrive nello store e non modifica profili JSON-LD."
}

if ([string]::IsNullOrWhiteSpace($Area)) {
    Show-Usage
    exit 0
}

if ($Area -eq "status") {
    Show-ReviewStatus -Root $WorkspaceRoot -MaxItems $Limit
    exit 0
}

if ($Area -eq "sources") {
    if ($Command -notin @("online", "offline")) {
        Show-Usage
        throw "Comando sources non supportato: $Command"
    }
    if ([string]::IsNullOrWhiteSpace($Item)) {
        $Item = "discover"
    }
    if ($Command -eq "online") {
        switch ($Item) {
            "discover" {
                Show-SourcesOnlineDiscovery -Root $WorkspaceRoot -MaxItems $Limit -RequestedProfileId $ProfileId -RequestedSubjectKind $SubjectKind -RequestedSubjectId $SubjectId -RequestedSubjectLabel $SubjectLabel
            }
            "status" {
                Show-SourcesOnlineDiscovery -Root $WorkspaceRoot -MaxItems $Limit -RequestedProfileId $ProfileId -RequestedSubjectKind $SubjectKind -RequestedSubjectId $SubjectId -RequestedSubjectLabel $SubjectLabel -ShowActiveSession
            }
            "start" {
                if (-not $Auto) {
                    Show-Usage
                    throw "Per il primo slice usare sources online start --auto in modalita preview-only."
                }
                Show-SourcesOnlineDiscovery -Root $WorkspaceRoot -MaxItems $Limit -RequestedProfileId $ProfileId -RequestedSubjectKind $SubjectKind -RequestedSubjectId $SubjectId -RequestedSubjectLabel $SubjectLabel -AsStart
            }
            default {
                Show-Usage
                throw "Comando sources online non supportato: $Item"
            }
        }
        exit 0
    }
    switch ($Item) {
        "discover" {
            Show-SourcesOfflineDiscovery -Root $WorkspaceRoot -MaxItems $Limit
        }
        "status" {
            Show-SourcesOfflineDiscovery -Root $WorkspaceRoot -MaxItems $Limit
        }
        "start" {
            if (-not $Auto) {
                Show-Usage
                throw "Per il primo slice usare sources offline start --auto in modalita preview-only."
            }
            Show-SourcesOfflineDiscovery -Root $WorkspaceRoot -MaxItems $Limit -AsStart
        }
        default {
            Show-Usage
            throw "Comando sources offline non supportato: $Item"
        }
    }
    exit 0
}

if ($Area -eq "consolidate") {
    if ([string]::IsNullOrWhiteSpace($Command)) {
        $Command = "discover"
    }
    switch ($Command) {
        "discover" {
            Show-ConsolidateDiscovery -Root $WorkspaceRoot -MaxItems $Limit
        }
        "status" {
            Show-ConsolidateStatus -Root $WorkspaceRoot -MaxItems $Limit
        }
        "start" {
            if (-not $Auto) {
                Show-Usage
                throw "Per il primo slice usare consolidate start --auto in modalita preview-only."
            }
            Start-ConsolidateSession -Root $WorkspaceRoot -MaxItems $Limit
        }
        "dry-run" {
            Show-ConsolidateDryRun -Root $WorkspaceRoot
        }
        "run" {
            Invoke-ConsolidateRunPreview -Root $WorkspaceRoot -PreviewOnly:$Preview
        }
        "profile-status" {
            if ([string]::IsNullOrWhiteSpace($Item)) {
                $Item = "dry-run"
            }
            switch ($Item) {
                "dry-run" {
                    Show-ConsolidateProfileStatusDryRun -Root $WorkspaceRoot -RequestedProfileId $ProfileId
                }
                "run" {
                    Invoke-ConsolidateProfileStatusRun -Root $WorkspaceRoot -RequestedProfileId $ProfileId -PreviewOnly:$Preview
                }
                default {
                    Show-Usage
                    throw "Comando consolidate profile-status non supportato: $Item"
                }
            }
        }
        default {
            Show-Usage
            throw "Comando consolidate non supportato: $Command"
        }
    }
    exit 0
}

if ($Area -ne "review") {
    Show-Usage
    throw "Area non supportata: $Area"
}

if ([string]::IsNullOrWhiteSpace($Command)) {
    $Command = "discover"
}

if ($Command -eq "verified-facts") {
    if ([string]::IsNullOrWhiteSpace($Item)) {
        $Item = "dry-run"
    }
    switch ($Item) {
        "dry-run" {
            Show-VerifiedFactsPreviewDryRun -Root $WorkspaceRoot
        }
        "run" {
            Invoke-VerifiedFactsPreviewRun -Root $WorkspaceRoot -PreviewOnly:$Preview
        }
        default {
            Show-Usage
            throw "Comando review verified-facts non supportato: $Item"
        }
    }
    exit 0
}

if ($Command -eq "targets") {
    if ([string]::IsNullOrWhiteSpace($Item)) {
        $Item = "dry-run"
    }
    switch ($Item) {
        "dry-run" {
            Show-HistoricalReviewTargetsDryRun -Root $WorkspaceRoot
        }
        "run" {
            Invoke-HistoricalReviewTargetsRun -Root $WorkspaceRoot -PreviewOnly:$Preview
        }
        default {
            Show-Usage
            throw "Comando review targets non supportato: $Item"
        }
    }
    exit 0
}

if ($Command -eq "store") {
    if ([string]::IsNullOrWhiteSpace($Item)) {
        $Item = "dry-run"
    }
    switch ($Item) {
        "dry-run" {
            Show-ReviewStorePreviewDryRun -Root $WorkspaceRoot
        }
        "run" {
            Invoke-ReviewStorePreviewRun -Root $WorkspaceRoot -PreviewOnly:$Preview
        }
        default {
            Show-Usage
            throw "Comando review store non supportato: $Item"
        }
    }
    exit 0
}

if ($Command -eq "dataset-export") {
    if ([string]::IsNullOrWhiteSpace($Item)) {
        $Item = "dry-run"
    }
    switch ($Item) {
        "dry-run" {
            Show-DatasetExportPreviewDryRun -Root $WorkspaceRoot -RequestedProfileId $ProfileId
        }
        "run" {
            Invoke-DatasetExportPreviewRun -Root $WorkspaceRoot -PreviewOnly:$Preview -RequestedProfileId $ProfileId
        }
        "show" {
            Show-DatasetExportPreviewCompact -Root $WorkspaceRoot -RequestedProfileId $ProfileId
        }
        default {
            Show-Usage
            throw "Comando review dataset-export non supportato: $Item"
        }
    }
    exit 0
}

if ($Command -eq "profile-patch") {
    if ([string]::IsNullOrWhiteSpace($Item)) {
        $Item = "dry-run"
    }
    switch ($Item) {
        "dry-run" {
            Show-ProfilePatchPreviewDryRun -Root $WorkspaceRoot
        }
        "run" {
            Invoke-ProfilePatchPreviewRun -Root $WorkspaceRoot -PreviewOnly:$Preview
        }
        "apply" {
            Invoke-ProfilePatchApply -Root $WorkspaceRoot -SandboxOnly:$Sandbox -CanonicalOnly:$Canonical -RequestedProfileId $ProfileId
        }
        default {
            Show-Usage
            throw "Comando review profile-patch non supportato: $Item"
        }
    }
    exit 0
}

switch ($Command) {
    "discover" {
        Show-ReviewDiscovery -Root $WorkspaceRoot -MaxItems $Limit
    }
    "status" {
        Show-ReviewStatus -Root $WorkspaceRoot -MaxItems $Limit
    }
    "start" {
        if (-not $Auto) {
            Show-Usage
            throw "Per il primo slice usare review start --auto in modalita preview-only."
        }
        Start-ReviewSession -Root $WorkspaceRoot -MaxItems $Limit
    }
    "work" {
        Show-ReviewWork -Root $WorkspaceRoot -MaxItems $Limit
    }
    "alternatives" {
        Show-ReviewAlternatives -Root $WorkspaceRoot -MaxItems $Limit -RequestedProfileId $ProfileId
    }
    "accept" {
        if ([string]::IsNullOrWhiteSpace($Item)) {
            throw "Specificare il numero item: review accept 1"
        }
        Accept-ReviewItem -Root $WorkspaceRoot -ItemNumber $Item
    }
    "reject" {
        if ([string]::IsNullOrWhiteSpace($Item)) {
            throw "Specificare il numero item: review reject 1"
        }
        Reject-ReviewItem -Root $WorkspaceRoot -ItemNumber $Item
    }
    "uncertain" {
        if ([string]::IsNullOrWhiteSpace($Item)) {
            throw "Specificare il numero item: review uncertain 1"
        }
        Mark-ReviewItemUncertain -Root $WorkspaceRoot -ItemNumber $Item
    }
    "refresh" {
        Refresh-ReviewDashboard -Root $WorkspaceRoot
    }
    "dashboard" {
        if ([string]::IsNullOrWhiteSpace($Item)) {
            Show-ReviewDashboard -Root $WorkspaceRoot
        } elseif ($Item -eq "show") {
            Show-ReviewDashboardCompact -Root $WorkspaceRoot
        } else {
            Show-Usage
            throw "Comando review dashboard non supportato: $Item"
        }
    }
    default {
        Show-Usage
        throw "Comando review non supportato: $Command"
    }
}
