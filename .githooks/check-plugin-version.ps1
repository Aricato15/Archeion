# Pre-commit check (ADR 0009): a commit that changes the Archeion plugin must change its
# version too, because Claude Code only refreshes its cached copy of a plugin when the
# version changes. Bump it with scripts\bump-version.ps1 -Target plugin -Part patch.
$ErrorActionPreference = 'Continue'   # git show writes to stderr when the file is new

$plugin = 'plugins/archeion/'
$manifest = 'plugins/archeion/.claude-plugin/plugin.json'
$staged = @(git -c core.quotepath=off diff --cached --name-only --diff-filter=ACMRD)
$changed = @($staged | Where-Object { $_.StartsWith($plugin) })
if ($changed.Count -eq 0) { exit 0 }

function Get-Version([string]$Text) {
    if ($Text -match '"version"\s*:\s*"([^"]*)"') { return $Matches[1] }
    return $null
}

$before = git show "HEAD:$manifest" 2>$null
if ($LASTEXITCODE -ne 0 -or -not $before) { exit 0 }   # the plugin is new in this commit
$after = git show ":$manifest" 2>$null
$old = Get-Version ($before -join "`n")
$new = Get-Version ($after -join "`n")
if ($old -and $new -and $old -ne $new) { exit 0 }

[Console]::Error.WriteLine("BLOCKED: the Archeion plugin changed, but its version is still ${old}:")
$changed | Select-Object -First 10 | ForEach-Object { [Console]::Error.WriteLine("  $_") }
[Console]::Error.WriteLine("Claude Code only updates a plugin when its version changes. Run:")
[Console]::Error.WriteLine("  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\bump-version.ps1 -Target plugin -Part patch")
[Console]::Error.WriteLine("then note the change in plugins/archeion/CHANGELOG.md and stage the files again.")
exit 1
