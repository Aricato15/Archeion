# Starts the backend and the frontend dev server, each in its own window. Called by start.bat.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

$cfg = Get-ArcheionConfig
$backendPort = [int]$cfg.ARCHEION_PORT
$frontendPort = [int]$cfg.ARCHEION_FRONTEND_PORT
$problems = New-Object System.Collections.Generic.List[string]

if (-not (Test-Path -LiteralPath $BackendPython)) {
    $problems.Add("The backend environment is missing (app\backend\venv). Run setup.bat.")
}
if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules'))) {
    $problems.Add("The frontend dependencies are missing (app\frontend\node_modules). Run setup.bat.")
}
if ($problems.Count -eq 0) {
    Invoke-Backend password status | Out-Null
    if ($LASTEXITCODE -eq 3) {
        $problems.Add("No admin password is set. Run set_admin_password.bat first.")
    } elseif ($LASTEXITCODE -ne 0) {
        $problems.Add("The backend couldn't check the admin password (exit code $LASTEXITCODE).")
    }
}
foreach ($port in @($backendPort, $frontendPort)) {
    $pids = Get-ListeningProcessIds $port
    if ($pids.Count -gt 0) {
        $names = ($pids | ForEach-Object { (Get-Process -Id $_ -ErrorAction SilentlyContinue).ProcessName }) -join ', '
        $problems.Add("Port $port is already in use ($names). Is Archeion already running? Stop it with stop.bat.")
    }
}

if ($problems.Count -gt 0) {
    Write-Host "Archeion can't start yet:" -ForegroundColor Yellow
    $problems | ForEach-Object { Write-Host "  - $_" }
    exit 1
}

Start-Process -FilePath 'cmd.exe' -WorkingDirectory $BackendDir `
    -ArgumentList '/k', 'title Archeion backend && venv\Scripts\python.exe -m app serve'
Start-Process -FilePath 'cmd.exe' -WorkingDirectory $FrontendDir `
    -ArgumentList '/k', 'title Archeion frontend && npm run dev'

$version = (Get-Content -LiteralPath (Join-Path $RepoRoot 'VERSION') -Raw).Trim()
Write-Host "Archeion $version is starting in two windows."
Write-Host "  Open:     http://127.0.0.1:$frontendPort/"
Write-Host "  API:      http://127.0.0.1:$backendPort/api/health"
Write-Host "Stop both with stop.bat."
exit 0
