# Scans for things that must never be committed: secrets, absolute paths and
# personal information. Run by .githooks/pre-commit on the staged changes, or by hand:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .githooks/check-sensitive.ps1 -All
# A line that is a deliberate, harmless example can carry the marker: sensitive-ok
# A registered project's name that is also an ordinary term (an example name in a test, a Mermaid
# keyword) is a clash: the commit stops for the user to review it, see registry/reviewed-names.txt
# and docs/decisions/0007-keep-project-information-out-of-the-repo.md.
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
# Files that must never be committed, whatever they contain. registry/ is the private
# project registry (ADR 0007); only the template in registry.example/ is committed.
# backups/ holds local copies of the registry and the database.
$blockedFile = '^registry/|^backups/|(^|/)\.env$|(^|/)\.env\.(?!example$)[^/]+$|\.(db|sqlite3?)$|\.db-(wal|shm)$|\.(pem|key|pfx)$|(^|/)settings\.local\.json$|(^|/)CLAUDE\.local\.md$'

# Project names must not leak into committed text (ADR 0007). The list is built here, at
# commit time, from the private registry and the workspace's project folders, so the
# names themselves are never written into the repo.
$names = New-Object System.Collections.Generic.HashSet[string]([StringComparer]::OrdinalIgnoreCase)
$self = Split-Path -Leaf (Get-Location)
$registry = Join-Path (Get-Location) 'registry'
if (Test-Path -LiteralPath $registry) {
    foreach ($f in Get-ChildItem -LiteralPath $registry -Recurse -Filter *.md -File) {
        if ($f.Name -like '_*' -or $f.Name -eq 'README.md') { continue }
        if ($f.Directory.Name -in @('projects', 'groups')) { [void]$names.Add($f.BaseName) }
        foreach ($line in (Get-Content -LiteralPath $f.FullName -TotalCount 30 -Encoding UTF8)) {
            if ($line -match '^(name|title):\s*(.+?)\s*$') { [void]$names.Add($Matches[2].Trim('"', "'")) }
            elseif ($line -match '^path:\s*(.+?)\s*$') { [void]$names.Add((Split-Path -Leaf $Matches[1])) }
        }
    }
}
$workspace = Split-Path -Parent (Get-Location)
foreach ($d in Get-ChildItem -LiteralPath $workspace -Directory -ErrorAction SilentlyContinue) {
    if ($d.Name -notlike '_*' -and $d.Name -ne $self -and (Test-Path -LiteralPath (Join-Path $d.FullName 'CLAUDE.md'))) {
        [void]$names.Add($d.Name)
    }
}
$names.RemoveWhere([Predicate[string]] { param($n) $n.Length -lt 3 -or $n -in @($self, 'registry', 'example') }) | Out-Null
if ($names.Count -gt 0) {
    $alternation = ($names | Sort-Object Length -Descending | ForEach-Object { [regex]::Escape($_) }) -join '|'
    $patterns += @{ Kind = 'project name'; Re = "(?i)(?<![A-Za-z0-9])($alternation)(?![A-Za-z0-9])" }
}

$findings = New-Object System.Collections.Generic.List[string]
$nameHits = New-Object System.Collections.Generic.List[object]

function Test-Line([string]$file, [int]$num, [string]$text) {
    if ($text -match 'sensitive-ok') { return }
    foreach ($p in $patterns) {
        foreach ($m in [regex]::Matches($text, $p.Re)) {
            if ($p.Kind -eq 'personal info' -and $m.Value -match $emailOk) { continue }
            if ($p.Kind -eq 'project name') {
                $nameHits.Add(@{ File = $file; Num = $num; Value = $m.Value })
            } else {
                $findings.Add("  [$($p.Kind)] ${file}:${num}: $($m.Value)")
            }
            break
        }
    }
}

# Terms the user has reviewed: registry/reviewed-names.txt (private, gitignored), one per line,
# `name` (accepted anywhere) or `name path/to/file` (accepted only there). `#` starts a comment.
$reviewed = New-Object System.Collections.Generic.List[object]
$reviewFile = Join-Path $registry 'reviewed-names.txt'
if (Test-Path -LiteralPath $reviewFile) {
    foreach ($line in (Get-Content -LiteralPath $reviewFile -Encoding UTF8)) {
        $t = ($line -replace '#.*$', '').Trim()
        if (-not $t) { continue }
        $parts = $t -split '\s+', 2
        $reviewed.Add(@{ Name = $parts[0]; Path = $(if ($parts.Count -gt 1) { $parts[1].Replace('\', '/') } else { '' }) })
    }
}
function Test-Reviewed([string]$name, [string]$file) {
    foreach ($r in $reviewed) {
        if ($r.Name -ieq $name -and ($r.Path -eq '' -or $r.Path -ieq $file)) { return $true }
    }
    return $false
}
# Is the term already in the committed text? Then it is an ordinary word that also names a project
# (a clash to review). A name that was never committed is a leak, and is blocked.
$committedCache = @{}
function Test-Committed([string]$term) {
    $key = $term.ToLowerInvariant()
    if (-not $committedCache.ContainsKey($key)) {
        $hit = $false
        try {
            & git grep -qiwIF -e $term HEAD 2>$null | Out-Null
            $hit = ($LASTEXITCODE -eq 0)
        } catch { $hit = $false }
        $committedCache[$key] = $hit
    }
    return $committedCache[$key]
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

$clashes = New-Object System.Collections.Generic.List[string]
foreach ($h in $nameHits) {
    if (Test-Reviewed $h.Value $h.File) { continue }
    if (Test-Committed $h.Value) {
        $clashes.Add("  [name clash] $($h.File):$($h.Num): $($h.Value)")
    } else {
        $findings.Add("  [project name] $($h.File):$($h.Num): $($h.Value)")
    }
}

if ($findings.Count -gt 0) {
    [Console]::Error.WriteLine("BLOCKED: sensitive content found (secrets, absolute paths, personal info or project names):")
    $findings | ForEach-Object { [Console]::Error.WriteLine($_) }
    [Console]::Error.WriteLine("Move it to a gitignored .env, use a relative path, or remove it.")
    [Console]::Error.WriteLine("Project details belong in the private registry/ folder, not in committed files.")
    [Console]::Error.WriteLine("For a harmless example, put 'sensitive-ok' on that line.")
    if ($clashes.Count -gt 0) {
        [Console]::Error.WriteLine("Also, name clashes for the user to review (see below):")
        $clashes | ForEach-Object { [Console]::Error.WriteLine($_) }
    }
    exit 1
}
if ($clashes.Count -gt 0) {
    [Console]::Error.WriteLine("REVIEW NEEDED: these lines contain the name of a registered project, but the same word is already in committed text, so it may only be a clash (an example name, a keyword):")
    $clashes | ForEach-Object { [Console]::Error.WriteLine($_) }
    [Console]::Error.WriteLine("Show them to the user and let them decide. Don't approve them yourself.")
    [Console]::Error.WriteLine("To accept one, the user adds a line to registry/reviewed-names.txt: 'name' (anywhere) or 'name path/to/file' (only there).")
    [Console]::Error.WriteLine("Or change the line to use another name, or mark a harmless example with 'sensitive-ok'.")
    exit 1
}
exit 0
