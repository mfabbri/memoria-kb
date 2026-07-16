[CmdletBinding()]
param(
    [string]$RepoRoot,
    [Alias("sources-yaml")]
    [string]$SourcesYaml = "..\memoria-sources\registry\camalanca_fonti.yaml",
    [Alias("audit-output-json")]
    [string]$AuditOutputJson = "risultati\source_quality_audit.json",
    [Alias("audit-output-md")]
    [string]$AuditOutputMd = "risultati\source_quality_audit.md",
    [ValidateSet("Targeted", "Full", "None")]
    [string]$TestSuite = "Targeted",
    [switch]$SkipRegistryValidation,
    [switch]$SkipSourceQualityAudit,
    [switch]$FailOnAuditErrors,
    [switch]$ShowAuditSummary,
    [switch]$RunRuff,
    [switch]$FailOnRuff,
    [string]$RuffPath = "",
    [string]$BaselineOutputDir = "",
    [string]$BaselineRunId = "mvp-quality-gate-baseline"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultRepoRoot = Split-Path -Parent $scriptDir
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = $defaultRepoRoot
}
$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$venvPython = Join-Path $resolvedRepoRoot ".venv\Scripts\python.exe"
$systemPython = "python"

function Resolve-PythonExe {
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        return $venvPython
    }
    return $systemPython
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Body
    )
    Write-Host ""
    Write-Host "== $Name =="
    & $Body
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Invoke-OptionalStep {
    param(
        [string]$Name,
        [scriptblock]$Body,
        [switch]$FailOnError
    )
    Write-Host ""
    Write-Host "== $Name =="
    & $Body
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        if ($FailOnError) {
            exit $exitCode
        }
        Write-Warning "$Name ha rilevato problemi ma non blocca il quality gate. Exit code: $exitCode"
    }
}

function Resolve-RuffCommand {
    param(
        [string]$RepoRoot,
        [string]$ConfiguredPath
    )
    if (-not [string]::IsNullOrWhiteSpace($ConfiguredPath)) {
        if (Test-Path -LiteralPath $ConfiguredPath -PathType Leaf) {
            return (Resolve-Path -LiteralPath $ConfiguredPath).Path
        }
        return $ConfiguredPath
    }

    $venvRuff = Join-Path $RepoRoot ".venv\Scripts\ruff.exe"
    if (Test-Path -LiteralPath $venvRuff -PathType Leaf) {
        return $venvRuff
    }

    $ruffCommand = Get-Command "ruff" -ErrorAction SilentlyContinue
    if ($null -ne $ruffCommand) {
        return $ruffCommand.Source
    }

    return $null
}

$previousPythonPath = $env:PYTHONPATH
$codePath = Join-Path $resolvedRepoRoot "code"
if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $env:PYTHONPATH = $codePath
} else {
    $env:PYTHONPATH = "$codePath;$previousPythonPath"
}

Push-Location $resolvedRepoRoot
try {
    if ($TestSuite -ne "None") {
        Invoke-Step -Name "Test quality gate" -Body {
            & (Join-Path $resolvedRepoRoot "scripts\test_quality_gate.ps1") -RepoRoot $resolvedRepoRoot -Suite $TestSuite
        }
    }

    if ($RunRuff) {
        $resolvedRuff = Resolve-RuffCommand -RepoRoot $resolvedRepoRoot -ConfiguredPath $RuffPath
        if ($null -eq $resolvedRuff) {
            Write-Warning "Ruff non trovato. Installa con: .\.venv\Scripts\python.exe -m pip install -e `".[dev]`""
            if ($FailOnRuff) {
                exit 1
            }
        }
        else {
            Invoke-OptionalStep -Name "Ruff static audit" -FailOnError:$FailOnRuff -Body {
                & $resolvedRuff check code tests --statistics
            }
        }
    }

    if (-not $SkipRegistryValidation) {
        Invoke-Step -Name "Validazione registry fonti" -Body {
            & (Join-Path $resolvedRepoRoot "scripts\validate_sources_registry.ps1") -RepoRoot $resolvedRepoRoot -SourcesYaml $SourcesYaml
        }
    }

    if (-not $SkipSourceQualityAudit) {
        $auditArgs = @{
            RepoRoot    = $resolvedRepoRoot
            SourcesYaml = $SourcesYaml
            OutputJson  = $AuditOutputJson
            OutputMd    = $AuditOutputMd
        }
        if ($ShowAuditSummary) { $auditArgs["ShowSummary"] = $true }
        if ($FailOnAuditErrors) { $auditArgs["FailOnErrorIssues"] = $true }
        Invoke-Step -Name "Audit qualità fonti" -Body {
            & (Join-Path $resolvedRepoRoot "scripts\run_source_quality_audit.ps1") @auditArgs
        }
    }

    Write-Host ""
    Write-Host "Quality gate completato."
    Write-Host "Audit Markdown: $AuditOutputMd"
    Write-Host "Audit JSON: $AuditOutputJson"

    if (-not [string]::IsNullOrWhiteSpace($BaselineOutputDir)) {
        $registryStatus = "passed"
        if ($SkipRegistryValidation) {
            $registryStatus = "skipped"
        }
        $sourceAuditStatus = "passed"
        if ($SkipSourceQualityAudit) {
            $sourceAuditStatus = "skipped"
        }
        $ruffStatus = "not_run"
        if ($RunRuff) {
            $ruffStatus = "passed"
        }
        $qualityGateCommand = ".\scripts\run_quality_gate.ps1 -TestSuite $TestSuite"
        $pythonExe = Resolve-PythonExe
        & $pythonExe -m caduti_fonti_report.document_analysis.quality_gate_baseline `
            --output-dir $BaselineOutputDir `
            --run-id $BaselineRunId `
            --test-suite $TestSuite `
            --status passed `
            --command $qualityGateCommand `
            --audit-output-json $AuditOutputJson `
            --audit-output-md $AuditOutputMd `
            --registry-validation-status $registryStatus `
            --source-quality-audit-status $sourceAuditStatus `
            --ruff-status $ruffStatus
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
