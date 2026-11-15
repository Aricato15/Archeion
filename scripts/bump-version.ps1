# Changes the app version everywhere it's recorded (ADR 0005).
#   scripts\bump-version.ps1 -Part minor      # 0.1.0 -> 0.2.0
#   scripts\bump-version.ps1 -Set 1.0.0
param(
    [ValidateSet('major', 'minor', 'patch')][string]$Part,
    [string]$Set
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

$semver = '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$'
$versionFile = Join-Path $RepoRoot 'VERSION'
$current = (Get-Content -LiteralPath $versionFile -Raw).Trim()
if ($current -notmatch $semver) { throw "VERSION holds '$current', which isn't MAJOR.MINOR.PATCH" }

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
    Write-Host "Current version: $current. Pass -Part major|minor|patch or -Set X.Y.Z."
    exit 0
}

function Set-FileText([string]$Path, [string]$Text) {
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding $false))
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

$changelog = Join-Path $RepoRoot 'CHANGELOG.md'
$log = [IO.File]::ReadAllText($changelog)
if ($log -notmatch [regex]::Escape("## [$new]")) {
    $date = Get-Date -Format 'yyyy-MM-dd'
    $log = ([regex]'(?m)^## \[Unreleased\]\s*$').Replace($log, "## [Unreleased]`n`n## [$new] - $date", 1)
    Set-FileText $changelog $log
}

Write-Host "Version $current -> $new. Updated VERSION, pyproject.toml, uv.lock, package.json, package-lock.json and CHANGELOG.md."
Write-Host "Move the Unreleased notes under [$new], then commit as: chore(release): $new"
