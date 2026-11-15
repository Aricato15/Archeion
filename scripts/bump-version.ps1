# Changes a version everywhere it's recorded.
#   scripts\bump-version.ps1 -Part minor                  # the app (ADR 0005): 0.1.0 -> 0.2.0
#   scripts\bump-version.ps1 -Set 1.0.0
#   scripts\bump-version.ps1 -Target plugin -Part patch   # the Archeion plugin (ADR 0009)
param(
    [ValidateSet('app', 'plugin')][string]$Target = 'app',
    [ValidateSet('major', 'minor', 'patch')][string]$Part,
    [string]$Set
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

$semver = '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$'
$versionFile = Join-Path $RepoRoot 'VERSION'
$pluginJson = Join-Path $RepoRoot 'plugins\archeion\.claude-plugin\plugin.json'
$marketplaceJson = Join-Path $RepoRoot '.claude-plugin\marketplace.json'
$versionField = [regex]'"version"\s*:\s*"([^"]*)"'
if ($Target -eq 'plugin') {
    $m = $versionField.Match([IO.File]::ReadAllText($pluginJson))
    if (-not $m.Success) { throw "plugin.json has no version" }
    $current = $m.Groups[1].Value
} else {
    $current = (Get-Content -LiteralPath $versionFile -Raw).Trim()
}
if ($current -notmatch $semver) { throw "The $Target version is '$current', which isn't MAJOR.MINOR.PATCH" }

if ($Set) {
    if ($Set -notmatch $semver) { throw "'$Set' isn't MAJOR.MINOR.PATCH" }
    $new = $Set
} elseif ($Part) {
    $major, $minor, $patch = $current.Split('.') | ForEach-Object { [int]$_ }
    switch ($Part) {
        'major' { $major++; $minor = 0; $patch = 0 }
        'minor' { $minor++; $patch = 0 }
        'patch' { $patch++ }
    }
    $new = "$major.$minor.$patch"
} else {
    Write-Host "Current $Target version: $current. Pass -Part major|minor|patch or -Set X.Y.Z."
    exit 0
}

function Set-FileText([string]$Path, [string]$Text) {
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding $false))
}

function Add-ChangelogRelease([string]$Path, [string]$Version) {
    $log = [IO.File]::ReadAllText($Path)
    if ($log -notmatch [regex]::Escape("## [$Version]")) {
        $date = Get-Date -Format 'yyyy-MM-dd'
        $log = ([regex]'(?m)^## \[Unreleased\]\s*$').Replace($log, "## [Unreleased]`n`n## [$Version] - $date`n", 1)
        Set-FileText $Path $log
    }
}

if ($Target -eq 'plugin') {
    # plugin.json and the marketplace entry carry the same version; Claude Code uses it to
    # spot updates, so it changes whenever the plugin does (the commit hook checks this).
    foreach ($file in @($pluginJson, $marketplaceJson)) {
        $text = [IO.File]::ReadAllText($file)
        if (-not $versionField.IsMatch($text)) { throw "$file has no version field" }
        Set-FileText $file ($versionField.Replace($text, "`"version`": `"$new`"", 1))
    }
    Add-ChangelogRelease (Join-Path $RepoRoot 'plugins\archeion\CHANGELOG.md') $new
    Write-Host "Plugin version $current -> $new. Updated plugin.json, .claude-plugin/marketplace.json and plugins/archeion/CHANGELOG.md."
    Write-Host "Move the Unreleased notes under [$new], then commit as: chore(plugin): release $new"
    exit 0
}

Set-FileText $versionFile "$new`n"

$pyproject = Join-Path $BackendDir 'pyproject.toml'
$text = [IO.File]::ReadAllText($pyproject)
$text = ([regex]'(?m)^version = "[^"]*"').Replace($text, "version = `"$new`"", 1)
Set-FileText $pyproject $text

Push-Location $BackendDir
try { uv lock --quiet; if ($LASTEXITCODE -ne 0) { throw "uv lock failed" } } finally { Pop-Location }
Push-Location $FrontendDir
try {
    npm version $new --no-git-tag-version --allow-same-version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "npm version failed" }
} finally { Pop-Location }

Add-ChangelogRelease (Join-Path $RepoRoot 'CHANGELOG.md') $new

Write-Host "Version $current -> $new. Updated VERSION, pyproject.toml, uv.lock, package.json, package-lock.json and CHANGELOG.md."
Write-Host "Move the Unreleased notes under [$new], then commit as: chore(release): $new"
