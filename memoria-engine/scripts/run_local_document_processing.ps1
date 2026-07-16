[CmdletBinding()]
param(
    [string]$RootDir = "data\raw",
    [string]$ProcessedDir = "data\processed\documents",
    [Alias("RemoteResultsDir")]
    [string]$ResultsDir = "risultati",
    [string]$ResearchDir = "ricerche",
    [string]$GlossaryDir = "",
    [string]$RunId = "",
    [switch]$RunOcr,
    [switch]$ForceDerived,
    [switch]$ForceOcr,
    [switch]$PreprocessBeforeOcr,
    [switch]$EnableRegionOcr,
    [string]$OcrLanguage = "ita",
    [string]$TesseractPath = "tesseract",
    [string]$PageSegmentationMode = "",
    [string]$EngineMode = "",
    [string]$Dpi = "",
    [int]$OcrMaxWorkers = 2,
    [int]$OcrProgressEvery = 25,
    [int]$MaxChars = 4500,
    [int]$OverlapChars = 300,
    [int]$MinLanguageTextChars = 40,
    [switch]$EnableLlmChunkClassification,
    [ValidateSet("", "fake", "ollama-wsl")]
    [string]$LlmChunkProvider = "",
    [string]$LlmChunkModelName = "",
    [string]$LlmChunkPromptVersion = "",
    [string]$LlmChunkWslDistribution = "",
    [int]$LlmChunkTimeoutSeconds = 0
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
        "-m", "caduti_fonti_report.document_analysis.local_processing_runner",
        "--root-dir", $RootDir,
        "--processed-dir", $ProcessedDir,
        "--results-dir", $ResultsDir,
        "--research-dir", $ResearchDir,
        "--max-chars", "$MaxChars",
        "--overlap-chars", "$OverlapChars",
        "--min-language-text-chars", "$MinLanguageTextChars"
    )
    if (-not [string]::IsNullOrWhiteSpace($RunId)) {
        $argsList += @("--run-id", $RunId)
    }
    if (-not [string]::IsNullOrWhiteSpace($GlossaryDir)) {
        $argsList += @("--glossary-dir", $GlossaryDir)
    }
    if ($RunOcr) {
        $argsList += "--run-ocr"
    }
    if ($ForceDerived) {
        $argsList += "--force-derived"
    }
    if ($ForceOcr) {
        $argsList += "--force-ocr"
    }
    if ($PreprocessBeforeOcr) {
        $argsList += "--preprocess-before-ocr"
    }
    if ($EnableRegionOcr) {
        $argsList += "--enable-region-ocr"
    }
    if (-not [string]::IsNullOrWhiteSpace($OcrLanguage)) {
        $argsList += @("--ocr-language", $OcrLanguage)
    }
    if (-not [string]::IsNullOrWhiteSpace($TesseractPath)) {
        $argsList += @("--tesseract-path", $TesseractPath)
    }
    if (-not [string]::IsNullOrWhiteSpace($PageSegmentationMode)) {
        $argsList += @("--psm", $PageSegmentationMode)
    }
    if (-not [string]::IsNullOrWhiteSpace($EngineMode)) {
        $argsList += @("--oem", $EngineMode)
    }
    if (-not [string]::IsNullOrWhiteSpace($Dpi)) {
        $argsList += @("--dpi", $Dpi)
    }
    if ($OcrMaxWorkers -gt 0) {
        $argsList += @("--ocr-max-workers", "$OcrMaxWorkers")
    }
    if ($OcrProgressEvery -gt 0) {
        $argsList += @("--ocr-progress-every", "$OcrProgressEvery")
    }
    if ($EnableLlmChunkClassification) {
        $argsList += "--enable-llm-chunk-classification"
    }
    if (-not [string]::IsNullOrWhiteSpace($LlmChunkProvider)) {
        $argsList += @("--llm-chunk-provider", $LlmChunkProvider)
    }
    if (-not [string]::IsNullOrWhiteSpace($LlmChunkModelName)) {
        $argsList += @("--llm-chunk-model-name", $LlmChunkModelName)
    }
    if (-not [string]::IsNullOrWhiteSpace($LlmChunkPromptVersion)) {
        $argsList += @("--llm-chunk-prompt-version", $LlmChunkPromptVersion)
    }
    if (-not [string]::IsNullOrWhiteSpace($LlmChunkWslDistribution)) {
        $argsList += @("--llm-chunk-wsl-distribution", $LlmChunkWslDistribution)
    }
    if ($LlmChunkTimeoutSeconds -gt 0) {
        $argsList += @("--llm-chunk-timeout-seconds", "$LlmChunkTimeoutSeconds")
    }
    & $pythonExe @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}
