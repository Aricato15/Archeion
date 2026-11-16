"""On-demand Claude (ADR 0020, ADR 0021): Claude Code runs that answer the inbox and end.

When it's switched on, the backend starts a run whenever a message waits that's newer than
the last run. A run is either a visible session (`cmd /c claude "/inbox"` in its own window, so
its thinking and tool calls show as they happen, closed by the backend once the Stop hook says
the turn ended) or headless (`claude -p` with no window, every event logged). Each run is a
row in claude_jobs, tracked by PID plus process start time. At most max_instances Claude
processes run at once, the inbox terminal (ADR 0013) included.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

from ..db import iso, utcnow, write_tx
from . import runner
from .runner import DROP_ENV, RunnerError

LOG_DIR = Path("app") / "backend" / "data" / "responder"
KEEP_LOGS = 30
MAX_INSTANCES = 2
DONE_ENV = "ARCHEION_ON_DEMAND_DONE"
# Nobody may be there to approve commands: edits are accepted and Archeion's own CLI and skills are
# allowed. In a visible session the person watching can approve anything else; headless, it's refused.
CLI = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1:*"
ALLOWED_TOOLS = [f"Bash({CLI})", f"PowerShell({CLI})", "Skill", "Read", "Grep", "Glob"]


# --- settings ------------------------------------------------------------------------------


def _row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM responder WHERE id = 1").fetchone()


def _ensure(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT OR IGNORE INTO responder (id) VALUES (1)")


def enabled(conn: sqlite3.Connection) -> bool:
    row = _row(conn)
    return bool(row and row["enabled"])


def limit(conn: sqlite3.Connection) -> int:
    """Max Claude instances: how many Claude processes may run at once."""
    row = _row(conn)
    return int(row["max_instances"]) if row else 1


def headless(conn: sqlite3.Connection) -> bool:
    row = _row(conn)
    return bool(row and row["headless"])


# --- jobs ----------------------------------------------------------------------------------


def jobs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """On-demand runs whose process is still the one we started."""
    return [r for r in conn.execute("SELECT * FROM claude_jobs ORDER BY id").fetchall() if runner._alive(r)]


def running(conn: sqlite3.Connection) -> bool:
    return bool(jobs(conn))


def instances(conn: sqlite3.Connection) -> int:
    """Claude processes running now: every on-demand run, plus the inbox terminal."""
    return len(jobs(conn)) + (1 if runner.terminal_running(conn) else 0)


def _base_blocker(*, can_start: bool) -> str | None:
    if not runner.supported():
        return "On-demand Claude starts Claude Code on this machine, so it needs Windows."
    if not can_start:
        return "The backend listens on another network interface, so it doesn't start Claude on this machine."
    if runner.find_claude() is None:
        return "The claude command isn't on the backend's PATH. Install Claude Code, then restart Archeion."
    return None


def _blocker(conn: sqlite3.Connection, *, can_start: bool) -> str | None:
    """Why a run can't start now."""
    reason = _base_blocker(can_start=can_start)
    if reason:
        return reason
    most = limit(conn)
    if instances(conn) >= most:
        if most == 1 and runner.terminal_running(conn):
            return "The inbox terminal is running, and Max Claude instances is 1. Stop it first, or allow 2."
        return f"{most} Claude instance(s) are running, the most allowed (Max Claude instances in Settings)."
    return None


def waiting(conn: sqlite3.Connection) -> int:
    """Open messages written after the last run started: what a run would be for. Each run
    records the highest message id when it starts, so messages Claude released during it
    (left open on purpose) are at or below that mark: they don't count and can't loop."""
    row = _row(conn)
    seen = int(row["seen_id"]) if row else 0
    sql = "SELECT count(*) FROM feedback WHERE status = 'open' AND id > ?"
    return int(conn.execute(sql, (seen,)).fetchone()[0])


def status(conn: sqlite3.Connection, *, can_start: bool) -> dict:
    row = _row(conn)
    alive = jobs(conn)
    reason = _blocker(conn, can_start=can_start)
    return {
        "enabled": bool(row and row["enabled"]),
        "running": bool(alive),
        "jobs": [{"pid": int(j["pid"]), "started_at": j["started_at"], "mode": j["mode"]} for j in alive],
        "headless": headless(conn),
        "accept_edits": runner.accepts_edits(conn),
        "max_instances": limit(conn),
        "instances": instances(conn),
        "terminal_running": runner.terminal_running(conn),
        "last_run_at": row["last_run_at"] if row else None,
        "waiting": waiting(conn),
        "can_start": reason is None,
        "reason": reason,
    }


def update(
    conn: sqlite3.Connection,
    *,
    enabled: bool | None = None,
    headless: bool | None = None,
    max_instances: int | None = None,
    accept_edits: bool | None = None,
    can_start: bool,
) -> None:
    current = _row(conn)
    will_headless = headless if headless is not None else bool(current and current["headless"])
    will_accept = accept_edits if accept_edits is not None else runner.accepts_edits(conn)
    if will_headless and not will_accept:
        raise RunnerError(
            "Headless runs have no one to confirm edits with. Choose auto accept edits, or turn Headless off."
        )
    if max_instances is not None and not 1 <= max_instances <= MAX_INSTANCES:
        raise RunnerError(f"Max Claude instances is 1 or {MAX_INSTANCES}.")
    most = max_instances if max_instances is not None else limit(conn)
    if enabled:
        reason = _base_blocker(can_start=can_start)
        if reason:
            raise RunnerError(reason)
        if most == 1 and runner.terminal_running(conn):
            raise RunnerError(
                "The inbox terminal is running, and Max Claude instances is 1. Stop it first, or allow 2."
            )
    if max_instances is not None:
        now = instances(conn)
        if max_instances < now:
            raise RunnerError(f"{now} Claude instances are running now; stop one before lowering the limit.")
        row = _row(conn)
        on = enabled if enabled is not None else bool(row and row["enabled"])
        if max_instances == 1 and on and runner.terminal_running(conn):
            raise RunnerError("The inbox terminal runs while on-demand Claude is on: keep 2, or stop one.")
    with write_tx(conn):
        _ensure(conn)
        for column, value in (("enabled", enabled), ("headless", headless), ("max_instances", max_instances)):
            if value is not None:
                conn.execute(f"UPDATE responder SET {column} = ? WHERE id = 1", (int(value),))  # noqa: S608
        if accept_edits is not None:
            mode = "accept_edits" if accept_edits else "confirm"
            conn.execute("UPDATE responder SET permission_mode = ? WHERE id = 1", (mode,))


def set_enabled(conn: sqlite3.Connection, value: bool, *, can_start: bool) -> None:
    update(conn, enabled=value, can_start=can_start)


# --- launching -------------------------------------------------------------------------------


def _flags(dirs: list[Path], *, accept_edits: bool = True) -> list[str]:
    """With "seek confirmations" no permission mode is passed: Claude asks before each edit,
    which only makes sense in a window someone can answer."""
    out = (["--permission-mode", "acceptEdits"] if accept_edits else []) + ["--allowedTools", *ALLOWED_TOOLS]
    for d in dirs:
        out += ["--add-dir", str(d)]
    return out


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in (*DROP_ENV, DONE_ENV)}
    env.update(extra or {})
    return env


def launch_window(repo_root: Path, dirs: list[Path], done: Path, *, accept_edits: bool = True) -> int:
    """An interactive session in its own console window, through cmd, so it can be watched."""
    proc = subprocess.Popen(  # noqa: S603 - fixed program and flags, paths from settings
        ["cmd", "/c", "claude", "/inbox", *_flags(dirs, accept_edits=accept_edits)],
        cwd=repo_root,
        env=_env({DONE_ENV: str(done)}),
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        close_fds=True,
    )
    return proc.pid


def launch_headless(claude: str, repo_root: Path, dirs: list[Path], log: Path) -> int:
    """No window: print mode, every event (thinking, tool calls, results) streamed to the log."""
    with log.open("wb") as out:
        proc = subprocess.Popen(  # noqa: S603
            [claude, "-p", "/inbox", "--output-format", "stream-json", "--verbose", *_flags(dirs)],
            cwd=repo_root,
            env=_env(),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
    return proc.pid


def _prune_logs(folder: Path) -> None:
    for pattern in ("*.log", "*.done"):
        files = sorted(folder.glob(pattern))
        for old in files[: max(0, len(files) - KEEP_LOGS)]:
            old.unlink(missing_ok=True)


def _rel(repo_root: Path, p: Path | None) -> str | None:
    return p.relative_to(repo_root).as_posix() if p else None


def start(conn: sqlite3.Connection, repo_root: Path, dirs: list[Path], *, can_start: bool) -> None:
    """Start one run, if a slot is free."""
    reason = _blocker(conn, can_start=can_start)
    if reason:
        raise RunnerError(reason)
    claude = runner.find_claude()
    if claude is None:  # checked above; it can vanish in between
        raise RunnerError("The claude command isn't on the backend's PATH.")
    now = utcnow()
    folder = repo_root / LOG_DIR
    folder.mkdir(parents=True, exist_ok=True)
    _prune_logs(folder)
    stamp = now.strftime("%Y%m%d-%H%M%S-%f")
    seen = int(conn.execute("SELECT coalesce(max(id), 0) FROM feedback").fetchone()[0])
    log: Path | None = None
    done: Path | None = None
    if headless(conn):
        mode = "headless"
        log = folder / f"{stamp}.log"
        pid = launch_headless(claude, repo_root, dirs, log)
    else:
        mode = "window"
        done = folder / f"{stamp}.done"
        pid = launch_window(repo_root, dirs, done, accept_edits=runner.accepts_edits(conn))
    started = runner.process_start_time(pid)
    with write_tx(conn):
        _ensure(conn)
        conn.execute("UPDATE responder SET last_run_at = ?, seen_id = ? WHERE id = 1", (iso(now), seen))
        conn.execute(
            "INSERT INTO claude_jobs (pid, proc_started, started_at, mode, log_path, done_path)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (pid, started, iso(now), mode, _rel(repo_root, log), _rel(repo_root, done)),
        )


def stop(conn: sqlite3.Connection) -> bool:
    """Close every on-demand run. True when something was running."""
    alive = jobs(conn)
    for j in alive:
        runner.kill_tree(int(j["pid"]))
    with write_tx(conn):
        conn.execute("DELETE FROM claude_jobs")
    return bool(alive)


def _reap(conn: sqlite3.Connection, repo_root: Path) -> bool:
    """Forget runs that ended, and close visible sessions whose turn ended (the Stop hook wrote
    their marker). True when any run finished."""
    finished = False
    for j in conn.execute("SELECT * FROM claude_jobs").fetchall():
        alive = runner._alive(j)
        marker = repo_root / j["done_path"] if j["done_path"] else None
        if alive and marker is not None and marker.is_file():
            runner.kill_tree(int(j["pid"]))
            alive = False
        if not alive:
            if marker is not None:
                marker.unlink(missing_ok=True)
            with write_tx(conn):
                conn.execute("DELETE FROM claude_jobs WHERE id = ?", (j["id"],))
            finished = True
    return finished


def tick(conn: sqlite3.Connection, repo_root: Path, dirs: list[Path], *, can_start: bool) -> str | None:
    """One check of the watcher: reap ended runs, then start one when switched on, something new
    waits and a slot is free. Returns "started" or "finished" when the state changed, else None."""
    finished = _reap(conn, repo_root)
    if enabled(conn) and waiting(conn) > 0 and _blocker(conn, can_start=can_start) is None:
        start(conn, repo_root, dirs, can_start=can_start)
        return "started"
    return "finished" if finished else None
