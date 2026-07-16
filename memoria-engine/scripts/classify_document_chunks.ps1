[CmdletBinding()]
param(
    [string]$ChunkDir = "data\processed\documents",
    [string]$OutputDir = "data\processed\documents",
    [string]$OutputJson = "risultati\document_analysis\llm_chunk_classifications.json",
    [string]$OutputMd = "risultati\document_analysis\llm_chunk_classifications.md",
    [string]$ModelName = "",
    [string]$PromptVersion = "",
    [ValidateSet("", "fake", "ollama-wsl")]
    [string]$Provider = "",
    [string]$WslDistribution = "",
    [int]$TimeoutSeconds = 0
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
    $argsList = @(
        "-m", "caduti_fonti_report.document_analysis.llm_chunk_classifier",
        "--chunk-dir", $ChunkDir,
        "--output-dir", $OutputDir,
        "--output-json", $OutputJson,
        "--output-md", $OutputMd
    )
    if (-not [string]::IsNullOrWhiteSpace($ModelName)) {
        $argsList += @("--model-name", $ModelName)
    }
    if (-not [string]::IsNullOrWhiteSpace($PromptVersion)) {
        $argsList += @("--prompt-version", $PromptVersion)
    }
    if (-not [string]::IsNullOrWhiteSpace($Provider)) {
        $argsList += @("--provider", $Provider)
    }
    if (-not [string]::IsNullOrWhiteSpace($WslDistribution)) {
        $argsList += @("--wsl-distribution", $WslDistribution)
    }
    if ($TimeoutSeconds -gt 0) {
        $argsList += @("--timeout-seconds", "$TimeoutSeconds")
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
