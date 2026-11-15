"""Feedback items: prompts, reviews and comments that reach Claude through /inbox.

Status flow: open -> in_progress (claim) -> answered (reply) -> resolved,
with release (in_progress -> open), reopen (answered/resolved -> open) and
dismiss (open -> resolved). Every transition is one conditional UPDATE, so
two claims of the same item can't both succeed.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..db import iso, utcnow, write_tx

KINDS = ("prompt", "review", "comment")
STATUSES = ("open", "in_progress", "answered", "resolved")

# (from, to) pairs a PATCH may request. Claim and reply have their own calls.
PATCH_TRANSITIONS = {
    ("in_progress", "open"),  # release
    ("answered", "open"),  # reopen
    ("resolved", "open"),  # reopen
    ("answered", "resolved"),  # resolve
    ("open", "resolved"),  # dismiss
}


class FeedbackNotFound(LookupError):
    pass


class FeedbackConflict(RuntimeError):
    """The item exists but isn't in a state that allows this action."""


def _row(r: sqlite3.Row) -> dict[str, Any]:
    d = dict(r)
    d["anchor"] = json.loads(d["anchor"]) if d["anchor"] else None
    return d


def get(conn: sqlite3.Connection, item_id: int) -> dict[str, Any]:
    r = conn.execute("SELECT * FROM feedback WHERE id = ?", (item_id,)).fetchone()
    if r is None:
        raise FeedbackNotFound(item_id)
    return _row(r)


def _status_of(conn: sqlite3.Connection, item_id: int) -> str:
    r = conn.execute("SELECT status FROM feedback WHERE id = ?", (item_id,)).fetchone()
    if r is None:
        raise FeedbackNotFound(item_id)
    return r["status"]


def create(
    conn: sqlite3.Connection,
    *,
    kind: str,
    body: str,
    doc_path: str | None = None,
    anchor: dict | None = None,
    parent_id: int | None = None,
    doc_rev: str | None = None,
) -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    now = iso(utcnow())
    with write_tx(conn):
        if parent_id is not None:
            _status_of(conn, parent_id)
        cur = conn.execute(
            "INSERT INTO feedback (kind, doc_path, anchor, body, parent_id, doc_rev, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (kind, doc_path, json.dumps(anchor) if anchor else None, body, parent_id, doc_rev, now, now),
        )
        item_id = cur.lastrowid
    assert item_id is not None
    return get(conn, item_id)


def list_items(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    doc_path: str | None = None,
    kind: str | None = None,
    limit: int = 500,
) -> list[dict]:
    sql = "SELECT * FROM feedback WHERE 1=1"
    args: list[Any] = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if doc_path:
        sql += " AND doc_path = ?"
        args.append(doc_path)
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    args.append(limit)
    return [_row(r) for r in conn.execute(sql, args).fetchall()]


def summary(conn: sqlite3.Connection) -> dict[str, int]:
    counts = dict.fromkeys(STATUSES, 0)
    for r in conn.execute("SELECT status, count(*) AS n FROM feedback GROUP BY status"):
        counts[r["status"]] = r["n"]
    return counts


def thread(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    """The whole conversation an item belongs to: its root and every follow-up, oldest first."""
    item = get(conn, item_id)
    root = item
    seen = {root["id"]}
    while root["parent_id"] is not None and root["parent_id"] not in seen:
        try:
            root = get(conn, root["parent_id"])
        except FeedbackNotFound:
            break
        seen.add(root["id"])
    items = [root]
    frontier = [root["id"]]
    visited = {root["id"]}
    while frontier:
        marks = ",".join("?" * len(frontier))
        rows = conn.execute(f"SELECT * FROM feedback WHERE parent_id IN ({marks})", frontier).fetchall()
        frontier = []
        for r in rows:
            if r["id"] not in visited:
                visited.add(r["id"])
                items.append(_row(r))
                frontier.append(r["id"])
    return sorted(items, key=lambda d: (d["created_at"], d["id"]))


def _transition(conn: sqlite3.Connection, item_id: int, frm: str, to: str, extra: dict | None = None) -> dict:
    now = iso(utcnow())
    sets = {"status": to, "updated_at": now, **(extra or {})}
    assignments = ", ".join(f"{k} = ?" for k in sets)
    with write_tx(conn):
        cur = conn.execute(
            f"UPDATE feedback SET {assignments} WHERE id = ? AND status = ?",
            (*sets.values(), item_id, frm),
        )
        if cur.rowcount == 0:
            status = _status_of(conn, item_id)
            raise FeedbackConflict(f"item {item_id} is {status}, expected {frm}")
    return get(conn, item_id)


def claim(conn: sqlite3.Connection, item_id: int) -> dict:
    return _transition(conn, item_id, "open", "in_progress", {"claimed_at": iso(utcnow())})


def reply(conn: sqlite3.Connection, item_id: int, text: str) -> dict:
    if not text.strip():
        raise ValueError("the reply is empty")
    return _transition(
        conn, item_id, "in_progress", "answered", {"reply": text, "answered_at": iso(utcnow())}
    )


def release(conn: sqlite3.Connection, item_id: int) -> dict:
    return _transition(conn, item_id, "in_progress", "open", {"claimed_at": None})


def set_status(conn: sqlite3.Connection, item_id: int, to: str) -> dict:
    current = _status_of(conn, item_id)
    if (current, to) not in PATCH_TRANSITIONS:
        raise FeedbackConflict(f"can't change {current} to {to}")
    extra = {"claimed_at": None} if to == "open" else None
    return _transition(conn, item_id, current, to, extra)


def edit_body(conn: sqlite3.Connection, item_id: int, body: str) -> dict:
    with write_tx(conn):
        cur = conn.execute(
            "UPDATE feedback SET body = ?, updated_at = ? WHERE id = ? AND status = 'open'",
            (body, iso(utcnow()), item_id),
        )
        if cur.rowcount == 0:
            raise FeedbackConflict(
                f"item {item_id} is {_status_of(conn, item_id)}; only open items can be edited"
            )
    return get(conn, item_id)


def delete(conn: sqlite3.Connection, item_id: int) -> None:
    with write_tx(conn):
        cur = conn.execute("DELETE FROM feedback WHERE id = ? AND status = 'open'", (item_id,))
        if cur.rowcount == 0:
            raise FeedbackConflict(
                f"item {item_id} is {_status_of(conn, item_id)}; only open items can be deleted"
            )
