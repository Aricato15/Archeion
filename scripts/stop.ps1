# Stops Archeion: the servers on its two ports and the console windows start.bat opened.
# Each server first gets Ctrl+C, then Ctrl+Break, so it can shut down cleanly (the backend
# runs its lifespan shutdown: watchers stop, open requests finish). Only if it hasn't exited
# in time is it killed. Then its window is closed, and the port is checked to be free.
# Only python/node listeners and cmd windows titled by start.bat are touched.
# Exit code: 0 when everything is stopped, 1 when something is still running.
param([int]$GracefulSeconds = 10)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\common.ps1"

$cfg = Get-ArcheionConfig
$targets = @(
    @{ Name = 'backend'; Port = [int]$cfg.ARCHEION_PORT; Allowed = @('python', 'pythonw', 'uvicorn') },
    @{ Name = 'frontend'; Port = [int]$cfg.ARCHEION_FRONTEND_PORT; Allowed = @('node') }
)

function Get-ProcessTable {
    $table = @{}
    foreach ($p in Get-CimInstance Win32_Process) { $table[[int]$p.ProcessId] = $p }
    return $table
}

function Get-Ancestors($Table, [int]$ProcId) {
    # Parent chain, skipping a parent whose PID was reused by a process younger than the child.
    $chain = @()
    $cur = $Table[$ProcId]
    while ($cur) {
        $parent = $Table[[int]$cur.ParentProcessId]
        if (-not $parent -or $parent.ProcessId -eq $cur.ProcessId -or $parent.CreationDate -gt $cur.CreationDate) { break }
        $chain += $parent
        $cur = $parent
    }
    return $chain
}

function Get-Descendants($Table, [int]$ProcId) {
    $out = @()
    foreach ($p in $Table.Values) {
        if ([int]$p.ParentProcessId -eq $ProcId -and $p.ProcessId -ne $ProcId -and $p.CreationDate -ge $Table[$ProcId].CreationDate) {
            $out += Get-Descendants $Table ([int]$p.ProcessId)
            $out += $p
        }
    }
    return $out   # deepest first
}

function Test-ArcheionWindow($Proc, [string]$Name) {
    return $Proc.Name -eq 'cmd.exe' -and $Proc.CommandLine -and $Proc.CommandLine.Contains("title Archeion $Name")
}

function Find-Windows($Table, $Target, [int[]]$ServerPids) {
    # The windows start.bat opened: tagged with name and port, or (older windows) an
    # Archeion-titled cmd that is an ancestor of the server.
    $found = @{}
    $tag = "title Archeion $($Target.Name) [port $($Target.Port)]"
    foreach ($p in $Table.Values) {
        if ($p.Name -eq 'cmd.exe' -and $p.CommandLine -and $p.CommandLine.Contains($tag)) { $found[[int]$p.ProcessId] = $p }
    }
    foreach ($procId in $ServerPids) {
        $win = Get-Ancestors $Table $procId | Where-Object { Test-ArcheionWindow $_ $Target.Name } | Select-Object -First 1
        if ($win) { $found[[int]$win.ProcessId] = $win }
    }
    return @($found.Values)
}

function Wait-Stopped([int]$Port, [int[]]$Pids, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $alive = @($Pids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
        if ($alive.Count -eq 0 -and (Get-ListeningProcessIds $Port).Count -eq 0) { return $true }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Send-CtrlEvent([int]$ProcId, [switch]$Break) {
    $ps = (Get-Process -Id $PID).Path
    $helper = Join-Path $PSScriptRoot 'send-ctrl-c.ps1'
    $argv = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$helper`"", '-ProcessId', $ProcId)
    if ($Break) { $argv += '-Break' }
    $p = Start-Process -FilePath $ps -WindowStyle Hidden -Wait -PassThru -ArgumentList $argv
    # Ctrl+Break ends the helper as well, so its exit code says nothing then.
    return $Break -or $p.ExitCode -eq 0
}

function Request-Shutdown([int[]]$Pids, [int]$Port, [int]$Seconds) {
    # Ctrl+C, then Ctrl+Break for whatever ignored it. True when everything exited in time.
    $first = [Math]::Min(3, $Seconds)
    foreach ($procId in $Pids) { [void](Send-CtrlEvent $procId) }
    if (Wait-Stopped $Port $Pids $first) { return $true }
    $alive = @($Pids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
    foreach ($procId in $alive) { [void](Send-CtrlEvent $procId -Break) }
    return (Wait-Stopped $Port $Pids ([Math]::Max(1, $Seconds - $first)))
}

function Stop-Tree($Table, [int]$ProcId) {
    # The process and everything it started, children first.
    foreach ($p in @(Get-Descendants $Table $ProcId) + @($Table[$ProcId])) {
        if ($p) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    }
}

# Never close the window this script itself runs in.
$self = @{}
foreach ($a in Get-Ancestors (Get-ProcessTable) $PID) { $self[[int]$a.ProcessId] = $true }

$problems = New-Object System.Collections.Generic.List[string]
foreach ($t in $targets) {
    $table = Get-ProcessTable
    $foreign = $false
    $servers = @()
    foreach ($procId in Get-ListeningProcessIds $t.Port) {
        $proc = $table[[int]$procId]
        if (-not $proc) { continue }
        $name = [IO.Path]::GetFileNameWithoutExtension($proc.Name).ToLower()
        if ($t.Allowed -notcontains $name) {
            Write-Host "Port $($t.Port) is held by $($proc.Name) (PID $procId), which isn't Archeion's. Left it alone." -ForegroundColor Yellow
            $foreign = $true
            continue
        }
        $servers += [int]$procId
    }
    $windows = Find-Windows $table $t $servers

    if ($servers.Count -eq 0 -and $windows.Count -eq 0) {
        Write-Host "The $($t.Name) isn't running (nothing listens on port $($t.Port))."
        continue
    }

    # 1. Ask the server to shut down cleanly; kill it only if it doesn't.
    if ($servers.Count -gt 0) {
        Write-Host "Stopping the $($t.Name) on port $($t.Port) (PID $($servers -join ', '))..."
        if (Request-Shutdown $servers $t.Port $GracefulSeconds) {
            Write-Host "  Shut down cleanly."
        } else {
            Write-Host "  It didn't exit within $GracefulSeconds s, so it's being killed." -ForegroundColor Yellow
            $table = Get-ProcessTable
            foreach ($procId in $servers) { if ($table[$procId]) { Stop-Tree $table $procId } }
            if (-not (Wait-Stopped $t.Port $servers 5)) { $problems.Add("the $($t.Name) is still running") }
        }
    }

    # 2. Close its console window, and anything still running in it.
    $table = Get-ProcessTable
    foreach ($w in $windows) {
        $wid = [int]$w.ProcessId
        if ($self[$wid]) {
            Write-Host "  Left the $($t.Name) window open, because stop.bat runs in it." -ForegroundColor Yellow
            continue
        }
        if (-not $table[$wid]) { continue }
        Stop-Tree $table $wid
        if (Wait-Stopped $t.Port @($wid) 5) {
            Write-Host "  Closed the $($t.Name) window."
        } else {
            $problems.Add("the $($t.Name) window (PID $wid) didn't close")
        }
    }

    # 3. Final check: the port is free.
    if ((Get-ListeningProcessIds $t.Port).Count -gt 0 -and -not $foreign) {
        $problems.Add("port $($t.Port) is still in use")
    }
}

if ($problems.Count -gt 0) {
    Write-Host "Archeion isn't fully stopped:" -ForegroundColor Yellow
    $problems | Select-Object -Unique | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host "Archeion is stopped."
exit 0
