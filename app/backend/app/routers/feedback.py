"""Feedback API: what the browser uses to write prompts, reviews and comments for Claude."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator

from ..deps import AppState, get_conn, get_state
from ..paths import MARKDOWN_EXT, resolve_doc_path, validate_rel_path
from ..services import feedback as fb
from ..services import git

router = APIRouter(prefix="/api/feedback")

Kind = Literal["prompt", "review", "comment"]
Status = Literal["open", "in_progress", "answered", "resolved"]


class Anchor(BaseModel):
    heading: str | None = Field(None, max_length=300)
    lines: tuple[int, int] | None = None
    quote: str | None = Field(None, max_length=2000)

    @field_validator("lines")
    @classmethod
    def _lines(cls, v: tuple[int, int] | None) -> tuple[int, int] | None:
        if v is not None and not (1 <= v[0] <= v[1] <= 1_000_000):
            raise ValueError("lines must be [start, end] with 1 <= start <= end")
        return v


class FeedbackIn(BaseModel):
    kind: Kind
    body: str = Field(min_length=1, max_length=20_000)
    doc_path: str | None = Field(None, max_length=512)
    anchor: Anchor | None = None
    parent_id: int | None = None

    @model_validator(mode="after")
    def _anchor_needs_doc(self) -> FeedbackIn:
        if self.anchor is not None and self.doc_path is None:
            raise ValueError("an anchor needs a doc_path")
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
    doc_path = None
    if item.doc_path is not None:
        resolve_doc_path(state.settings.docs_root, item.doc_path, allowed={MARKDOWN_EXT})
        doc_path = validate_rel_path(item.doc_path)
    try:
        rev = git.head(state.settings.repo_root)
    except git.GitError:
        rev = None
    anchor = item.anchor.model_dump(exclude_none=True) if item.anchor else None
    return fb.create(
        conn,
        kind=item.kind,
        body=item.body,
        doc_path=doc_path,
        anchor=anchor or None,
        parent_id=item.parent_id,
        doc_rev=rev,
    )


@router.get("")
def list_items(
    status_: Status | None = Query(None, alias="status"),
    doc_path: str | None = None,
    kind: Kind | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[dict]:
    return fb.list_items(conn, status=status_, doc_path=doc_path, kind=kind)


@router.get("/summary")
def summary(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return fb.summary(conn)


@router.get("/{item_id}")
def get_item(item_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return {"item": fb.get(conn, item_id), "thread": fb.thread(conn, item_id)}


@router.post("/{item_id}/claim")
def claim(item_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return fb.claim(conn, item_id)


@router.post("/{item_id}/reply")
def reply(item_id: int, body: ReplyIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return fb.reply(conn, item_id, body.reply)


@router.patch("/{item_id}")
def patch(item_id: int, body: PatchIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    item = fb.get(conn, item_id)
    if body.body is not None:
        item = fb.edit_body(conn, item_id, body.body)
    if body.status is not None and body.status != item["status"]:
        item = fb.set_status(conn, item_id, body.status)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(item_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> Response:
    fb.delete(conn, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
