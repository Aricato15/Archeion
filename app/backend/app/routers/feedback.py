"""Feedback API: what the browser uses to write prompts, reviews and comments for Claude."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator

from ..deps import AppState, get_conn, get_state
from ..paths import MARKDOWN_EXT, validate_rel_path
from ..services import feedback as fb
from ..services import git

router = APIRouter(prefix="/api/feedback")

Kind = Literal["prompt", "review", "comment"]
Status = Literal["open", "in_progress", "answered", "resolved"]


class StudyAnchor(BaseModel):
    """An element of a code study (ADR 0019): what a question about the study is about."""

    project: str = Field(max_length=64, pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
    # A saved snapshot, or the draft of a study in progress (ADR 0020).
    snapshot: str = Field(max_length=40, pattern=r"^(draft|\d{4}-\d{2}-\d{2}-[0-9a-f]{7}(-\d+)?)$")
    element: str = Field(max_length=120, pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
    kind: Literal["component", "flow", "activity", "state machine", "entity", "interface", "finding"]


class TaskAnchor(BaseModel):
    """A job the thread is about, such as studying a project (ADR 0020). Handled by
    Archeion's own inbox, whatever the project."""

    type: Literal["study", "design", "handoff-design", "report"]
    project: str = Field(max_length=64, pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
    # A design task is about one design of the project (ADR 0022); a handoff names a revision.
    slug: str | None = Field(None, max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*$")
    revision: int | None = Field(None, ge=1)


class Anchor(BaseModel):
    heading: str | None = Field(None, max_length=300)
    lines: tuple[int, int] | None = None
    quote: str | None = Field(None, max_length=2000)
    study: StudyAnchor | None = None
    task: TaskAnchor | None = None

    @field_validator("lines")
    @classmethod
    def _lines(cls, v: tuple[int, int] | None) -> tuple[int, int] | None:
        if v is not None and not (1 <= v[0] <= v[1] <= 1_000_000):
            raise ValueError("lines must be [start, end] with 1 <= start <= end")
        return v


class FeedbackIn(BaseModel):
    # A follow-up (parent_id) takes its thread's kind, project and doc when they're left out.
    kind: Kind | None = None
    body: str = Field(min_length=1, max_length=20_000)
    doc_path: str | None = Field(None, max_length=512)
    anchor: Anchor | None = None
    parent_id: int | None = None
    # archeion or a registered project. A follow-up always stays with its thread's project.
    source: str | None = Field(None, max_length=64)

    @model_validator(mode="after")
    def _check(self) -> FeedbackIn:
        if self.parent_id is None and self.kind is None:
            raise ValueError("a new thread needs a kind")
        if self.anchor is not None and self.doc_path is None and not (self.anchor.study or self.anchor.task):
            raise ValueError("an anchor needs a doc_path, unless it points at a study element")
        return self


class ReplyIn(BaseModel):
    reply: str = Field(min_length=1, max_length=50_000)


class PatchIn(BaseModel):
    status: Status | None = None
    body: str | None = Field(None, min_length=1, max_length=20_000)


@router.post("", status_code=status.HTTP_201_CREATED)
def create(
    item: FeedbackIn, state: AppState = Depends(get_state), conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    kind, source_id, doc_path = item.kind, item.source, None
    if item.parent_id is not None:
        # A thread is about one thing (ADR 0018): a follow-up keeps the root's project, and
        # its kind and doc unless it names its own.
        root = fb.root(conn, item.parent_id)
        kind = kind or root["kind"]
        source_id = root["source"]
        if item.doc_path is None:
            doc_path = root["doc_path"]
    src = state.sources.get(source_id or "archeion")
    if item.doc_path is not None:
        src.resolve(item.doc_path, allowed={MARKDOWN_EXT})
        doc_path = validate_rel_path(item.doc_path)
    try:
        rev = git.head(src.root)
    except git.GitError:
        rev = None
    anchor = item.anchor.model_dump(exclude_none=True) if item.anchor else None
    if item.anchor and item.anchor.task:
        if item.anchor.task.project not in state.sources.registry.projects:
            raise ValueError(f"'{item.anchor.task.project}' isn't a registered project")
        if src.id != "archeion":
            raise ValueError("a task is for Archeion's inbox: leave out source, or use archeion")
    assert kind is not None
    return fb.create(
        conn,
        kind=kind,
        body=item.body,
        doc_path=doc_path,
        anchor=anchor or None,
        parent_id=item.parent_id,
        doc_rev=rev,
        source=src.id,
    )


@router.get("")
def list_items(
    status_: Status | None = Query(None, alias="status"),
    doc_path: str | None = None,
    kind: Kind | None = None,
    source: str | None = Query(None, max_length=64),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    """One row per thread (ADR 0018), filtered by the thread's status and its root's fields."""
    return fb.list_threads(conn, status=status_, doc_path=doc_path, kind=kind, source=source)


@router.get("/summary")
def summary(
    source: str | None = Query(None, max_length=64), conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    """Threads per status (optionally for one source), plus waiting threads per source."""
    return {**fb.summary(conn, source), "waiting_by_source": fb.open_by_source(conn)}


@router.get("/{item_id}")
def get_item(item_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return {"item": fb.get(conn, item_id), "thread": fb.thread(conn, item_id)}


@router.post("/{item_id}/claim")
def claim(item_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return fb.claim(conn, item_id)


@router.post("/{item_id}/reply")
def reply(item_id: int, body: ReplyIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return fb.reply(conn, item_id, body.reply)


class ReopenIn(BaseModel):
    body: str | None = Field(None, max_length=20_000)


@router.post("/{item_id}/reopen", status_code=status.HTTP_201_CREATED)
def reopen(
    item_id: int,
    body: ReopenIn | None = None,
    state: AppState = Depends(get_state),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Send the thread back to Claude as a new message (ADR 0018); 409 while one waits."""
    try:
        rev = git.head(state.sources.get(fb.root(conn, item_id)["source"]).root)
    except (LookupError, git.GitError):
        rev = None
    return fb.reopen(conn, item_id, body.body if body else None, doc_rev=rev)


@router.patch("/{item_id}")
def patch(item_id: int, body: PatchIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    item = fb.get(conn, item_id)
    if body.body is not None:
        item = fb.edit_body(conn, item_id, body.body)
    # "resolved" is for the whole thread, so it applies even when this item already is.
    if body.status is not None and (body.status == "resolved" or body.status != item["status"]):
        item = fb.set_status(conn, item_id, body.status)
    return item


@router.delete("/{item_id}/thread", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(item_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> Response:
    """Delete the whole thread this item belongs to, answered or resolved ones included."""
    fb.delete_thread(conn, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(item_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> Response:
    fb.delete(conn, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
