[CmdletBinding()]
param(
    [string]$RepoRoot,
    [Alias("sources-yaml")]
    [string]$SourcesYaml = "..\memoria-sources\registry\camalanca_fonti.yaml",
    [Alias("output-json")]
    [string]$OutputJson = "risultati\source_quality_audit.json",
    [Alias("output-md")]
    [string]$OutputMd = "risultati\source_quality_audit.md",
    [switch]$ShowSummary,
    [switch]$FailOnErrorIssues,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
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

function Test-PythonCanImportProject {
    param([string]$PythonExe)
    try {
        $null = & $PythonExe -c "import yaml; import caduti_fonti_report" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-PythonExe {
    if (Test-Path -LiteralPath $venvPython) {
        if (Test-PythonCanImportProject -PythonExe $venvPython) {
            return $venvPython
        }
    }

    if (Test-PythonCanImportProject -PythonExe $systemPython) {
        return $systemPython
    }

    $message = @(
        "Nessun interprete Python disponibile con PyYAML e package del progetto importabile.",
        "Esegui dalla root del repository oppure crea/aggiorna la virtualenv.",
        "Comando consigliato:",
        "  .venv\Scripts\python.exe -m pip install PyYAML"
    ) -join [Environment]::NewLine
    throw $message
}

function Convert-ToRepoRelativePath {
    param([string]$PathValue)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return $PathValue.Replace("/", "\")
}

$previousPythonPath = $env:PYTHONPATH
$codePath = Join-Path $resolvedRepoRoot "code"
if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $env:PYTHONPATH = $codePath
} else {
    $env:PYTHONPATH = "$codePath;$previousPythonPath"
}

try {
    Push-Location $resolvedRepoRoot
    $pythonExe = Resolve-PythonExe
    $resolvedPython = (& $pythonExe -c "import sys; print(sys.executable)")
    Write-Host "Uso Python: $resolvedPython"
    Write-Host "Registry fonti: $SourcesYaml"
    Write-Host "Output Markdown: $OutputMd"
    Write-Host "Output JSON: $OutputJson"

    & $pythonExe -m caduti_fonti_report.source_quality_audit `
        --repo-root . `
        --registry (Convert-ToRepoRelativePath -PathValue $SourcesYaml) `
        --output-json (Convert-ToRepoRelativePath -PathValue $OutputJson) `
        --output-md (Convert-ToRepoRelativePath -PathValue $OutputMd) `
        @ExtraArgs

    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $jsonPath = if ([System.IO.Path]::IsPathRooted($OutputJson)) { $OutputJson } else { Join-Path $resolvedRepoRoot $OutputJson }
    if ($ShowSummary -or $FailOnErrorIssues) {
        if (-not (Test-Path -LiteralPath $jsonPath)) {
            throw "File JSON audit non trovato: $jsonPath"
        }
        $audit = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
        $assessments = @($audit.assessments)
        $issues = @($assessments | ForEach-Object { @($_.issues) })
        $errorIssues = @($issues | Where-Object { $_.severity -eq "error" })
        $warningIssues = @($issues | Where-Object { $_.severity -eq "warning" })
        if ($ShowSummary) {
            Write-Host "Fonti analizzate: $($audit.source_count)"
            Write-Host "Problemi error: $($errorIssues.Count)"
            Write-Host "Problemi warning: $($warningIssues.Count)"
            Write-Host "Audit generato: $OutputMd"
        }
        if ($FailOnErrorIssues -and $errorIssues.Count -gt 0) {
            throw "Audit qualità fonti completato ma contiene $($errorIssues.Count) problemi con severity=error."
        }
    }
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
