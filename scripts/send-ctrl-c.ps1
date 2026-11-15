# Sends Ctrl+C (or, with -Break, Ctrl+Break) to the console that a process runs in, so it
# can shut down cleanly. Ctrl+Break also reaches processes that inherited "ignore Ctrl+C".
# stop.ps1 starts it in its own hidden window, because a process has to leave its own
# console to attach to another one. Exit codes: 0 sent, 2 couldn't attach, 3 couldn't send.
param([Parameter(Mandatory = $true)][int]$ProcessId, [switch]$Break)

Add-Type -Namespace Archeion -Name Console -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true)] public static extern bool FreeConsole();
[DllImport("kernel32.dll", SetLastError = true)] public static extern bool AttachConsole(uint dwProcessId);
[DllImport("kernel32.dll", SetLastError = true)] public static extern bool SetConsoleCtrlHandler(System.IntPtr handler, bool add);
[DllImport("kernel32.dll", SetLastError = true)] public static extern bool GenerateConsoleCtrlEvent(uint ctrlEvent, uint processGroupId);
'@

[void][Archeion.Console]::FreeConsole()
if (-not [Archeion.Console]::AttachConsole([uint32]$ProcessId)) { exit 2 }
# Ignore Ctrl+C ourselves, since it goes to every process attached to the console.
[void][Archeion.Console]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)
# CTRL_C_EVENT (0) or CTRL_BREAK_EVENT (1) to process group 0: everything in that console.
$sent = [Archeion.Console]::GenerateConsoleCtrlEvent([uint32]$(if ($Break) { 1 } else { 0 }), 0)
# Stay attached briefly so the event is delivered before we leave the console.
Start-Sleep -Milliseconds 500
[void][Archeion.Console]::FreeConsole()
if ($sent) { exit 0 } else { exit 3 }
