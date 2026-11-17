"""Project PDF reports API (ADR 0025): the catalog, presets and the content a report is drawn from."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from ..deps import AppState, get_state
from ..services import report_render as rr
from ..services import reports as rp

router = APIRouter(prefix="/api/reports")

ProjectParam = Path(max_length=64, pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
NameParam = Path(max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*$")
FileParam = Path(max_length=130, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\.pdf$")
JobParam = Path(pattern=r"^[0-9a-f]{12}$")


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
    return rp.preflight(
        state.sources,
        state.settings.registry_root,
        project,
        state.settings.report_browser,
        rr.frontend_up(state.settings),
    )


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


@router.post("/{project}/presets/{name}/build", status_code=202)
def build(project: str = ProjectParam, name: str = NameParam, state: AppState = Depends(get_state)) -> dict:
    """Starts building the preset into a PDF in the background; poll the job it returns."""
    _check(state, project)
    try:
        rp.get_preset(state.settings.registry_root, project, name)
        return state.report_jobs.start(
            project, name, lambda: rr.build(state.settings, state.sources, project, name)
        )
    except rp.PresetNotFound as exc:
        raise HTTPException(404, f"no preset '{name}'") from exc
    except rp.ReportError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{project}/builds/{job}")
def build_status(
    project: str = ProjectParam, job: str = JobParam, state: AppState = Depends(get_state)
) -> dict:
    _check(state, project)
    found = state.report_jobs.get(job)
    if found is None or found["project"] != project:
        raise HTTPException(404, "no such build")
    return found


@router.get("/{project}/files")
def files(project: str = ProjectParam, state: AppState = Depends(get_state)) -> list[dict]:
    _check(state, project)
    return rr.list_reports(state.settings.registry_root, project)


@router.get("/{project}/files/{filename}")
def download(
    project: str = ProjectParam,
    filename: str = FileParam,
    inline: bool = False,
    state: AppState = Depends(get_state),
) -> FileResponse:
    _check(state, project)
    try:
        path = rr.report_file(state.settings.registry_root, project, filename)
    except rp.PresetNotFound as exc:
        raise HTTPException(404, "no such report") from exc
    except rp.ReportError as exc:
        raise HTTPException(422, str(exc)) from exc
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline" if inline else "attachment",
    )


@router.get("/{project}/files/{filename}/verify")
def verify(
    project: str = ProjectParam, filename: str = FileParam, state: AppState = Depends(get_state)
) -> dict:
    _check(state, project)
    try:
        return rr.verify(state.settings.registry_root, project, filename)
    except rp.PresetNotFound as exc:
        raise HTTPException(404, "no such report") from exc


@router.delete("/{project}/files/{filename}", status_code=204)
def delete_file(
    project: str = ProjectParam, filename: str = FileParam, state: AppState = Depends(get_state)
) -> None:
    _check(state, project)
    try:
        rr.delete_report(state.settings.registry_root, project, filename)
    except rp.PresetNotFound as exc:
        raise HTTPException(404, "no such report") from exc
