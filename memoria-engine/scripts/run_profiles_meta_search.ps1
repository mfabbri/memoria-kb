[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProfilesIndex,
    [string]$SourcesYaml = "..\memoria-sources\registry\camalanca_fonti.yaml",
    [string]$OutputMd = "risultati\profili_purocielo_fonti_report.md",
    [string]$OutputJson = "risultati\profili_purocielo_fonti_report.json",
    [string]$OutputDir = "risultati\profili_purocielo_schede",
    [string]$AcquireDocumentsRoot = "",
    [int]$Limit = 0,
    [string]$Source = "",
    [string]$ProfileId = "",
    [string]$Name = "",
    [double]$Delay = 0,
    [switch]$IncludeSearchPlan,
    [switch]$ExecuteFirstPlannedAttempt,
    [switch]$EnsureAuthenticatedSession,
    [switch]$RefreshAuthenticatedCache,
    [int]$KeepAuthenticatedBrowserOpenSeconds = 0,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
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

    throw "Nessun interprete Python disponibile con PyYAML e package del progetto importabile."
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
    $resolvedPython = (& $pythonExe -c "import sys; print(sys.executable)")
    Write-Host "Uso Python: $resolvedPython"

    $argsList = @(
        "-m", "caduti_fonti_report.profiles_runner",
        "--profiles-index", $ProfilesIndex,
        "--sources-yaml", $SourcesYaml,
        "--output-md", $OutputMd,
        "--output-json", $OutputJson,
        "--output-dir", $OutputDir,
        "--limit", "$Limit",
        "--delay", "$Delay"
    )

    if (-not [string]::IsNullOrWhiteSpace($Source)) {
        $argsList += @("--source", $Source)
    }
    if (-not [string]::IsNullOrWhiteSpace($ProfileId)) {
        $argsList += @("--profile-id", $ProfileId)
    }
    if (-not [string]::IsNullOrWhiteSpace($Name)) {
        $argsList += @("--name", $Name)
    }
    if ($IncludeSearchPlan) {
        $argsList += @("--include-search-plan")
    }
    if ($ExecuteFirstPlannedAttempt) {
        $argsList += @("--execute-first-planned-attempt")
    }
    if ($EnsureAuthenticatedSession) {
        $argsList += @("--ensure-authenticated-session")
    }
    if ($RefreshAuthenticatedCache) {
        $argsList += @("--refresh-authenticated-cache")
    }
    if ($KeepAuthenticatedBrowserOpenSeconds -gt 0) {
        $argsList += @("--keep-authenticated-browser-open-seconds", "$KeepAuthenticatedBrowserOpenSeconds")
    }
    if (-not [string]::IsNullOrWhiteSpace($AcquireDocumentsRoot)) {
        $argsList += @("--acquire-documents-root", $AcquireDocumentsRoot)
    }
    if ($ExtraArgs -and $ExtraArgs.Count -gt 0) {
        $argsList += $ExtraArgs
    }

    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
