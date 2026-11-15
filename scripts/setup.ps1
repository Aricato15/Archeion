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

Write-Host "== Registry"
$registry = Join-Path $RepoRoot 'registry'
if (Test-Path -LiteralPath $registry) {
    Write-Host "   registry\ exists; left as it is."
} else {
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'registry.example') -Destination $registry -Recurse
    Write-Host "   Created registry\ from registry.example\ (gitignored: your project details stay on this machine)."
    Write-Host "   Fill it with: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\archeion.ps1 projects scan --write"
}

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
Write-Host "Setup done. Next: start.bat, then create the admin password in the viewer."
exit 0
