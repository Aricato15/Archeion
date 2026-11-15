"""Health, first-run setup, login and session routes: the only public endpoints."""

from __future__ import annotations

import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..deps import AppState, get_conn, get_state, require_session
from ..security import (
    COOKIE_NAME,
    MIN_PW_LEN,
    Session,
    create_session,
    delete_session,
    get_pw_hash,
    local_only,
    pw_is_set,
    set_first_pw,
    verify_pw,
)

public = APIRouter(prefix="/api")
protected = APIRouter()

# The only routes reachable without a session. tests/test_auth_required.py enforces this.
PUBLIC_ROUTES = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
    ("GET", "/api/auth/setup"),
    ("POST", "/api/auth/setup"),
}


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class SetupBody(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


def _start_session(state: AppState, conn: sqlite3.Connection, response: Response) -> None:
    raw, _ = create_session(conn, state.settings.session_idle_hours, state.settings.session_max_days)
    response.set_cookie(
        COOKIE_NAME,
        raw,
        max_age=int(state.settings.session_max_days * 86400),
        path="/",
        httponly=True,
        samesite="strict",
    )


@public.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@public.post("/auth/login", status_code=status.HTTP_204_NO_CONTENT)
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    state: AppState = Depends(get_state),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    key = _client_key(request)
    wait = state.limiter.retry_after(key)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too many failed attempts, try again later",
            headers={"Retry-After": str(wait)},
        )
    stored = get_pw_hash(conn)
    if stored is None or not verify_pw(body.password, stored):
        state.limiter.fail(key)
        time.sleep(state.settings.login_fail_delay_seconds)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong password")
    state.limiter.reset(key)
    _start_session(state, conn, response)


@public.get("/auth/setup")
def setup_status(state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Whether the admin password still has to be created (a fresh start, ADR 0011)."""
    needed = not pw_is_set(conn)
    return {
        "needed": needed,
        "allowed": needed and local_only(state.settings.host),
        "min_length": MIN_PW_LEN,
    }


@public.post("/auth/setup", status_code=status.HTTP_204_NO_CONTENT)
def setup(
    body: SetupBody,
    response: Response,
    state: AppState = Depends(get_state),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Create the first admin password and log in. Refused once a password exists: changing
    it stays with the CLI (password set), which logs out every session."""
    if not local_only(state.settings.host):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Archeion listens beyond this machine, so set the password with the CLI: password set",
        )
    if not set_first_pw(conn, body.password):
        raise HTTPException(status.HTTP_409_CONFLICT, "an admin password is already set; log in instead")
    _start_session(state, conn, response)


@protected.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_conn)) -> None:
    delete_session(conn, request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict")


@protected.get("/api/auth/session")
def session_info(session: Session = Depends(require_session)) -> dict:
    return {"expires_at": session.expires_at}


@protected.get("/api/version")
def version(state: AppState = Depends(get_state)) -> dict:
    return {"version": state.version}
