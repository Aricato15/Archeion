# SessionStart hook: tells a new Claude Code session about open feedback. Silent when there's none,
# and when the backend isn't installed yet.
$ErrorActionPreference = 'SilentlyContinue'
. "$PSScriptRoot\common.ps1"

if (-not (Test-Path -LiteralPath $BackendPython)) { exit 0 }
Push-Location $BackendDir
try {
    $out = & $BackendPython -m app inbox count --project archeion 2>$null
} finally { Pop-Location }
$n = 0
if ([int]::TryParse(("$out").Trim(), [ref]$n) -and $n -gt 0) {
    $noun = if ($n -eq 1) { 'item' } else { 'items' }
    Write-Output "Archeion: $n open feedback $noun from the viewer. Run /inbox to work through them."
}
exit 0
