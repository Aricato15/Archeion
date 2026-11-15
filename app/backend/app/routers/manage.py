"""Managing roots and registering projects from the viewer (ADR 0010).

The only files the backend writes: the ARCHEION_ROOTS line of .env, and new pages in
registry/projects/. Never a project's files, never an existing registry page.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..deps import AppState, get_state
from ..services.events import Event
from ..services.registry import register, survey
from ..services.roots import ENV_KEY, NAME_RE, WORKSPACE, format_roots, parse_roots, write_env_roots

router = APIRouter(prefix="/api")


class RootIn(BaseModel):
    name: str = Field(max_length=64)
    folder: str = Field(max_length=1024)


class RootsIn(BaseModel):
    roots: list[RootIn] = Field(max_length=50)


class RegisterIn(BaseModel):
    root: str | None = Field(None, max_length=64)
    path: str = Field(max_length=1024)
    name: str = Field(max_length=64)


def _locked() -> str | None:
    if ENV_KEY in os.environ:
        return (
            f"{ENV_KEY} is set in the environment Archeion was started with, and that overrides .env. "
            "Change it there, or unset it and restart Archeion to edit roots here."
        )
    return None


def _roots_view(state: AppState) -> dict:
    roots = state.sources.roots
    reg = state.sources.registry
    used: dict[str, list[str]] = {}
    for p in reg.projects.values():
        used.setdefault(p.root or WORKSPACE, []).append(p.id)
    locked = _locked()
    return {
        "workspace": {"name": WORKSPACE, "folder": str(roots.workspace), "projects": used.get(WORKSPACE, [])},
        "roots": [
            {"name": name, "folder": str(folder), "projects": used.get(name, [])}
            for name, folder in roots.named.items()
        ],
        "errors": roots.errors,
        "editable": locked is None,
        "locked_reason": locked,
    }


def _changed(state: AppState) -> None:
    """Tell the viewer and restart the file watchers with the new sources. Called on the
    event loop (async routes), where asyncio.Event may be set."""
    state.bus.publish(Event("registry.changed", {"version": state.sources.version}))
    state.sources.changed.set()


@router.get("/settings/roots")
def get_roots(state: AppState = Depends(get_state)) -> dict:
    return _roots_view(state)


@router.put("/settings/roots")
async def put_roots(body: RootsIn, state: AppState = Depends(get_state)) -> dict:
    locked = _locked()
    if locked:
        raise ValueError(locked)
    settings = state.settings
    problems = [
        f"root name '{r.name}' must be 2-32 characters of lowercase letters, digits and -"
        for r in body.roots
        if not NAME_RE.match(r.name.strip())
    ]
    raw, more = format_roots([(r.name, r.folder) for r in body.roots])
    problems += more
    roots = parse_roots(raw, settings.repo_root, settings.workspace_dir)
    problems += roots.errors
    if problems:
        raise ValueError("Not saved: " + "; ".join(problems))
    write_env_roots(settings.repo_root / ".env", raw)
    settings.roots = raw
    settings.__dict__.pop("project_roots", None)
    state.sources.set_roots(roots)
    _changed(state)
    return _roots_view(state)


@router.get("/registry/roots")
def get_survey(state: AppState = Depends(get_state)) -> list[dict]:
    m = state.sources
    return survey(m.registry, m.repo_root, m.roots)


@router.post("/registry/projects", status_code=201)
async def post_project(body: RegisterIn, state: AppState = Depends(get_state)) -> dict:
    m = state.sources
    page = register(
        m.registry_root,
        m.registry,
        m.repo_root,
        m.roots,
        root=body.root,
        path=body.path,
        name=body.name.strip(),
    )
    m.reload()
    _changed(state)
    project = m.registry.projects.get(body.name.strip())
    return {"page": page, "project": project.public() if project else None}
