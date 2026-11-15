# Runs Archeion's command-line interface from a project session:
#   archeion.ps1 <command> [args]     e.g.  archeion.ps1 inbox list --here
#   archeion.ps1 --where              prints where Archeion is and its version
#
# Claude Code runs this plugin from a cached copy, not from the Archeion repo, so this
# script finds Archeion itself (ADR 0009), in this order:
#   1. ARCHEION_HOME, if set (put it in the "env" of your user-level Claude Code settings)
#   2. the folder the "archeion" marketplace was added from (a directory marketplace)
#   3. ../archeion, next to the current project
# The command runs in the current folder, so `--here` means the project this session is in.
$ErrorActionPreference = 'Stop'

# The oldest Archeion whose command-line interface this plugin works with.
$MinArcheion = '0.4.0'

function Test-ArcheionHome([string]$Dir) {
    return [bool]($Dir -and (Test-Path -LiteralPath (Join-Path $Dir 'scripts\archeion.ps1')) -and (Test-Path -LiteralPath (Join-Path $Dir 'VERSION')))
}

function Find-ArcheionHome {
    if (Test-ArcheionHome $env:ARCHEION_HOME) { return (Resolve-Path -LiteralPath $env:ARCHEION_HOME).Path }
    $config = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
    $known = Join-Path $config 'plugins\known_marketplaces.json'
    if (Test-Path -LiteralPath $known) {
        try {
            $entry = (Get-Content -LiteralPath $known -Raw -Encoding UTF8 | ConvertFrom-Json).archeion
            if ($entry -and $entry.source.source -eq 'directory') {
                foreach ($dir in @($entry.installLocation, $entry.source.path)) {
                    if (Test-ArcheionHome $dir) { return (Resolve-Path -LiteralPath $dir).Path }
                }
            }
        } catch { }
    }
    $sibling = Join-Path (Get-Location).ProviderPath '..\archeion'
    if (Test-ArcheionHome $sibling) { return (Resolve-Path -LiteralPath $sibling).Path }
    return $null
}

$archeionHome = Find-ArcheionHome
if (-not $archeionHome) {
    [Console]::Error.WriteLine("Can't find Archeion. Set ARCHEION_HOME to its folder (in the `"env`" of your user-level Claude Code settings), or add it as the `"archeion`" plugin marketplace.")
    exit 2
}

$version = (Get-Content -LiteralPath (Join-Path $archeionHome 'VERSION') -Raw).Trim()
$parsed = $null
if (-not [version]::TryParse($version, [ref]$parsed) -or $parsed -lt [version]$MinArcheion) {
    [Console]::Error.WriteLine("Archeion $version is older than this plugin needs ($MinArcheion or later). Update Archeion (pull it and run setup.bat), or use an older version of the plugin.")
    exit 3
}

if ($args.Count -ge 1 -and $args[0] -eq '--where') {
    Write-Output "Archeion $version at $archeionHome"
    exit 0
}

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $archeionHome 'scripts\archeion.ps1') @args
exit $LASTEXITCODE
