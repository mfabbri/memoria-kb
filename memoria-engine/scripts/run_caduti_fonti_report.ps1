[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Csv,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$systemPython = "python"

function Import-DotEnv {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return 0
    }

    $loadedCount = 0
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        if ($trimmed.StartsWith("export ")) {
            $trimmed = $trimmed.Substring(7).Trim()
        }

        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $name = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim()

        if (-not ($name -match "^[A-Za-z_][A-Za-z0-9_]*$")) {
            continue
        }

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
            $loadedCount += 1
        }
    }

    return $loadedCount
}

function Test-PythonHasYaml {
    param(
        [string]$PythonExe
    )

    try {
        $null = & $PythonExe -c "import yaml" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-PythonExe {
    if (Test-Path $venvPython) {
        if (Test-PythonHasYaml -PythonExe $venvPython) {
            return $venvPython
        }
    }

    if (Test-PythonHasYaml -PythonExe $systemPython) {
        return $systemPython
    }

    $venvInstallHint = Join-Path $repoRoot ".venv\\Scripts\\python.exe -m pip install PyYAML"
    $systemInstallHint = "python -m pip install PyYAML"
    $message = @(
        "Nessun interprete Python disponibile con il modulo 'yaml'.",
        "Installa PyYAML con uno di questi comandi:",
        "  $venvInstallHint",
        "  $systemInstallHint"
    ) -join [Environment]::NewLine
    throw $message
}

$pythonExe = Resolve-PythonExe
$resolvedPython = (& $pythonExe -c "import sys; print(sys.executable)")
Write-Host "Uso Python: $resolvedPython"

$envPath = Join-Path $repoRoot ".env"
$loadedEnvCount = Import-DotEnv -Path $envPath
if ($loadedEnvCount -gt 0) {
    Write-Host "Variabili caricate da .env: $loadedEnvCount"
}

$scriptPath = Join-Path $repoRoot "code\\caduti_fonti_report.py"
$csvPath = (Resolve-Path -LiteralPath $Csv).Path
$sourcesPath = Join-Path $repoRoot "..\memoria-sources\registry\camalanca_fonti.yaml"
$outputMdPath = Join-Path $repoRoot "risultati\\caduti_purocielo_fonti_report.md"
$outputJsonPath = Join-Path $repoRoot "risultati\\caduti_purocielo_fonti_report.json"
$outputDirPath = Join-Path $repoRoot "risultati\\caduti_purocielo_schede"

    & $pythonExe `
    $scriptPath `
    --csv $csvPath `
    --sources-yaml $sourcesPath `
    --output-md $outputMdPath `
    --output-json $outputJsonPath `
    --output-dir $outputDirPath `
    @ExtraArgs

exit $LASTEXITCODE
