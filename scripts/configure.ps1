# Interactive .env editor. Called by configure.bat.
# Every setting comes from scripts/settings.schema.json, so a new setting only needs a schema entry.
#
#   configure.ps1                 prompt for each setting (Enter keeps the shown value), then write .env
#   configure.ps1 -Defaults       no prompts: keep current values, fill the rest with defaults
#   configure.ps1 -ExampleOnly    only regenerate .env.example from the schema
#   -OutDir <dir>                 write the files somewhere else (for testing)
#
# .env.example is regenerated on every run, so it never drifts from the schema.
param(
    [switch]$Defaults,
    [switch]$ExampleOnly,
    [string]$OutDir
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

if (-not $OutDir) { $OutDir = $RepoRoot }
$envPath = Join-Path $OutDir '.env'
$examplePath = Join-Path $OutDir '.env.example'
$schema = Get-SettingsSchema
$utf8 = New-Object Text.UTF8Encoding $false
$inv = [Globalization.CultureInfo]::InvariantCulture

function Test-Value($s, [string]$value) {
    # Returns an error message, or $null when the value is fine.
    if ($value -match '[\r\n]') { return 'must be a single line' }
    switch ($s.type) {
        'port' {
            $n = 0
            if (-not [int]::TryParse($value, [ref]$n) -or $n -lt 1024 -or $n -gt 65535) { return 'must be a whole number from 1024 to 65535' }
            if ($s.range -and ($n -lt $s.range[0] -or $n -gt $s.range[1])) {
                return "must be in the workspace range $($s.range[0])-$($s.range[1]) (see ../CLAUDE.md)"
            }
        }
        'int' {
            $n = 0
            if (-not [int]::TryParse($value, [ref]$n)) { return 'must be a whole number' }
            if ($null -ne $s.min -and $n -lt $s.min) { return "must be at least $($s.min)" }
        }
        'number' {
            $d = 0.0
            if (-not [double]::TryParse($value, [Globalization.NumberStyles]::Float, $inv, [ref]$d)) { return 'must be a number (use . for decimals)' }
            if ($null -ne $s.min -and $d -lt $s.min) { return "must be at least $($s.min)" }
        }
        'host' {
            if ($value -notmatch '^[A-Za-z0-9.:-]+$') { return 'must be a host name or IP address' }
        }
        'relpath' {
            if ($value -match '^[A-Za-z]:' -or $value -match '^[\\/]') { return 'must be relative to the repo root (no drive letter, no leading slash)' }
            if (($value -replace '\\', '/').Split('/') -contains '..') { return "must stay inside the repo (no '..')" }
        }
        'string' {
            if ($value -match '#') { return "can't contain '#'" }
        }
    }
    return $null
}

function Format-EnvValue($s, [string]$value) {
    if ($s.type -eq 'relpath') { $value = $value -replace '\\', '/' }
    if ($value -match '[\s#"]') { return '"' + ($value -replace '"', '\"') + '"' }
    return $value
}

function Write-Example {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('# Generated from scripts/settings.schema.json by configure.bat. Do not edit by hand:')
    $lines.Add('# change the schema and run configure.bat (or scripts\configure.ps1 -ExampleOnly).')
    $lines.Add('# Copy to .env (gitignored), or run configure.bat to create .env interactively.')
    $lines.Add('# Paths are relative to the repo root. Never put secrets or absolute paths in this file.')
    foreach ($g in $schema.groups) {
        $lines.Add('')
        $lines.Add("# --- $($g.title)")
        foreach ($s in $g.settings) {
            $lines.Add("# $($s.description)")
            if ($s.type -eq 'secret') {
                $lines.Add("$($s.name)=")
            } else {
                $lines.Add("$($s.name)=$(Format-EnvValue $s ([string]$s.default))")
            }
        }
    }
    [IO.File]::WriteAllText($examplePath, (($lines -join "`n") + "`n"), $utf8)
}

Write-Example
Write-Host "Wrote $([IO.Path]::GetFileName($examplePath)) from the schema."
if ($ExampleOnly) { exit 0 }

# Current values: what's in .env now, else the defaults.
$current = Read-EnvFile $envPath
$known = @{}
$values = [ordered]@{}
foreach ($g in $schema.groups) {
    foreach ($s in $g.settings) {
        $known[$s.name] = $true
        $values[$s.name] = if ($current.Contains($s.name)) { $current[$s.name] } else { [string]$s.default }
    }
}

if (-not $Defaults) {
    Write-Host ''
    Write-Host 'Archeion settings. Press Enter to keep the value in [brackets].' -ForegroundColor Cyan
    foreach ($g in $schema.groups) {
        Write-Host ''
        Write-Host "== $($g.title)" -ForegroundColor Cyan
        foreach ($s in $g.settings) {
            Write-Host "  $($s.description)" -ForegroundColor DarkGray
            while ($true) {
                if ($s.type -eq 'secret') {
                    $shown = if ($values[$s.name]) { 'set, Enter keeps it' } else { 'not set' }
                    $secure = Read-Host "  $($s.name) [$shown]" -AsSecureString
                    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
                    try { $answer = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
                    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
                } else {
                    $answer = Read-Host "  $($s.name) [$($values[$s.name])]"
                }
                $answer = "$answer".Trim()
                if ($answer -eq '') { $answer = $values[$s.name] }
                $problem = if ($answer -eq '' -and $s.type -eq 'secret') { $null } else { Test-Value $s $answer }
                if ($problem) { Write-Host "  $($s.name) $problem. Try again." -ForegroundColor Yellow; continue }
                if ($s.type -eq 'host' -and $answer -eq '0.0.0.0') {
                    Write-Host '  Note: 0.0.0.0 exposes the backend to your network. Login is still required.' -ForegroundColor Yellow
                }
                $values[$s.name] = $answer
                break
            }
        }
    }
}

# Checks across settings.
$errors = New-Object System.Collections.Generic.List[string]
foreach ($g in $schema.groups) {
    foreach ($s in $g.settings) {
        $v = $values[$s.name]
        if ($s.type -eq 'secret' -and $v -eq '') { continue }
        $problem = Test-Value $s $v
        if ($problem) { $errors.Add("$($s.name) $problem (value: $v)") }
    }
}
if ($values['ARCHEION_PORT'] -eq $values['ARCHEION_FRONTEND_PORT']) {
    $errors.Add('ARCHEION_PORT and ARCHEION_FRONTEND_PORT must differ')
}
if ($errors.Count -gt 0) {
    Write-Host 'Not written, because:' -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  - $_" }
    exit 1
}

# Build .env: schema settings first, then any other lines the old .env had, unchanged.
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('# Written by configure.bat. Machine-specific and gitignored: never commit this file.')
foreach ($g in $schema.groups) {
    $lines.Add('')
    $lines.Add("# --- $($g.title)")
    foreach ($s in $g.settings) {
        $lines.Add("$($s.name)=$(Format-EnvValue $s $values[$s.name])")
    }
}
$extra = @($current.Keys | Where-Object { -not $known.ContainsKey($_) })
if ($extra.Count -gt 0) {
    $lines.Add('')
    $lines.Add('# --- Other settings (not in the schema, kept as they were)')
    foreach ($k in $extra) { $lines.Add("$k=$($current[$k])") }
}
$text = ($lines -join "`n") + "`n"

if (-not $Defaults) {
    Write-Host ''
    Write-Host 'Summary:' -ForegroundColor Cyan
    foreach ($g in $schema.groups) {
        foreach ($s in $g.settings) {
            $shown = if ($s.type -eq 'secret') { if ($values[$s.name]) { '(set)' } else { '(not set)' } } else { $values[$s.name] }
            Write-Host "  $($s.name) = $shown"
        }
    }
    $ok = Read-Host 'Write these to .env? [Y/n]'
    if ($ok -and $ok.Trim().ToLower() -notin @('y', 'yes')) {
        Write-Host 'Nothing written.'
        exit 0
    }
}

if (Test-Path -LiteralPath $envPath) {
    Copy-Item -LiteralPath $envPath -Destination "$envPath.bak" -Force
    Write-Host 'Kept the previous .env as .env.bak (gitignored).'
}
[IO.File]::WriteAllText($envPath, $text, $utf8)
Write-Host 'Wrote .env. Restart Archeion (stop.bat, then start.bat) for changes to take effect.' -ForegroundColor Green
exit 0
