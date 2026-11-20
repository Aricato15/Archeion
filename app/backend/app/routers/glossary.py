"""Project glossaries API (ADR 0023): terms kept in registry/glossary/<project>.json."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from ..deps import AppState, get_state
from ..services import demo
from ..services import glossary as gl

router = APIRouter(prefix="/api/glossary", dependencies=[Depends(demo.read_only)])

ProjectParam = Path(max_length=64, pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
TermParam = Path(max_length=140, pattern=r"^[a-z0-9][a-z0-9-]*$")


class TermBody(BaseModel):
    term: str = Field(max_length=gl.MAX_TERM)
    definition: str = Field(max_length=gl.MAX_DEFINITION)
    aliases: list[str] = Field(default_factory=list, max_length=gl.MAX_ALIASES)


def _check(state: AppState, project: str) -> None:
    if project not in state.sources.registry.projects:
        raise HTTPException(404, f"no registered project named '{project}'")


@router.get("/{project}")
def terms(project: str = ProjectParam, state: AppState = Depends(get_state)) -> list[dict]:
    _check(state, project)
    return gl.load(demo.root_for(state.settings, project), project)


@router.post("/{project}", status_code=201)
def add(body: TermBody, project: str = ProjectParam, state: AppState = Depends(get_state)) -> dict:
    _check(state, project)
    try:
        return gl.upsert(state.settings.registry_root, project, body.model_dump())
    except gl.GlossaryError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/{project}/{term_id}")
def change(
    body: TermBody,
    project: str = ProjectParam,
    term_id: str = TermParam,
    state: AppState = Depends(get_state),
) -> dict:
    _check(state, project)
    try:
        return gl.upsert(state.settings.registry_root, project, body.model_dump(), replace=term_id)
    except gl.TermNotFound as exc:
        raise HTTPException(404, f"no term '{term_id}'") from exc
    except gl.GlossaryError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/{project}/{term_id}", status_code=204)
def delete(
    project: str = ProjectParam, term_id: str = TermParam, state: AppState = Depends(get_state)
) -> None:
    _check(state, project)
    try:
        gl.remove(state.settings.registry_root, project, term_id)
    except gl.TermNotFound as exc:
        raise HTTPException(404, f"no term '{term_id}'") from exc
