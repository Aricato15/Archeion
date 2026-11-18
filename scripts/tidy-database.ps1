# Optional cleanup for a database that a pre-release 1.3.2 build touched (docs/updates/update-v1.3.2.md).
# Backs the database up, then drops its unused responder.bypass column. Stop Archeion first.
#   scripts\tidy-database.ps1
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

$cfg = Get-ArcheionConfig
$port = [int]$cfg['ARCHEION_PORT']
if ((Get-ListeningProcessIds $port).Count -gt 0) {
    Write-Host "The backend is running on port $port. Run stop.bat first." -ForegroundColor Red
    exit 1
}
$db = $cfg['ARCHEION_DB_PATH']
if (-not [IO.Path]::IsPathRooted($db)) { $db = Join-Path $RepoRoot $db }
& $BackendPython -I (Join-Path $PSScriptRoot 'tidy-database.py') $db
exit $LASTEXITCODE
