# Installs the backend venv and the frontend node_modules, inside the project. Called by setup.bat.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

foreach ($tool in @('uv', 'npm', 'git')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "$tool isn't installed or isn't on PATH. Install it and run setup.bat again." -ForegroundColor Red
        exit 1
    }
}

Write-Host "== Backend: uv sync (app\backend\venv)"
Push-Location $BackendDir
try {
    uv sync --frozen
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
} finally { Pop-Location }

Write-Host "== Frontend: npm ci (app\frontend\node_modules)"
Push-Location $FrontendDir
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
} finally { Pop-Location }

Write-Host "== Settings"
& (Join-Path $PSScriptRoot 'configure.ps1') -ExampleOnly
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.env'))) {
    Write-Host "   No .env yet: the defaults apply. Run configure.bat to change ports or other settings."
}

$hooks = git -C $RepoRoot config --get core.hooksPath
if ($hooks -ne '.githooks') {
    Write-Host ""
    Write-Host "Note: the sensitive-content commit check isn't active in this clone. Turn it on with:" -ForegroundColor Yellow
    Write-Host "  git config core.hooksPath .githooks"
}

Write-Host ""
Write-Host "Setup done. Next: set_admin_password.bat (once), then start.bat."
exit 0
