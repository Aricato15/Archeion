"""Docs viewer routes. Every route takes `source`: "archeion" (this repo's docs/, the
default) or a registered project's id, whose files are served read-only (ADR 0006)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..deps import AppState, get_state
from ..paths import IMAGE_TYPES, MARKDOWN_EXT, DocNotFound, DocPathError, validate_rel_path
from ..services import docs_fs, git
from ..services.sources import Source

router = APIRouter(prefix="/api/docs")
extra = APIRouter(prefix="/api")

# Images can be SVG: never let one run script or load anything.
IMAGE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "Cache-Control": "no-cache",
}

SourceParam = Query("archeion", max_length=64)


def _source(state: AppState, source_id: str) -> Source:
    return state.sources.get(source_id)


def _md_rel(source: Source, rel: str) -> str:
    """A well-formed .md path the source allows (the file need not exist, e.g. for history)."""
    rel = validate_rel_path(rel)
    if Path(rel).suffix.lower() != MARKDOWN_EXT:
        raise DocPathError("only Markdown docs have history")
    if not source.allows(rel):
        raise DocPathError("not part of this project's docs")
    return rel


@router.get("/tree")
def doc_tree(source: str = SourceParam, state: AppState = Depends(get_state)) -> dict:
    return _source(state, source).tree()


@router.get("/file")
def doc_file(
    path: str = Query(max_length=512), source: str = SourceParam, state: AppState = Depends(get_state)
) -> dict:
    src = _source(state, source)
    target = src.resolve(path, allowed={MARKDOWN_EXT})
    rel = validate_rel_path(path)
    info = docs_fs.file_info(target, rel)
    info["source"] = src.id
    try:
        info["private"] = git.is_ignored(src.root, rel)
        info["dirty"] = False if info["private"] else git.is_dirty(src.root, rel, info["content"])
    except git.GitError:
        info["private"], info["dirty"] = False, False
    return info


@router.get("/raw")
def doc_raw(
    path: str = Query(max_length=512), source: str = SourceParam, state: AppState = Depends(get_state)
) -> FileResponse:
    target = _source(state, source).resolve(path, allowed=set(IMAGE_TYPES))
    return FileResponse(target, media_type=IMAGE_TYPES[target.suffix.lower()], headers=IMAGE_HEADERS)


@router.get("/history")
def doc_history(
    path: str = Query(max_length=512),
    source: str = SourceParam,
    limit: int = Query(50, ge=1, le=200),
    state: AppState = Depends(get_state),
) -> list[dict]:
    src = _source(state, source)
    rel = _md_rel(src, path)
    return [c.__dict__ for c in git.history(src.root, rel, limit)]


@router.get("/diff")
def doc_diff(
    path: str = Query(max_length=512),
    rev: str = Query(max_length=40),
    source: str = SourceParam,
    state: AppState = Depends(get_state),
) -> dict:
    src = _source(state, source)
    rel = _md_rel(src, path)
    if rev == git.WORKTREE:
        target = src.resolve(rel, allowed={MARKDOWN_EXT})
        diff = git.worktree_diff(src.root, rel, docs_fs.read_text(target))
    elif git.valid_rev(rev):
        try:
            diff = git.commit_diff(src.root, rev, rel)
        except git.GitError as exc:
            raise HTTPException(404, "unknown revision") from exc
    else:
        raise DocPathError("invalid revision")
    return {"source": src.id, "path": rel, "rev": rev, "diff": diff}


@router.get("/at")
def doc_at(
    path: str = Query(max_length=512),
    rev: str = Query(max_length=40),
    source: str = SourceParam,
    state: AppState = Depends(get_state),
) -> dict:
    src = _source(state, source)
    rel = _md_rel(src, path)
    if not git.valid_rev(rev):
        raise DocPathError("invalid revision")
    content = git.show_file(src.root, rev, rel)
    if content is None:
        raise DocNotFound(rel)
    return {"source": src.id, "path": rel, "rev": rev, "content": content}


@extra.get("/roadmap")
def roadmap(state: AppState = Depends(get_state)) -> dict:
    """The cross-project roadmap plus every project's own, where one exists."""
    reg = state.sources.registry
    projects = []
    for p in reg.projects.values():
        if p.demo:
            continue  # the example project isn't one of the user's (ADR 0030)
        src = state.sources.sources.get(p.id)
        projects.append({"project": p.id, "title": p.title, "roadmap": docs_fs.roadmap(src) if src else None})
    return {"cross": docs_fs.roadmap(state.sources.get("archeion")), "projects": projects}


@extra.get("/diagrams")
def diagrams(
    source: str | None = Query(None, max_length=64), state: AppState = Depends(get_state)
) -> list[dict]:
    sources = [_source(state, source)] if source else state.sources.all()
    return docs_fs.diagrams(sources)


@extra.get("/search")
def search(
    q: str = Query(min_length=2, max_length=200),
    source: str | None = Query(None, max_length=64),
    state: AppState = Depends(get_state),
) -> list[dict]:
    sources = [_source(state, source)] if source else state.sources.all()
    return docs_fs.search(sources, q)


@extra.get("/changelog")
def changelog(state: AppState = Depends(get_state)) -> dict:
    """Archeion's own CHANGELOG.md, read from the repo root (the docs source is docs/, so it
    can't serve it). It's the file of whichever commit is checked out. Read-only."""
    path = state.settings.repo_root / "CHANGELOG.md"
    if not path.is_file():
        raise HTTPException(404, "this checkout has no CHANGELOG.md")
    return {"content": path.read_text(encoding="utf-8")}


@extra.get("/sources")
def sources(state: AppState = Depends(get_state)) -> list[dict]:
    return [s.public() for s in state.sources.all()]


@extra.get("/registry")
def registry(state: AppState = Depends(get_state)) -> dict:
    data = state.sources.registry.public()
    data["unregistered"] = state.sources.unregistered()
    return data
