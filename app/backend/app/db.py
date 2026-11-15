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


MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [_m1_auth, _m2_feedback, _m3_feedback_source]


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
