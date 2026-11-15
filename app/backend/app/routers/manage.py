"""Managing roots and registering projects from the viewer (ADR 0010).

The only files the backend writes: the ARCHEION_ROOTS line of .env, new pages in
registry/projects/, and the `type:` (ADR 0016) and `inbox_edits:` (ADR 0017) lines of an
existing page there. Never a project's files, never anything else in an existing registry page.
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import AppState, get_state
from ..services.events import Event
from ..services.registry import register, set_inbox_edits, set_type, survey
from ..services.roots import (
    ENV_KEY,
    NAME_RE,
    WORKSPACE,
    WORKSPACE_KEY,
    format_roots,
    parse_roots,
    write_env,
)

router = APIRouter(prefix="/api")


class RootIn(BaseModel):
    name: str = Field(max_length=64)
    folder: str = Field(max_length=1024)


class RootsIn(BaseModel):
    roots: list[RootIn] = Field(max_length=50)
    # False removes the workspace root (ARCHEION_WORKSPACE_ROOT); it can't be added here,
    # because new roots are named roots (ADR 0012).
    keep_workspace: bool = True


class RegisterIn(BaseModel):
    root: str | None = Field(None, max_length=64)
    path: str = Field(max_length=1024)
    name: str = Field(max_length=64)
    type: Literal["project", "module"] | None = None  # None: detected (ADR 0016)


class TypeIn(BaseModel):
    type: Literal["project", "module"] | None  # None: back to detection


class InboxEditsIn(BaseModel):
    inbox_edits: bool | None  # None: the default (a module follows its project)


def _locked() -> str | None:
    for key in (ENV_KEY, WORKSPACE_KEY):
        if key in os.environ:
            return (
                f"{key} is set in the environment Archeion was started with, and that overrides .env. "
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
        "workspace": (
            {"name": WORKSPACE, "folder": str(roots.workspace), "projects": used.get(WORKSPACE, [])}
            if roots.workspace is not None
            else None
        ),
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
    drop_workspace = not body.keep_workspace and state.sources.roots.workspace is not None
    roots = parse_roots(raw, settings.repo_root, None if drop_workspace else state.sources.roots.workspace)
    problems += roots.errors
    if problems:
        raise ValueError("Not saved: " + "; ".join(problems))
    values = {ENV_KEY: raw}
    if drop_workspace:
        values[WORKSPACE_KEY] = ""
        settings.workspace_root = ""
    write_env(settings.repo_root / ".env", values)
    settings.roots = raw
    for cached in ("project_roots", "workspace_dir"):
        settings.__dict__.pop(cached, None)
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
        type=body.type,
    )
    m.reload()
    _changed(state)
    project = m.registry.projects.get(body.name.strip())
    return {"page": page, "project": project.public() if project else None}


@router.put("/registry/projects/{project_id}/type")
async def put_project_type(project_id: str, body: TypeIn, state: AppState = Depends(get_state)) -> dict:
    m = state.sources
    try:
        set_type(m.registry_root, m.registry, project_id, body.type)
    except KeyError:
        raise HTTPException(404, f"no project named '{project_id}'") from None
    m.reload()
    _changed(state)
    return m.registry.projects[project_id].public()


@router.put("/registry/projects/{project_id}/inbox-edits")
async def put_inbox_edits(project_id: str, body: InboxEditsIn, state: AppState = Depends(get_state)) -> dict:
    """Whether Archeion's /inbox may edit the project's files for its inbox items (ADR 0017)."""
    m = state.sources
    try:
        set_inbox_edits(m.registry_root, m.registry, project_id, body.inbox_edits)
    except KeyError:
        raise HTTPException(404, f"no project named '{project_id}'") from None
    m.reload()
    _changed(state)
    return m.registry.projects[project_id].public()
