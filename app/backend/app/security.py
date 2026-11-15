"""Admin credential hashing, sessions and the login rate limiter."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import timedelta

from .db import iso, parse_iso, utcnow, write_tx

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_MAXMEM = 64 * 1024 * 1024
MIN_PW_LEN = 12

COOKIE_NAME = "archeion_session"
# Only touch last_seen_at this often, so browsing doesn't write on every request.
TOUCH_EVERY = timedelta(seconds=60)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_pw(pw: str, *, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        pw.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=SCRYPT_MAXMEM, dklen=SCRYPT_DKLEN
    )
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(digest)}"


def verify_pw(pw: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            pw.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=SCRYPT_MAXMEM,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# --- admin credential -------------------------------------------------------------------


def pw_is_set(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM admin WHERE id = 1").fetchone() is not None


def get_pw_hash(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT pw_hash FROM admin WHERE id = 1").fetchone()
    return row["pw_hash"] if row else None


def set_pw(conn: sqlite3.Connection, pw: str) -> None:
    """Store a new admin credential and log out every session, in one transaction."""
    if len(pw) < MIN_PW_LEN:
        raise ValueError(f"the password must be at least {MIN_PW_LEN} characters")
    hashed = hash_pw(pw)
    with write_tx(conn):
        conn.execute(
            "INSERT INTO admin (id, pw_hash, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET pw_hash = excluded.pw_hash, updated_at = excluded.updated_at",
            (hashed, iso(utcnow())),
        )
        conn.execute("DELETE FROM sessions")


def set_first_pw(conn: sqlite3.Connection, pw: str) -> bool:
    """Store the first admin credential, only if none exists yet (ADR 0011). False when one
    already does, so two first-run requests can't both set it."""
    if len(pw) < MIN_PW_LEN:
        raise ValueError(f"the password must be at least {MIN_PW_LEN} characters")
    hashed = hash_pw(pw)
    with write_tx(conn):
        cur = conn.execute(
            "INSERT INTO admin (id, pw_hash, updated_at) VALUES (1, ?, ?) ON CONFLICT(id) DO NOTHING",
            (hashed, iso(utcnow())),
        )
        return cur.rowcount == 1


# --- sessions ---------------------------------------------------------------------------


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("ascii", "replace")).hexdigest()


@dataclass(frozen=True)
class Session:
    token_hash: str
    expires_at: str


def create_session(conn: sqlite3.Connection, idle_hours: float, max_days: float) -> tuple[str, Session]:
    """Create a session; returns the raw cookie value (never stored) and the session."""
    raw = secrets.token_urlsafe(32)
    now = utcnow()
    expires = now + timedelta(days=max_days)
    th = _hash_token(raw)
    with write_tx(conn):
        conn.execute(
            "DELETE FROM sessions WHERE expires_at < ? OR last_seen_at < ?",
            (iso(now), iso(now - timedelta(hours=idle_hours))),
        )
        conn.execute(
            "INSERT INTO sessions (token_hash, created_at, last_seen_at, expires_at) VALUES (?, ?, ?, ?)",
            (th, iso(now), iso(now), iso(expires)),
        )
    return raw, Session(th, iso(expires))


def check_session(
    conn: sqlite3.Connection, raw: str | None, idle_hours: float, *, touch: bool = True
) -> Session | None:
    """Return the session for a cookie value if it is still valid, else None."""
    if not raw or len(raw) > 200:
        return None
    th = _hash_token(raw)
    row = conn.execute(
        "SELECT token_hash, last_seen_at, expires_at FROM sessions WHERE token_hash = ?", (th,)
    ).fetchone()
    if row is None:
        return None
    now = utcnow()
    last_seen = parse_iso(row["last_seen_at"])
    if parse_iso(row["expires_at"]) <= now or last_seen + timedelta(hours=idle_hours) <= now:
        with write_tx(conn):
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (th,))
        return None
    if touch and now - last_seen >= TOUCH_EVERY:
        with write_tx(conn):
            conn.execute("UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?", (iso(now), th))
    return Session(th, row["expires_at"])


def delete_session(conn: sqlite3.Connection, raw: str | None) -> None:
    if not raw:
        return
    with write_tx(conn):
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(raw),))


def clear_sessions(conn: sqlite3.Connection) -> int:
    with write_tx(conn):
        return conn.execute("DELETE FROM sessions").rowcount


# --- login rate limit -------------------------------------------------------------------


class LoginLimiter:
    """In-memory failure counter per client. Resets when the backend restarts."""

    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._failures.setdefault(key, deque())
        while q and q[0] <= now - self.window:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int:
        """Seconds to wait before another attempt is allowed (0 = allowed now)."""
        now = time.monotonic()
        with self._lock:
            q = self._prune(key, now)
            if len(q) < self.max_failures:
                return 0
            # Back off harder the more the limit is exceeded, capped at the window.
            extra = len(q) - self.max_failures
            wait_until = q[-1] + min(self.window, 30 * (2**extra))
            return max(1, int(wait_until - now) + 1) if wait_until > now else 0

    def fail(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
