# Scans for things that must never be committed: secrets, absolute paths and
# personal information. Run by .githooks/pre-commit on the staged changes, or by hand:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .githooks/check-sensitive.ps1 -All
# A line that is a deliberate, harmless example can carry the marker: sensitive-ok
# See docs/decisions/0003-track-on-github-keep-configuration-out.md.
param([switch]$All)

$ErrorActionPreference = 'Stop'
Set-Location (git rev-parse --show-toplevel)

$patterns = @(
    @{ Kind = 'secret';        Re = 'sk-ant-[A-Za-z0-9_-]{10,}' },
    @{ Kind = 'secret';        Re = '\bsk-[A-Za-z0-9]{32,}' },
    @{ Kind = 'secret';        Re = '\bgh[pousr]_[A-Za-z0-9]{20,}' },
    @{ Kind = 'secret';        Re = 'github_pat_[A-Za-z0-9_]{20,}' },
    @{ Kind = 'secret';        Re = '\bAKIA[0-9A-Z]{16}\b' },
    @{ Kind = 'secret';        Re = '-----BEGIN [A-Z ]*PRIVATE KEY-----' },
    @{ Kind = 'secret';        Re = '(?i)\b(api[_-]?key|secret|token|passw(or)?d)["'']?\s*[:=]\s*["'']?[A-Za-z0-9/+_.=-]{8,}' },
    @{ Kind = 'absolute path'; Re = '(?<![A-Za-z0-9])[A-Za-z]:[\\/][A-Za-z0-9_.$ -]' },
    @{ Kind = 'absolute path'; Re = '/(Users|home)/[A-Za-z0-9._-]+' },
    @{ Kind = 'personal info'; Re = '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' }
)
# Emails that are fine to commit.
$emailOk = '@(example\.(com|org|net)|users\.noreply\.github\.com|anthropic\.com)$'
# Files that must never be committed, whatever they contain.
$blockedFile = '(^|/)\.env$|(^|/)\.env\.(?!example$)[^/]+$|\.(db|sqlite3?)$|\.db-(wal|shm)$|\.(pem|key|pfx)$|(^|/)settings\.local\.json$|(^|/)CLAUDE\.local\.md$'

$findings = New-Object System.Collections.Generic.List[string]

function Test-Line([string]$file, [int]$num, [string]$text) {
    if ($text -match 'sensitive-ok') { return }
    foreach ($p in $patterns) {
        foreach ($m in [regex]::Matches($text, $p.Re)) {
            if ($p.Kind -eq 'personal info' -and $m.Value -match $emailOk) { continue }
            $findings.Add("  [$($p.Kind)] ${file}:${num}: $($m.Value)")
            break
        }
    }
}

if ($All) {
    $files = @(git ls-files)
    foreach ($f in $files) {
        if ($f -match $blockedFile) { $findings.Add("  [blocked file] $f"); continue }
        if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { continue }
        $bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $f))
        if ($bytes -contains 0) { continue }   # binary
        $lines = [Text.Encoding]::UTF8.GetString($bytes) -split "`r?`n"
        for ($i = 0; $i -lt $lines.Count; $i++) { Test-Line $f ($i + 1) $lines[$i] }
    }
} else {
    foreach ($f in @(git diff --cached --name-only --diff-filter=ACMR)) {
        if ($f -match $blockedFile) { $findings.Add("  [blocked file] $f") }
    }
    $file = ''; $num = 0
    foreach ($line in @(git -c core.quotepath=off diff --cached -U0 --diff-filter=ACMR --no-color)) {
        if ($line -match '^\+\+\+ b/(.*)$') { $file = $Matches[1]; continue }
        if ($line -match '^@@ -\S+ \+(\d+)') { $num = [int]$Matches[1]; continue }
        if ($line.StartsWith('+')) { Test-Line $file $num $line.Substring(1); $num++ }
    }
}

if ($findings.Count -gt 0) {
    [Console]::Error.WriteLine("BLOCKED: sensitive content found (secrets, absolute paths or personal info):")
    $findings | ForEach-Object { [Console]::Error.WriteLine($_) }
    [Console]::Error.WriteLine("Move it to a gitignored .env, use a relative path, or remove it.")
    [Console]::Error.WriteLine("For a harmless example, put 'sensitive-ok' on that line.")
    exit 1
}
exit 0
