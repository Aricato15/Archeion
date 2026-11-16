"""SQLite access: one connection per use, workspace pragmas, numbered migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: we issue BEGIN IMMEDIATE / COMMIT ourselves.
    conn = sqlite3.connect(path, isolation_level=None, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def write_tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _exec_all(conn: sqlite3.Connection, script: str) -> None:
    """Run several statements inside the caller's transaction (executescript would COMMIT first)."""
    for statement in script.split(";"):
        if statement.strip():
            conn.execute(statement)


def _m1_auth(conn: sqlite3.Connection) -> None:
    _exec_all(
        conn,
        """
        CREATE TABLE admin (
          id          INTEGER PRIMARY KEY CHECK (id = 1),
          pw_hash     TEXT NOT NULL,
          updated_at  TEXT NOT NULL
        );
        CREATE TABLE sessions (
          token_hash    TEXT PRIMARY KEY,
          created_at    TEXT NOT NULL,
          last_seen_at  TEXT NOT NULL,
          expires_at    TEXT NOT NULL
        );
        """,
    )


def _m2_feedback(conn: sqlite3.Connection) -> None:
    _exec_all(
        conn,
        """
        CREATE TABLE feedback (
          id           INTEGER PRIMARY KEY,
          kind         TEXT NOT NULL CHECK (kind IN ('prompt','review','comment')),
          doc_path     TEXT,
          anchor       TEXT,
          body         TEXT NOT NULL,
          status       TEXT NOT NULL DEFAULT 'open'
                       CHECK (status IN ('open','in_progress','answered','resolved')),
          reply        TEXT,
          parent_id    INTEGER REFERENCES feedback(id) ON DELETE SET NULL,
          doc_rev      TEXT,
          created_at   TEXT NOT NULL,
          updated_at   TEXT NOT NULL,
          claimed_at   TEXT,
          answered_at  TEXT
        );
        CREATE INDEX feedback_status ON feedback(status, created_at);
        CREATE INDEX feedback_doc ON feedback(doc_path);
        CREATE INDEX feedback_parent ON feedback(parent_id);
        """,
    )


# Append only. The index + 1 is the schema version stored in PRAGMA user_version.
def _m3_feedback_source(conn: sqlite3.Connection) -> None:
    # Which doc source (archeion or a registered project) an item targets (ADR 0006).
    # Stored as a plain id: projects aren't rows in this database.
    _exec_all(
        conn,
        """
        ALTER TABLE feedback ADD COLUMN source TEXT NOT NULL DEFAULT 'archeion';
        CREATE INDEX feedback_source ON feedback(source, status)
        """,
    )


def _m4_feedback_origin(conn: sqlite3.Connection) -> None:
    # Which registered project sent an item from its own session (/archeion:report,
    # ADR 0009). NULL: written in the viewer. A plain id, like source.
    _exec_all(conn, "ALTER TABLE feedback ADD COLUMN origin TEXT")


def _m5_runner(conn: sqlite3.Connection) -> None:
    # The inbox terminal the viewer starts (ADR 0013): its interval, and while it runs its
    # PID plus the process's start time, so a reused PID isn't taken for it.
    _exec_all(
        conn,
        """
        CREATE TABLE runner (
          id            INTEGER PRIMARY KEY CHECK (id = 1),
          interval      TEXT NOT NULL DEFAULT '10m',
          pid           INTEGER,
          proc_started  INTEGER,
          started_at    TEXT
        )
        """,
    )


def _m6_feedback_threads(conn: sqlite3.Connection) -> None:
    # Feedback is a thread (ADR 0018): every message records its thread's root id, so a
    # thread is one indexed lookup. A plain id like parent_id's target, not a foreign key:
    # the root is never deleted while it has replies (only open items can be deleted, and an
    # open thread takes no replies). Backfilled in id order, since a parent is always older.
    _exec_all(conn, "ALTER TABLE feedback ADD COLUMN thread_id INTEGER")
    roots: dict[int, int] = {}
    for r in conn.execute("SELECT id, parent_id FROM feedback ORDER BY id").fetchall():
        thread = roots.get(r["parent_id"], r["id"]) if r["parent_id"] is not None else r["id"]
        roots[r["id"]] = thread
        conn.execute("UPDATE feedback SET thread_id = ? WHERE id = ?", (thread, r["id"]))
    _exec_all(conn, "CREATE INDEX feedback_thread ON feedback(thread_id, id)")


def _m7_reopen_as_message(conn: sqlite3.Connection) -> None:
    # Reopening used to send an answered item back to open with its reply still on it, so the
    # next answer overwrote the last one. Now reopening adds a message (ADR 0018). Turn each item
    # reopened the old way into that shape: the item is answered again, and a "Reopened" message
    # after it waits for Claude. Fixed text on purpose: a migration doesn't follow later code.
    rows = conn.execute(
        "SELECT f.* FROM feedback f WHERE f.status = 'open' AND f.reply IS NOT NULL"
        " AND f.id = (SELECT max(id) FROM feedback x WHERE x.thread_id = f.thread_id)"
    ).fetchall()
    for r in rows:
        conn.execute("UPDATE feedback SET status = 'answered' WHERE id = ?", (r["id"],))
        conn.execute(
            "INSERT INTO feedback (kind, source, doc_path, body, parent_id, thread_id, doc_rev,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r["kind"],
                r["source"],
                r["doc_path"],
                "Reopened: please take another look at your last answer.",
                r["id"],
                r["thread_id"],
                r["doc_rev"],
                r["updated_at"],
                r["updated_at"],
            ),
        )
    # An earlier message reopened the old way, with a later one after it: just answered again.
    conn.execute("UPDATE feedback SET status = 'answered' WHERE status = 'open' AND reply IS NOT NULL")


def _m8_responder(conn: sqlite3.Connection) -> None:
    # On-demand Claude (ADR 0020): whether it's switched on, the run in progress (PID plus
    # the process's start time, as for the runner), when the last run started, and the
    # highest feedback id it could see: only messages above it are new to on-demand Claude.
    _exec_all(
        conn,
        """
        CREATE TABLE responder (
          id            INTEGER PRIMARY KEY CHECK (id = 1),
          enabled       INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
          pid           INTEGER,
          proc_started  INTEGER,
          started_at    TEXT,
          last_run_at   TEXT,
          seen_id       INTEGER NOT NULL DEFAULT 0,
          log_path      TEXT
        )
        """,
    )


def _m9_claude_jobs(conn: sqlite3.Connection) -> None:
    # Claude jobs (ADR 0021): headless or in a window, at most max_instances Claude processes
    # (the inbox terminal included), and one row per on-demand run, so two can run side by side.
    # The responder row's pid columns are no longer used; the runs live in claude_jobs.
    _exec_all(
        conn,
        """
        ALTER TABLE responder ADD COLUMN headless INTEGER NOT NULL DEFAULT 0 CHECK (headless IN (0, 1));
        ALTER TABLE responder ADD COLUMN max_instances INTEGER NOT NULL DEFAULT 1
          CHECK (max_instances BETWEEN 1 AND 2);
        CREATE TABLE claude_jobs (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          pid           INTEGER NOT NULL,
          proc_started  INTEGER,
          started_at    TEXT NOT NULL,
          mode          TEXT NOT NULL CHECK (mode IN ('window', 'headless')),
          log_path      TEXT,
          done_path     TEXT
        )
        """,
    )


def _m10_permission_mode(conn: sqlite3.Connection) -> None:
    # How Archeion's Claude sessions handle file edits (ADR 0021): accept them, or ask first.
    _exec_all(
        conn,
        """
        ALTER TABLE responder ADD COLUMN permission_mode TEXT NOT NULL DEFAULT 'accept_edits'
          CHECK (permission_mode IN ('accept_edits', 'confirm'))
        """,
    )


MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [
    _m1_auth,
    _m2_feedback,
    _m3_feedback_source,
    _m4_feedback_origin,
    _m5_runner,
    _m6_feedback_threads,
    _m7_reopen_as_message,
    _m8_responder,
    _m9_claude_jobs,
    _m10_permission_mode,
]


def migrate(conn: sqlite3.Connection) -> int:
    conn.execute("BEGIN IMMEDIATE")
    try:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current > len(MIGRATIONS):
            raise RuntimeError(
                f"database schema {current} is newer than this app ({len(MIGRATIONS)}); upgrade the app"
            )
        for version in range(current, len(MIGRATIONS)):
            MIGRATIONS[version](conn)
            conn.execute(f"PRAGMA user_version = {version + 1}")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
    return len(MIGRATIONS)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def init(self) -> None:
        conn = connect(self.path)
        try:
            migrate(conn)
        finally:
            conn.close()

    def connect(self) -> sqlite3.Connection:
        return connect(self.path)

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        c = connect(self.path)
        try:
            yield c
        finally:
            c.close()
