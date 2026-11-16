"""On-demand Claude, switched on, run and watched from the viewer (ADR 0020)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import AppState, get_conn, get_state
from ..security import local_only
from ..services import responder

router = APIRouter(prefix="/api/responder")


class SettingsIn(BaseModel):
    enabled: bool | None = None
    # ADR 0021: no window at all, and how many Claude processes may run at once.
    headless: bool | None = None
    max_instances: int | None = Field(None, ge=1, le=2)


def granted_dirs(state: AppState) -> list[Path]:
    """The folders a run may read and edit besides the repo: every granted root."""
    return [path for _, path in state.sources.roots.all()]


def _view(state: AppState, conn: sqlite3.Connection) -> dict:
    return responder.status(conn, can_start=local_only(state.settings.host))


@router.get("")
def get_responder(state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return _view(state, conn)


@router.put("")
def put_settings(
    body: SettingsIn, state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    responder.update(
        conn,
        enabled=body.enabled,
        headless=body.headless,
        max_instances=body.max_instances,
        can_start=local_only(state.settings.host),
    )
    return _view(state, conn)


@router.post("/run")
def run_now(state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """One run now, switched on or not."""
    responder.start(
        conn, state.settings.repo_root, granted_dirs(state), can_start=local_only(state.settings.host)
    )
    return _view(state, conn)


@router.post("/stop")
def stop(state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    responder.stop(conn)
    return _view(state, conn)
