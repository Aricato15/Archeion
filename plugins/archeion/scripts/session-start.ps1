# SessionStart hook: tells a project session about feedback waiting for it in Archeion.
# Silent when nothing is waiting, when Archeion can't be found, when this folder isn't a
# registered project, and inside Archeion itself (its own hook covers it).
$ErrorActionPreference = 'SilentlyContinue'
$launcher = Join-Path $PSScriptRoot 'archeion.ps1'

$where = & powershell -NoProfile -ExecutionPolicy Bypass -File $launcher --where 2>$null
if ($LASTEXITCODE -ne 0 -or "$where" -notmatch ' at (.+)$') { exit 0 }
$archeionHome = $Matches[1].Trim().TrimEnd('\')
$here = (Get-Location).ProviderPath.TrimEnd('\')
if ($here -eq $archeionHome -or $here.StartsWith("$archeionHome\", [StringComparison]::OrdinalIgnoreCase)) { exit 0 }

$out = & powershell -NoProfile -ExecutionPolicy Bypass -File $launcher inbox count --here 2>$null
$n = 0
if ($LASTEXITCODE -eq 0 -and [int]::TryParse(("$out").Trim(), [ref]$n) -and $n -gt 0) {
    $noun = if ($n -eq 1) { 'item' } else { 'items' }
    Write-Output "Archeion: $n open feedback $noun for this project, written in the viewer. Run /archeion:inbox to work through them."
}
exit 0
