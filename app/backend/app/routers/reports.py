"""Project PDF reports API (ADR 0025): the catalog, presets and the content a report is drawn from."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict

from ..deps import AppState, get_state
from ..services import reports as rp

router = APIRouter(prefix="/api/reports")

ProjectParam = Path(max_length=64, pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
NameParam = Path(max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*$")


class PresetBody(BaseModel):
    """Any shape: `validate_preset` checks it against the catalog and says what's wrong."""

    model_config = ConfigDict(extra="allow")


def _check(state: AppState, project: str) -> None:
    if project not in state.sources.registry.projects:
        raise HTTPException(404, f"no registered project named '{project}'")


@router.get("/{project}/catalog")
def catalog(project: str = ProjectParam, state: AppState = Depends(get_state)) -> list[dict]:
    _check(state, project)
    return rp.catalog(state.sources, state.settings.registry_root, project)


@router.get("/{project}/preflight")
def preflight(project: str = ProjectParam, state: AppState = Depends(get_state)) -> dict:
    _check(state, project)
    return rp.preflight(state.sources, state.settings.registry_root, project, state.settings.report_browser)


@router.get("/{project}/presets")
def presets(project: str = ProjectParam, state: AppState = Depends(get_state)) -> list[dict]:
    _check(state, project)
    return rp.list_presets(state.settings.registry_root, project)


@router.put("/{project}/presets")
def save_preset(body: PresetBody, project: str = ProjectParam, state: AppState = Depends(get_state)) -> dict:
    _check(state, project)
    entries = rp.catalog(state.sources, state.settings.registry_root, project)
    try:
        return rp.save_preset(state.settings.registry_root, project, body.model_dump(), entries)
    except rp.ReportError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/{project}/presets/{name}", status_code=204)
def delete_preset(
    project: str = ProjectParam, name: str = NameParam, state: AppState = Depends(get_state)
) -> None:
    _check(state, project)
    try:
        rp.delete_preset(state.settings.registry_root, project, name)
    except rp.PresetNotFound as exc:
        raise HTTPException(404, f"no preset '{name}'") from exc


@router.get("/{project}/presets/{name}/content")
def content(project: str = ProjectParam, name: str = NameParam, state: AppState = Depends(get_state)) -> dict:
    _check(state, project)
    try:
        preset = rp.get_preset(state.settings.registry_root, project, name)
        return rp.content(state.sources, state.settings.registry_root, project, preset)
    except rp.PresetNotFound as exc:
        raise HTTPException(404, f"no preset '{name}'") from exc
    except rp.ReportError as exc:
        raise HTTPException(422, str(exc)) from exc
