# SessionStart hook: tells a project session about feedback waiting for it in Archeion.
# Silent when nothing is waiting, when Archeion can't be found, when this folder isn't a
# registered project, and inside Archeion itself (its own hook covers it).
$ErrorActionPreference = 'SilentlyContinue'
$launcher = Join-Path $PSScriptRoot 'archeion.ps1'

# A design package waiting to be consumed (Archeion ADR 0022): a handoff.json in .archeion/designs/<slug>/.
# It needs no Archeion, so it's checked first, and it only ever matches a project that was handed a design.
$packages = @(Get-ChildItem -LiteralPath (Join-Path (Get-Location).ProviderPath '.archeion\designs') -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'handoff.json') })
if ($packages.Count -gt 0) {
    $names = ($packages | ForEach-Object { $_.Name }) -join ', '
    Write-Output "Archeion: a design package is waiting in .archeion/designs/ ($names). Run /archeion:consume-design to turn it into this project's docs."
}

$where =& powershell -NoProfile -ExecutionPolicy Bypass -File $launcher --where 2>$null
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
