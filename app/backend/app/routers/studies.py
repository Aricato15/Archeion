"""Code studies API (ADR 0019): read-only views of the snapshots in registry/studies/.
Snapshots are written only by the CLI (`study save`), never through the API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ..deps import AppState, get_state
from ..services import git, study_compose
from ..services import studies as st
from ..services.registry import Project

router = APIRouter(prefix="/api/studies")
system = APIRouter(prefix="/api/system")

ProjectParam = Path(max_length=64, pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
SnapshotParam = Path(max_length=40, pattern=r"^(latest|draft|\d{4}-\d{2}-\d{2}-[0-9a-f]{7}(-\d+)?)$")


def _project(state: AppState, name: str) -> Project:
    p = state.sources.registry.projects.get(name)
    if p is None:
        raise HTTPException(404, f"no registered project named '{name}'")
    return p


def commits_since(p: Project | None, commit: str | None) -> int | None:
    if p is None or p.dir is None or not commit:
        return None
    try:
        return git.commits_since(p.dir, commit)
    except git.GitError:
        return None


def _row(state: AppState, snap: st.Snapshot) -> dict:
    row = st.summary(snap)
    row["commits_since"] = commits_since(state.sources.registry.projects.get(snap.project), row["commit"])
    return row


@router.get("")
def latest(state: AppState = Depends(get_state)) -> list[dict]:
    """Every registered project's latest snapshot. Studies of projects no longer registered
    stay on disk but aren't listed."""
    reg = state.sources.registry
    found = st.latest_by_project(state.settings.registry_root)
    return [_row(state, snap) for name, snap in sorted(found.items()) if name in reg.projects]


@router.get("/search")
def search(q: str = Query(min_length=2, max_length=200), state: AppState = Depends(get_state)) -> list[dict]:
    """Elements of every registered project's latest study that match `q`."""
    reg = state.sources.registry
    latest = {}
    for name, snap in st.latest_by_project(state.settings.registry_root).items():
        if name in reg.projects:
            latest[name] = (snap.id, st.load(snap)[0])
    return st.search(latest, q)


@router.get("/{project}")
def project_snapshots(project: str = ProjectParam, state: AppState = Depends(get_state)) -> list[dict]:
    """Newest first, with the draft of a study in progress (ADR 0020) ahead of them."""
    p = _project(state, project)
    draft = st.get_draft(state.settings.registry_root, p.id)
    snaps = st.snapshots(state.settings.registry_root, p.id)
    return [_row(state, s) for s in ([draft] if draft else []) + snaps]


@router.get("/{project}/diff")
def diff(
    project: str = ProjectParam,
    from_: str = Query(alias="from", max_length=40),
    to: str = Query("latest", max_length=40),
    state: AppState = Depends(get_state),
) -> dict:
    """What changed between two snapshots, section by section, matched by element id."""
    p = _project(state, project)
    try:
        a = st.get_snapshot(state.settings.registry_root, p.id, from_)
        b = st.get_snapshot(state.settings.registry_root, p.id, to)
    except st.StudyNotFound as exc:
        raise HTTPException(404, f"no snapshot {exc.args[0]}") from exc
    return {"from": a.id, "to": b.id, "sections": st.diff(st.load(a)[0], st.load(b)[0])}


@router.get("/{project}/composed")
def composed(project: str = ProjectParam, state: AppState = Depends(get_state)) -> dict:
    """A group's own study and its members' latest studies, put together (ADR 0027)."""
    p = _project(state, project)
    if p.type != "group":
        raise HTTPException(409, f"'{project}' isn't a group")
    reg = state.sources.registry
    out = study_compose.compose(state.settings.registry_root, reg, p.id)
    for row in out["members"]:
        snap = row["snapshot"]
        member = reg.projects.get(row["project"])
        row["commits_since"] = commits_since(member, row["commit"]) if snap and member else None
    return out


@router.get("/{project}/{snapshot}")
def snapshot(
    project: str = ProjectParam, snapshot: str = SnapshotParam, state: AppState = Depends(get_state)
) -> dict:
    p = _project(state, project)
    try:
        snap = st.get_snapshot(state.settings.registry_root, p.id, snapshot)
    except st.StudyNotFound as exc:
        raise HTTPException(404, f"no snapshot {exc.args[0]}") from exc
    model, problems = st.load(snap)
    return {**_row(state, snap), "model": model, "notes_text": st.load_notes(snap), "problems": problems}


@system.get("/links")
def links(state: AppState = Depends(get_state)) -> dict:
    """Links between projects found in their code, and where they disagree with depends_on."""
    reg = state.sources.registry
    found = st.latest_by_project(state.settings.registry_root)
    models = {}
    for name, snap in found.items():
        if name in reg.projects:
            model, problems = st.load(snap)
            if not problems:
                models[name] = model
    return st.system_links(
        {p.id: p.ports for p in reg.projects.values()},
        {p.id: p.depends_on for p in reg.projects.values()},
        models,
    )
