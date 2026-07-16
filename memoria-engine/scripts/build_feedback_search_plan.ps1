[CmdletBinding()]
param(
    [string]$ActionsJson = "risultati\document_analysis\research_feedback_actions.json",
    [string]$LinksJson = "",
    [Parameter(Mandatory = $true)]
    [string]$ProfilesIndex,
    [string]$SourcesYaml = "..\memoria-sources\registry\camalanca_fonti.yaml",
    [string]$OutputJson = "risultati\document_analysis\feedback_search_plan.json",
    [string]$OutputMd = "risultati\document_analysis\feedback_search_plan.md"
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
    if (-not [string]::IsNullOrWhiteSpace($LinksJson)) {
        & $pythonExe `
            -m caduti_fonti_report.document_analysis.feedback_search_plan `
            --actions-json $ActionsJson `
            --links-json $LinksJson `
            --profiles-index $ProfilesIndex `
            --sources-yaml $SourcesYaml `
            --output-json $OutputJson `
            --output-md $OutputMd
    } else {
        & $pythonExe `
            -m caduti_fonti_report.document_analysis.feedback_search_plan `
            --actions-json $ActionsJson `
            --profiles-index $ProfilesIndex `
            --sources-yaml $SourcesYaml `
            --output-json $OutputJson `
            --output-md $OutputMd
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
