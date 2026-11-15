"""Docs viewer routes: tree, files, images, history, diffs, roadmap, diagrams, search."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..deps import AppState, get_state
from ..paths import IMAGE_TYPES, MARKDOWN_EXT, DocNotFound, DocPathError, resolve_doc_path, validate_rel_path
from ..services import docs_fs, git

router = APIRouter(prefix="/api/docs")
extra = APIRouter(prefix="/api")

# Images can be SVG: never let one run script or load anything.
IMAGE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "Cache-Control": "no-cache",
}


def _md_rel(rel: str) -> str:
    """A well-formed .md path under docs/ (the file need not exist, e.g. for history)."""
    rel = validate_rel_path(rel)
    if Path(rel).suffix.lower() != MARKDOWN_EXT:
        raise DocPathError("only Markdown docs have history")
    return rel


def _repo_rel(rel: str) -> str:
    return f"docs/{rel}"


@router.get("/tree")
def doc_tree(state: AppState = Depends(get_state)) -> dict:
    return docs_fs.tree(state.settings.docs_root)


@router.get("/file")
def doc_file(path: str = Query(max_length=512), state: AppState = Depends(get_state)) -> dict:
    target = resolve_doc_path(state.settings.docs_root, path, allowed={MARKDOWN_EXT})
    rel = validate_rel_path(path)
    info = docs_fs.file_info(target, rel)
    try:
        info["dirty"] = git.is_dirty(state.settings.repo_root, _repo_rel(rel), info["content"])
    except git.GitError:
        info["dirty"] = False
    return info


@router.get("/raw")
def doc_raw(path: str = Query(max_length=512), state: AppState = Depends(get_state)) -> FileResponse:
    target = resolve_doc_path(state.settings.docs_root, path, allowed=set(IMAGE_TYPES))
    return FileResponse(target, media_type=IMAGE_TYPES[target.suffix.lower()], headers=IMAGE_HEADERS)


@router.get("/history")
def doc_history(
    path: str = Query(max_length=512),
    limit: int = Query(50, ge=1, le=200),
    state: AppState = Depends(get_state),
) -> list[dict]:
    rel = _md_rel(path)
    return [c.__dict__ for c in git.history(state.settings.repo_root, _repo_rel(rel), limit)]


@router.get("/diff")
def doc_diff(
    path: str = Query(max_length=512), rev: str = Query(max_length=40), state: AppState = Depends(get_state)
) -> dict:
    rel = _md_rel(path)
    repo = state.settings.repo_root
    if rev == git.WORKTREE:
        target = resolve_doc_path(state.settings.docs_root, rel, allowed={MARKDOWN_EXT})
        diff = git.worktree_diff(repo, _repo_rel(rel), docs_fs.read_text(target))
    elif git.valid_rev(rev):
        try:
            diff = git.commit_diff(repo, rev, _repo_rel(rel))
        except git.GitError as exc:
            raise HTTPException(404, "unknown revision") from exc
    else:
        raise DocPathError("invalid revision")
    return {"path": rel, "rev": rev, "diff": diff}


@router.get("/at")
def doc_at(
    path: str = Query(max_length=512), rev: str = Query(max_length=40), state: AppState = Depends(get_state)
) -> dict:
    rel = _md_rel(path)
    if not git.valid_rev(rev):
        raise DocPathError("invalid revision")
    content = git.show_file(state.settings.repo_root, rev, _repo_rel(rel))
    if content is None:
        raise DocNotFound(rel)
    return {"path": rel, "rev": rev, "content": content}


@extra.get("/roadmap")
def roadmap(state: AppState = Depends(get_state)) -> dict:
    return docs_fs.roadmap(state.settings.docs_root)


@extra.get("/diagrams")
def diagrams(state: AppState = Depends(get_state)) -> list[dict]:
    return docs_fs.diagrams(state.settings.docs_root)


@extra.get("/search")
def search(q: str = Query(min_length=2, max_length=200), state: AppState = Depends(get_state)) -> list[dict]:
    return docs_fs.search(state.settings.docs_root, q)
