# Stops whatever Archeion runs on its two ports. Only python and node processes are touched.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

$cfg = Get-ArcheionConfig
$targets = @(
    @{ Name = 'backend'; Port = [int]$cfg.ARCHEION_PORT; Allowed = @('python', 'pythonw', 'uvicorn') },
    @{ Name = 'frontend'; Port = [int]$cfg.ARCHEION_FRONTEND_PORT; Allowed = @('node') }
)

$stopped = 0
foreach ($t in $targets) {
    $pids = Get-ListeningProcessIds $t.Port
    if ($pids.Count -eq 0) {
        Write-Host "The $($t.Name) isn't running (nothing listens on port $($t.Port))."
        continue
    }
    foreach ($procId in $pids) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if (-not $proc) { continue }
        if ($t.Allowed -notcontains $proc.ProcessName.ToLower()) {
            Write-Host "Port $($t.Port) is held by $($proc.ProcessName) (PID $procId), which isn't Archeion's. Left it alone." -ForegroundColor Yellow
            continue
        }
        Stop-Process -Id $procId -Force
        Write-Host "Stopped the $($t.Name): $($proc.ProcessName) (PID $procId) on port $($t.Port)."
        $stopped++
    }
}
if ($stopped -gt 0) { Write-Host "You can close the two Archeion console windows." }
exit 0
