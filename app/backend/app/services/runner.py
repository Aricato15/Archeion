"""The inbox terminal: a Claude Code window that runs `/loop <interval> /inbox` (ADR 0013).

The viewer starts and stops it; this module tracks it. The process ID and the process's
start time are stored in SQLite, so the status survives a backend restart and a reused
PID isn't mistaken for the terminal. It's Windows only, like the root scripts: the
terminal opens in its own console window on this machine.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..db import iso, utcnow, write_tx

INTERVAL_RE = re.compile(r"^([1-9][0-9]*)([mh])$")
DEFAULT_INTERVAL = "10m"
MAX_MINUTES = 24 * 60
# Not passed on: they belong to whoever started the backend, not to the new session.
DROP_ENV = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "ARCHEION_CALLER_DIR")


class RunnerError(ValueError):
    """A request the runner refuses; mapped to 400 like other ValueErrors."""


@dataclass
class Launch:
    pid: int


def normalize_interval(value: str) -> str:
    """'10m', '1h' ... between 1 minute and 24 hours. Raises RunnerError otherwise."""
    v = value.strip().lower()
    m = INTERVAL_RE.match(v)
    if not m:
        raise RunnerError(f"'{value}' isn't an interval such as 10m or 1h")
    minutes = int(m.group(1)) * (60 if m.group(2) == "h" else 1)
    if minutes > MAX_MINUTES:
        raise RunnerError("the interval can be at most 24h")
    return v


def supported() -> bool:
    return os.name == "nt"


def find_claude() -> str | None:
    return shutil.which("claude")


# --- process checks (Windows) --------------------------------------------------------


def process_start_time(pid: int) -> int | None:
    """The process's creation time (FILETIME ticks) while it runs, else None."""
    if not supported() or pid <= 0:
        return None
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not k32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        created = times[0]
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        k32.CloseHandle(handle)


def launch(claude: str, interval: str, cwd: Path, flags: list[str] | None = None) -> Launch:
    """Open Claude Code in a new console window, through cmd (ADR 0021), already running the loop."""
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
    proc = subprocess.Popen(  # noqa: S603 - fixed program and a validated interval
        ["cmd", "/c", claude, f"/loop {interval} /inbox", *(flags or [])],
        cwd=cwd,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        close_fds=True,
    )
    return Launch(pid=proc.pid)


def kill_tree(pid: int) -> None:
    subprocess.run(  # noqa: S603
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


# --- state ---------------------------------------------------------------------------


def _row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runner WHERE id = 1").fetchone()


def _alive(row: sqlite3.Row | None) -> bool:
    if row is None or row["pid"] is None:
        return False
    started = process_start_time(int(row["pid"]))
    return started is not None and started == row["proc_started"]


# Claude Code's auto permission mode (ADR 0021): it decides most prompts itself. The stored setting is
# still called accept_edits, which is what it was before it launched auto.
AUTO_FLAGS = ("--permission-mode", "auto")


def accepts_edits(conn: sqlite3.Connection) -> bool:
    """The Edits setting (ADR 0021): accept file edits, or ask before each one. Shared by both
    Claude terminals; it lives on the responder row with the other Claude job settings."""
    row = conn.execute("SELECT permission_mode FROM responder WHERE id = 1").fetchone()
    return row is None or row["permission_mode"] == "accept_edits"


def permission_flags(conn: sqlite3.Connection) -> list[str]:
    return list(AUTO_FLAGS) if accepts_edits(conn) else []


def terminal_running(conn: sqlite3.Connection) -> bool:
    return _alive(_row(conn))


def _on_demand(conn: sqlite3.Connection) -> str | None:
    """Why on-demand Claude blocks the terminal (ADR 0021): Max Claude instances counts the
    terminal and every on-demand run, and with a limit of 1 the two don't mix at all."""
    row = conn.execute("SELECT * FROM responder WHERE id = 1").fetchone()
    if row is None:
        return None
    most = int(row["max_instances"])
    jobs = [j for j in conn.execute("SELECT * FROM claude_jobs").fetchall() if _alive(j)]
    if len(jobs) >= most:
        return (
            f"On-demand Claude is working ({len(jobs)} run(s)), and Max Claude instances is {most}."
            " Wait for it to finish, or allow more."
        )
    if most == 1 and row["enabled"]:
        return "On-demand Claude is switched on, and Max Claude instances is 1. Switch it off, or allow 2."
    return None


def status(conn: sqlite3.Connection, *, can_start: bool) -> dict:
    row = _row(conn)
    running = _alive(row)
    claude = find_claude() if supported() else None
    reason = None
    if not supported():
        reason = "The inbox terminal opens a console window, so it needs Windows."
    elif not can_start:
        reason = (
            "The backend listens on another network interface, so it doesn't open windows on this machine."
        )
    elif claude is None:
        reason = "The claude command isn't on the backend's PATH. Install Claude Code, then restart Archeion."
    elif not running:
        reason = _on_demand(conn)
    return {
        "running": running,
        "interval": row["interval"] if row else DEFAULT_INTERVAL,
        "pid": int(row["pid"]) if running and row else None,
        "started_at": row["started_at"] if running and row else None,
        "can_start": reason is None,
        "reason": reason,
    }


def set_interval(conn: sqlite3.Connection, interval: str) -> str:
    value = normalize_interval(interval)
    with write_tx(conn):
        conn.execute(
            "INSERT INTO runner (id, interval) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET interval = excluded.interval",
            (value,),
        )
    return value


def start(conn: sqlite3.Connection, repo_root: Path, interval: str | None, *, can_start: bool) -> None:
    """Start the terminal. Refused while it runs: restart is stop, then start."""
    current = status(conn, can_start=can_start)
    if not current["can_start"]:
        raise RunnerError(current["reason"])
    if current["running"]:
        raise RunnerError("The inbox terminal is already running. Stop it first, or use Restart.")
    value = normalize_interval(interval) if interval else current["interval"]
    claude = find_claude()
    if claude is None:  # checked above; it can vanish in between
        raise RunnerError("The claude command isn't on the backend's PATH.")
    proc = launch(claude, value, repo_root, permission_flags(conn))
    started = process_start_time(proc.pid)
    with write_tx(conn):
        conn.execute(
            "INSERT INTO runner (id, interval, pid, proc_started, started_at) VALUES (1, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET interval = excluded.interval, pid = excluded.pid, "
            "proc_started = excluded.proc_started, started_at = excluded.started_at",
            (value, proc.pid, started, iso(utcnow())),
        )


def stop(conn: sqlite3.Connection) -> bool:
    """Close the terminal if it's the one we started. True when something was stopped."""
    row = _row(conn)
    was_running = _alive(row)
    if was_running and row is not None:
        kill_tree(int(row["pid"]))
    with write_tx(conn):
        conn.execute("UPDATE runner SET pid = NULL, proc_started = NULL, started_at = NULL WHERE id = 1")
    return was_running
