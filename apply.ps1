param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadRoot = Join-Path $PackageRoot "payload"
$TargetRoot = [System.IO.Path]::GetFullPath($TargetRoot)

if (-not (Test-Path $TargetRoot -PathType Container)) {
    throw "Repository non trovato: $TargetRoot"
}
if (-not (Test-Path (Join-Path $TargetRoot "memoria-bootstrap") -PathType Container)) {
    throw "La destinazione non sembra la radice di me.mo.ri.a-kb: manca memoria-bootstrap"
}

$Files = Get-ChildItem -Path $PayloadRoot -Recurse -File
if ($Files.Count -eq 0) { throw "Payload vuoto" }

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $TargetRoot ".codex-migration-backup\discovery-fix-$Timestamp"

foreach ($File in $Files) {
    $Relative = [System.IO.Path]::GetRelativePath($PayloadRoot, $File.FullName)
    $Destination = Join-Path $TargetRoot $Relative
    $Exists = Test-Path $Destination -PathType Leaf
    $Action = if ($Exists) { "UPDATE" } else { "CREATE" }
    Write-Host "$Action $Relative"

    if ($DryRun) { continue }

    if ($Exists) {
        $BackupFile = Join-Path $BackupRoot $Relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $BackupFile) | Out-Null
        Copy-Item -LiteralPath $Destination -Destination $BackupFile -Force
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    Copy-Item -LiteralPath $File.FullName -Destination $Destination -Force
}

if ($DryRun) {
    Write-Host "Dry run completato: nessun file modificato"
} else {
    if (Test-Path $BackupRoot) { Write-Host "Backup: $BackupRoot" }
    Write-Host "Correzione discovery Codex applicata"
    Write-Host "Riavvia Codex dalla radice del repository per ricaricare skill e configurazione"
}
