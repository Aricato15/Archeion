"""Shared app state and FastAPI dependencies, including the session guard."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request, status

from .config import Settings
from .db import Database
from .security import COOKIE_NAME, LoginLimiter, Session, check_session
from .services.events import EventBus


@dataclass
class AppState:
    settings: Settings
    db: Database
    bus: EventBus
    limiter: LoginLimiter
    version: str
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    tasks: list[asyncio.Task] = field(default_factory=list)


def get_state(request: Request) -> AppState:
    return request.app.state.archeion


def get_conn(state: AppState = Depends(get_state)) -> Iterator[sqlite3.Connection]:
    with state.db.conn() as conn:
        yield conn


def session_from_request(state: AppState, request: Request) -> Session | None:
    with state.db.conn() as conn:
        return check_session(conn, request.cookies.get(COOKIE_NAME), state.settings.session_idle_hours)


def require_session(request: Request, state: AppState = Depends(get_state)) -> Session:
    """Guard for every route except health and login. Uses its own short-lived connection."""
    session = session_from_request(state, request)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not logged in")
    request.state.session = session
    return session
