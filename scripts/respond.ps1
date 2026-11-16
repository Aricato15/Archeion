# On-demand Claude (ADR 0020): answers Archeion's inbox once, then the window closes.
# Started by the backend in its own console window; not meant to be run by hand, though it can be:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\respond.ps1 -Log <file> [-AddDir <folder>]...
param(
    [Parameter(Mandatory = $true)][string]$Log,
    [string[]]$AddDir = @()
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"
Set-Location -LiteralPath $RepoRoot
$Host.UI.RawUI.WindowTitle = 'Archeion: on-demand Claude'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Nobody is there to approve commands: edits are accepted, and Archeion's own CLI and skills are
# allowed. Anything else (a project's tests, say) is refused, and Claude says so in its reply.
$cli = 'powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1:*'
$claudeArgs = @(
    '-p', '/inbox',
    '--permission-mode', 'acceptEdits',
    '--allowedTools', "Bash($cli)", "PowerShell($cli)", 'Skill', 'Read', 'Grep', 'Glob'
)
foreach ($dir in $AddDir) { $claudeArgs += @('--add-dir', $dir) }

Write-Host "On-demand Claude: answering the inbox. This window closes when it's done."
Write-Host "Log: $Log"
Write-Host ''
try {
    & claude @claudeArgs 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $Log
    $code = $LASTEXITCODE
} catch {
    "Failed to run claude: $_" | Tee-Object -FilePath $Log -Append
    $code = 1
}
Write-Host ''
Write-Host "Done (exit code $code). Closing in 10 seconds."
Start-Sleep -Seconds 10
exit $code
