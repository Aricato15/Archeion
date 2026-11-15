"""The inbox terminal, started and watched from the viewer (ADR 0013)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import AppState, get_conn, get_state
from ..security import local_only
from ..services import runner

router = APIRouter(prefix="/api/runner")


class IntervalIn(BaseModel):
    interval: str = Field(max_length=16)


class StartIn(BaseModel):
    interval: str | None = Field(None, max_length=16)


def _view(state: AppState, conn: sqlite3.Connection) -> dict:
    return runner.status(conn, can_start=local_only(state.settings.host))


@router.get("")
def get_runner(state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return _view(state, conn)


@router.put("")
def put_interval(
    body: IntervalIn, state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Save the interval. A running terminal keeps its own until it's restarted."""
    runner.set_interval(conn, body.interval)
    return _view(state, conn)


@router.post("/start")
def start_runner(
    body: StartIn, state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    runner.start(conn, state.settings.repo_root, body.interval, can_start=local_only(state.settings.host))
    return _view(state, conn)


@router.post("/stop")
def stop_runner(state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    runner.stop(conn)
    return _view(state, conn)
