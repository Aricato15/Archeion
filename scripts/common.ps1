# Shared helpers for the root scripts. Dot-source it: . "$PSScriptRoot\common.ps1"

$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:BackendDir = Join-Path $RepoRoot 'app\backend'
$script:FrontendDir = Join-Path $RepoRoot 'app\frontend'
$script:BackendPython = Join-Path $BackendDir 'venv\Scripts\python.exe'

# The backend venv lives in app/backend/venv (ADR 0004), not uv's default .venv.
$env:UV_PROJECT_ENVIRONMENT = 'venv'

function Get-SettingsSchema {
    # The single list of .env settings (scripts/settings.schema.json).
    $path = Join-Path $PSScriptRoot 'settings.schema.json'
    return (Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Read-EnvFile([string]$Path) {
    # KEY=value lines of a .env file, in order. Comments and blank lines are skipped.
    $values = [ordered]@{}
    if (Test-Path -LiteralPath $Path) {
        foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
            if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
                $value = $Matches[2]
                if ($value -match '^"(.*)"$') {
                    $value = $Matches[1] -replace '\\"', '"'
                } elseif ($value -match "^'(.*)'$") {
                    $value = $Matches[1]
                } else {
                    $value = $value -replace '\s+#.*$', ''
                }
                $values[$Matches[1]] = $value
            }
        }
    }
    return $values
}

function Get-ArcheionConfig {
    # Schema defaults, overridden by the repo-root .env (if it exists).
    $cfg = @{}
    foreach ($g in (Get-SettingsSchema).groups) {
        foreach ($s in $g.settings) { $cfg[$s.name] = [string]$s.default }
    }
    $fromFile = Read-EnvFile (Join-Path $RepoRoot '.env')
    foreach ($k in $fromFile.Keys) { $cfg[$k] = $fromFile[$k] }
    return $cfg
}

function Get-ListeningProcessIds([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return @() }
    return @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Invoke-Backend {
    # Runs `python -m app <args>` from app/backend with the venv's python.
    # Its output flows through; read $LASTEXITCODE afterwards for the exit code.
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CliArgs)
    # inbox --here needs the folder the caller ran in, not app/backend.
    $env:ARCHEION_CALLER_DIR = (Get-Location).ProviderPath
    Push-Location $BackendDir
    try {
        & $BackendPython -m app @CliArgs
    } finally {
        Pop-Location
    }
}
