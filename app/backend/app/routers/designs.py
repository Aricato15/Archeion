"""Designs API (ADR 0022): the Design tab's views of registry/designs/, and the user's moves
through its stages. Saving a design's content is the CLI's job (the design skill); the viewer
can move the stage, approve (which writes a revision and the structural lines of the project's
registry page) and ask for a handoff."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from ..deps import AppState, get_conn, get_state
from ..services import design_checks as checks
from ..services import designs as dz
from ..services import feedback as fb
from ..services import studies as st
from ..services.events import Event
from ..services.registry import SELF_ID, RegisterError, apply_structure, plan_structure

router = APIRouter(prefix="/api/designs")

ProjectParam = Path(max_length=64, pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
SlugParam = Path(max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*$")


def _project(state: AppState, name: str):
    p = state.sources.registry.projects.get(name)
    if p is None:
        raise HTTPException(404, f"no registered project named '{name}'")
    return p


def _ref(state: AppState, project: str, slug: str) -> dz.DesignRef:
    _project(state, project)
    try:
        return dz.get(state.settings.registry_root, project, slug)
    except dz.DesignNotFound:
        raise HTTPException(404, f"no design '{slug}' for {project}") from None


def _taken(state: AppState) -> dict[int, list[str]]:
    taken: dict[int, list[str]] = {}
    for p in state.sources.registry.projects.values():
        for port in p.ports:
            taken.setdefault(port, []).append(p.id)
    return taken


@router.get("")
def all_designs(state: AppState = Depends(get_state)) -> list[dict]:
    """Every registered project's designs (a row each), for the Projects page's stage badges."""
    reg = state.sources.registry
    root = state.settings.registry_root
    return [
        dz.summary(dz.get(root, name, slug))
        for name in dz.projects_with_designs(root)
        if name in reg.projects
        for slug in dz.slugs(root, name)
    ]


@router.get("/{project}")
def project_designs(project: str = ProjectParam, state: AppState = Depends(get_state)) -> list[dict]:
    p = _project(state, project)
    root = state.settings.registry_root
    return [dz.summary(dz.get(root, p.id, s)) for s in dz.slugs(root, p.id)]


@router.get("/{project}/preflight")
def preflight(
    project: str = ProjectParam,
    purpose: Literal["design", "handoff"] = Query("design", alias="for"),
    slug: str = Query(dz.DEFAULT_SLUG, max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*$"),
    state: AppState = Depends(get_state),
) -> dict:
    """What stands in the way of designing or handing off this project, with each fix."""
    m = state.sources
    unregistered = [u["name"] for u in m.unregistered()] if m.roots.all() else []
    reg = m.registry
    problems = dz.preflight(
        reg,
        project=project,
        unregistered=unregistered,
        purpose=purpose,
        slug=slug,
        registry_root=state.settings.registry_root,
        has_study=bool(project in reg.projects and st.snapshots(state.settings.registry_root, project)),
    )
    return {"ok": not any(x["severity"] == "block" for x in problems), "problems": problems}


@router.get("/{project}/{slug}")
def design(
    project: str = ProjectParam,
    slug: str = SlugParam,
    revision: str | None = Query(None, max_length=20, pattern=r"^(latest|r?\d+)$"),
    state: AppState = Depends(get_state),
) -> dict:
    """The working copy, or a frozen revision, with its files, model and problems."""
    ref = _ref(state, project, slug)
    folder, label = ref.folder, "working copy"
    if revision:
        try:
            rev, folder = dz.revision_folder(ref, revision)
        except dz.DesignNotFound as exc:
            raise HTTPException(404, str(exc)) from None
        label = f"revision {rev['number']}"
    model, problems = dz.load(folder, project)
    return {
        **dz.summary(ref),
        "label": label,
        "files": dz.read_files(folder),
        "model": model,
        "model_problems": problems,
    }


class StageIn(BaseModel):
    stage: Literal["brief", "architecture", "plan"]


@router.put("/{project}/{slug}/stage")
def put_stage(
    body: StageIn,
    project: str = ProjectParam,
    slug: str = SlugParam,
    state: AppState = Depends(get_state),
) -> dict:
    """The user moves a design between brief, architecture and plan. Going back is allowed."""
    ref = _ref(state, project, slug)
    dz.set_stage(ref, body.stage)
    return dz.summary(ref)


@router.get("/{project}/{slug}/approval")
def approval(
    project: str = ProjectParam, slug: str = SlugParam, state: AppState = Depends(get_state)
) -> dict:
    """What approving would do: what stops it, and which registry-page lines it would change."""
    ref = _ref(state, project, slug)
    reg = state.sources.registry
    problems = dz.approval_problems(ref, reg, _taken(state))
    changes: list[dict] = []
    if not problems:
        model, _ = dz.load(ref.folder, project)
        try:
            changes = plan_structure(state.sources.registry_root, reg, project, model.get("structure", {}))
        except RegisterError as exc:
            problems.append(str(exc))
    revs = dz.revisions(ref)
    return {
        "problems": problems,
        "changes": changes,
        "page": reg.projects[project].page,
        "next_revision": (revs[0]["number"] if revs else 0) + 1,
    }


@router.post("/{project}/{slug}/approve")
async def approve(
    project: str = ProjectParam, slug: str = SlugParam, state: AppState = Depends(get_state)
) -> dict:
    """Freeze a revision and write the design's structural facts into the project's registry page."""
    ref = _ref(state, project, slug)
    m = state.sources
    reg = m.registry
    taken = _taken(state)
    try:
        model, _ = dz.load(ref.folder, project)
        structure = model.get("structure", {})
        plan = plan_structure(m.registry_root, reg, project, structure)
        rev = dz.approve(ref, reg, taken)
        if plan:
            apply_structure(m.registry_root, reg, project, structure)
    except (dz.DesignError, RegisterError) as exc:
        raise HTTPException(409, str(exc)) from None
    if plan:
        m.reload()
        state.bus.publish(Event("registry.changed", {"version": m.version}))
        m.changed.set()
    return {**dz.summary(ref), "approved": rev["id"], "changes": plan}


@router.post("/{project}/{slug}/handoff", status_code=201)
def handoff(
    project: str = ProjectParam,
    slug: str = SlugParam,
    state: AppState = Depends(get_state),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Ask Archeion's inbox to deliver the latest revision to the project's own folder."""
    ref = _ref(state, project, slug)
    m = state.sources
    unregistered = [u["name"] for u in m.unregistered()] if m.roots.all() else []
    blocking = [
        x
        for x in dz.preflight(
            m.registry,
            project=project,
            unregistered=unregistered,
            purpose="handoff",
            slug=slug,
            registry_root=state.settings.registry_root,
            has_study=True,
        )
        if x["severity"] == "block"
    ]
    if blocking:
        raise HTTPException(409, "; ".join(x["message"] for x in blocking))
    rev, _ = dz.revision_folder(ref, "latest")
    body = (
        f"Deliver revision {rev['number']} of the design '{slug}' to {project}: copy its package into the"
        f" project's {dz.PACKAGE_DIR}/{slug}/ with `design package {project} --slug {slug}"
        f" --revision {rev['number']}`, then reply with the files. The project's session then runs"
        " /archeion:consume-design."
    )
    anchor = {"task": {"type": "handoff-design", "project": project, "slug": slug, "revision": rev["number"]}}
    item = fb.create(conn, kind="prompt", body=body, anchor=anchor, source=SELF_ID)
    dz.record_handoff(ref, rev["number"], item["thread_id"])
    return item


@router.get("/{project}/{slug}/impact")
def impact(
    project: str = ProjectParam, slug: str = SlugParam, state: AppState = Depends(get_state)
) -> list[dict]:
    """What the design asks of other projects: calls to endpoints no neighbour exposes, dropped
    endpoints others call, dependencies the model contradicts, ports in use. Each can be sent to
    the neighbour's inbox from the viewer."""
    ref = _ref(state, project, slug)
    model, _ = dz.load(ref.folder, project)
    return checks.impact(state.sources.registry, state.settings.registry_root, project, model)


@router.get("/{project}/{slug}/built")
def built(project: str = ProjectParam, slug: str = SlugParam, state: AppState = Depends(get_state)) -> dict:
    """The design's model against the project's latest study: what's still to build, and what was
    built that the design doesn't say."""
    ref = _ref(state, project, slug)
    model, _ = dz.load(ref.folder, project)
    snaps = st.snapshots(state.settings.registry_root, project)
    if not snaps:
        return {"studied": None, "sections": {}}
    built_model, problems = st.load(snaps[0])
    return checks.built_vs_designed(model, None if problems else built_model, snaps[0].id)
