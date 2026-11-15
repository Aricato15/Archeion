# Runs the backend CLI: scripts\archeion.ps1 <command> [args]
#   e.g. scripts\archeion.ps1 inbox list      (used by the /inbox skill)
#        scripts\archeion.ps1 password status
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

if (-not (Test-Path -LiteralPath $BackendPython)) {
    [Console]::Error.WriteLine("The backend environment is missing (app\backend\venv). Run setup.bat.")
    exit 1
}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Invoke-Backend @args
exit $LASTEXITCODE
