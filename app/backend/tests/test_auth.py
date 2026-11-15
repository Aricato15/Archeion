from __future__ import annotations

from datetime import timedelta

import pytest

from app.__main__ import EXIT_NO_PASSWORD, main
from app.db import iso, utcnow
from app.security import (
    COOKIE_NAME,
    LoginLimiter,
    check_session,
    create_session,
    hash_pw,
    set_pw,
    verify_pw,
)
from tests.conftest import make_pw


def test_hash_round_trip():
    value = make_pw()
    stored = hash_pw(value, n=2**10)
    assert stored.startswith("scrypt$1024$8$1$")
    assert value not in stored
    assert verify_pw(value, stored)
    assert not verify_pw(value + "x", stored)
    assert not verify_pw(value, "garbage")


def test_short_pw_rejected(db):
    with db.conn() as conn, pytest.raises(ValueError):
        set_pw(conn, "short")


def test_login_logout(client, pw):
    assert client.get("/api/auth/session").status_code == 401
    r = client.post("/api/auth/login", json={"password": pw})
    assert r.status_code == 204
    cookie = r.headers["set-cookie"]
    assert COOKIE_NAME in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert client.get("/api/auth/session").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/api/auth/session").status_code == 401


def test_wrong_pw(client, pw):
    r = client.post("/api/auth/login", json={"password": pw + "nope"})
    assert r.status_code == 401
    assert COOKIE_NAME not in r.headers.get("set-cookie", "")


def test_login_without_pw_set(client, db):
    assert client.post("/api/auth/login", json={"password": make_pw()}).status_code == 401


def test_setting_pw_logs_everyone_out(authed, db):
    assert authed.get("/api/auth/session").status_code == 200
    with db.conn() as conn:
        set_pw(conn, make_pw())
    assert authed.get("/api/auth/session").status_code == 401


def test_expired_and_idle_sessions(db):
    with db.conn() as conn:
        raw, _ = create_session(conn, idle_hours=12, max_days=7)
        assert check_session(conn, raw, 12) is not None
        conn.execute("UPDATE sessions SET last_seen_at = ?", (iso(utcnow() - timedelta(hours=13)),))
        assert check_session(conn, raw, 12) is None
        raw, _ = create_session(conn, idle_hours=12, max_days=7)
        conn.execute("UPDATE sessions SET expires_at = ?", (iso(utcnow() - timedelta(seconds=1)),))
        assert check_session(conn, raw, 12) is None
        assert check_session(conn, None, 12) is None
        assert check_session(conn, "x" * 500, 12) is None


def test_raw_cookie_value_not_stored(authed, db):
    raw = authed.cookies.get(COOKIE_NAME)
    with db.conn() as conn:
        rows = [r[0] for r in conn.execute("SELECT token_hash FROM sessions")]
    assert rows and raw not in rows


def test_rate_limit(client, pw):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"password": "bad"}).status_code == 401
    r = client.post("/api/auth/login", json={"password": pw})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0


def test_limiter_unit():
    lim = LoginLimiter(max_failures=2, window_seconds=600)
    assert lim.retry_after("a") == 0
    lim.fail("a")
    assert lim.retry_after("a") == 0
    lim.fail("a")
    assert lim.retry_after("a") > 0
    assert lim.retry_after("b") == 0
    lim.reset("a")
    assert lim.retry_after("a") == 0


def test_origin_guard(client, pw):
    r = client.post("/api/auth/login", json={"password": pw}, headers={"Origin": "http://evil.example.com"})
    assert r.status_code == 403
    client.headers.pop("Origin")
    assert client.post("/api/auth/login", json={"password": pw}).status_code == 403


def test_trusted_host(client):
    assert client.get("/api/health", headers={"Host": "attacker.example.com"}).status_code == 400
    assert client.get("/api/health").json() == {"status": "ok"}


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_version_endpoint(authed):
    assert authed.get("/api/version").json() == {"version": "9.9.9"}


def test_cli_password_status_and_clear(settings, db, capsys):
    assert main(["password", "status"], settings) == EXIT_NO_PASSWORD
    with db.conn() as conn:
        set_pw(conn, make_pw())
        create_session(conn, 12, 7)
    assert main(["password", "status"], settings) == 0
    assert main(["password", "clear-sessions"], settings) == 0
    assert "Logged out 1 session" in capsys.readouterr().out


def test_cli_password_set(settings, db, monkeypatch):
    value = make_pw()
    answers = iter([value, value])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    assert main(["password", "set"], settings) == 0
    with db.conn() as conn:
        from app.security import get_pw_hash

        assert verify_pw(value, get_pw_hash(conn))

    mismatch = iter([value, value + "x"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(mismatch))
    assert main(["password", "set"], settings) == 1
