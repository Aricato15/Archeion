"""On-demand Claude (ADR 0020): a Claude Code run that answers the inbox once and exits.

When it's switched on, the backend starts `claude -p "/inbox"` in its own console window
whenever a message is waiting that's newer than the last run, so a reply in the viewer is
answered within seconds and nothing runs while nothing waits. It never runs alongside the
inbox terminal (ADR 0013). Runs are tracked like the terminal: PID plus process start time.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

from ..db import iso, utcnow, write_tx
from . import runner
from .runner import DROP_ENV, RunnerError

SCRIPT = Path("scripts") / "respond.ps1"
LOG_DIR = Path("app") / "backend" / "data" / "responder"
KEEP_LOGS = 30


def _row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM responder WHERE id = 1").fetchone()


def _alive(row: sqlite3.Row | None) -> bool:
    if row is None or row["pid"] is None:
        return False
    started = runner.process_start_time(int(row["pid"]))
    return started is not None and started == row["proc_started"]


def running(conn: sqlite3.Connection) -> bool:
    return _alive(_row(conn))


def enabled(conn: sqlite3.Connection) -> bool:
    row = _row(conn)
    return bool(row and row["enabled"])


def _blocker(conn: sqlite3.Connection, *, can_start: bool) -> str | None:
    """Why no run can start here at all (not counting one already running)."""
    if not runner.supported():
        return "On-demand Claude opens a console window, so it needs Windows."
    if not can_start:
        return "The backend listens on another network interface, so it doesn't open windows on this machine."
    if runner.find_claude() is None:
        return "The claude command isn't on the backend's PATH. Install Claude Code, then restart Archeion."
    if runner.status(conn, can_start=True)["running"]:
        return "The inbox terminal is running. Stop it first: only one Claude job runs at a time."
    return None


def waiting(conn: sqlite3.Connection) -> int:
    """Open messages written after the last run started: what a run would be for. Each run
    records the highest message id when it starts, so messages Claude released during it
    (left open on purpose) are at or below that mark: they don't count and can't loop."""
    row = _row(conn)
    seen = int(row["seen_id"]) if row else 0
    return int(
        conn.execute("SELECT count(*) FROM feedback WHERE status = 'open' AND id > ?", (seen,)).fetchone()[0]
    )


def status(conn: sqlite3.Connection, *, can_start: bool) -> dict:
    row = _row(conn)
    alive = _alive(row)
    reason = _blocker(conn, can_start=can_start)
    return {
        "enabled": bool(row and row["enabled"]),
        "running": alive,
        "pid": int(row["pid"]) if alive and row else None,
        "started_at": row["started_at"] if alive and row else None,
        "last_run_at": row["last_run_at"] if row else None,
        "waiting": waiting(conn),
        "can_start": reason is None,
        "reason": reason,
    }


def set_enabled(conn: sqlite3.Connection, value: bool, *, can_start: bool) -> None:
    if value:
        reason = _blocker(conn, can_start=can_start)
        if reason:
            raise RunnerError(reason)
    with write_tx(conn):
        conn.execute(
            "INSERT INTO responder (id, enabled) VALUES (1, ?)"
            " ON CONFLICT(id) DO UPDATE SET enabled = excluded.enabled",
            (1 if value else 0,),
        )


def _roots_args(dirs: list[Path]) -> list[str]:
    out: list[str] = []
    for d in dirs:
        out += ["-AddDir", str(d)]
    return out


def launch(repo_root: Path, log: Path, dirs: list[Path]) -> int:
    """Open a console window running scripts/respond.ps1, which runs `claude -p "/inbox"`
    with its output both shown and logged, and closes when it's done."""
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV}
    proc = subprocess.Popen(  # noqa: S603 - fixed script, paths from settings
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / SCRIPT),
            "-Log",
            str(log),
            *_roots_args(dirs),
        ],
        cwd=repo_root,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        close_fds=True,
    )
    return proc.pid


def _prune_logs(folder: Path) -> None:
    logs = sorted(folder.glob("*.log"))
    for old in logs[: max(0, len(logs) - KEEP_LOGS)]:
        old.unlink(missing_ok=True)


def start(conn: sqlite3.Connection, repo_root: Path, dirs: list[Path], *, can_start: bool) -> None:
    """Start one run. Refused while one runs, or while the inbox terminal runs."""
    if running(conn):
        raise RunnerError("On-demand Claude is already working on the inbox.")
    reason = _blocker(conn, can_start=can_start)
    if reason:
        raise RunnerError(reason)
    now = utcnow()
    folder = repo_root / LOG_DIR
    folder.mkdir(parents=True, exist_ok=True)
    _prune_logs(folder)
    log = folder / f"{now.strftime('%Y%m%d-%H%M%S')}.log"
    seen = int(conn.execute("SELECT coalesce(max(id), 0) FROM feedback").fetchone()[0])
    pid = launch(repo_root, log, dirs)
    started = runner.process_start_time(pid)
    with write_tx(conn):
        conn.execute(
            "INSERT INTO responder (id, pid, proc_started, started_at, last_run_at, seen_id, log_path)"
            " VALUES (1, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET pid = excluded.pid,"
            " proc_started = excluded.proc_started, started_at = excluded.started_at,"
            " last_run_at = excluded.last_run_at, seen_id = excluded.seen_id, log_path = excluded.log_path",
            (pid, started, iso(now), iso(now), seen, log.relative_to(repo_root).as_posix()),
        )


def stop(conn: sqlite3.Connection) -> bool:
    row = _row(conn)
    was = _alive(row)
    if was and row is not None:
        runner.kill_tree(int(row["pid"]))
    with write_tx(conn):
        conn.execute("UPDATE responder SET pid = NULL, proc_started = NULL, started_at = NULL WHERE id = 1")
    return was


def tick(conn: sqlite3.Connection, repo_root: Path, dirs: list[Path], *, can_start: bool) -> str | None:
    """One check of the watcher: start a run when switched on, idle, allowed and something new
    waits. Returns "started" or "finished" when the state changed, else None."""
    row = _row(conn)
    if row is None:
        return None
    alive = _alive(row)
    if row["pid"] is not None and not alive:
        with write_tx(conn):
            conn.execute(
                "UPDATE responder SET pid = NULL, proc_started = NULL, started_at = NULL WHERE id = 1"
            )
        return "finished"
    if alive or not row["enabled"] or waiting(conn) == 0:
        return None
    if _blocker(conn, can_start=can_start):
        return None
    start(conn, repo_root, dirs, can_start=can_start)
    return "started"
